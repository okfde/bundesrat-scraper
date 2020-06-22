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


#TOP Format related functions

#46a -> 46. a)
def reformat_top_num(top_num):
    try:
        num = int(top_num)
        return str(num) + "."
    except ValueError: # Happens when top_num e.g. 48 a or 56 b
        return '{} {}'.format(top_num[:-1]+ ".", top_num[-1] + ")")

def get_reformatted_tops(top_nums):
    return [reformat_top_num(t) for t in top_nums]

#Extracts  session json TOPs and returns original form (for json) and reformated form (for parsing) 
#Also add to reformated TOPs the (if present) next TOP
def extractOriginalAndReformatedTOPNumbers(session):
    top_nums = [t['number'] for t in session['tops'] if t['top_type'] == 'normal'] # 1, 2, 3a, 3b, 4,....
    reformatted_top_nums = get_reformatted_tops(top_nums) #1., 2., 3. a), 3. b), 4.,...
    return zip(top_nums, with_next(reformatted_top_nums))

def with_next(iterable):
    a, b = itertools.tee(iterable)
    next(b, None)
    return itertools.zip_longest(a, b)
