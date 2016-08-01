import threading
import time

exitFlag = 0


class DownloadThread(threading.Thread):
    def __init__(self, thread_id, name, url):
        threading.Thread.__init__(self)
        self.threadID = thread_id
        self.name = name
        self.url = url

    def run(self):
        #TODO download html and images


def print_time(thread_name, delay, counter):
    while counter:
        if exitFlag:
            thread_name.exit()
        time.sleep(delay)
        print("%s: %s" % (thread_name, time.ctime(time.time())))
        counter -= 1
