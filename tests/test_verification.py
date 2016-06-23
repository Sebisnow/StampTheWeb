import unittest
from app.main import downloader as down
from flask import current_app
from app import create_app, db
import ipfsApi as ipfs


class BasicsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
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
        # TODO change to verification
        print("test submit to Originstamp")
        result = down.get_text_timestamp("Big test in Python")
        print("    Submit Status code: " + str(result.originStampResult.status_code))
        print("    Submit Response Text: " + result.originStampResult.text)
        print("    Submit Hash: " + result.hashValue)
        print("    Submit Title: " + result.webTitle)
        self.assertTrue(result.originStampResult.status_code == 200)

    def test_ipfs(self):
        # TODO change to verification by ipfs
        print("test IPFS")
        result = down.get_text_timestamp("Big test in Python")
        client = ipfs.Client()
        text = client.cat(result.hashValue)
        print("    Submited Text: 'Big test in Python'")
        print("    Text from IPFS by Hash: " + text)
        self.assertEqual(text, "Big test in Python")

