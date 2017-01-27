from subprocess import run, PIPE
from flask import abort, flash, current_app, render_template, request, redirect, url_for, Response
from flask_login import login_required, current_user
from app.main import proxy_util as p_util
from . import main
from .forms import EditProfileForm, EditProfileAdminForm, PostForm, PostEdit, PostVerify, PostFreq, \
    SearchPost, SearchOptions, PostBlock, PostCountry, URL_Status, TimestampForm
from .. import db
from ..models import Permission, Role, User, Post, Regular, Location, Block
from ..decorators import admin_required
from app.main import downloader, verification
from datetime import datetime
from lxml.html.diff import htmldiff
from markupsafe import Markup
import validators
from ..nocache import nocache
from sqlalchemy import or_, and_
import socket
import requests
import json
from random import randint

global selected
log = print


"""@main.route('/', methods=['GET', 'POST'])
def index():
    form = PostForm()
    form_freq = PostFreq()
    global selected
    if current_user.can(Permission.WRITE_ARTICLES) and \
            form.validate_on_submit():

        url_site = form.urlSite.data
        results = downloader.get_url_history(url_site)

        origin_stamp_result = results.originStampResult
        sha256 = results.hashValue
        title = results.webTitle
        if origin_stamp_result is not None:
            date_time_gmt = origin_stamp_result.headers['Date']
            orig_stamp_time = datetime.strptime(date_time_gmt, "%a, %d %b %Y %H:%M:%S %Z")
        else:
            orig_stamp_time = datetime.utcnow()

        already_exist = Post.query.filter(and_(Post.urlSite.like(url_site),
                                               Post.hashVal.like(sha256))).first()
        if already_exist is not None:
            flash('The URL was already submitted and the content of the website has not changed since!')
            post_old = Post.query.get_or_404(already_exist.id)
            return render_template('post.html', posts=[post_old], single=True)
        else:
            post_new = Post(body=form.body.data, urlSite=url_site, hashVal=sha256, webTitl=title,
                            origStampTime=orig_stamp_time, author=current_user._get_current_object())
            db.session.add(post_new)
            db.session.commit()
            log(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " New Post added")
            flash('A new time-stamp has been created. Scroll down to view it.')
        return redirect(url_for('.index'))
    elif current_user.can(Permission.WRITE_ARTICLES) and \
            form_freq.validate_on_submit() and form_freq.frequency.data > 0:
        url_site = form_freq.url.data
        freq = form_freq.frequency.data
        email = form_freq.email.data
        results = downloader.get_url_history(url_site)
        origin_stamp_result = results.originStampResult
        sha256 = results.hashValue
        title = results.webTitle
        if origin_stamp_result is not None:
            date_time_gmt = origin_stamp_result.headers['Date']
            orig_stamp_time = datetime.strptime(date_time_gmt, "%a, %d %b %Y %H:%M:%S %Z")
        else:
            orig_stamp_time = datetime.now()

        already_exist = Post.query.filter(and_(Post.urlSite.like(url_site),
                                               Post.hashVal.like(sha256))).first()
        if already_exist is not None:
            post_new = already_exist
        else:
            post_new = Post(body=form_freq.body.data, urlSite=url_site, hashVal=sha256, webTitl=title,
                            origStampTime=orig_stamp_time, author=current_user._get_current_object())
            db.session.add(post_new)
            db.session.commit()
            log(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " New Post added")
        # = Post.query.filter(and_(Post.url_site.like(url_site),
        # Post.hashVal.like(sha256))).first()
        regular_new = Regular(frequency=freq, postID=post_new, email=email)
        db.session.add(regular_new)
        db.session.commit()
        log(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " New Regular task added")
        flash('A new regular has been added task added. '
              'In case of change in the provided URL a new time-stamp would be created.')
        page = request.args.get('page', 1, type=int)
        pagination = Regular.query.order_by(Regular.timestamp.desc()).paginate(
            page, per_page=current_app.config['STW_POSTS_PER_PAGE'], error_out=False)
        posts = pagination.items
        return render_template('regular.html', form=form_freq, posts=posts, pagination=pagination)

    else:
        domain_name = downloader.get_all_domain_names(Post)
        domain_name_unique = set(domain_name)
        for name in domain_name_unique:
            if ';' not in name:
                count = domain_name.count(name)
                domain_name_unique.remove(name)
                domain_name_unique.add(name + ';' + str(count))

        page = request.args.get('page', 1, type=int)
        pagination = Post.query.order_by(Post.timestamp.desc()).paginate(
            page, per_page=current_app.config['STW_POSTS_PER_PAGE'], error_out=False)
        posts = pagination.items
        # In case user is not comparing articles anymore
        if 'selected' in globals():
            if selected is not None:
                selected = None
        return render_template('index.html', form=form, posts=posts, pagination=pagination,
                               doman_name=domain_name_unique, formFreq=form_freq, home_page="active")"""


@main.route('/', methods=['GET', 'POST'])
def index():
    """
    Refactored version of the website entry point using DownloadThread class for processing. Handles posts to regular
    form and posts to standard form.

    :return: Renders template to present to the user.
    """
    form = PostForm()
    form_freq = PostFreq()
    ts_form = TimestampForm()
    global selected
    if current_user.can(Permission.WRITE_ARTICLES) and \
            form.validate_on_submit():

        url_site = form.urlSite.data
        results = downloader.get_url_hist(url_site, user=current_user)
        if results.originStampResult is not None:
            flash('At {} new time-stamp has been created. Scroll down to view it.'
                  .format(results.originStampResult["created_at"]))
        else:
            flash('An error occurred. please try once more')
        return redirect(url_for('.index'))
    elif current_user.can(Permission.WRITE_ARTICLES) and \
            form_freq.validate_on_submit() and form_freq.frequency.data > 0:
        url_site = form_freq.url.data
        freq = form_freq.frequency.data
        email = form_freq.email.data
        results = downloader.get_url_hist(url_site)
        post_new = Post.query.filter(and_(Post.urlSite.like(url_site),
                                          Post.hashVal.like(results.hashValue))).first()
        regular_new = Regular(frequency=freq, postID=post_new, email=email)
        db.session.add(regular_new)
        db.session.commit()
        log(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " New Regular task added")
        flash('A new regular task added. In case of changes in the provided URL a new time-stamp will be created.')
        page = request.args.get('page', 1, type=int)
        pagination = Regular.query.order_by(Regular.timestamp.desc()).paginate(
            page, per_page=current_app.config['STW_POSTS_PER_PAGE'], error_out=False)
        posts = pagination.items
        return render_template('regular.html', form=form_freq, posts=posts, pagination=pagination)

    elif current_user.can(Permission.WRITE_ARTICLES) and \
            ts_form.validate_on_submit():

        # Location Independent Timestamp was triggered hand over to form to the outsourced handling mathod
        return lit(ts_form)
    else:
        template, form, posts, pagination, domain_name_unique = _render_standard_timestamp_post('index.html', form,
                                                                                                False)
        return render_template(template, form=form, posts=posts, pagination=pagination,
                               doman_name=domain_name_unique, formFreq=form_freq, tsForm=ts_form, home_page="active")


