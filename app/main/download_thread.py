import threading
import re
import os
import urllib.error
from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse
import asyncio

import pdfkit
import requests
import chardet
from flask import current_app as app
from requests.packages.urllib3.exceptions import MaxRetryError
from selenium import webdriver
from bs4 import BeautifulSoup
import ipfsApi
import shutil
import time
from readability.readability import Document
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.common.exceptions import TimeoutException
from requests.exceptions import ReadTimeout, HTTPError
from warc3 import warc

from app.main import proxy_util
# from ..models import Warcs

exit_flag = 0
ipfs_Client = ipfsApi.Client('127.0.0.1', 5001)
js_path = os.path.abspath(os.path.expanduser("~/") + '/bin/phantomjs/lib/phantom/bin/phantomjs')

api_key = '7be3aa0c7f9c2ae0061c9ad4ac680f5c'
api_post_url = 'http://www.originstamp.org/api/stamps'

negative_tag_classes = ["ad", "advertisement", "gads", "iqad", "anzeige", "dfp_ad"]
# :param negative_tags: if any HTML tags are definitely just advertisement and definitely not describe the content
# the tag can be added using a pipe. E.g "aside|ad".
negative_tags = re.compile("aside", re.I)
positive_tags = re.compile("article|article-title|headline|breitwandaufmacher|article-section", re.I)


