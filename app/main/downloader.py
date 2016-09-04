import json
import os
import re
import requests
import traceback
import ipfsApi
from subprocess import check_output, call, DEVNULL
import pdfkit
import queue
import threading
import csv
from app.main import download_thread as d_thread
from random import randrange
from flask import flash
from flask import current_app as app
from urllib.parse import urlparse
from app.main.download_thread import DownloadThread
from app.main import proxy_util


# regular expression to check URL, see https://mathiasbynens.be/demo/url-regex
urlPattern = re.compile('^(https?|ftp)://[^\s/$.?#].[^\s]*$')
# nullDevice = open(os.devnull, 'w')
basePath = 'app/pdf/'
d_thread.base_path = basePath
errorCaught = ""
ipfs_Client = ipfsApi.Client('127.0.0.1', 5001)

apiPostUrl = 'http://www.originstamp.org/api/stamps'
apiKey = '7be3aa0c7f9c2ae0061c9ad4ac680f5c '
blockSize = 65536
options = {'quiet': ''}


class ReturnResults(object):
    """
    :author: Waqar and Sebastian
    Helper class to return the results from downloader to the views. Therefore this class is equivalent to an API.
    """

    def __init__(self, originstamp_result, hash_value, web_title, errors=None):
        self.originStampResult = originstamp_result
        self.hashValue = hash_value
        self.webTitle = web_title
        self.errors = errors


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
    basePath = 'app/pdf/temp-world.geo.json'
    with open(basePath) as data_file:
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
    basePath = 'app/pdf/temp-world.geo.json'
    with open(basePath) as data_file:
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
    basePath = 'app/pdf/temp-world.geo.json'
    with open(basePath) as data_file:
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
    with open(basePath + "proxy_list.tsv", "rt", encoding="utf8") as tsv:
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
        return calculate_hash_for_html_doc(r.text)


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
    :param url: url to retrieve
    :param sha256: name of the downloaded png
    :returns: path to the created png """
    app.logger.info('Creating PNG from URL:' + url)
    path = basePath + sha256 + '.png'
    app.logger.info('PNG Path:' + path)
    call(['wkhtmltoimage', '--quality', '20', url, path], stderr=DEVNULL)
    # call(["webkit2png", "-o", path, "-g", "1000", "1260", "-t", "30", url
    # subprocess.Popen(['wget', '-O', path, 'http://images.websnapr.com/?url='+url+'&size=s&nocache=82']).wait()
    if os.path.isfile(path):
        return
    if not app.config["TESTING"]:
        flash(u'Could not create PNG from ' + url, 'error')
    app.logger.error('Could not create PNG from the URL : ' + url)
    return


def create_html_from_url(html_text, ipfs_hash, url):
    path = basePath + ipfs_hash + '.html'
    app.logger.info("Fetching the HTML file from IPFS to save locally.")
    # fetch the to IPFS submitted html text to store on disk
    try:
        cur_dir = os.getcwd()
        os.chdir(basePath)
        ipfs_Client.get(ipfs_hash)
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
                ip = ipfs_Client.add(path)
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
    :param url: url to retrieve
    :param sha256: the hash of the url which is important for the filename
    method to write pdf file
    """
    app.logger.info('Creating PDF from URL:' + url)
    path = basePath + sha256 + '.pdf'
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
    :param html_text: html doc to hash as text
    :returns: calculated hash for given URL and the document used to create the hash
    """
    app.logger.info('Creating HTML and Hash')
    text, title = d_thread.preprocess_doc(html_text)
    sha256 = save_file_ipfs(text)

    app.logger.info('Hash:' + sha256)
    # app.logger.info('HTML:' + text)
    return sha256, text, title


def submit(sha256, title=None):
    """
    Submits the given hash to the originstamp API and returns the request object.

    :param sha256: hash to submit
    :param title: title of the hashed document
    :returns: resulting request object
    """
    headers = {'Content-Type': 'application/json', 'Authorization': 'Token token="7be3aa0c7f9c2ae0061c9ad4ac680f5c"'}
    data = {'hash_sha256': sha256, 'title': title}
    return requests.post(apiPostUrl, json=data, headers=headers)


def get_originstamp_history(sha256):
    """
    Fetches the history of the hash from originstamp. Response object looks like the following. Most important for
    StampTheWeb is the created_at tag:
    {'title': '', 'created_at': '2016-06-23T08:36:21.242Z', 'updated_at': '2016-06-24T00:02:28.728Z',
    'blockchain_transaction': {'created_at': '2016-06-24T00:02:26.796Z', 'updated_at': '2016-06-26T20:04:08.674Z',
    'public_key': '03a1673f7e06c345e3f8f26160b42616f421041e13b301e561b52aaeaa62f2deda', 'status': 1,
    'seed': '<very long seed representing the blockchain>',
    'private_key': 'a3dabafdc73c4b0bcc50191aef89c3fdb5cf9e728af6bcddec3a9905b04a4092',
    'recipient': '1KLwyN4qoA6yTmdr39Eqj5b1FCW6hxik9R', 'tx_hash':
    'd9496339662ad07e693605e9e374fb3cc09058f59b7c4ab2a958d713d9232cb2'},
    'hash_sha256': 'QmXiSkFRT7agFChpLa5BhJkvDAVHEefrekAf7DWjZKnmE8', 'submitted_at': None}

    :author: Sebastian
    :param sha256: hash to submit
    :returns: resulting response object
    """
    headers = {'Content-Type': 'application/json', 'Authorization': 'Token token="7be3aa0c7f9c2ae0061c9ad4ac680f5c"'}

    return requests.get("{}/{}".format(apiPostUrl, sha256), headers=headers)


def submit_add_to_db(url, sha256, title):
    """
    submit hash to originStamp and store in DB.
    # TODO store in WARC file that is described by the URL and append changed hashes of a URL to the same WARC.

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
            history = get_originstamp_history(sha256)
            if not app.config["TESTING"]:
                flash(u'Submitted hash to Originstamp successfully but hash already taken: '
                      u'{}'.format(history.json()["created_at"]))
            app.logger.error('Submitted hash to Originstamp successfully but hash already taken: '
                             '{}'.format(history.json()["created_at"]))
            return ReturnResults(originstamp_result, sha256, "None", originstamp_result.text)
        else:
            if not app.config["TESTING"]:
                flash(u'Hash was submitted to OriginStamp successfully' + ' Hash ' + sha256)
            app.logger.info('Hash was submitted to OriginStamp successfully')
            return ReturnResults(originstamp_result, sha256, "")
        # raise OriginstampError('Could not submit sha256 to Originstamp', r)
    else:
        return ReturnResults(originstamp_result, sha256, "")


