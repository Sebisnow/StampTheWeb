from datetime import datetime
from urllib.parse import urlparse
import csv
import asyncio
import os
import re
from aiohttp import ClientError
from freeproxy import from_hide_my_ip, from_cyber_syndrome, from_free_proxy_list, from_xici_daili
import requests
from proxybroker import Broker
from random import randrange
import geoip
import socket
# TODO instead of  proxyfile use db table for active proxies
# from .. import db

# For local testing please override the path to the proxy list with the actual one. eg.:
#static_path = os.path.abspath(os.path.expanduser("~/") + "PycharmProjects/STW/static")

static_path = os.path.abspath(os.path.expanduser("~/") + "StampTheWeb/static")
if not os.path.exists(static_path):
    static_path = "/home/ubuntu/StampTheWeb/static"
proxy_path = static_path + "/proxy_list.tsv"
country_path = static_path + "/country_codes.csv"
# regular expression to check URL, see https://mathiasbynens.be/demo/url-regex
url_specification = re.compile('^(https?|ftp)://[^\s/$.?#].[^\s]*$')
base_path = 'app/pdf/'
default_event_loop = None
logger = print
ip_check_url = "http://httpbin.org/ip"


def get_one_proxy(location=None, level=0):
    """
    Fetches one proxy using proxybroker. Handles RuntimeError of proxybroker. If it fails twice the proxy list is used
    to retrieve a proxy from the location.
    If no proxies from that location are available then it fetches a random proxy.

    :author: Sebastian
    :param location: Two letter iso country code to fetch a proxy from. If not present fetches a random active proxy
     from the static proxy list.
    :param level: for internal use if this is called recursively
    :return: Returns the location of the proxy together with the proxy.
    """
    try:
        if location is None:
            prox = get_one_random_proxy()
            return prox[0], prox[1]
        else:
            try:
                proxy = get_one_specific_proxy(location)
            except RuntimeError as e:
                asyncio.set_event_loop(asyncio.new_event_loop())
                logger("Error {}, trying again.".format(e))
                proxy = get_one_specific_proxy(location)
    except RuntimeError as run:
        logger("Error on second try {}, trying again with alternative.".format(run))
        proxy = _get_one_proxy_alternative(location)
        if proxy is None:
            logger("No active proxy found, trying a random proxy")
            if level > 0:
                return None, None
            loc, prox = get_one_proxy(level=1)
            if prox is None:
                logger("Found no proxy at all, trying without")
                return None, None
            location, proxy = prox[0], prox[1]
    return location, proxy


def get_rand_proxy(proxy_list=None, level=0):
    """
    Retrieve one random proxy from the proxy list. Recursively fetches a random, working proxy to return.
    Tries ten times before returning with no result.

    :author: Sebastian
    :return: One randomly chosen proxy
    """
    if level > 9:
        return None
    logger("Getting a random, active proxy {}.".format(level))
    proxies = proxy_list or get_proxy_list()
    prox = proxies[randrange(0, len(proxies))]
    if is_proxy_alive(prox[1], 3):
        return prox
    else:
        proxies.remove(prox)
        return get_rand_proxy(proxies, level=level+1)


def get_one_specific_proxy(country, types='HTTP'):
    """
    Find one new, working proxy from the specified country. Run time of this method depends heavily on the country
    specified as for some countries it is hard to find proxies (e.g. Myanmar).

    :author: Sebastian
    :param country: Two-letter ISO formatted country code. If a lookup is needed before calling this method, please
    consult /static/country_codes.csv.
    :param types: The type of proxy to search for as a list of strings. Defaults to HTTP.
    If only one type should be specified a string like "HTTPS" will also work.
    Other possibilities are HTTPS, SOCKS4, SOCKS5. E.g. types=['HTTP, HTTPS']
    :return: A string containing the newly found proxy from the specified country in <Proxy IP>:<Port> notation.
    :raises RuntimeError if proxybroker has problems with its loop. Catch it and start new event_loop.
    """
    logger("Fetching one proxy from: {}".format(country))
    if type(types) is not list:
        types = [types]
    loop = asyncio.get_event_loop()

    proxies = asyncio.Queue(loop=loop)
    broker = Broker(proxies, loop=loop)
    loop.run_until_complete(broker.find(limit=1, countries=[country], types=types))

    while True:
        proxy = proxies.get_nowait()
        if proxy is None:
            break
        fetched_proxy = "{}:{}".format(proxy.host, str(proxy.port))
        logger("Proxy from {} is: {}".format(country, fetched_proxy))
        _add_to_proxy_list(country, fetched_proxy)
        return fetched_proxy
    return None


