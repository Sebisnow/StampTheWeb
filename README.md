Stamp The Web
=============


## Synopsis
Stamp The Web is a trusted timestamping service for web-based content that can be used free of charge. The service enables users to automatically create trusted timestamps to preserve the existence of online content at a particular point in time, such as news paper articles, blog posts, etc.
This enables users to prove that certain information online existed in a particular state at the time it was 'trusted timestamped' using Stamp The Web.

## Version
1.0

## Code
The code is written using python Flask and related packages. It is tested with python 3.4.2, 3.5.2 and 3.4.3. The code contains two Flask Blueprints (main and auth) to manage the code reasonably.

`app.register_blueprint(main_blueprint)`
`app.register_blueprint(auth_blueprint, url_prefix='/auth')`

Both these blue_prints contain different set of files, folders and other related documents for homogeneous tasks.


## Motivation
'Stamp the Web' is a step towards a secure digital heritage protection system. It is aim to make this system open source. There are many other existing systems available however this system follows different approach. By adding hashes of timestamped content into bitcoin block chain, with the help of 'OriginStamp.org' API.


## Documentation
Please follow the link to get the technical documentation of this system.

## Tests
By using the main file 'manage.py' from terminal execute the following command.

```python manage.py test```

## Quick Start
In order to start working on the project. Install all the packages listed in 'requirements.txt' file. In order to find any help or report a bug please refer to the following:

### Installation

'Stamp the Web' requires python 3 and Flask to run.

It is tested with the following python packages:

* alembic==0.8.6
* Babel==1.3
* beautifulsoup4==4.4.1
* bleach==1.4.3
* blinker==1.4
* chardet==2.3.0
* click==6.6
* cryptography==1.2.3
* cssselect==0.9.1
* docutils==0.12
* dominate==2.2.0
* enum34==1.1.2
* feedparser==5.1.3
* Flask==0.11.1
* Flask-Bootstrap==3.3.6.0
* Flask-Login==0.3.2
* Flask-Mail==0.9.1
* Flask-Migrate==1.8.0
* Flask-Moment==0.5.1
* Flask-PageDown==0.2.1
* Flask-Script==2.0.5
* Flask-SQLAlchemy==2.1
* Flask-SSLify==0.1.5
* Flask-WTF==0.12
* funcsigs==0.4
* gdata==2.0.18
* gevent==1.1.1
* greenlet==0.4.9
* gunicorn==19.4.5
* html5lib==0.9999999
* idna==2.0
* ipaddress==1.0.16
* itsdangerous==0.24
* Jinja2==2.8
* linecache2==1.0.0
* lxml==3.6.0
* Mako==1.0.4
* Markdown==2.6.6
* MarkupSafe==0.23
* mock==1.3.0
* pbr==1.8.0
* Pillow==3.1.2
* psutil==3.4.2
* psycopg2==2.6.1
* pyasn1==0.1.9
* PyChart==1.39
* pycrypto==2.6.1
* pydot==1.0.29
* Pygments==2.1
* pyinotify==0.9.6
* PyOpenGL==3.0.2
* pyOpenSSL==0.15.1
* pyparsing==2.0.3
* Pyrex==0.9.8.5
* python-dateutil==2.4.2
* python-editor==1.0
* python-ldap==2.4.22
* python-openid==2.2.5
* python-stdnum==1.2
* pytz==2014.10
* PyWebDAV==0.9.8
* PyYAML==3.11
* readability-lxml==0.6.2
* reportlab==3.3.0
* requests==2.10.0
* roman==2.0.0
* schedule==0.3.2
* simplejson==3.8.1
* six==1.10.0
* SQLAlchemy==1.0.13
* traceback2==1.4.0
* unittest2==1.1.0
* unity-lens-photos==1.0
* uTidylib==0.2
* vatnumber==1.2
* virtualenv==15.0.2
* visitor==0.1.3
* vobject==0.8.1rc0
* Werkzeug==0.11.10
* WTForms==2.1
* xlwt==0.7.5
* ZSI==2.1a1


To install a python package use the following command.
```sh
$ pip install [python-package]
```



## License
Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files

