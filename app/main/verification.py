import hashlib
import os
import json
import requests
import chardet
import traceback
import re
from time import mktime

from bs4 import BeautifulSoup
from readability.readability import Document
from subprocess import call, DEVNULL
from os.path import devnull
from app import db
import pdfkit
from . import main
from flask import abort, flash, current_app
import logging
# from manage import app
from app import create_app as app

# regular expression to check URL, see https://mathiasbynens.be/demo/url-regex
urlPattern = re.compile('^(https?|ftp)://[^\s/$.?#].[^\s]*$')
nullDevice = open(os.devnull, 'w')
basePath = 'app/pdf/'
errorCaught = ""

apiPostUrl = 'http://www.originstamp.org/api/stamps'
# other apiKey:
# 77024f80396895bca0c028db35548c6e
# abeff668860c14b9643f4406c52a1dc2
apiKey = '7be3aa0c7f9c2ae0061c9ad4ac680f5c '
blockSize = 65536
options = {'quiet': ''}


class ReturnResults(object):
    def __init__(self, html_text, hashValue, webTitle):
        self.html_text = html_text
        self.hashValue = hashValue
        self.webTitle = webTitle


def create_png_from_html(url, sha256):
    """Create png from URL. Returns path to file.
    :param url: url to retrieve
    :param sha256: name of the downloaded png"""
    current_app.logger.info('Creating PNG from URL:' + url)
    path = basePath + sha256 + '.png'
    current_app.logger.info('PNG Path:' + path)
    call(['wkhtmltoimage', '--quality', '20', url, path], stderr=DEVNULL)
    if os.path.isfile(path):
        return
    flash(u'Could not create PNG from ' + url, 'error')
    current_app.logger.error('Could not create PNG from the: ' + url)
    return


def create_pdf_from_url(url, sha256):
    #:param url: url to retrieve
    # method to write pdf file
    current_app.logger.info('Creating PDF from URL:' + url)
    path = basePath + sha256 + '.pdf'
    current_app.logger.info('PDF Path:' + path)
    try:
        pdfkit.from_url(url, path)
    except Exception as e:
        # is needed on on windows, where os.rename can't override existing files.
        flash(u'Could not create PDF from ' + url, 'error')
        current_app.logger.error('Could not create PDF from the: ' + url)
        current_app.logger.error(traceback.format_exc(), e)
    return


def get_file_text(hash):
    # Parm hash: value of hash to open the file
    path = basePath + hash + '.html'
    try:
        if os.path.isfile(path):
            file = open(path, encoding="utf-8")
            text = file.read()
        else:
            flash('HTML not found, due to some internal problem. Hash:' + hash)
            logging.error('HTML file not found ' + path + 'Hash:' + hash)
            return ''
    except:
        if os.path.isfile(path):
            file = open(path, encoding="cp1252")
            text = file.read()
        else:
            flash('HTML not found, due to some internal problem. Hash:' + hash)
            logging.error('HTML file not found ' + path + 'Hash:' + hash)
            return ''
    return text


def writePostsData(posts):
    container = {}
    child = []
    for post in posts:
        item_dict = {}
        item_dict['id'] = str(post.id)
        item_dict['title'] = post.webTitl
        item_dict['url'] = '/comp/' + str(post.id)
        item_dict['class'] = 'event-success'
        dt = post.timestamp
        sec_since_epoch = mktime(dt.timetuple()) + dt.microsecond / 1000000.0
        millis_since_epoch = sec_since_epoch * 1000
        item_dict['start'] = str(millis_since_epoch)
        item_dict['end'] = str(millis_since_epoch + 9000000)
        child.append(dict(item_dict))
    container['success'] = '1'
    container['result'] = child
    path = basePath + 'events.json.php'
    if os.path.isfile(path):
        try:
            os.remove(basePath + 'events.json.php')
            with open(basePath + 'events.json.php', 'w') as outfile:
                json.dump(container, outfile, sort_keys=True, indent=4, separators=(',', ': '))
        except:
            flash(u'Internal System Error. Could not delete timeline file.', 'error')
            current_app.logger.error('Internal System Error. Could not delete timeline file.')
    else:
        try:
            with open(basePath + 'events.json.php', 'w') as outfile:
                json.dump(container, outfile, sort_keys=True, indent=4, separators=(',', ': '))
        except:
            flash(u'Internal System Error. Could not write events to calendar.', 'error')
            current_app.logger.error('Internal System Error. Could not write events to calendar.')


def calculate_hash_for_html_doc(html_doc):
    """Calculate hash for given html document.
    :param html_doc: html doc to hash
    :returns: calculated hash for given URL and the document used to create the hash
    """
    current_app.logger.info('Creating HTML and Hash')
    doc = Document(html_doc)
    # Detect the encoding of the html for future reference
    encoding = chardet.detect(doc.summary().encode()).get('encoding')
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
    current_app.logger.info('Hash:' + sha256)
    current_app.logger.info('HTML:' + text)
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
    return requests.get(apiPostUrl, json=data, headers=headers)


