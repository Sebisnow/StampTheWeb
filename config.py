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
    STW_CHINA_PROXY = "http://60.216.40.135:9999"
    STW_USA_PROXY = "http://199.115.117.212:80"
    STW_UK_PROXY = "http://90.216.222.23:8080"
    CHINA_PROXY = "60.216.40.135"
    USA_PROXY = "199.115.117.212"
    UK_PROXY = "90.216.222.23"
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
