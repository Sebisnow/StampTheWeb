from flask import render_template, redirect, url_for, abort, flash, request,\
    current_app
from flask_login import login_required, current_user
from . import main
from .forms import EditProfileForm, EditProfileAdminForm, PostForm,PostVerify, PostFreq, SearchPost,SearchOptions
from .. import db
from ..models import Permission, Role, User, Post,Regular
from ..decorators import admin_required
from app.main import downloader,verification
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for
from urllib.parse import urlparse
from lxml.html.diff import htmldiff
from markupsafe import Markup
import validators
from ..nocache import nocache
from sqlalchemy import or_,and_




@main.route('/', methods=['GET', 'POST'])
def index():
    form = PostForm()
    formFreq = PostFreq()
    if current_user.can(Permission.WRITE_ARTICLES) and \
            form.validate_on_submit() and not formFreq.frequency.data:
        sha256=None
        dateTimeGMT=None
        post_new = None
        urlSite=form.urlSite.data
        if form.urlSite.data != None:
            results = downloader.get_url_history(urlSite)
            originStampResult = results.originStampResult
            sha256 = results.hashValue
            title = results.webTitle
            if originStampResult is not None and originStampResult.headers['Date'] is not None:
                dateTimeGMT=originStampResult.headers['Date']
                post_new = Post(body=form.body.data, urlSite=urlSite, hashVal=sha256, webTitl=title, origStampTime=datetime.strptime(dateTimeGMT, "%a, %d %b %Y %H:%M:%S %Z"),
                                author=current_user._get_current_object())
            else:
                flash('Could not submit to Originstamp')
        already_exist = Post.query.filter(and_(Post.urlSite.like(urlSite),
                                            Post.hashVal.like(sha256))).first()
        if already_exist is not None:
            flash('The URL was already submitted')
            post_old = Post.query.get_or_404(already_exist.id)
            return render_template('post.html', posts=[post_old],single=True)
        else:
            if post_new is not None:
                db.session.add(post_new)
                db.session.commit()
        return redirect(url_for('.index'))
    elif current_user.can(Permission.WRITE_ARTICLES) and \
            formFreq.validate_on_submit() and formFreq.frequency.data > 0:
        sha256=None
        dateTimeGMT=None
        urlSite=formFreq.urlSite.data
        freq = formFreq.frequency.data
        china = formFreq.china.data
        usa = formFreq.usa.data
        uk = formFreq.uk.data
        email = formFreq.email.data

        if formFreq.urlSite.data != None:
            results = downloader.get_url_history(urlSite)
            originStampResult = results.originStampResult
            sha256 = results.hashValue
            title = results.webTitle
            if originStampResult is not None:
                dateTimeGMT=originStampResult.headers['Date']
                origStampTime=datetime.strptime(dateTimeGMT, "%a, %d %b %Y %H:%M:%S %Z")
            else:
                origStampTime = datetime.now()
        post_new = Post(body=formFreq.body.data,urlSite=urlSite,hashVal=sha256,webTitl=title,origStampTime=origStampTime,
                    author=current_user._get_current_object())
        already_exist = Post.query.filter(and_(Post.urlSite.like(urlSite),
                                            Post.hashVal.like(sha256))).first()
        if already_exist is not None:
            flash('The URL Already Submitted')
            post_old = Post.query.get_or_404(already_exist.id)
            return render_template('post.html', posts=[post_old],single=True)
        else:
            db.session.add(post_new)
            db.session.commit()
            post_found = Post.query.filter(and_(Post.urlSite.like(urlSite),
                                                Post.hashVal.like(sha256))).first()

            regular_new = Regular(frequency=freq,china=china,uk=uk,usa=usa,postID=post_found,email=email)
            db.session.add(regular_new)
            db.session.commit()
            page = request.args.get('page', 1, type=int)
        pagination = Regular.query.order_by(Regular.timestamp.desc()).paginate(
            page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
            error_out=False)
        posts = pagination.items
        return render_template('regular.html', form=formFreq, posts=posts,
                               pagination=pagination)

    else:
        domain_list = []
        domain_name = []
        #Getting Domains visited by all the users
        for domains in Post.query.filter(Post.urlSite != None):
            if domains.urlSite is not None:
                url_parse = urlparse(domains.urlSite)
                if url_parse.netloc and url_parse.scheme:
                    domain_list.append(domains.urlSite)
                    if(url_parse.netloc.startswith('www.')):
                        domain_name.append(url_parse.netloc[4:])
                    else:
                        domain_name.append(url_parse.netloc)
        domain_name_unique = set(domain_name)
        for name in domain_name_unique:
            if ';' not in name:
                count=domain_name.count(name)
                domain_name_unique.remove(name)
                domain_name_unique.add(name+ ';'+str(count))

        page = request.args.get('page', 1, type=int)
        pagination = Post.query.order_by(Post.timestamp.desc()).paginate(
            page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
            error_out=False)
        posts = pagination.items
        return render_template('index.html', form=form, posts=posts,
                               pagination=pagination,doman_name=domain_name_unique,formFreq=formFreq)


