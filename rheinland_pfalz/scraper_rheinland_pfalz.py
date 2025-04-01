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

# Updated to use the Bundesrat tag page instead of search
INDEX_URL = 'https://tpp.rlp.de/dataset/?tags=Bundesrat&page={}'
BASE_URL = 'https://tpp.rlp.de'
NUM_RE = re.compile(r'der (\d+)\. Sitzung')#Typos all over the place, so only match little part
BR_TEXT_RE = re.compile(r'^Ergebnis BR:')
#Pixel Range in which TOP Numbers are in PDF
LEFT_TOP = 80
RIGHT_TOP = 150

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):

    #Out: Dict of {sessionNumberOfBR: PDFWebLink} entries
    def _get_pdf_urls(self):
        #Have to check all search result pages, because can't find anywhere a complete list
        #of all "Abstimmungsverhalten" PDFs of RP
        searchPageNum = 1
        while True:
            response = requests.get(INDEX_URL.format(searchPageNum))
            root = etree.fromstring(response.content)
            
            # Updated XPath to match the new website structure
            # Now looking for h2 elements with links that contain session information
            resultsOnPage = root.xpath('//h2/a[contains(@href, "eakte")]')
            
            if len(resultsOnPage) == 0: #Empty Search Page -> Visited everything possible -> break Loop
                break

            for partLink in resultsOnPage:
                text = partLink.text_content()
                maybeNum = NUM_RE.search(text) #Links to a Bundesrat-PDF?
                if maybeNum: #Also have e.g. "Digitalpakt und Grundgesetzänderung" as link -> Filter them out
                    num = int(maybeNum.group(1))
                    #Have to look at this link again before I can get PDF URL
                    redirectLink = partLink.attrib['href']
                    if not redirectLink.startswith(BASE_URL):
                        redirectLink = BASE_URL + redirectLink
                        
                    responseLink = requests.get(redirectLink)
                    rootLink = etree.fromstring(responseLink.content)
                    
                    # Updated XPath to find the PDF download link
                    # Looking for the direct download link with PDF extension
                    pdf_links = rootLink.xpath('//a[contains(@href, ".pdf") and contains(@href, "download")]/@href')
                    
                    if pdf_links:
                        # Take the first PDF download link found
                        link = pdf_links[0]
                        print(f"Found session {num} with PDF link: {link}")
                        yield int(num), link

            searchPageNum+=1

