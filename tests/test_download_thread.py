import unittest
import requests
from app.main import download_thread as down
import app.main.downloader as downloader
from app import create_app, db
import ipfsApi as ipfs
import os
import logging
from bs4 import BeautifulSoup as Bs
from readability import Document

proxy = "5.135.176.41:3123"
url = "http://www.theverge.com/2016/8/12/12444920/no-mans-sky-travel-journal-day-four-ps4-pc"
path = "/home/sebastian/testing-stw/temporary/1/"
base_path = "/home/sebastian/testing-stw/"
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
    <img alt="image" class="alignright wp-image-15034 size-thumbnail" ipfs-src="ipfs_hash comes here" src="https://netninja.com/wp-content/uploads/2015/09/image2-150x150.jpeg"/>

   </p>
   <p id="secondpara" align="blah">This is paragraph that is almost equally long.
    <b>two
    </b>.
    <img alt="cat" class="size-thumbnail wp-image-15040 aligncenter" ipfs-src="ipfs_hash comes here" src="https://netninja.com/wp-content/uploads/2015/09/cat-150x150.jpg"/>

   </p>
  </body>
 </html>"""


class BasicsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = ipfs.Client()
        db.create_all()
        log_handler = logging.FileHandler('/home/sebastian/testing-stw/STW.log')
        log_handler.setLevel(logging.INFO)
        self.app.logger.setLevel(logging.INFO)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_thread_initialization(self):
        #TODO
        print("Test thread initialization:")
        thread = down.DownloadThread(1, url, proxy, base_path=base_path)
        self.assertEqual(thread.url, url)
        self.assertEqual(thread.threadID, 1)
        self.assertEqual(thread.path, path)
        self.assertTrue(os.path.exists(path))
        print("    Download folder was created.")
        self.assertEqual(thread.phantom.capabilities.get("proxy")["proxy"], proxy)
        print("    Proxy is set correctly to " + proxy + ".")

    def test_class(self):
        print("Testing the functionality of the DownloadThread class")
        thread = down.DownloadThread(1, url, proxy, base_path=base_path)
        start = thread.start()
        print(start)
        print("    Waiting for thread to join.")
        result = thread.join()
        print("after join:\n" + thread.html)
        print("    Testing whether thread is alive")
        self.assertFalse(thread.is_alive())
        print("    The resulting html:\n" + result.html)
        print("    Testing the IPFS hash: \n" + str(result.ipfs_hash))
        self.assertIsNotNone(result.ipfs_hash)
        if result.ipfs_hash:
            file_path = downloader.ipfs_get(result.ipfs_hash)
            self.assertTrue(os.path.exists(file_path))
        else:
            raise self.failureException

    def test_load_images(self):
        print("Testing the load_images method")
        thread = down.DownloadThread(2, url, html=html, base_path=base_path)
        soup = Bs(html, "lxml")
        images = thread.load_images(soup)
        self.assertEqual(len(images), 2)

