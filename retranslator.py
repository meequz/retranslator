import logging
import re
from collections import namedtuple
from urllib.parse import urlparse

import requests
from flask import Flask
from flask import request as flask_request
from flask import Response


DEFAULT_MIMETYPE = 'text/html; charset=UTF-8'


app = Flask(__name__)


def replace_urls(text):
    regex = ('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F]'
             '[0-9a-fA-F]))+')
    urls = re.findall(regex, text)
    for url in urls:
        parsed = urlparse(url)
        new_url = flask_request.url_root + url[len(parsed.scheme)+3:]
        text = text.replace(url, new_url)
    return text


def get_req_link(link):
    if '://' not in link[:10]:
        link = 'http://' + link
    return urlparse(link)


def get_req_headers(link):
    req_headers = dict(flask_request.headers)
    host = req_headers.get('Host')
    if host:
        req_headers['Host'] = link.netloc
    return req_headers


def get_res_content(req_response):
    mimetype = req_response.headers.get('Content-Type', DEFAULT_MIMETYPE)
    if 'text' in mimetype.lower():
        text = replace_urls(req_response.text)
        return bytes(text, 'utf-8')


def get_res_headers(req_response):
    return dict(req_response.headers)


def get_res_response(link):
    method = flask_request.method
    link = get_req_link(link)
    req_headers = get_req_headers(link)
    req_response = requests.request(
        method, link.geturl(), headers=req_headers, timeout=10)
    res_content = get_res_content(req_response)
    res_headers = get_res_headers(req_response)
    return Response(res_content, headers=res_headers)


@app.route('/<path:link>', strict_slashes=False)
def translate(link):
    try:
        res_response = get_res_response(link)
    except Exception:
        res_response = Response('Invalid link', status=403)
    return res_response


if __name__ == '__main__':
    app.run()
