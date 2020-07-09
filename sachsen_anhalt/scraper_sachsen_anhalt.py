import re
import pdb

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

INDEX_URL = 'https://lv.sachsen-anhalt.de/bundesrat/aktuell/'
NUM_RE = re.compile(r'Ergebnisse .* (\d+)\.[ ]?Sitzung des Bundesrates.*')# SA also has "Erläuterungen", don't want those
BR_TEXT_RE = re.compile(r'^[ ]?Ergebnis BR:(.*)')
SENAT_TEXT_RE = re.compile(r'^[ ]?Abstimmung ST:(.*)')
BRSENAT_TEXT_RE = re.compile(r'^[ ]?Ergebnis BR / Abstimmung ST:(.*)')#Space at front is ok+

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):

    #Out: Dict of {sessionNumberOfBR: PDFWebLink} entries
    def _get_pdf_urls(self):
        response = requests.get(INDEX_URL)
        root = etree.fromstring(response.content)
        names = root.xpath('//a')# Somehow, 985 can not be found with almost any xpath, so just get all links and filter by title
        for name in names:
            text = name.text_content()
            maybeNum = NUM_RE.search(text)
            if not maybeNum: #Nothing found -> No link to session PDF
                continue
            num = int(maybeNum.group(1))
            link = name.attrib['href']
            yield int(num), link
