import csv
import json
import os
import re
from datetime import datetime
import requests
import traceback
from subprocess import check_output, DEVNULL
import pdfkit
import queue
import threading
from random import randrange
from flask import flash
from flask import current_app as app
from urllib.parse import urlparse

from selenium.common.exceptions import WebDriverException, TimeoutException

from app.main.download_thread import DownloadThread
from app.main import proxy_util
from app.models import Country, Post, User
from app.main import download_thread as d_thread
from .. import db
# nullDevice = open(os.devnull, 'w')
errorCaught = ""

blockSize = 65536
options = {'quiet': ''}


class ReturnResults(object):
    """
    :author:Sebastian
    Helper class to return the results from downloader to the views. Therefore this class is equivalent to an API.
    """

    def __init__(self, originstamp_result, hash_value, web_title, errors=None, user_input=None, original=None):
        self.originStampResult = originstamp_result
        self.hashValue = hash_value
        self.webTitle = web_title
        self.errors = errors
        self.user_input = user_input
        self.original = original


def get_all_domain_names(post):
    domain_list = []
    domain_name = []
    # Getting Domains visited by all the users
    for domains in post.query.filter(post.urlSite is not None):
        if domains.urlSite is not None:
            url_parse = urlparse(domains.urlSite)
            if url_parse.netloc and url_parse.scheme:
                domain_list.append(domains.urlSite)
                if url_parse.netloc.startswith('www.'):
                    domain_name.append(url_parse.netloc[4:])
                else:
                    domain_name.append(url_parse.netloc)
    return domain_name


def remove_unwanted_data_regular():
    base_path = 'app/pdf/temp-world.geo.json'
    with open(base_path) as data_file:
        data = json.load(data_file)
    a = 0
    while a < 211:
        data["features"][a]["properties"]["Location"] = ""
        data["features"][a]["properties"]["Location_no"] = 0
        del data["features"][a]["properties"]["ISO_3_CODE"]
        del data["features"][a]["properties"]["NAME_1"]
        del data["features"][a]["properties"]["NAME"]
        del data["features"][a]["properties"]["GMI_CNTRY"]
        del data["features"][a]["properties"]["NAME_12"]
        del data["features"][a]["properties"]["AREA"]
        del data["features"][a]["properties"]["Percentage"]
        del data["features"][a]["properties"]["URLS"]
        a += 1

    return data


def remove_unwanted_data():
    base_path = 'app/pdf/temp-world.geo.json'
    with open(base_path) as data_file:
        data = json.load(data_file)
    a = 0
    while a < 211:
        data["features"][a]["properties"]["Percentage"] = 0
        del data["features"][a]["properties"]["ISO_3_CODE"]
        del data["features"][a]["properties"]["NAME_1"]
        del data["features"][a]["properties"]["GMI_CNTRY"]
        del data["features"][a]["properties"]["NAME_12"]
        del data["features"][a]["properties"]["AREA"]
        a += 1

    return data


def remove_unwanted_data_block_country():
    base_path = 'app/pdf/temp-world.geo.json'
    with open(base_path) as data_file:
        data = json.load(data_file)
    a = 0
    while a < 211:
        data["features"][a]["properties"]["Block"] = 0
        data["features"][a]["properties"]["Block_Status"] = "Unknown"
        del data["features"][a]["properties"]["ISO_3_CODE"]
        del data["features"][a]["properties"]["NAME_1"]
        del data["features"][a]["properties"]["GMI_CNTRY"]
        del data["features"][a]["properties"]["NAME_12"]
        del data["features"][a]["properties"]["AREA"]
        del data["features"][a]["properties"]["Percentage"]
        del data["features"][a]["properties"]["URLS"]
        a += 1

    return data


def search_for_url(url):
    index = 0
    proxy_list = {}
    with open(proxy_util.base_path + "proxy_list.tsv", "rt", encoding="utf8") as tsv:
        for line in csv.reader(tsv, delimiter="\t"):
            proxy_list[index] = [line[0], line[1], None]
            index += 1

    q = queue.Queue()
    for k in proxy_list:
        p = proxy_list[k][1]
        t = threading.Thread(target=get_url, args=(q, p, url))
        t.daemon = True
        t.start()

    for k in proxy_list:
        proxy_list[k][2] = q.get()
        #print(proxy_list[k][2], proxy_list[k][0])  # TODO for Debugging open this

    return proxy_list


def get_url(q, p, url):
    r = None
    try:
        r = requests.get(url, proxies={"http": p})
    except:
        q.put(r)

    if r is not None:
        q.put(r.status_code)
    else:
        q.put(None)


def get_text_from_other_country(china, usa, uk, russia, url):
    if china is True:
        proxy = app.config['STW_CHINA_PROXY']
        sha256, text = update_and_send(proxy, url)
        return sha256, text

    if usa is True:
        proxy = app.config['STW_USA_PROXY']
        sha256, text = update_and_send(proxy, url)
        return sha256, text
    if uk:
        proxy = app.config['STW_UK_PROXY']
        sha256, text = update_and_send(proxy, url)
        return sha256, text
    if russia:
        proxy = app.config['STW_RUSSIA_PROXY']
        sha256, text = update_and_send(proxy, url)
        return sha256, text


def update_and_send(proxy, url):
    try:
        r = requests.get(url, proxies={"http": proxy})
    except:
        return None, None

    if r:
        return calculate_hash_for_html_block(r.text)


class OriginstampError(Exception):
    """
    Error-Class for problems happening during requesting URL.
    """

    def __init__(self, message, req):
        super(OriginstampError, self).__init__(message)
        self.request = req


