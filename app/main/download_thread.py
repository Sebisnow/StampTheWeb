import threading
import os
import re
import zipfile
import requests
import chardet
from flask import current_app as app
from selenium import webdriver
from warcat.model import WARC
from warcat.model.field import Header
from warcat.model.record import Record
from warcat.model.block import BlockWithPayload
from warcat.model.field import Fields
from bs4 import BeautifulSoup
import ipfsApi
import shutil
import time
from readability.readability import Document
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.common.exceptions import TimeoutException
from requests.exceptions import ReadTimeout, HTTPError

from app.main.proxy_util import get_one_proxy
# from ..models import Warcs

exitFlag = 0
urlPattern = re.compile('^(https?|ftp)://[^\s/$.?#].[^\s]*$')
ipfs_Client = ipfsApi.Client('127.0.0.1', 5001)
js_path = os.path.abspath(os.path.expanduser("~/") + '/bin/phantomjs/lib/phantom/bin/phantomjs')
base_path = 'app/pdf/'
proxy_path = os.path.abspath(os.path.expanduser("~/") + "PycharmProjects/STW/static/")

negative_tag_classes = ["ad", "advertisement", "gads", "iqad", "anzeige", "dfp_ad"]
negative_tags = re.compile("aside", re.I)


class DownloadThread(threading.Thread):
    """
    Class that subclasses threading.Thread in order to start a new thread with a new download job.
    To check whether a proxy was used check self.html which is None if a proxy was and is to be used.
    If html is provided then a proxy is not required.

    :author: Sebastian
    """
    def __init__(self, thread_id, url=None, prox=None, prox_loc=None, basepath='app/pdf/', html=None):
        """
        Default constructor for the DownloadThread class, that initializes the creation of a new download job in a
        separate thread.
        Attention: If basePath does not exist yet this will throw a FileNotFoundException (e.g. in testing)

        :author: Sebastian
        :param thread_id: The ID of this thread.
        :param url: The URL that is to be downloaded in this job.
        :param prox: The proxy to use when downloading from the before specified URL.
        :param prox_loc: The proxy location.
        :param basepath: The path to store the temporary files in.
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
        self.basepath = basepath
        self.path = basepath + "temporary"
        self.ipfs_hash = None
        self.images = dict()

        if not self.html:
            app.logger.info("Using Proxy: " + prox)
            self.phantom = self.initialize(prox)

        if not os.path.exists(self.path):
            try:
                os.mkdir(self.path)
            except FileNotFoundError:
                # should ony be thrown and caught in testing mode!
                self.path = os.path.abspath(os.path.expanduser("~/")) + "/testing-stw/temporary"
                if not os.path.exists(self.path):
                    os.mkdir(self.path)
        """else:
            shutil.rmtree(self.path)
            os.mkdir(self.path)"""
        self.path = self.path + "/" + str(thread_id) + "/"
        app.logger.info("initialized a new Thread:" + str(self.threadID))
        if os.path.exists(self.path):
            shutil.rmtree(self.path)
        os.mkdir(self.path)

    @staticmethod
    def initialize(proxy):
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
        """
        print("Started Thread" + str(self.threadID))
        failed = False
        try:
            self.download()
        except TimeoutException:
            failed = True
            # TODO not reachable from this country - tried two proxies
            app.logger.error("Couldn't reach website through proxy, trying again with new proxy")
        if failed:
            self.initialize(get_one_proxy(self.prox_loc))
            try:
                self.download()
            except TimeoutException:
                app.logger.error("Couldn't reach website through two proxies, unreachable from loc {}"
                                 .format(self.prox_loc))

    def download(self):
        """
        Orchestrates the download job of this thread. Time consuming method that downloads the html via phantomJS.
        Makes the assumption that if a html is provided no proxy is set.

        :author: Sebastian
        :raises TimeoutException: If the proxy is not active anymore or unreachable for too long a TimeoutException is
        thrown to be caught and handled by calling function.
        """
        if not self.html:
            print("Downloading without html, proxy is set to({}): {}".format(self.prox_loc, self.proxy))
            self.phantom.get(self.url)
            self.html = str(self.phantom.page_source)

        self.html, title = preprocess_doc(self.html)
        print("Thread{} Preprocessed doc! self.html now is: {}".format(self.threadID, type(self.html)))
        soup = BeautifulSoup(self.html, "lxml")

        # self.proxy is None if html was given to DownloadThread.
        self.images = self.load_images(soup, self.proxy)
        with open(self.path + "/page_source.html", "w") as f:
            f.write(self.html)

        archive = zipfile.ZipFile(self.path + '/STW.zip', "w", zipfile.ZIP_DEFLATED)
        archive.write(self.path + "/page_source.html")
        for img in self.images:
            print("Thread{} Path to image: " + str(self.images.get(img).get("filename")).format(self.threadID))
            archive.write(self.path + self.images.get(img).get("filename"))
        archive.close()
        # Add folder to ipfs # TODO best place to zip files if necessary
        """would not be necessary to add folder to ipfs since the html has the ipfs_hash
        of the images stored within the img tags and thus is unique itself."""
        self.ipfs_hash = add_to_ipfs(self.path + 'STW.zip')
        print("Thread{} Downloaded and submitted everything to ipfs: \n{}".format(self.threadID, self.ipfs_hash))

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
        print("Thread{} Loading images".format(self.threadID))
        files = dict()
        img_ctr = 0
        current_directory = os.getcwd()
        os.chdir(self.path)
        header = {'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.9; rv:32.0) Gecko/20100101 Firefox/32.0'}

        for img in soup.find_all(['amp-img', 'img']):
            try:
                res = self.down_image(img, header, proxy)
            except NameError:
                # the picture in the url was not retrievable, continue to next image
                continue
            except ConnectionError:
                print("Thread{} Could not connect to retrieve image. Trying again with proxy".format(self.threadID))
                # TODO start image load again with different proxy

            filename = 'img{}.png'.format(str(img_ctr))
            img_ctr += 1
            if res.status_code == 200:
                with open(filename, 'wb') as f:
                    for chunk in res.iter_content(1024):
                        f.write(chunk)
                image_hash = add_to_ipfs(filename)
                print("Added image to ipfs: " + filename)
                img['ipfs-src'] = image_hash
                files[img_ctr] = {"filename": filename,
                                  "hash":     image_hash
                                  }

        print("Thread{} Downloaded images: {}".format(self.threadID, str(files)))
        self.html = str(soup.find("html"))
        os.chdir(current_directory)
        return files

    def down_image(self, img, header, proxy=None):
        """
        Downloads only one image. Helper Method to load_images

        :author: Sebastian
        :raises NameError: If there is an image that can not be fetched because no known attribute
        containing a link to it exists or has a link that satisfies the urlPattern.
        :param img: The img tag object.
        :param header: The header that is used if the image is retrieved via proxy
        :param proxy: The proxy that is to be used to download the image. Defaults to None, to download it directly.
        :return: A Response object with the response status and the image to store.
        """

        if urlPattern.match(img['src']):
            tag = img['src']
        elif img['data-full-size'] and urlPattern.match(img['data-full-size']):
            tag = img['data-full-size']
        elif img['data-original'] and urlPattern.match(img['data-original']):
            tag = img['data-original']
        elif img['data'] and urlPattern.match(img['data']):
            tag = img['data']
        else:
            print("Thread{}: An image did not have a html specification url: {}".format(self.threadID, img))
            raise NameError("Thread{}: An image did not have a html specification url: {}".format(self.threadID, img))

        print("Thread{}: Downloading image: {}".format(self.threadID, tag))
        if proxy:
            try:
                """
                First we try to get the image without a proxy and only if that fails the proxy is used.
                Alternatively or possibly another exception needs to be handled if MaxRetryError occurs
                due to too many connections to proxy.
                """
                res = requests.get(tag, stream=True)
                print("Thread{} Requested image without proxy.".format(self.threadID))
            except ConnectionRefusedError as con:
                print("Thread{} Could not request image due to: {}\ntrying with proxy: {}".format(
                    self.threadID, con.strerror, proxy))
                res = requests.get(tag, stream=True, proxies={"http": "http://" + proxy}, headers=header)
        else:
            res = requests.get(tag, stream=True)
        return res

    def add_to_warc(self):
        """
        Creates a WARC record for this download job.
        If no WARC file exists for this url a new Warc file with one record is created

        :author: Sebastian
        :return: The path to the WARC file.
        """
        # TODO store one WARC per URL instead of only one WARC - issue is the IPFS/IPNS publishing.
        warc = WARC()
        path_to_warc = "{}warcs/{}.warc.gz".format(self.basepath, self.url)
        # found_warc = Warcs.query.filter(Warcs.url.equals(self.url))
        found_warc = os.path.exists(path_to_warc)
        if not found_warc:
            warc.load(path_to_warc)
        else:
            warc.records[0] = Header(fields={'url': self.url, 'creation_time': time.time()})
        # TODO fill in Header, Fields and Record with data
        header = Header()
        content = Fields()
        content_block = BlockWithPayload(fields=content)
        record = Record(header=header)
        record.content_block = content_block
        warc.records.append(record)
        return path_to_warc