def submit_add_to_db(url, sha256, title):
    """
    submit hash to originStamp and store in DB.

    :param url: URL downloaded
    :param title: Title of the document behind the URL
    :param sha256: hash to name file after
    """
    originStampResult = submit(sha256, title)
    current_app.logger.info(originStampResult.text)
    current_app.logger.info('Origin Stamp Response:' + originStampResult.text)
    if originStampResult.status_code >= 300:
        flash(u'An Error occur while submitting hash to originstamp. Hash: ' + sha256, 'error')
        current_app.logger.error('An Error occur while submitting hash to originstamp. Hash:' + sha256)
        return originStampResult
        # raise OriginstampError('Could not submit hash to Originstamp', r)
    elif "errors" in originStampResult.json():
        flash(u'An Error occur while submitting hash to originstamp. Hash:' + sha256, 'error')
        current_app.logger.error('An Error occur while submitting hash to originstamp. Hash: ' + sha256)
        return originStampResult

    return originStampResult


def submitHash(hash):
    originStampResult = submit(hash, "")
    current_app.logger.info(originStampResult.text)
    current_app.logger.info('Origin Stamp Response:' + originStampResult.text)
    if originStampResult.status_code >= 300:
        flash(u'300 Internal System Error. Could not submit hash to originstamp.', 'error')
        current_app.logger.error('300 Internal System Error. Could not submit hash to originstamp')
        return ReturnResults(None, hash, "None")
        # raise OriginstampError('Could not submit hash to Originstamp', r)
    elif "errors" in originStampResult.json():
        flash(u'300 Internal System Error. Could not submit hash to originstamp.', 'error')
        current_app.logger.error('300 Internal System Error. Could not submit hash to originstamp')
        return ReturnResults(None, hash, "None")
    else:
        return ReturnResults(originStampResult, hash, "")


def getHashOfFile(fname):
    hash_sha265 = hashlib.sha256()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha265.update(chunk)
    return hash_sha265.hexdigest()


def get_text_timestamp(text):
    hash_object = hashlib.sha256(text)
    hex_dig = hash_object.hexdigest()
    results = submitHash(hex_dig)
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
    # get_hash_history
    # validate URL
    if not re.match(urlPattern, url):
        flash('100' + 'Bad URL' + 'URL needs to be valid to create timestamp for it:' + url, 'error')
        current_app.logger.error('100' + 'Bad URL' + 'URL needs to be valid to create timestamp for it:' + url)
        return ReturnResults(None, None, None)

    res = requests.get(url)
    if res.status_code >= 300:
        flash('100 Bad URL Could not retrieve URL to create timestamp for it.' + url, 'error')
        current_app.logger.error('100 Bad URL Could not retrieve URL to create timestamp for it:' + url)
        return ReturnResults(None, None, None)
    # soup = BeautifulSoup(res.text.encode(res.encoding), 'html.parser')
    # encoding = chardet.detect(res.text.encode()).get('encoding')
    doc = Document(res.text)
    try:
        sha256, html_text = calculate_hash_for_html_doc(res.text)
        f_name = sha256 + 'temporary'
        with open(basePath + f_name + '.html', 'w') as file:
            file.write(html_text)
        html_text = get_file_text(f_name)
        # originStampResult = save_render_zip_submit(doc, sha256, url, soup.title.string)

    except:
        flash(u'A problem occured while creating html for the URL :' + url, 'error')
        current_app.logger.error('A problem occured while creating html for the URL:' + url)
        if html_text is not None:
            return ReturnResults(html_text, sha256, doc.title())
        else:
            return ReturnResults(None, sha256, doc.title())

    # return json.dumps(check_database_for_url(url), default=date_handler)

    return ReturnResults(html_text, sha256, doc.title())


def remove_tags(text):
    TAG_RE = re.compile(r'<[^>]+>')
    return TAG_RE.sub('', text)


def save_render_zip_submit(doc, sha256, url, title):
    # with open(basePath + sha256 + '.html', 'w') as file:
    # file.write(doc)
    create_png_from_html(url, sha256)
    create_pdf_from_url(url, sha256)
    # archive = zipfile.ZipFile(basePath + sha256 + '.zip', "w", zipfile.ZIP_DEFLATED)
    # archive.write(basePath + sha256 + '.html')
    # os.remove(basePath + sha256 + '.html')
    # archive.write(basePath + sha256 + '.png')
    # os.remove(basePath + sha256 + '.png')
    originStampResult = submit_add_to_db(url, sha256, title)
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