def create_png_from_url(url, sha256):
    """
    Create png from URL. Returns path to file.
    This method uses PhantomJS to capture lazily loaded content and takes a picture of the website.

    --# TODO This method loads the website again, which causes quite the time overhead for the redundant network
    comunication, move everything to use the DownloadThread class to only get the webresources once and take advantage
    of running it in a separate thread. #--

    :author: Sebastian
    :param url: url to retrieve
    :param sha256: name of the downloaded png
    :returns: path to the created png or None
    """
    app.logger.info('Creating PNG from URL:' + url)
    path = '{}{}.png'.format(proxy_util.base_path, sha256)
    app.logger.info('PNG Path:' + path)

    phantom = d_thread.DownloadThread.initialize()
    app.logger.info('Initializing done fetching url.')
    phantom.get(url)

    app.logger.info('Downloaded url, start scrolling.')
    try:
        d_thread.DownloadThread.scroll(phantom)
    except WebDriverException as e:
        #print error but continue without scrolling down until alternative is found
        #TODO find alternative to scrolling via javascript eval()
        app.logger.info(e.msg)
    phantom.get_screenshot_as_file(path)

    app.logger.info("PNG created: {}".format(os.path.exists(path)))
    if os.path.isfile(path):
        return path
    if not app.config["TESTING"]:
        flash(u'Could not create PNG from ' + url, 'error')
    app.logger.error('Could not create PNG from the URL : ' + url)
    return None


def create_html_from_url(html_text, ipfs_hash, url):
    path = proxy_util.base_path + ipfs_hash + '.html'
    app.logger.info("Fetching the HTML file from IPFS to save locally.")
    # fetch the to IPFS submitted html text to store on disk
    try:
        cur_dir = os.getcwd()
        os.chdir(proxy_util.base_path)
        d_thread.ipfs_Client.get(ipfs_hash)
        app.logger.info("Trying to fetch the HTML from IPFS")

        app.logger.info("Fetched the html from ipfs: " + str(os.path.exists(ipfs_hash)))
        os.rename(ipfs_hash, ipfs_hash + ".html")
        app.logger.info("Renamed the fetched HTML to have the .html ending")
        app.logger.info("There is a file called " + path + ": " + str(os.path.exists(ipfs_hash + '.html')))
        os.chdir(cur_dir)
    except FileNotFoundError as f:
        app.logger.error("FileNotFoundError while trying to get file through IPFS\n" + f.strerror + "\n" + f.filename +
                         "\n" + str(f))
    except Exception as e:

        app.logger.info('Could not fetch from IPFS, trying again in another way.\n ' + str(e))
        try:
            # TODO the following part can be refactored and almost deleted
            app.logger.info("Writing text to file " + path)
            with open(path, 'w') as file:
                file.write(html_text)
            if os.path.isfile(path):
                ip = d_thread.ipfs_Client.add(path)
                ipfs_hash = ip[0]["Hash"]
                app.logger.info("Added following file to IPFS: " + path)
                app.logger.info('With Hash:' + ipfs_hash)
                return ipfs_hash
        except FileNotFoundError as e:

            if not app.config["TESTING"]:
                flash(u'Could not create HTML from ' + url, 'error')
            app.logger.error('Could not create HTML from the: ' + url + '\n' + e.strerror + "\n" +
                             e.filename + "\n" + str(e))
            app.logger.error(e.args)
            return None
        except AttributeError as att:
            if not app.config["TESTING"]:
                flash(u'Due to attribute error I could not create HTML from ' + url, 'error')
            app.logger.error('Due to attribute error I could not create HTML from the: ' + url + '\n' + att.args)
            return None
        return None


def create_pdf_from_url(url, sha256):
    """
    Generates a pdf from the given url and stores it under the name of the given hash value.

    :author Sebastian
    :param url: url to retrieve
    :param sha256: the hash of the url which is important for the filename
    method to write pdf file
    """
    app.logger.info('Creating PDF from URL:' + url)
    path = proxy_util.base_path + sha256 + '.pdf'
    app.logger.info('PDF Path:' + path)
    try:
        # TODO throws error
        pdfkit.from_url(url, path)
    except OSError as e:

        app.logger.error('Could not create PDF from the URL: ' + url)
        app.logger.error(e)
        if os.path.isfile(path):
            app.logger.error('But local PDF exists at: ' + path)
            return
        if not app.config["TESTING"]:
            flash(u'Could not create PDF from ' + url, 'error')
    return


def calculate_hash_for_html_doc(html_text):
    """
    Calculate hash for given html document.

    :author Sebastian
    :param html_text: html doc to hash as text
    :returns: calculated hash for given URL and the document used to create the hash
    """
    app.logger.info('Creating HTML and Hash')
    text, title = d_thread.preprocess_doc(html_text)
    sha256 = save_file_ipfs(text)

    app.logger.info('Hash:' + sha256)
    # app.logger.info('HTML:' + text)
    return sha256, text, title


def calculate_hash_for_html_block(html_text):
    """
    Calculate hash for given html document.

    :author: Sebastian and Waqar
    :param html_text: html doc to hash as text
    :returns: calculated hash for given URL and the document used to create the hash
    """
    app.logger.info('Creating HTML and Hash')
    text, title = d_thread.preprocess_doc(html_text)
    sha256 = save_file_ipfs(text)

    app.logger.info('Hash:' + sha256)
    # app.logger.info('HTML:' + text)
    return sha256, text


def submit(sha256, title=None):
    """
    Submits the given hash to the originstamp API and returns the request object.

    :author Sebastian
    :param sha256: hash to submit
    :param title: title of the hashed document
    :returns: resulting request object
    """
    headers = {'Content-Type': 'application/json', 'Authorization': 'Token token={}'.format(d_thread.api_key)}
    data = {'hash_sha256': sha256, 'title': title}
    return requests.post(d_thread.api_post_url, json=data, headers=headers)


