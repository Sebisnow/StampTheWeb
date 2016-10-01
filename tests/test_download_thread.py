import unittest

import asyncio

from app.main import download_thread as down
import app.main.downloader as downloader
from app import create_app, db
import ipfsApi
import os
import logging
from bs4 import BeautifulSoup as Bs, BeautifulSoup
import app.main.proxy_util as prox
from app.main import proxy_util

proxy = "5.135.176.41:3123"
china_proxy = "58.67.159.50:80"
fr_proxy = "178.32.153.219:80"
url = "http://www.theverge.com/2016/8/12/12444920/no-mans-sky-travel-journal-day-four-ps4-pc"
blocked_url = "http://www.nytimes.com/2016/09/29/opinion/vladimir-putins-outlaw-state.html"
ip_check_url = "http://httpbin.org/ip"
base_path = "/home/sebastian/testing-stw/"
downloader.basePath = base_path
down.base_path = base_path
prox.proxy_path = os.path.abspath(os.path.expanduser("~/") + "PycharmProjects/STW/static/")
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
        #TODO
        print("Test thread initialization:")
        thread = down.DownloadThread(1, url, proxy, basepath=base_path)
        self.assertEqual(thread.url, url)
        self.assertEqual(thread.threadID, 1)

        path = "/home/sebastian/testing-stw/temporary/1/"
        self.assertEqual(thread.path, path)
        self.assertTrue(os.path.exists(path))
        print("    Download folder was created.")
        self.assertEqual(thread.phantom.capabilities.get("proxy")["proxy"], proxy)
        print("    Proxy is set correctly to " + proxy + ".")
        thread.phantom.capabilities["browserName"] = "Mozilla/5.0"
        print(str(thread.phantom.capabilities))

    def test_class_with_proxy(self):
        print("\nTesting the functionality of the DownloadThread class:")
        thread = down.DownloadThread(1, "http://www.ip-address.org/find-ip/check-my-ip.php", "122.193.14.106:80", prox_loc="CN", basepath=base_path)
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

    def test_class_without_proxy(self):
        print("\nTesting the functionality of the DownloadThread class:")
        thread = down.DownloadThread(1, url, basepath=base_path)
        thread.start()
        print("    Waiting for thread to join.")
        thread.join()
        print("    After join:\n" + str(thread.html))
        text = thread.html

        print("    The originstamp_result of this thread: \n{}".format(thread.originstamp_result.json()))
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
        images = thread.load_images(soup)
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
        thread = down.DownloadThread(101, blocked_url, proxy=china_proxy, prox_loc="CN")
        thread.start()
        thread.join()
        print(str(thread.html))
        self.assertIsNotNone(thread.error)

    def test_phantom_proxy(self):
        this_proxy = china_proxy
        print(this_proxy.split(":")[0])
        thread = down.DownloadThread(101, ip_check_url, proxy=this_proxy,  prox_loc="CN")
        thread.start()
        thread.join()
        """soup = BeautifulSoup(thread.html, "lxml")
        ips = list()
        for div in soup.find_all("div"):
            if div["class"] and div["class"] == "lanip":
                ips.append(div.string)
                print(ips)"""

        print(thread.html)
        print(str(thread.error) + " | Was the error")
        print(thread.phantom.service.service_args)
        print(thread.html.find(this_proxy.split(":")[0]))
        self.assertNotEqual(-1, thread.html.find(this_proxy.split(":")[0]))

    def test_get_one_proxy_if_not_set(self):
        thread = down.DownloadThread(101, ip_check_url, prox_loc="CN")
        thread.start()
        thread.join()
        soup = BeautifulSoup(thread.html, "lxml")
        ips = list()
        for div in soup.find_all("div"):
            if div["class"] and div["class"] == "lanip":
                ips.append(div.string)
                print(ips)
        self.assertIsNotNone(thread.html)
