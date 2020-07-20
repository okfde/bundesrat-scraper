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

INDEX_URL = 'https://www.landesregierung-thueringen.de/thueringen-in-berlin/bundesrat/'
BASE_URL='https://www.landesregierung-thueringen.de/'
NUM_RE = re.compile(r'[0]?(\d+)[_-]') 

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):

    #Out: Dict of {sessionNumberOfBR: PDFWebLink} entries
    def _get_pdf_urls(self):
        response = requests.get(INDEX_URL)
        root = etree.fromstring(response.content)

        names = root.xpath('/html/body/main/div[2]/div/section/div/div[1]/div[3]/div/div/div/div/div/div/div/div/p/a')# Again, more clever xpaths just don't get recognized
        for name in names:
            link = name.attrib['href']
            if "www.bundesrat.de" in link: #Link to something irrelevant at bottom of table
                continue
            num = int(NUM_RE.search(link).group(1)) #title formatmore consistent than link names
            if num == 1220: #Somehow, this is the pdf number for TH for session 984
                num = 984
            if "http" in link : #already full path in a tag (e.g. BA 951), else append to absolute path
               realLink = link
            else:
               realLink = BASE_URL + link 
            if num == 987: #TH Merged session 987, 988 into one document -> Return it for 987 as well as 988 (987 by "default" yield
                yield 988, realLink
            yield num, realLink