def submit_add_to_db(url, sha256, title):
    """
    submit hash to originStamp and store in DB.
    # TODO store in WARC file that is described by the URL and append changed hashes of a URL to the same WARC.

    :author Sebastian
    :param url: URL downloaded
    :param title: Title of the document behind the URL
    :param sha256: Hash to name file after
    """
    originstamp_result = submit(sha256, title)
    app.logger.info(originstamp_result.text)
    app.logger.info('Origin Stamp Response:' + originstamp_result.text)
    # TODO should yield different result if the response was different or handling can be left for calling function.
    if originstamp_result.status_code >= 400:
        if not app.config["TESTING"]:
            flash(u'Could not submit hash to originstamp. Error Code: ' + originstamp_result.status_code +
                  '\n ErrorMessage: ' + originstamp_result.text, 'error')
        app.logger.error('Could not submit hash to originstamp. Error Code: ' + originstamp_result.status_code +
                         '\n ErrorMessage: ' + originstamp_result.text)
        return originstamp_result
        # raise OriginstampError('Could not submit hash to Originstamp', r)
    elif originstamp_result.status_code >= 300:
        if not app.config["TESTING"]:
            flash(u'Internal System Error. Error Code: ' + originstamp_result.status_code +
                  '\n ErrorMessage: ' + originstamp_result.text, 'error')
        app.logger.error('300 Internal System Error. Could not submit hash to originstamp')
        return originstamp_result
    elif originstamp_result.status_code == 200:
        # if not app.config["TESTING"]: flash(u'URL already submitted to OriginStamp'+ url + ' Hash '+sha256)
        # app.logger.error('URL already submitted to OriginStamp')
        return originstamp_result
    elif "errors" in originstamp_result.json():
        if not app.config["TESTING"]:
            flash(u'Internal System Error. Error Code: ' + originstamp_result.status_code +
                  '\n ErrorMessage: ' + originstamp_result.text, 'error')
        app.logger.error('An Error occurred. Error Code: ' + originstamp_result.status_code +
                         '\n ErrorMessage: ' + originstamp_result.text)
        return originstamp_result

    return originstamp_result


def load_images(soup):
    files = list()
    img_ctr = 0
    for img in soup.find_all(['amp-img', 'img']):
        if proxy_util.url_specification.match(img['src']):
            filename = 'img' + str(img_ctr)
            img_ctr += 1
            r = requests.get(img['src'], stream=True)
            if r.status_code == 200:
                with open(filename, 'wb') as f:
                    for chunk in r.iter_content(1024):
                        f.write(chunk)
                img['src'] = filename
                files.append(filename)
    return files


def submitHash(sha256):
    """
    Meta method that initiates the submission to Originstamp and handles response messages and errors.

    :author: Waqar and Sebastian
    :param sha256: The hash of the file(s) to timestamp.
    :return: Returns a ReturnResults Object with the result of the submission.
    """
    originstamp_result = submit(sha256, "")
    app.logger.info(originstamp_result.text)
    app.logger.info('Origin Stamp Response:' + originstamp_result.text)
    if originstamp_result.status_code >= 300:
        if not app.config["TESTING"]:
            flash(u'300 Internal System Error. Could not submit sha256 to originstamp.', 'error')
        app.logger.error('300 Internal System Error. Could not submit sha256 to originstamp')
        return ReturnResults(None, sha256, "None")
    elif originstamp_result.status_code == 200:
        if "errors" in originstamp_result.json():
            # hash already submitted
            history = d_thread.get_originstamp_history(sha256)
            if not app.config["TESTING"]:
                flash(u'Submitted hash to Originstamp successfully but hash already taken: '
                      u'{}'.format(history.json()["created_at"]))
            app.logger.error('Submitted hash to Originstamp successfully but hash already taken: '
                             '{}'.format(history.json()["created_at"]))
            return ReturnResults(history, sha256, "None", originstamp_result.text)
        else:
            if not app.config["TESTING"]:
                flash(u'Hash was submitted to OriginStamp successfully' + ' Hash ' + sha256)
            app.logger.info('Hash was submitted to OriginStamp successfully')
            return ReturnResults(originstamp_result, sha256, "")
        # raise OriginstampError('Could not submit sha256 to Originstamp', r)
    else:
        return ReturnResults(originstamp_result, sha256, "", "submission failed")


def getHashOfFile(fname):
    """
    This method submits a file to IPFS and returns the resulting hash that describes the address of the file on IPFS.

    :author: Sebastian
    :param fname: The path to the File to get the hash for.
    :return: Returns the Hash of the file.
    """
    res = d_thread.ipfs_Client.add(fname)
    """
    # deprecated legacy function without IPFS
    hash_sha265 = hashlib.sha256()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha265.update(chunk)
    return hash_sha265.hexdigest()
    """
    return res['Hash']


def get_text_timestamp(text):
    """
    Generate a timestamp for a text and submit that text to ipfs.
    Method is tested in terms of IPFS Hash and in terms of submission to Originstamp.

    :author: Waqar and Sebastian
    :param text: The text to be timestamped
    :return: ReturnResults object
    """
    results = submitHash(save_file_ipfs(text))
    return results


def save_file_ipfs(text):
    """
    Saves the file on IPFS and thus creates the hash to be submitted to Originstamp.

    :author: Sebastian
    :param text: The text to be timestamped.
    :return: Returns the hash of the stored file, which equals the address on IPFS.
    """
    path = proxy_util.base_path + "temp.html"
    app.logger.info("Working Directory: " + os.getcwd() + "trying to create temporary file:" + path)
    try:
        app.logger.info(path + " File exists before modification " + str(os.path.exists(path)))
        with open(path, "w") as f:
            f.write(text)
    except FileNotFoundError as e:
        app.logger.error("Due to FileNotFoundError could not create tempfile to save text in " + path +
                         "\n Current working directory is: " + os.getcwd())
        app.logger.error(e.characters_written)
        app.logger.error(e.strerror)
    except AttributeError as e:
        app.logger.error("Due to AttributeError could not create tempfile to save text in " + path)
        app.logger.error(e.args)
    except Exception as e:
        app.logger.error("could not create tempfile to save text in " + path)
        app.logger.error(e)
        app.logger.error(traceback.print_exc())

    app.logger.info("    There is a file called " + path + ": " + str(os.path.exists(path)))
    ipfs_hash = d_thread.ipfs_Client.add(path)
    print(ipfs_hash[0]['Hash'])
    return ipfs_hash[0]['Hash']


def get_hash_history(sha256):
    """
    :author Waqar
    :parm sha256: the sha256 which needs to verify from OriginStamps
    """
    results = submitHash(sha256)
    return results


