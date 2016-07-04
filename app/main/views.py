from flask import render_template, redirect, url_for, abort, flash, request,\
    current_app
from flask_login import login_required, current_user
from . import main
from .forms import EditProfileForm, EditProfileAdminForm, PostForm, PostEdit, PostVerify, PostFreq, \
    SearchPost,SearchOptions,PostBlock, PostCountry
from .. import db
from ..models import Permission, Role, User, Post, Regular, Location, Block
from ..decorators import admin_required
from app.main import downloader,verification
from datetime import datetime
from flask import render_template, request, redirect, url_for
from lxml.html.diff import htmldiff
from markupsafe import Markup
import validators
from ..nocache import nocache
from sqlalchemy import or_, and_
import socket
import requests
import json


global selected


@main.route('/', methods=['GET', 'POST'])
def index():
    form = PostForm()
    form_freq = PostFreq()
    if current_user.can(Permission.WRITE_ARTICLES) and \
            form.validate_on_submit():
        sha256=None
        date_time_gmt=None
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
            flash('The URL was already submitted and the content of the website ahs not changed since!')
            post_old = Post.query.get_or_404(already_exist.id)
            return render_template('post.html', posts=[post_old],single=True)
        else:
            post_new = Post(body=form.body.data, urlSite=url_site, hashVal=sha256, webTitl=title,
                            origStampTime=orig_stamp_time,
                            author=current_user._get_current_object())
            db.session.add(post_new)
            db.session.commit()
        return redirect(url_for('.index'))
    elif current_user.can(Permission.WRITE_ARTICLES) and \
            form_freq.validate_on_submit() and form_freq.frequency.data > 0:
        sha256 = None
        date_time_gmt = None
        url_site = form_freq.urlSite.data
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
                            origStampTime=orig_stamp_time,
                            author=current_user._get_current_object())
            db.session.add(post_new)
            db.session.commit()
        #  = Post.query.filter(and_(Post.url_site.like(url_site),
        # Post.hashVal.like(sha256))).first()
        regular_new = Regular(frequency=freq, postID=post_new,email=email)
        db.session.add(regular_new)
        db.session.commit()
        page = request.args.get('page', 1, type=int)
        pagination = Regular.query.order_by(Regular.timestamp.desc()).paginate(
            page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
            error_out=False)
        posts = pagination.items
        return render_template('regular.html', form=form_freq, posts=posts,
                               pagination=pagination)

    else:
        domain_name = downloader.get_all_domain_names(Post)
        domain_name_unique = set(domain_name)
        for name in domain_name_unique:
            if ';' not in name:
                count = domain_name.count(name)
                domain_name_unique.remove(name)
                domain_name_unique.add(name + ';'+str(count))

        page = request.args.get('page', 1, type=int)
        pagination = Post.query.order_by(Post.timestamp.desc()).paginate(
            page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
            error_out=False)
        posts = pagination.items
        return render_template('index.html', form=form, posts=posts, pagination=pagination,
                               doman_name=domain_name_unique, formFreq=form_freq, home_page="active")


