import json
import itertools
import os
import re
from urllib.parse import urlsplit

import requests
from lxml import html as etree

import pdfcutter

BASE_URL = 'https://www.berlin.de'
INDEX_URL = 'https://www.berlin.de/rbmskzl/politik/bundesangelegenheiten/aktuelles/artikel.776154.php'
PDF_URL = 'https://www.landesvertretung.bremen.de/sixcms/media.php/13/{number}.%20BR-Sitzung_Kurzbericht.pdf'

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


PDF_URLS = dict(get_pdf_urls())

print(PDF_URLS)

