Stamp The Web
=============


## Synopsis
Stamp The Web is a trusted timestamping service for web-based content that can be used free of charge. The service enables users to automatically create trusted timestamps to preserve the existence of online content at a particular point in time, such as news paper articles, blog posts, etc.
This enables users to prove that certain information online existed in a particular state at the time it was 'trusted timestamped' using Stamp The Web.

## Code
The code is written using python Flask and related packages. It is tested with python 3.4.2, 3.5.2 and 3.4.3. The code contains two Flask Blueprints (main and auth) to manage the code reasonably.
```app.register_blueprint(main_blueprint)```
```app.register_blueprint(auth_blueprint, url_prefix='/auth')```

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


## License
Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files

