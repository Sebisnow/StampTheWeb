import threading
import os
import re
import requests
import chardet
from flask import current_app as app
from selenium import webdriver
from warcat.model import WARC
from bs4 import BeautifulSoup
import ipfsApi as ipfs
import shutil
from readability.readability import Document
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

exitFlag = 0
urlPattern = re.compile('^(https?|ftp)://[^\s/$.?#].[^\s]*$')
ipfs_Client = ipfs.Client('127.0.0.1', 5001)
js_path = os.path.abspath(os.path.expanduser("~/") + '/bin/phantomjs/lib/phantom/bin/phantomjs')


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
            self.phantom = self.initialize(prox)

        if not os.path.exists(self.path):
            os.mkdir(self.path)
        else:
            shutil.rmtree(self.path)
            os.mkdir(self.path)
        self.path = self.path + "/" + str(thread_id) + "/"
        print("initialized")
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
        self.download()
        # TODO return something?
        return self.ipfs_hash
        # TODO download html and images include in warc

    def download(self):
        """
        Orchestrates the download job of this thread.
        Makes the assumption that if a html is provided no proxy is set.

        :author: Sebastian
        """
        soup = None
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
            tag = None
            if urlPattern.match(img['src']):
                tag = img['src']
            elif img['data-original'] and urlPattern.match(img['data-original']):
                tag = img['data-original']
            elif img['data'] and urlPattern.match(img['data']):
                tag = img['data']
            else:
                print("An image did not have a html specification url: \n" + img)
            filename = 'img' + str(img_ctr)
            img_ctr += 1
            print("Downloading image: " + tag)
            if proxy:
                try:
                    """
                    First we try to get the image without a proxy and only if that fails the proxy is used.
                    Alternatively or possibly another exception needs to be handled if MaxRetryError occurs
                    due to too many connections to proxy.
                    """
                    res = requests.get(tag, stream=True)
                except:
                    print("Could not request image trying with proxy: " + proxy)
                    res = requests.get(tag, stream=True, proxies={"http": "http://" + proxy}, headers=header)
            else:
                res = requests.get(tag, stream=True)

            if res.status_code == 200:
                with open(filename, 'wb') as f:
                    for chunk in res.iter_content(1024):
                        f.write(chunk)
                image_hash = self.add_to_ipfs(filename)
                print("Added image to ipfs: " + filename)
                img['ipfs-src'] = image_hash
                files[img_ctr] = {"filename": filename,
                                  "hash": image_hash
                                  }

        print("Downloaded images: " + str(files))
        self.html = str(soup.find("html"))
        os.chdir(current_directory)
        return files

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

    def join(self, timeout=None):
        print("The html just before join: \n" + str(self.html))
        result = DownloadResult(self.threadID, self.url, self.ipfs_hash, self.html,
                                self.images, self.prox_loc)
        threading.Thread.join(self)
        return result


class DownloadResult:
    """
    The class to return the results of a DownloadThread with the following attributes:
    :param thread_id: The thread id of the used DownloadThread.
    :param url: The URL that was downloaded in this job.
    :param ipfs_hash: The hash that represents the content of the URL.
    :param prox_loc: The proxy location.
    :param images: A dictionary of images in the form of
                    image number(starting with 0): {"filename": <name>, "hash": <hash>}.
    :param html: The processed html with img tags that have the ipfs-src attribute.

    :author: Sebastian
    """
    def __init__(self, thread_id, url, ipfs_hash, html, images, prox_loc=None):
        self.thread_id = thread_id
        self.url = url
        self.ipfs_hash = ipfs_hash
        self.html = html
        self.images = images
        self.prox_loc = prox_loc


def preprocess_doc(doc):
    """
    Calculate hash for given html document. The html document is expected as a document object from readability package.

    :author: Sebastian
    :param doc: html doc to preprocess
    :returns: The preprocessed html as a String.
    """
    print('Preprocessing Document')

    # Detect the encoding of the html for future reference
    encoding = chardet.detect(doc.content().encode()).get('encoding')
    if not encoding:
        encoding = 'utf-8'
    doc.encoding = encoding
    # TODO document encoding could be detected with chardet again: chardet.detect(doc.content)

    head = '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1' \
           '-transitional.dtd">\n' + '<head>\n' + \
           '<meta http-equiv="Content-Type" content="text/html" ' \
           'charset="' + encoding + '">\n' + '</head>\n' + '<body>\n' \
           + '<h1>' + doc.title().split(sep='|')[0] + '</h1>'

    text = head + doc.summary()[12:]
    print('Preprocessing done')
    return text
