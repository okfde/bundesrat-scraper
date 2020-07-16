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

INDEX_URL = 'http://suche.transparenz.hamburg.de/?q=Bundesrat&limit=200&sort=score+desc%2Ctitle_sort+asc&extras_registerobject_type=senatmitteil' #Not even close to PDF different Results, so only have to look up one search and not traverse all of them (Like for RP)

BASE_URL='http://suche.transparenz.hamburg.de/'
NUM_RE = re.compile(r'.*-bundesrat-(\d+)\-sitzung-.*')
BR_TEXT_RE = re.compile(r'^Ergebnis BR:')

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):

    #Out: Dict of {sessionNumberOfBR: PDFWebLink} entries
    def _get_pdf_urls(self):
        # Current Session on different page then all the rest

        response = requests.get(INDEX_URL)
        root = etree.fromstring(response.content)
        fields = root.xpath('/html/body/div[1]/div/div/div[2]/div/div[3]/div/div[2]/div[2]/div/ul/li[3]/h3/a') #All Search Result links
        for field in fields:
            redirectLink = BASE_URL + field.attrib['href'] #HA Redirects you to other site before you can download actual PDF
            maybeNum = NUM_RE.search(redirectLink)
            if not maybeNum: #Doesn't link to 
                continue
            num = int(maybeNum.group(1))

            redirectResponse = requests.get(redirectLink)
            redirectRoot = etree.fromstring(redirectResponse.content)
            pdfATag = redirectRoot.xpath('/html/body/div[1]/div/div/div[2]/div/div[3]/div/div[2]/div/ul/li/div/div[2]/div[1]/a')[0] #Only one element with that xpath
            
            pdfLink =  pdfATag.attrib['href']
            yield int(num), pdfLink

