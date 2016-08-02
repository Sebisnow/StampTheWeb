import os
import unittest
import tempfile
import requests
from app.main import downloader as down
from app.main import views as view
from app import create_app, db
import ipfsApi as ipfs
import logging


class BasicsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')

        os.remove('/home/sebastian/testing-stw/stw.log')
        log_handler = logging.FileHandler('/home/sebastian/testing-stw/stw.log')
        log_handler.setLevel(logging.INFO)
        self.app.logger.addHandler(log_handler)
        self.app.logger.setLevel(logging.INFO)
        self.app.logger.info("Start logging tests:\n")

        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = ipfs.Client()
        db.create_all()
        down.basePath = "/home/sebastian/testing-stw/"

        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_index(self):
        """
        Simulate the behaviour of the Timestamp extension that sends a POST request.
        """

        self.app.logger.info("Testing the index of views:")
        print("Testing the index of views:")

        resp = self.client.get('/', follow_redirects=True)
        self.app.logger.info("    Response is: " + str(resp))
        print("    Response is: " + str(resp))
        self.assertEqual(resp.status_code, 200)

    def test_extension_api(self):
        """
        Simulate the behaviour of the Timestamp extension that sends a POST request.
        """

        self.app.logger.info("Testing the web interface for the Timestamp Extension:")
        print("Testing the web interface for the Timestamp Extension:")

        url = "http://www.sueddeutsche.de/wirtschaft/oelpreis-saudischer-oelminister-die" \
              "-oelflut-ist-zu-ende-1.3047480"
        website = requests.get(url)
        requ_data = dict(
            URL=url,
            body=website.text,
            user="SomeOne"
        )
        # TODO does not work yet since on post the COntent-Type and the data is not really transmitted.
        resp = self.client.post('/timestamp', data=requ_data, content_type="application/json", follow_redirects=True)
        self.app.logger.info("    Response is: " + str(resp))
        print("    Response is: " + str(resp))
        print("    " + str(resp.headers))
        # TODO now tests whether it is correct json
        print("    Testing that non json data returns 415 error")
        self.assertEqual(resp.status_code, 415)
        """with requests.Session() as sess:
            print("    Starting request")
            resp = sess.send(pre_req)
            print("    Response is: " + resp.status_code)
            self.assertTrue(resp.status_code == 200)"""
