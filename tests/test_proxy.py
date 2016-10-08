import unittest

from freeproxy import from_cyber_syndrome
from freeproxy import from_free_proxy_list
from freeproxy import from_hide_my_ip
from freeproxy import from_xici_daili

from app.main import proxy_util as p
from app import create_app, db
import ipfsApi
import logging
import os

from app.main.proxy_util import ip_lookup_country
from .post_data import proxy_list

fr_proxy = "178.32.153.219:80"
china_proxy = "222.161.3.163:9999"


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

    def tearDown(self):
        db.session.remove()
        # db.drop_all()
        self.app_context.pop()

    def test_ip_location_lookup(self):
        self.assertEqual("FR", p.ip_lookup_country("5.135.176.41"))

    def test_check_proxies(self):
        # TODO !! may take more than 45 minutes !!
        print("\nTesting and updating the proxy list - This will take over half an hour!! :")
        #try:
        prox_list = p.update_proxies()

        print(str(prox_list))
        self.assertGreater(len(prox_list), 30, "Gathered no more than 10 proxies")
        tested_proxies = p.test_proxies(prox_list)
        print("{} tested proxies compared to {} retrieved prxies".format(len(prox_list), len(tested_proxies)))
        print(tested_proxies)
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
        print(p_list)
        self.assertGreater(len(p_list), 10, "Did not gather more than 10 proxies. Proxy list generation failed!")

    def test_proxy_check(self):
        self.assertTrue(p.is_proxy_alive(fr_proxy))

    def test_gather_proxies_alternative(self):
        self.assertGreaterEqual(len(p.gather_proxies_alternative()), 2)

    def test_test(self):

        proxies = list(set(from_xici_daili() + from_cyber_syndrome() + from_hide_my_ip() + from_free_proxy_list()))
        print(str(len(proxies)))
        proxies = p.t_prox(proxies, timeout=5, single_url="http://baidu.com")
        self.assertGreaterEqual(len(proxies), 10)
        print("{} working proxies gathered".format(str(len(proxies))))

        proxies_list = list()
        countries = set()
        for proxy in proxies:
            split_proxy = proxy.split(":")
            country = ip_lookup_country(split_proxy[0])
            countries.add(country)
            proxies_list.append([country, "{}:{}".format(split_proxy[0], split_proxy[1])])
        print(str(len(countries)))
        print(countries)

    def test_get_rand_proxy(self):
        self.assertIsNotNone(p.get_rand_proxy())

if __name__ == '__main__':
    unittest.main()
