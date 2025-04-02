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

# Update URLs to match the new website structure
CURR_INDEX_URL = 'https://www.schleswig-holstein.de/DE/landesregierung/ministerien-behoerden/LVB/Aufgaben/Bundesratsarbeit/abstimmverhalten'
ARCHIVE_INDEX_URL = 'https://www.schleswig-holstein.de/DE/landesregierung/ministerien-behoerden/LVB/Aufgaben/Bundesratsarbeit/abstimmverhalten'

BASE_URL='https://www.schleswig-holstein.de/'
NUM_RE = re.compile(r'(\d+)\.\sSitzung')
BR_TEXT_RE = re.compile(r'^Ergebnis\sBR:')

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):

    #Out: Dict of {sessionNumberOfBR: PDFWebLink} entries
    def _get_pdf_urls(self):
        # The new website structure has all PDFs on a single page
        print(f"Fetching PDFs from {CURR_INDEX_URL}")
        response = requests.get(CURR_INDEX_URL)
        
        # Use html.fromstring instead of etree.fromstring
        root = html.fromstring(response.content)
        
        # Find all PDF links on the page
        pdf_links = root.xpath('//a[contains(@href, ".pdf")]')
        print(f"Found {len(pdf_links)} PDF links")
        
        found_sessions = {}
        for link in pdf_links:
            href = link.attrib['href']
            
            # Get the text content of the link
            link_text = link.text_content().strip()
            
            # Try to extract session number using regex
            match = NUM_RE.search(link_text)
            if match:
                num = int(match.group(1))
                # Full URL to the PDF
                full_url = href if href.startswith('http') else BASE_URL + href
                
                # Debug output
                print(f"Found session {num}: {full_url}")
                
                found_sessions[num] = full_url
                yield num, full_url
        
        if not found_sessions:
            print("WARNING: No sessions found! Check if the website structure has changed.")

    #There are some links that point to PDF directly (have "PDF" in title),
    #or that redirect first to another page, where PDF Link is written down
    #In: <a>-tag HTML
    #Out: (num, link)
    def extractLinkAndNumber(self, aTag):
        # This method is kept for backward compatibility but is no longer used
        # in the new website structure
        text = aTag.text
        num = int(NUM_RE.search(text).group(1))
        if "PDF" in text.upper(): #Links to PDF directly
            link = BASE_URL + aTag.attrib['href']
        else:
            redirectLink = BASE_URL + aTag.attrib['href']
            redirectResponse = requests.get(redirectLink)
            redirectRoot = html.fromstring(redirectResponse.content)
            redirectATag = redirectRoot.xpath('//a[contains(@href, "pdf")]')[0] #Somehow, XPath from Chrome doesn't find anything here, so search inside href for "pdf" substring
            link = BASE_URL + redirectATag.attrib['href']
        return num, link

#Senats/BR Texts and TOPS in SH all have same formatting
class SenatsAndBRTextExtractor(PDFTextExtractor.AbstractSenatsAndBRTextExtractor):
    def _extractSenatBRTexts(self, selectionCurrentTOP, selectionNextTOP):
        page_heading = 73 #Bottom of heading on each page
        page_footer = 1215 #Upper of footer on each page

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

        br_text = "" #SH doesnt repeat BR Text in its PDFs
        if not senats_text.strip():
            print('empty')
        return senats_text, br_text

#Senats/BR Texts and TOPS in SH  all have same formatting
class TextExtractorHolder(PDFTextExtractor.TextExtractorHolder):
    def _getRightTOPPositionFinder(self, top):
        return PDFTextExtractor.DefaultTOPPositionFinder(self.cutter, TOPRight=250)# Need this only for SH 985 18a/18b, because "(LFGB)" catches b) + cant have TOPRight too far left, because subparts are part of text "column"
    # Decide if I need custom rules for special session/TOP cases because PDF format isn't consistent
    #In BW all Text Rules are consistent
    def _getRightSenatBRTextExtractor(self, top, cutter): 
        return SenatsAndBRTextExtractor(cutter)
