import unittest
from app.main import proxy_util as p
from app import create_app, db
import ipfsApi
import logging
import os


class MyTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = ipfsApi.Client()
        db.create_all()
        p.proxy_path = os.path.abspath(os.path.expanduser("~/") + "PycharmProjects/STW/static/")
        log_handler = logging.FileHandler('/home/sebastian/testing-stw/STW.log')
        log_handler.setLevel(logging.INFO)
        self.app.logger.setLevel(logging.INFO)

    def test_ip_location_lookup(self):
        self.assertEqual("FR", p.get_proxy_location("5.135.176.41"))

    def test_check_proxies(self):
        # TODO !! may take more than 45 minutes !!
        print("\nTesting and updating the proxy list - This will take over half an hour!! :")
        #try:
        prox_list = p.update_proxies()

        print(str(prox_list))
        self.assertGreater(len(prox_list), 10, "Gathered more than 10 proxies")
        """except UnicodeDecodeError as e:
            print("Encountered UnicodeDecodeError, nothing to be done but to try later as it is internal error of "
                  "proxybroker.")
            print(str(e.object))
            print((e.__str__()))
            pass"""

    def test_get_one_proxy(self):
        print("\nTesting the retrieval of one proxy:")
        prox = p.get_one_proxy("AT")
        self.assertIsNotNone(prox, "Retrieval of one proxy failed.")
        print(prox)

    def test_get_proxy_list(self):
        print("\nTesting the loading of the proxy list:")
        p_list = p.get_proxy_list()
        self.assertGreater(len(p_list), 10, "Did not gather more than 10 proxies. Proxy list generation failed!")


if __name__ == '__main__':
    unittest.main()
