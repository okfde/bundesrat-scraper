import itertools
from urllib.parse import urlsplit
import os
import requests

#Escape . and ) in TOPs for regex
#Cant use re.escape because it escapes spaces too, which is bad for later split
def escapeForRegex(s):
    return s.replace(".", "\\.").replace(")", "\\)")

def get_filename_url(url):
    splitresult = urlsplit(url)
    filename = splitresult.path.replace('/', '_')
    filename = os.path.join('./_cache', filename)
    if os.path.exists(filename):
        return filename
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception('{} not found'.format(url))
    with open(filename, 'wb') as f:
        f.write(response.content)
    return filename

def get_session_pdf_filename(session, PDF_URLS):
    url = PDF_URLS[session['number']]
    return get_filename_url(url)

def with_next(iterable):
    a, b = itertools.tee(iterable)
    next(b, None)
    return itertools.zip_longest(a, b)
