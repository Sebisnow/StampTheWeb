import hashlib
import json
import os
import re
import requests
import uuid
import shutil
import zipfile
import traceback
import ipfsApi as ipfs
from readability.readability import Document
from subprocess import call, DEVNULL
from app import db
import pdfkit
from . import main
from flask import flash,current_app
import logging
#from manage import app
from flask import current_app as app


# regular expression to check URL, see https://mathiasbynens.be/demo/url-regex
urlPattern = re.compile('^(https?|ftp)://[^\s/$.?#].[^\s]*$')
#nullDevice = open(os.devnull, 'w')
basePath = 'app/pdf/'
errorCaught = ""
ipfs_Client = ipfs.Client('127.0.0.1', 5001)

apiPostUrl = 'http://www.originstamp.org/api/stamps'
# other apiKey:
# 77024f80396895bca0c028db35548c6e
# abeff668860c14b9643f4406c52a1dc2
apiKey = '7be3aa0c7f9c2ae0061c9ad4ac680f5c '
blockSize = 65536
options = {'quiet': ''}


class ReturnResults(object):
    def __init__(self, originStampResult, hashValue, webTitle):
        self.originStampResult = originStampResult
        self.hashValue = hashValue
        self.webTitle = webTitle


class DownloadError(Exception):
    """
    Error-Class for problems happening during running wkhtmltopdf/image.
    """

    def __init__(self, message):
        super(DownloadError, self).__init__(message)


class RequestError(Exception):
    """
    Error-Class for problems happening during requesting URL.
    """

    def __init__(self, message, req):
        super(RequestError, self).__init__(message)
        request = req


def get_text_from_other_country(china, usa, uk, url):
    if china is True:
        proxy = current_app.config['FLASKY_CHINA_PROXY']
        hash, text = update_and_send(proxy, url)
        return hash, text

    if usa is True:
        proxy = current_app.config['FLASKY_USA_PROXY']
        hash,text = update_and_send(proxy, url)
        return hash, text
    if uk:
        proxy = current_app.config['FLASKY_UK_PROXY']
        hash,text = update_and_send(proxy, url)
        return hash, text


def update_and_send(proxy, url):

    try:
        r = requests.get(url, proxies={"http": proxy})
    except:
        return None, None

    if r:
        return calculate_hash_for_html_doc(Document(r.text))


class OriginstampError(Exception):
    """
    Error-Class for problems happening during requesting URL.
    """

    def __init__(self, message, req):
        super(OriginstampError, self).__init__(message)
        request = req


def create_png_from_url(url, sha256):
    """
    Create png from URL. Returns path to file.

    :param url: url to retrieve
    :param sha256: name of the downloaded png
    :returns: path to the created png """
    app.logger.info('Creating PNG from URL:'+url)
    path = basePath + sha256 + '.png'
    app.logger.info('PNG Path:'+path)
    #call(['wkhtmltoimage', url, path, '--quality 20'], stderr=nullDevice)
    call(['wkhtmltoimage', '--quality', '20', url, path], stderr=DEVNULL)
    #call(["webkit2png", "-o", path, "-g", "1000", "1260", "-t", "30", url
    #subprocess.Popen(['wget', '-O', path, 'http://images.websnapr.com/?url='+url+'&size=s&nocache=82']).wait()
    if os.path.isfile(path):
        return
    flash(u'Could not create PNG from ' + url, 'error')
    app.logger.error('Could not create PNG from the: '+url)
    return


def create_html_from_url(doc, hash, url):
    path = basePath + hash + '.html'
    with open(path, 'w') as file:
        file.write(doc)
    if os.path.isfile(path):
        return
    flash(u'Could not create HTML from ' + url, 'error')
    app.logger.error('Could not create HTML from the: ' + url)
    return


def create_pdf_from_url(url,sha256):
    '''
    :param url: url to retrieve
    :param sha256: the hash of the url which is important for the filename
    method to write pdf file
    '''
    app.logger.info('Creating PDF from URL:' + url)
    path = basePath + sha256 + '.pdf'
    app.logger.info('PDF Path:'+path)
    try:
        pdfkit.from_url(url, path)
    except Exception as e:
        # is needed on on windows, where os.rename can't override existing files.
        if os.path.isfile(path):
            return
        flash(u'Could not create PDF from '+ url, 'error')
        app.logger.error('Could not create PDF from the: '+url)
        app.logger.error(traceback.format_exc(),e)
    return


