import os, requests, json, re
from subprocess import call, DEVNULL
import ipfsApi as ipfs
from urllib.parse import urlparse

ipfs_Client = ipfs.Client('127.0.0.1', 5001)
apiPostUrl = 'http://www.originstamp.org/api/stamps'
apiKey = '7be3aa0c7f9c2ae0061c9ad4ac680f5c '


def submit(sha256, title=None):
    """
    Submits the given hash to the originstamp API and returns the request object.

    :param sha256: hash to submit
    :param title: title of the hashed document
    :returns: resulting request object
    """
    headers = {'Content-Type': 'application/json', 'Authorization': 'Token token="7be3aa0c7f9c2ae0061c9ad4ac680f5c"'}
    data = {'hash_sha256': sha256, 'title': title}
    return requests.post(apiPostUrl, json=data, headers=headers)
