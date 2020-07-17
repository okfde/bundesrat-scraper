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

INDEX_URL = 'https://staatskanzlei.hessen.de/berlin-europa/hessen-berlin/bundesrat/abstimmungsverhalten-und-ergebnislisten'

BASE_URL='http://suche.transparenz.hamburg.de/'
NUM_RE = re.compile(r'.*[/_](\d+)[.]?_.*\.pdf') #Link from 965 completely different than all other links
BR_TEXT_RE = re.compile(r'^Ergebnis BR:')

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):

    #Out: Dict of {sessionNumberOfBR: PDFWebLink} entries
    def _get_pdf_urls(self):
        # Current Session on different page then all the rest

        response = requests.get(INDEX_URL)
        root = etree.fromstring(response.content)
        yearFields = root.xpath('/html/body/div[1]/div[3]/section/div[1]/div/div/div/div[3]/div/div/div/div[2]/div/div/span/div[3]/div/div/div/a') #Get Links to year sections
        for yearField in yearFields:
            yearLink = yearField.attrib['href']
            yearResponse = requests.get(yearLink, headers={'User-Agent': '-'}) #Without User-Agent, get 403 Forbidden for 2020 Page (but not for 2018/2019)
            yearRoot = etree.fromstring(yearResponse.content)
            if "2018" in yearLink: #Extra redirect in this year

                sessionInYearFields = yearRoot.xpath('/html/body/div[1]/div[3]/section/div[1]/div/div/div/div[2]/div/div/div/div[2]/div/div/span/div[3]/div/div/div/a') #All Sessions in given year
                for sessionField in sessionInYearFields:
                    redirectLink = sessionField.attrib['href'] #Link to Website, where I can find actual PDF Link
                    redirectResponse = requests.get(redirectLink)
                    redirectRoot = etree.fromstring(redirectResponse.content)
                    pdfField = redirectRoot.xpath('/html/body/div[1]/div[3]/section/div[1]/div/div/div/div/div/div/article/div[1]/ul/li/div/div/span/a')[0] #Exactly one field with this xpath
                    sessionPDFLink = pdfField.attrib['href']
                    num = int(NUM_RE.search(sessionPDFLink).group(1))
                    yield int(num), sessionPDFLink
            else: #2019- no second redirect anymore
                sessionInYearFields = yearRoot.xpath('/html/body/div[1]/div[3]/section/div[1]/div/div/div/div/div/div/article/div[1]/div[2]/div/div/div/div[2]/div/div/div/span/a') #All Sessions in given year (2019-)
                for sessionField in sessionInYearFields:
                    sessionPDFLink = sessionField.attrib['href']
                    num = int(NUM_RE.search(sessionPDFLink).group(1))
                    yield int(num), sessionPDFLink
