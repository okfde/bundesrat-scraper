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

class TOPPositionFinder(PDFTextExtractor.DefaultTOPPositionFinder):

    #SL formats .e.g. 973 25 a) as 25a. So use different format and only search for this 25a. alone (without number search before)
    def _getTOPSubpartSelection(self, top):
        number, subpart = top.split() #46. b) -> [46., b)]
        TOPRightFormat = number[:-1] + subpart.replace(")", ".") # 46. b) -> 46b.
        topSelection = self._getNumberSelection(TOPRightFormat) #Although not only a number, this still works
        return topSelection

#Senats/BR Texts and TOPS in BW  all have same formatting
class SenatsAndBRTextExtractor(PDFTextExtractor.AbstractSenatsAndBRTextExtractor):

    def _extractSenatBRTexts(self, selectionCurrentTOP, selectionNextTOP):
        page_heading = 73 #Bottom of heading on each page
        page_footer = 1260 #Upper of footer on each page

        #Get indented Text, Senats/BR text is everything below it, need to check below this because otherwise I also filter Name of TOP

        #Because selectionNextTOP is never empty (but could be empty selector), I can use it without checking if it is None or empty
        senatTitleSelection = self.cutter.all().filter(auto_regex="^Haltung SL:").below(selectionCurrentTOP).above(selectionNextTOP)
        BRTitleSelection = self.cutter.all().filter(auto_regex="^Ergebnis BR:").below(selectionCurrentTOP).above(selectionNextTOP)

        senats_text = self.cutter.all().filter(
                doc_top__gte = senatTitleSelection.doc_top-1 #Senats Text starts next to title
        ).above(BRTitleSelection).clean_text()
        br_text = self.cutter.all().filter(
                doc_top__gte = BRTitleSelection.doc_top-1, #BR Text starts next to title
                auto_regex="^[^_]+" #Each TOP ends with ----- line, filter this one out
        ).above(selectionNextTOP).clean_text()

        # Although in 973 TOP 9, senats_text ends with many blank lines, in JSON they are somehow striped
        return senats_text, br_text

#Senats/BR Texts and TOPS in SL all have same formatting
class TextExtractorHolder(PDFTextExtractor.TextExtractorHolder):

    def _getRightTOPPositionFinder(self, top):
        return TOPPositionFinder(self.cutter)

    # Decide if I need custom rules for special session/TOP cases because PDF format isn't consistent
    #In BW all Text Rules are consistent
    def _getRightSenatBRTextExtractor(self, top, cutter): 
        return SenatsAndBRTextExtractor(cutter)