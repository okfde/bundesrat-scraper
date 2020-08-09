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

INDEX_URL = 'https://www.saarland.de/lvsaarland/DE/bundesrat/br-beschluesse/br-beschluesse_node.html?gtp=%252687c6339c-fd8a-4a70-9bff-954224c0fe05_list%253D{searchnumber}'
BASE_URL = 'https://www.saarland.de/'
NUM_RE = re.compile(r'(\d+)[.]?[ ]?Sitzung') #Space is sometimes missing between number and "Sitzung"
BR_TEXT_RE = re.compile(r'^Ergebnis BR:')

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):



    #Out: Dict of {sessionNumberOfBR: PDFWebLink} entries
    def _get_pdf_urls(self):
        searchpage=1
        while True:
            #Go through search pages 1,..., until search is empty
            searchresponse = requests.get(INDEX_URL.format(searchnumber=searchpage))
            searchroot = etree.fromstring(searchresponse.content)
            fields = searchroot.xpath('//a[@class="Publication"]')
            if len(fields) == 0: #Have seen all search results
                break

            for field in fields:
                text = field.text_content()
                if text == "": # 952 not there, but still link -> would break num regex
                    continue
                num = int(NUM_RE.search(text).group(1))

                partLinkRedirect = field.attrib['href'] #Only /dokumente/... in href
                linkRedirect = BASE_URL + partLinkRedirect
                if "960.Sitzung" in linkRedirect: #Forgot PDF Link for session 960 -> would break xpath for PDF Link
                    continue
                redirectresponse = requests.get(linkRedirect) #Need to go to another page where PDF Link is located
                redirectroot = etree.fromstring(redirectresponse.content)

                partPDFlink = redirectroot.xpath('//a[@class="downloadLink"]')[0].attrib['href'] #Link to PDF
                pdfLink = BASE_URL + partPDFlink

                yield int(num), pdfLink
            searchpage+=1

#Senats/BR Texts and TOPS in BW  all have same formatting
class SenatsAndBRTextExtractor(PDFTextExtractor.AbstractSenatsAndBRTextExtractor):

    def __init__(self, cutter, senatsTextPrefix="Haltung SL:"):
        self.senatsTextPrefix = senatsTextPrefix
        super().__init__(cutter)

    def _extractSenatBRTexts(self, selectionCurrentTOP, selectionNextTOP):
        page_heading = 73 #Bottom of heading on each page
        page_footer = 1260 #Upper of footer on each page

        #Get indented Text, Senats/BR text is everything below it, need to check below this because otherwise I also filter Name of TOP

        #Because selectionNextTOP is never empty (but could be empty selector), I can use it without checking if it is None or empty
        senatTitleSelection = self.cutter.all().filter(auto_regex="^{}".format(self.senatsTextPrefix)).below(selectionCurrentTOP)
        BRTitleSelection = self.cutter.all().filter(auto_regex="^Ergebnis BR:").below(selectionCurrentTOP)
        if selectionNextTOP: #Otherwise Always empty text if no next TOP
            senatTitleSelection = senatTitleSelection.above(selectionNextTOP)
            BRTitleSelection = BRTitleSelection.above(selectionNextTOP)

        senats_text = self.cutter.all().filter(
                doc_top__gte = senatTitleSelection.doc_top-1 #Senats Text starts next to title
        )
        if BRTitleSelection: #Otherwise Always empty text if BRTitleSelection empty
            senats_text = senats_text.above(BRTitleSelection)

        br_text = self.cutter.all().filter(
                doc_top__gte = BRTitleSelection.doc_top-1, #BR Text starts next to title
                auto_regex="^[^_]+" #Each TOP ends with ----- line, filter this one out
        )
        if selectionNextTOP: #Otherwise Always empty text if no next TOP
            br_text = br_text.above(selectionNextTOP)

        senats_text = senats_text.clean_text()
        br_text = br_text.clean_text()

        # Although in 973 TOP 9, senats_text ends with many blank lines, in JSON they are somehow striped
        return senats_text, br_text

#Senats/BR Texts and TOPS in SL all have same formatting
class TextExtractorHolder(PDFTextExtractor.TextExtractorHolder):

    def _getRightTOPPositionFinder(self, top):
        if self.sessionNumber == 992 and top in ["23. b)", "69. b)", "69. d)"]:
            return PDFTextExtractor.CustomTOPFormatPositionFinder(self.cutter, formatSubpartTOP="{number}{subpart}") #Somehow dot not in same chunk as number and subpart
        if self.sessionNumber == 992 and "40" in top: #992 40 a,b,c are very weird (all TOPs before the text, would have to take 41 as next TOP, dont have upper bound for text ...), need this for right Text 39 (nextTop is 40a
            return PDFTextExtractor.DefaultTOPPositionFinder(self.cutter)

        return PDFTextExtractor.CustomTOPFormatPositionFinder(self.cutter, formatSubpartTOP="{number}{subpart}.") #25a.

    # Decide if I need custom rules for special session/TOP cases because PDF format isn't consistent
    #In BW all Text Rules are consistent
    def _getRightSenatBRTextExtractor(self, top, cutter): 
        if self.sessionNumber == 992 and "40" in top: #992 40 a,b,c are very weird (all TOPs before the text, would have to take 41 as next TOP, dont have upper bound for text ...), therefore do this statically
            senatsText = "Stellungnahme gemäß Drs. 295/1/20 (Enthaltung zu Ziffern 13, 31, 32," # For all subparts same
            brText = "Stellungnahme gemäß Drs. 295/1/20 ohne Ziffern 20, 26, 32 sowie 40 bis 44 (Sammelabstimmung zu Ziffern 1 bis 7, 9, 10, 14 bis 18, 21 bis 24, 28 bis 30, 33 bis 38 und 47 bis 50)"
            return PDFTextExtractor.StaticTextSenatsAndBRTextExtractor(cutter, senatsText, brText)
        if self.sessionNumber == 984 and top == "26.":
            return SenatsAndBRTextExtractor(cutter, senatsTextPrefix="Haltung") #Forgot "SL:" 984 26 , only reason for this parameter
        return SenatsAndBRTextExtractor(cutter)
