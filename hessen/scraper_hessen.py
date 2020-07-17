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

INDEX_URL = 'https://staatskanzlei.hessen.de/berlin-europa/hessen-berlin/bundesrat/abstimmungsverhalten-und-ergebnislisten'

BASE_URL='http://suche.transparenz.hamburg.de/'
NUM_RE = re.compile(r'.*[/_](\d+)[.]?_.*\.pdf') #Link from 965 completely different than all other links
BR_TEXT_RE = re.compile(r'^Ergebnis BR:')

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):

    #Out: Dict of {sessionNumberOfBR: PDFWebLink} entries
    def _get_pdf_urls(self):
        # Current Session on different page then all the rest

        response = requests.get(INDEX_URL)
        root = etree.fromstring(response.content)
        yearFields = root.xpath('/html/body/div[1]/div[3]/section/div[1]/div/div/div/div[3]/div/div/div/div[2]/div/div/span/div[3]/div/div/div/a') #Get Links to year sections
        for yearField in yearFields:
            yearLink = yearField.attrib['href']
            yearResponse = requests.get(yearLink, headers={'User-Agent': '-'}) #Without User-Agent, get 403 Forbidden for 2020 Page (but not for 2018/2019)
            yearRoot = etree.fromstring(yearResponse.content)
            if "2018" in yearLink: #Extra redirect in this year

                sessionInYearFields = yearRoot.xpath('/html/body/div[1]/div[3]/section/div[1]/div/div/div/div[2]/div/div/div/div[2]/div/div/span/div[3]/div/div/div/a') #All Sessions in given year
                for sessionField in sessionInYearFields:
                    redirectLink = sessionField.attrib['href'] #Link to Website, where I can find actual PDF Link
                    redirectResponse = requests.get(redirectLink)
                    redirectRoot = etree.fromstring(redirectResponse.content)
                    pdfField = redirectRoot.xpath('/html/body/div[1]/div[3]/section/div[1]/div/div/div/div/div/div/article/div[1]/ul/li/div/div/span/a')[0] #Exactly one field with this xpath
                    sessionPDFLink = pdfField.attrib['href']
                    num = int(NUM_RE.search(sessionPDFLink).group(1))
                    yield int(num), sessionPDFLink
            else: #2019- no second redirect anymore
                sessionInYearFields = yearRoot.xpath('/html/body/div[1]/div[3]/section/div[1]/div/div/div/div/div/div/article/div[1]/div[2]/div/div/div/div[2]/div/div/div/span/a') #All Sessions in given year (2019-)
                for sessionField in sessionInYearFields:
                    sessionPDFLink = sessionField.attrib['href']
                    num = int(NUM_RE.search(sessionPDFLink).group(1))
                    yield int(num), sessionPDFLink

#For HE 985, Subparts are on next line below actual number of TOP. Therefore, first line of texts gets cut away or first line next TOP is added. Add Extra Offsets to fix this
class VerticalSenatsAndBRTextExtractor985(PDFTextExtractor.VerticalSenatsAndBRTextExtractor):

    #Out: tuple of clean_text of senats/BR Text
    def _extractSenatBRTexts(self, selectionCurrentTOP, selectionNextTOP):
        if selectionNextTOP is None:
            selectionNextTOP = selectionCurrentTOP.empty()
        offsetSubpartCurrentTOPHasSubpart = 0 #Offset to get first line of text
        offsetSubpartNextTOPHasSubpart = 0 #Offset to remove first line of text next top

        LETTER_RE = re.compile(r'[a-z]')
        if LETTER_RE.search(selectionCurrentTOP.clean_text()): # Current TOP has Subpart -> add offset for first line
            offsetSubpartCurrentTOPHasSubpart = 25
        if LETTER_RE.search(selectionNextTOP.clean_text()): # Next TOP has Subpart -> remove offset for first line next TOP
            offsetSubpartNextTOPHasSubpart = 25
        #Need for some reason everywhere small offset, dont know why, but it works
        senats_text = self.cutter.all().filter(
                doc_top__gte = selectionCurrentTOP.doc_top - self.offset - offsetSubpartCurrentTOPHasSubpart, #Also look at row with TOP in it
                doc_top__lt = selectionNextTOP.doc_top - self.offset - offsetSubpartNextTOPHasSubpart, # Lower Bound

                top__gte=self.page_heading,
                bottom__lt=self.page_footer,

                left__gte = self.senatLeft - self.offset,
                right__lt = self.senatRight + self.offset,
        )
        br_text = self.cutter.all().filter(
                doc_top__gte = selectionCurrentTOP.doc_top - self.offset - offsetSubpartCurrentTOPHasSubpart, #Also look at row with TOP in it
                doc_top__lt = selectionNextTOP.doc_top - self.offset - offsetSubpartNextTOPHasSubpart, # Lower Bound

                top__gte=self.page_heading,
                bottom__lt=self.page_footer,

                left__gte = self.brLeft - self.offset,
                right__lt = self.brRight + self.offset,
        )

        senats_text = senats_text.clean_text()
        br_text = br_text.clean_text()
        return senats_text, br_text

