import threading
import os
import re
import requests
import chardet
import csv
import asyncio
from proxybroker import Broker
from random import randrange
from flask import current_app as app
from selenium import webdriver
from warcat.model import WARC
from bs4 import BeautifulSoup
import ipfsApi as ipfs
import shutil
from readability.readability import Document
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.common.exceptions import TimeoutException

exitFlag = 0
urlPattern = re.compile('^(https?|ftp)://[^\s/$.?#].[^\s]*$')
ipfs_Client = ipfs.Client('127.0.0.1', 5001)
js_path = os.path.abspath(os.path.expanduser("~/") + '/bin/phantomjs/lib/phantom/bin/phantomjs')
base_path = 'app/pdf/'


class DownloadThread(threading.Thread):
    """
    Class that subclasses threading.Thread in order to start a new thread with a new download job.
    To check whether a proxy was used check self.html which is None if a proxy was and is to be used.
    If html is provided then a proxy is not required.

    :author: Sebastian
    """
    def __init__(self, thread_id, url=None, prox=None, prox_loc=None, base_path='app/pdf/', html=None):
        """
        Default constructor for the DownloadThread class, that initializes the creation of a new download job in a
        separate thread.

        :author: Sebastian
        :param thread_id: The ID of this thread.
        :param url: The URL that is to be downloaded in this job.
        :param prox: The proxy to use when downloading from the before specified URL.
        :param prox_loc: The proxy location.
        :param base_path: The path to store the temporary files in.
        :param html: Defaults to None and needs only to be specified if a user input of an HTML was given by the
        StampTheWeb extension.
        """
        threading.Thread.__init__(self)
        app.logger.info("Starting Thread")
        self.threadID = thread_id
        self.url = url
        self.html = html
        self.prox_loc = prox_loc
        self.proxy = prox
        self.basepath = base_path
        self.path = base_path + "temporary"
        self.ipfs_hash = None
        self.images = dict()

        if not self.html:
            app.logger.info("Using Proxy: " + prox)
            self.phantom = self.initialize(prox)

        if not os.path.exists(self.path):
            os.mkdir(self.path)
        else:
            shutil.rmtree(self.path)
            os.mkdir(self.path)
        self.path = self.path + "/" + str(thread_id) + "/"
        app.logger.info("initialized a new Thread:" + str(self.threadID))
        os.mkdir(self.path)

    def initialize(self, proxy):
        """
        Helper method that initializes the PhantomJS Headless browser and sets the proxy.

        :author: Sebastian
        :param proxy: The proxy to set.
        :return: The PhantomJS driver object.
        """
        dcap = dict(DesiredCapabilities.PHANTOMJS)
        dcap[
            "phantomjs.page.settings.userAgent"] = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/53 " \
                                                   "(KHTML, like Gecko) Chrome/15.0.87"
        phantom = webdriver.PhantomJS(js_path, desired_capabilities=dcap)
        phantom.capabilities["acceptSslCerts"] = True
        if proxy:
            phantom.capabilities["proxy"] = {"proxy": proxy,
                                         "proxy-type": "http"}
        max_wait = 30

        phantom.set_window_size(1024, 768)
        phantom.set_page_load_timeout(max_wait)
        phantom.set_script_timeout(max_wait)
        return phantom

    def run(self):
        """
        Run the initialized thread and start the download job.

        :author: Sebastian
        :return: The downloaded HTML with picture references replaced by their IPFS hash so that they are uniquely
        identified for further submissions, hash creations and comparisons
        """
        print("Started Thread" + str(self.threadID))
        try:
            self.download()
        except TimeoutException:
            app.logger.error("Couldn't reach website through proxy, trying again with new proxy")
            self.initialize(get_rand_proxy(self.prox_loc))
            self.download()
            # TODO set new proxy and try again

        return self.ipfs_hash
        # TODO download html and images include in warc

    def download(self):
        """
        Orchestrates the download job of this thread. Time consuming method that downloads the html via phantomJS.
        Makes the assumption that if a html is provided no proxy is set.

        :author: Sebastian
        """
        if not self.html:
            print("Downloading without html, proxy is set to: " + str(self.proxy))
            self.phantom.get(self.url)
            self.html = str(self.phantom.page_source)

        self.html = preprocess_doc(Document(self.html, min_text_length=5))
        print("Preprocessed doc:\n" + self.html)
        soup = BeautifulSoup(self.html, "lxml")

        # self.proxy is None if html was given to DownloadThread.
        self.images = self.load_images(soup, self.proxy)
        with open(self.path + "/page_source.html", "w") as f:
            f.write(self.html)
        # Add folder to ipfs # TODO best place to zip files if necessary
        """not necessary to add folder to ipfs since the html has
        the ipfs_hash of the images stored withing the img tags."""
        self.ipfs_hash = self.add_to_ipfs(self.path)
        print("Downloaded and submitted everything to ipfs: \n" + self.ipfs_hash)
        shutil.rmtree(self.path)

    def load_images(self, soup, proxy=None):
        """
        Takes a BeautifulSoup Object and downloads all the images referenced in the HTML of the BS object.
        The method also changes the HTML, since it adds a tag attribute of ipfs-src with the hash returned
        from ipfs as value and thereby uniquely identifies the image. Thus pictures are taken into account when the Hash
        is created for the HTML.

        :author: Sebastian
        :param soup: The BeautifulSoup object of the html file.
        :param proxy: The proxy if a proxy is used otherwise it defaults to none.
        :return: A list of file names of the pictures that were downloaded and submitted to ipfs.
        """
        print("Loading images")
        files = dict()
        img_ctr = 0
        current_directory = os.getcwd()
        os.chdir(self.basepath)
        header = {'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.9; rv:32.0) Gecko/20100101 Firefox/32.0'}

        for img in soup.find_all(['amp-img', 'img']):
            try:
                res = self.down_image(img, img_ctr, header, proxy)
            except NameError:
                # the picture in the url was not retrievable, continue to next image
                continue
            except ConnectionError as con:
                print("Could not connect to retrieve image. Trying again with proxy")
                # TODO start image load again with different proxy

            filename = 'img' + str(img_ctr)
            img_ctr += 1
            if res.status_code == 200:
                with open(filename, 'wb') as f:
                    for chunk in res.iter_content(1024):
                        f.write(chunk)
                image_hash = self.add_to_ipfs(filename)
                print("Added image to ipfs: " + filename)
                img['ipfs-src'] = image_hash
                files[img_ctr] = {"filename": filename,
                                  "hash":     image_hash
                                  }

        print("Downloaded images: " + str(files))
        self.html = str(soup.find("html"))
        os.chdir(current_directory)
        return files

    def down_image(self, img, counter, header, proxy=None):
        """
        Downloads only one image. Helper Method to load_images

        :author: Sebastian
        :param img: The img tag object.
        :param counter: A counter to set the name of the img locally
        :param header: The header that is used if the image is retrieved via proxy
        :param proxy: The proxy that is to be used to download the image. Defaults to None, to download it directly.
        :return: A Response object with the response status and the image to store.
        """
        tag = None
        if urlPattern.match(img['src']):
            tag = img['src']
        elif img['data-full-size'] and urlPattern.match(img['data-full-size']):
            tag = img['data-full-size']
        elif img['data-original'] and urlPattern.match(img['data-original']):
            tag = img['data-original']
        elif img['data'] and urlPattern.match(img['data']):
            tag = img['data']
        else:
            print("An image did not have a html specification url: \n" + img)
            raise NameError("An image did not have a html specification url: \n" + img)

        print("Downloading image: " + tag)
        if proxy:
            try:
                """
                First we try to get the image without a proxy and only if that fails the proxy is used.
                Alternatively or possibly another exception needs to be handled if MaxRetryError occurs
                due to too many connections to proxy.
                """
                res = requests.get(tag, stream=True)
                print("Requested image without proxy.")
            except ConnectionRefusedError as con:
                print("Could not request image due to: " + con.strerror + "\ntrying with proxy: " + proxy)
                res = requests.get(tag, stream=True, proxies={"http": "http://" + proxy}, headers=header)
        else:
            res = requests.get(tag, stream=True)
        return res

    def add_to_ipfs(self, fname):
        """
            Helper method that submits a file to IPFS and returns the resulting hash,
            that describes the address of the file on IPFS.

            :author: Sebastian
            :param fname: The path to the File to get the hash for.
            :return: Returns the Hash of the file.
        """
        if not os.path.isdir(fname):
            res = ipfs_Client.add(fname)
            print("IPFS result: " + str(res))
            return res['Hash']
        else:
            # TODO zip files and add zip to ipfs
            res = ipfs_Client.add(fname)[0]
            print("IPFS result: " + str(res))
            return res['Hash']