def ipfs_get(timestamp):
    """
    Get data from IPFS. The data on IPFS is identified by the hash (timestamp variable).
    We collect the data by making a system call. IPFS has to be installed for this functionality to work.
    Can be replaced by ipfs python api once that is fully implemented.

    :author: Sebastian
    :param timestamp: The hash describing the data on IPFS.
    :return: Returns the path to the locally stored data collected from IPFS.
    """

    path = proxy_util.base_path + timestamp
    cur_dir = os.getcwd()
    os.chdir(proxy_util.base_path)
    app.logger.info("Trying to fetch the HTML from IPFS")
    try:
        check_output(['ipfs', 'get', timestamp], stderr=DEVNULL)
        app.logger.info("ipfs command completed. Fetched File present: " +
                        str(os.path.exists(proxy_util.base_path + timestamp)))
    except FileNotFoundError as e:
        app.logger.info(e.strerror + " ipfs command not found trying another way." + str(type(timestamp)))
        check_output(['/home/ubuntu/bin/ipfs', 'get', timestamp], stderr=DEVNULL)

        app.logger.info("There is a file called " + path + timestamp + ": " +
                        str(os.path.exists(proxy_util.base_path + timestamp)))
        app.logger.info("There is a file called " + path + ": " + str(os.path.exists(path)))

    except Exception as e:

        app.logger.error("Error while trying to fetch from IPFS or renaming" + str(e) + "\n" +
                         "Could be a Permission problem on the Server")
        check_output(['/home/ubuntu/bin/ipfs', 'get', timestamp], stderr=DEVNULL)
        app.logger.info("There is a file called " + path + ": " + str(os.path.exists(proxy_util.base_path +
                                                                                     timestamp)))
    os.chdir(cur_dir)
    return path


def get_url_hist(url, user=None, robot_check=False, location=None):
    """
    Alternative to get_url_history that uses the DownloadThread class for timestamping.

    :author: Sebastian
    :param url: The URL of the website to timestamp.
    :param user: The username of the user that started the distributed timestamp. If the call came from the extension
     and no user was sent the user will be set to Bot.
    :param robot_check: Boolean value that indicates whether the downloader should honour the robots.txt of
    the given website or not.
    :param location: Defaults to None. Specifies the location the html comes from or should come from.

    :return:
    """
    thread = _run_thread(url, randrange(20, 40), robot_check=robot_check, location=location)
    thread.join()
    error = _submit_threads_to_db([thread], user)
    if len(error) != 0:
        app.logger.error('An error was returned trying to retrieve {}:\n {}'.format(url, str(error[0].error)))
        return ReturnResults(None, None, None, error[0].error)

    return ReturnResults(thread.originstamp_result, thread.ipfs_hash, thread.title)


def get_url_history(url):
    """
    Entry point for the downloader

    :author: Sebastian
    :param url: the URL to get the history for
    :return: a ReturnResults Object with the originStampResult, hashValue and webTitle and optionally an error message
    """
    # validate URL
    sha256 = None
    if not re.match(proxy_util.url_specification, url):
        if not app.config["TESTING"]:
            flash('100' + 'Bad URL' + 'URL needs to be valid to create timestamp for it:' + url, 'error')
        app.logger.error('100' + 'Bad URL.' + 'URL needs to be valid to create timestamp for it:\n' + url)
        return ReturnResults(None, None, None)

    res = requests.get(url)

    if res.status_code >= 300:
        if not app.config["TESTING"]:
            flash('100 Bad URL Could not retrieve URL to create timestamp for it.' + url, 'error')
        app.logger.error('100 Bad URL Could not retrieve URL to create timestamp for it:' + url)
        return ReturnResults(None, None, None)
    # soup = BeautifulSoup(res.text.encode(res.encoding), 'html.parser')
    title = None
    # encoding = chardet.detect(res.text.encode()).get('encoding')
    try:
        sha256, html_text, title = calculate_hash_for_html_doc(res.text)
        # if check_database_for_hash(sha256) < 1:
        originstamp_result = save_render_zip_submit(html_text, sha256, url, title)

    except Exception as e:

        # should only occur if data was submitted successfully but png or pdf creation failed
        if not app.config["TESTING"]:
            flash(u'Internal System Error: ' + str(e.args), 'error')
        app.logger.error('Internal System Error: ' + str(e) + str(e.args))
        traceback.print_exc()
        return ReturnResults(None, sha256, title)

    # return json.dumps(check_database_for_url(url), default=date_handler)
    return ReturnResults(originstamp_result, sha256, title)


'''
# Deprecated Method of old STW
def load_zip_submit(url, soup, enc):
    old_path = os.getcwd()
    tmp_dir = proxy_util.base_path + str(uuid.uuid4())
    os.mkdir(tmp_dir)
    os.chdir(tmp_dir)
    file_list = load_images(soup)
    js_list = load_amp_js(soup)
    with open('site.html', 'w') as file:
        file.write(str(soup.encode(enc)))
    file_list.append('site.html')
    sha256 = compress_files(file_list, js_list)
    if check_database_for_hash(sha256) < 1:
        submit_add_to_db(url, sha256, soup.title.string)
        os.rename(sha256 + '.zip', '../' + sha256 + '.zip')
    os.chdir(old_path)
    shutil.rmtree(tmp_dir)
'''