def calculate_hash_for_html_doc(doc):
    """
    Calculate hash for given html document.

    :param html_doc: html doc to hash
    :returns: calculated hash for given URL and the document used to create the hash
    """
    app.logger.info('Creating HTML and Hash')

    # Detect the encoding of the html for future reference
    #encoding = chardet.detect(doc.summary().encode()).get('encoding')
    encoding = 'utf-8'
    doc.encoding = encoding

    text = '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1' \
           '-transitional.dtd">\n' + '<head>\n' + \
           '<meta http-equiv="Content-Type" content="text/html; ' \
           'charset=' + encoding + '">\n' + '</head>\n' + '<body>\n' \
           + '<h1>' + doc.title().split(sep='|')[0] + '</h1>'

    text += doc.summary() + '</body>'
    calc_hash = hashlib.sha256()
    calc_hash.update(doc.summary().encode(encoding))
    sha256 = calc_hash.hexdigest()
    app.logger.info('Hash:' + sha256)
    app.logger.info('HTML:' + text)
    return sha256, text


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


def submit_add_to_db(url, sha256, title):
    """
    submit hash to originStamp and store in DB.

    :param url: URL downloaded
    :param title: Title of the document behind the URL
    :param sha256: hash to name file after
    """
    originStampResult = submit(sha256, title)
    app.logger.info(originStampResult.text)
    app.logger.info('Origin Stamp Response:' + originStampResult.text)
    if originStampResult.status_code >= 400 :
        flash(u'Could not submit hash to originstamp. Error Code: ' + originStampResult.status_code +
              '\n ErrorMessage: ' + originStampResult.text,'error')
        app.logger.error('Could not submit hash to originstamp. Error Code: ' + originStampResult.status_code +
                         '\n ErrorMessage: ' + originStampResult.text)
        return originStampResult
        #raise OriginstampError('Could not submit hash to Originstamp', r)
    elif originStampResult.status_code >= 300 :
        flash(u'Internal System Error. Error Code: ' + originStampResult.status_code +
              '\n ErrorMessage: ' + originStampResult.text,'error')
        app.logger.error('300 Internal System Error. Could not submit hash to originstamp' )
        return originStampResult
    elif originStampResult.status_code == 200:
        #flash(u'URL already submitted to OriginStamp'+ url + ' Hash '+sha256)
        #app.logger.error('URL already submitted to OriginStamp' )
        return originStampResult
    elif "errors" in originStampResult.json():
        flash(u'Internal System Error. Error Code: ' + originStampResult.status_code +
              '\n ErrorMessage: ' + originStampResult.text,'error')
        app.logger.error('An Error occurred. Error Code: ' + originStampResult.status_code +
                         '\n ErrorMessage: ' + originStampResult.text)
        return originStampResult

    #date = parser.parse(r.json()['created_at'])
    #query = 'INSERT INTO stampedSites (hash, datetime, url, title) VALUES (%s, %s, %s, %s);'
    #db.execute_on_database(query, (sha256, date.strftime('%Y-%m-%d %H:%M:%S'), url, title))
    return originStampResult


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


def load_amp_js(soup):
    files = list()
    js_ctr = 0
    for scr in soup.find_all('script', {'src': re.compile('https://cdn.ampproject.org/.*')}):
        filename = 'js' + str(js_ctr) + '.js'
        js_ctr += 1
        r = requests.get(scr['src'], stream=True)
        if r.status_code == 200:
            with open(filename, 'wb') as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)
            scr['src'] = filename
            files.append(filename)
    return files