@main.route('/compare', methods=['GET', 'POST'])
def compare():
    form = PostVerify()
    global selected
    if current_user.can(Permission.WRITE_ARTICLES) and \
            form.validate_on_submit():
        search_keyword = form.urlSite.data
        if not validators.url(search_keyword):
            domain = search_keyword
            search_keyword = '%' + search_keyword + '%'
            posts = Post.query.filter(or_(Post.urlSite.like(search_keyword),
                                          Post.webTitl.like(search_keyword), Post.body.like(search_keyword)))

            verification.writePostsData(posts)
            page = request.args.get('page', 1, type=int)
            pagination = posts.order_by(Post.timestamp.desc()).filter(Post.urlSite is not None).paginate(
                page, per_page=current_app.config['STW_POSTS_PER_PAGE'], error_out=False)
            posts = pagination.items
            return render_template('search_domains.html', verify=posts,
                                   pagination=pagination, domain=domain, search=True)
        elif validators.url(search_keyword):
            posts = Post.query.filter(Post.urlSite.contains(search_keyword))
            verification.writePostsData(posts)
            page = request.args.get('page', 1, type=int)
            pagination = posts.order_by(Post.timestamp.desc()).filter(Post.urlSite is not None).paginate(
                page, per_page=current_app.config['STW_POSTS_PER_PAGE'],
                error_out=False)
            posts = pagination.items
            return render_template('search_domains.html', verify=posts,
                                   pagination=pagination, search=True, domain=search_keyword)
    domain_name_unique = []
    # Getting Domains user visited
    if not current_user.is_anonymous:
        domain_name = downloader.get_all_domain_names(Post)
        domain_name_unique = set(domain_name)
        for name in domain_name_unique:
            if ';' not in name:
                count = domain_name.count(name)
                domain_name_unique.remove(name)
                domain_name_unique.add(name + ';' + str(count))
    page = request.args.get('page', 1, type=int)
    pagination = Post.query.order_by(Post.timestamp.desc()).filter(Post.urlSite is not None).paginate(
        page, per_page=current_app.config['STW_POSTS_PER_PAGE'],
        error_out=False)
    verify = pagination.items
    # In case user is not comparing articles anymore
    if 'selected' in globals():
        if selected is not None:
            selected = None
    return render_template('verify.html', form=form, verify=verify,
                           pagination=pagination, doman_name=domain_name_unique, comp_page="active")


@main.route('/compare_options/<ids>', methods=['GET', 'POST'])
def compare_options(ids):
    form = SearchPost()
    form_choice = SearchOptions()
    a_split = ids.split(':')
    post_1 = Post.query.get_or_404(a_split[0])
    search_keyword = a_split[1]
    if current_user.can(Permission.WRITE_ARTICLES) and \
            form.validate_on_submit():
        search_keyword = form.urlSite.data

        if not validators.url(search_keyword):
            domain = search_keyword
            search_keyword = '%' + search_keyword + '%'
            posts = Post.query.filter(or_(Post.urlSite.like(search_keyword),
                                          Post.webTitl.like(search_keyword), Post.body.like(search_keyword)))

            page = request.args.get('page', 1, type=int)
            pagination = posts.order_by(Post.timestamp.desc()).filter(Post.urlSite is not None).paginate(
                page, per_page=current_app.config['STW_POSTS_PER_PAGE'],
                error_out=False)
            posts = pagination.items
            return render_template('search_options.html', verify=posts, form=form, form_choice=form_choice,
                                   pagination=pagination, last_post=post_1, domain=domain, last=str(post_1.id))

        elif validators.url(search_keyword):
            posts = Post.query.filter(Post.urlSite.contains(search_keyword))
            verification.writePostsData(posts)
            page = request.args.get('page', 1, type=int)
            pagination = posts.order_by(Post.timestamp.desc()).filter(Post.urlSite is not None).paginate(
                page, per_page=current_app.config['STW_POSTS_PER_PAGE'],
                error_out=False)
            posts = pagination.items
            return render_template('search_options.html', verify=posts,
                                   pagination=pagination, last_post=post_1, form=form, form_choice=form_choice,
                                   last=str(post_1.id))

    elif current_user.can(Permission.WRITE_ARTICLES) and \
            form_choice.validate_on_submit():
        china = True if form_choice.choice_switcher.data == 'china' else False
        usa = True if form_choice.choice_switcher.data == 'usa' else False
        uk = True if form_choice.choice_switcher.data == 'uk' else False
        russia = True if form_choice.choice_switcher.data == 'russia' else False
        hash_2, text_2 = downloader.get_text_from_other_country(china, usa, uk, russia, post_1.urlSite)
        if text_2 is not None:
            text_1 = verification.get_file_text(post_1.hashVal)
            text_left = verification.remove_tags(text_1)
            text_right = verification.remove_tags(text_2)
            text_left = htmldiff(text_left, text_left)
            text_right = htmldiff(text_left, text_right)
            if post_1.hashVal == hash:
                flash('The content at this url has not changed')
            else:
                flash('Change in the content found')

            global selected
            selected = None

            return render_template('very.html', double=True, left=Markup(text_left), dateLeft=post_1.timestamp,
                                   dateRight=datetime.utcnow(), right=Markup(text_right), search=False)
        else:
            text_1 = verification.get_file_text(post_1.hashVal)
            text_left = verification.remove_tags(text_1)
            text_left = htmldiff(text_left, text_left)
            flash('The selected page is blocked in '+form_choice.choice_switcher.data)
            global selected
            selected = None
            return render_template('very.html', double=True, left=Markup(text_left), dateLeft=post_1.timestamp,
                                   dateRight=datetime.utcnow(), search=False)

    if not validators.url(search_keyword):
        domain = search_keyword
        search_keyword = '%' + search_keyword + '%'
        posts = Post.query.filter(or_(Post.urlSite.like(search_keyword),
                                      Post.webTitl.like(search_keyword), Post.body.like(search_keyword)))

        page = request.args.get('page', 1, type=int)
        pagination = posts.order_by(Post.timestamp.desc()).filter(Post.urlSite is not None).paginate(
            page, per_page=current_app.config['STW_POSTS_PER_PAGE'],
            error_out=False)
        posts = pagination.items
        return render_template('search_options.html', verify=posts, form=form, form_choice=form_choice,
                               pagination=pagination, last_post=post_1, domain=domain, last=str(post_1.id))

    elif validators.url(search_keyword):
        posts = Post.query.filter(Post.urlSite.contains(search_keyword))
        verification.writePostsData(posts)
        page = request.args.get('page', 1, type=int)
        pagination = posts.order_by(Post.timestamp.desc()).filter(Post.urlSite is not None).paginate(
            page, per_page=current_app.config['STW_POSTS_PER_PAGE'],
            error_out=False)
        posts = pagination.items
        return render_template('search_options.html', verify=posts,
                               pagination=pagination, last_post=post_1, form=form, form_choice=form_choice,
                               last=str(post_1.id), comp_page="active")


