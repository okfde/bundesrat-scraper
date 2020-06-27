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

INDEX_URL = 'https://landesvertretung-brandenburg.de/bundesrat/abstimmungsverhalten-im-bundesrat/'
NUM_RE = re.compile(r'(\d+)\. Sitzung des Bundesrates')
BR_TEXT_RE = re.compile(r'^Ergebnis BR:')

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):

    #Out: Dict of {sessionNumberOfBR: PDFWebLink} entries
    def _get_pdf_urls(self):
        response = requests.get(INDEX_URL)
        root = etree.fromstring(response.content)

        #Have three completely different xpaths for year-tables
        #Therefore, filter (almost) all links (a)
        allLinks = root.xpath('//ul/li/a')
        for name in allLinks:
            text = name.text_content()
            maybeNum = NUM_RE.search(text) #Links to a Bundesrat-PDF?
            if maybeNum: #Also have e.g. "Mitglieder Brandenburgs im Bundesrat" as link -> Filter them out
                num = int(maybeNum.group(1))
                link = name.attrib['href']
                link = link.replace(" ", "%20") #Replace Space with HTML Escape Character
                yield int(num), link

#Senats/BR Texts and TOPS in BW  all have same formatting
class SenatsAndBRTextExtractor(PDFTextExtractor.AbstractSenatsAndBRTextExtractor):
    def _extractSenatBRTexts(self, selectionCurrentTOP, selectionNextTOP):
        page_heading = 73 #Bottom of heading on each page
        page_footer = 1260 #Upper of footer on each page

        #Get indented Text, Senats/BR text is everything below it, need to check below this because otherwise I also filter Name of TOP
        TOPRightIndented = self.cutter.all().below(selectionCurrentTOP).filter(
            left__gte = selectionCurrentTOP.left + 100 
        )

        if selectionNextTOP:
            TOPRightIndented = TOPRightIndented.above(selectionNextTOP)

        last_indented_with_text = None
        #empty, but present lines below senat text can mess up parsing, so only watch for last non-empty
        for line in TOPRightIndented:
            if line.clean_text(): #empty strings are falsy
                last_indented_with_text = line

        senatsBR_text = self.cutter.all().below(last_indented_with_text)
        if selectionNextTOP:
            senatsBR_text = senatsBR_text.above(selectionNextTOP)

        br_text_title = senatsBR_text.filter(auto_regex='^Ergebnis Bundesrat:')
        senats_text = senatsBR_text.above(br_text_title).clean_text()
        #For some reason the BR Text is always empty when I do:
        #BR_text = senatsBR_text.below(BR_text_title).clean_text()
        br_text = senatsBR_text.filter(
            doc_top__gte=br_text_title.doc_top +1 ,
        ).clean_text()

        return senats_text, br_text

#Senats/BR Texts and TOPS in BW  all have same formatting
class NSTextExtractorHolder(PDFTextExtractor.TextExtractorHolder):
    # Decide if I need custom rules for special session/TOP cases because PDF format isn't consistent
    #In BW all Text Rules are consistent
    def _getRightSenatBRTextExtractor(self, top, cutter): 
        return SenatsAndBRTextExtractor(cutter)

