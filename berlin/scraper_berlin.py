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
import selectionVisualizer as dVis
import PDFTextExtractor
import MainBoilerPlate

BASE_URL = 'https://www.berlin.de'
INDEX_URL = 'https://www.berlin.de/rbmskzl/politik/bundesangelegenheiten/aktuelles/artikel.776154.php'

LINK_TEXT_RE = re.compile(r'(\d+)\. Sitzung am .*')

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):
    def _get_pdf_urls(self):
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

class TextExtractorHolder(PDFTextExtractor.TextExtractorHolder):
    def _getRightSenatBRTextExtractor(self, top, cutter): 
        return PDFTextExtractor.VerticalSenatsAndBRTextExtractor(cutter,
            # Taken from pdftohtml -xml output
            page_heading = 135,
            page_footer = 806,
            senatLeft = 585,
            brLeft = 910,
        )