def compress_files(files, js_files):
    filename = str(uuid.uuid4()) + '.zip'
    archive = zipfile.ZipFile(filename, "w")
    sha256_calc = hashlib.sha256()
    for file in files:
        with open(file, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_calc.update(chunk)
        archive.write(file)
        os.remove(file)
    for file in js_files:
        archive.write(file)
        os.remove(file)
    archive.close()
    sha256 = sha256_calc.hexdigest()
    try:
        os.rename(filename, sha256 + ".zip")
    except FileExistsError as e:
        # is needed on on windows, where os.rename can't override existing files.
        os.remove(sha256 + ".zip")
        os.rename(filename, sha256 + ".zip")
    return sha256


def check_database_for_hash(sha256):
    query = 'SELECT COUNT(*) AS c FROM posts WHERE posts.hashVal = '+sha256+';'
    from sqlalchemy import text
    sql = text(query)
    result = db.engine.execute(sql)
    return result


def check_database_for_url(url):
    query = 'SELECT * FROM stampedSites WHERE stampedSites.url = %s ORDER BY datetime ASC;'
    return db.execute_on_database(query, url)


def submitHash(hash):
    originStampResult = submit(hash, "")
    app.logger.info(originStampResult.text)
    app.logger.info('Origin Stamp Response:' + originStampResult.text)
    if originStampResult.status_code >= 300 and app.config['TESTING'] == False:
        flash(u'300 Internal System Error. Could not submit hash to originstamp.','error')
        app.logger.error('300 Internal System Error. Could not submit hash to originstamp' )
        return ReturnResults(None, hash, "None")
    elif originStampResult.status_code == 200 and app.config['TESTING'] == False:
        flash(u'Hash already submitted to OriginStamp' + ' Hash '+hash)
        app.logger.error('Hash already submitted to OriginStamp' )
        return ReturnResults(originStampResult, hash, "")
        #raise OriginstampError('Could not submit hash to Originstamp', r)
    elif "errors" in originStampResult.json() and app.config['TESTING'] == False:
        flash(u'300 Internal System Error. Could not submit hash to originstamp.','error')
        app.logger.error('300 Internal System Error. Could not submit hash to originstamp' )
        return ReturnResults(None, hash, "None")
    else:
        return ReturnResults(originStampResult, hash, "")


def getHashOfFile(fname):
    res = ipfs_Client.add(fname)
    """
    hash_sha265 = hashlib.sha256()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha265.update(chunk)
    return hash_sha265.hexdigest()
    """
    return res['Hash']

def get_text_timestamp(text):
    ipfs_hash = ipfs_Client.add_str(text)
    # hash_object = hashlib.sha256(text)
    # hex_dig = hash_object.hexdigest()
    results = submitHash(ipfs_hash)
    return results


def get_hash_history(hash):
    """
    :parm hash: the hash which needs to verify from OriginStamps
    """
    results = submitHash(hash)
    return results


def get_url_history(url):
    """
    Entry point for the downloader
    :param url: the URL to get the history for
    :return: history of the URL in the system
    """
    # validate URL
    OriginstampError = None
    sha256 = None
    if not re.match(urlPattern, url):
        flash('100' + 'Bad URL' + 'URL needs to be valid to create timestamp for it:' + url, 'error')
        app.logger.error('100' + 'Bad URL' + 'URL needs to be valid to create timestamp for it:' + url)
        return ReturnResults(None, None, None)

    res = requests.get(url)
    if res.status_code >= 300:
        flash('100 Bad URL Could not retrieve URL to create timestamp for it.' + url, 'error')
        app.logger.error('100 Bad URL Could not retrieve URL to create timestamp for it:' + url)
        return ReturnResults(None, None, None)
    #soup = BeautifulSoup(res.text.encode(res.encoding), 'html.parser')
    doc = Document(res.text)
    #encoding = chardet.detect(res.text.encode()).get('encoding')
    try:
        sha256, html_text = calculate_hash_for_html_doc(doc)
        #if check_database_for_hash(sha256) < 1:
        originStampResult = save_render_zip_submit(html_text, sha256, url, doc.title())
    except:
        # TODO needs a better description of what errors could occur and need catching
        flash(u'300 Internal System Error. Could not submit hash to originstamp:' + url,'error')
        app.logger.error('300 Internal System Error. Could not submit hash to originstamp' )

        # TODO OriginstampError is never set anything but none
        '''
        if OriginstampError is not None:
            return ReturnResults(originStampResult, sha256, doc.title())
        else:
            return ReturnResults(None, sha256, doc.title())
        '''
        return ReturnResults(None, sha256, doc.title())
    #return json.dumps(check_database_for_url(url), default=date_handler)
    return ReturnResults(originStampResult, sha256, doc.title())

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

def save_render_zip_submit(doc, sha256, url, title):

    create_html_from_url(doc, sha256, url)
    #archive = zipfile.ZipFile(basePath + sha256 + '.zip', "w", zipfile.ZIP_DEFLATED)
    #archive.write(basePath + sha256 + '.html')
    #os.remove(basePath + sha256 + '.html')
    #archive.write(basePath + sha256 + '.png')
    #os.remove(basePath + sha256 + '.png')
    originStampResult = submit_add_to_db(url, sha256, title)

    # moved image creation behind Timestamping so images are only created for new Stamps if no eror occurred
    if originStampResult.status_code == 200:
        create_png_from_url(url, sha256)
        create_pdf_from_url(url, sha256)
    return originStampResult


def main():
    # url = 'http://www.theverge.com/2015/12/11/9891068/oneplus-x-review-android'
    # url = 'http://www.theverge.com/2016/1/29/10868232/starry-high-speed-internet-millimeter-wave'
    # url = 'http://www.sueddeutsche.de/wirtschaft/kommentar-gefaehrlich-verfuehrerisch-1.2833295'
    # url = 'http://www.suedkurier.de/nachrichten/politik/Deutschland-weist-pro-Tag-bis-zu-200-Fluechtlinge-ab;art410924,8467176'
    # url = 'http://www.nytimes.com/2016/01/29/us/politics/republican-debate.html?hp&action=click&pgtype=Homepage&clickSource=story-heading&module=a-lede-package-region&region=top-news&WT.nav=top-news'
    # url = 'http://www.theguardian.com/uk-news/2016/jan/29/maoist-cult-leader-jailed-for-23-years-as-slave-daughter-goes-public'
    # url = 'http://www.suedkurier.de/region/kreis-konstanz/kreis-konstanz/Birgit-Homburger-Haemmerle-handelt-unverantwortlich;art372432,8486747'
    # url = 'http://www.theguardian.com/world/2016/feb/01/aung-san-suu-kyi-leads-party-into-myanmar-parliament-to-claim-power'
    # url = 'http://www.theverge.com/2016/1/31/10880394/samsung-internet-android-ad-content-blocker-adblock-fast'
    # url = 'http://www.suedkurier.de/region/kreis-konstanz/konstanz/Katamarane-verkehren-wieder-nach-Fahrplan;art372448,7538479'
    # url = 'http://www.theverge.com/2016/2/1/10881470/airmail-ios-email-app-launch'
    # url = 'http://www.suedkurier.de/region/linzgau-zollern-alb/zollernalbkreis/Obduktion-soll-toedlichen-Fastnachtsunfall-aufklaeren;art372549,8488507'
    # url = 'http://www.theverge.com/2016/1/31/10878834/spotify-dont-turn-into-itunes'
    url = 'https://www.washingtonpost.com/politics/a-more-agitated-sanders-tries-to-fend-off-attacks-of-nervous-establishment/2016/01/31/15922f0c-c83b-11e5-a7b2-5a2f824b02c9_story.html?hpid=hp_hp-top-table-main_sandersmoment1045p%3Ahomepage%2Fstory'
    print(get_url_history(url))


def json_error(code, title, detail):
    return json.dumps({'jsonapi': {'version': '1.0'},
                       'errors': {'code': code,
                                  'title': title,
                                  'detail': detail}})


def date_handler(obj):
    return obj.isoformat() if hasattr(obj, 'isoformat') else obj


def execute_on_database(query, args):
    connection = db.session.connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute('USE posts')
            cursor.fetchall()
            cursor.execute(query, args)
            result = cursor.fetchall()
        connection.commit()
    finally:
        connection.close()
    return result


if __name__ == '__main__':
    main()