def preprocess_doc(doc):
    """
    Calculate hash for given html document. The html document is expected as a document object from readability package.

    :author: Sebastian
    :param doc: html doc to preprocess
    :returns: The preprocessed html as a String.
    """
    print('Preprocessing Document')

    # Detect the encoding of the html, if not detectable use utf-8 as default.
    encoding = chardet.detect(doc.content().encode()).get('encoding')
    if not encoding:
        print("Using default encoding utf-8")
        encoding = 'utf-8'
    doc.encoding = encoding

    head = '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1' \
           '-transitional.dtd">\n' + '<head>\n' + \
           '<meta http-equiv="Content-Type" content="text/html" ' \
           'charset="' + encoding + '">\n' + '</head>\n' + '<body>\n' \
           + '<h1>' + doc.title().split(sep='|')[0] + '</h1>'

    text = head + doc.summary()[12:]
    # sometimes some tags get messed up and need to be translated back
    # TODO could probably be done in one iteration.
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    print('Preprocessing done')
    return text


def get_rand_proxy(prox_loc=None):
    """
    Retrieve one random proxy.

    :author: Sebastian
    :param prox_loc: The location of the proxy to be retrieved.
    :return: One randomly chosen proxy
    """
    proxy_list = get_proxy_list()
    if prox_loc:
        proxy_list = [proxy for proxy in proxy_list if proxy[0] == prox_loc]
        if len(proxy_list) == 0:
            broker = Broker

    prox_num = randrange(0, len(proxy_list))
    return proxy_list[prox_num][1]


