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

INDEX_URL = 'https://landesvertretung-brandenburg.de/bundesrat/abstimmungsverhalten-im-bundesrat/'
NUM_RE = re.compile(r'(\d+)\. Sitzung des Bundesrates')
BR_TEXT_RE = re.compile(r'^Ergebnis BR:')

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):

    #Out: Dict of {sessionNumberOfBR: PDFWebLink} entries
    def _get_pdf_urls(self):
        response = requests.get(INDEX_URL)
        root = etree.fromstring(response.content)

        #Have three completely different xpaths for year-tables
        #Therefore, filter (almost) all links (a)
        allLinks = root.xpath('//ul/li/a')
        for name in allLinks:
            text = name.text_content()
            maybeNum = NUM_RE.search(text) #Links to a Bundesrat-PDF?
            if maybeNum: #Also have e.g. "Mitglieder Brandenburgs im Bundesrat" as link -> Filter them out
                num = int(maybeNum.group(1))
                link = name.attrib['href']
                link = link.replace(" ", "%20") #Replace Space with HTML Escape Character
                yield int(num), link
