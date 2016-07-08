import unittest
from app.main import downloader as down
from flask import current_app
from app import create_app, db
import ipfsApi as ipfs
import os
from subprocess import check_output, DEVNULL


class BasicsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = ipfs.Client()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_app_exists(self):
        print("test app exists")
        self.assertFalse(current_app is None)

    def test_app_is_testing(self):
        print("test app is testing")
        self.assertTrue(current_app.config['TESTING'])

    def test_text_timestamp(self):
        print("test submit to Originstamp")
        text = "Big test in Python"
        result = down.get_text_timestamp(text)
        print("    Submit Status code: " + str(result.originStampResult.status_code))
        print("    Submit Response Text: " + result.originStampResult.text)
        print("    Submit Hash: " + result.hashValue)
        print("    Submit Title: " + result.webTitle)
        self.assertTrue(result.originStampResult.status_code == 200)
        with open("test1.html", "w+") as f:
            f.write(str(text))
            print(f.encoding)
        hash = self.client.add("test1.html")
        print(hash)

        retur = check_output(['ipfs', 'get', hash['Hash']], stderr=DEVNULL)
        print(retur)
        doc = ""
        with open(hash['Hash'], "r") as f:
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
        down.basePath = '/home/sebastian/testing-stw/'

        result = down.get_url_history("http://www.sueddeutsche.de/wirtschaft/oelpreis-saudischer-oelminister-die"
                                      "-oelflut-ist-zu-ende-1.3047480")
        self.assertEqual(result.originStampResult.status_code, 200, "   Status code is " +
                         str(result.originStampResult.status_code))
        print("    Submitted URL, Status code: " + str(result.originStampResult.status_code))
        self.assertIsNotNone(result.originStampResult.headers['Date'])
        print("    Return Headers have 'Date' attached: " + result.originStampResult.headers['Date'])
        print("    Return Message: " + result.originStampResult.text)
        self.sys_data_test(result)

    def sys_data_test(self, result):
        hash_val = result.hashValue
        print("    Check for HTML")
        self.assertTrue(os.path.exists(down.basePath + hash_val + ".html"), "HTML was not created")
        print("    Check for PNG")
        self.assertTrue(os.path.exists(down.basePath + hash_val + ".png"), "PNG was not created")
        print("    Check for PDF")
        self.assertTrue(os.path.exists(down.basePath + hash_val + ".pdf"), "PDF was not created")

    def test_hash_consistency(self):
        print("Testing the Hash Values")
        down.basePath = '/home/sebastian/testing-stw/'

        thread1 = down.get_url_history("http://www.sueddeutsche.de/wirtschaft/oelpreis-saudischer-oelminister-die"
                                       "-oelflut-ist-zu-ende-1.3047480")
        print("    Testing the resulting Hash Values for consistency")
        thread2 = down.get_url_history("http://www.sueddeutsche.de/wirtschaft/oelpreis-saudischer-oelminister-die"
                                       "-oelflut-ist-zu-ende-1.3047480")
        print(thread1.hashValue)
        print(thread2.hashValue)
        print("    Second function call finished")
        thread3 = down.get_url_history("http://www.sueddeutsche.de/wirtschaft/oelpreis-saudischer-oelminister-die"
                                       "-oelflut-ist-zu-ende-1.3047480")

        print("    Checking the first two of three hashes")
        self._baseAssertEqual(thread1.hashValue, thread2.hashValue, "The Hash Values of 1 and 2 do not match")
        print("    Checking the second two of three hashes")
        self._baseAssertEqual(thread2.hashValue, thread3.hashValue, "The Hash Values of 2 and 3 do not match")
