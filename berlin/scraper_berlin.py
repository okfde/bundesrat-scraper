import json
import re

import requests
from lxml import html as etree

import pdfcutter
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
        print(num)
        link = field.xpath('div[3]/a')[0]
        yield num, BASE_URL + link.attrib['href']


def get_beschluesse_text(session, filename):
    cutter = pdfcutter.PDFCutter(filename=filename)
    session_number = int(session['number'])

    top_nums = [t['number'] for t in session['tops'] if t['top_type'] == 'normal'] # 1, 2, 3a, 3b, 4,....
#    reformatted_top_nums = get_reformatted_tops(top_nums) #1., 2., 3. a), 3. b), 4.,...
    return {}




def get_session(session):
    PDF_URLS = dict(get_pdf_urls())
    try:
        filename = helper.get_session_pdf_filename(session, PDF_URLS)
    except KeyError:
        return
    return dict(get_beschluesse_text(session, filename))