def get_one_random_proxy(types='HTTP'):
    """
    Find one new, working proxy from any country.

    :author: Sebastian
    :param types: The type of proxy to search for as a list of strings. Defaults to HTTP.
    If only one type should be specified a string like "HTTPS" will also work.
    Other possibilities are HTTPS, SOCKS4, SOCKS5. E.g. types=['HTTP, HTTPS']
    :return:The newly found proxys location (two-letter-iso country code) as well as the
    proxy (in <Proxy IP>:<Port> notation).
    """
    logger("Fetching one random proxy")
    if type(types) is not list:
        types = [types]
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        logger("----New event loop")
        loop = asyncio.new_event_loop()

    proxies = asyncio.Queue(loop=loop)
    broker = Broker(proxies, loop=loop)
    loop.run_until_complete(broker.find(limit=1, types=types))

    while True:
        proxy = proxies.get_nowait()
        if proxy is None:
            break
        fetched_proxy = "{}:{}".format(proxy.host, str(proxy.port))
        country = proxy.geo["code"]
        logger("Proxy from {} is: {}".format(country, fetched_proxy))
        _add_to_proxy_list(country, fetched_proxy)
        return country, fetched_proxy
    return None, None


def get_proxy_list(update=False, prox_loc=None):
    """
    Get a list of available proxies to use from the proxy list.
    # TODO check the proxy status.

    :author: Sebastian
    :param prox_loc: Defaults to None. If specified only proxies from this location are taken into account.
    :param update: Is set to False by default. If set to True the proxy list will be fetched again.
    This takes quite a while!
    :return: A list of lists with 3 values representing proxies [1] with their location [0] and
    None(Waqar uses third value).
    """
    logger("Getting the proxylist")
    proxy_list = []
    if update:
        proxy_list = update_proxies()
    else:
        with open(proxy_path, "rt", encoding="utf8") as tsv:
            for line in csv.reader(tsv, delimiter="\t"):
                if prox_loc is None or prox_loc == line[0]:
                    proxy_list.append([line[0], line[1], None])

    logger("Returning the proxy list")
    return proxy_list


def update_proxies():
    """
    Gather new proxies to be stored in the static proxy file.

    :author: Sebastian
    :return: A list of active proxies.
    """
    logger("Start updating the proxy list")
    logger("Getting the proxies now. That may take quite a while!")
    try:
        try:
            proxy_list = gather_proxies()
        except RuntimeError as e:
            logger(str(e))
            asyncio.set_event_loop(asyncio.new_event_loop())
            proxy_list = gather_proxies()
    except RuntimeError or ClientError or OSError or UnicodeDecodeError as e:
        logger("Could not fetch new Proxies due to {}, doing it the long way!".format(e))
        # TODO Does not take country list into account - Fallback not needed anymore until next error in proxybroker
        # package
        proxy_list = _gather_proxies_alternative()
    logger("All proxies gathered!")
    return _write_proxies(_clean_proxy_list(proxy_list))


def _clean_proxy_list(proxy_list):
    """
    Cleans the proxy list so that only two proxies per country remain.
    :param proxy_list: The list of proxies
    :return: A list of proxies where each country provides max two proxies.
    """
    country_dict = dict()
    cleaned_proxy_list = list()
    for proxy in proxy_list:
        if proxy[0] not in country_dict.keys():
            country_dict[proxy[0]] = 1
            cleaned_proxy_list.append(proxy)
        elif country_dict[proxy[0]] == 1:
            country_dict[proxy[0]] = 2
            cleaned_proxy_list.append(proxy)
    return cleaned_proxy_list