def add_to_ipns(path):
    """
        Helper method that submits a file to IPNS and returns the resulting hash,
        that describes the static address of the file on IPNS, no matter if the file changes or not
        the address stays the same.

        :author: Sebastian
        :param path: The path to the File to get the hash for.
        :return: Returns the Hash of the file.
    """
    # TODO after WARC creation submit it to IPNS. Issue is how to preserve the other files under the public peerID
    ipfs_Client.name_publish(path)


def get_from_ipns(ipns_hash):
    """
        Helper method that looks up a file on IPNS and retrieves the IPFS file,
        that is described in the static address of the file on IPNS.

        :author: Sebastian
        :param ipns_hash: The IPNS hash where to retrieve the file from.
        :return: Returns the Hash of the file.
    """
    # TODO after WARC creation submit it to IPNS. Issue is how to preserve the other files under the public peerID

    ipfs_hash = ipfs_Client.name_resolve(ipns_hash)
    return get_from_ipfs(ipfs_hash)


def add_to_ipfs(fname):
    """
        Helper method that submits a file to IPFS and returns the resulting hash,
        that describes the address of the file on IPFS.

        :author: Sebastian
        :param fname: The path to the File to get the hash for.
        :return: Returns the Hash of the file.
    """
    if not os.path.isdir(fname):
        #TODO only submit ZIP not the whole structure /home/seb...
        # os.chdir(fname.rpartition("/")[0])
        # os.chdir(fname)
        res = ipfs_Client.add(fname, recursive=False)
        if type(res) is list:
            print("Entire IPFS result" + str(res))
            print("IPFS result: " + str(res[0]))
            return res[0]['Hash']

        print("IPFS result: " + str(res))
        return res['Hash']
    else:
        res = ipfs_Client.add(fname, recursive=False)[0]
        print("IPFS result for directory: " + str(res))
        return res['Hash']


