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

from datetime import datetime


BASE_URL="https://www.landesvertretung.sachsen.de"
INDEX_URL="https://www.landesvertretung.sachsen.de/js/chronik/bundesrat{}.json"

LINK_TEXT_RE = re.compile(r'(\d+)\. Bundesratssitzung .*')
FIRST_YEAR=2016

def get_pdf_urls():
    curr_year = datetime.now().year
    for year in range(FIRST_YEAR, curr_year + 1): #2016 - now
        url_year = INDEX_URL.format(year)
        #There is a JS function wrapped around this JSON, so delete it
        site_year = requests.get(url_year).text 
        list_year = site_year.replace('return {', '{').replace('};','}').split('\r\n')[1:-1]
        json_year = json.loads('\r\n'.join(list_year))
        for meeting in json_year['data']:
            if meeting is None:
                continue
            num = LINK_TEXT_RE.search(meeting['text'])
            if num is None:
                continue
            num = int(num.group(1))
            if num == 955:
                continue # meeting 955 has no PDF
            link_meeting = BASE_URL + meeting['url']
            response = requests.get(link_meeting)
            root = etree.fromstring(response.content)
            link = root.xpath('//*[@id="main-content"]/ul[2]/li/a')[0].attrib['href']

            yield num, BASE_URL + link

def reformat_top_num(top_num):
    try:
        num = int(top_num)
        return str(num) + "."
    except ValueError: # Happens when top_num e.g. 48 a or 56 b
        return '{}{}.'.format(top_num[:-1], top_num[-1] + ")")

def get_reformatted_tops(top_nums):
    return [reformat_top_num(t) for t in top_nums]

def get_beschluesse_text(session, filename):
    cutter = pdfcutter.PDFCutter(filename=filename)
    session_number = int(session['number'])

    top_nums = [t['number'] for t in session['tops'] if t['top_type'] == 'normal'] # 1, 2, 3a, 3b, 4,....
    reformatted_top_nums = get_reformatted_tops(top_nums) #1., 2., 3a)., 3b)., 4.,...

    #e.g. "1b", ("1b).", "2.")
    for top_num, (current, next_) in zip(top_nums, helper.with_next(reformatted_top_nums)):
        current_top = cutter.filter(auto_regex='^{}\.$'.format(current[:-1].replace(')', '\\)'))) #Escape . in 46. because of regex

        #Sometimes they forgot the . after the TOP
        if not current_top:
            current_top = cutter.filter(auto_regex='^{}$'.format(current[:-1].replace(')', '\\)')))

        next_top = None
        if next_ is not None: #There is a TOP after this one which we have to take as a lower border
            next_top = cutter.filter(auto_regex='^{}\.$'.format(next_[:-1].replace(')', '\\)'))) #Escape . in 46. because of regex
            if not next_top:
                next_top = cutter.filter(auto_regex='^{}$'.format(next_[:-1].replace(')', '\\)'))) #Escape . in 46. because of regex
        senats_text, br_text = getSenatsAndBrTextsForCurrentTOP(cutter, current_top, next_top)
        yield top_num, {'senat': senats_text, 'bundesrat': br_text}

def getSenatsAndBrTextsForCurrentTOP(cutter, current_top, next_top):
    page_heading = 111 #Right under the grey heading of each table
    page_number = 788 #Bottom of each page
    right_title = 616
    right_senat = 892
    right_br = 1160

    if next_top:
        senats_text = cutter.all().filter(
            doc_top__gte=current_top.doc_top -2 ,
            top__gte=page_heading,
            bottom__lt=page_number,
            doc_bottom__lt=next_top.doc_bottom -2,
            left__gt=right_title,
            right__lt=right_senat
        )
        br_text = cutter.all().filter(
            doc_top__gte=current_top.doc_top -2 ,
            top__gte=page_heading,
            doc_bottom__lt=next_top.doc_bottom -2,
            bottom__lt=page_number,
            left__gt=right_senat,
            right__lt=right_br
        )
    else:
        senats_text = cutter.all().filter(
            doc_top__gte=current_top.doc_top -2 ,
            top__gte=page_heading,
            bottom__lt=page_number,
            left__gt=right_title,
            right__lt=right_senat
        )
        br_text = cutter.all().filter(
            doc_top__gte=current_top.doc_top -2 ,
            top__gte=page_heading,
            bottom__lt=page_number,
            left__gt=right_senat,
            right__lt=right_br
        )

    return senats_text.clean_text(), br_text.clean_text()

def get_session(session):
    PDF_URLS = dict(get_pdf_urls())
    #PDF_URLS = {973: PDF_URLS[973]}
    try:
        filename = helper.get_session_pdf_filename(session, PDF_URLS)
    except KeyError:
        return
    return dict(get_beschluesse_text(session, filename))
    #return dict()
