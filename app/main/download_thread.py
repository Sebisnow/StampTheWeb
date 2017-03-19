import threading
import re
import os
import urllib.error
from datetime import datetime
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
from selenium.common.exceptions import TimeoutException, WebDriverException
from requests.exceptions import ReadTimeout, HTTPError
from warc3 import warc
import binascii

from app.main import proxy_util
from app.main.proxy_util import logger

# from ..models import Warcs

exit_flag = 0
ipfs_Client = ipfsApi.Client('127.0.0.1', 5001)
js_path = os.path.abspath(os.path.expanduser("~/") + '/bin/phantomjs/lib/phantom/bin/phantomjs')

api_key_v1 = '7be3aa0c7f9c2ae0061c9ad4ac680f5c'
api_key_v2 = '3b0f883a-1e67-432a-95d9-b54512b6f199'
api_post_url_v2 = 'https://api.originstamp.org/api/'
api_post_url_v1 = 'http://www.originstamp.org/api/stamps'
header = {'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.9; rv:32.0) Gecko/20100101 Firefox/32.0'}

negative_tags = ["ad", "advertisement", "gads", "iqad", "anzeige", "dfp_ad"]
# :param negative_classes: if any HTML tags are definitely just advertisement and definitely not describe the content
# the tag can be added using a pipe. E.g "aside|ad".
negative_classes = re.compile("aside", re.I)
positive_classes = re.compile("article|article-title|headline|breitwandaufmacher|article-section|article.*", re.I)


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
        logger("Starting Thread-{}".format(str(thread_id)))

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

            self.phantom = self.initialize(self.proxy, self.prox_loc, self.threadID)
        else:
            self.extension_triggered = True
            self.phantom = self.initialize(thread_id=self.threadID)
            logger("Thread{} was extension triggered!".format(self.threadID))

        # create temporary storage folder
        if not os.path.exists(self.path):
            try:
                os.mkdir(self.path)
            except FileNotFoundError:
                # should only be thrown and caught in testing mode!
                logger("Thread-{}: Path not found: {}".format(self.threadID, self.path))
                if app.config["TESTING"]:
                    self.path = os.path.abspath(os.path.expanduser("~/")) + "/testing-stw/temporary"
                    logger("Thread-{}: Testing, so new path is: {}".format(self.threadID, self.path))
                else:
                    self.path = "{}/StampTheWeb/{}temporary".format(os.path.abspath(os.path.expanduser("~/")),
                                                                    self.storage_path)
                    if not os.path.exists(self.path.rpartition("/")[0]):
                        os.mkdir(self.path.rpartition("/")[0])

                if not os.path.exists(self.path):
                    os.mkdir(self.path)

        self.path = "{}/{}/".format(self.path, str(thread_id))
        logger("Initialized a new Thread: {} with proxy {} and location {}"
               .format(str(self.threadID), self.proxy, self.prox_loc))

        # remove temporary folder with thread id as name and recreate
        if os.path.exists(self.path):
            shutil.rmtree(self.path)
        os.mkdir(self.path)

    @staticmethod
    def initialize(proxy=None, proxy_location=None, thread_id=404):
        """
        Helper method that initializes the PhantomJS Headless browser and sets the proxy.

        :author: Sebastian
        :param proxy: The proxy to set.
        :param proxy_location: A location for a proxy. If no proxy is specified it is fetched from that location.
        :param thread_id: The thread that started the initialization process. Only for logging purposes.
        :return: The PhantomJS driver object.
        """
        logger("Thread-{}: Initialize Phantom with proxy:{} and location: {}".format(thread_id, proxy, proxy_location))
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
                logger("Thread-{}: retrieve proxy for location: {}".format(thread_id, proxy_location))
                new_proxy = proxy_util.get_one_proxy(proxy_location)

            except RuntimeError:
                logger("Thread-{}: Restarted proxy retrieval with new event loop".format(thread_id))
                asyncio.set_event_loop(asyncio.new_event_loop())
                new_proxy = proxy_util.get_one_proxy(proxy_location)

            service_args = [
                '--proxy={}'.format(new_proxy),
                '--proxy-type=http',
            ]
        else:
            service_args = []
            logger("Thread-{}: Neither proxy nor location are set, doing things locally".format(thread_id))
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
        logger("Thread-{}: Setting up proxies {} from {}".format(self.threadID, self.proxy, self.prox_loc))
        if self.proxy is not None:
            alive = proxy_util.is_proxy_alive(self.proxy, timeout=4)
            if self.prox_loc is None:
                self.prox_loc = proxy_util.ip_lookup_country(self.proxy.split(":")[0])
            if not alive:
                if not self._get_one_proxy(self.prox_loc):
                    logger("Thread-{}: Setting up proxies failed. Trying without proxies!".format(self.threadID))
                    self.prox_loc, self.proxy = None, None

        else:

            if self.prox_loc is not None and self._get_one_proxy(self.prox_loc):
                    logger("Thread-{}: Setting up proxies failed. Trying without proxies!".format(self.threadID))
                    self.prox_loc, self.proxy = None, None
        logger("Thread-{}: Proxies set up {} from {} ".format(self.threadID, self.proxy, self.prox_loc))

    def run(self):
        """
        Run the initialized thread and start the download job. Afterwards submit the hash to originstamp to create a
        lasting and verifyable timestamp. If HTML is not allowed to be retrieved by the crawler raise URLError.

        :author: Sebastian
        :raises URLError: Is raised if HTML retrieval is forbidden by robots.txt.
                ValueError: Is raised if URL was unreachable due to heuristics failure.
        """
        logger("Started Thread-{}: {}".format(self.threadID, self))
        if self.robot_check and not self.bot_parser.can_fetch(self.url):
            self.error = urllib.error.URLError("Not allowed to fetch root html file specified by url:{} because of "
                                               "robots.txt".format(self.url))
            logger("Thread-{}: {}".format(self.threadID, self.error))
            raise self.error
        try:
            self.download()
        except ValueError as e:
            self.error = e
            logger("Thread-{}: {}".format(self.threadID, self.error))
            raise e
        except (RuntimeError, ConnectionResetError, TimeoutException, HTTPError) as e:
            # Give it another try
            logger("Thread-{}: {} ---  We're giving it a second try".format(self.threadID, e))
            try:
                if self.prox_loc is None:
                    self.download()
                elif not proxy_util.is_proxy_alive(self.proxy, 3):
                    self._get_one_proxy()
                    self.download()
                else:
                    raise ValueError("Thread-{} Proxy checked after failed retrieval, but proxy is alive"
                                     .format(self.threadID))
            except (RuntimeError, ConnectionResetError, TimeoutException, HTTPError, ValueError) as e:
                self.error = e
                logger("Thread-{} Gave it a second try, still didn't work. URL unreachable because of {}"
                       .format(self.threadID, e))
                self.phantom.quit()
                raise e
        # submit the hash to originstamp to create a lasting timestamp.
        if self.error is None:
            logger("Thread-{}: Encountered no errors, going for submission".format(self.threadID))
            self.handle_submission()
        self.phantom.quit()

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
            logger(" Thread-{}: Downloading {}, proxy is set to({}): {}".format(self.threadID, self.url, self.prox_loc,
                                                                                self.proxy))
            # try downloading, if site is unreachable through proxy reinitialize with new proxy from same location.
            if not self._download_html():
                logger("Thread-{}: Couldn't reach website through proxy, trying again with new proxy"
                       .format(self.threadID))
                if self._get_one_proxy(self.prox_loc):
                    self.initialize(self.proxy, self.prox_loc, self.threadID)

                # try again, if False is returned site was unreachable again -> propagate upwards by raising error
                if not self._download_html() and not self._download_html_backup():
                    logger("Thread-{}: Again, couldn't reach website through two proxies and without phantomJS, "
                           "unreachable from loc {}".format(self.threadID, self.prox_loc))
                    self.error = TimeoutException("Thread-{}: Couldn't reach website through two proxies, unreachable "
                                                  "from loc {}".format(self.threadID, self.prox_loc))
                    raise self.error

        # check that HTML was really downloaded and is not an error page using the proxy by checking simple heuristics
        if self.proxy is not None and not is_correct_html(self.html, self.threadID, self.url):
            self.error = ValueError("Thread-{}: Website did not pass the heuristics check. Unreachable from "
                                    "loc {} with {}".format(self.threadID, self.prox_loc, self.proxy))
            logger(str(self.error))
            raise self.error

        self.html, self.title = preprocess_doc(self.html)
        soup = BeautifulSoup(self.html, "lxml")

        self.images = self._load_images(soup, self.proxy)
        with open(self.path + "page_source.html", "w") as f:
            f.write(self.html)

        self.ipfs_hash = binascii.hexlify(add_to_ipfs(self.path + 'page_source.html').encode('utf-8')).decode('utf-8')
        logger("Thread-{} Downloaded and submitted everything to ipfs: \n{}".format(self.threadID, self.ipfs_hash))

        with open(proxy_util.base_path + self.ipfs_hash + ".html", "w") as f:
            f.write(self.html)

    def _download_html(self):
        """
        Helper Method that downloads the HTML after scrolling down to enable dynamic content.

        :author: Sebastian
        :returns: returns False if an error occurred during the HTML downloading. Otherwise returns True
        """
        try:
            self.phantom.get(self.url)
        except TimeoutException as e:
            logger("Thread-{}: Could not access website : {}".format(self.threadID, e))
            return False
        except urllib.error.URLError as e:
            logger("Thread-{}: Could not access website, proxy refused connection: {}".format(self.threadID, e))
            return False
        logger("Thread-{}: Accessed website successfully".format(self.threadID))
        try:
            self.scroll(self.phantom)
        except WebDriverException as e:
            #print error but continue without scrolling down until alternative is found
            #TODO find alternative to scrolling via javascript eval() as some security policies disallow it.
            logger(e.msg)

        self.html = str(self.phantom.page_source)
        logger("Thread-{}: Downloaded website successfully".format(self.threadID))
        return True

    def _download_html_backup(self):

        logger("Thread-{}Trying the backup without phantomJS".format(self.threadID))
        try:
            """
            First we try to get the image with a proxy. If that fails we try it without proxy.
            """
            if self.proxy is not None:
                res = requests.get(self.url, stream=True, proxies={"http": "http://" + self.proxy}, headers=header)
                return res

            res = requests.get(self.url, stream=True, headers=header)
        except ConnectionRefusedError or MaxRetryError as con:
            logger("Thread-{} Could not request page due to: {}\ntrying without proxy.".format(
                self.threadID, con.strerror))
            try:
                res = requests.get(self.url, stream=True, headers=header)
            except OSError:
                return False
        except OSError:
            return False
        if res.status_code == 200:
            logger("Thread-{} successfully requested page without phantomJS and html:\n {}".format(
                self.threadID, res.status_code, res.text))
            self.html = res.text
            return True
        return False

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
        logger("Thread-{} Loading images".format(self.threadID))
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
                logger("Thread-{} Could not connect to retrieve image. Can't retrieve from this location."
                       .format(self.threadID))
                continue
            except urllib.error.URLError as e:
                logger(str(e))
                continue

            if res.status_code == 200:
                filename = 'img{}'.format(str(img_ctr))
                img_ctr += 1

                with open(filename, 'wb') as f:
                    for chunk in res.iter_content(1024):
                        f.write(chunk)

                image_hash = add_to_ipfs(filename)
                logger("Thread-{}: Added image to ipfs: {}".format(self.threadID, filename))
                img['ipfs-src'] = image_hash
                files[img_ctr] = {"filename": filename,
                                  "hash":     image_hash}

        logger("Thread-{} Downloaded images: {}".format(self.threadID, str(files)))
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

        attributes = ['src', 'data-full-size', 'data-original', 'data']
        tag = None
        for attr in attributes:
            if attr in img.attrs and proxy_util.url_specification.match(img[attr]):
                tag = img[attr]
            elif attr in img.attrs and _starts_with_slashes(img[attr]):
                tag = "http:{}".format(img[attr])
        if tag is None:
            msg = "Thread-{}: An image did not have an html specification url: {}".format(self.threadID, img)
            logger(msg)
            raise NameError(msg)
        logger("Thread-{}: Trying to download image: {}".format(self.threadID, tag))
        if self.robot_check and not self.bot_parser.can_fetch(self.url):
            text = "Thread-{}: Not allowed to fetch image file specified by url:{} because of robots.txt"\
                .format(self.threadID, self.url)
            logger(text)
            raise urllib.error.URLError(text)

        try:
            """
            First we try to get the image with a proxy. If that fails we try it without proxy.
            """
            if proxy:
                res = requests.get(tag, stream=True, proxies={"http": "http://" + proxy}, headers=header)
                return res

            res = requests.get(tag, stream=True, headers=header)
        except ConnectionRefusedError or MaxRetryError as con:
            logger("Thread-{} Could not request image due to: {}\ntrying without proxy.".format(
                self.threadID, con.strerror))
            res = requests.get(tag, stream=True, headers=header)
        except ConnectionResetError as reset:
            raise reset

        return res

    def _make_pdf(self):
        """
        Creates a pdf file from the preprocessed html with the images embedded in it.

        """
        # TO DO preserve links done
        html_path = "{}pdf_source.html".format(self.path)
        pdf_path = "{}{}.pdf".format(self.storage_path, self.ipfs_hash)
        #if not os.path.exists(pdf_path):  # Always create pdf even if overwrite is necessary
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
        logger("Thread-{}: Created PDF file from Preprocessed and img source changed html file: {}"
               .format(self.threadID, pdf_path))
        #else:
        #   logger("Thread-{}: PDF exists already in {}!".format(self.threadID, pdf_path))

    def _get_one_proxy(self, location=None):
        """
        Fetches one proxy using the proxy util. Sets self.proxy directly. Handles RuntimeError of proxybroker.

        :param location: Two letter iso country code to fetch a proxy from. If not present fetches a random active proxy
         from the static proxy list.
        :return: Returns True if everything worked as planned, otherwise False.
        """
        prox_loc, proxy = proxy_util.get_one_proxy(location)
        if proxy is None:
            return False
        self.prox_loc = prox_loc if prox_loc is not None else self.prox_loc
        self.proxy = proxy
        return True

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
        logger("Thread-{}: Adding to warc".format(self.threadID))
        # TODO only store references to ipfs in warc. binary data is difficult to work with and storage inefficient.
        # TODO store one WARC per URL instead of only one WARC - issue is the IPFS/IPNS publishing.
        originstamp_result = self.originstamp_result

        path_to_warc = "{}warcs/{}.warc.gz".format(self.storage_path, urlparse(self.url).netloc)
        # found_warc = Warcs.query.filter(Warcs.url.equals(self.url))
        with warc.open(path_to_warc, "ab") as warc_file:

            record_header = warc.WARCHeader({'hash_value': self.ipfs_hash, 'title': originstamp_result['title'],
                                             'ipfs_address': convert_from_hex(self.ipfs_hash), 'country': self.prox_loc,
                                             'creation_time': originstamp_result['created_at'],
                                             'content_type': 'application/warc-fields', 'WARC-Target-URI': self.url,
                                             'robots_txt': self.robot_check})

            content_block = '"{}"\n'.format(self._create_content()).encode()
            record = warc.WARCRecord(record_header, content_block, defaults=True)
            record.header.setdefault("content-type", "application/json")

            warc_file.write_record(record)
        logger("Thread-{}: Finished adding to warc, the path is: {}".format(self.threadID, path_to_warc))
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
        Handles the submission of the hash to OriginStamp to create the actual timestamp.
        The title that is submitted to OriginStamp contains the URL in Memento format.
            (For reference see: http://timetravel.mementoweb.org/about/)
        Handles PNG and PDF creation and storage. Sets location to Germany if no proxy was used.

        :author: Sebastian
        """
        logger("Thread-{} submit hash to originstamp.".format(self.threadID))
        if self.prox_loc is None:
            #TO DO define default location as constant
            self.prox_loc = "DE"
        self.originstamp_result = submit(self.ipfs_hash, title="StampTheWeb decentralized timestamp of article {} at "
                                                               "{} from location {}"
                                         .format(self.url, datetime.utcnow().strftime("%Y%m%d%H%M"), self.prox_loc))
        logger("Thread-{}: Originstamp result: {}".format(self.threadID, str(self.originstamp_result.text)))
        if self.originstamp_result.status_code != 200:
            msg = "Thread-{} Originstamp submission returned {} and failed for some reason: {}"\
                .format(self.threadID, str(self.originstamp_result.status_code), self.originstamp_result.text)
            self.error = HTTPError(msg)
            # self.originstamp_result = self.originstamp_result.json()
            logger(msg)
            raise self.error
        else:
            self._take_screenshot()
            self._make_pdf()

            #TODO in new OriginStamp API there will eb no error on second submit - no harm done though
            if "errors" in self.originstamp_result.text:
                logger("Thread-{} submitted hash to originstamp but the content has not changed. A timestamp "
                       "exists already.".format(self.threadID))
                # hash already submitted
                self.already_submitted = True
                history = get_originstamp_history(self.ipfs_hash)
                if history.status_code == 200:
                    self.originstamp_result = history.json()
                    self.originstamp_result["created_at"] = self._format_date(
                        self.originstamp_result["date_created"]/1000)

            else:
                logger("Thread-{} successfully submitted hash to originstamp and created a new timestamp."
                       .format(self.threadID))
                self.originstamp_result = self.originstamp_result.json()
                #TODO format of timestamp? not unix timestamp three 0 at the end
                self.originstamp_result["created_at"] = self._format_date(self.originstamp_result["date_created"]/1000  )
                logger("Thread-{} returned the following originstamp Result: {}".format(self.threadID,
                                                                                        self.originstamp_result[
                                                                                            "created_at"]))
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
        self.phantom.get_screenshot_as_file(screenshot_path)
        """logger("Screenshot present at {}: {}".format(screenshot_path, os.path.exists(screenshot_path)))
        if not os.path.exists(screenshot_path):
            logger("Thread-{}: No Screenshot available yet. Writing png to: {}"
                   .format(self.threadID, screenshot_path))
            self.phantom.get_screenshot_as_file(screenshot_path)
        else:
            logger("Thread-{}: Screenshot present at: {}".format(self.threadID, screenshot_path))"""
        self.screenshot["ipfs_hash"] = add_to_ipfs(screenshot_path)
        self.screenshot["path"] = screenshot_path

    @staticmethod
    def _format_date(date):
        """
        Expects a unix timestamp
        :param date: unix timestamp in seconds
        :return: The time as String in %Y-%m-%d %H:%M:%S format
        """
        return datetime.fromtimestamp(int(date)).strftime('%Y-%m-%dT%H:%M:%S.%fZ')

    @staticmethod
    def scroll(phantom):
        try:
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
        except WebDriverException as e:
            logger("Could not scroll down due to javascript security policy forbidding the use of eval: {}"
                   .format(e.msg))
            raise e

    def get_links(self):
        """
        Checks the html for valid links and returns them as a list.
        :return: A list of links. If there is no html yet or if there are no links to be found the list is empty.
        """
        logger("Thread-{} Getting Links:".format(self.threadID))
        links = list()
        if self.html is not None:
            soup = BeautifulSoup(self.html, "lxml")
            for tag in soup.find_all("a"):
                link = tag.get("href")
                if re.match(proxy_util.url_specification, str(link)):
                    logger("Thread-{} has link: {}".format(self.threadID, link))
                    links.append(link)
        return links


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
            logger("IPFS result from list: " + str(res[0]))
            return res[0]['Hash']

        logger("IPFS result: " + str(res))
        return res['Hash']
    else:
        res = ipfs_Client.add(fname, recursive=False)[0]
        logger("IPFS result for directory: " + str(res))
        return res['Hash']


def convert_from_hex(hex_string):
    """
    If timestamped contend via ipfs is to be reached the timestamp that is in hex since OriginStamp v2 needs to be
    reformatted to IPFS address.

    :param hex_string: The timestamp of Originstamp in SHA 256 in HEX
    :return: The IPFS address.
    """
    return binascii.unhexlify(hex_string.encode('utf-8')).decode('utf-8')


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
    logger("Trying to fetch the File from IPFS: {}".format(timestamp))
    try:
        ipfs_Client.get(timestamp, timeout=5)
    except ReadTimeout:
        logger("Could not fetch file from IPFS, file does probably not exist.")
        raise ValueError
    except HTTPError:
        logger("Could not fetch file from IPFS, Hash was of the wrong format. Length: {}"
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
    # remove some common advertisement tags beforehand
    bs = BeautifulSoup(html_text, "lxml")
    for tag_desc in negative_tags:
        for tag in bs.findAll(attrs={'class': re.compile(r".*\b{}\b.*".format(tag_desc))}):
            tag.extract()
    doc = Document(str(bs.html), negative_keywords=negative_classes, positive_keywords=positive_classes)
    try:
        # Detect the encoding of the html, if not detectable use utf-8 as default.
        encoding = chardet.detect(doc.content().encode()).get('encoding')
        title = doc.title()
    except TypeError or IndexError as e:
        logger("Encountered {} setting encoding to utf-8.".format(str(e)))
        encoding = "utf-8"
        title = bs.title.getText()
    if not encoding:
        logger("Using default encoding utf-8")
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
    logger('Preprocessing done. Type of text is: {}, Length of test is {}'.format(type(text), len(text)))
    return text, title


def submit(sha256, title=None):
    """
        Submits the given hash to the originstamp API and returns the request object.

        :author: Sebastian
        :param sha256: hash to submit
        :param title: title of the hashed document
        :returns: resulting request object
        """
    headers = {'Content-Type': 'application/json', 'Authorization': api_key_v2}
    data = {'hash_sha256': sha256, 'title': title}
    return requests.post(api_post_url_v2 + sha256, json=data, headers=headers)


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
    headers = {'Content-Type': 'application/json', 'Authorization': api_key_v2}

    return requests.get("{}/{}".format(api_post_url_v2, sha256), headers=headers)


def submit_v_1(sha256, title=None):
    """
    Submits the given hash to the originstamp API and returns the request object.

    :author: Sebastian
    :param sha256: hash to submit
    :param title: title of the hashed document
    :returns: resulting request object
    """
    headers = {'Content-Type': 'application/json', 'Authorization': 'Token token="{}"'.format(api_key_v1)}
    data = {'hash_sha256': sha256, 'title': title}
    return requests.post(api_post_url_v1, json=data, headers=headers)


def get_originstamp_history_v1(sha256):
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
    headers = {'Content-Type': 'application/json', 'Authorization': 'Token token={}'.format(api_key_v1)}

    return requests.get("{}/{}".format(api_post_url_v1, sha256), headers=headers)


def is_correct_html(html, t_id=None, url=None):
    """
    Applies heuristics to filter "incorrect" HTML. Checks the character length of the HTML as proxies sometimes send
    back empty HTMLs. In short HTMLs it checks for keywords like Error or Denied as heuristics.

    :author: Sebastian
    :param html: The HTML as String.
    :param t_id: Optional parameter used only for logging in case this method is called by a DownloadThread to
    associate the text in the log with the thread.
    :param url: THe url that the html was retrieved from. Used as an exception to the length rule if url is
    proxy_util.ip_check_url = "http://httpbin.org/ip"
    :return: True if the heuristics conclude it is a real HTML without errors, otherwise False.
    """

    keywords = ["Error", "ERROR", "Denied", "Authentication Required", "Authenticate"]
    if html is None:
        logger("Thread-{} Failed the HTML correctness check on 1. condition it is None".format(t_id))
        return False
    if url is not None and url.find("httpbin.org") != -1:
        logger("Thread-{} HTML correctness check succeeded, because URL is {}!".format(t_id, url))
        return True
    if len(html) < 300:
        logger("Thread-{} Failed the HTML correctness check on 2. condition it is too small".format(t_id))
        return False
    if len(html) < 1000:
        for key in keywords:
            if key in html:
                logger("Thread-{} Failed the HTML correctness check on 3. condition for Keyword '{}'".format(t_id, key))
                return False
    logger("Thread-{} HTML correctness check succeeded. HTML seems valid!".format(t_id))
    return True


def _starts_with_slashes(img_attr):
    if str(img_attr).startswith("//"):
        return True
    else:
        return False