def save_render_zip_submit(html_text, sha256, url, title):
    """
    After IPFS has done it's magic this is the main handler for everything after the hash creation.
    save_render_zip_submit creates(fetches from IPFS) the HTML file. Submits the sha256 hash to originstamp and creates
    pdf and png of the website behind the URL.

    :author: Sebastian
    :param html_text: The HTML text as string.
    :param sha256: The hash value associated with the HTML.
    :param url: The URL that is being Timestamped.
    :param title: The Title the user chose for this Timestamp.
    :returns OriginStampResult object: Returns an OriginstampResult object containing the results.
    """
    try:
        create_html_from_url(html_text, sha256, url)
    except FileNotFoundError as fileError:
        # can only occur if data was submitted successfully but png or pdf creation failed
        if not app.config["TESTING"]:
            flash(u'Internal System Error while creating the HTML: ' + fileError.strerror, 'error')
        app.logger.error('Internal System Error while creating HTML,: ' +
                         fileError.strerror + "\n Maybe check the path, current base path is: " + proxy_util.base_path)
    # archive = zipfile.ZipFile(proxy_util.base_path + sha256 + '.zip', "w", zipfile.ZIP_DEFLATED)
    # archive.write(proxy_util.base_path + sha256 + '.html')
    # os.remove(proxy_util.base_path + sha256 + '.html')
    # archive.write(proxy_util.base_path + sha256 + '.png')
    # os.remove(proxy_util.base_path + sha256 + '.png')
    originstamp_result = submit_add_to_db(url, sha256, title)

    # moved image creation behind Timestamping so images are only created for new Stamps if no error occurred
    if originstamp_result.status_code == 200:
        try:
            create_pdf_from_url(url, sha256)
            create_png_from_url(url, sha256)
        except FileNotFoundError as fileError:
            # can only occur if data was submitted successfully but png or pdf creation failed
            if not app.config["TESTING"]:
                flash(u'FileNotFoundError while creating image and pdf: ' + fileError.strerror +
                      '\n Originstamp Result was: ' + str(originstamp_result.status_code), 'error')
            app.logger.error('FileNotFoundError while creating image and pdf: ' +
                             fileError.strerror + '\n Originstamp Result was: ' + str(originstamp_result.status_code))
            originstamp_result.error = fileError
            return originstamp_result
        except Exception as e:
            # can only occur if data was submitted successfully but png or pdf creation failed
            if not app.config["TESTING"]:
                flash(u'Internal System Error while creating image and pdf: ' + e.args +
                      '\n Originstamp Result was: ' + str(originstamp_result.status_code), 'error')
            app.logger.error('Internal System Error while creating image and pdf: ' +
                             e.args + '\n Originstamp Result was: ' + str(originstamp_result.status_code))
            originstamp_result.error = e
            return originstamp_result
    return originstamp_result


def get_links_for_threads(joined_threads, proxy_list, num_threads, robot_check, user):
    """
    Use this method to scrape the links of the downloaded website and for each start a new download thread.
    This helper method starts num_threads new DownloadThreads for every link contained in all unique
    DownloadThreads handed to it(joined_threads variable). It joins the threads and submits them to return a dictionary
    (identified by the ipfs_hash) of dictionaries. The outer dictionary consists of one key for each unique download.
    The inner dictionaries have their link as key and a list of threads as value:

    -- thread_dict -- :
    {
    "ipfs_hash1":   {   "http.example.com" : [Thread-1, Thread-2, ...],
                        "http.example.com/foobar": [Thread-1, Thread-2, ...],
                        ...
                    },
    "ipfs_hash2":   {   "http.examples.com" : [Thread-1, Thread-2, ...],
                        "http.examples.com/foobars": [Thread-1, Thread-2, ...],
                        ...
                    },
    ...
    "error_threads": [Thread-1, Thread-2, ...]
    }

    :author: Sebastian
    :param joined_threads: The threads to download and timestamp the links from as a list.
    :param proxy_list: A list of proxies to use first for the DownloadThreads.
    :param num_threads: The Number of threads to start for each timestamp request.
    :param robot_check: Whether or not to adhere to robots.txt.
    :param user: The user that triggered the timestamp.
    :return: Returns the thread_dict that contains all joined and submitted links as well as all error_threads.
    """
    cnt = 1
    thread_dict = dict()
    for thread in joined_threads:
        if thread.error is not None:
            continue

        # New DownloadThreads only for different results(e.g. hash is a new one).
        if thread.ipfs_hash not in thread_dict:
            thread_dict[thread.ipfs_hash] = dict()

            # for every link do a country independent timestamp
            links = thread.get_links()
            for link in links:
                print("All links of thread-{}:\n{}".format(thread.threadID, links))
                link_threads = list()
                cnt *= 10
                # Get a proxy from the location of the URL and start thread manually
                orig_proxy, original_country = proxy_util.get_proxy_from_url(link, proxy_list)
                original = _run_thread(link, cnt, proxy_list=[[original_country, orig_proxy]],
                                       robot_check=robot_check, location=original_country)
                link_threads.append(original)

                cnt += 1
                # Start all other threads and add to list for link
                started_threads = start_threads(None, link_threads, link, cnt, num_threads, robot_check,
                                                proxy_list)
                print("Started Threads: {}".format(started_threads))

                # For every link create an entry in the thread_dict containing a list of started threads
                thread_dict[thread.ipfs_hash][link] = link_threads + started_threads
                #TODO List gets too deep
                print("Added {} to thread dict for link {}".format(link_threads, link))
                cnt += 1

    # Join all threads and submit results to db
    thread_dict["error_threads"] = list()
    for hash_value, link_dict in thread_dict.items():
        if hash_value != "error_threads":
            for link, thread_list in link_dict.items():
                print("Going for the join of threads from {}: {}".format(link, thread_list))
                joined_threads, votes = _join_threads(thread_list)
                if len(joined_threads) > 0:
                    # submit threads and add error threads returned to error part of dict.
                    thread_dict["error_threads"].append(
                        _submit_threads_to_db(joined_threads, user, original_hash=joined_threads[0].ipfs_hash))

                """for url in link_dict:
                    print("Going for the join of threads: {}".format(url))
                    joined_threads, votes = _join_threads(link_dict[url])
                    if len(joined_threads) > 0:
                        # submit threads and add error threads returned to error part of dict.
                        thread_dict["error_threads"].append(
                            _submit_threads_to_db(joined_threads, user, original_hash=joined_threads[0].ipfs_hash))
    """
    return thread_dict


