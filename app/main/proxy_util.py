from urllib.request import urlopen
from contextlib import closing
import json
import csv
import asyncio
import os
from proxybroker import Broker
from random import randrange

# For testing please override the path to the proxy list with the actual one. eg.:
# proxy_util.proxy_path = os.path.abspath(os.path.expanduser("~/") + "PycharmProjects/STW/static/")
proxy_path = os.path.abspath(os.path.expanduser("~/") + "StampTheWeb/static/")


def get_proxy_location(ip_address):
    """
    Looks up the location of an IP Address and returns the two-letter ISO country code.

    :author: Sebastian
    :param ip_address: The IP Address to get the location for.
    :return: The country_code as two letter string
    """
    # Automatically geolocate the connecting IP
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
    country_list = []
    with open(proxy_path + "/proxy_list.tsv", "r", encoding="utf8") as tsv:
        for line in csv.reader(tsv, delimiter="\t"):
            country_list.append(line[0])

        country = country_list[randrange(0, len(country_list))]
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
    # TODO check proxy_list for active proxies or use python package like getprox or proxybroker to check or get them.
    proxy_list = []
    if update:
        proxy_list = update_proxies(prox_loc)
    else:
        with open(proxy_path + "/proxy_list.tsv", "rt", encoding="utf8") as tsv:
            for line in csv.reader(tsv, delimiter="\t"):
                proxy_list.append([line[0], line[1], None])
        if prox_loc:
            prox = get_one_proxy(prox_loc)
            if prox:
                proxy_list.append([prox_loc, prox, None])

    return proxy_list


def update_proxies(prox_loc=None):
    """
    Checks the proxies stored in the proxy_list.tsv file. If there are proxies that are inactive,
    new proxies from that country are gathered and stored in the file instead.

    :author: Sebastian
    :param prox_loc: A new location to be added to the countries already in use. Defaults to None.
    :return: A list of active proxies.
    """
    with open(proxy_path + "/proxy_list.tsv", "r", encoding="utf8") as tsv:
        country_list = []
        for line in csv.reader(tsv, delimiter="\t"):
            country_list.append(line[0])
        if prox_loc:
            country_list.append(prox_loc)
        country_list = set(country_list)
        proxy_list = gather_proxies(country_list)

    with open(proxy_path + "/proxy_list.tsv", "w", encoding="utf8") as tsv:
        # tsv.writelines([proxy[0] + "\t" + proxy[1] for proxy in proxy_list])
        for proxy in proxy_list:
            tsv.write("{}\t{}\n".format(proxy[0], proxy[1]))
    return proxy_list


def gather_proxies(countries):
    """
    This method uses the proxybroker package to asynchronously get two new proxies per specified country
    and returns the proxies as a list of country and proxy.

    :author: Sebastian
    :param countries: The ISO style country codes to fetch proxies for. Countries is a list of two letter strings.
    :return: A list of proxies that are themself a list with  two paramters[Location, proxy address].
    """
    # TODO !! May take more than 45 minutes !!
    proxy_list = []
    types = ['HTTP']
    for country in countries:
        loop = asyncio.get_event_loop()

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


def get_one_proxy(country):
    types = ['HTTP']
    loop = asyncio.get_event_loop()

    proxies = asyncio.Queue(loop=loop)
    broker = Broker(proxies, loop=loop)

    loop.run_until_complete(broker.find(limit=1, countries=country, types=types))

    while True:
        proxy = proxies.get_nowait()
        if proxy is None:
            break
        print(str(proxy))
        return "{}:{}".format(proxy.host, str(proxy.port))
    return None