@main.route('/compare', methods=['GET', 'POST'])
def compare():
    form = PostVerify()
    if current_user.can(Permission.WRITE_ARTICLES) and \
            form.validate_on_submit():
        searchkeyword=form.urlSite.data
        if not validators.url(searchkeyword):
            domain = searchkeyword
            searchkeyword = '%'+searchkeyword+'%'
            posts = Post.query.filter(or_(Post.urlSite.like(searchkeyword),
                                            Post.webTitl.like(searchkeyword),Post.body.like(searchkeyword)))

            verification.writePostsData(posts)
            page = request.args.get('page', 1, type=int)
            pagination = posts.order_by(Post.timestamp.desc()).filter(Post.urlSite != None).paginate(
                page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
                error_out=False)
            posts = pagination.items
            return render_template('search_domains.html', verify=posts,
                                   pagination=pagination,domain=domain, search = True)


        elif validators.url(searchkeyword):
            posts = Post.query.filter(Post.urlSite.contains(searchkeyword))
            verification.writePostsData(posts)
            page = request.args.get('page', 1, type=int)
            pagination = posts.order_by(Post.timestamp.desc()).filter(Post.urlSite != None).paginate(
                page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
                error_out=False)
            posts = pagination.items
            return render_template('search_domains.html', verify=posts,
                                   pagination=pagination,search = True, domain=searchkeyword)

    user = User.query.filter_by(username=current_user.username).filter(Post.urlSite != None).first_or_404()
    domain_list = []
    domain_name = []
    #Getting Domains user visited
    if not current_user.is_anonymous:
        for domains in user.posts.filter(Post.urlSite != None):
            if domains.urlSite is not None:
                url_parse = urlparse(domains.urlSite)
                if url_parse.netloc and url_parse.scheme:
                    domain_list.append(domains.urlSite)
                    if(url_parse.netloc.startswith('www.')):
                        domain_name.append(url_parse.netloc[4:])
                    else:
                        domain_name.append(url_parse.netloc)
        doman_name_unique = set(domain_name)
        for name in doman_name_unique:
            if ';' not in name:
                count=domain_name.count(name)
                doman_name_unique.remove(name)
                doman_name_unique.add(name+ ';'+str(count))
    page = request.args.get('page', 1, type=int)
    pagination = user.posts.order_by(Post.timestamp.desc()).filter(Post.urlSite != None).paginate(
        page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
        error_out=False)
    verify = pagination.items
    return render_template('verify.html', form=form, verify=verify,
                           pagination=pagination,doman_name=doman_name_unique)