def location_independent_timestamp(url, proxies=None, robot_check=False, num_threads=5, user="Bot", links=False):
    """
    This way of timestamping starts several threads(usually 5). The first thread downloads what will be considered the
    original content as it uses a proxy from the country of origin of the url. Thus this method retrieves a baseline
    for result comparisons together with four (per default) other random locations if none are specified in the list
    'proxies'. The Method returns all DownloadThread objects as a list. The first is the benchmark (original content)
    to compare the rest with.
    The results of the download are stored in the db, on IPFS and as WARC automatically.


    :author: Sebastian
    :param url: he URL of the website to timestamp.
    :param proxies: A list of two-itemed lists of max 5 Proxies that should be taken into account for the timestamp.
    Defaults to None. Each list item should consist of a list of length two with the country code at index 0
    and the proxy in '<host>:<port>' notation as string.
    :param robot_check: Boolean value that indicates whether the downloader should honour the robots.txt of
    the given website or not -- if the users view is needed do not use False.
    :param num_threads: Number of threads to be used for the timestamp. Defaults to 5.
    :param user: The username of the user that initiated the timestamp. As default the Bot user will be used.
    :param links: States whether or not to timestamp all linked pages as well. Defaults to False.
    :return:
    If link is False:
        Triple:
        -A list of DownloadThread objects where the first (at index 0).is the result of the timestamp from
        the country of origin of the website. Only threads without error.
        -The DownloadThread of the original (Same object present in list).
        -The list of DownloadThreads that caused an error.

    If link is set to True:
        Tuple:
        -The DownloadThread objects of the specified URL
        -Dict containing the links of each of the downloads if the downloads produced an individual hash:
                -- thread_dict -- :
            {
            "ipfs_hash1":   {   "http.example.com" : [Thread-1, Thread-2, ...],
                                "http.example.com/foobar": [Thread-1, Thread-2, ...],
                                ...
                            },
            "ipfs_hash2":   {   "http.examples.com" : [Thread-1, Thread-2, ...],
                                "http.examples.com/foobars": [Thread-1, Thread-2, ...],
                                ...
                            },
            ...
            "error_threads": [Thread-1, Thread-2, ...]
            }
    """

    proxy_list = proxy_util.get_proxy_list()
    threads = list()

    # Get a proxy from the location of the URL
    orig_proxy, original_country = proxy_util.get_proxy_from_url(url, proxy_list)
    original = _run_thread(url, 0, proxy_list=[[original_country, orig_proxy]], robot_check=robot_check,
                           location=original_country)
    threads.append(original)
    # Start all other threads
    threads = start_threads(proxies, threads, url, 1, num_threads, robot_check, proxy_list)

    # join all threads and return them, votes wi
    joined_threads, votes = _join_threads(threads)
    if links:
        app.logger.info("Finished LIT going for the links.")
        submitted_thread_dict = get_links_for_threads(joined_threads, proxy_list, num_threads, robot_check, user)
        return joined_threads, submitted_thread_dict
    error_threads = _submit_threads_to_db(joined_threads, user, original_hash=original.ipfs_hash)
    app.logger.info("LIT finished: Correct {}, Error {}".format(len(joined_threads), len(error_threads)))
    return joined_threads, original, error_threads


def distributed_timestamp(url, html=None, proxies=None, user="Bot", robot_check=False, num_threads=5, location=None):
    """
    Perform a distributed timestamp where not only one file is taken into account, but several HTMLs retrieved by
    proxies from different locations. 5 pseudo random locations from the proxy list are used. Optionally default
    proxies to use can be set via the proxies attribute. A maximum of 5 proxies will be taken into account.
    After fetching all 5 htmls they are added to ipfs and their hashes are compared.
    If more than one of the htmls are the same, the one with the most
    votes (EQUAL HASHVALUES) is used as the correct html for the timestamp.
    Otherwise the distributed timestamp is started again in order for one html to become more than one vote.
    Store the different html hashes in db or WARC as well, as censored versions.

    :author: Sebastian
    :param url: The URL of the website to timestamp.
    :param html: The body of the site to timestamp.
    :param proxies: A list of two-itemed lists of max 5 Proxies that should be taken into account for the distributed
    timestamp. Defaults to None. Each list item should consist of a list of length two with the country code at index 0
    and the proxy in '<host>:<port>' notation as string.
    :param user: The username of the user that started the distributed timestamp. If the call came from the extension
     and no user was sent the user will be set to Bot.
    :param robot_check: Boolean value that indicates whether the downloader should honour the robots.txt of
    the given website or not.
    :param num_threads: Number of threads to be used for distributed timestamp. Defaults to 5.
    :param location: Defaults to None. Specifies the location the html comes from or should come from.
    :return: If extension triggered: Returns the result of the distributed Timestamp as a ReturnResults Object,
    including the originStampResult, hashValue, webTitle and errors(defaults to None) together with the original if the
    user_input is not the same as the original. Otherwise of the two only the user_input is returned.

    If not extension triggered this method returns a list of DownloadThread objects and the votes list.
    Votes has an integer stored for each thread, the highest is taken as the original.
    """
    print("Distributed timestamping")
    extension_triggered = False
    if not re.match(proxy_util.url_specification, url):
        return ReturnResults(None, None, None, OriginstampError("The entered URL does not correspond "
                                                                "to URL specifications", 501))
    proxy_list = proxy_util.get_proxy_list()
    threads = []

    cnt = 0
    if html:
        # if an html is given the distributed timestamp was triggered by a user(extension)
        print("Triggered by extension!")
        extension_triggered = True
        threads.append(_run_thread(url, cnt, html=html, robot_check=robot_check, location=location))
        cnt += 1

    threads = start_threads(proxies, threads, url, cnt, num_threads, robot_check, proxy_list)

    # join all threads and return the DownloadThread with the most votes
    joined_threads, votes = _join_threads(threads)

    _submit_threads_to_db(joined_threads, user)

    max_index = votes.index(max(votes))
    print("Distributed timestamp done, return results.")
    if extension_triggered:
        if max(votes) == votes[0]:
            # The input of the user is the same result as the one with the highest votes.
            return ReturnResults(originstamp_result=joined_threads[max_index].originstamp_result,
                                 hash_value=joined_threads[max_index].ipfs_hash,
                                 web_title=joined_threads[max_index].html.title, user_input=joined_threads[0])

        return ReturnResults(originstamp_result=joined_threads[max_index].originstamp_result,
                             hash_value=joined_threads[max_index].ipfs_hash,
                             web_title=joined_threads[max_index].html.title,
                             user_input=joined_threads[0],
                             original=joined_threads[max_index])
    else:
        return joined_threads, votes


