import logging
import os
import re
import traceback
from urllib.parse import urlparse as urllib_urlparse

import requests
from bs4 import BeautifulSoup
from flask import Flask
from flask import redirect
from flask import request as flask_request
from flask import Response
from flask import send_from_directory


DEFAULT_MIMETYPE = 'text/html; charset=UTF-8'


app = Flask(__name__)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def add_root(url):
    return flask_request.url_root + url


def replace_absolute_urls(text):
    regex = ('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F]'
             '[0-9a-fA-F]))+')
    urls = sorted(list(set(re.findall(regex, text))), key=len)
    for url in reversed(urls):
        if not url.lower().startswith(flask_request.url_root.lower()):
            text = text.replace(url, add_root(url))
    return text


def is_relative(url):
    http = url.lower().startswith('http://')
    https = url.lower().startswith('https://')
    schemeless = url.lower().startswith('//')
    return not(http or https or schemeless)


def replace_relative_url_in_soup(soup, prefix, tag_name, attr_name):
    for tag in soup.findAll(tag_name):
        if attr_name in tag.attrs and is_relative(tag[attr_name]):
            tag[attr_name] = prefix + tag[attr_name]


def replace_schemeless_url_in_soup(soup, tag_name, attr_name):
    regex = ('//(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F]'
             '[0-9a-fA-F]))+')
    for tag in soup.findAll(tag_name):
        if attr_name in tag.attrs and re.match(regex, tag[attr_name]):
            tag[attr_name] = add_root(tag[attr_name][2:])


def replace_relative_urls_in_html(soup, prefix):
    replace_relative_url_in_soup(soup, prefix, 'a', 'href')
    replace_relative_url_in_soup(soup, prefix, 'link', 'href')
    replace_relative_url_in_soup(soup, prefix, 'link', 'src')
    replace_relative_url_in_soup(soup, prefix, 'img', 'src')
    replace_relative_url_in_soup(soup, prefix, 'script', 'src')


def replace_schemeless_urls_in_html(soup):
    replace_schemeless_url_in_soup(soup, 'a', 'href')
    replace_schemeless_url_in_soup(soup, 'link', 'href')
    replace_schemeless_url_in_soup(soup, 'link', 'src')
    replace_schemeless_url_in_soup(soup, 'img', 'src')
    replace_schemeless_url_in_soup(soup, 'script', 'src')


def remove_attr(soup, tag_name, attr_name):
    for tag in soup.findAll(tag_name):
        tag.attrs.pop(attr_name, None)


def remove_attrs_in_html(soup):
    remove_attr(soup, 'link', 'integrity')
    remove_attr(soup, 'script', 'integrity')


def is_html(text):
    return bool(BeautifulSoup(text, 'html.parser').find())


def html_to_res_html(text, link):
    soup = BeautifulSoup(text, 'html.parser')
    prefix_for_relative = add_root(link.scheme + '://' + link.netloc)
    replace_relative_urls_in_html(soup, prefix_for_relative)
    replace_schemeless_urls_in_html(soup)
    remove_attrs_in_html(soup)
    return str(soup)


def replace_relative_url_in_css(regex, url_idx, text, prefix):
    urls = re.findall(regex, text, re.IGNORECASE)
    for url in urls:
        new_url = url[:url_idx] + prefix + url[url_idx:]
        text = text.replace(url, new_url)
    return text


def replace_relative_urls_in_css(text, link):
    # replace urls starts with '/'
    prefix = add_root(link.scheme + '://' + link.netloc)
    text = replace_relative_url_in_css(
        'url\(\/(?!/).*?\)', 4, text, prefix)
    text = replace_relative_url_in_css(
        'url\(\"\/(?!/).*?\"\)', 5, text, prefix)
    text = replace_relative_url_in_css(
        "url\(\'\/(?!/).*?\'\)", 5, text, prefix)

    # replace urls starts with '../'
    prefix = add_root('/'.join(link.geturl().split('/')[:-1]) + '/')
    text = replace_relative_url_in_css(
        'url\(..\/.*?\)', 4, text, prefix)
    text = replace_relative_url_in_css(
        'url\(\"..\/.*?\"\)', 5, text, prefix)
    text = replace_relative_url_in_css(
        "url\(\'..\/.*?\'\)", 5, text, prefix)

    return text


def css_to_res_css(text, link):
    text = replace_relative_urls_in_css(text, link)
    return text


def find_all(string, substring):
    return [i for i in range(len(string)) if string.startswith(substring, i)]


def urlparse(link):
    if '://' not in link[:10]:
        link = 'http://' + link
    return urllib_urlparse(link)


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
        text = html_to_res_html(text, link)
    if 'text/css' in content_type.lower():
        text = css_to_res_css(text, link)
    return bytes(text, 'utf-8') or res_content


def get_res_headers(req_response):
    res_headers = dict(req_response.headers)
    res_headers.pop('Content-Encoding', None)
    res_headers.pop('Transfer-Encoding', None)


def get_req_response(link):
    method = flask_request.method
    req_headers = get_req_headers(link)
    req_response = requests.request(
        method, link.geturl(), headers=req_headers,
        timeout=10, allow_redirects=False,
    )
    return req_response


def self_redirect(url):
    return redirect(add_root(url))


def get_res_response(link):
    req_response = get_req_response(link)
    if req_response.is_redirect:
        next_url = req_response.next.url
        logger.warning('Following redirect  %s -> %s', link.geturl(), next_url)
        return self_redirect(next_url)

    content_type = get_content_type(req_response)
    res_content = get_res_content(req_response, link, content_type)
    res_headers = get_res_headers(req_response)
    return Response(res_content, headers=res_headers, mimetype=content_type)


def cut_roots(link, root):
    while link.lower().startswith(root):
        link = link[len(root):]
    return link


def extract_link():
    """Extract a correct URL from the URL provided"""
    root = flask_request.url_root.lower()
    raw_link = flask_request.url[len(root):]
    link = cut_roots(raw_link, root)
    link = urlparse(link).geturl()
    return raw_link, link


@app.route('/<path:link>', strict_slashes=False)
def translate(link):
    raw_link, link = extract_link()
    if raw_link != link:
        return self_redirect(link)

    try:
        res_response = get_res_response(urlparse(link))
    except Exception as exc:
        logger.error(exc, exc_info=True)
        tb = '<pre>' + traceback.format_exc() + '</pre>'
        res_response = Response(tb, status=403)

    return res_response


@app.route('/favicon.ico')
def favicon():
    path = os.path.join(app.root_path, 'static')
    mimetype = 'image/vnd.microsoft.icon'
    return send_from_directory(path, 'favicon.ico', mimetype=mimetype)


if __name__ == '__main__':
    app.run()
