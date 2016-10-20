import asyncio
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


@main.route('/', methods=['GET', 'POST'])
def index():
    form = PostForm()
    form_freq = PostFreq()
    global selected
    if current_user.can(Permission.WRITE_ARTICLES) and \
            form.validate_on_submit():
        sha256 = None
        date_time_gmt = None

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
            current_app.logger.info(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " New Post added")
            flash('A new time-stamp has been created. Scroll down to view it.')
        return redirect(url_for('.index'))
    elif current_user.can(Permission.WRITE_ARTICLES) and \
            form_freq.validate_on_submit() and form_freq.frequency.data > 0:
        sha256 = None
        date_time_gmt = None
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
            current_app.logger.info(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " New Post added")
        # = Post.query.filter(and_(Post.url_site.like(url_site),
        # Post.hashVal.like(sha256))).first()
        regular_new = Regular(frequency=freq, postID=post_new, email=email)
        db.session.add(regular_new)
        db.session.commit()
        current_app.logger.info(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " New Regular task added")
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
                               doman_name=domain_name_unique, formFreq=form_freq, home_page="active")


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
        print(type(current_user))
        print(current_user)
        country = form.countries.data
        proxy = None
        if country != "none":
            try:
                p_util.get_one_proxy(country)
            except RuntimeError:
                asyncio.set_event_loop(asyncio.new_event_loop())
                proxy = p_util.get_one_proxy(country)
        result = downloader.distributed_timestamp(form.urlSite.data, user=current_user.username)
        submitted = True

    if request.method == 'POST' and not submitted:
        header = request.headers
        current_app.logger.info("Received a POST request with following Header: \n" + str(request.headers))
        print("received Post \n" + str(request.headers))
        # change app config to testing in order to disable flashes or messages.
        testing = current_app.config["TESTING"]
        current_app.config["TESTING"] = True
        response = Response()
        response.content_type = 'application/json'
        if header['content-type'] == 'application/json':
            print("The data is of json format")
            try:
                submitting_user = None
                post_data = request.get_json()
                if "user" in post_data:
                    submitting_user = post_data["user"]
                current_app.logger.info("The data that was posted: \n" + str(post_data.keys()))
                url = post_data["URL"]
                current_app.logger.info("Starting distributed timestamp by extension call")
                print("starting dist timestamp with the following data:URL: {}\nHTML:\n{}".format(url,
                                                                                                  type(post_data["body"])))

                result = downloader.distributed_timestamp(url, post_data["body"], user=submitting_user)
                # TODO do not store new POST
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
                current_app.logger.info("Result of distributed_timestamp:\n" + str(result.originStampResult))

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
                current_app.logger.info("cleaning up and returning response")
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


@main.route('/litimestamp/', methods=['GET', 'POST'])
def loc_indep_timestamp():
    """
    Get the data that was timestamped identified by the given timestamping hash.

    :author: Sebastian
    :return: The Data that was timestamped.
    """
    form = TimestampForm()
    if form.validate_on_submit():
        country = form.countries.data
        url = form.urlSite.data
        robot = form.robot.data
        link = form.link.data
        current_app.logger.info("The selected country is: {}".format(country))
        current_app.logger.info("Robots.txt?: {}".format(robot))
        current_app.logger.info("The user {} wants to timestamp the url: {}".format(current_user, url))
        if link:
            return timestamp_links(form, country, url, robot)
        if country != "none":
            current_app.logger.info("Country is set to: {}".format(country))
            location, proxy = p_util.get_one_proxy(country)

            threads, orig_thread, error_threads = downloader.\
                location_independent_timestamp(url, [[location, proxy]], robot, user=current_user)
        else:
            threads, orig_thread, error_threads = downloader.\
                location_independent_timestamp(url, robot_check=robot, user=current_user)

        flash("Finished location independent timestamp!")
        current_app.logger.info("Finished location independent timestamp with {} error threads:{}"
                                .format(str(error_threads), str(threads)))

        country_list = p_util.get_country_list()
        error_countries = [loc[0] for loc in country_list if loc[1] in [thread.prox_loc for thread in error_threads]]

        original_post = Post.query.get_or_404(orig_thread.ipfs_hash)
        current_app.logger.info("Got the original post:{}".format(original_post))
        threads = threads.remove(orig_thread)

        # sort all posts to their hashs
        ret_countries = dict()
        ret_countries[orig_thread.ipfs_hash] = ReturnCountries(original_post)
        for thread in threads:
            if thread.ipfs_hash not in ret_countries:
                ret_countries[thread.ipfs_hash] = ReturnCountries(Post.query.get_or_404(thread.ipfs_hash))
            for con in country_list:
                if con[1] == thread.prox_loc:
                    ret_countries[thread.ipfs_hash].countries.append(con[0])
        template, form, posts, pagination, domain_name_unique = render_standard_timestamp_post('timestamp_result.html',
                                                                                               form, render=False)

        return render_template(template, form=form, posts=posts, pagination=pagination, doman_name=domain_name_unique,
                               return_countries=ret_countries, home_page="active", original_post=original_post,
                               error_countries=error_countries)

    return render_standard_timestamp_post('timestamp.html', form)


def timestamp_links(form, country, url, robot):
    if country != "none":
        current_app.logger.info("Country is set to: {}".format(country))
        location, proxy = p_util.get_one_proxy(country)

        threads, orig_thread, error_threads = downloader. \
            location_independent_timestamp(url, [[location, proxy]], robot, user=current_user, links=True)
    else:
        threads, orig_thread, error_threads = downloader. \
            location_independent_timestamp(url, robot_check=robot, user=current_user, links=True)

    flash("Finished location independent timestamp!")
    current_app.logger.info("Finished location independent timestamp with {} error threads:{}"
                            .format(str(error_threads), str(threads)))
    return render_template("result_links",)


@main.route('/timestamp/<timestamp>', methods=['GET'])
def timestamp_get(timestamp):
    """
    Get the data that was timestamped identified by the given timestamping hash.

    :author: Seabstian
    :param timestamp: A timestamp hash.
    :return: The Data that was timestamped.
    """
    if timestamp.isalnum():
        # downloader.get_hash_history(timestamp)
        post_old = Post.query.get_or_404(timestamp)
        return render_template('post.html', posts=[post_old], single=True)
    else:
        response = requests.Response()
        response.status_code = 415
        response.reason = "415 Unsupported Data Type. Timestamps are alphanumeric!"
        return response


@main.route('/get_new_proxies', methods=['GET'])
def get_new_proxies():
    """
    Initiate a proxy update.

    :return: The Data that was timestamped.
    """
    output = run(['python3', 'app/main/proxy_util.py'], stdout=PIPE)
    print("This is the output: \n-----------------------------\n" + output)
    return render_standard_timestamp_post()


def render_standard_timestamp_post(template="timestamp.html", form=None, render=True):
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


class ReturnCountries:
    def __init__(self, db_post, countries=list()):
        self.countries = countries
        self.post = db_post
