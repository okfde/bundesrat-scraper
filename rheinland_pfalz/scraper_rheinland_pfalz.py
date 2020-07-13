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

INDEX_URL = 'https://tpp.rlp.de/dataset?q=Abstimmungsverhalten&sort=score+desc%2C+metadata_modified+desc&page={}'
BASE_URL = 'https://tpp.rlp.de'
NUM_RE = re.compile(r'der (\d+)\. Sitzung')#Typos all over the place, so only match little part
BR_TEXT_RE = re.compile(r'^Ergebnis BR:')
#Pixel Range in which TOP Numbers are in PDF
LEFT_TOP = 80
RIGHT_TOP = 150

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):

    #Out: Dict of {sessionNumberOfBR: PDFWebLink} entries
    def _get_pdf_urls(self):
        #Have to check all search result pages, because can't find anywhere a complete list
        #of all "Abstimmungsverhalten" PDFs of RP
        searchPageNum = 1
        while True:
            response = requests.get(INDEX_URL.format(searchPageNum))
            root = etree.fromstring(response.content)
            resultsOnPage = root.xpath('//*[@id="content"]/div[3]/div/div/ul/li/div/h3/a') # All Search Results On this Page

            if len(resultsOnPage) == 0: #Empty Search Page -> Visited everything possible -> break Loop
                break

            for partLink in resultsOnPage: #Only /sharepoint... , not http://www...

                text = partLink.text_content()
                maybeNum = NUM_RE.search(text) #Links to a Bundesrat-PDF?
                if maybeNum: #Also have e.g. "Digitalpakt und Grundgesetzänderung" as link -> Filter them out
                    num = int(maybeNum.group(1))
                    #Have to look at this link again before I can get PDF URL
                    redirectLink = BASE_URL + partLink.attrib['href']
                    responseLink = requests.get(redirectLink)
                    rootLink = etree.fromstring(responseLink.content)
                    link = rootLink.xpath('//*[@id="dataset-resources"]/ul/li/div/ul/li[2]/a')[0].attrib['href'] #There should only be one result with that xpath
                    yield int(num), link

            searchPageNum+=1
