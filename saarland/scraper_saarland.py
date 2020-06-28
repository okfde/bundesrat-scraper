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

INDEX_URL = 'https://www.saarland.de/SID-C1973F70-4C2D724F/244360.htm'
BASE_URL = 'https://www.saarland.de'
NUM_RE = re.compile(r'(\d+)\.[ ]?Sitzung') #Space is sometimes missing between number and "Sitzung"
BR_TEXT_RE = re.compile(r'^Ergebnis BR:')

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):

    #Out: Dict of {sessionNumberOfBR: PDFWebLink} entries
    def _get_pdf_urls(self):
        response = requests.get(INDEX_URL)
        root = etree.fromstring(response.content)

        fieldsNew = root.xpath('//*[@class="download"]/h4/a')#-974
        fieldsOld = root.xpath('//*[@class="download"]/a')#973-936
        fields = fieldsNew + fieldsOld
        for field in fields:
            text = field.text_content()
            num = int(NUM_RE.search(text).group(1))
            partLink = field.attrib['href'] #Only /dokumente/... in href
            if "pdf" not in partLink: #955 false link -> Breaks Parser
                continue
            link = BASE_URL + partLink
            yield int(num), link
