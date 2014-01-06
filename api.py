from __future__ import print_function

from urllib import urlencode

import treq
from twisted.web.http_headers import Headers
from oauthlib import oauth1

import settings
import config

__all__ = ["moefou", "moefm"]


def request(method, url, **kwargs):
    oauth_tokens = settings.get("oauth_tokens")
    if not oauth_tokens:
        raise ValueError("OAuth token is unavailable")

    if kwargs.get("params"):
        encoded_params = urlencode(kwargs["params"])
        url = "".join([url, "&" if "?" in url else "?", encoded_params])
        del kwargs["params"]

    client = oauth1.Client(
        config.CONSUMER_KEY,
        client_secret=config.CONSUMER_SECRET,
        resource_owner_key=oauth_tokens["oauth_token"],
        resource_owner_secret=oauth_tokens["oauth_token_secret"],
    )
    new_url, headers, data = client.sign(
        url, method, body=kwargs.get("data"), headers=kwargs.get("headers"),
    )

    # Twisted doesn't support unicode...
    new_url = new_url.encode("utf-8")
    h = Headers({})
    for k, v in headers.iteritems():
        k = k.encode("utf-8")
        if isinstance(v, basestring):
            v = v.encode("utf-8")
            h.addRawHeader(k, v)
        else:
            v = [x.encode("utf-8") for x in v]
            h.setRawHeaders(k, v)

    kwargs["headers"] = h
    kwargs["data"] = data

    defer = treq.request(method, new_url, **kwargs)
    return defer.addCallback(treq.json_content)


class Api(object):
    def __init__(self, root):
        super(Api, self).__init__()
        self.root = root

    def get(self, path, params=None, **kwargs):
        return request("GET", self.root + path, params=params, **kwargs)

    def post(self, path, body=None, **kwargs):
        return request("GET", self.root + path, body=body, **kwargs)


moefou = Api(config.MOEFOU_API_ROOT)
moefm = Api(config.MOEFM_API_ROOT)

if __name__ == '__main__':
    from twisted.internet import reactor
    from pprint import pprint
    import sys

    def done(obj):
        pprint(obj)
        reactor.stop()

    def error(fail):
        fail.printDetailedTraceback()
        reactor.stop()

    request("GET", sys.argv[1]).addCallbacks(done, error)
    reactor.run()
