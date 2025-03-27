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

INDEX_URL = 'https://stm.baden-wuerttemberg.de/de/vertretung-beim-bund/bundesrat/bundesratsinitiativen-und-abstimmungsverhalten'
NUM_RE = re.compile(r'(\d+)\. Sitzung des Bundesrates am .*')

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):

    #Out: Dict of {sessionNumberOfBR: PDFWebLink} entries
    def _get_pdf_urls(self):
        response = requests.get(INDEX_URL)
        root = etree.fromstring(response.content)
        # Updated XPath to target the links in the accordion content for "Abstimmungsverhalten"
        names = root.xpath('//div[@id="accordion-item-28900-content"]//a[contains(@href, ".pdf") and contains(text(), "Sitzung des Bundesrates")]')
        for name in names:
            text = name.text_content()
            num_match = NUM_RE.search(text)
            if num_match:
                num = int(num_match.group(1))
                link = name.attrib['href']
                if not link.startswith('http'):
                    link = 'https://stm.baden-wuerttemberg.de' + link
                yield int(num), link

#Senats/BR Texts and TOPS in BW  all have same formatting
class SenatsAndBRTextExtractor(PDFTextExtractor.AbstractSenatsAndBRTextExtractor):
    def _extractSenatBRTexts(self, selectionCurrentTOP, selectionNextTOP):
        page_heading = 73 #Bottom of heading on each page
        page_footer = 1260 #Upper of footer on each page

        #Get indented Text, Senats text is everything below it, need to check below this because otherwise I also filter Name of TOP
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

        senats_text = self.cutter.all().below(last_indented_with_text)
        if selectionNextTOP:
            senats_text = senats_text.above(selectionNextTOP)

        senats_text = senats_text.clean_text()
        if not senats_text.strip():
            print('empty')

        br_text = "" #BW doesnt repeat BR Text in its PDFs
        return senats_text, br_text

#Senats/BR Texts and TOPS in BW  all have same formatting
class TextExtractorHolder(PDFTextExtractor.TextExtractorHolder):
    def _getRightTOPPositionFinder(self, top):
        return PDFTextExtractor.DefaultTOPPositionFinder(self.cutter, TOPRight=144)# Need this only for BW 985 18a/18b, because "(LFGB)" catches b) + cant have TOPRight too far left, because subparts are part of text "column"
    # Decide if I need custom rules for special session/TOP cases because PDF format isn't consistent
    #In BW all Text Rules are consistent
    def _getRightSenatBRTextExtractor(self, top, cutter): 
        return SenatsAndBRTextExtractor(cutter)