@main.route('/block', methods=['GET', 'POST'])
def block():
    form = PostBlock()
    global selected
    if current_user.can(Permission.WRITE_ARTICLES) and form.validate_on_submit():
        sha256 = None
        date_time_gmt = None
        url_site = form.urlSite.data
        china = True if form.choice_switcher.data == 'china' else False
        usa = True if form.choice_switcher.data == 'usa' else False
        uk = True if form.choice_switcher.data == 'uk' else False
        russia = True if form.choice_switcher.data == 'russia' else False
        results = downloader.get_url_history(url_site)
        originstamp_result = results.originStampResult
        sha256 = results.hashValue
        title = results.webTitle
        if originstamp_result is not None:
            date_time_gmt = originstamp_result.headers['Date']
            originstamp_time = datetime.strptime(date_time_gmt, "%a, %d %b %Y %H:%M:%S %Z")
        else:
            originstamp_time = datetime.now()

        already_exist = Post.query.filter(and_(Post.urlSite.like(url_site),
                                               Post.hashVal.like(sha256))).first()
        if already_exist is not None:
            post_new = already_exist
        else:
            post_new = Post(body=form.body.data, urlSite=url_site, hashVal=sha256, webTitl=title,
                            origStampTime=originstamp_time, author=current_user._get_current_object())
            db.session.add(post_new)
            db.session.commit()

        # check if it is blocked in any country
        hash_2, text_2 = downloader.get_text_from_other_country(china, usa, uk, russia, url_site)

        if text_2 is not None:
            flash("The Article is not blocked in " + form.choice_switcher.data)
            loaded_post = Post.query.get_or_404(post_new.id)
            return render_template('very.html', verify=[loaded_post], single=True, search=False)
        else:

            block_new = Block(china=china, uk=uk, usa=usa, russia=russia, postID=post_new)
            db.session.add(block_new)
            db.session.commit()
            flash("This Article is blocked in "+form.choice_switcher.data)
            return redirect(url_for('.block'))
    page = request.args.get('page', 1, type=int)
    pagination = Block.query.order_by(Block.timestamp.desc()).paginate(
        page, per_page=current_app.config['STW_POSTS_PER_PAGE'], error_out=False)
    posts = pagination.items
    # In case user is not comparing articles anymore
    if 'selected' in globals():
        if selected is not None:
            selected = None
    return render_template('block.html', form=form, posts=posts,
                           pagination=pagination, block_block="active", block_page="active")


@main.route('/statistics')
def statistics():
    global selected
    domain_name = downloader.get_all_domain_names(Post)
    domain_name_unique = set(domain_name)
    counter_stat = {}
    response = None
    for domain in domain_name_unique:
        loc = Location.query.filter_by(ip=domain).first()
        if loc:
            percentage = domain_name.count(domain) / len(domain_name) * 100
            if loc.country_code in counter_stat.keys():
                counter_stat[loc.country_code][1] = counter_stat[loc.country_code][1] + '<br>' + domain + ' (' + \
                                                    str(percentage) + '%)'
                counter_stat[loc.country_code][2] += percentage
            else:
                counter_stat[loc.country_code] = [loc.country_name, domain + ' (' + str(percentage) + '%)', percentage]
        else:
            ip = socket.gethostbyname(domain)
            url = 'http://freegeoip.net/json/' + ip
            try:
                response = requests.get(url)
            except:
                flash("An Error occurred while finding the location of a URL")
            js = response.json()
            percentage = domain_name.count(domain) / len(domain_name) * 100
            if js['country_code'] in counter_stat.keys():
                counter_stat[js['country_code']][1] = counter_stat[js['country_code']][1] + '<br>' + domain + ' (' + \
                                                      str(percentage) + '%)'
                counter_stat[js['country_code']][2] += percentage
            else:
                counter_stat[js['country_code']] = [js['country_name'], domain + ' (' + str(percentage) + '%)',
                                                    percentage]
            location = Location(ip=domain, country_code=js['country_code'], country_name=js['country_name'])
            db.session.add(location)
            db.session.commit()

    data = downloader.remove_unwanted_data()
    for key in counter_stat:
        a = 0
        while a < 210:
            a += 1
            if data["features"][a]["properties"]["Country_Code"] == key and \
               counter_stat[key][0] == data["features"][a]["properties"]["NAME"]:
                data["features"][a]["properties"]["URLS"] = counter_stat[key][1]
                data["features"][a]["properties"]["Percentage"] = counter_stat[key][2]

    json.dump(data, open("app/pdf/stat-data.geo.json", 'w'))
    # In case user is not comparing articles anymore
    if 'selected' in globals():
        if selected is not None:
            selected = None
    return render_template('statistics.html', stat_page="active")