@main.route('/compare_options/<ids>', methods=['GET', 'POST'])
def compare_options(ids):
    form = SearchPost()
    form_choice = SearchOptions()
    a_split = ids.split(':')
    post_1 = Post.query.get_or_404(a_split[0])
    searchkeyword = a_split[1]
    if current_user.can(Permission.WRITE_ARTICLES) and \
            form.validate_on_submit():
        searchkeyword=form.urlSite.data

        if not validators.url(searchkeyword):
            domain = searchkeyword
            searchkeyword = '%'+searchkeyword+'%'
            posts = Post.query.filter(or_(Post.urlSite.like(searchkeyword),
                                            Post.webTitl.like(searchkeyword),Post.body.like(searchkeyword)))


            page = request.args.get('page', 1, type=int)
            pagination = posts.order_by(Post.timestamp.desc()).filter(Post.urlSite != None).paginate(
                page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
                error_out=False)
            posts = pagination.items
            return render_template('search_options.html', verify=posts, form=form, form_choice=form_choice,
                                   pagination=pagination,last_post = post_1, domain=domain,last=str(post_1.id))


        elif validators.url(searchkeyword):
            posts = Post.query.filter(Post.urlSite.contains(searchkeyword))
            verification.writePostsData(posts)
            page = request.args.get('page', 1, type=int)
            pagination = posts.order_by(Post.timestamp.desc()).filter(Post.urlSite != None).paginate(
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
        hash_2,text_2 = downloader.get_text_from_other_country(china,usa,uk,post_1.urlSite)
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

    if not validators.url(searchkeyword):
        domain = searchkeyword
        searchkeyword = '%'+searchkeyword+'%'
        posts = Post.query.filter(or_(Post.urlSite.like(searchkeyword),
                                        Post.webTitl.like(searchkeyword),Post.body.like(searchkeyword)))


        page = request.args.get('page', 1, type=int)
        pagination = posts.order_by(Post.timestamp.desc()).filter(Post.urlSite != None).paginate(
            page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
            error_out=False)
        posts = pagination.items
        return render_template('search_options.html', verify=posts, form=form, form_choice=form_choice,
                               pagination=pagination,last_post = post_1, domain=domain,last=str(post_1.id))


    elif validators.url(searchkeyword):
        posts = Post.query.filter(Post.urlSite.contains(searchkeyword))
        verification.writePostsData(posts)
        page = request.args.get('page', 1, type=int)
        pagination = posts.order_by(Post.timestamp.desc()).filter(Post.urlSite != None).paginate(
            page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
            error_out=False)
        posts = pagination.items
        return render_template('search_options.html', verify=posts,
                               pagination=pagination, last_post = post_1,form=form,form_choice=form_choice,
                               last=str(post_1.id))


@main.route('/regular', methods=['GET', 'POST'])
def regular():
    formFreq = PostFreq()
    if current_user.can(Permission.WRITE_ARTICLES) and formFreq.validate_on_submit():
        sha256 = None
        dateTimeGMT=None
        urlSite=formFreq.urlSite.data
        freq = formFreq.frequency.data
        china = formFreq.china.data
        usa = formFreq.usa.data
        uk = formFreq.uk.data
        email = formFreq.email.data

        if formFreq.urlSite.data != None:
            results = downloader.get_url_history(urlSite)
            originStampResult = results.originStampResult
            sha256 = results.hashValue
            title = results.webTitle
            if originStampResult is not None:
                dateTimeGMT=originStampResult.headers['Date']
                origStampTime=datetime.strptime(dateTimeGMT, "%a, %d %b %Y %H:%M:%S %Z")
            else:
                origStampTime = datetime.now()
        post_new = Post(body=formFreq.body.data,urlSite=urlSite,hashVal=sha256,webTitl=title,origStampTime=origStampTime,
                    author=current_user._get_current_object())
        already_exist = Post.query.filter(and_(Post.urlSite.like(urlSite),
                                            Post.hashVal.like(sha256))).first()
        if already_exist is not None:
            flash('The URL Already Submitted')
            post_old = Post.query.get_or_404(already_exist.id)
            return render_template('post.html', posts=[post_old],single=True)
        else:
            db.session.add(post_new)
            db.session.commit()
            post_found = Post.query.filter(and_(Post.urlSite.like(urlSite),
                                                Post.hashVal.like(sha256))).first()

            regular_new = Regular(frequency=freq,china=china,uk=uk,usa=usa,postID=post_found,email=email)
            db.session.add(regular_new)
            db.session.commit()
    page = request.args.get('page', 1, type=int)
    pagination = Regular.query.order_by(Regular.timestamp.desc()).paginate(
        page, per_page=current_app.config['FLASKY_POSTS_PER_PAGE'],
        error_out=False)
    posts = pagination.items
    return render_template('regular.html', form=formFreq, posts=posts,
                           pagination=pagination)

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


@main.route('/post/<int:id>')
def post(id):
    post = Post.query.get_or_404(id)
    return render_template('post.html', posts=[post],single=True)
@main.route('/very/<int:id>')
def very(id):
    very = Post.query.get_or_404(id)
    return render_template('very.html', verify=[very],single=True,search = False)

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
                           dateRight = datetime.now(),right=Markup(text_right),search=False)

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
                           dateRight = post_2.timestamp,right=Markup(text_right),search=False)



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
                           pagination=pagination,domain=domain)



@main.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    post = Post.query.get_or_404(id)
    if current_user != post.author and \
            not current_user.can(Permission.ADMINISTER):
        abort(403)
    form = PostForm()
    if form.validate_on_submit():
        post.body = form.body.data
        db.session.add(post)
        flash('The post has been updated.')
        return redirect(url_for('.post', id=post.id))
    form.body.data = post.body
    return render_template('edit_post.html', form=form)