def update_proxies_with_country(prox_loc=None):
    """
    Checks the proxies stored in the proxy_list.tsv file. If there are proxies that are inactive,
    new proxies from that country are gathered and stored in the file instead.

    :author: Sebastian
    :param prox_loc: A new location to be added to the countries already in use. Defaults to None.
    :return: A list of active proxies.
    """
    logger("Start updating the proxy list")
    country_list = []
    with open(proxy_path, "r", encoding="utf8") as tsv:
        for line in csv.reader(tsv, delimiter="\t"):
            country_list.append(line[0])
        if prox_loc:
            country_list.append(prox_loc)
        country_list = set(country_list)
    logger(country_list)
    logger("Getting the proxies now. That may take quite a while!")
    try:
        try:
            proxy_list = gather_proxies_by_country(country_list)
        except RuntimeError as e:
            logger(str(e))
            asyncio.set_event_loop(asyncio.new_event_loop())
            proxy_list = gather_proxies_by_country(country_list)
    except RuntimeError or ClientError or OSError or UnicodeDecodeError as e:
        logger("Could not fetch new Proxies due to {}, doing it the long way!".format(e))
        # TODO Does not take country list into account - Fallback not needed anymore until next error in proxybroker
        # package
        proxy_list = _gather_proxies_alternative()
    logger("All proxies gathered!")
    return _write_proxies(proxy_list)


def _write_proxies(proxy_list):
    """
    Write proxies to the static file in the proxy_path.

    :author: Sebastian
    :param proxy_list: The list of two-itemed-lists of proxies with their country as first item in the list
    and the proxy itself as second item in the list.
    :return: THe proxy_list that was the input.
    """
    with open(proxy_path, "w", encoding="utf8") as tsv:
        # tsv.writelines([proxy[0] + "\t" + proxy[1] for proxy in proxy_list])
        for proxy in proxy_list:
            tsv.write("{}\t{}\n".format(proxy[0], proxy[1]))
            logger("writing proxy {} from {} to file.".format(proxy[1], proxy[0]))
    logger("All {} proxies wrote to file!".format(len(proxy_list)))
    return proxy_list


def gather_proxies():
    proxy_list = list()
    types = ['HTTP']
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        logger("----New event loop")
        loop = asyncio.new_event_loop()

    proxies = asyncio.Queue(loop=loop)
    broker = Broker(proxies, loop=loop)
    loop.run_until_complete(broker.find(limit=100, types=types))
    with open("{}/temp.csv".format(static_path), "w"):
        pass  # if file is present overwrite it

    while True:
        proxy = proxies.get_nowait()
        if proxy is None:
            break
        logger(str(proxy))
        with open("{}/temp.csv".format(static_path), "a") as temp:
            temp.write("{}\t{}\n".format(proxy.geo["code"], "{}:{}".format(proxy.host, str(proxy.port))))
        proxy_list.append([proxy.geo["code"], "{}:{}".format(proxy.host, str(proxy.port))])

    return proxy_list


def gather_proxies_by_country(countries):
    """
    This method uses the proxybroker package to asynchronously get two new proxies per specified country
    and returns the proxies as a list of country and proxy.

    :author: Sebastian
    :param countries: The ISO style country codes to fetch proxies for. Countries is a list of two letter strings.
    :return: A list of proxies that are themselves a list with  two paramters[Location, proxy address].
    """
    # TODO !! May take more than 45 minutes !! Run in separate thread?
    proxy_list = []
    types = ['HTTP']
    for country in countries:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            logger("----New event loop")
            loop = asyncio.new_event_loop()

        proxies = asyncio.Queue(loop=loop)
        broker = Broker(proxies, loop=loop)
        loop.run_until_complete(broker.find(limit=2, countries=country, types=types))
        with open("{}/temp.csv".format(static_path), "w"):
            pass  # if file is present overwrite it

        while True:
            proxy = proxies.get_nowait()
            if proxy is None:
                break
            logger(str(proxy))
            with open("{}/temp.csv".format(static_path), "a") as temp:
                temp.write("{}\t{}\n".format(country, "{}:{}".format(proxy.host, str(proxy.port))))
            proxy_list.append([country, "{}:{}".format(proxy.host, str(proxy.port))])
    return proxy_list