def getHashOfFile(fname):
    """
    This method submits a file to IPFS and returns the resulting hash that describes the address of the file on IPFS.

    :author: Sebastian
    :param fname: The path to the File to get the hash for.
    :return: Returns the Hash of the file.
    """
    res = ipfs_Client.add(fname)
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
    path = basePath + "temp.html"
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
    ipfs_hash = ipfs_Client.add(path)
    print(ipfs_hash[0]['Hash'])
    return ipfs_hash[0]['Hash']


def get_hash_history(sha256):
    """
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

    path = basePath + timestamp
    cur_dir = os.getcwd()
    os.chdir(basePath)
    app.logger.info("Trying to fetch the HTML from IPFS")
    try:
        check_output(['ipfs', 'get', timestamp], stderr=DEVNULL)
        app.logger.info("ipfs command completed. Fetched File present: " +
                        str(os.path.exists(basePath + timestamp)))
    except FileNotFoundError as e:
        app.logger.info(e.strerror + " ipfs command not found trying another way." + str(type(timestamp)))
        check_output(['/home/ubuntu/bin/ipfs', 'get', timestamp], stderr=DEVNULL)

        app.logger.info("There is a file called " + path + timestamp + ": " +
                        str(os.path.exists(basePath + timestamp)))
        app.logger.info("There is a file called " + path + ": " + str(os.path.exists(path)))

    except Exception as e:

        app.logger.error("Error while trying to fetch from IPFS or renaming" + str(e) + "\n" +
                         "Could be a Permission problem on the Server")
        check_output(['/home/ubuntu/bin/ipfs', 'get', timestamp], stderr=DEVNULL)
        app.logger.info("There is a file called " + path + ": " + str(os.path.exists(basePath +
                                                                                     timestamp)))
    os.chdir(cur_dir)
    return path


def get_url_history(url):
    """
    Entry point for the downloader

    :author: Sebastian
    :param url: the URL to get the history for
    :return: a ReturnResults Object with the originStampResult, hashValue and webTitle and optionally an error message
    """
    # validate URL
    sha256 = None
    if not re.match(urlPattern, url):
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
        app.logger.error('Internal System Error: ' + str(e.args))
        traceback.print_exc()
        return ReturnResults(None, sha256, title)

    # return json.dumps(check_database_for_url(url), default=date_handler)
    return ReturnResults(originstamp_result, sha256, title)


'''
# Deprecated Method of old STW
def load_zip_submit(url, soup, enc):
    old_path = os.getcwd()
    tmp_dir = basePath + str(uuid.uuid4())
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
    :return: Returns an OriginstampResult object.
    """
    try:
        create_html_from_url(html_text, sha256, url)
    except FileNotFoundError as fileError:
        # can only occur if data was submitted successfully but png or pdf creation failed
        if not app.config["TESTING"]:
            flash(u'Internal System Error while creating the HTML: ' + fileError.strerror, 'error')
        app.logger.error('Internal System Error while creating HTML,: ' +
                         fileError.strerror + "\n Maybe check the path, current base path is: " + basePath)
    # archive = zipfile.ZipFile(basePath + sha256 + '.zip', "w", zipfile.ZIP_DEFLATED)
    # archive.write(basePath + sha256 + '.html')
    # os.remove(basePath + sha256 + '.html')
    # archive.write(basePath + sha256 + '.png')
    # os.remove(basePath + sha256 + '.png')
    originstamp_result = submit_add_to_db(url, sha256, title)

    # moved image creation behind Timestamping so images are only created for new Stamps if no error occurred
    if originstamp_result.status_code == 200:
        try:
            create_png_from_url(url, sha256)
            # TODO  pdf creation throws error on server - check
            create_pdf_from_url(url, sha256)
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


