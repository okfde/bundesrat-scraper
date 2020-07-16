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

INDEX_URL = 'https://www.bayern.de/staatsregierung/bayern-in-berlin/bayern-im-bundesrat_/bayerische-voten-im-bundesrat/'
BASE_URL='https://www.bayern.de'
NUM_RE = re.compile(r'.*/.*[Aa]bstimmungsverhalten-(\d+).*.pdf$')

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):

    #Out: Dict of {sessionNumberOfBR: PDFWebLink} entries
    def _get_pdf_urls(self):
        response = requests.get(INDEX_URL)
        root = etree.fromstring(response.content)
        names = root.xpath('/html/body/div[1]/div[6]/div/div[2]/div[5]/div[1]/div[3]/div[3]/div/div/ul/li/a')
        names += root.xpath('/html/body/div[1]/div[6]/div/div[2]/div[5]/div[1]/div[3]/div[3]/div/div[1]/ul/li[4]/span/a') #986 has extra span, there need to add it manually
        names += root.xpath('/html/body/div[1]/div[6]/div/div[2]/div[5]/div[1]/div[3]/div[3]/div/div[7]/p[2]/a') #2014 needs special treatment
        for name in names:
            link = name.attrib['href']
            num = int(NUM_RE.search(link).group(1))
            if "http" in link : #already full path in a tag (e.g. BA 951), else append to absolute path
                realLink = link
            else:
                realLink = BASE_URL + link 
            yield num, realLink

#Senats/BR Texts and TOPS in BA  all have same formatting
class TextExtractorHolder(PDFTextExtractor.TextExtractorHolder):

    #Can't uncouple Subpart from number TOP (e.g. BA 985 "9a)." ) , so use CustomTOPFormatPositionFinder for this
    #Still use default format for number only TOPs
    def _getRightTOPPositionFinder(self, top):
        formatTOPsWithSubpart="{number}{subpart})." #e.g. BA 985 9. a) is "9a)."
        if self.sessionNumber == 940 and top == "6. b)":
            formatTOPsWithSubpart="{number}{subpart})" #e.g. 6b) in BA 940
        return PDFTextExtractor.CustomTOPFormatPositionFinder(self.cutter, formatSubpartTOP=formatTOPsWithSubpart)

    # Decide if I need custom rules for special session/TOP cases because PDF format isn't consistent
    #In BA all Text Rules are consistent
    def _getRightSenatBRTextExtractor(self, top, cutter): 
        return PDFTextExtractor.VerticalSenatsAndBRTextExtractor(cutter,
                # Taken from pdftohtml -xml output
                page_heading = 129,
                page_footer = 773,
                senatLeft = 565,
                brLeft = 855,
         )



