import unittest
from app.main import downloader as down
from app.main import proxy_util, download_thread
from flask import current_app
from app import create_app, db
import ipfsApi
import os
import logging
from subprocess import check_output, DEVNULL

from app.models import Post

url = "http://www.theverge.com/2016/8/12/12444920/no-mans-sky-travel-journal-day-four-ps4-pc"
sz_url = "http://www.sueddeutsche.de/wirtschaft/oelpreis-saudischer-oelminister-die-oelflut-ist-zu-ende-1.3047480"


class ThreadSubstitute:
    def __init__(self, threadID, ipfs_hash, url, prox_loc, error=None):
        self.threadID = threadID
        self.ipfs_hash = ipfs_hash
        self.url = url
        self.prox_loc = prox_loc
        self.error = error


class BasicsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = ipfsApi.Client()
        db.create_all()
        down.basePath = "/home/sebastian/testing-stw/"
        download_thread.base_path = "/home/sebastian/testing-stw/"
        proxy_util.proxy_path = "/home/sebastian/PycharmProjects/STW/static/"
        log_handler = logging.FileHandler('/home/sebastian/testing-stw/STW.log')
        log_handler.setLevel(logging.INFO)
        self.app.logger.setLevel(logging.INFO)

    def tearDown(self):
        db.session.remove()
        # db.drop_all()
        self.app_context.pop()

    def test_app_exists(self):
        print("test app exists")
        self.assertFalse(current_app is None)

    def test_app_is_testing(self):
        print("test app is testing")
        self.assertTrue(current_app.config['TESTING'])

    def test_get_originstamp_history(self):
        sha256 = "QmXiSkFRT7agFChpLa5BhJkvDAVHEefrekAf7DWjZKnmE8"
        print("Test getting history from Originstamp")
        response = down.get_originstamp_history(sha256)
        body = response.json()
        print("    Creation Time: " + body["created_at"])
        print(response.json())
        self.assertIsNotNone(response)

    def test_text_timestamp(self):
        print("test submit to Originstamp")
        text = "Big test in Python!"
        result = down.get_text_timestamp(text)
        print(result)
        print("    Submit Status code: " + str(result.originStampResult.status_code))
        print("    Submit Response Text: " + result.originStampResult.text)
        print("    Submit Hash: " + result.hashValue)
        print("    Submit Title: " + result.webTitle)
        self.assertTrue(result.originStampResult.status_code == 200)
        with open("test1.html", "w+") as f:
            f.write(str(text))
            print(f.encoding)
        hashval = self.client.add("test1.html")
        print(hashval)

        retur = check_output(['ipfs', 'get', hashval['Hash']], stderr=DEVNULL)
        print(retur.decode())
        doc = ""
        with open(hashval['Hash'], "r") as f:
            doc += f.read()
        self.assertEqual(str(text), doc)

    def test_ipfs_hashing(self):
        print("test IPFS hashing")
        result = down.get_text_timestamp("Big test in Python")

        text = self.client.cat(result.hashValue)
        print("    Submitted Text: 'Big test in Python'")
        print("    Text from IPFS by Hash: " + text)
        self.assertEqual(text, "Big test in Python")

    def test_sys(self):
        print("System testing")
        result = down.get_url_history(url)
        # TODO fails so far
        self.assertEqual(result.originStampResult.status_code, 200, "   Status code is " +
                         str(result.originStampResult.status_code))
        print("    Submitted URL, Status code: " + str(result.originStampResult.status_code))
        self.assertIsNotNone(result.originStampResult.headers['Date'])
        print("    Return Headers have 'Date' attached: " + result.originStampResult.headers['Date'])
        print("    Return Message: " + result.originStampResult.text)
        self.sys_data_test(result)

    def sys_data_test(self, result):
        # Helper Method for test_sys

        hash_val = result.hashValue
        print("    Check for HTML")
        self.assertTrue(os.path.exists(down.basePath + hash_val + ".html"), "HTML was not created")
        print("    Check for PNG")
        self.assertTrue(os.path.exists(down.basePath + hash_val + ".png"), "PNG was not created")
        print("    Check for PDF")
        self.assertTrue(os.path.exists(down.basePath + hash_val + ".pdf"), "PDF was not created")

    def test_hash_consistency(self):
        print("Testing the Hash Values")

        thread1 = down.get_url_history(sz_url)
        print("    Testing the resulting Hash Values for consistency")
        thread2 = down.get_url_history(sz_url)
        print(thread1.hashValue)
        print(thread2.hashValue)
        print("    Second function call finished")
        thread3 = down.get_url_history("http://www.sueddeutsche.de/wirtschaft/oelpreis-saudischer-oelminister-die"
                                       "-oelflut-ist-zu-ende-1.3047480")

        print("    Checking the first two of three hashes")
        self._baseAssertEqual(thread1.hashValue, thread2.hashValue, "The Hash Values of 1 and 2 do not match")
        print("    Checking the second two of three hashes")
        self._baseAssertEqual(thread2.hashValue, thread3.hashValue, "The Hash Values of 2 and 3 do not match")

    def test_save_file_ipfs(self):
        test_sha = "QmREyeWxAGtuQ5UiiTs13zp5ZamjkVBYpnDCF1bTgn7Atc"
        # :param test_sha: this is the IPFS hash of the example.html content
        print("Testing the save_file_ipfs with test hash and example input file to verify the IPFS saving steps")
        with open(down.basePath + "example.html", "r") as f:
            ex_text = f.read()
        sha256 = down.save_file_ipfs(ex_text)
        print("    The example hash: " + test_sha)
        print("    The returned hash: " + sha256)
        self.assertEqual(sha256, test_sha)

    def test_create_html_from_url(self):
        test_sha = "QmREyeWxAGtuQ5UiiTs13zp5ZamjkVBYpnDCF1bTgn7Atc"
        print("Testing the create_html_from_url method to verify IPFS gets the file and it is renamed to have a .html "
              "ending.")
        if os.path.exists(down.basePath + test_sha + ".html"):
            os.remove(down.basePath + test_sha + ".html")
        print("    There is a file called " + test_sha + ".html (should be False): " + str(os.path.exists(
            down.basePath + test_sha + '.html')))
        # :param test_sha: this is the IPFS hash of the example.html content

        with open(down.basePath + "example.html", "r") as f:
            ex_text = f.read()
        down.create_html_from_url(ex_text, test_sha, "test-URL")
        print("    There is a file called " + test_sha + ".html: " + str(os.path.exists(
            down.basePath + test_sha + '.html')))
        self.assertTrue(os.path.exists(down.basePath + test_sha + '.html'))

    def test_distributed_timestamp_not_none(self):
        result = down.distributed_timestamp(url)
        self.assertIsNotNone(result)\


    def test_distributed_timestamp_with_proxy(self):
        result = down.distributed_timestamp(url, proxies=[["FR", "5.135.176.41:3123"]])
        self.assertIsNotNone(result)

    def test_check_threads_same_result(self):
        threads = list()
        for i in range(5):
            threads.append(ThreadSubstitute(threadID=i, ipfs_hash=33, url=str(i), prox_loc="any"))
        result_threads, votes = down.check_threads(threads)
        self.assertEqual(4, max(votes))

    def test_check_threads_twice_same_result(self):
        threads = list()
        for i in range(2):
            threads.append(ThreadSubstitute(threadID=i, ipfs_hash=33, url=str(i), prox_loc="any"))
        for i in range(3):
            threads.append(ThreadSubstitute(threadID=i, ipfs_hash=35, url=str(i), prox_loc="other"))
        result_threads, votes = down.check_threads(threads)
        self.assertEqual(2, max(votes))

    def test_check_threads_no_same_result(self):
        threads = list()
        for i in range(5):
            threads.append(ThreadSubstitute(threadID=i, ipfs_hash=i, url=str(i), prox_loc="any"))
        result_threads, votes = down.check_threads(threads)
        self.assertEqual(0, max(votes))

    def test_check_user(self):
        user = "Bot"
        sha256 = "Qmb833LJQKVSzdUJadMmjNyQRzarD2cmYx1LJFBX589zkK"
        db_user = down.check_user(user)
        db.session.commit()
        print("The user: {}".format(str(db_user)))
        self.assertEqual(113, db_user.id)

    def test_location_independant_timestamp(self):
        threads = down.location_independent_timestamp(url)
        self.assertIsNotNone(threads)
