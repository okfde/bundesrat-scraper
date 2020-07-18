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

INDEX_URL = 'https://www.regierung-mv.de/Landesregierung/stk/Landesvertretung/Unsere-Aufgaben/Abstimmung/'
BASE_URL='https://www.regierung-mv.de/'
NUM_RE = re.compile(r'r (\d+)\.[  ]?Sitzung') #Yes, Session 992 uses a different (unicode) space then all of the other Sessions

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):

    #Out: Dict of {sessionNumberOfBR: PDFWebLink} entries
    def _get_pdf_urls(self):
        response = requests.get(INDEX_URL)
        root = etree.fromstring(response.content)

        names = root.xpath('//a')# Again, more clever xpaths just don't get recognized
        for name in names:
            if ('title' not in name.attrib) or ("Abstimmungsverhalten" not in name.attrib['title']) or ('href' not in name.attrib): #Not a PDF Link
                continue
            link = name.attrib['href']
            title = name.attrib['title']
            #For the oldest sessions, the actual session number is not part of a-Title. Therefore, hard-code it
            if "2. März 2018" in title:
                num = 965
            elif "2. Februar 2018" in title:
                num = 964
            elif "15. Dezember 2017" in title:
                num = 963
            elif "24. November 2017" in title:
                num = 962
            elif "3. November 2017" in title:
                num = 961
            else:
                num = int(NUM_RE.search(title).group(1)) #title formatmore consistent than link names
            if "http" in link : #already full path in a tag (e.g. BA 951), else append to absolute path
               realLink = link
            else:
               realLink = BASE_URL + link 
            yield num, realLink