@main.route('/compare', methods=['GET', 'POST'])
def compare():
    form = PostVerify()
    if current_user.can(Permission.WRITE_ARTICLES) and \
            form.validate_on_submit():
        search_keyword = form.urlSite.data
        if not validators.url(search_keyword):
            domain = search_keyword
            search_keyword = '%'+search_keyword+'%'
            posts = Post.query.filter(or_(Post.urlSite.like(search_keyword),
                                          Post.webTitl.like(search_keyword), Post.body.like(search_keyword)))

            verification.writePostsData(posts)
            page = request.args.get('page', 1, type=int)
            pagination = posts.order_by(Post.timestamp.desc()).filter(Post.urlSite is not None).paginate(
                page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
                error_out=False)
            posts = pagination.items
            return render_template('search_domains.html', verify=posts,
                                   pagination=pagination, domain=domain, search=True)
        elif validators.url(search_keyword):
            posts = Post.query.filter(Post.urlSite.contains(search_keyword))
            verification.writePostsData(posts)
            page = request.args.get('page', 1, type=int)
            pagination = posts.order_by(Post.timestamp.desc()).filter(Post.urlSite is not None).paginate(
                page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
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
                domain_name_unique.add(name + ';'+str(count))
    page = request.args.get('page', 1, type=int)
    pagination = Post.query.order_by(Post.timestamp.desc()).filter(Post.urlSite is not None).paginate(
        page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
        error_out=False)
    verify = pagination.items
    return render_template('verify.html', form=form, verify=verify,
                           pagination=pagination,doman_name=domain_name_unique, comp_page="active")


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
            search_keyword = '%'+search_keyword+'%'
            posts = Post.query.filter(or_(Post.urlSite.like(search_keyword),
                                          Post.webTitl.like(search_keyword),Post.body.like(search_keyword)))

            page = request.args.get('page', 1, type=int)
            pagination = posts.order_by(Post.timestamp.desc()).filter(Post.urlSite is not None).paginate(
                page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
                error_out=False)
            posts = pagination.items
            return render_template('search_options.html', verify=posts, form=form, form_choice=form_choice,
                                   pagination=pagination, last_post=post_1, domain=domain, last=str(post_1.id))

        elif validators.url(search_keyword):
            posts = Post.query.filter(Post.urlSite.contains(search_keyword))
            verification.writePostsData(posts)
            page = request.args.get('page', 1, type=int)
            pagination = posts.order_by(Post.timestamp.desc()).filter(Post.urlSite is not None).paginate(
                page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
                error_out=False)
            posts = pagination.items
            return render_template('search_options.html', verify=posts,
                                   pagination=pagination, last_post = post_1,form=form,form_choice=form_choice,
                                   last=str(post_1.id))

    elif current_user.can(Permission.WRITE_ARTICLES) and\
                form_choice.validate_on_submit():
        china = form_choice.china.data
        usa = form_choice.usa.data
        uk = form_choice.uk.data
        hash_2, text_2 = downloader.get_text_from_other_country(china,usa,uk,post_1.urlSite)
        if text_2 is not None:
            text_1 = verification.get_file_text(post_1.hashVal)
            text_left = verification.remove_tags(text_1)
            text_right = verification.remove_tags(text_2)
            text_left = htmldiff(text_left, text_left)
            text_right = htmldiff(text_left, text_right)
            if post_1.hashVal == hash:
                flash('The content in the url is not changed')
            else:
                flash('Change in the content found')

            return render_template('very.html',double=True,left=Markup(text_left),dateLeft = post_1.timestamp,
                                   dateRight = datetime.utcnow(),right=Markup(text_right),search=False)
        else:
            text_1 = verification.get_file_text(post_1.hashVal)
            text_left = verification.remove_tags(text_1)
            text_left = htmldiff(text_left, text_left)
            flash('The selected page is blocked in this country')
            return render_template('very.html',double=True,left=Markup(text_left),dateLeft = post_1.timestamp,
                                   dateRight = datetime.utcnow(),search=False)

    if not validators.url(search_keyword):
        domain = search_keyword
        search_keyword = '%'+search_keyword+'%'
        posts = Post.query.filter(or_(Post.urlSite.like(search_keyword),
                                        Post.webTitl.like(search_keyword), Post.body.like(search_keyword)))


        page = request.args.get('page', 1, type=int)
        pagination = posts.order_by(Post.timestamp.desc()).filter(Post.urlSite != None).paginate(
            page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
            error_out=False)
        posts = pagination.items
        return render_template('search_options.html', verify=posts, form=form, form_choice=form_choice,
                               pagination=pagination,last_post = post_1, domain=domain,last=str(post_1.id))


    elif validators.url(search_keyword):
        posts = Post.query.filter(Post.urlSite.contains(search_keyword))
        verification.writePostsData(posts)
        page = request.args.get('page', 1, type=int)
        pagination = posts.order_by(Post.timestamp.desc()).filter(Post.urlSite != None).paginate(
            page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
            error_out=False)
        posts = pagination.items
        return render_template('search_options.html', verify=posts,
                               pagination=pagination, last_post = post_1,form=form,form_choice=form_choice,
                               last=str(post_1.id), comp_page="active")

@main.route('/block',  methods=['GET', 'POST'])
def block():
    form = PostBlock()
    if current_user.can(Permission.WRITE_ARTICLES) and form.validate_on_submit():
        sha256 = None
        dateTimeGMT=None
        urlSite=form.urlSite.data
        china = form.china.data
        usa = form.usa.data
        uk = form.uk.data
        results = downloader.get_url_history(urlSite)
        originStampResult = results.originStampResult
        sha256 = results.hashValue
        title = results.webTitle
        if originStampResult is not None:
            dateTimeGMT=originStampResult.headers['Date']
            origStampTime=datetime.strptime(dateTimeGMT, "%a, %d %b %Y %H:%M:%S %Z")
        else:
            origStampTime = datetime.now()

        already_exist = Post.query.filter(and_(Post.urlSite.like(urlSite),
                                            Post.hashVal.like(sha256))).first()
        if already_exist is not None:
            post_new = already_exist
        else:
            post_new = Post(body=form.body.data, urlSite=urlSite, hashVal=sha256, webTitl=title,
                            origStampTime=origStampTime,
                            author=current_user._get_current_object())
            db.session.add(post_new)
            db.session.commit()

        #check if it is blocked in any country
        hash_2, text_2 = downloader.get_text_from_other_country(china,usa,uk,urlSite)

        if text_2 is not None:
            flash("The Article is not blocked in this country")
            post = Post.query.get_or_404(post_new.id)
            return render_template('very.html', verify=[post], single=True, search = False)
        else:

            block_new = Block(china=china,uk=uk,usa=usa,postID=post_new)
            db.session.add(block_new)
            db.session.commit()
            flash("This Article is blocked in this country")
            return redirect(url_for('.block'))
    page = request.args.get('page', 1, type=int)
    pagination = Block.query.order_by(Block.timestamp.desc()).paginate(
        page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
        error_out=False)
    posts = pagination.items
    return render_template('block.html', form=form, posts=posts,
                           pagination=pagination, block_page="active")

@main.route('/statistics')
def statistics():
    domain_name = downloader.get_all_domain_names(Post)
    doman_name_unique = set(domain_name)
    countr_stat = {}
    for domain in doman_name_unique:
        loc = Location.query.filter_by(ip=domain).first()
        if loc:
            percentage = domain_name.count(domain)/len(domain_name) * 100
            if loc.country_code in countr_stat.keys():
                countr_stat[loc.country_code][1] = countr_stat[loc.country_code][1] + '<br>'+domain +' (' +str(percentage) +'%)'
                countr_stat[loc.country_code][2] = countr_stat[loc.country_code][2] + percentage
            else:
                countr_stat[loc.country_code]=[loc.country_name, domain +' (' +str(percentage) +'%)', percentage]
        else:
            ip = socket.gethostbyname(domain)
            url = 'http://freegeoip.net/json/' + ip
            try:
                response = requests.get(url)
            except:
                flash("An Error occure while finding the location of a URL")
            js = response.json()
            percentage = domain_name.count(domain)/len(domain_name) * 100
            if js['country_code'] in countr_stat.keys():
                countr_stat[js['country_code']][1] = countr_stat[js['country_code']][1] + '<br>'+domain +' (' +str(percentage) +'%)'
                countr_stat[js['country_code']][2] = countr_stat[js['country_code']][2] + percentage
            else:
                countr_stat[js['country_code']]=[js['country_name'], domain +' (' +str(percentage) +'%)', percentage]
            location = Location(ip=domain, country_code=js['country_code'], country_name=js['country_name'])
            db.session.add(location)
            db.session.commit()

    data = downloader.remove_unwanted_data()
    for key in countr_stat:
        a = 0
        while a < 210:
            a+=1
            if data["features"][a]["properties"]["Country_Code"] == key and countr_stat[key][0] == data["features"][a]["properties"]["NAME"]:
                data["features"][a]["properties"]["URLS"] = countr_stat[key][1]
                data["features"][a]["properties"]["Percentage"] = countr_stat[key][2]

    json.dump(data, open("app/pdf/world-population.geo1.json",'w'))

    return render_template('statistics.html', stat_page="active")

@main.route('/compare_country', methods=['GET', 'POST'])
def compare_country():
    form = PostCountry()
    if current_user.can(Permission.WRITE_ARTICLES) and form.validate_on_submit():
        freq = form.frequency.data
        sha256 = None
        dateTimeGMT=None
        china = form.china.data
        usa = form.usa.data
        uk = form.uk.data
        urlSite=form.urlSite.data
        email = form.email.data
        results = downloader.get_url_history(urlSite)
        originStampResult = results.originStampResult
        sha256 = results.hashValue
        title = results.webTitle
        if originStampResult is not None:
            dateTimeGMT=originStampResult.headers['Date']
            origStampTime=datetime.strptime(dateTimeGMT, "%a, %d %b %Y %H:%M:%S %Z")
        else:
            origStampTime = datetime.now()

        already_exist = Post.query.filter(and_(Post.urlSite.like(urlSite),
                                            Post.hashVal.like(sha256))).first()
        if already_exist is not None:
            post_new = already_exist
        else:
            post_new = Post(body=form.body.data, urlSite=urlSite, hashVal=sha256, webTitl=title,
                            origStampTime=origStampTime,
                            author=current_user._get_current_object())
            db.session.add(post_new)
            db.session.commit()

        regular_new = Regular(frequency=freq,china=china,uk=uk,usa=usa,postID=post_new,email=email)
        db.session.add(regular_new)
        db.session.commit()
        return redirect(url_for('.compare_country'))
    page = request.args.get('page', 1, type=int)
    pagination = Regular.query.order_by(Regular.timestamp.desc()).paginate(
        page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
        error_out=False)
    posts = pagination.items

    data = downloader.remove_unwanted_data_regular()
    #Getting locations of our proxies
    ips = []
    ips.append(current_app.config['CHINA_PROXY'])
    ips.append(current_app.config['USA_PROXY'])
    ips.append(current_app.config['UK_PROXY'])
    ips.append("")

    x=1
    for ip in ips:
        loc = Location.query.filter_by(ip=ip).first()
        locat = None
        country_code=None
        if loc:
            locat = loc.country_name
            country_code=loc.country_code
        else:
            url = 'http://freegeoip.net/json/' + ip
            response=None
            try:
                response = requests.get(url)
            except:
                flash("An Error occur while finding the location of a URL")
            if response:
                js = response.json()
                locat = js['country_name'] +' '+ js['region_name'] +' '+ js['city']
                country_code=js['country_code']
                location = Location(ip=ip, country_code=js['country_code'], country_name=locat)
                db.session.add(location)
                db.session.commit()
        a = 0
        while a < 210:
            a+=1
            if data["features"][a]["properties"]["Country_Code"] == country_code:
                if x == 4:
                    data["features"][a]["properties"]["Location"]= "(Default) "+locat

                else:
                    data["features"][a]["properties"]["Location"]= locat
                data["features"][a]["properties"]["Location_no"]= x
                x+=1
                break


    json.dump(data, open("app/pdf/world-population.geo2.json",'w'))

    return render_template('compare_country.html', form=form, posts=posts,
                           pagination=pagination, reg_sch="active", regular="active")

@main.route('/regular', methods=['GET', 'POST'])
def regular():
    formFreq = PostFreq()
    if current_user.can(Permission.WRITE_ARTICLES) and formFreq.validate_on_submit():
        sha256 = None
        dateTimeGMT=None
        urlSite=formFreq.urlSite.data
        freq = formFreq.frequency.data
        email = formFreq.email.data
        results = downloader.get_url_history(urlSite)
        originStampResult = results.originStampResult
        sha256 = results.hashValue
        title = results.webTitle
        if originStampResult is not None:
            dateTimeGMT=originStampResult.headers['Date']
            origStampTime=datetime.strptime(dateTimeGMT, "%a, %d %b %Y %H:%M:%S %Z")
        else:
            origStampTime = datetime.now()

        already_exist = Post.query.filter(and_(Post.urlSite.like(urlSite),
                                            Post.hashVal.like(sha256))).first()
        if already_exist is not None:
            post_new = already_exist
        else:
            post_new = Post(body=formFreq.body.data, urlSite=urlSite, hashVal=sha256, webTitl=title,
                            origStampTime=origStampTime,
                            author=current_user._get_current_object())
            db.session.add(post_new)
            db.session.commit()
        regular_new = Regular(frequency=freq,postID=post_new,email=email)
        db.session.add(regular_new)
        db.session.commit()
        return redirect(url_for('.regular'))
    page = request.args.get('page', 1, type=int)
    pagination = Regular.query.order_by(Regular.timestamp.desc()).paginate(
        page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
        error_out=False)
    posts = pagination.items
    return render_template('regular.html', form=formFreq, posts=posts,
                           pagination=pagination, reg_page="active", regular="active")

@main.route('/user/<username>')
def user(username):
    user = User.query.filter_by(username=username).first_or_404()
    page = request.args.get('page', 1, type=int)
    pagination = user.posts.order_by(Post.timestamp.desc()).paginate(
        page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
        error_out=False)
    posts = pagination.items
    return render_template('user.html', user=user, posts=posts,
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
    user = User.query.get_or_404(id)
    form = EditProfileAdminForm(user=user)
    if form.validate_on_submit():
        user.email = form.email.data
        user.username = form.username.data
        user.confirmed = form.confirmed.data
        user.role = Role.query.get(form.role.data)
        user.name = form.name.data
        user.location = form.location.data
        user.about_me = form.about_me.data
        db.session.add(user)
        flash('The profile has been updated.')
        return redirect(url_for('.user', username=user.username))
    form.email.data = user.email
    form.username.data = user.username
    form.confirmed.data = user.confirmed
    form.role.data = user.role_id
    form.name.data = user.name
    form.location.data = user.location
    form.about_me.data = user.about_me
    return render_template('edit_profile.html', form=form, user=user)


@main.route('/check_selected', methods=['GET','POST'])
def check_selected():
    global selected
    post = request.args.get('post', 0, type=int)
    if 'selected' in globals():
        if selected is not None:
            result = str(selected)+':'+str(post)
            selected = None
            return json.dumps({'result': result});
        else:
            selected = post
            return json.dumps({'result': str(post)});
    else:
        selected = post
        return json.dumps({'result': str(post)});

@main.route('/post/<int:id>')
def post(id):
    post = Post.query.get_or_404(id)
    return render_template('post.html', posts=[post], single=True)
@main.route('/very/<int:id>')
def very(id):
    very = Post.query.get_or_404(id)
    return render_template('very.html', verify=[very], single=True,search = False)
@main.route('/comp/<int:id>')
def comp(id):
    comp = Post.query.get_or_404(id)
    return render_template('comp.html', verify=[comp],single=True,search = False)

@main.route('/verifyID/<int:id>', methods=['GET', 'POST'])
@login_required
def verifyID(id):
    post = Post.query.get_or_404(id)
    result_verify = verification.get_url_history(post.urlSite)
    text_previous = verification.get_file_text(post.hashVal)
    text_left = verification.remove_tags(text_previous)
    text_right = verification.remove_tags(result_verify.html_text)
    text_left = htmldiff(text_left, text_left)
    text_right = htmldiff(text_left, text_right)
    if result_verify.hashValue == post.hashVal:
        flash('The content in the url is not changed')
    else:
        flash('Change in the content found')

    return render_template('very.html',double=True,left=Markup(text_left),dateLeft = post.timestamp,
                           dateRight=datetime.now(), right=Markup(text_right), search=False, comp_page="active")

@main.route('/verify_two/<ids>', methods=['GET', 'POST'])
@login_required
def verify_two(ids):
    a_split = ids.split(':')
    post_1 = Post.query.get_or_404(a_split[0])
    post_2 = Post.query.get_or_404(a_split[1])
    #result_verify_1 = verification.get_url_history(post_1.urlSite)
    text_1 = verification.get_file_text(post_1.hashVal)
    text_2 = verification.get_file_text(post_2.hashVal)
    text_left = verification.remove_tags(text_1)
    text_right = verification.remove_tags(text_2)
    text_left = htmldiff(text_left, text_left)
    text_right = htmldiff(text_left, text_right)
    if post_1.hashVal == post_2.hashVal:
        flash('The content in the url is not changed')
    else:
        flash('Change in the content found')

    return render_template('very.html',double=True,left=Markup(text_left),dateLeft = post_1.timestamp,
                           dateRight = post_2.timestamp,right=Markup(text_right),search=False, comp_page="active")

@main.route('/verifyDomain/<domain>', methods=['GET', 'POST'])
@login_required
@nocache
def verifyDomain(domain):
    posts = Post.query.filter(Post.urlSite.contains(domain))
    verification.writePostsData(posts)
    page = request.args.get('page', 1, type=int)
    pagination = posts.order_by(Post.timestamp.desc()).filter(Post.urlSite != None).paginate(
        page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
        error_out=False)
    posts = pagination.items
    return render_template('search_domains.html', verify=posts,
                           pagination=pagination,domain=domain, comp_page="active")

@main.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    post = Post.query.get_or_404(id)
    if current_user != post.author and \
            not current_user.can(Permission.ADMINISTER):
        abort(403)
    form = PostEdit()
    if form.validate_on_submit():
        post.body = form.body.data
        db.session.add(post)
        flash('The post has been updated.')
        return redirect(url_for('.post', id=post.id))
    form.body.data = post.body
    return render_template('edit_post.html', form=form)