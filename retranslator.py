import logging
import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from flask import Flask
from flask import request as flask_request
from flask import Response


DEFAULT_MIMETYPE = 'text/html; charset=UTF-8'


app = Flask(__name__)
logger = logging.getLogger(__name__)


def replace_absolute_urls(text):
    regex = ('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F]'
             '[0-9a-fA-F]))+')
    urls = re.findall(regex, text)
    for url in urls:
        parsed = urlparse(url)
        new_url = flask_request.url_root + url[len(parsed.scheme)+3:]
        text = text.replace(url, new_url)
    return text


def replace_relative_url(soup, prefix, tag_name, attr_name):
    for tag in soup.findAll(tag_name):
        if attr_name in tag.attrs and not tag[attr_name].startswith('http'):
            tag[attr_name] = prefix + tag[attr_name]


def replace_relative_urls_in_html(soup, host):
    prefix = flask_request.url_root + host
    replace_relative_url(soup, prefix, 'a', 'href')
    replace_relative_url(soup, prefix, 'link', 'href')
    replace_relative_url(soup, prefix, 'link', 'src')
    replace_relative_url(soup, prefix, 'img', 'src')


def remove_attr(soup, tag_name, attr_name):
    for tag in soup.findAll(tag_name):
        tag.attrs.pop(attr_name, None)


def remove_attrs_in_html(soup):
    remove_attr(soup, 'link', 'integrity')


def is_html(text):
    return bool(BeautifulSoup(text, 'html.parser').find())


def html_to_res_html(text, host):
    soup = BeautifulSoup(text, 'html.parser')
    replace_relative_urls_in_html(soup, host)
    remove_attrs_in_html(soup)
    return str(soup)


def find_all(string, substring):
    return [i for i in range(len(string)) if string.startswith(substring, i)]


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


def get_content_type(response):
    return response.headers.get('Content-Type', DEFAULT_MIMETYPE)


def get_res_content(req_response, link, content_type):
    res_content = req_response.content
    text = ''
    if 'text' in content_type.lower():
        text = replace_absolute_urls(req_response.text)
    if 'text/html' in content_type.lower() and is_html(text):
        text = html_to_res_html(text, link.netloc)
    return bytes(text, 'utf-8') or res_content


def get_res_headers(req_response):
    res_headers = dict(req_response.headers)
    res_headers.pop('Content-Encoding', None)
    res_headers.pop('Transfer-Encoding', None)


def get_res_response(link):
    method = flask_request.method
    link = get_req_link(link)
    req_headers = get_req_headers(link)

    req_response = requests.request(
        method, link.geturl(), headers=req_headers, timeout=10)

    content_type = get_content_type(req_response)
    res_content = get_res_content(req_response, link, content_type)
    res_headers = get_res_headers(req_response)

    return Response(res_content, headers=res_headers, mimetype=content_type)


@app.route('/<path:link>', strict_slashes=False)
def translate(link):
    try:
        res_response = get_res_response(link)
    except Exception as exc:
        logger.error(exc, exc_info=True)
        res_response = Response('Invalid link', status=403)
    return res_response


if __name__ == '__main__':
    app.run()


#~ xml_sample = '<?xml version="1.0" encoding="UTF-8"?><note><to>Tove</to><from>Jani</from><heading>Reminder</heading><body>Dont forget me this weekend!</body></note>'
#~ html_sample = '<!DOCTYPE html><html><body><h1>My First Heading</h1><p>My first paragraph.</p></body></html>'
#~ json_example = '{"widget": {"debug": "on"}}'
#~ css_sample = 'p {text-align: center; color: red;}'
