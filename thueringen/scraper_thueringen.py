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

# Updated URL to the new website
INDEX_URL = 'https://thueringen.de/bundesrat'
BASE_URL = 'https://thueringen.de/'
NUM_RE = re.compile(r'(\d+)\._BR_') 

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):

    #Out: Dict of {sessionNumberOfBR: PDFWebLink} entries
    def _get_pdf_urls(self):
        response = requests.get(INDEX_URL)
        root = etree.fromstring(response.content)

        # Updated XPath to match the new website structure
        links = root.xpath('//a[contains(@href, "fileadmin") and contains(@href, ".pdf")]')
        
        for link in links:
            href = link.attrib['href']
            # Skip if not a PDF link for Bundesrat sessions
            if not 'BR_-_Abstimmungsverhalten-TH' in href:
                continue
                
            # Extract session number from the PDF filename
            match = NUM_RE.search(href)
            if not match:
                continue
                
            num = int(match.group(1))
            
            # Ensure the URL is absolute
            if href.startswith('http'):
                realLink = href
            else:
                realLink = BASE_URL.rstrip('/') + href if not href.startswith('/') else BASE_URL.rstrip('/') + href
                
            yield num, realLink

# TH has sometimes "double rows" , spanning both columns , which are part of both senat and br text (e.g. 986 7). Therefore, have to look at both texts at the same time and decide whether a line is senat text, br text or both
class VerticalSenatsAndBRTextExtractor(PDFTextExtractor.VerticalSenatsAndBRTextExtractor):

    #Out: tuple of clean_text of senats/BR Text
    def _extractSenatBRTexts(self, selectionCurrentTOP, selectionNextTOP):
        if selectionNextTOP is None:
            selectionNextTOP = selectionCurrentTOP.empty()
        #Need for some reason everywhere small offset, dont know why, but it works
        # Senats and BR Text together, no right bound
        senats_br_text = self.cutter.all().filter(
                doc_top__gte = selectionCurrentTOP.doc_top - self.offset, #Also look at row with TOP in it
                doc_top__lt = selectionNextTOP.doc_top - self.offset, # Lower Bound

                top__gte=self.page_heading,
                bottom__lt=self.page_footer,

                left__gte = self.senatLeft - self.offset,
       )
        senats_br_text = sorted(senats_br_text, key = lambda x: x.doc_top ) #Sort selection by appeareance in file, first one first
        senats_text = selectionCurrentTOP.empty()
        br_text = selectionCurrentTOP.empty()
        # selection1 | selection2 is concatenation of 2 selections
        # Used to keep spaces between lines in clean_text() (clean_text concatenation forgets \n's)
        for selection in senats_br_text:
            if selection.left <= self.senatRight and selection.right >= self.brLeft: #Double Row, add to both
                senats_text = senats_text | selection
                br_text = br_text | selection
                continue
            #From here on: Either in senat or br
            if selection.left <= self.senatRight: #Senat Text
                senats_text = senats_text | selection
                continue
            elif self.brLeft <= selection.left: #BR Text
                br_text = br_text | selection
                continue
            else: #shouldn't have text that isn't these ranges
                raise IllegalArgumentException()

        senats_text = senats_text.clean_text()
        br_text = br_text.clean_text()
        return senats_text, br_text

#TH 987 is in the same pdf as TH 988, no next top would add whole 988 to last TOP in 987 
#Therefore, looked what is bottom border for last TOP 987 myself ("998. (Sonder-)Sitzung...")
class VerticalSenatsAndBRTextExtractor987(VerticalSenatsAndBRTextExtractor):
    def _extractSenatBRTexts(self, selectionCurrentTOP, selectionNextTOP):
        selectionNextTOP = self.cutter.all().filter(auto_regex="^988\. \(Sonder-\)Sitzung des Bundesrates$")
        return super()._extractSenatBRTexts(selectionCurrentTOP, selectionNextTOP)

# TH 992 TOPs 40. a) - c), all have same text block with double rows + normal rows, but position of TOPs to far below
#Therefore, looked by hand for upper border("Mitteilung der Kommission") of the block + bottom border("Drucksache 316/20")
class VerticalSenatsAndBRTextExtractor992_40abc(VerticalSenatsAndBRTextExtractor):
    def _extractSenatBRTexts(self, selectionCurrentTOP, selectionNextTOP):

        selectionCurrentTOP = min(self.cutter.all().filter(auto_regex="^Mitteilung der Kommission$"), key= lambda x: x.doc_top)
        selectionNextTOP = self.cutter.all().filter(auto_regex="^Drucksache 316/20 $")
        return super()._extractSenatBRTexts(selectionCurrentTOP, selectionNextTOP)

page_heading = 250

    #Senats/BR Texts and TOPS in BA  all have same formatting
class TextExtractorHolder(PDFTextExtractor.TextExtractorHolder):

    #Can't uncouple Subpart from number TOP (e.g. BA 985 "9a)." ) , so use CustomTOPFormatPositionFinder for this
    #Still use default format for number only TOPs
    def _getRightTOPPositionFinder(self, top):
        formatNumberOnlyTOPs="{number}" #e.g. TH 986 1. is "1"
        formatTOPsWithSubpart="{number} {subpart}" #e.g. TH 986 29. a) is "29 a)"
        return PDFTextExtractor.CustomTOPFormatPositionFinder(self.cutter, formatNumberOnlyTOP = formatNumberOnlyTOPs, formatSubpartTOP=formatTOPsWithSubpart, TOPRight=90 , page_heading = page_heading)

    # Decide if I need custom rules for special session/TOP cases because PDF format isn't consistent
    #In BA all Text Rules are consistent
    def _getRightSenatBRTextExtractor(self, top, cutter): 
        senatLeft = 390 #Default
        brLeft = 615
        page_footer = 1180

        if self.sessionNumber == 987:
            return VerticalSenatsAndBRTextExtractor987(cutter,
                    # Taken from pdftohtml -xml output
                    page_heading = page_heading,
                    page_footer =  page_footer,
                    senatLeft = senatLeft,
                    brLeft = brLeft,
             )
        if self.sessionNumber == 992 and "40" in top:
            return VerticalSenatsAndBRTextExtractor992_40abc(cutter,
                    # Taken from pdftohtml -xml output
                    page_heading = page_heading,
                    page_footer =  page_footer,
                    senatLeft = senatLeft,
                    brLeft = brLeft,
             )
        
        return VerticalSenatsAndBRTextExtractor(cutter,
                # Taken from pdftohtml -xml output
                page_heading = page_heading,
                page_footer =  page_footer,
                senatLeft = senatLeft,
                brLeft = brLeft,
         )
