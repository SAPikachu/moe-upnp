#!/usr/bin/env python
from __future__ import print_function, unicode_literals

from requests_oauthlib import OAuth1Session

import config
import settings

OAUTH_URLS = {
    name: config.MOEFOU_API_ROOT + path
    for name, path in {
        "request_token": "/oauth/request_token",
        "authorize": "/oauth/authorize",
        "access_token": "/oauth/access_token",
    }.iteritems()
}


def get_session(**kwargs):
    return OAuth1Session(
        config.CONSUMER_KEY,
        client_secret=config.CONSUMER_SECRET,
        **kwargs
    )


def login():
    oauth = get_session()
    fetch_response = oauth.fetch_request_token(OAUTH_URLS["request_token"])
    resource_owner_key = fetch_response.get("oauth_token")
    resource_owner_secret = fetch_response.get("oauth_token_secret")

    base_authorization_url = OAUTH_URLS["authorize"]
    authorization_url = oauth.authorization_url(base_authorization_url)
    print("Please go here and authorize:", authorization_url)
    verifier = raw_input('Paste the verifier here: ')

    oauth = get_session(
        resource_owner_key=resource_owner_key,
        resource_owner_secret=resource_owner_secret,
        verifier=verifier,
    )
    oauth_tokens = oauth.fetch_access_token(OAUTH_URLS["access_token"])
    settings.set("oauth_tokens", oauth_tokens)


if __name__ == "__main__":
    login()
