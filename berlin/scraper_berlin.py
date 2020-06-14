import json
import re

import requests
from lxml import html as etree

import pdfcutter

# Import relative Parent Directory for Helper Classes
import os, sys
sys.path.insert(0, os.path.abspath('..')) #Used when call is ` python3 file.py`
sys.path.insert(0, os.path.abspath('.')) #Used when call is ` python3 $COUNTY/file.py`
import helper

BASE_URL = 'https://www.berlin.de'
INDEX_URL = 'https://www.berlin.de/rbmskzl/politik/bundesangelegenheiten/aktuelles/artikel.776154.php'

LINK_TEXT_RE = re.compile(r'(\d+)\. Sitzung am .*')

def get_pdf_urls():
    response = requests.get(INDEX_URL)
    root = etree.fromstring(response.content)
    fields = root.xpath('//*[@class="html5-section download modul-download"]')
    for field in fields:
        title = field.xpath('div[1]/p')[0]
        num = LINK_TEXT_RE.search(title.text_content())
        if num is None:
            continue
        num = int(num.group(1))
        link = field.xpath('div[3]/a')[0]
        yield num, BASE_URL + link.attrib['href']

def reformat_top_num(top_num):
    try:
        num = int(top_num)
        return str(num) + "."
    except ValueError: # Happens when top_num e.g. 48 a or 56 b
        return '{} {}'.format(top_num[:-1]+ ".", top_num[-1] + ")")

def get_reformatted_tops(top_nums):
    return [reformat_top_num(t) for t in top_nums]

def get_beschluesse_text(session, filename):
    cutter = pdfcutter.PDFCutter(filename=filename)
    session_number = int(session['number'])

    top_nums = [t['number'] for t in session['tops'] if t['top_type'] == 'normal'] # 1, 2, 3a, 3b, 4,....
    reformatted_top_nums = get_reformatted_tops(top_nums) #1., 2., 3. a), 3. b), 4.,...

    #e.g. "1b", ("1. b)", "2.")
    for top_num, (current, next_) in zip(top_nums, helper.with_next(reformatted_top_nums)):
        if(')' in current): #e.g. 46. a) problem: 46 isn't part of the TOP anymore. There, find the first line below 46 that is starting with b)
            current_top = cutter.filter(auto_regex='^{}'.format(current.split()[-1].replace(')', '\\)'))) #46. b) -> b\) because of regex brackets
            curr_num = current.split()[0] #46. b) -> 46.
#            current_num = cutter.filter(auto_regex='^{}$'.format(curr_num)) #Find line beginning with 46.
            current_num = cutter.filter(auto_regex='^{}\.$'.format(curr_num[:-1])) #Find line beginning with 46
            if ('a)' in current): #a) is next to number not, below it
                current_top = current_top.right_of(current_num)[0] #Find first line starting with b) below TOP 46.
            else:
                current_top = current_top.below(current_num)[0] #Find first line starting with b) below TOP 46.
        else:
            current_top = cutter.filter(auto_regex='^{}\.$'.format(current[:-1])) #Escape . in 46. because of regex

        next_top = None
        if next_ is not None: #There is a TOP after this one which we have to take as a lower border
            #Exactly the same as for the current_top
            if(')' in next_):
                next_top = cutter.filter(auto_regex='^{}'.format(next_.split()[-1].replace(')', '\\)')))
                next_top = next_top.below(current_top)[0] #Don't have to find TOP number line, because we can use current_top as a upper border
            else:
                next_top = cutter.filter(auto_regex='^{}\.$'.format(next_[:-1]))
        senats_text, br_text = getSenatsAndBrTextsForCurrentTOP(cutter, current_top, next_top)
        yield top_num, {'senat': senats_text, 'bundesrat': br_text}

def getSenatsAndBrTextsForCurrentTOP(cutter, current_top, next_top):
    page_heading = 135 #Right under the grey heading of each table
    page_number = 806 #Bottom of each page
    right_title = 585
    right_senat = 910
    right_br = 1233

    if next_top:
        senats_text = cutter.all().filter(
            doc_top__gte=current_top.doc_top -15 ,
            top__gte=page_heading,
            bottom__lt=page_number,
            doc_bottom__lt=next_top.doc_bottom -15,
            left__gt=right_title,
            right__lt=right_senat
        )
        br_text = cutter.all().filter(
            doc_top__gte=current_top.doc_top -15 ,
            top__gte=page_heading,
            doc_bottom__lt=next_top.doc_bottom -15,
            bottom__lt=page_number,
            left__gt=right_senat,
            right__lt=right_br
        )
    else:
        senats_text = cutter.all().filter(
            doc_top__gte=current_top.doc_top -15 ,
            top__gte=page_heading,
            bottom__lt=page_number,
            left__gt=right_title,
            right__lt=right_senat
        )
        br_text = cutter.all().filter(
            doc_top__gte=current_top.doc_top -15 ,
            top__gte=page_heading,
            bottom__lt=page_number,
            left__gt=right_senat,
            right__lt=right_br
        )

    return senats_text.clean_text(), br_text.clean_text()

def get_session(session):
    PDF_URLS = dict(get_pdf_urls())
#    PDF_URLS = {973: PDF_URLS[973]}
    try:
        filename = helper.get_session_pdf_filename(session, PDF_URLS)
    except KeyError:
        return
    return dict(get_beschluesse_text(session, filename))