def start_threads(proxies, threads, url, cnt, num_threads, robot_check, proxy_list):
    num_threads += cnt
    print("Proxies: " + str(proxies))
    if proxies is not None:
        for proxy in proxies:
            if cnt >= 5:
                break
            app.logger.info("--- Start Thread-{} with proxy: {}".format(cnt, [proxy]))
            threads.append(_run_thread(url, cnt, proxy_list=[proxy], robot_check=robot_check))
            cnt += 1

    for n in range(cnt, num_threads):
        threads.append(_run_thread(url, n, proxy_list=proxy_list, robot_check=robot_check))
    print("Threads created: {}".format(threads))
    return threads


def _run_thread(url, num=randrange(100, 10000), robot_check=False, proxy_list=None, html=None, location=None):
    """
    Convenience method to start one new thread with a downloading job and possibly with a random proxy depending on
    the user input.

    :author: sebastian
    :param url: The URL to download from.
    :param num: The ID of the thread.
    :param robot_check: Whether or not to honour robots.txt, defaults to False.
    :param proxy_list: The proxy to be used for downloading. If the list contains only one item this item is used.
    :param html: Defaults to None and is only specified if the user sent his or her own HTML to timestamp.
    :param location: Defaults to None. Specifies the location the html comes from or should come from.
    :return: The DownloadThread object that represents the freshly started thread.
    """

    if html is not None:
        thread = DownloadThread(num, html=html, robot_check=robot_check, prox_loc=location)
        thread.start()

    elif proxy_list is None:
        if location is not None:
            thread = DownloadThread(num, url=url, robot_check=robot_check, prox_loc=location)
        else:
            thread = DownloadThread(num, url=url, robot_check=robot_check)
        thread.start()
    else:
        # if  only one proxy is given that is taken otherwise randomly choose one.
        proxy_num = randrange(0, len(proxy_list))
        thread = DownloadThread(num, url=url, proxy=proxy_list[proxy_num][1], prox_loc=proxy_list[proxy_num][0],
                                robot_check=robot_check)
        thread.start()
    return thread


def _join_threads(threads, original_present=False):
    """
    Method that joins the threads in the list of DownloadThreads handed to it
    and returns the DownloadThread object with the highest votes after the join.
    The hash consists of the html plus the images.

    The voting could also be implemented in the following way:
        Another possible algorithm to identify the \textit{original} content is to first find out in which country the
        website originated from, crawl the website from that country and take that country’s content as the original to
        compare with the rest of the distributed timestamp.

    :author Sebastian
    :param threads: A list of DownloadThreads that need to be joined.
    :param original_present: Boolean value that states whether or not the threads should be checked for votes.
    :return: A list of DownloadThread objects with all important information about hash, html and infos about the
    download job and the index of the DownloadThread with the highest votes as second parameter.
    """
    app.logger.info("Joining Threads {}.".format(threads))
    for thread in threads:
        if type(thread) == list:
            print("having subthreads {}".format(thread))
            for subthread in thread:
                print("joining subthread {}".format(subthread))
                subthread.join()
        print("thread to join {}".format(thread))
        thread.join()
    if original_present:
        return threads, None
    return _check_threads(threads)


def _check_threads(threads):
    """
    Checks the threads for the one to return. Votes are cast for the agreement of the hashes, the one with the highest
    agreement has the highest probability of being the original.
    This is ony the fall back to getting the original by country of origin of the website.

    :author: Sebastian
    :param threads: The joined thread objects from the distributed timestamp.
    :return: All threads and as second parameter the index of the thread that should be taken as the timestamp and
    returned to the user.
    """
    votes = [0 for x in threads]
    for num in range(0, len(threads)):
        if threads[num].ipfs_hash is not None:
            print("We have an ipfs_hash from {} in Thread-{}: {}".format(threads[num].prox_loc, threads[num].threadID,
                                                                         threads[num].ipfs_hash))

        elif threads[num].error is not None or threads[num].ipfs_hash is None:
            # An error occurred in this thread, site unreachable from this location.
            app.logger.info("The url of Thread-{} ({}) is unreachable from {}."
                            .format(threads[num].threadID, threads[num].url, threads[num].prox_loc))
            continue

        for cnt in range(0, len(threads)):
            if threads[num].ipfs_hash == threads[cnt].ipfs_hash:
                # increment even if it is the same thread to separate if no other was successful
                votes[num] += 1
    app.logger.info(votes)
    print("Joined Threads: {}".format(votes))
    return threads, votes


def _submit_threads_to_db(results, user=None, original_hash=None):
    """
    Submits the results to db and judges the results as blocked or censored. According to judgement the result is
    either submitted or the countries table is updated to reflect the results.

    :author: Sebastian
    :param results: The results of the timestamping in list form with DownloadThread objects as items.
    :param user: The user that submitted the timestamp request as String of his username.
    :param original_hash: The hash to compare the results with to identify censored/modified content.
    """
    print("Add {} threads to db with original: {}. THe rest: {}".format(len(results), original_hash, results))
    error_threads = list()
    for thread in results:
        print("Adding Thread-{} to db".format(thread.threadID))

        if thread.error is not None:
            print("Add error thread {} from {} to db. Type of Error  was {}\n error was: {}"
                  .format(thread.threadID, thread.prox_loc, type(thread.error), str(thread.error)))
            if thread.prox_loc is not None and thread.error == TimeoutException:
                    country = Country.query.filter_by(country_code=thread.prox_loc).first()

                    country.block_count += 1
                    country.block_url = "{}{};".format(country.block_url, thread.url)
                    db.session.add(country)
                    db.session.commit()
                    print("Updated {} block count to {}".format(thread.prox_loc, str(country.block_count)))
                    print("Finished adding error Thread-{} to db".format(thread.threadID))

            error_threads.append(thread)
            results.remove(thread)
        elif thread.originstamp_result is None:
            # No error but originstamp result is not there -> something went really wrong
            print("No error but originstamp result is not there -> something went really wrong in Thread-{}"
                  .format(thread.threadID))
            error_threads.append(thread)
            results.remove(thread)

        elif original_hash is not None and original_hash != thread.ipfs_hash:
            print("The content from Thread-{} from {} does not match the original!\n {}\n{}"
                  .format(thread.threadID, thread.prox_loc, thread.ipfs_hash, original_hash))
            country = Country.query.filter_by(country_code=thread.prox_loc).first()
            country.censor_count += 1
            country.censored_urls = "{}{};".format(country.censored_urls, thread.url)
            db.session.add(country)
            db.session.commit()
            add_post_to_db(thread.url, thread.url, thread.title, thread.ipfs_hash,
                           thread.originstamp_result["created_at"], user=user)

        elif thread.ipfs_hash is not None:
            print("Adding Post for Thread-{} from country {} with Originstamp result: {}"
                  .format(thread.threadID, thread.prox_loc, str(thread.originstamp_result)))
            add_post_to_db(thread.url, thread.url, thread.title, thread.ipfs_hash,
                           thread.originstamp_result["created_at"], user=user)
        else:
            print("None Error and no hash in Thread-{} from {} proxy {} hash {}"
                  .format(thread.threadID, thread.prox_loc, thread.proxy, thread.ipfs_hash))
            error_threads.append(thread)
            results.remove(thread)

    print("Adding threads to db done. Error thread count is {} versus {} working threads."
          .format(len(error_threads), len(results)))
    return error_threads


