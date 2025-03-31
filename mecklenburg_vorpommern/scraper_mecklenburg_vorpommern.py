import re
import pdb

import requests
from lxml import html

import pdfcutter

# Import relative Parent Directory for Helper Classes
import os, sys
sys.path.insert(0, os.path.abspath('..')) #Used when call is ` python3 file.py`
sys.path.insert(0, os.path.abspath('.')) #Used when call is ` python3 $COUNTY/file.py`
import helper
import selectionVisualizer as dVis
import PDFTextExtractor
import MainBoilerPlate

INDEX_URL = 'https://www.regierung-mv.de/Landesregierung/wkm/Landesvertretung/Unsere-Aufgaben/Abstimmung/'
BASE_URL='https://www.regierung-mv.de/'
NUM_RE = re.compile(r'(\d+)\.\s*Sitzung') #Updated regex to match new format

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):

    #Out: Dict of {sessionNumberOfBR: PDFWebLink} entries
    def _get_pdf_urls(self):
        response = requests.get(INDEX_URL, headers={'User-Agent': 'Mozilla/5.0'}) #Updated User-Agent
        root = html.fromstring(response.content)

        # Find all links with PDF files
        pdf_links = root.xpath('//a[contains(@href, ".pdf")]')
        
        for link in pdf_links:
            href = link.get('href')
            if not href:
                continue
                
            # Get the text content of the link or its parent element
            link_text = (link.text_content() or '').strip()
            
            # Try to extract session number from the link text
            match = NUM_RE.search(link_text)
            if match:
                num_str = match.group(1)
                try:
                    num = int(num_str)
                    realLink = href if href.startswith('http') else BASE_URL + href
                    yield num, realLink
                except ValueError:
                    continue

#Senats/BR Texts and TOPS in BA  all have same formatting
class TextExtractorHolder(PDFTextExtractor.TextExtractorHolder):

    #Can't uncouple Subpart from number TOP (e.g. BA 985 "9a)." ) , so use CustomTOPFormatPositionFinder for this
    #Still use default format for number only TOPs
    def _getRightTOPPositionFinder(self, top):
        formatNumberOnlyTOPs="{number}" #e.g. MV 985 1. is "1"
        formatTOPsWithSubpart="{number} {subpart})" #e.g. MV 985 9. a) is "9 a)"
        return PDFTextExtractor.CustomTOPFormatPositionFinder(self.cutter, formatNumberOnlyTOP = formatNumberOnlyTOPs, formatSubpartTOP=formatTOPsWithSubpart, TOPRight=160)

    # Decide if I need custom rules for special session/TOP cases because PDF format isn't consistent
    #In BA all Text Rules are consistent
    def _getRightSenatBRTextExtractor(self, top, cutter): 
        senatLeft = 525 #Default
        brLeft = 855
        if 972 <= self.sessionNumber <= 984: #Different Table Sizes
            senatLeft = 505
            brLeft = 825
        #senats and br text are so close together, that pdftohtml puts them in same chunk
        #Therefore, change borders so both senats and br text are put into senats text (never use br text anyway)
        if self.sessionNumber == 977 and top == "10.": 
            return PDFTextExtractor.VerticalSenatsAndBRTextExtractor(cutter,
                    page_heading = 70,
                    page_footer = 1262,
                    senatLeft = senatLeft,
                    brLeft = 1500, #Really huge, so senats + br text inside senat, and br empty
             )


        return PDFTextExtractor.VerticalSenatsAndBRTextExtractor(cutter,
                # Taken from pdftohtml -xml output
                page_heading = 70,
                page_footer = 1262,
                senatLeft = senatLeft,
                brLeft = brLeft,
         )
