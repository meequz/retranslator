import logging
import re
from collections import namedtuple
from urllib.parse import urlparse

import requests
from flask import Flask
from flask import request
from flask import Response


DEFAULT_MIMETYPE = 'text/html; charset=UTF-8'


app = Flask(__name__)


def find_urls(text):
    regex = ('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F]'
             '[0-9a-fA-F]))+')
    urls = re.findall(regex, text)
    return urls


def get_fail_response():
    dictionary = {'content': b'Invalid link',
                  'headers': {},
                  'text': 'Invalid link'}
    return namedtuple('Response', dictionary.keys())(*dictionary.values())


def convert_url(url):
    parsed = urlparse(url)
    new_url = request.url_root + url[len(parsed.scheme)+3:]
    return new_url


def replace_urls(text):
    urls = find_urls(text)
    for url in urls:
        new_url = convert_url(url)
        text = text.replace(url, new_url)
    return text


def get_new_content(response):
    mimetype = response.headers.get('Content-Type', DEFAULT_MIMETYPE)
    if 'text' in mimetype.lower():
        text = replace_urls(response.text)
        return bytes(text, 'utf-8')


def perform_request(method, link, headers={}):
    if not isinstance(headers, dict):
        headers = dict(headers)
    if '://' not in link[:10]:
        link = 'http://' + link
    response = requests.request(method, link, headers=headers, timeout=10)
    return response


@app.route('/<path:link>', strict_slashes=False)
def translate(link):
    try:
        req_response = perform_request(request.method, link, request.headers)
    except Exception:
        req_response = get_fail_response()
    
    content = get_new_content(req_response)
    req_headers = dict(req_response.headers)
    res_response = Response(content, headers=req_headers)
    return res_response


if __name__ == '__main__':
    app.run()