#Don't have BR Text in RP PDFs
#RP splits its PDF in two parts:
#In upper part, all TOPs have their senat text below them.
#In the lower part (after "Umdruck M/YYYY ,,Grüne Liste"), the senat text is grouped and is *above* the TOP Group
class SenatsAndBRTextExtractor(PDFTextExtractor.AbstractSenatsAndBRTextExtractor):

    def __init__(self, cutter):
        self.umdruckSelection = cutter.filter(auto_regex="^Umdruck")[0] #Starts lower part of pdf, good to distinguish upper and lower part
        self.selectionsPartTitles, self.dictPartTitleToSenatsText = self.computeParts(cutter) #Gets recomputed every time, but don't care
        super().__init__(cutter)

    #Compute Dict that maps (in lower part) the roman numeral (stripped) of the group to the Group Senats Text it belongs to (i.e. "I" -> "Keine Zustimmung")
    # This dict is used for every TOP in the lower part to find right senats text faster
    #Also return the selection of all roman numerals so that I can check faster in which group a TOP belongs
    def computeParts(self, cutter):
        #Find all roman numerals
        partsTitleSelections = cutter.all().filter(auto_regex='^[IVX]+\.$')
        dictTitleToSenatsText = {}
        for titleSelection in partsTitleSelections:
            #Find for each roman numeral first TOP below it -> in between is senat text
            selectionsNextPDFTOPs = cutter.all().filter(
                doc_top__gt  = titleSelection.doc_top,
                left__gte = LEFT_TOP, #Only get TOPs
                right__lte = RIGHT_TOP #Only get TOPs
            )
            selectionDirectNextTOP = self._getHighestSelectionNotEmpty(selectionsNextPDFTOPs)# Could be empty, but this is handeled by super method as well
            senats_text = cutter.all().below(titleSelection).above(selectionDirectNextTOP)
            title = titleSelection.clean_text().strip()

            dictTitleToSenatsText[title] = senats_text.clean_text()
        return partsTitleSelections, dictTitleToSenatsText

    def _extractSenatBRTexts(self, selectionCurrentTOP, selectionNextTOP):
        page_heading = 73 #Bottom of heading on each page
        page_footer = 1260 #Upper of footer on each page

        if len(selectionCurrentTOP) == 0: #Some TOPs not present e.g. RP 982 1.
            return "", ""

        if self.inUpperPart(selectionCurrentTOP):
            return self.parseLikeUpperPart(selectionCurrentTOP, selectionNextTOP)
        return self.parseLikeLowerPart(selectionCurrentTOP)

    #Upper Part means, above "Umdruck" Title. After this, format of TOPs/Senats Text completely different
    def inUpperPart(self, TOPSelection):
        return TOPSelection.doc_top < self.umdruckSelection.doc_top

    #In Upper Part, senat text directly below TOP
    def parseLikeUpperPart(self, selectionCurrentTOP, selectionNextTOP):
        selectionDirectNextTOP = self.computeDirectNextTOP(selectionCurrentTOP, selectionNextTOP)

        #Get indented Text, Senats/BR text is everything below it, need to check below this because otherwise I also filter Name of TOP
        TOPRightIndented = self.cutter.all().below(selectionCurrentTOP).filter(
            left__gte = selectionCurrentTOP.left + 100
        )

        if selectionDirectNextTOP:
            TOPRightIndented = TOPRightIndented.above(selectionDirectNextTOP)

        #Find last indented line as upper bound for senat text
        last_indented_with_text = None
        #empty, but present lines below senat text can mess up parsing, so only watch for last non-empty
        for line in TOPRightIndented:
            if line.clean_text(): #empty strings are falsy
                last_indented_with_text = line

        senats_text = self.cutter.all().below(last_indented_with_text)
        if selectionDirectNextTOP:
            senats_text = senats_text.above(selectionDirectNextTOP)
        senats_text = senats_text.clean_text()
        if not senats_text.strip():
            print('empty')
        return senats_text, "" #RP no BR Text in PDFs

    #Ordering TOPs very special, so have to find next TOP again (e.g. session 985 , first TOP 2., then directly 4.
    #However, in e.g. 982, the subparts are indented and not distinguishable from a normal line -> If current and Next TOP contain subpart, then just take the already computed next TOP as direct next TOP
    #This works because RP doesn't seem to put one part  of subpart of TOP in upper and other one in lower part, they always stay together
    def computeDirectNextTOP(self, selectionCurrentTOP, selectionNextTOP):
        SUBPART_RE = re.compile(r'.*[a-z]\)')# Contains Subpart? -> Next Direct TOP = Next TOP (e.g. RP 982 2b))
        if SUBPART_RE.match(selectionCurrentTOP.clean_text()) and  selectionNextTOP and (SUBPART_RE.match(selectionNextTOP.clean_text())):
            return selectionNextTOP

        #Find next line not indented == next TOP
        selectionsNextPDFTOPs = self.cutter.all().filter(
            doc_top__gt  = selectionCurrentTOP.doc_top,
            left__gte = LEFT_TOP,
            right__lte = RIGHT_TOP,
        ).above(self.umdruckSelection) #stay in upper part
        selectionDirectNextTOP = self._getHighestSelectionNotEmpty(selectionsNextPDFTOPs)# Could be empty, but this is handeled by super method as well
        if not selectionDirectNextTOP: #TOP is Last in upper part -> Umdruck is lower border
            selectionDirectNextTOP = self.umdruckSelection
        return selectionDirectNextTOP

    #When in lower part, senat text is above group of TOPs
    #First find right group and then lookup right group senat text in dict
    def parseLikeLowerPart(self, selectionCurrentTOP):
        partTitleSelection = self.getPartTitleSelection(selectionCurrentTOP)
        if not partTitleSelection:
            # Handle case where no part title is found
            print(f"Warning: No part title found for TOP {selectionCurrentTOP.clean_text()}. Using empty text.")
            return "", ""
            
        partTitle = partTitleSelection.clean_text().strip()
        if partTitle not in self.dictPartTitleToSenatsText:
            # Handle case where part title is not in dictionary
            print(f"Warning: Part title '{partTitle}' not found in dictionary for TOP {selectionCurrentTOP.clean_text()}. Using empty text.")
            return "", ""
            
        senats_text = self.dictPartTitleToSenatsText[partTitle]
        return senats_text, "" #No BR Text in RP PDFs

    #Right Group of TOP in lower part == lowest Roman numeral still above TOP
    def getPartTitleSelection(self, selectionCurrentTOP):
        partsAboveTOPSelections = self.selectionsPartTitles.above(selectionCurrentTOP)
        if len(partsAboveTOPSelections) == 0:
            return None
        partSelection = self.getLowestSelection(partsAboveTOPSelections)
        return partSelection

    #Return selection with biggest doc_top
    def getLowestSelection(self, selections):
        if len(selections) == 0: #max throws error for empty set
            return None
        return max(selections, key= lambda x: x.doc_top)

    #Fork of DefaultTOPPositionFinder class in PDFTextExtractor File, but need it now for finding alternative next TOP as well, so just copy-pasted it and added not empty Selecion Check.
    def _getHighestSelectionNotEmpty(self, selections):
        notEmptySelecions = selections.filter(regex="[^ ]+")
        if len(notEmptySelecions) == 0: #min throws error for empty set
            return notEmptySelecions
        return min(notEmptySelecions, key= lambda x: x.doc_top)

class SenatsAndBRTextExtractor967(SenatsAndBRTextExtractor):
    # In 963 RP, we have same formatting for lower and upper part (like normal upper part)
    def _extractSenatBRTexts(self, selectionCurrentTOP, selectionNextTOP):
        page_heading = 73 #Bottom of heading on each page
        page_footer = 1260 #Upper of footer on each page

        if len(selectionCurrentTOP) == 0: #Some TOPs not present e.g. RP 982 1.
            return "", ""
        return self.parseLikeUpperPart(selectionCurrentTOP, selectionNextTOP)


#Senats/BR Texts and TOPS in RP  all have same formatting
class TextExtractorHolder(PDFTextExtractor.TextExtractorHolder):

    def _getRightTOPPositionFinder(self, top):
        return PDFTextExtractor.DefaultTOPPositionFinder(self.cutter, TOPRight=250)# Need this only for RP 985 18a/18b, because "(LFGB)" catches b) + cant have TOPRight too far left, because subparts are part of text "column"
    # Decide if I need custom rules for special session/TOP cases because PDF format isn't consistent
    #In RP all Text Rules are consistent
    def _getRightSenatBRTextExtractor(self, top, cutter):
        if self.sessionNumber == 967:
            return SenatsAndBRTextExtractor967(cutter)
        return SenatsAndBRTextExtractor(cutter)