class DownloadThread(threading.Thread):
    """
    Class that subclasses threading.Thread in order to start a new thread with a new download job.
    To check whether a proxy was used check self.html which is None if a proxy was and is to be used.
    If html is provided then a proxy is not required.

    :author: Sebastian
    """
    def __init__(self, thread_id, url=None, proxy=None, prox_loc=None, basepath='app/pdf/', html=None,
                 robot_check=False, create_warc=True):
        """
        Default constructor for the DownloadThread class, that initializes the creation of a new download job in a
        separate thread.

        :author: Sebastian
        :param thread_id: The ID of this thread.
        :param url: The URL that is to be downloaded in this job.
        :param proxy: The proxy to use when downloading from the before specified URL.
        :param prox_loc: The proxy location.
        :param basepath: The base path to store the temporary files in.
        :param html: Defaults to None and needs only to be specified if a user input of an HTML was given by the
        StampTheWeb extension.
        :param robot_check: Boolean value that indicates whether the downloader should honour the robots.txt of
        the given website or not.
        :param create_warc: This boolean parameter specifies whether or not a warc should be created for this
        download job.
        """
        threading.Thread.__init__(self)
        print("Starting Thread")

        self.url, self.html, self.robot_check, self.threadID = url, html, robot_check, thread_id
        self.proxy, self.prox_loc, self.warc = proxy, prox_loc, create_warc
        self.storage_path, self.images = basepath, dict()
        self.path = "{}temporary".format(basepath)
        self.ipfs_hash, self.title, self.originstamp_result = None, None, None
        self.error, self.screenshot, self.already_submitted = None, dict(), False
        if self.robot_check:
            url_parser = urlparse(self.url)
            self.bot_parser = RobotFileParser().set_url("{url.scheme}://{url.netloc}/robots.txt".format(url=url_parser))
            self.bot_parser.read()

        if self.html is None:
            self._proxy_setup()
            self.extension_triggered = False

            print("Thread{} is using Proxy: {}".format(self.threadID, self.proxy))
            self.phantom = self.initialize(self.proxy, self.prox_loc)
        else:
            self.extension_triggered = True
            self.phantom = self.initialize()
            print("Thread{} was extension triggered!".format(self.threadID))

        # create temporary storage folder
        if not os.path.exists(self.path):
            try:
                os.mkdir(self.path)
            except FileNotFoundError:
                # should only be thrown and caught in testing mode!
                print("Path not found: {}".format(self.path))
                if app.config["TESTING"]:
                    self.path = os.path.abspath(os.path.expanduser("~/")) + "/testing-stw/temporary"
                    print("Testing, so new path is: {}".format(self.path))
                else:
                    self.path = "{}/StampTheWeb/{}temporary".format(os.path.abspath(os.path.expanduser("~/")),
                                                                    self.storage_path)
                    if not os.path.exists(self.path.rpartition("/")[0]):
                        os.mkdir(self.path.rpartition("/")[0])

                if not os.path.exists(self.path):
                    os.mkdir(self.path)

        self.path = "{}/{}/".format(self.path, str(thread_id))
        print("Initialized a new Thread: {}".format(str(self.threadID)))

        # remove temporary folder with thread id as name and recreate
        if os.path.exists(self.path):
            shutil.rmtree(self.path)
        os.mkdir(self.path)

    @staticmethod
    def initialize(proxy=None, proxy_location=None):
        """
        Helper method that initializes the PhantomJS Headless browser and sets the proxy.

        :author: Sebastian
        :param proxy: The proxy to set.
        :param proxy_location: A location for a proxy. If no proxy is specified it is fetched from that location.
        :return: The PhantomJS driver object.
        """
        print("Initialize Phantom with proxy:{} and location: {}".format(proxy, proxy_location))
        dcap = dict(DesiredCapabilities.PHANTOMJS)
        dcap["phantomjs.page.settings.userAgent"] = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/53 " \
                                                    "(KHTML, like Gecko) Chrome/15.0.87"

        if proxy is not None:
            service_args = [
                '--proxy={}'.format(proxy),
                '--proxy-type=http',
            ]
        elif proxy_location is not None:
            try:
                print("retrieve proxy for location: {}".format(proxy_location))
                new_proxy = proxy_util.get_one_proxy(proxy_location)

            except RuntimeError:
                print("Restarted proxy retrieval with new event loop")
                new_proxy = proxy_util.get_one_proxy(proxy_location, asyncio.new_event_loop())

            service_args = [
                '--proxy={}'.format(new_proxy),
                '--proxy-type=http',
            ]
        else:
            service_args = []
            print("Neither proxy nor location are set, doing things locally")
        dcap["acceptSslCerts"] = True
        phantom = webdriver.PhantomJS(js_path, desired_capabilities=dcap, service_args=service_args)

        max_wait = 35

        phantom.set_window_size(1024, 768)
        phantom.set_page_load_timeout(max_wait)
        phantom.set_script_timeout(max_wait)
        return phantom

    def _proxy_setup(self):
        """
        Prepare proxies, check if alive and get new one if necessary.

        """
        print("Setting up proxies")
        if self.proxy is not None:
            alive = proxy_util.is_proxy_alive(self.proxy)
            if self.prox_loc is None:
                self.prox_loc = proxy_util.ip_lookup_country(self.proxy.split(":")[0])
            if not alive:
                self.proxy = proxy_util.get_one_proxy(self.prox_loc)

        else:
            if self.prox_loc is not None:
                self.proxy = proxy_util.get_one_proxy(self.prox_loc)

    def run(self):
        """
        Run the initialized thread and start the download job. Afterwards submit the hash to originstamp to create a
        lasting and verifyable timestamp. If HTML is not allowed to be retrieved by the crawler raise URLError.

        :author: Sebastian
        :raises URLError: Is raised if HTML retrieval is forbidden by robots.txt.
        """
        print("Started Thread" + str(self.threadID))
        if self.robot_check and not self.bot_parser.can_fetch(self.url):
            self.error = urllib.error.URLError("Not allowed to fetch root html file specified by url:{} because of "
                                               "robots.txt".format(self.url))
            raise self.error
        try:
            self.download()
        except RuntimeError as e:
            # store error and reraise to stop thread.
            self.error = e
            raise e
        except ConnectionResetError as e:
            # store error and reraise to stop thread.
            self.error = e
            raise e
        except TimeoutException as timeout:
            self.error = timeout
            raise timeout
        # submit the hash to originstamp to create a lasting timestamp.
        if self.error is None:
            self.handle_submission()

    def download(self):
        """
        Orchestrates the download job of this thread. Time consuming method that downloads the html via phantomJS.
        Makes the assumption that if a html is provided no proxy is set.
        Raises TimeoutException if html is unreachable from two proxies of the same country.

        :author: Sebastian
        :raises TimeoutException: If the proxy is not active anymore or the website is unreachable a
        TimeoutException is thrown.
        """
        if self.html is None:
            print(" Thread{}: Downloading without html, proxy is set to({}): {}".format(self.threadID, self.prox_loc,
                                                                                        self.proxy))
            # try downloading, if site is unreachable through proxy reinitialize with new proxy from same location.
            if not self._download_html():
                print("Couldn't reach website through proxy, trying again with new proxy")
                self.initialize(proxy_util.get_one_proxy(self.prox_loc))

                # try again, if False is returned site was unreachable again -> propagate upwards by raising error
                if not self._download_html():
                    print("Couldn't reach website through two proxies, unreachable from loc {}"
                          .format(self.prox_loc))
                    self.error = TimeoutException("Couldn't reach website through two proxies, unreachable from loc {}"
                                                  .format(self.prox_loc))
                    raise self.error

        # check that HTML was really downloaded by checking the size
        if len(self.html) < 50:
            print("Could not retrieve website.")
            self.error = TimeoutException("Couldn't reach website through two proxies, unreachable from loc {}"
                                          .format(self.prox_loc))
            raise self.error

        self.html, self.title = preprocess_doc(self.html)
        soup = BeautifulSoup(self.html, "lxml")

        self.images = self._load_images(soup, self.proxy)
        with open(self.path + "page_source.html", "w") as f:
            f.write(self.html)

        """archive = zipfile.ZipFile(self.path + 'STW.zip', "w", zipfile.ZIP_DEFLATED)
        archive.write(self.path + "page_source.html")
        for img in self.images:
            print("Thread{} Path to image: {}".format(self.threadID, str(self.images.get(img).get("filename"))))
            archive.write(self.path + self.images.get(img).get("filename"))
        archive.close()
        # Add folder to ipfs # TODO best place to zip files if necessary
        # would not be necessary to add folder to ipfs since the html has the ipfs_hash
        # of the images stored within the img tags and thus is unique itself.
        self.ipfs_hash = add_to_ipfs(self.path + 'STW.zip')"""

        self.ipfs_hash = add_to_ipfs(self.path + 'page_source.html')
        print("Thread{} Downloaded and submitted everything to ipfs: \n{}".format(self.threadID, self.ipfs_hash))

    def _download_html(self):
        """
        Helper Method that downloads the HTML after scrolling down to enable dynamic content.

        :author: Sebastian
        :returns: returns False if an error occurred during the HTML downloading. Otherwise returns True
        """
        try:
            self.phantom.get(self.url)
            self.scroll(self.phantom)
        except TimeoutException as e:
            print(e)
            return False
        print("Fetched website successfully")
        self.html = str(self.phantom.page_source)
        return True

    def _load_images(self, soup, proxy=None):
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

        for img in soup.find_all(['amp-img', 'img']):
            try:
                res = self._down_image(img, proxy)
            except NameError:
                # the picture in the url was not retrievable, continue to next image
                continue
            except ConnectionError:
                print("Thread{} Could not connect to retrieve image. Can't retrieve from this location."
                      .format(self.threadID))
            except urllib.error.URLError as e:
                print(str(e))

            if res.status_code == 200:
                filename = 'img{}'.format(str(img_ctr))
                img_ctr += 1

                with open(filename, 'wb') as f:
                    for chunk in res.iter_content(1024):
                        f.write(chunk)

                image_hash = add_to_ipfs(filename)
                print("Added image to ipfs: " + filename)
                img['ipfs-src'] = image_hash
                files[img_ctr] = {"filename": filename,
                                  "hash":     image_hash}

        print("Thread{} Downloaded images: {}".format(self.threadID, str(files)))
        self.html = str(soup.find("html"))
        os.chdir(current_directory)
        return files

    def _down_image(self, img, proxy=None):
        """
        Downloads only one image. Helper Method to load_images

        :author: Sebastian
        :raises NameError: If there is an image that can not be fetched because no known attribute
        containing a link to it exists or has a link that satisfies the urlPattern.
        :param img: The img tag object.
        :param proxy: The proxy that is to be used to download the image. Defaults to None, to download it directly.
        :return: A Response object with the response status and the image to store.
        """
        header = {'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.9; rv:32.0) Gecko/20100101 Firefox/32.0'}

        if 'src' in img.attrs and proxy_util.url_specification.match(img['src']):
            tag = img['src']
        elif 'data-full-size' in img.attrs and proxy_util.url_specification.match(img['data-full-size']):
            tag = img['data-full-size']
        elif 'data-original' in img.attrs and proxy_util.url_specification.match(img['data-original']):
            tag = img['data-original']
        elif 'data' in img.attrs and proxy_util.url_specification.match(img['data']):
            tag = img['data']
        else:
            print("Thread{}: An image did not have a html specification url: {}".format(self.threadID, img))
            raise NameError("Thread{}: An image did not have a html specification url: {}".format(self.threadID, img))

        print("Thread{}: Trying to download image: {}".format(self.threadID, tag))
        if self.robot_check and not self.bot_parser.can_fetch(self.url):
            print("Not allowed to fetch image file specified by url:{} because of "
                  "robots.txt".format(self.url))
            raise urllib.error.URLError("Not allowed to fetch image file specified by url:{} because of "
                                        "robots.txt".format(self.url))
        res = None
        try:
            """
            First we try to get the image with a proxy. If that fails we try it without proxy.
            """
            if proxy:
                res = requests.get(tag, stream=True, proxies={"http": "http://" + proxy}, headers=header)
                return res

            print("Thread{} Requested image with proxy.".format(self.threadID))
        except ConnectionRefusedError or MaxRetryError as con:
            print("Thread{} Could not request image due to: {}\ntrying without proxy.".format(
                self.threadID, con.strerror))
            res = requests.get(tag, stream=True, headers=header)
        except ConnectionResetError as reset:
            raise reset

        return res

    def _make_pdf(self):
        """
        Creates a pdf file from the preprocessed html with the images embedded in it.

        """
        html_path = "{}pdf_source.html".format(self.path)
        pdf_path = "{}{}.pdf".format(self.storage_path, self.ipfs_hash)
        if not os.path.exists(pdf_path):
            soup = BeautifulSoup(self.html, "lxml")
            for img in soup.find_all(['amp-img', 'img']):
                if "ipfs-src" in img.attrs:
                    for key in self.images:
                        if img["ipfs-src"] == self.images[key]["hash"]:
                            img["src"] = self.images[key]["filename"]

            with open(html_path, "w") as html_file:
                html_file.write(str(soup.find("html")).replace("noscript", "div"))
            # PDF is written to the basepath of the application (usually app/pdf/)
            pdfkit.from_file(html_path, pdf_path)
            print("Created PDF file from Preprocessed and img source changed html file: {}".format(pdf_path))
        else:
            print("PDF exists already in {}!".format(pdf_path))

    def _add_to_warc(self):
        """
        Creates a WARC record for this download job.
        If no WARC file exists for this url a new Warc file with one record is created.
        This should only be called if a new timestamp was created.
        The first record (at index 0) is the Header of the entire WARC specifying the URL again and the creation time.
        Every record consists of a header and data. The header states what content-type to expect, the timestamp etc.

        :author: Sebastian
        :return: The path to the WARC file.
        """
        print("Adding to warc")
        # TODO only store references to ipfs in warc. binary data is difficult to work with.
        # TODO store one WARC per URL instead of only one WARC - issue is the IPFS/IPNS publishing.
        originstamp_result = self.originstamp_result

        path_to_warc = "{}warcs/{}.warc.gz".format(self.storage_path, urlparse(self.url).netloc)
        # found_warc = Warcs.query.filter(Warcs.url.equals(self.url))
        with warc.open(path_to_warc, "ab") as warc_file:

            record_header = warc.WARCHeader({'hash_value': self.ipfs_hash, 'title': originstamp_result['title'],
                                             'creation_time': originstamp_result['created_at'],
                                             'content_type': 'application/warc-fields', 'WARC-Target-URI': self.url,
                                             'country': self.prox_loc, 'robots_txt': self.robot_check})

            content_block = '"{}"\n'.format(self._create_content()).encode()
            record = warc.WARCRecord(record_header, content_block, defaults=True)
            record.header.setdefault("content-type", "application/json")

            warc_file.write_record(record)
        print("Finished adding to warc, the path is: {}".format(path_to_warc))
        return path_to_warc

    def _create_content(self):
        """
        Helper Method to create a filled warc content field. The HTML is added as one field.
        One field for the images. The image field contains all images with their ipfs_hash and their binary_data.
        A screenshot of the website is added. For completeness the originstamp_result is added as well.

        :author: Sebastian
        :return: The content field filled with information concerning this download.
        """
        content = dict()
        content['html'] = self.html
        pictures = dict()
        cnt = 0
        for img in self.images:
            with open(self.path + self.images[img]["filename"], 'rb') as binary_image:
                image_data = dict()
                image_data["ipfs_hash"] = self.images[img]["hash"]
                image_data["binary_data"] = binary_image.read()
                pictures[str(img)] = image_data
            cnt += 1

        content["images"] = pictures
        with open(self.screenshot["path"], 'rb') as binary_screenshot:
            image_data = dict()
            image_data["ipfs_hash"] = self.screenshot["ipfs_hash"]
            image_data["binary_data"] = binary_screenshot.read()
            content["screenshot"] = image_data
        content["originstamp_result"] = self.originstamp_result
        return content

    def handle_submission(self):
        """
        Handles the submission of the hash to originstamp to create the actual timestamp and the resulting consequences.
        Handles PNG creation and storage.

        :author: Sebastian
        """
        print("Thread{} submit hash to originstamp.".format(self.threadID))
        self.originstamp_result = submit(self.ipfs_hash, title="Distributed timestamp of {} from location {}"
                                         .format(self.url, self.prox_loc))

        print("Originstamp result: {}".format(str(self.originstamp_result.text)))
        if self.originstamp_result.status_code != 200:
            self.error = HTTPError("Originstamp submission returned {} and failed for some reason: {}"
                                   .format(str(self.originstamp_result.status_code), self.originstamp_result.text))
            raise self.error
        else:
            self._take_screenshot()
            self._make_pdf()

            if "errors" in self.originstamp_result.text:
                print("Thread{} submitted hash to originstamp but the content has not changed. A timestamp "
                      "exists already.".format(self.threadID))
                # hash already submitted
                self.already_submitted = True
                self.originstamp_result = get_originstamp_history(self.ipfs_hash).json()

            else:
                print("Thread{} successfully submitted hash to originstamp and created a new timestamp."
                      .format(self.threadID))
                self.originstamp_result = self.originstamp_result.json()
                # Only add content to warc for new or changed content -> only for new timestamps
                if self.warc:
                    self._add_to_warc()

    def _take_screenshot(self):
        """
        Takes a screenshot of the website that was downloaded using this DownloadThread.
        It sets the screenshot variable of DownlaodThread to consist of the ipfs_hash and the path to the screenshot.

        :author: Sebastian
        """

        screenshot_path = "{}{}.png".format(self.storage_path, self.ipfs_hash)
        if not os.path.exists(screenshot_path):
            print("Hash submitted but png not existent. Writing png to: {}"
                  .format(screenshot_path))
            self.phantom.get_screenshot_as_file(screenshot_path)
        else:
            print("Screenshot present at: {}".format(screenshot_path))
        self.screenshot["ipfs_hash"] = add_to_ipfs(screenshot_path)
        self.screenshot["path"] = screenshot_path

    @staticmethod
    def scroll(phantom):
        pause = 0.2
        start_time = time.time()
        last_height = phantom.execute_script("return document.body.scrollHeight")
        # only load for a maximum of 5 seconds
        while True or time.time()-start_time > 5:
            phantom.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(pause)
            new_height = phantom.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height


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
        #TO DO only submit ZIP not the whole structure /home/seb...
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
        path = proxy_util.base_path + timestamp
    cur_dir = os.getcwd()
    os.chdir(proxy_util.base_path)
    print("Trying to fetch the File from IPFS: {}".format(timestamp))
    try:
        ipfs_Client.get(timestamp, timeout=5)
    except ReadTimeout:
        print("Could not fetch file from IPFS, file does probably not exist.")
        raise ValueError
    except HTTPError:
        print("Could not fetch file from IPFS, Hash was of the wrong format. Length: {}"
              .format(len(timestamp)))
        raise ValueError
    os.chdir(cur_dir)
    return path


