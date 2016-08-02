from app import email
import os
import requests
import traceback
from readability.readability import Document
from subprocess import call, DEVNULL
import pdfkit
# from manage import app
from flask import current_app as app
from app.models import Post
from datetime import datetime
from app import db
from sqlalchemy import and_
import ipfsApi as ipfs

"""
:author: Waqar
This module sends email. In case a scheduled articles is found changed and blocked in a given country.
Some code from downloader.py is copied here. Since this code works out of application context. The code
re-usability from downloader.py was not possible.
"""

basePath = 'app/pdf/'
apiPostUrl = 'http://www.originstamp.org/api/stamps'
apiKey = '7be3aa0c7f9c2ae0061c9ad4ac680f5c '
blockSize = 65536
options = {'quiet': ''}
errorCaught = ""
ipfs_Client = ipfs.Client('127.0.0.1', 5001)


class OriginstampError(Exception):
    """
    Error-Class for problems happening during requesting URL.
    """

    def __init__(self, message, req):
        super(OriginstampError, self).__init__(message)
        request = req


def get_pages_send_email(post, task):
    url = post.urlSite
    if task.china:
        proxy = app.config['STW_CHINA_PROXY']
        if update_and_send(proxy, post, url, 'China', True):
            return True
    elif task.usa:
        proxy = app.config['STW_USA_PROXY']
        if update_and_send(proxy, post, url, 'USA', True):
            return True
    elif task.uk:
        proxy = app.config['STW_UK_PROXY']
        if update_and_send(proxy, post, url, 'UK', True):
            return True
    else:
        proxy = None
        if update_and_send(proxy, post, url, 'UK', False):
            return True


def update_and_send(proxy, post, url, country, is_proxy):
    user = post.author
    if is_proxy:
        try:
            r = requests.get(url, proxies={"http": proxy})
        except:
            email.send_email_normal(user.email, 'Your requested web Article Blocked in ' + country,
                                    'main/block_mail', user=user, post=post, server=app.config['SERVER_URL'])
            return True
    else:
        try:
            r = requests.get(url)
        except:
            email.send_email_normal(user.email, 'Your requested web Article Blocked',
                                    'main/block_mail', user=user, post=post, server=app.config['SERVER_URL'])
            return True
    if r:
        doc = Document(r.text)
        sha256, html_text = calculate_hash_for_html_doc(doc)
        if sha256 == post.hashVal:
            return True
        else:

            try:
                originStampResult = save_render_zip_submit(html_text, sha256, url, doc.title())
            except:
                app.logger.error('300 Internal System Error. Could not submit hash to originstamp')

            app.logger.error('Hash: ' + sha256 + ' submitted to originstamp')
            dateTimeGMT = originStampResult.headers['Date']
            post_new = Post(body=doc.title(), urlSite=url, hashVal=sha256, webTitl=doc.title(),
                            origStampTime=datetime.strptime(dateTimeGMT, "%a, %d %b %Y %H:%M:%S %Z"),
                            author=user)
            db.session.add(post_new)
            db.session.commit()
            post_created = Post.query.filter(and_(Post.urlSite.like(url),
                                                  Post.hashVal.like(sha256))).first()
            ids = str(post.id) + ':' + str(post_created.id)
            if post_created:
                email.send_email_normal(user.email, 'Change in the requested Article found',
                                        'main/normal_email', user=user, post=post_created, ids=ids,
                                        server=app.config['SERVER_URL'])
            return True
    else:
        email.send_email_normal(user.email, 'Your requested web Article Blocked in ' + country,
                                'main/block_email', user=user, post=post, server=app.config['SERVER_URL'])
        return True


def calculate_hash_for_html_doc(doc):
    """
    Calculate hash for given html document.
    :param doc: html doc to hash
    :returns: calculated hash for given URL and the document used to create the hash
    """
    app.logger.info('Creating HTML and Hash')

    text = preprocess_doc(doc)
    sha256 = save_file_ipfs(text)

    app.logger.info('Hash:' + sha256)
    # app.logger.info('HTML:' + text)
    return sha256, text


