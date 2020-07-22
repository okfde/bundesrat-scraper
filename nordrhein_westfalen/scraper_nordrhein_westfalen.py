import re
import pdb

import requests
from lxml import html as etree

# Import relative Parent Directory for Helper Classes
import os, sys
sys.path.insert(0, os.path.abspath('..')) #Used when call is ` python3 file.py`
sys.path.insert(0, os.path.abspath('.')) #Used when call is ` python3 $COUNTY/file.py`
import PDFTextExtractor
import MainBoilerPlate

INDEX_URL = 'https://www.mbei.nrw/de/abstimmverhalten'
BASE_URL='https://www.mbei.nrw/'
NUM_RE = re.compile(r'/de/(\d+)-sitzung')

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):

    #Out: Dict of {sessionNumberOfBR: WebLink} entries
    #No PDF but html Links, but still works
    def _get_pdf_urls(self):
        response = requests.get(INDEX_URL)
        root = etree.fromstring(response.content)

        names = root.xpath('/html/body/div[2]/div/div[1]/div/div[2]/div/div[2]/div/div/div/div/div[1]/div/div[1]/div/article/div/div[3]/div/div/p/a') #NRW adds Texts for future sessions, but this xpath doesn't match them
        for name in names:
            link = name.attrib['href']
            num = int(NUM_RE.search(link).group(1))
            if "http" in link : #already full path in a tag (e.g. BA 951), else append to absolute path
               realLink = link
            else:
               realLink = BASE_URL + link 
            yield num, realLink

