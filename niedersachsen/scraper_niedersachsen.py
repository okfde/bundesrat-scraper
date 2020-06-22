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

INDEX_URL = 'https://niedersachsen.de/startseite/politik_staat/bundesrat/abstimmungsverhalten_niedersachsen_im_bundesrat/abstimmungsverhalten-niedersachsens-im-bundesrat-157696.html'

NUM_RE = re.compile(r'(\d+)\. Sitzung des Bundesrates')
LINK_TEXT_RE = re.compile(r'Abstimmungsverhalten und Beschlüsse vom.*') #In 2020 added "Abstimmungsverhalten und Beschlüsse des Bundesrates durch seine Europakammer am 21. April 2020" that I dont want, so added "vom" to regex
SENAT_TEXT_RE = re.compile(r'^Haltung NI\s*:\s*(.*)')
BR_TEXT_RE = re.compile(r'^Ergebnis BR\s*:\s*(.*)')

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):

    #Out: Dict of {sessionNumberOfBR: PDFWebLink} entries
    def _get_pdf_urls(self):
        #Normal parsing NS Site is to hard because HTML is not formatted consistently
        response = requests.get(INDEX_URL)
        root = etree.fromstring(response.content)
        lines = re.split('\n|<br>', response.text)# For 2020, Niedersachsen doesn't break lines anymore between Sitzungen, but rather uses only <br>. Split on both
        meeting_nums = [NUM_RE.search(l).group(1) for l in lines if NUM_RE.search(l)]
        pdf_links = [a.attrib['href'] for a in root.xpath('//a') if a.text != None and LINK_TEXT_RE.search(a.text)]
        for (num, link) in zip(meeting_nums, pdf_links):
            yield int(num), link

# For Niedersachsen 970, All two digit Numbers of TOP are cut into two lines. Handle here for 10. to 97.
class TOPPositionFinder970MultiDigitNumber(PDFTextExtractor.DefaultTOPPositionFinder):
    def _getNumberSelection(self, number):
        # Split by PDF Pattern 10-97
        firstDigits = number[:-2] # 123. -> 12
        lastDigitDot = number[-2:] # 12. -> 2. 
        return self._getNumberSelectionSplittedNumber(firstDigits, lastDigitDot)

    #Used when Number is split into different chunks/lines in PDF
    #e.g. 10. -> 1\n0. in NS 970 10.,
    #Chunk of TOP with only number is defined as highest chunk with *first* part of the number
    #Main Idea: Go through all chunks x starting with *last* part of number, from highest to lowest. If "slightly" above this chunk there is a line y that starts with *first* part of number, return the first satisfying y as number chunk (by Definition)
    def _getNumberSelectionSplittedNumber(self, firstPartNumber, lastPartNumber):
        escapedFirstPartNumber = helper.escapeForRegex(firstPartNumber) #Not super necessary, but doesn't hurt
        escapedLastPartNumber = helper.escapeForRegex(lastPartNumber) #Here necessary because of dot

        #Get all chunks that start with *last* part of number. 
        allSelectionsLastPartNumber = self.cutter.filter(auto_regex='^{}'.format(escapedLastPartNumber))# Returns all Selections that have Chunks which start with the number

        #Sort them from highest to lowest
        sortedAllSelecionsLastPartNumber = sorted(allSelectionsLastPartNumber, key= lambda x: x.doc_top) #Sort by appearance

        firstPartNumberSelection = None
        for selection in sortedAllSelecionsLastPartNumber: #Start with highest selection
            #All Chunks that are "slightly" (strict) above last part number chunk
            aboveSelections = self.cutter.all().filter(
                doc_top__gte=selection.doc_top - 50 ,
                doc_bottom__lte = selection.doc_top ,
            )
            #Any Chunk slightly above that starts with *first* part of number?
            maybeFirstPartNumberAboveSelection = aboveSelections.filter(auto_regex='^{}$'.format(escapedFirstPartNumber))

            if len(maybeFirstPartNumberAboveSelection) == 1: #There is exactly one such selection
                #Therefore. return it (per Definition) as number chunk and stop
                firstPartNumberSelection = maybeFirstPartNumberAboveSelection
                break
        return firstPartNumberSelection