def distributed_timestamp(url, html_body=None, proxies=None):
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
    :param html_body: The body of the site to timestamp.
    :param proxies: A list of max 5 Proxies that should be taken
     into account for the distributed timestamp.
    Defaults to None
    :return: Returns the result of the distributed Timestamp as a ReturnResults Object, including the
    originStampResult, hashValue, webTitle and errors(defaults to None).
    """

    if not re.match(urlPattern, url):
        return ReturnResults(None, None, None, OriginstampError("The entered URL does not correspond "
                                                                "to URL specifications", 501))
    extension_triggered = False
    if html_body:
        extension_triggered = True
    proxy_list = proxy_util.get_proxy_list()

    threads = []
    if proxies is None or len(proxies) == 0:
        # no manual proxies set fetch them from list
        if extension_triggered:
            threads.append(run_thread(url, 1, html_body))
        else:
            threads.append(run_thread(url, 1, proxy_list))

        for n in range(2, 6):
            threads.append(run_thread(url, n, proxy_list))

    else:
        # manual proxies set
        if extension_triggered:
            threads.append(run_thread(url, 1, html_body))
        else:
            threads.append(run_thread(url, 1, [proxies[0]]))
        # if there are entries in the proxies use them
        cnt = 2
        for prox in proxies:
            if cnt > 5:
                break
            threads.append(run_thread(url, cnt, [prox]))
            cnt += 1
        # create the rest of the threads to fill up to 5 threads with proxy_list
        for n in range(cnt, 6):
            threads.append(run_thread(url, n, proxy_list))
    # join all threads and return the DownloadThread with the most votes
    joined_threads, max_index = join_threads(threads)

    originstamp_result = submit(joined_threads[max_index].ipfs_hash, joined_threads[max_index].url)
    app.logger.info("The result from Originstamp:{}".format(originstamp_result))
    # TODO threads are joined return the result to be added to db and store the countries that censored in db as well.

    return ReturnResults(originstamp_result=originstamp_result, hash_value=joined_threads[max_index].ipfs_hash,
                         web_title=joined_threads[max_index].html.title)


def run_thread(url, num, proxy_list=None, html=None):
    """
    Convencience method to start one new thread with a downloading job and possibly with a random proxy

    :author: sebastian
    :param url: The URL to download from.
    :param num: The ID of the thread.
    :param proxy_list: The proxy to be used for downloading
    :param html: Defaults to None and is only specified if the user sent an HTML to timestamp.
    :return: The DownloadThread object that represents the freshly started thread.
    """
    if html is None:
        prox_num = randrange(0, len(proxy_list))
        thread = DownloadThread(num, url=url, prox=proxy_list[prox_num][1], prox_loc=proxy_list[prox_num][0])
        thread.start()
    else:
        thread = DownloadThread(num, html=html)
        thread.start()
    return thread


def join_threads(threads):
    """
    Method that joins the threads in the list of DownloadThreads handed to it
    and returns the DownloadThread object with the highest votes after the join.
    The hash consists of the html plus the images.

    :param threads: A list of DownloadThreads that need to be joined.
    :return: A list of DownloadThread objects with all important information about hash, html and infos about the
    download job and the index of the DownloadThread with the highest votes as second parameter.
    """
    app.logger.info("Joining Threads.")
    results = []
    for thread in threads:
        thread.join()
        results.append(thread)

    # TODO store different results
    votes = [0 for x in results]
    for num in range(0, len(results)):
        for cnt in range(0, len(results)):
            if results[num].ipfs_hash == results[cnt].ipfs_hash:
                votes[num] += 1
    app.logger.info(votes)
    print("Joined Threads: {}".format(votes))
    return results, votes.index(max(votes))


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
