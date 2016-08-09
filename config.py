import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard to guess string'
    SQLALCHEMY_COMMIT_ON_TEARDOWN = True
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = 'stamptheweb@gmail.com'
    MAIL_PASSWORD = 'hD7BieuJFM7Zi2ZsJh6kb8Sn'
    STW_MAIL_SUBJECT_PREFIX = '[StampTheWeb]'
    STW_MAIL_SENDER = 'StampTheWeb Admin <stamptheweb@gmail.com>'
    # STW_ADMIN = os.environ.get('STW_ADMIN')
    STW_ADMIN = 'stamptheweb@gmail.com'
    STW_POSTS_PER_PAGE = 20
    STW_CHINA_PROXY = "123.56.28.196:8888"
    STW_USA_PROXY = "40.84.193.251:3128"
    STW_UK_PROXY = "89.34.97.132:8080"
    STW_RUSSIA_PROXY = "109.237.13.90:8080"
    """To find locations of proxies been used. We require ip addresses only"""
    CHINA_PROXY = "123.56.28.196"
    USA_PROXY = "40.84.193.251"
    UK_PROXY = "90.216.222.23"
    RUSSIA_PROXY = "109.237.13.90"
    SERVER_URL = 'https://stamptheweb.org'
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # added due to an error. Tracks modifications of SQL Alchemy objects.

    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(Config):
    """When used the errors are shown in the Web Browser"""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
                              'sqlite:///' + os.path.join(basedir, 'data-dev.sqlite')


class TestingConfig(Config):
    """Uses a different DB and removes it after the testing is done"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or \
                              'sqlite:///' + os.path.join(basedir, 'data-test.sqlite')


class ProductionConfig(Config):
    """To be used when deployed"""
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
                              'sqlite:///' + os.path.join(basedir, 'data-dev.sqlite')


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'heroku': DevelopmentConfig,
    'default': DevelopmentConfig
}