# For Niedersachsen 970, All tow digit Numbers of TOP from 10. are cut into two lines. Handle this for TOPs 98. until end
class TOPPositionFinder970MultiDigitNumber2(TOPPositionFinder970MultiDigitNumber):
    def _getNumberSelection(self, number):
        #e.g. 98. -> 98\n. in NS 970 98.,
        firstTwoDigits = number[:2] # 123. -> 12, 10 -> 10
        lastPartNumber = number[2:] # 98. -> . , 107. -> 7.   (Only part in same chunk)

        # Do same as for 10-97 with different split of number
        return self._getNumberSelectionSplittedNumber(firstTwoDigits, lastPartNumber)

#Senats/BR Texts in NS all have same formatting
class SenatsAndBRTextExtractor(PDFTextExtractor.AbstractSenatsAndBRTextExtractor):
    def _extractSenatBRTexts(self, selectionCurrentTOP, selectionNextTOP):
        page_heading = 73 #Bottom of heading on each page
        page_footer = 1260 #Upper of footer on each page
        senats = self.cutter.filter(auto_regex='^Haltung NI')
        senats = senats.below(selectionCurrentTOP)
        if selectionNextTOP:
            senats = senats.above(selectionNextTOP)

        #INFO Space relevant because without Rules broke because of "Ergebnisse" in NS 970 70a
        #INFO But can't filter 'Ergebnis BR' directly, because these two words are sometimes in different chunks
        ergebnis_br = self.cutter.filter(auto_regex='^Ergebnis ').below(selectionCurrentTOP)

        if selectionNextTOP:
            ergebnis_br = ergebnis_br.above(selectionNextTOP)

        #cutter.above() is strict, can get it non strict by going a little bit higher
        senats_text = self.cutter.all().filter(
            doc_top__gte=senats.doc_top - 1 ,
            top__gte=page_heading,
            bottom__lt=page_footer,
        )

        br_text = self.cutter.all().filter(
            doc_top__gte=ergebnis_br.doc_top - 1 ,#Relative to all pages
            top__gte=page_heading,
            bottom__lt=page_footer,
        )

        if selectionNextTOP:
            br_text = br_text.above(selectionNextTOP)
            senats_text = senats_text.above(ergebnis_br)


        #Cut away "Haltung NI:" and "Ergebnis BR:" from text
    #    print("current_top", current_top.clean_text())
        senats_text = senats_text.clean_text()
    #    print("next top", next_top)
    #    print("senats_text", senats_text)
        if senats_text != "":
            senats_text = SENAT_TEXT_RE.search(senats_text).group(1)

        br_text = br_text.clean_text()
    #    print("br_text", br_text)
        if br_text != "":
            br_text = BR_TEXT_RE.search(br_text).group(1)
        return senats_text, br_text

class NSTextExtractorHolder(PDFTextExtractor.TextExtractorHolder):

    # Decide if I need custom rules for special session/TOP cases because PDF format isn't consistent
    # For NS I need custom TOP Finder Rules (but no custom Senats/BR Text Finder Rules)
    def _getRightTOPPositionFinder(self, top):
        if self.sessionNumber == 970 and 10 <= int(top.split()[0][:-1]) <= 97:
            return TOPPositionFinder970MultiDigitNumber(self.cutter)
        elif self.sessionNumber == 970 and int(top.split()[0][:-1]) >= 98 :
            return TOPPositionFinder970MultiDigitNumber2(self.cutter)
        return PDFTextExtractor.DefaultTOPPositionFinder(self.cutter)

    # Decide if I need custom rules for special session/TOP cases because PDF format isn't consistent
    #In NS all Text Rules are consistent
    def _getRightSenatBRTextExtractor(self, top, cutter): 
        return SenatsAndBRTextExtractor(cutter)