def add_post_to_db(url, body, title, sha256, originstamp_time, user=None):
    """
    Method to add one new post to the database.

    :author: Sebastian
    :param url: The url of the post.
    :param body: The preprocessed html associated to the url that was the base of the timestamp.
    :param title: Optional title of the Post. Should mostly be the title of the website.
    :param sha256: The hash associated to the timestamp.
    :param originstamp_time: The time of the timestamp retrieved from originstamp.org.
    :param user: The user tat initiated this timestamp and to whom the post will eb attributed.
    If no user is named it will be attributed to the Stamp The Web 'Bot'.
    """
    already_exists = Post.query.filter(Post.hashVal == sha256).first()
    print("Query Adding one new post. Already exists: {}".format(already_exists))
    if already_exists is not None:
        print("Increasing  count for: {}".format(already_exists.hashVal))
        already_exists.count += 1
        db.session.add(already_exists)
    else:
        print("Make new post")
        if user is None:
            # Use bot for post, bot is authorid 113
            post_new = Post(body=body, urlSite=url, hashVal=sha256, webTitl=title,
                            origStampTime=datetime.strptime(originstamp_time, "%Y-%m-%dT%H:%M:%S.%fZ"),
                            author_id=113)
        else:
            user = check_user(user)
            print("We have a user:{}".format(user))
            post_new = Post(body=body, urlSite=url, hashVal=sha256, webTitl=title,
                            origStampTime=datetime.strptime(originstamp_time, "%Y-%m-%dT%H:%M:%S.%fZ"),
                            author_id=user.id)
        print("Finished adding one new post, committing")
        db.session.add(post_new)
    db.session.commit()


def check_user(user):
    """
    Check the database for a username to retrieve the user object from it.
    If no user can be found None will be returned.

    :author: Sebastian
    :param user: The username to search the db for.
    :return: An object of the db class User with al the information stored for a user.
    If no user can be found None will be returned.
    """
    if user == "Bot":
        db_user = User.query.filter(User.id == 113).first()
    else:
        db_user = User.query.filter(User.username == user.username).first()
    print(str(db_user))
    return db_user


def main():
    # url = 'http://www.theverge.com/2015/12/11/9891068/oneplus-x-review-android'
    # url = 'http://www.theverge.com/2016/1/29/10868232/starry-high-speed-internet-millimeter-wave'
    # url = 'http://www.sueddeutsche.de/wirtschaft/kommentar-gefaehrlich-verfuehrerisch-1.2833295'
    # url = 'http://www.suedkurier.de/nachrichten/politik/Deutschland-weist-pro-Tag-bis-zu-200-Fluechtlinge-
    # ab;art410924,8467176'
    # url = 'http://www.nytimes.com/2016/01/29/us/politics/republican-debate.html?hp&action=click&pgtype=Homepage&
    # clickSource=story-heading&module=a-lede-package-region&region=top-news&WT.nav=top-news'
    # url = 'http://www.theguardian.com/uk-news/2016/jan/29/maoist-cult-leader-jailed-for-23-years-as-slave-
    # daughter-goes-public'
    # url = 'http://www.suedkurier.de/region/kreis-konstanz/kreis-konstanz/Birgit-Homburger-Haemmerle-handelt-
    # unverantwortlich;art372432,8486747'
    # url = 'http://www.theguardian.com/world/2016/feb/01/aung-san-suu-kyi-leads-party-into-myanmar-parliament-to
    # -claim-power'
    # url = 'http://www.theverge.com/2016/1/31/10880394/samsung-internet-android-ad-content-blocker-adblock-fast'
    # url = 'http://www.suedkurier.de/region/kreis-konstanz/konstanz/Katamarane-verkehren-wieder-nach-Fahrplan;
    # art372448,7538479'
    # url = 'http://www.theverge.com/2016/2/1/10881470/airmail-ios-email-app-launch'
    # url = 'http://www.suedkurier.de/region/linzgau-zollern-alb/zollernalbkreis/Obduktion-soll-toedlichen-
    # Fastnachtsunfall-aufklaeren;art372549,8488507'
    # url = 'http://www.theverge.com/2016/1/31/10878834/spotify-dont-turn-into-itunes'
    url = 'https://www.washingtonpost.com/politics/a-more-agitated-sanders-tries-to-fend-off-attacks-of-nervous-' \
          'establishment/2016/01/31/15922f0c-c83b-11e5-a7b2-5a2f824b02c9_story.html?hpid=hp_hp-top-table-main_' \
          'sandersmoment1045p%3Ahomepage%2Fstory'
    print(get_url_history(url))


def date_handler(obj):
    return obj.isoformat() if hasattr(obj, 'isoformat') else obj


if __name__ == '__main__':
    main()
