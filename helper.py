import itertools
from urllib.parse import urlsplit
import os
import requests
from pdfcutter import utils
from lxml import html as etree

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
    response = requests.get(url, headers={'User-Agent': '-'}) #Need this for MV (else after ~5 PDFs cant download anymore) and don't want to restructure everything to add User-Agent, so just try to add it always and see if it breaks somewhere
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
