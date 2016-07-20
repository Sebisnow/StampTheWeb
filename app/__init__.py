from flask import Flask
from flask_bootstrap import Bootstrap
from flask_mail import Mail
from flask_moment import Moment
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_pagedown import PageDown
from config import config
import logging
from markupsafe import Markup
import re
from logging.handlers import RotatingFileHandler

bootstrap = Bootstrap()
mail = Mail()
moment = Moment()
db = SQLAlchemy()
pagedown = PageDown()

login_manager = LoginManager()
login_manager.session_protection = 'strong'
login_manager.login_iew = 'auth.login'

def clever_function(str,domain):
    #Changes the String to highlight text for html5
    insensitive_domain = re.compile(re.escape(domain), re.IGNORECASE)
    if domain.lower() in str.lower():
        htmlString = insensitive_domain.sub('<mark>'+domain+'</mark>', str)
        return Markup(htmlString)
    else:
        return Markup(str)


def create_app(config_name):
    app = Flask(__name__,static_folder='pdf') #working
    #app = Flask(__name__, static_url_path='')
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)
    app.config['UPLOAD_FOLDER'] = 'pdf/' #working


    #Setting up Logging
    handler = RotatingFileHandler('webStamps.log', maxBytes=10000, backupCount=1)
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)

    bootstrap.init_app(app)
    mail.init_app(app)
    moment.init_app(app)
    db.init_app(app)
    login_manager.init_app(app)
    pagedown.init_app(app)


    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from .auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')

    app.jinja_env.globals.update(clever_function=clever_function)
    app.jinja_env.add_extension('jinja2.ext.do')

    return app




