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

INDEX_URL = 'https://lv.sachsen-anhalt.de/bundesrat/aktuell/'
NUM_RE = re.compile(r'(\d+)\. Sitzung des Bundesrates')
RESULTS_RE = re.compile(r'Ergebnisse_(\d+)\._BR___Abstimmung_S(achsen-Anhalt|T)\.pdf')
BR_TEXT_RE = re.compile(r'^\s?Ergebnis\sBR:(.*)')
SENAT_TEXT_RE = re.compile(r'^\s?Abstimmung\sST:(.*)')
BRSENAT_TEXT_RE = re.compile(r'^( Hinweis: Die nächste Sitzung des BR wurde für den 03.07.2020, 09.30 Uhr, einberufen.|)[ ]?Ergebnis\sBR[ ]?/\sAbstimmung\sST:(.*)')#Space at front is ok+ , mid space missing for SA 991 1a, long prefix only needed for SA 991 1c strange order selected lines

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):

    #Out: Dict of {sessionNumberOfBR: PDFWebLink} entries
    def _get_pdf_urls(self):
        response = requests.get(INDEX_URL)
        # Use html.fromstring instead of etree.fromstring
        root = html.fromstring(response.content)
        
        # Find all links on the page
        links = root.xpath('//a')
        
        # Dictionary to store session numbers and their PDF links
        session_links = {}
        
        for link in links:
            href = link.get('href', '')
            
            # Check if this is a results PDF link
            if 'Ergebnisse' in href and href.endswith('.pdf'):
                # Extract session number from the PDF filename
                match = RESULTS_RE.search(href)
                if match:
                    session_num = int(match.group(1))
                    # Make sure the URL is absolute
                    if not href.startswith('http'):
                        if href.startswith('/'):
                            href = 'https://lv.sachsen-anhalt.de' + href
                        else:
                            href = 'https://lv.sachsen-anhalt.de/' + href
                    
                    session_links[session_num] = href
        
        # Return session numbers and links as tuples
        for num, link in session_links.items():
            yield num, link

class TOPPositionFinder(PDFTextExtractor.DefaultTOPPositionFinder):
    def _getTOPSubpartSelection(self, top):
        number, subpart = top.split() #46. b) -> [46., b)]
        formatedTOP = number[:-1] + subpart[:-1] #[46., b)] -> 46b
        topSelection = self._getNumberSelection(formatedTOP) #Not only number, but still works, bu
        topSelection = topSelection.filter(
                left__lte = 160 # Dont match e.g. "980 Sitzung" in title for TOP 9 (happens in 989 TOP 9)
                )
        #dVis.showCutter(topSelection)
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


        ergebnis_br = self.cutter.filter(auto_regex='^\s?Ergebnis\sBR').below(selectionCurrentTOP)
        if selectionNextTOP: #Otherwise allways empty if no nextTOP
            ergebnis_br = ergebnis_br.above(selectionNextTOP)

        br_text = self.cutter.all().filter(
            doc_top__gte=ergebnis_br.doc_top - 10 ,#Relative to all pages
            top__gte=page_heading, #Remove Page header if in current selecion
            bottom__lt=page_footer,
        )
        #dVis.showCutter(br_text)

        if selectionNextTOP:
            br_text = br_text.above(selectionNextTOP)

        if "Abstimmung ST" in ergebnis_br.clean_text(): #"Ergebnis BR / Abstimmung ST:" Combo Block -> Senat + BR Text are same

            br_text  = br_text.clean_text()
            maybe_br_text = BRSENAT_TEXT_RE.search(br_text)
            if maybe_br_text:
                br_text = maybe_br_text.group(2)
            else:
                br_text = ""
            senats_text = br_text

        else: #Separat Senats Text
            abstimmung_st_senat = self.cutter.filter(auto_regex='^Abstimmung\sST').below(selectionCurrentTOP).above(selectionNextTOP)

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

        if not senats_text.strip():
            print('empty')
        return senats_text, br_text

class TextExtractorHolder(PDFTextExtractor.TextExtractorHolder):
    def _getRightSenatBRTextExtractor(self, top, cutter):
        return SenatsAndBRTextExtractor(cutter)

    def _getRightTOPPositionFinder(self, top):
        return TOPPositionFinder(self.cutter)