def _add_to_proxy_list(country, proxy):
    """
    Adds one proxy with the associated country to the proxy list file.

    :author: Sebastian
    :param country: ISO country code of the country.
    :param proxy: The working proxy to add to the proxy file.
    """
    with open(proxy_path, "a") as prox_file:
        prox_file.write("{}\t{}\n".format(country, proxy))


def remove_proxy(proxy):
    """
    Removes a proxy. This method should be used if a proxy on the list is broken or returns advertisement.

    :author: Sebastian
    :param proxy: The not properly working proxy to remove from the proxy file.
    """
    proxy_list = get_proxy_list()
    for prox in proxy_list:
        if prox[1] == proxy:
            proxy_list.remove(prox)
    _write_proxies(proxy_list)


def _get_one_proxy_alternative(country):
    """
    Fetches one active proxy from the specified country from the proxy list.

    :author: Sebastian
    :param country: The location of the proxy to fetch
    :return: The proxy from the specified location.
    """
    logger("Getting one proxy the alternative way")
    proxies = get_proxy_list()
    for proxy in proxies:
        if country == proxy[0] and is_proxy_alive(proxy[1], 3):
            return proxy[1]
    return None


def _gather_proxies_alternative():
    """
    Alternative to gather_proxies that uses freeproxy to gather proxies from different sources.
    It usually yields more than # # proxies. It only returns active proxies with the country code added to them.

    :return: A List of Lists. Each inner list has three values: Index 0 is the two-letter ISO country code of the proxy,
    Index 1 is the proxy with port number and index 2 is None in the beginning.
    """
    proxies = from_xici_daili() + from_cyber_syndrome() + from_hide_my_ip() + from_free_proxy_list()
    logger("{} different proxies gathered".format(str(len(proxies))))

    # add temporary stored proxies
    temp_path = "{}/temp.csv".format(static_path)
    if os.path.exists(temp_path):
        with open(temp_path, "rt", encoding="utf8") as tsv:
            for line in csv.reader(tsv, delimiter="\t"):
                logger("Add temporary proxy {} from: {}".format(line[1], line[0]))
                proxies.append(line[1])
        os.remove(temp_path)

    proxies = check_proxies(list(set(proxies)), 3)

    logger("{} working proxies gathered".format(str(len(proxies))))
    proxy_list = list()
    countries_dict = dict()

    # Store proxies in a list in a dictionary identified by their countrycode {"DE":[<proxy>, <proxy>], "AT":[<proxy>]}
    for proxy in proxies:
        country = ip_lookup_country(proxy.split(":")[0])
        if country not in countries_dict:
            countries_dict[country] = list()
        countries_dict[country].append(proxy)

    # Store max two proxies per country and append to proxy list to return
    for country in countries_dict:
        cnt = 0
        for proxy in countries_dict[country]:
            if cnt > 1:
                break
            proxy_list.append([country, proxy])
            cnt += 1

    proxy_list.sort()
    logger(str(len(countries_dict)))
    logger(proxy_list)
    return proxy_list


def check_proxies(proxies, timeout=4):
    """
    Tests a list of proxies and returns only the alive ones.
    Timeout is set to timeout seconds so some working proxies that respond slowly will also be removed.
    Due to the timeout of per default four seconds this method might take a long while to finish if many proxies
    need checking.
    #TODO Proxy gathering usually takes less than two minutes but the testing takes above an hour for all proxies.

    :author: Sebastian
    :param proxies: List of proxies that this method checks the status for.
    :param timeout: The timeout to use to check each proxy. Defaults to 4.
    :return: A list of proxies responding within timeout seconds.
    """
    # TODO could be implemented to use multithreading in order to increase speed for many proxies
    logger("Testing {} proxies".format(str(len(proxies))))
    tested_proxies = list()
    for proxy in set(proxies):
        if is_proxy_alive(proxy, timeout):
            tested_proxies.append(proxy)
    return tested_proxies


