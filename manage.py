#!/usr/bin/env python
import os
from app import create_app, db
from app.main import proxy_util
from app.models import User, Role, Permission, Post, Regular
from flask_script import Manager, Shell, Server
from flask_migrate import Migrate, MigrateCommand
from flask import send_from_directory
import schedule
import time
import datetime
import send_mail
from threading import Thread
import ssl

"""The application runs according to the configurations provided in FLASK_CONFIG variable
    either Configuration, Development or Production"""
app = create_app(os.getenv('FLASK_CONFIG') or 'default')
manager = Manager(app)
migrate = Migrate(app, db)
proxy_util.logger = app.logger.info


def make_shell_context():
    return dict(app=app, db=db, User=User, Role=Role, Permission=Permission,
                Post=Post)


manager.add_command("shell", Shell(make_context=make_shell_context))
manager.add_command('db', MigrateCommand)
context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
if os.path.exists('/etc/ssl/certs/StampTheWeb.crt') and os.path.exists('/etc/ssl/private/StampTheWeb-d.key'):
    context.load_cert_chain('/etc/ssl/certs/StampTheWeb.crt', keyfile='/etc/ssl/private/StampTheWeb-d.key')
else:
    context.load_cert_chain('StampTheWeb.crt', keyfile='StampTheWeb-d.key')

manager.add_command('runserver', Server(ssl_context=context))


@manager.command
def test():
    """Run the unit tests."""
    import unittest
    tests = unittest.TestLoader().discover('tests')
    unittest.TextTestRunner(verbosity=2).run(tests)


# @manager.command
# def runserver():
#    """Run the flask HTTPS server"""
#    context = ('STW.crt', 'STW.key')
#    app.logger.info("Added HTTPS to flask from : " + str(context))
#
#    action = script.make_runserver(app, ssl_context=context)


# @app.route('/')
# def root():
#    return app.send_static_file('index.html')


start_time = time.time()


def run_every_day():
    """
    This method runs every day and checks the scheduled tasks and updates the proxy list daily.

    :author: Waqar and Sebastian
    """
    with app.app_context():
        app.logger.info("Starting the regular check for changes at {}".format(datetime.datetime.utcnow()))

        # update proxy list - may take up to 45 minutes depending on network latency and proxy availability
        try:
            app.logger.info("Regular task at {}: Updateing the proxy_list".format(datetime.datetime.utcnow()))
            proxy_util.logger = app.logger.info
            proxy_util.update_proxies()
            app.logger.info("Regular task at {}: Yay, proxy_list updated!".format(datetime.datetime.utcnow()))
        except UnicodeDecodeError as e:
            app.logger.error("Regular task at {}: Encountered a UnicodeDecodeError while fetching proxies. "
                             "Trying again later. {}".format(datetime.datetime.utcnow(), e))
        except RuntimeError as e:
            app.logger.error("Regular task at {}: Encountered a RuntimeError while fetching proxies. "
                             "Trying again later. {}".format(datetime.datetime.utcnow(), e))

        app.logger.info("Regular task at {}: Starting the regular queries".format(datetime.datetime.utcnow()))
        # proceed with the Regular tasks stored in db
        tasks = Regular.query.all()
        for task in tasks:
            seconds_passed = datetime.timedelta.total_seconds(datetime.datetime.utcnow() - task.timestamp)
            frequency = task.frequency
            seconds_required = 86400 * frequency
            # TODO add break/deletion/timeout criteria for a task (e.g. 3 months and after two and a half months
            # send mail to resubscribe)
            if seconds_required < seconds_passed:
                post = task.postID
                if send_mail.get_pages_send_email(post, task):
                    task.timestamp = datetime.datetime.utcnow()
                    db.session.commit()
                    # print('Something happened') # for Debugging

                    # print("Elapsed time: " + str(time.time() - start_time))  # for Debuggin
        app.logger.info("Regular task at {}: Finished the regular check for changes".format(datetime.datetime.utcnow()))


def run_schedule():
    while 1:
        schedule.run_pending()
        time.sleep(1)


# continue with the rest of your code


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """""The root directory of the applicaton from where it will return the requested
        files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'],
                               filename)


@manager.command
def profile(length=25, profile_dir=None):
    """Start the application under the code profiler."""
    from werkzeug.contrib.profiler import ProfilerMiddleware
    app.wsgi_app = ProfilerMiddleware(app.wsgi_app, restrictions=[length],
                                      profile_dir=profile_dir)


@manager.command
def deploy():
    """Run deployment tasks.
        Currently we do not require it """
    #from flask_migrate import upgrade
    #from app.models import Role, User

    # migrate database to latest revision
    # upgrade()


if __name__ == '__main__':
    """Starting a schedule task after every 86400 seconds i.e 1 day
        This will check the schedule comparison requests and check for update"""
    schedule.every(86400).seconds.do(run_every_day)
    t = Thread(target=run_schedule)
    t.start()
    manager.run()