def get_from_ipfs(timestamp, file_path=None):
    """
    Get data from IPFS. The data on IPFS is identified by the hash (timestamp variable).
    We collect the data using the IPFS API. IPFS has to be installed and a daemon process of IPFS needs to be
    running for this functionality to work. If the data is not present on IPFS it raises a ValueError.


    :author: Sebastian
    :raises ValueError: A ValueError is raised whenever the process fails due to a incorrectly formatted hash or a hash
    that is not retrievable by ipfs within the timeout of 5 seconds. Whenever this error is raised we assume the data
    is currently not present on IPFS
    :param file_path: If the file to retrieve should be stored in a specific location it can be specified via this
    parameter.
    :param timestamp: The hash describing the data on IPFS.
    :return: Returns the path to the locally stored data collected from IPFS.
    """
    if file_path:
        path = file_path + timestamp
    else:
        path = base_path + timestamp
    cur_dir = os.getcwd()
    os.chdir(base_path)
    app.logger.info("Trying to fetch the File from IPFS: {}".format(timestamp))
    try:
        ipfs_Client.get(timestamp, timeout=5)
    except ReadTimeout:
        app.logger.info("Could not fetch file from IPFS, file does probably not exist.")
        raise ValueError
    except HTTPError:
        app.logger.info("Could not fetch file from IPFS, Hash was of the wrong format. Length: {}"
                        .format(len(timestamp)))
        raise ValueError
    os.chdir(cur_dir)
    return path


def preprocess_doc(html_text):
    """
    Calculate hash for given html document. The html document is expected as a document object from readability package.

    :author: Sebastian
    :param html_text: html document in string format to preprocess.
    :returns: The preprocessed html as a String and the title if needed by the callee.
    """
    print('Preprocessing Document: {}'.format(type(html_text)))

    # remove some common advertisement tags beforehand
    bs = BeautifulSoup(html_text, "lxml")
    for tag_desc in negative_tag_classes:
        for tag in bs.findAll(attrs={'class': re.compile(r".*\b{}\b.*".format(tag_desc))}):
            tag.extract()
    doc = Document(str(bs.html), negative_keywords=negative_tags)
    try:
        # Detect the encoding of the html, if not detectable use utf-8 as default.
        encoding = chardet.detect(doc.content().encode()).get('encoding')
        title = doc.title()
    except TypeError:
        print("Encountered TypeError setting encoding to utf-8.")
        encoding = "utf-8"
        title = bs.title.getText()
    if not encoding:
        print("Using default encoding utf-8")
        encoding = 'utf-8'
        title = bs.title.getText()
    doc.encoding = encoding

    head = '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1' \
           '-transitional.dtd">\n' + '<head>\n' + \
           '<meta http-equiv="Content-Type" content="text/html" ' \
           'charset="' + encoding + '">\n' + '</head>\n' + '<body>\n' \
           + '<h1>' + title.split(sep='|')[0] + '</h1>'

    # Unparsable Type Error in encoding, where's the problem.
    text = head + doc.summary()[12:]

    # sometimes some tags get messed up and need to be translated back
    text = text.replace("&lt;", "<").replace("&gt;", ">")
    print('Preprocessing done. Type of text is: {}'.format(type(text)))
    return text, title
