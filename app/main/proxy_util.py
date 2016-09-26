from urllib.request import urlopen
from urllib.parse import urlparse
from contextlib import closing
import json
import csv
import asyncio
import os
import re
from proxybroker import Broker
from random import randrange
import geoip
import socket

# For lcoal testing please override the path to the proxy list with the actual one. eg.:
# proxy_util.proxy_path = os.path.abspath(os.path.expanduser("~/") + "PycharmProjects/STW/static/")
proxy_path = os.path.abspath(os.path.expanduser("~/") + "StampTheWeb/static/")
# regular expression to check URL, see https://mathiasbynens.be/demo/url-regex
url_specification = re.compile('^(https?|ftp)://[^\s/$.?#].[^\s]*$')
base_path = 'app/pdf/'


def get_proxy_location(ip_address):
    """
    Looks up the location of an IP Address and returns the two-letter ISO country code.

    :author: Sebastian
    :param ip_address: The IP Address to get the location for.
    :return: The country_code as two letter string
    """
    # Automatically geolocate the connecting IP
    print("Getting the proxy location of:{}".format(str(ip_address)))
    url = 'http://freegeoip.net/json/' + ip_address
    with closing(urlopen(url)) as response:
        location = json.loads(str(response.read().decode()))
        return location['country_code']


def get_rand_proxy():
    """
    Retrieve one random proxy if no location is set. if a location is set retrieve a proxy from that location

    :author: Sebastian
    :return: One randomly chosen proxy
    """
    print("Getting a random proxy.")
    country_list = []
    with open(proxy_path + "/proxy_list.tsv", "r", encoding="utf8") as tsv:
        for line in csv.reader(tsv, delimiter="\t"):
            country_list.append(line[0])

        country = country_list[randrange(0, len(country_list))]
        print("Random proxy will be from: {}".format(country))
        return get_one_proxy(country)


def get_proxy_list(update=False, prox_loc=None):
    """
    Get a ist of available proxies to use.
    # TODO check the proxy status.

    :author: Sebastian
    :param prox_loc: A location to be added to the proxy_list in ISO-2letter Format -> "DE".
    :param update: Is set to True by default. If set to False the proxy list will not be checked for inactive proxies.
    :return: A list of lists with 3 values representing proxies [1] with their location [0].
    """
    print("Getting the proxylist")
    proxy_list = []
    if update:
        proxy_list = update_proxies(prox_loc)
    else:
        with open(proxy_path + "/proxy_list.tsv", "rt", encoding="utf8") as tsv:
            for line in csv.reader(tsv, delimiter="\t"):
                proxy_list.append([line[0], line[1], None])
        if prox_loc and len(prox_loc) == 2 and type(prox_loc) == str:
            prox = get_one_proxy(prox_loc)
            if prox:
                proxy_list.append([prox_loc, prox, None])
    print("Returning the proxy list")
    return proxy_list


def update_proxies(prox_loc=None):
    """
    Checks the proxies stored in the proxy_list.tsv file. If there are proxies that are inactive,
    new proxies from that country are gathered and stored in the file instead.

    :author: Sebastian
    :param prox_loc: A new location to be added to the countries already in use. Defaults to None.
    :return: A list of active proxies.
    """
    print("Start updating the proxy list")
    country_list = []
    with open(proxy_path + "/proxy_list.tsv", "r", encoding="utf8") as tsv:
        for line in csv.reader(tsv, delimiter="\t"):
            country_list.append(line[0])
        if prox_loc:
            country_list.append(prox_loc)
        country_list = set(country_list)

    print("Getting the proxies now. That may take quite a while!")
    proxy_list = gather_proxies(country_list)
    print("All proxies gathered!")

    with open(proxy_path + "/proxy_list.tsv", "w", encoding="utf8") as tsv:
        # tsv.writelines([proxy[0] + "\t" + proxy[1] for proxy in proxy_list])
        for proxy in proxy_list:
            tsv.write("{}\t{}\n".format(proxy[0], proxy[1]))
            print("writing proxy {} from {} to file.".format(proxy[1], proxy[0]))
    print("All proxies wrote to file!")
    return proxy_list


def gather_proxies(countries):
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
            print("----New event loop")
            loop = asyncio.new_event_loop()

        proxies = asyncio.Queue(loop=loop)
        broker = Broker(proxies, loop=loop)

        loop.run_until_complete(broker.find(limit=2, countries=country, types=types))

        while True:
            proxy = proxies.get_nowait()
            if proxy is None:
                break
            print(str(proxy))
            proxy_list.append([country, "{}:{}".format(proxy.host, str(proxy.port))])
    return proxy_list


def get_one_proxy(country, types='HTTP'):
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
    """
    print("Fetching one proxy from: {}".format(country))
    if type(types) is not list:
        types = [types]

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()

    proxies = asyncio.Queue(loop=loop)
    broker = Broker(proxies, loop=loop)

    loop.run_until_complete(broker.find(limit=1, countries=country, types=types))

    while True:
        proxy = proxies.get_nowait()
        if proxy is None:
            break
        print("Proxy from {} is: {}:{}".format(country, proxy.host, str(proxy.port)))

        return "{}:{}".format(proxy.host, str(proxy.port))
    return None


def get_country_of_url(url):
    """
    Takes a URL and computes the country where this website is hosted to return.

    :author: Sebastian
    :param url: The url of the website to get the country of.
    :return: The country as two letter ISO-code of the website specified by the url.
    """
    return _ip_lookup_country(_lookup_website_ip(url))


def _ip_lookup_country(ip):
    """
    Looks up an IP address in the MaxMindDataBase GeoLite2-Country.mmdb to find out to which country the IP address l
    links to.
    This DB should be updated once in a while.
    (For update purposes Database downloadable from: http://dev.maxmind.com/geoip/geoip2/geolite2/

    :author: Sebastian
    :param ip: The IP address as string (without the port).
    :raises ValueError: A Value Error is raised if the IP address specified does not match IP specifications.
    :return: The location of the IP address as two letter ISO-code.
    """
    db = geoip.open_database("/home/sebastian/PycharmProjects/STW/static/GeoLite2-Country.mmdb")
    return db.lookup(ip).country


def _lookup_website_ip(url):
    """
    Looks up a URL to find out which IP address it is linked to.

    :author: Sebastian
    :param url: The URL to get the IP address for.
    :return: Returns the IP address of the website.
    """
    domain = urlparse(url).netloc
    return socket.gethostbyname_ex(domain)[2][0]