@main.route('/faq')
def faq():
    data = downloader.remove_unwanted_data_regular()
    # Getting locations of our proxies
    ips = list()
    ips.append(current_app.config['CHINA_PROXY'])
    ips.append(current_app.config['USA_PROXY'])
    ips.append(current_app.config['UK_PROXY'])
    ips.append(current_app.config['RUSSIA_PROXY'])
    ips.append("")

    x = 1
    # TODO in proxy_util we have a tool with a db where checking an ip for its location is easy and quick!
    # TODo checkout ip_lookup_country
    for ip in ips:
        loc = Location.query.filter_by(ip=ip).first()
        location = None
        country_code = None
        if loc:
            location = loc.country_name
            country_code = loc.country_code
        else:
            url = 'http://freegeoip.net/json/' + ip
            response = None
            try:
                response = requests.get(url)
            except:
                flash("An Error occur while finding the location of a URL")
            if response:
                js = response.json()
                location = js['country_name'] + ' ' + js['region_name'] + ' ' + js['city']
                country_code = js['country_code']
                location = Location(ip=ip, country_code=js['country_code'], country_name=location)
                db.session.add(location)
                db.session.commit()
        a = 0
        while a < 210:
            a += 1
            if data["features"][a]["properties"]["Country_Code"] == country_code:
                if x == 5:
                    data["features"][a]["properties"]["Location"] = "(Default) " + location

                else:
                    data["features"][a]["properties"]["Location"] = location
                data["features"][a]["properties"]["Location_no"] = x
                x += 1
                break

    json.dump(data, open("app/pdf/country-map.geo.json", 'w'))
    return render_template('faq.html', faq_page="active")


@main.route('/block_country', methods=['GET', 'POST'])
@nocache
def block_country():
    form = URL_Status()
    global selected
    if current_user.can(Permission.WRITE_ARTICLES) and form.validate_on_submit():
        block_list = downloader.search_for_url(form.urlSite.data)
        data = downloader.remove_unwanted_data_block_country()
        for k in block_list:
            a = 0
            while a < 210:
                if data["features"][a]["properties"]["NAME"] == block_list[k][0]:
                    if block_list[k][2] == 200:
                        data["features"][a]["properties"]["Block"] = 2
                        data["features"][a]["properties"]["Block_Status"] = "Not Blocked in this country [200]"
                    elif block_list[k][2] == 404:
                        data["features"][a]["properties"]["Block"] = 1
                        data["features"][a]["properties"]["Block_Status"] = "The URL not found [404]"
                    elif block_list[k][2] == 403:
                        data["features"][a]["properties"]["Block"] = 1
                        data["features"][a]["properties"]["Block_Status"] = "The URL is fobidden in this country [403]"
                    else:
                        data["features"][a]["properties"]["Block"] = 1
                        data["features"][a]["properties"]["Block_Status"] = "The URL is blocked in this country"
                a += 1

        json.dump(data, open("app/pdf/block-data-country.geo.json", 'w'))
        return render_template('block_country.html', block_country="active", block_page="active",
                               form=form, file='block-data-country.geo.json', version=randint(0, 1000),
                               url_site=form.urlSite.data)
    # In case user is not comparing articles anymore
    if 'selected' in globals():
        if selected is not None:
            selected = None
    return render_template('block_country.html', block_country="active", block_page="active",
                           form=form, file='tempelate_block_country.json', version=randint(0, 1000))


@main.route('/compare_country', methods=['GET', 'POST'])
def compare_country():
    form = PostCountry()
    global selected
    if current_user.can(Permission.WRITE_ARTICLES) and form.validate_on_submit():
        freq = form.frequency.data
        sha256 = None
        date_time_gmt = None
        china = True if form.choice_switcher.data == 'china' else False
        usa = True if form.choice_switcher.data == 'usa' else False
        uk = True if form.choice_switcher.data == 'uk' else False
        russia = True if form.choice_switcher.data == 'russia' else False
        url_site = form.urlSite.data
        email = form.email.data
        results = downloader.get_url_history(url_site)
        originstamp_result = results.originStampResult
        sha256 = results.hashValue
        title = results.webTitle
        if originstamp_result is not None:
            date_time_gmt = originstamp_result.headers['Date']
            originstamp_time = datetime.strptime(date_time_gmt, "%a, %d %b %Y %H:%M:%S %Z")
        else:
            originstamp_time = datetime.now()

        already_exist = Post.query.filter(and_(Post.urlSite.like(url_site), Post.hashVal.like(sha256))).first()
        if already_exist is not None:
            post_new = already_exist
        else:
            post_new = Post(body=form.body.data, urlSite=url_site, hashVal=sha256, webTitl=title,
                            origStampTime=originstamp_time, author=current_user._get_current_object())
            db.session.add(post_new)
            db.session.commit()

        regular_new = Regular(frequency=freq, china=china, uk=uk, usa=usa, russia=russia, postID=post_new, email=email)
        db.session.add(regular_new)
        db.session.commit()
        flash('A new Regular Scheduled recurring Time-stamp has been created. '
              'This will compare the changes in the content of the provided URL with the selected country.')
        return redirect(url_for('.compare_country'))
    page = request.args.get('page', 1, type=int)
    pagination = Regular.query.order_by(Regular.timestamp.desc()).paginate(
        page, per_page=current_app.config['STW_POSTS_PER_PAGE'], error_out=False)
    posts = pagination.items

    # In case user is not comparing articles anymore
    if 'selected' in globals():
        if selected is not None:
            selected = None
    return render_template('compare_country.html', form=form, posts=posts,
                           pagination=pagination, reg_sch="active", regular="active")


