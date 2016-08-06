import threading
import os
import re
import requests
from flask import current_app as app
from selenium import webdriver
from warcat.model import WARC
from bs4 import BeautifulSoup
import ipfsApi as ipfs
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

exitFlag = 0
urlPattern = re.compile('^(https?|ftp)://[^\s/$.?#].[^\s]*$')
ipfs_Client = ipfs.Client('127.0.0.1', 5001)
js_path = os.path.abspath(os.path.expanduser("~/") + '/bin/phantomjs/lib/phantom/bin/phantomjs')


class DownloadThread(threading.Thread):
    """
    Class that subclasses threading.Thread in order to start a new thread with a new download job.
    :author: Sebastian
    """
    def __init__(self, thread_id, url, prox=None, base_path='app/pdf/', html=None):
        """
        Default constructor for the DownloadThread class, that initializes the creation of a new download job in a
        separate thread.

        :author: Sebastian
        :param thread_id: The ID of this thread.
        :param url: The URL that is to be downloaded in this job.
        :param prox: The proxy to use when downloading from the before specified URL.
        :param base_path: The path to store the temporary files in.
        :param html: Defaults to None and needs only to be specified if a user input of an HTML was given by the
        StampTheWeb extension.
        """
        threading.Thread.__init__(self)
        self.threadID = thread_id
        self.url = url
        self.html = html

        if not self.html:

            self.phantom = self.initialize(prox)
        self.path = base_path + "/temporary"
        if not os.path.exists(self.path):
            os.mkdir(self.path)
        self.path = self.path + "/" + str(thread_id)
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
        self.download()
        # TODO return something?
        return self.html
        # TODO download html and images include in warc

    def download(self):
        """
        Orchestrates the download job of this thread.
        :author: Sebastian
        """
        image_files = []
        if not self.html:
            self.phantom.set_window_size(1366, 768)
            self.phantom.get(self.url)
            image_files = self.load_images(BeautifulSoup(self.phantom.page_source, "lxml"))
            with open(self.path + "/page_source.html", "w") as file:
                file.write(self.phantom.page_source)
                self.html = self.phantom.page_source
        else:
            image_files = self.load_images(BeautifulSoup(self.html, "lxml"))
            with open(self.path + "/page_source.html", "w") as file:
                file.write(self.html)

        #TODO delete the temporary folder if everything is submitted to ipfs or handle outside of thread

    def load_images(self, soup):
        """
        Takes a BeautifulSoup Object and downloads all the images referenced in the HTML of the BS object.
        The method also changes the HTML, since it adds a tag attribute of ipfs-src with the hash returned
        from ipfs as value and thereby uniquely identifies the image. Thus pictures are taken in account when the Hash
        is created for the HTML.

        :author: Sebastian
        :param soup: The BeautifulSoup object of the html file
        :return: A list of file names of the pictures that were downloaded and submitted to ipfs.
        """
        files = list()
        img_ctr = 0
        current_directory = os.getcwd()
        os.chdir(self.path)
        for img in soup.find_all(['amp-img', 'img']):
            if urlPattern.match(img['src']):
                filename = 'img' + str(img_ctr)
                img_ctr += 1
                r = requests.get(img['src'], stream=True)
                if r.status_code == 200:

                    with open(filename, 'wb') as f:
                        for chunk in r.iter_content(1024):
                            f.write(chunk)
                    ipfs_hash = self.add_to_ipfs(filename)
                    img['ipfs-src'] = ipfs_hash
                    files.append(filename)
        self.html = soup.html
        os.chdir(current_directory)
        app.logger.info("Downloaded following images and submitted them to ipfs: " + str(files))
        return files

    def add_to_ipfs(self, fname):
        """
            Helper method that submits a file to IPFS and returns the resulting hash,
            that describes the address of the file on IPFS.

            :author: Sebastian
            :param fname: The path to the File to get the hash for.
            :return: Returns the Hash of the file.
        """
        res = ipfs_Client.add(fname)

        return res['Hash']

    def join(self, timeout=None):
        threading.Thread.join(self)
        return self.html
