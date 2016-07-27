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
    #STW_ADMIN = os.environ.get('STW_ADMIN')
    STW_ADMIN = 'stamptheweb@gmail.com'
    STW_POSTS_PER_PAGE = 20
    STW_CHINA_PROXY = "101.201.42.44:3128"
    STW_USA_PROXY = "169.50.87.252:80"
    STW_UK_PROXY = "89.34.97.132:8080"
    STW_RUSSIA_PROXY = "80.240.114.77:8000"
    """To find locations of proxies been used. We require ip addresses only"""
    CHINA_PROXY = "60.216.40.135"
    USA_PROXY = "199.115.117.212"
    UK_PROXY = "90.216.222.23"
    RUSSIA_PROXY = "80.240.114.77"
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