@main.route('/regular', methods=['GET', 'POST'])
def regular():
    form_freq = PostFreq()
    global selected
    if current_user.can(Permission.WRITE_ARTICLES) and form_freq.validate_on_submit():
        sha256 = None
        date_time_gmt = None
        url_site = form_freq.url.data
        freq = form_freq.frequency.data
        email = form_freq.email.data
        results = downloader.get_url_history(url_site)
        originstamp_result = results.originStampResult
        sha256 = results.hashValue
        title = results.webTitle
        if originstamp_result is not None:
            date_time_gmt = originstamp_result.headers['Date']
            originstamp_time = datetime.strptime(date_time_gmt, "%a, %d %b %Y %H:%M:%S %Z")
        else:
            originstamp_time = datetime.now()

        already_exist = Post.query.filter(and_(Post.urlSite.like(url_site),
                                               Post.hashVal.like(sha256))).first()
        if already_exist is not None:
            post_new = already_exist
        else:
            post_new = Post(body=form_freq.body.data, urlSite=url_site, hashVal=sha256, webTitl=title,
                            origStampTime=originstamp_time, author=current_user._get_current_object())
            db.session.add(post_new)
            db.session.commit()
        regular_new = Regular(frequency=freq, postID=post_new, email=email)
        db.session.add(regular_new)
        db.session.commit()
        flash('A new Regular Scheduled recurring Time-stamp has been created')
        return redirect(url_for('.regular'))
    page = request.args.get('page', 1, type=int)
    pagination = Regular.query.order_by(Regular.timestamp.desc()).paginate(
        page, per_page=current_app.config['STW_POSTS_PER_PAGE'],
        error_out=False)

    # TODO
    """TODO write appropriate query to get records for current user
    pagination = Regular.query.filter_by(Regular.post_id.author_id == current_user).paginate(
        page, per_page=current_app.config['STW_POSTS_PER_PAGE'],
        error_out=False)"""
    posts = pagination.items
    # In case user is not comparing articles anymore
    if 'selected' in globals():
        if selected is not None:
            selected = None
    return render_template('regular.html', form=form_freq, posts=posts,
                           pagination=pagination, reg_page="active", regular="active")


@main.route('/user/<username>')
def user(username):
    the_user = User.query.filter_by(username=username).first_or_404()
    page = request.args.get('page', 1, type=int)
    pagination = the_user.posts.order_by(Post.timestamp.desc()).paginate(
        page, per_page=current_app.config['STW_POSTS_PER_PAGE'],
        error_out=False)
    posts = pagination.items
    return render_template('user.html', user=the_user, posts=posts,
                           pagination=pagination)


@main.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm()
    if form.validate_on_submit():
        current_user.name = form.name.data
        current_user.location = form.location.data
        current_user.about_me = form.about_me.data
        db.session.add(current_user)
        flash('Your profile has been updated.')
        return redirect(url_for('.user', username=current_user.username))
    form.name.data = current_user.name
    form.location.data = current_user.location
    form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', form=form)


