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

INDEX_URL = 'http://suche.transparenz.hamburg.de/?q=Bundesrat&limit=200&sort=score+desc%2Ctitle_sort+asc&extras_registerobject_type=senatmitteil' #Not even close to PDF different Results, so only have to look up one search and not traverse all of them (Like for RP)

BASE_URL='http://suche.transparenz.hamburg.de/'
NUM_RE = re.compile(r'.*-bundesrat-(\d+)\-sitzung-.*')
BR_TEXT_RE = re.compile(r'^Ergebnis BR:')

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):

    #Out: Dict of {sessionNumberOfBR: PDFWebLink} entries
    def _get_pdf_urls(self):
        # Current Session on different page then all the rest

        response = requests.get(INDEX_URL)
        root = etree.fromstring(response.content)
        fields = root.xpath('/html/body/div[1]/div/div/div[2]/div/div[3]/div/div[2]/div[2]/div/ul/li[3]/h3/a') #All Search Result links
        for field in fields:
            redirectLink = BASE_URL + field.attrib['href'] #HA Redirects you to other site before you can download actual PDF
            maybeNum = NUM_RE.search(redirectLink)
            if not maybeNum: #Doesn't link to 
                continue
            num = int(maybeNum.group(1))

            redirectResponse = requests.get(redirectLink)
            redirectRoot = etree.fromstring(redirectResponse.content)
            pdfATag = redirectRoot.xpath('/html/body/div[1]/div/div/div[2]/div/div[3]/div/div[2]/div/ul/li/div/div[2]/div[1]/a')[0] #Only one element with that xpath
            
            pdfLink =  pdfATag.attrib['href']
            yield int(num), pdfLink

#HA don't have all TOPs in PDF, and them again in non-linear order
class SenatsAndBRTextExtractor(PDFTextExtractor.AbstractSenatsAndBRTextExtractor):
    def _extractSenatBRTexts(self, selectionCurrentTOP, selectionNextTOP):
        #TODO Cut Footer
        page_heading = 73 #Bottom of heading on each page
        page_footer = 1195 #Upper of footer on each page
        if not selectionCurrentTOP: #TOP not in PDF -> empty texts
            return "", ""

        #As e.g. HA 985 TOPs not consecutive (After TOP 4 directly TOP 7), one has to find next direct TOP which is lower bound for text
        selectionsNextPDFTOPs = self.cutter.all().filter(
            doc_top__gt  = selectionCurrentTOP.doc_top,
            left__gte = selectionCurrentTOP.left - 10,
            right__lte = selectionCurrentTOP.right + 30, #Offset for subpart
        )
        selectionDirectNextTOP = self._getHighestSelectionNotEmpty(selectionsNextPDFTOPs)# Could be empty, but will be handeled

        #Get indented Text, Senats text is everything intended before next TOP
        TOPRightIndented = self.cutter.all().filter(
            doc_top__gte = selectionCurrentTOP.doc_top -10, #Start with line where TOP stands
            left__gte = selectionCurrentTOP.left + 100,
            top__gte=page_heading, #Ignore Page header
            bottom__lt=page_footer, #Ignore Page Footer
        )

        if selectionDirectNextTOP: #Next TOP as lower bound
            TOPRightIndented = TOPRightIndented.above(selectionDirectNextTOP)

        senats_text = TOPRightIndented.clean_text()
        br_text = senats_text #Whole Text where senat and br and both mentioned, so just copy it
        return senats_text, br_text

    #Fork of DefaultTOPPositionFinder class in PDFTextExtractor File, but need it now for finding alternative next TOP as well, so just copy-pasted it and added not empty Selecion Check.
    def _getHighestSelectionNotEmpty(self, selections): 
        notEmptySelecions = selections.filter(regex="[^ ]+")
        if len(notEmptySelecions) == 0: #min throws error for empty set
            return selections
        return min(notEmptySelecions, key= lambda x: x.doc_top)

#Somehow, with ^ (beginning of selection) when searching for  "TOP 9a" 985 HA, never get any selection. Therefore, remove ^ from regex for Hamburg
class CustomTOPFormatPositionFinderNoPrefix(PDFTextExtractor.CustomTOPFormatPositionFinder):
    #Fork of DefaultTOPPositionFinder._getNumberSelection, only difference regex no "^"
    def _getPrefixStringSelection(self, s):
        escapedS = helper.escapeForRegex(s)
        allSelectionsS = self.cutter.filter(auto_regex='{}'.format(escapedS))# Returns all Selections that have Chunks which *contain* s
        return self._getHighestSelection(allSelectionsS)

#Senats/BR Texts and TOPS in HA all have same formatting
class TextExtractorHolder(PDFTextExtractor.TextExtractorHolder):
    #Can't uncouple Subpart from number TOP (e.g. HA 985 "9a" ) , so use EntwinedNumberSubpartTOPPositionFinder for this
    # Also search for TOPs with prefix "TOP", because only number (e.g. HA 985 TOP 4) is to general to get right selection
    def _getRightTOPPositionFinder(self, top):
        formatTOPsOnlyNumber="TOP {number}[ :]*$" #e.g. HA 985 4 is "TOP 4". Use $ to not match "TOP 1" with "TOP 11", but allow spaces and colons. TODO This $,[] is hacky, because . and ) get escaped by me in DefaultTOPPositionFinder , but $,[],* doesn't and I abuse this.
        #TODO Are there even TOPs in HA with ":" after TOP Number/Subpart? Think so, but couldn't find them anymore
        formatTOPsWithSubpart="{number}{subpart}" #e.g. HA 985 9. a) is "TOP 9a" (Has to start with TOP because I check for prefix) TODO This [] is hacky, because . and ) get escaped by me in DefaultTOPPositionFinder , but [],* doesn't and I abuse this.
        return CustomTOPFormatPositionFinderNoPrefix(self.cutter, formatTOPsOnlyNumber, formatTOPsWithSubpart)

    # Decide if I need custom rules for special session/TOP cases because PDF format isn't consistent
    #In HA all Text Rules are consistent
    def _getRightSenatBRTextExtractor(self, top, cutter): 
        return SenatsAndBRTextExtractor(cutter)

