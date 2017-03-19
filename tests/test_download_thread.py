import unittest
import asyncio
from urllib.parse import urlparse
from warc3 import warc
from app.main import download_thread as down
import app.main.downloader as downloader
from app import create_app, db
import ipfsApi
import os
import logging
from bs4 import BeautifulSoup as Bs
import app.main.proxy_util as prox
from app.main import proxy_util
from datetime import datetime

proxy_location, proxy = proxy_util.get_one_random_proxy()
china, china_proxy = proxy_util.get_one_proxy("CN")
france, fr_proxy = proxy_util.get_one_proxy("FR")
url = "http://www.theverge.com/2016/8/12/12444920/no-mans-sky-travel-journal-day-four-ps4-pc"
blocked_url = "http://www.nytimes.com/2016/09/29/opinion/vladimir-putins-outlaw-state.html"
spiegel_url = "http://www.spiegel.de/politik/ausland/syrien-john-kerry-will-ermittlungen-wegen-" \
              "kriegsverbrechen-a-1115714.html"
base_path = "/home/sebastian/testing-stw/"
downloader.basePath = base_path
down.base_path = base_path
downloader.proxy_util.base_path = base_path
prox.static_path = os.path.abspath(os.path.expanduser("~/") + "PycharmProjects/STW/static/")
html = """
<html>
  <head>
   <title>Page title
   </title>
  </head>
  <body>
   <p id="firstpara" align="center">This is a veeeeery long paragraph
    <b>one
    </b>.
    <img alt="image" class="alignright wp-image-15034 size-thumbnail" ipfs-src="ipfs_hash comes here"
    src="https://netninja.com/wp-content/uploads/2015/09/image2-150x150.jpeg"/>

   </p>
   <p id="secondpara" align="blah">This is paragraph that is almost equally long.
    <b>two
    </b>.
    <img alt="cat" class="size-thumbnail wp-image-15040 aligncenter" ipfs-src="ipfs_hash comes here"
    src="https://netninja.com/wp-content/uploads/2015/09/cat-150x150.jpg"/>

   </p>
  </body>
 </html>"""


class BasicsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = ipfsApi.Client()
        db.create_all()
        down.basePath = "/home/sebastian/testing-stw/"
        log_handler = logging.FileHandler('/home/sebastian/testing-stw/STW.log')
        log_handler.setLevel(logging.INFO)
        self.app.logger.setLevel(logging.INFO)
        proxy_util.default_event_loop = asyncio.new_event_loop()

    def tearDown(self):
        db.session.remove()
        # db.drop_all()
        self.app_context.pop()

    def test_thread_initialization(self):
        print("Test thread initialization:")
        thread = down.DownloadThread(1, url, proxy, basepath=base_path)
        self.assertEqual(thread.url, url)
        self.assertEqual(thread.threadID, 1)

        path = "/home/sebastian/testing-stw/temporary/1/"
        self.assertEqual(thread.path, path)
        self.assertTrue(os.path.exists(path))
        print("    Download folder was created.")
        print(thread.phantom.service.service_args)
        self.assertEqual(thread.phantom.service.service_args[0], "--proxy={}".format(proxy))
        print("    Proxy is set correctly to " + proxy + ".")
        thread.phantom.capabilities["browserName"] = "Mozilla/5.0"
        print(str(thread.phantom.capabilities))

    def test_class_with_china_proxy(self):
        print("\nTesting the functionality of the DownloadThread class:")
        thread = down.DownloadThread(1, proxy_util.ip_check_url, china_proxy, prox_loc=china, basepath=base_path)
        thread.start()
        print("    Waiting for thread to join.")
        thread.join()
        print("    After join:\n" + str(thread.html))
        text = thread.html

        print("    The originstamp_result of this thread: \n{}\n And the errors if any:\n"
              .format(thread.originstamp_result, str(thread.error)))
        self.assertIsNotNone(text, "None HTML was stored and processed.")
        print("    Testing whether thread is alive")
        thread.join()
        self.assertFalse(thread.is_alive(), "Thread is still alive after join")
        ipfs_hash = thread.ipfs_hash
        self.assertIsNotNone(ipfs_hash, "The DownloadThread did not produce an ipfs_hash")
        if ipfs_hash:
            file_path = downloader.ipfs_get(ipfs_hash)
            self.assertTrue(os.path.exists(file_path), "File not transmitted to ipfs, it cannot be fetched")
        else:
            raise self.failureException

    def test_class_with_proxy(self):
        print("\nTesting the functionality of the DownloadThread class:")
        thread = down.DownloadThread(10, url=proxy_util.ip_check_url, proxy=fr_proxy, prox_loc=france, robot_check=False,
                                     basepath=base_path)
        thread.start()
        print("    Waiting for thread to join.")
        thread.join()
        print("    After join:\n" + str(thread.html))
        text = thread.html

        print("    The originstamp_result of this thread: \n{}\n And the errors if any:\n"
              .format(thread.originstamp_result, str(thread.error)))
        self.assertIsNotNone(text, "None HTML was stored and processed.")
        print("    Testing whether thread is alive")
        thread.join()
        self.assertFalse(thread.is_alive(), "Thread is still alive after join")
        ipfs_hash = thread.ipfs_hash
        self.assertIsNotNone(ipfs_hash, "The DownloadThread did not produce an ipfs_hash")
        if ipfs_hash:
            file_path = downloader.ipfs_get(ipfs_hash)
            self.assertTrue(os.path.exists(file_path), "File not transmitted to ipfs, it cannot be fetched")
        else:
            raise self.failureException

    def test_class_without_proxy(self):
        print("\nTesting the functionality of the DownloadThread class:")
        thread = down.DownloadThread(1, url, basepath=base_path)
        thread.start()
        print("    Waiting for thread to join.")
        thread.join()
        print("    After join:\n" + str(thread.html))
        text = thread.html

        print("    The originstamp_result of this thread: \n{}".format(str(thread.originstamp_result)))
        self.assertIsNotNone(text, "None HTML was stored and processed.")
        print("    Testing whether thread is alive")
        thread.join()
        self.assertFalse(thread.is_alive(), "Thread is still alive after join")
        ipfs_hash = thread.ipfs_hash
        self.assertIsNotNone(ipfs_hash, "The DownloadThread did not produce an ipfs_hash")
        if ipfs_hash:
            file_path = downloader.ipfs_get(ipfs_hash)
            self.assertTrue(os.path.exists(file_path), "File not transmitted to ipfs, it cannot be fetched")
        else:
            raise self.failureException

    def test_class_with_country(self):
        print("\nTesting the functionality of the DownloadThread class:")
        thread = down.DownloadThread(1, blocked_url, basepath=base_path, prox_loc="FR")
        thread.start()
        print("    Waiting for thread to join.")
        thread.join()
        print("    After join:\n" + str(thread.html))
        text = thread.html

        print("    The originstamp_result of this thread: \n{}".format(thread.originstamp_result))
        self.assertIsNotNone(text, "None HTML was stored and processed.")
        print("    Testing whether thread is alive")
        thread.join()
        self.assertFalse(thread.is_alive(), "Thread is still alive after join")
        ipfs_hash = thread.ipfs_hash
        self.assertIsNotNone(ipfs_hash, "The DownloadThread did not produce an ipfs_hash")
        if ipfs_hash:
            file_path = downloader.ipfs_get(ipfs_hash)
            self.assertTrue(os.path.exists(file_path), "File not transmitted to ipfs, it cannot be fetched")
        else:
            raise self.failureException

    def test_load_images(self):
        print("\nTesting the load_images method")
        thread = down.DownloadThread(2, url, html=html, basepath=base_path)
        soup = Bs(html, "lxml")
        images = thread._load_images(soup)
        self.assertEqual(len(images), 2)

    def test_zip_submission(self):
        """Deprecated"""
        print("Testing the IPFS submission of Zip files:")
        #os.chdir(base_path)
        res = down.add_to_ipfs(base_path + "sebastian.zip")
        self.assertTrue(res.isalnum)

    def test_preprocessing_aside_removal(self):

        with open("{}test.html".format(base_path), "r") as text:
            entire_site = text.read()
            preprocessed_text, title = down.preprocess_doc(html_text=entire_site)
            print(preprocessed_text)
            self.assertEqual(-1, preprocessed_text.find("<aside"))

    def test_download_blocked_site(self):
        thread = down.DownloadThread(101, blocked_url, proxy=china_proxy, prox_loc=china)
        thread.start()
        thread.join()
        print(str(thread.html))
        self.assertIsNotNone(thread.error)

    # fails if proxy needs to be set again, which is often the case
    def test_phantom_proxy(self):
        prox_loc, this_proxy = proxy_util.get_one_random_proxy()
        country = proxy_util.ip_lookup_country(this_proxy.split(":")[0])

        print(this_proxy.split(":")[0])
        thread = down.DownloadThread(101, proxy_util.ip_check_url, proxy=this_proxy,  prox_loc=country,
                                     basepath=base_path)
        thread.start()
        thread.join()

        print(thread.html)
        print(str(thread.error) + " | Was the error")
        print(thread.phantom.service.service_args)
        print(thread.html.find(this_proxy.split(":")[0]))
        self.assertNotEqual(-1, thread.html.find(this_proxy.split(":")[0]))

    def test_get_one_proxy_if_not_set(self):
        thread = down.DownloadThread(101, url, prox_loc="DE", basepath=base_path)
        thread.start()
        thread.join()
        self.assertIsNone(thread.error)
        self.assertIsNotNone(thread.html)

    def test_date_formatter(self):
        date = datetime.now()
        unix_timestamp = date.timestamp()
        print(unix_timestamp)
        print(type(unix_timestamp))
        print(date)

        formatted_timestamp = date.strftime("%Y%m%d%H%M")
        readable_date = down.DownloadThread._format_date(unix_timestamp)
        print(readable_date)
        self.assertEqual(readable_date, formatted_timestamp)

    @unittest.expectedFailure
    def test_warc_creation(self):
        thread = down.DownloadThread(101, proxy_util.ip_check_url, proxy=fr_proxy, prox_loc=france, basepath=base_path)

        path_to_warc = "{}warcs/{}.warc.gz".format(thread.storage_path, urlparse(thread.url).netloc)
        file_size = 0
        exists = os.path.exists(path_to_warc)
        if exists:
            file_size = os.path.getsize(path_to_warc)

        thread.start()
        thread.join()

        print("Path exists already: {}".format(exists))
        # thread._add_to_warc()
        self.assertGreater(os.path.getsize(path_to_warc), file_size)
        print("Path exists already: {}".format(os.path.exists(path_to_warc)))
        with warc.open(path_to_warc) as warc_file:
            for record, offset, leftover in warc_file.browse():
                print(str(record.header))
                print(str(record.payload.read()))
