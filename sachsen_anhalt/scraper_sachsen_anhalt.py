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

INDEX_URL = 'https://lv.sachsen-anhalt.de/bundesrat/aktuell/'
NUM_RE = re.compile(r'Ergebnisse .* (\d+)\.[ ]?Sitzung des Bundesrates.*')# SA also has "Erläuterungen", don't want those
BR_TEXT_RE = re.compile(r'^[ ]?Ergebnis BR:(.*)')
SENAT_TEXT_RE = re.compile(r'^[ ]?Abstimmung ST:(.*)')
BRSENAT_TEXT_RE = re.compile(r'^[ ]?Ergebnis BR / Abstimmung ST:(.*)')#Space at front is ok+

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):

    #Out: Dict of {sessionNumberOfBR: PDFWebLink} entries
    def _get_pdf_urls(self):
        response = requests.get(INDEX_URL)
        root = etree.fromstring(response.content)
        names = root.xpath('//a')# Somehow, 985 can not be found with almost any xpath, so just get all links and filter by title
        for name in names:
            text = name.text_content()
            maybeNum = NUM_RE.search(text)
            if not maybeNum: #Nothing found -> No link to session PDF
                continue
            num = int(maybeNum.group(1))
            link = name.attrib['href']
            yield int(num), link

#SA uses "46" or "23a" as TOPs instead of "46." and "23. a)"
class TOPPositionFinder(PDFTextExtractor.DefaultTOPPositionFinder):
    def _getTOPSubpartSelection(self, top):
        number, subpart = top.split() #46. b) -> [46., b)]
        formatedTOP = number[:-1] + subpart[:-1] #[46., b)] -> 46b
        topSelection = self._getNumberSelection(formatedTOP) #Not only number, but still works, bu
        topSelection = topSelection.filter(
                left__lte = 160 # Dont match e.g. "980 Sitzung" in title for TOP 9 (happens in 989 TOP 9)
                )
        return topSelection

    def _getNumberSelection(self, number):
        formatedNumber = number.split(".")[0] #46. -> 46 , Done with split because also use it here in SA for Subparts as well
        escapedNum = helper.escapeForRegex(formatedNumber)
        allSelectionsNumber = self.cutter.filter(auto_regex='^{}'.format(escapedNum)).filter(
                left__lte = 160 # Dont match e.g. "980 Sitzung" in title for TOP 9 (happens in 989 TOP 9)
                )
        return self._getHighestSelection(allSelectionsNumber)


class SenatsAndBRTextExtractor(PDFTextExtractor.AbstractSenatsAndBRTextExtractor):

    #First Extract BR Text and only after this Senat Text, because SA sometimes uses "Ergebnis BR / Abstimmung ST:" Combo Blocks and BR Text always above senats text
    def _extractSenatBRTexts(self, selectionCurrentTOP, selectionNextTOP):
        page_heading = 123 #Bottom of heading on each page
        page_footer = 1260 #Upper of footer on each page


        ergebnis_br = self.cutter.filter(auto_regex='^Ergebnis BR').below(selectionCurrentTOP).above(selectionNextTOP)

        br_text = self.cutter.all().filter(
            doc_top__gte=ergebnis_br.doc_top - 1 ,#Relative to all pages
            top__gte=page_heading, #Remove Page header if in current selecion
            bottom__lt=page_footer,
        )

        if selectionNextTOP:
            br_text = br_text.above(selectionNextTOP)

        if "Abstimmung ST" in ergebnis_br.clean_text(): #"Ergebnis BR / Abstimmung ST:" Combo Block -> Senat + BR Text are same

            br_text = br_text.clean_text()
            weg = br_text
            maybe_br_text = BRSENAT_TEXT_RE.search(br_text)
            if maybe_br_text:
                br_text = maybe_br_text.group(1)
            else:
                br_text = ""
            senats_text = br_text

        else: #Separat Senats Text
            abstimmung_st_senat = self.cutter.filter(auto_regex='^Abstimmung ST').below(selectionCurrentTOP).above(selectionNextTOP)

            senats_text = self.cutter.all().filter(
                doc_top__gte=abstimmung_st_senat.doc_top - 1 ,#Relative to all pages
                top__gte=page_heading, #Remove Page header if in current selecion
                bottom__lt=page_footer,
            )
            if selectionNextTOP:
                senats_text = senats_text.above(selectionNextTOP)

            if abstimmung_st_senat: #If no senat text, then .above() would somehow select nothing, which is not what we want
                br_text = br_text.above(abstimmung_st_senat) #For some reason, .above(senats_text) sometimes returns empty selection

            # Filter out "Ergebnis BR" Prefix
            br_text = br_text.clean_text()
            maybe_br_text = BR_TEXT_RE.search(br_text)
            if maybe_br_text:
                br_text = maybe_br_text.group(1)
            else:
                br_text = ""



            # Filter out "Abstimmung ST:" Prefix
            senats_text = senats_text.clean_text()
            maybe_senats_text = SENAT_TEXT_RE.search(senats_text)
            if  maybe_senats_text:
                senats_text = maybe_senats_text.group(1)
            else:
                senats_text = ""

        return senats_text, br_text

class TextExtractorHolder(PDFTextExtractor.TextExtractorHolder):
    def _getRightSenatBRTextExtractor(self, top, cutter):
        return SenatsAndBRTextExtractor(cutter)

    def _getRightTOPPositionFinder(self, top):
        return TOPPositionFinder(self.cutter)