@main.route('/edit-profile/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_profile_admin(id):
    users = User.query.get_or_404(id)
    form = EditProfileAdminForm(user=users)
    if form.validate_on_submit():
        users.email = form.email.data
        users.username = form.username.data
        users.confirmed = form.confirmed.data
        users.role = Role.query.get(form.role.data)
        users.name = form.name.data
        users.location = form.location.data
        users.about_me = form.about_me.data
        db.session.add(users)
        flash('The profile has been updated.')
        return redirect(url_for('.user', username=users.username))
    form.email.data = users.email
    form.username.data = users.username
    form.confirmed.data = users.confirmed
    form.role.data = users.role_id
    form.name.data = users.name
    form.location.data = users.location
    form.about_me.data = users.about_me
    return render_template('edit_profile.html', form=form, user=users)


@main.route('/check_selected', methods=['GET', 'POST'])
def check_selected():
    global selected
    posts = request.args.get('post', 0, type=int)
    if 'selected' in globals():
        if selected is not None:
            result = str(selected) + ':' + str(posts)
            selected = None
            return json.dumps({'result': result})
        else:
            selected = posts
            return json.dumps({'result': str(posts)})
    else:
        selected = posts
        return json.dumps({'result': str(posts)})


@main.route('/post/<int:id>')
def post(id):
    posts = Post.query.get_or_404(id)
    return render_template('post.html', posts=[posts], single=True)


@main.route('/very/<int:id>')
def very(id):
    posts = Post.query.get_or_404(id)
    return render_template('post.html', posts=[posts], single=True)


@main.route('/comp/<int:id>')
def comp(id):
    posts = Post.query.get_or_404(id)
    return render_template('post.html', posts=[posts], single=True)


@main.route('/verifyID/<int:id>', methods=['GET', 'POST'])
@login_required
def verifyID(id):
    posts = Post.query.get_or_404(id)
    result_verify = verification.get_url_history(posts.urlSite)
    text_previous = verification.get_file_text(posts.hashVal)
    text_left = verification.remove_tags(text_previous)
    text_right = verification.remove_tags(result_verify.html_text)
    text_left = htmldiff(text_left, text_left)
    text_right = htmldiff(text_left, text_right)
    if result_verify.hashValue == posts.hashVal:
        flash('The content at this url has not changed.')
    else:
        flash('Change in the content found')

    global selected
    selected = None

    return render_template('very.html', double=True, left=Markup(text_left), dateLeft=posts.timestamp,
                           dateRight=datetime.now(),
                           right=Markup(text_right), search=False, comp_page="active", hash2=result_verify.hashValue,
                           hash1=posts.hashVal)


@main.route('/verify_two/<ids>', methods=['GET', 'POST'])
@login_required
def verify_two(ids):
    a_split = ids.split(':')
    post_1 = Post.query.get_or_404(a_split[0])
    post_2 = Post.query.get_or_404(a_split[1])
    # result_verify_1 = verification.get_url_history(post_1.url)
    text_1 = verification.get_file_text(post_1.hashVal)
    text_2 = verification.get_file_text(post_2.hashVal)
    text_left = verification.remove_tags(text_1)
    text_right = verification.remove_tags(text_2)
    text_left = htmldiff(text_left, text_left)
    text_right = htmldiff(text_left, text_right)
    if post_1.hashVal == post_2.hashVal:
        flash('The content at this url has not changed')
    else:
        flash('Change in the content found')
    global selected
    selected = None

    return render_template('very.html', double=True, left=Markup(text_left), dateLeft=post_1.timestamp,
                           hash2=post_2.hashVal,
                           dateRight=post_2.timestamp, right=Markup(text_right), search=False, comp_page="active",
                           hash1=post_1.hashVal)


@main.route('/verifyDomain/<domain>', methods=['GET', 'POST'])
@login_required
@nocache
def verify_domain(domain):
    global selected
    posts = Post.query.filter(Post.urlSite.contains(domain))
    verification.writePostsData(posts)
    page = request.args.get('page', 1, type=int)
    pagination = posts.order_by(Post.timestamp.desc()).filter(Post.urlSite is not None).paginate(
        page, per_page=current_app.config['STW_POSTS_PER_PAGE'],
        error_out=False)
    posts = pagination.items
    # In case user is not comparing articles anymore
    if 'selected' in globals():
        if selected is not None:
            selected = None
    return render_template('search_domains.html', verify=posts,
                           pagination=pagination, domain=domain, comp_page="active")


@main.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    posts = Post.query.get_or_404(id)
    if current_user != posts.author and \
            not current_user.can(Permission.ADMINISTER):
        abort(403)
    form = PostEdit()
    if form.validate_on_submit():
        posts.body = form.body.data
        db.session.add(posts)
        flash('The post has been updated.')
        return redirect(url_for('.post', id=posts.id))
    form.body.data = posts.body
    return render_template('edit_post.html', form=form)


@main.route('/timestamp', methods=['POST', 'GET'])
def timestamp_api():
    """
    Listens for POST queries done by the Stamp The Web WebExtension and starts a distributed timestamp.

    :author: Sebastian
    :return: Whether the POST request was successful or not.
    If successful it will contain a link to the data.
    """
    submitted = False
    form = TimestampForm()
    if form.validate_on_submit():
        log(type(current_user))
        log(current_user)
        country = form.countries.data
        proxy = None
        if country != "none":
            proxy = p_util.get_one_proxy(country)
        else:
            country = None
        downloader.distributed_timestamp(form.urlSiteT.data, user=current_user.username,
                                         proxies=[[country, proxy]])
        submitted = True

    if request.method == 'POST' and not submitted:
        header = request.headers
        log("Received a POST request with following Header: \n" + str(request.headers))
        log("received Post \n" + str(request.headers))
        # change app config to testing in order to disable flashes or messages.
        testing = current_app.config["TESTING"]
        current_app.config["TESTING"] = True
        response = Response()
        response.content_type = 'application/json'
        if header['content-type'] == 'application/json':
            log("The data is of json format")
            try:
                submitting_user = None
                post_data = request.get_json()
                if "user" in post_data:
                    submitting_user = post_data["user"]
                log("The data that was posted: \n" + str(post_data.keys()))
                url = post_data["URL"]
                log("Starting distributed timestamp by extension call")
                log("starting dist timestamp with the following data:URL: {}\nHTML:\n{}"
                    .format(url, type(post_data["body"])))

                result = downloader.distributed_timestamp(url, post_data["body"], user=submitting_user)
                originstamp_result = result.originStampResult
                if result is None:
                    response.status_code = 404
                elif result.original is None:
                    # users input is the original data of the website, return the originstamp result
                    response.response = originstamp_result

                else:
                    # users input is not the original data of the website, return the originstamp result
                    resp_data = dict()
                    resp_data["Original_data"] = originstamp_result
                    resp_data["Your_Submitted_data"] = result.user_input.originstamp_result
                    response.response = resp_data
                    response.headers["UserHashValue"] = result.user_input.ipfs_hash
                log("Result of distributed_timestamp:\n" + str(result.originStampResult))

                response.status_code = 200
                response.headers["URL"] = "http://stamptheweb.org/timestamp/{}".format(result.hashValue)
                response.headers["HashValue"] = result.hashValue
                if post_data["user"]:
                    response.headers["user"] = submitting_user
                else:
                    response.headers["user"] = "BOT"

            except Exception as e:
                # DO NOT  YET! Catch error and continue, but log the error
                current_app.logger.error("An exception was thrown on a POST request: \n" + str(e.__str__()) + "\n" +
                                         str(e.__traceback__) + "\n\n Response so far was " + str(response))
                response.status_code = 481
                response.reason = "Error in try catch block!"

            finally:
                log("cleaning up and returning response")
                current_app.config["TESTING"] = testing
                return response
        else:
            response.status_code = 415
            response.reason = "Unsupported Media Type. Only JSON Format allowed!"
    else:
        # on GET requests

        domain_name = downloader.get_all_domain_names(Post)
        domain_name_unique = set(domain_name)
        for name in domain_name_unique:
            if ';' not in name:
                count = domain_name.count(name)
                domain_name_unique.remove(name)
                domain_name_unique.add(name + ';' + str(count))

        page = request.args.get('page', 1, type=int)
        pagination = Post.query.order_by(Post.timestamp.desc()).paginate(
            page, per_page=current_app.config['STW_POSTS_PER_PAGE'], error_out=False)
        posts = pagination.items
        return render_template('timestamp.html', form=form, posts=posts, pagination=pagination,
                               doman_name=domain_name_unique, home_page="active")


@main.route('/litimestamp', methods=['GET', 'POST'])
@login_required
def loc_indep_timestamp():
    """
    Get the data that was timestamped identified by the given timestamping hash.

    :author: Sebastian
    :return: The Data that was timestamped.
    """
    form = TimestampForm()
    if form.validate_on_submit():
        start_time = datetime.now()
        country = form.countries.data
        url = form.urlSiteT.data
        robot = form.robot.data
        link = form.link.data

        log("The user {} wants to timestamp the url: {}".format(current_user, url))
        if link:
            template = _timestamp_links(form, country, url, robot)
            log("Execution time was: {}".format(datetime.now() - start_time))
            return template
        if country != "none":
            log("The selected country is: {}".format(country))
            location, proxy = p_util.get_one_proxy(country)

            threads, orig_thread, error_threads = downloader.\
                location_independent_timestamp(url, [[location, proxy]], robot, user=current_user)
        else:
            threads, orig_thread, error_threads = downloader.\
                location_independent_timestamp(url, robot_check=robot, user=current_user)

        flash("Finished location independent timestamp!")
        log("Finished location independent timestamp with {} error threads:{}".format(str(threads), str(error_threads)))
        country_list = p_util.get_country_list()

        # Store all countries that were unretrievable, if all were retrievable set error_countries to None
        error_countries = [loc[0] for loc in country_list if loc[1] in [thread.prox_loc for thread in error_threads]]
        if len(error_countries) == 0:
            error_countries = None
        ret_countries = dict()
        # DO we have an original or not
        if orig_thread in error_threads:
            original_post = None
            orig_country = None
        else:
            original_post = Post.query.filter(Post.hashVal == orig_thread.ipfs_hash).first()
            log("Got the original post:{}, threads is {}.".format(original_post.hashVal, type(threads)))
            orig_country = [co[0] for co in country_list if co[1] == orig_thread.prox_loc][0]
            threads.remove(orig_thread)

        # sort all posts to their hashs
        ret_countries = _prepare_return_country_dict(threads, country_list, ret_countries)

        template, form, posts, pagination, domain_name_unique = _render_standard_timestamp_post('timestamp_result.html',
                                                                                                form, render=False)
        log("Start rendering with ret_countries {}".format(ret_countries))
        for key in ret_countries:
            log("Start rendering with ret_countries hash {} and countries {}"
                .format(key, ret_countries[key].countries))
        log("Execution time was: {}".format(datetime.now() - start_time))
        return render_template(template, form=form, posts=posts, pagination=pagination, doman_name=domain_name_unique,
                               return_countries=ret_countries, home_page="active", original_post=original_post,
                               error_countries=error_countries, original_country=orig_country)

    return _render_standard_timestamp_post('timestamp.html', form)


def lit(form):
    """
    Outsourced method called by the index function if a Location Independent Timestamp was triggered.

    :author: Sebastian
    :param form: Timestamp form with all the user input data.
    :return: Render the results of the Location Independent Timestamp.
    """
    start_time = datetime.now()
    country = form.countries.data
    url = form.urlSiteT.data
    robot = form.robot.data
    link = form.link.data

    log("The user {} wants to timestamp the url: {}".format(current_user, url))
    if link:
        template = _timestamp_links(form, country, url, robot)
        log("Execution time was: {}".format(datetime.now() - start_time))
        return template
    if country != "none":
        log("The selected country is: {}".format(country))
        location, proxy = p_util.get_one_proxy(country)

        threads, orig_thread, error_threads = downloader. \
            location_independent_timestamp(url, [[location, proxy]], robot, user=current_user)
    else:
        threads, orig_thread, error_threads = downloader. \
            location_independent_timestamp(url, robot_check=robot, user=current_user)

    flash("Finished location independent timestamp!")
    log("Finished location independent timestamp with {} error threads:{}".format(str(threads), str(error_threads)))
    country_list = p_util.get_country_list()

    # Store all countries that were unretrievable, if all were retrievable set error_countries to None
    error_countries = [loc[0] for loc in country_list if loc[1] in [thread.prox_loc for thread in error_threads]]
    if len(error_countries) == 0:
        error_countries = None
    ret_countries = dict()
    # DO we have an original or not
    if orig_thread in error_threads:
        original_post = None
        orig_country = None
    else:
        original_post = Post.query.filter(Post.hashVal == orig_thread.ipfs_hash).first()
        log("Got the original post:{}, threads is {}.".format(original_post.hashVal, type(threads)))
        orig_country = [co[0] for co in country_list if co[1] == orig_thread.prox_loc][0]
        if orig_thread in threads:
            threads.remove(orig_thread)

    # sort all posts to their hashs
    ret_countries = _prepare_return_country_dict(threads, country_list, ret_countries)

    template, form, posts, pagination, domain_name_unique = _render_standard_timestamp_post('timestamp_result.html',
                                                                                            form, render=False)
    log("Start rendering with ret_countries {}".format(ret_countries))
    for key in ret_countries:
        log("Start rendering with ret_countries hash {} and countries {}"
            .format(key, ret_countries[key].countries))
    log("Execution time was: {}".format(datetime.now() - start_time))
    return render_template(template, form=form, posts=posts, pagination=pagination, doman_name=domain_name_unique,
                           return_countries=ret_countries, home_page="active", original_post=original_post,
                           error_countries=error_countries, original_country=orig_country)


def _timestamp_links(form, country, url, robot):
    """
    Called if the user chooses to include all links in the location independent timestamp(LIT).

    :author: Sebastian
    :param form: The form submitted by the user.
    :param country: The country the user wishes to produce a timestamp for.
    :param url: The URL to timestamp.
    :param robot: Whether or not to adhere to robots.txt.
    :return: Renders a special template to present the results of the LIT with links.
    """
    if country != "none":
        log("Country is set to: {}".format(country))
        location, proxy = p_util.get_one_proxy(country)

        joined_threads, submit_thread_dict = downloader.\
            location_independent_timestamp(url, [[location, proxy]], robot, user=current_user, links=True)
    else:
        joined_threads, submit_thread_dict = downloader. \
            location_independent_timestamp(url, robot_check=robot, user=current_user, links=True)

    log("Finished location independent timestamp with:\n   Base threads {}\n   thread_dict: {}\n   error threads:{}"
        .format(str(joined_threads), str(submit_thread_dict), str(submit_thread_dict["error_threads"])))
    template, form, posts, pagination, domain_name_unique = _render_standard_timestamp_post('result_links.html',
                                                                                            form, render=False)
    log("Before rewrite the Thread dict looks like {}".format(submit_thread_dict))
    # rewrite the submit_thread_dict to consist of posts instead od threads
    _rewrite_thread_dict(submit_thread_dict)

    log("After rewrite the Thread dict looks like {}".format(submit_thread_dict))

    return render_template(template, form=form, posts=posts, pagination=pagination, doman_name=domain_name_unique,
                           thread_dict=submit_thread_dict, home_page="active")


@main.route('/timestamp/<timestamp>', methods=['GET'])
def timestamp_get(timestamp):
    """
    Get the data that was timestamped, identified by the given timestamping hash.

    :author: Sebastian
    :param timestamp: A timestamp hash.
    :return: The Data that was timestamped.
    """
    if timestamp.isalnum():
        # downloader.get_hash_history(timestamp)
        post_old = Post.query.filter_by(hashVal=timestamp).first()
        print("Trying to get {}: {}".format(timestamp, str(post_old)))
        if post_old is None:
            return render_template('404.html')
        return render_template('post.html', posts=[post_old], single=True)
    else:
        response = requests.Response()
        response.status_code = 415
        response.reason = "415 Unsupported Data Type. Timestamps are alphanumeric!"
        return response


@main.route('/get_new_proxies', methods=['GET'])
@login_required
def get_new_proxies():
    """
    Initiate a manual proxy update.

    :author: Sebastian
    :return: The Data that was timestamped.
    """
    output = run(['python3.5', 'app/main/proxy_util.py'], stdout=PIPE)
    log("This is the output: \n-----------------------------\n".format(output))
    return _render_standard_timestamp_post()


def _render_standard_timestamp_post(template="timestamp.html", form=None, render=True):
    """
    Convenience method to render timestamp posts.

    :author: Sebastian
    :param template: The template to use as basis, given as string.
    :param form: The form to include in the template. Defaults to None and a TimestampForm is used within the method.
    :param render: Whether to render the template directly or to hand back the instantiated variables
    necessary for rendering. Defaults to True.
    :return: Either the rendered template if variable render is set to True (default), or the variables necessary for
    rendering a timestamp template (template, form, posts, pagination and domain_name_unique)
    """
    if form is None:
        form = TimestampForm
    domain_name = downloader.get_all_domain_names(Post)
    domain_name_unique = set(domain_name)
    for name in domain_name_unique:
        if ';' not in name:
            count = domain_name.count(name)
            domain_name_unique.remove(name)
            domain_name_unique.add(name + ';' + str(count))

    page = request.args.get('page', 1, type=int)
    pagination = Post.query.order_by(Post.timestamp.desc()).paginate(
        page, per_page=current_app.config['STW_POSTS_PER_PAGE'], error_out=False)
    posts = pagination.items
    if render:
        return render_template(template, form=form, posts=posts, pagination=pagination,
                               doman_name=domain_name_unique, home_page="active")
    else:
        return template, form, posts, pagination, domain_name_unique


def _rewrite_thread_dict(submit_thread_dict):
    """
    Convenience method specifically used to rewrite the thread dictionary returned by location independent timestamp
    with links. The error_threads part are deleted as error threads are not shown on link timestamp.

    :author: Sebastian
    :param submit_thread_dict: The thread dictionary returned by downloader.location_independent_timestamp.

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
    for hash_value, link_dict in submit_thread_dict.items():
        if hash_value != "error_threads":
            for link, thread_list in link_dict.items():
                post_list = list()
                for thread in thread_list:
                    post_list.append(Post.query.filter_by(hashVal=thread.ipfs_hash).first())
                link_dict[link] = post_list
    submit_thread_dict.pop("error_threads")
    """for link in submit_thread_dict[hash_val]:
        for thread in submit_thread_dict[hash_val][link]:
            if thread.error is None and thread.ipfs_hash is not None:
                submit_thread_dict[hash_val][link][submit_thread_dict[hash_val][link].index(thread)] = \
                    Post.query.filter(Post.hashVal == thread.ipfs_hash).first()"""


def _prepare_return_country_dict(threads, country_list, ret_countries):
    """
    Modifies the dict of ReturnCountries and sorts all countries to the hashes.

    # TODO  Implementation improvements possible: Iterate through country_list only once,
            remove superfluous  resources (hash_country) # done!

    :author: Sebastian
    :param threads: The threads that the timestamp returned.
    :param country_list: The list of country names and their iso abbreviations.
    :param ret_countries: The dict of ReturnCountries to modify.
    """
    for thread in threads:
        if thread.ipfs_hash is not None:
            log(thread.prox_loc)
            if thread.ipfs_hash not in ret_countries.keys():
                db_post = Post.query.filter(Post.hashVal == thread.ipfs_hash).first()
                if db_post is not None:
                    ret_countries[thread.ipfs_hash] = ReturnCountries(db_post, [])
                    log("Retrieved a post for Thread-{}  for {} to add to return_country as {}"
                        .format(thread.threadID, thread.ipfs_hash, ret_countries[thread.ipfs_hash]))
                else:
                    log("Couldn't retrieve a post for {} for Thread-{} from {} to add to return_country"
                        .format(thread.ipfs_hash, thread.threadID, thread.prox_loc))
                    continue
            ret_countries[thread.ipfs_hash].countries += [con[0] for con in country_list if con[1] == thread.prox_loc]
            log("Added to return_countries at {}: {}".format(thread.ipfs_hash, ret_countries))
    log("Finished preparing the return_countries: {}".format(ret_countries))
    return ret_countries


class ReturnCountries:
    def __init__(self, db_post, countries):
        self.countries = countries
        self.post = db_post

    def __repr__(self):
        return "ReturnCountries ID: {} Countries: {} The post: {}".format(id(self), self.countries, self.post)