def get_proxy_list(update=False, prox_loc=None):
    """
    Get a ist of available proxies to use.
    # TODO check the proxy status.

    :author: Sebastian
    :param update: Is set to True by default. If set to False the proxy list will not be checked for inactive proxies.
    :return: A list of lists with 3 values representing proxies [1] with their location [0].
    """
    # TODO check proxy_list for active proxies or use python package like getprox or proxybroker to check or get them.
    proxy_list = []
    if update:
        proxy_list = update_proxies(prox_loc)
    else:
        index = 0
        with open("static/proxy_list.tsv", "rt", encoding="utf8") as tsv:
            for line in csv.reader(tsv, delimiter="\t"):
                proxy_list[index] = [line[0], line[1], None]
                index += 1

    return proxy_list


def update_proxies(prox_loc=None):
    """
    Checks the proxies stored in the proxy_list.tsv file. If there are proxies that are inactive,
    new proxies from that country are gathered and stored in the file instead.

    :author: Sebastian
    :return: A list of active proxies
    """
    with open("static/proxy_list.tsv", "r+", encoding="utf8") as tsv:
        country_list = []
        for line in csv.reader(tsv, delimiter="\t"):
            country_list.append(line[0])
        if prox_loc:
            country_list.append(prox_loc)
        proxy_list = gather_proxies(country_list)
        tsv.truncate(0)
        tsv.writelines([proxy[0] + "\t" + proxy[1] for proxy in proxy_list])
    return proxy_list


def gather_proxies(countries):
    """
    This method uses the proxybroker package to asynchronously get two new proxies per specified country
    and returns the proxies as a list of country and proxy.

    :param countries: The ISO style country codes to fetch proxies for. Countries is a list of two letter strings.
    :return: A list of proxies that are themself a list with  two paramters[Location, proxy address].
    """
    proxy_list = []
    types = [('HTTP', ('Anonymous', 'High'))]
    for country in countries:
        loop = asyncio.get_event_loop()

        proxies = asyncio.Queue(loop=loop)
        broker = Broker(proxies, loop=loop)

        loop.run_until_complete(broker.find(limit=2, countries=country, types=types))

        while True:
            proxy = proxies.get_nowait()
            if proxy is None:
                break
            proxy_list.append([country, proxy.host + ":" + str(proxy.port)])
    return proxy_list
