import threading
import os
from selenium import webdriver
from warcat.model import WARC
from bs4 import BeautifulSoup
from app.main import downloader as down

exitFlag = 0
js_path = os.path.abspath(os.path.expanduser("~/") + '/bin/phantomjs/lib/phantom/bin/phantomjs')


class DownloadThread(threading.Thread):
    def __init__(self, thread_id, url, prox):
        threading.Thread.__init__(self)
        self.threadID = thread_id
        self.url = url
        service_args = [
            '--proxy=' + prox,
            '--proxy-type=socks5',
        ]
        self.phantom = webdriver.PhantomJS(js_path, service_args=service_args)
        self.path = down.basePath + "/temporary"
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
        image_files = down.load_images(BeautifulSoup(self.phantom.page_source, "lxml"))
        html = self.phantom.page_source
        return html