def is_proxy_alive(proxy, timeout=8):
    """
    Tests whether the specified HTTP proxy is alive. Therefore two websites are trying to be accessed "google.com",
    and "baidu.com". If either one is working the proxy is considered alive.

    :param proxy: The proxy to check. String in <Host>:<Post> notation.
    :param timeout: The timeout within which a response should be retrieved via the proxy. Defaults to 8 seconds.
    :return: Either True if the proxy is alive ot False if it is not alive.
    """
    try:
        res = requests.head("http://google.com", timeout=timeout, proxies={"http": "http://" + proxy},
                            allow_redirects=True)
        if res.status_code <= 400:
            logger("Proxy {} is alive!".format(proxy))
            return True
    except IOError:
        logger("----{} not alive".format(proxy))

    try:
        res = requests.head("http://baidu.com/", timeout=timeout, proxies={"http": "http://" + proxy},
                            allow_redirects=True)
        if res.status_code <= 400:
            logger("Proxy {} is alive!".format(proxy))
            return True
    except IOError:
        remove_proxy(proxy)
        logger("----Second check failed {} definitely not alive. Returning False".format(proxy))
    return False


def get_country_of_url(url):
    """
    Takes a URL and computes the country where this website is hosted to return.

    :author: Sebastian
    :param url: The url of the website to get the country of.
    :return: The country as two letter ISO-code of the website specified by the url.
    """
    return ip_lookup_country(_lookup_website_ip(url))


def ip_lookup_country(ip):
    """
    Looks up an IP address in the MaxMindDataBase GeoLite2-Country.mmdb to find out to which country the IP address l
    links to.
    This DB should be updated once in a while.
    (For update purposes Database downloadable from: http://dev.maxmind.com/geoip/geoip2/geolite2/

    :author: Sebastian
    :param ip: The IP address as string (-- without the port --).
    :raises ValueError: A Value Error is raised if the IP address specified does not match IP specifications.
    :return: The location of the IP address as two letter ISO-code.
    """
    database = geoip.open_database("{}/GeoLite2-Country.mmdb".format(static_path))
    if ip is None:
        return "DE"
    return database.lookup(ip).country


def _lookup_website_ip(url):
    """
    Looks up a URL to find out which IP address it is linked to.

    :author: Sebastian
    :param url: The URL to get the IP address for.
    :return: Returns the IP address of the website.
    """
    domain = urlparse(url).netloc
    try:
        return socket.gethostbyname_ex(domain)[2][0]
    except socket.gaierror as e:
        logger("Website cannot be looked up {}. Reverting to Default (Germany)".format(str(e)))
        return None


def get_country_list(full=True):
    """
    Gets a list for country codes decoding with full english name and two letter iso code.
    Or just the ones where prxies are present if full is set to False.

    :author: Sebastian
    :param full: Whether to return a list of all countries in the world (Default, Parameter is True)
    or just the list of countries where we have proxies from.
    :return: A list of lists. The inner lists consist of two parameters. Parameter at index 0 is the full, english name
    of the country described in two letters by index 1.
    """
    country_list = list()
    logger(proxy_path)
    with open(country_path, "r") as tsv:
        for line in csv.reader(tsv, delimiter=";"):
            country_list.append(line)
    if full:
        return country_list
    else:
        proxy_list = [proxy[0] for proxy in get_proxy_list()]
        countries = [country for country in country_list if country[1] in proxy_list]
        return countries


def get_proxy_from_url(url, proxy_list=None):
    """
    Find out the country of origin of a url and then fetch a proxy from that country.

    :author: Sebastian
    :param url: The URL to of the website to get a proxy for.
    :param proxy_list: Optional parameter. If not present the proxy list is read from file. If it was read from file
    before it is not necessary to do so again.
    :return: Returns the proxy as string and the country as two letter ISO code of the same country as the URL.
    """
    logger("Getting a proxy for url {}".format(url))
    if proxy_list is None:
        proxy_list = get_proxy_list()
    original_country = get_country_of_url(url)
    orig_proxy = None

    for proxy in proxy_list:
        if proxy[0] == original_country:
            orig_proxy = proxy[1]
            break
    if orig_proxy is None:
        orig_proxy = get_one_proxy(original_country)
        if orig_proxy is None:
            # The Fallback is to use a German proxy as the original
            # logger("Using Fallback to German proxy.")
            #orig_proxy = get_one_proxy("DE")
            _ = "DE"
            return None, None

    logger("Found a proxy {} from {}".format(orig_proxy, original_country))
    return orig_proxy, original_country


if __name__ == '__main__':
    update_proxies()
    logger("Finished at {}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
