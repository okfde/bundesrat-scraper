import itertools
from urllib.parse import urlsplit
import os
import requests
from pdfcutter import utils
from lxml import html as etree
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

#Escape . and ) in TOPs for regex
#Cant use re.escape because it escapes spaces too, which is bad for later split
def escapeForRegex(s):
    return s.replace(".", "\\.").replace(")", "\\)")

def get_filename_url(url):
    splitresult = urlsplit(url)
    # Ensure path is a string before replacing
    path = splitresult.path
    if isinstance(path, bytes):
        path = path.decode('utf-8')
    
    # Extract the filename from the path
    if path.endswith('/'):
        # If path ends with /, use the last directory name
        parts = path.rstrip('/').split('/')
        filename = parts[-1] if parts else 'index'
    else:
        # Otherwise use the last part of the path
        filename = os.path.basename(path)
    
    # If filename is empty or just contains query parameters, use a default name
    if not filename or filename.startswith('?'):
        filename = 'document'
    
    # Add a unique identifier based on the URL to avoid collisions
    import hashlib
    url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()[:8]
    
    # Ensure filename has .pdf extension for PDF files
    base, ext = os.path.splitext(filename)
    if url.lower().endswith('.pdf') and ext.lower() != '.pdf':
        filename = f"{base}_{url_hash}.pdf"
    else:
        filename = f"{filename}_{url_hash}{ext}"
    
    # Ensure the filename is safe for the filesystem
    filename = filename.replace('/', '_').replace('\\', '_').replace(':', '_')
    
    cache_path = os.path.join('./_cache', filename)
    if os.path.exists(cache_path):
        return cache_path
    
    # Add retry logic with exponential backoff
    import time
    import random
    from requests.exceptions import RequestException
    
    max_retries = 5
    retry_delay = 2  # Initial delay in seconds
    
    for retry in range(max_retries):
        try:
            # Add a more realistic user agent
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Cache-Control': 'max-age=0'
            }
            
            # Add a small delay before each request to avoid overwhelming the server
            time.sleep(1 + random.random())
            
            # Ignore SSL certificate verification, needed e.g. Hamburg 1048 pdf
            response = requests.get(url, headers=headers, timeout=30, verify=False)
            
            if response.status_code != 200:
                raise Exception(f'{url} returned status code {response.status_code}')
            
            with open(cache_path, 'wb') as f:
                f.write(response.content)
            
            return cache_path
            
        except RequestException as e:
            if retry < max_retries - 1:
                # Calculate exponential backoff with jitter
                sleep_time = retry_delay * (2 ** retry) + random.uniform(0, 1)
                print(f"Connection error: {e}. Retrying in {sleep_time:.2f} seconds...")
                time.sleep(sleep_time)
            else:
                raise Exception(f"Failed to download {url} after {max_retries} attempts: {e}")

def get_session_pdf_filename(session, PDF_URLS):
    url = PDF_URLS.get(session['number'], PDF_URLS.get(str(session['number'])))  #not cache uses int, cache uses str
    if url is None:
        raise KeyError(f"No PDF URL found for session {session['number']}")
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
    sorted_top_nums=sorted(top_nums, key=get_sort_key)
    print(sorted_top_nums)
    reformatted_top_nums = get_reformatted_tops(sorted_top_nums) #1., 2., 3. a), 3. b), 4.,...
    return zip(sorted_top_nums, with_next(reformatted_top_nums))

def get_sort_key(item):
    """
    Sort a list of mixed numeric and alphanumeric items.

    This function handles:
    - Pure numbers (like 1, 3, 10)
    - Items with numeric prefix followed by letters (like 23a, 23b)

    Args:
        items: List of strings or numbers to be sorted

    Returns:
        Sorted list

    1 3 10 23a 23b 24
    into
    1 3 10 23a 23b 24
    """
    # Convert item to string for processing
    item_str = item.strip()

    # If item is purely numeric, return it as a number for proper sorting
    if item_str.isdigit():
        return (int(item_str), "")

    # For items like "23a", split into numeric and alpha parts
    numeric_part = ""
    alpha_part = ""

    for i, char in enumerate(item_str):
        if char.isdigit():
            numeric_part += char
        else:
            alpha_part = item_str[i:]
            break

    # Return tuple of (numeric_part, alpha_part) for sorting
    return (int(numeric_part) if numeric_part else 0, alpha_part)


def with_next(iterable):
    a, b = itertools.tee(iterable)
    next(b, None)
    return itertools.zip_longest(a, b)

#pdfcutter.utils.obj_to_coord
#Compare doc_top instead of top
#Only use Selection, easier to directly call doc_top than to compute it myself
#Don't have doc_top as attribute, therefore add page height page_number of times
def _obj_to_coord_doc_top(x):
    top = int(x.attrib['top'])
    page_number = int(x.getparent().attrib['number'])
    page_height = int(x.getparent().attrib['height'])
    doc_top = top + page_number*page_height

    return (doc_top, int(x.attrib['left']))

#pdfcutter.utils.fuzzy_compare
#Compare doc_top instead of top
@utils.cmp_to_key
def _fuzzy_compare_doctop(a, b):
    a = _obj_to_coord_doc_top(a)
    b = _obj_to_coord_doc_top(b)
    if utils.similar(a[0], b[0], 4):
        if utils.similar(a[1], b[1], 4):
            return 0
        return 1 if a[1] > b[1] else -1
    return 1 if a[0] > b[0] else -1

# pdfcutter orders text by top, not doc_top. This leads to ordering problems for multi-page selections
def cleanTextOrderedByDocTop(selection, join_words = True, fix_hyphens=True):
    #Exactly https://github.com/stefanw/pdfcutter/blob/master/pdfcutter/pdfcutter.py , but sort by doctop before

    #Selection.text_list
    texts = [etree.tostring(
            t, method="text", encoding='utf-8').decode('utf-8')
            for t in sorted(selection.selected,key=_fuzzy_compare_doctop) #Sort by doc_top, not top
    ]
    if join_words:
        texts = [t.strip().replace('- ', '-') for t in texts]

    #Selection.text()
    text = ' '.join(texts)

    #Selection.clean_text()
    text = utils.remove_multispace(text)
    if fix_hyphens:
        text = utils.remove_hyphenation(text)
    return text