#TODO Same class already used in HA - merge
#Somehow, with ^ (beginning of selection) when searching for  "30, 31, 55" 992 HE, never get any selection. Therefore, remove ^ from regex for Hamburg
class CustomTOPFormatPositionFinderNoPrefix(PDFTextExtractor.CustomTOPFormatPositionFinder):
    #Fork of DefaultTOPPositionFinder._getNumberSelection, only difference regex no "^"
    def _getPrefixStringSelection(self, s):
        escapedS = helper.escapeForRegex(s)
        allSelectionsS = self.cutter.filter(auto_regex='{}'.format(escapedS))# Returns all Selections that have Chunks which *contain* s
        return self._getHighestSelection(allSelectionsS)


#Senats/BR Texts and TOPS in HE all have same formatting
class TextExtractorHolder(PDFTextExtractor.TextExtractorHolder):

    #Can't uncouple Subpart from number TOP (e.g. BA 985 "9a)." ) , so use CustomTOPFormatPositionFinder for this
    #Still use default format for number only TOPs
    def _getRightTOPPositionFinder(self, top):
        if self.sessionNumber == 985: #In 985, subpart always on newline to Number. DefaultTOPPositionFinder can handle this
            return PDFTextExtractor.DefaultTOPPositionFinder(self.cutter)
        formatTOPsWithSubpart="{number} {subpart}." #e.g. HE 965 13. b) is "13 b." - Default
        if self.sessionNumber == 965:
            formatTOPsWithSubpart="{number} {subpart}." #e.g. HE 965 13. b) is "13 b."
            if top == "14. a)":
                formatTOPsWithSubpart="{number}{subpart}/" #e.g. HE 965 14. a) is "14a/"
            elif top == "14. b)":
                formatTOPsWithSubpart="{number}{subpart}" #e.g. HE 965 14. b) is "14b"
        elif 985 <= self.sessionNumber <= 988 :
            formatTOPsWithSubpart="{number} {subpart})" #e.g. HE 986 32. b) is "32 b)"
        elif (self.sessionNumber == 992) and (top in ["30.", "31.", "55."]):# They forgot point after number there but e.g. 31 is ubiquious ("Drucksache 331/20" in TOP 2.)
            formatNumberOnlyTOP="{number}"
            rightBorderTOP = 237 # Taken from pdftohtml -xml output
            return CustomTOPFormatPositionFinderNoPrefix(self.cutter, TOPRight=rightBorderTOP, formatNumberOnlyTOP=formatNumberOnlyTOP, formatSubpartTOP=formatTOPsWithSubpart) #Subpart format not necessary , but more consistent like this

        return PDFTextExtractor.CustomTOPFormatPositionFinder(self.cutter, formatSubpartTOP=formatTOPsWithSubpart)
#        return PDFTextExtractor.DefaultTOPPositionFinder(self.cutter)

#        formatNumberOnlyTOPs="{number}"
#        formatTOPsWithSubpart="{number}{subpart})." #e.g. BA 985 9. a) is "9a)."
#        return PDFTextExtractor.CustomTOPFormatPositionFinder(self.cutter, formatSubpartTOP=formatTOPsWithSubpart)

    # Decide if I need custom rules for special session/TOP cases because PDF format isn't consistent
    #In BA all Text Rules are consistent
    def _getRightSenatBRTextExtractor(self, top, cutter): 
        if self.sessionNumber == 985:
            return VerticalSenatsAndBRTextExtractor985(cutter,
                # Taken from pdftohtml -xml output
                page_heading = 95,
                page_footer = 825,
                senatLeft = 409,
                brLeft = 800,
            )
        #HE 965 14a/b have very strange format together
        if (self.sessionNumber == 965) and top == "14. b)":
            return VerticalSenatsAndBRTextExtractor985(cutter,
                # Taken from pdftohtml -xml output
                page_heading = 95,
                page_footer = 825,
                senatLeft = 409,
                brLeft = 800,
            )

        return PDFTextExtractor.VerticalSenatsAndBRTextExtractor(cutter,
                # Taken from pdftohtml -xml output
                page_heading = 95,
                page_footer = 825,
                senatLeft = 409,
                brLeft = 800,
         )

