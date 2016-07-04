import os
basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard to guess string'
    SQLALCHEMY_COMMIT_ON_TEARDOWN = True
    MAIL_SERVER = 'smtp.uni-konstanz.de'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_SUBJECT_PREFIX = '[Stamp The Web]'
    MAIL_SENDER = 'Stamp The Web Admin <waqar.detho@uni-konstanz.de>'
    #ADMIN = os.environ.get('ADMIN')
    ADMIN = 'waqar.detho@uni-konstanz.de'
    POSTS_PER_PAGE = 20
    CHINA_PROXY_PORT = "101.201.42.44:3128"
    USA_PROXY_PORT = "169.50.87.252:80"
    UK_PROXY_PORT = "89.34.97.132:8080"
    CHINA_PROXY = "101.201.42.44"
    USA_PROXY = "169.50.87.252"
    UK_PROXY = "89.34.97.132"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'data-dev.sqlite')


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'data-test.sqlite')


class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'data-dev.sqlite')

config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'heroku': DevelopmentConfig,

    'default': DevelopmentConfig
}
