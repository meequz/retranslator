import re
from collections import namedtuple
from urllib.parse import urlparse

import requests
from flask import Flask
from flask import request
from flask import Response


USERAGENT = ('Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:55.0) Gecko/20100101 '
             'Firefox/55.0')
REQUESTS_HEADERS = {'User-Agent': USERAGENT}
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


@app.route('/<path:link>', strict_slashes=False)
def translate(link):
    link = 'http://' + link
    
    try:
        response = requests.get(link, timeout=10, headers=REQUESTS_HEADERS)
    except Exception:
        response = get_fail_response()
    
    content = response.content
    
    mimetype = response.headers.get('Content-Type', DEFAULT_MIMETYPE)
    if 'text' in mimetype.lower():
        text = replace_urls(response.text)
        content = bytes(text, 'utf-8')
    
    return Response(content, mimetype=mimetype)


if __name__ == '__main__':
    app.run()
