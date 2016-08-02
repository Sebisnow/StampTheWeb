import threading
import os
import re
import requests
from selenium import webdriver
from warcat.model import WARC
from bs4 import BeautifulSoup

exitFlag = 0
urlPattern = re.compile('^(https?|ftp)://[^\s/$.?#].[^\s]*$')
js_path = os.path.abspath(os.path.expanduser("~/") + '/bin/phantomjs/lib/phantom/bin/phantomjs')


class DownloadThread(threading.Thread):
    def __init__(self, thread_id, url, prox, base_path='app/pdf/'):
        threading.Thread.__init__(self)
        self.threadID = thread_id
        self.url = url
        service_args = [
            '--proxy=' + prox,
            '--proxy-type=socks5',
        ]
        self.phantom = webdriver.PhantomJS(js_path, service_args=service_args)
        self.path = base_path + "/temporary"
        if not os.path.exists(self.path):
            os.mkdir(self.path)
        self.path = self.path + "/" + str(thread_id)
        os.mkdir(self.path)

    def run(self):

        return self.download()
        # TODO download html and images include in warc

    def download(self):

        self.phantom.set_window_size(1366, 768)
        self.phantom.get(self.url)
        with open(self.path + "/page_source.html", "w") as file:
            file.write(self.phantom.page_source)
        image_files = self.load_images(BeautifulSoup(self.phantom.page_source, "lxml"))
        html = self.phantom.page_source
        return html

    def load_images(self, soup):
        files = list()
        img_ctr = 0
        current_directory = os.getcwd()
        os.chdir(self.path)
        for img in soup.find_all(['amp-img', 'img']):
            if urlPattern.match(img['src']):
                filename = 'img' + str(img_ctr)
                img_ctr += 1
                r = requests.get(img['src'], stream=True)
                if r.status_code == 200:
                    with open(filename, 'wb') as f:
                        for chunk in r.iter_content(1024):
                            f.write(chunk)
                    img['src'] = filename
                    files.append(filename)
        os.chdir(current_directory)
        return files