def preprocess_doc(doc):
    """
    Calculate hash for given html document.
    :param doc: html doc to hash
    :returns: calculated hash for given URL and the document used to create the hash
    """
    app.logger.info('Preprocessing Document')

    # Detect the encoding of the html for future reference
    # encoding = chardet.detect(doc.summary().encode()).get('encoding')
    encoding = 'utf-8'
    doc.encoding = encoding
    # TODO all the Header information should be preserved not rewritten
    text = '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1' \
           '-transitional.dtd">\n' + '<head>\n' + \
           '<meta http-equiv="Content-Type" content="text/html" ' \
           'charset="' + encoding + '">\n' + '</head>\n' + '<body>\n' \
           + '<h1>' + doc.title().split(sep='|')[0] + '</h1>'

    text += doc.summary() + '</body>'

    app.logger.info('Preprocessing done')
    return text


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


def save_render_zip_submit(doc, sha256, url, title):
    try:
        create_png_from_html(url, sha256)
    except FileNotFoundError as fileError:
        # can only occur if data was submitted successfully but png or pdf creation failed
        if not app.config["TESTING"]:
            app.logger.error('Internal System Error while creating Screenshot,: ' +
                             fileError.strerror + "\n Maybe check the path, current base path is: " + basePath + ' Background process')
    try:
        create_pdf_from_url(url, sha256)
    except FileNotFoundError as fileError:
        # can only occur if data was submitted successfully but png or pdf creation failed
        if not app.config["TESTING"]:
            app.logger.error('FileNotFoundError while creating pdf: ' +
                             fileError.strerror + '\n Background process')
    try:
        create_html_from_url(doc, sha256, url)
    except FileNotFoundError as fileError:
        # can only occur if data was submitted successfully but png or pdf creation failed
        if not app.config["TESTING"]:
            app.logger.error('FileNotFoundError while creating HTML file: ' +
                             fileError.strerror + '\n Background process')
    origin_stamp_result = submit_add_to_db(url, sha256, title)
    return origin_stamp_result


def create_png_from_html(url, sha256):
    """
    Create png from URL. Returns path to file.

    :param url: url to retrieve
    :param sha256: name of the downloaded png
    :returns: path to the created png """
    app.logger.info('Creating PNG from URL:' + url)
    path = basePath + sha256 + '.png'
    app.logger.info('PNG Path:' + path)
    call(['wkhtmltoimage', '--quality', '20', url, path], stderr=DEVNULL)
    if os.path.isfile(path):
        return
    app.logger.error('Could not create PNG from the: ' + url)
    return


def create_html_from_url(doc, hash, url):
    path = basePath + hash + '.html'
    with open(path, 'w') as file:
        file.write(doc)
    if os.path.isfile(path):
        return
    app.logger.error('Could not create HTML from the: ' + url)
    return


def create_pdf_from_url(url, sha256):
    #:param url: url to retrieve
    # method to write pdf file
    app.logger.info('Creating PDF from URL:' + url)
    path = basePath + sha256 + '.pdf'
    app.logger.info('PDF Path:' + path)
    try:
        pdfkit.from_url(url, path)
    except Exception as e:
        # is needed on on windows, where os.rename can't override existing files.
        if os.path.isfile(path):
            return
        app.logger.error('Could not create PDF from the: ' + url)
        app.logger.error(traceback.format_exc(), e)
    return


def submit_add_to_db(url, sha256, title):
    """
    submit hash to originStamp and store in DB.

    :param url: URL downloaded
    :param title: Title of the document behind the URL
    :param sha256: hash to name file after
    """
    originStampResult = submit(sha256, title)
    app.logger.info(originStampResult.text + 'URL ' + url)
    app.logger.info('Origin Stamp Response:' + originStampResult.text)
    if originStampResult.status_code >= 300:
        app.logger.error('300 Internal System Error. Could not submit hash to originstamp')
        return originStampResult
    elif originStampResult.status_code == 200:
        return originStampResult
    elif "errors" in originStampResult.json():
        app.logger.error('300 Internal System Error. Could not submit hash to originstamp')
        return originStampResult

    return originStampResult


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
