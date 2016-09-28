import os
import unittest
from app.main import downloader as down
from app import create_app, db
import ipfsApi as ipfs
import logging
import json
from flask import request
from .post_data import post_data_json
import app.main.proxy_util as proxy

proxy.proxy_path = os.path.abspath(os.path.expanduser("~/") + "PycharmProjects/STW/static/")


class BasicsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        if os.path.exists('/home/sebastian/testing-stw/stw.log'):
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
        # db.drop_all()
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

    def test_extension_api_basic(self):
        with self.app.test_request_context('/timestamp', method='POST', content_type='application/json',
                                           data=post_data_json):
            # now you can do something with the request until the
            # end of the with block, such as basic assertions:
            print(request.headers["content-type"])
            print(request.get_json())
            self.assertEqual(request.path, '/timestamp')
            self.assertEqual(request.method, 'POST')

    def test_extension_api_duplicate_submission(self):
        """
        Simulate the behaviour of the Timestamp extension that sends a POST request.
        """

        self.app.logger.info("Testing the web interface for the Timestamp Extension:")
        print("Testing the web interface for the Timestamp Extension:")
        resp = self.client.post('/timestamp', data=post_data_json, content_length=len(post_data_json),
                                content_type="application/json", follow_redirects=True)
        self.app.logger.info("    Response is: " + str(resp))
        print("    Response is: " + str(resp))
        print("    Header: " + str(resp.headers))
        self.assertEqual(resp.status_code, 200)

        """with requests.Session() as sess:
            print("    Starting request")
            resp = sess.send(pre_req)
            print("    Response is: " + resp.status_code)
            self.assertTrue(resp.status_code == 200)"""

    def test_extension_api_post_data(self):
        with self.app.test_request_context('/timestamp', method='POST', content_type='application/json',
                                           data=post_data_json):
            # now you can do something with the request until the
            # end of the with block, such as basic assertions:
            print(request.headers["content-type"])
            posted_data = request.get_json()
            print(type(posted_data))
            json_of_data = json.loads(post_data_json)
            print(type(json_of_data))
            print(json_of_data["body"])
            self.assertEqual(posted_data['body'], json_of_data['body'])
