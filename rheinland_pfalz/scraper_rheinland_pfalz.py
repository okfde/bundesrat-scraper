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

INDEX_URL = 'https://tpp.rlp.de/dataset?q=Abstimmungsverhalten&sort=score+desc%2C+metadata_modified+desc&page={}'
BASE_URL = 'https://tpp.rlp.de'
NUM_RE = re.compile(r'der (\d+)\. Sitzung')#Typos all over the place, so only match little part
BR_TEXT_RE = re.compile(r'^Ergebnis BR:')

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):

    #Out: Dict of {sessionNumberOfBR: PDFWebLink} entries
    def _get_pdf_urls(self):
        #Have to check all search result pages, because can't find anywhere a complete list
        #of all "Abstimmungsverhalten" PDFs of RP
        searchPageNum = 1
        while True:
            response = requests.get(INDEX_URL.format(searchPageNum))
            root = etree.fromstring(response.content)
            resultsOnPage = root.xpath('//*[@id="content"]/div[3]/div/div/ul/li/div/h3/a') # All Search Results On this Page

            if len(resultsOnPage) == 0: #Empty Search Page -> Visited everything possible -> break Loop
                break

            for partLink in resultsOnPage: #Only /sharepoint... , not http://www...

                text = partLink.text_content()
                maybeNum = NUM_RE.search(text) #Links to a Bundesrat-PDF?
                if maybeNum: #Also have e.g. "Digitalpakt und Grundgesetzänderung" as link -> Filter them out
                    num = int(maybeNum.group(1))
                    #Have to look at this link again before I can get PDF URL
                    redirectLink = BASE_URL + partLink.attrib['href']
                    responseLink = requests.get(redirectLink)
                    rootLink = etree.fromstring(responseLink.content)
                    link = rootLink.xpath('//*[@id="dataset-resources"]/ul/li/div/ul/li[2]/a')[0].attrib['href'] #There should only be one result with that xpath
                    yield int(num), link

            searchPageNum+=1

# TODO Look if there is something above current TOP with pattern [IVX]+\.  , then take next passage as Senat text, else the Senat Text is below 
# TODO What to do if below one top no other top, but no last top? (e.g. 973: TOP 40  (Page 16) - still "Erläuterungen" below
# TODO TOPs unorderded, how to get next? Maybe just select all ^..\. and the take first (wrt doc_top) below current top selection (Also e.g. 970 25a. is easy to select)

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