def preprocess_doc(html_text):
    """
    Preprocessing of an html text as a String is done here. Tags that are advertisement and that do not describe the
    content are removed at first. The encoding is detected and next the html is parsed and preprocessed using the
    readability-lxml Document class to clean the content (text and images embedded in the text).
    An HTML string is returned together with the title of the website.

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
    doc = Document(str(bs.html), negative_keywords=negative_tags, positive_keywords=positive_tags)
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


def submit(sha256, title=None):
    """
    Submits the given hash to the originstamp API and returns the request object.

    :author: Sebastian
    :param sha256: hash to submit
    :param title: title of the hashed document
    :returns: resulting request object
    """
    headers = {'Content-Type': 'application/json', 'Authorization': 'Token token="{}"'.format(api_key)}
    data = {'hash_sha256': sha256, 'title': title}
    return requests.post(api_post_url, json=data, headers=headers)


def get_originstamp_history(sha256):
    """
    Fetches the history of the hash from originstamp. Response object looks like the following. Most important for
    StampTheWeb is the created_at tag:
    {'title': '', 'created_at': '2016-06-23T08:36:21.242Z', 'updated_at': '2016-06-24T00:02:28.728Z',
    'blockchain_transaction': {'created_at': '2016-06-24T00:02:26.796Z', 'updated_at': '2016-06-26T20:04:08.674Z',
    'public_key': '03a1673f7e06c345e3f8f26160b42616f421041e13b301e561b52aaeaa62f2deda', 'status': 1,
    'seed': '<very long seed representing the blockchain>',
    'private_key': 'a3dabafdc73c4b0bcc50191aef89c3fdb5cf9e728af6bcddec3a9905b04a4092',
    'recipient': '1KLwyN4qoA6yTmdr39Eqj5b1FCW6hxik9R', 'tx_hash':
    'd9496339662ad07e693605e9e374fb3cc09058f59b7c4ab2a958d713d9232cb2'},
    'hash_sha256': 'QmXiSkFRT7agFChpLa5BhJkvDAVHEefrekAf7DWjZKnmE8', 'submitted_at': None}

    :author: Sebastian
    :param sha256: hash to submit
    :returns: resulting response object
    """
    headers = {'Content-Type': 'application/json', 'Authorization': 'Token token={}'.format(api_key)}

    return requests.get("{}/{}".format(api_post_url, sha256), headers=headers)
