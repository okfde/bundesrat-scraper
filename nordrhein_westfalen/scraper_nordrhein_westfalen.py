import re
import pdb

import requests
from lxml import html as etree

# Import relative Parent Directory for Helper Classes
import os, sys
sys.path.insert(0, os.path.abspath('..')) #Used when call is ` python3 file.py`
sys.path.insert(0, os.path.abspath('.')) #Used when call is ` python3 $COUNTY/file.py`
import PDFTextExtractor
import MainBoilerPlate

INDEX_URL = 'https://mbeim.nrw/nrw-beim-bund/nordrhein-westfalen-im-bundesrat/abstimmverhalten-im-bundesrat'
BASE_URL = 'https://mbeim.nrw/'
NUM_RE = re.compile(r'(\d+)-sitzung')
SESSION_URL_FORMAT = 'https://mbeim.nrw/{}-sitzung-des-bundesrates-abstimmverhalten-des-landes-nordrhein-westfalen'

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):

    #Out: Dict of {sessionNumberOfBR: WebLink} entries
    #Now gets HTML pages for sessions instead of .odt files
    def _get_pdf_urls(self):
        response = requests.get(INDEX_URL)
        root = etree.fromstring(response.content)

        # Get all links that contain session numbers in the text
        session_links = root.xpath('//a[contains(text(), "Sitzung des Bundesrates")]')
        
        for link in session_links:
            # Extract session number from the text
            text = link.text_content()
            match = re.search(r'(\d+)\.\s+Sitzung', text)
            if match:
                num = int(match.group(1))
                # Create the URL for the session HTML page
                session_url = SESSION_URL_FORMAT.format(num)
                yield num, session_url

#Don't have to change scraper.ipynb when derive TextExtractorHolder. But basically re-implement everything for HTML Parsing
#Also have TOPFinder and TextExtractor all in here, didn't want to add new classes for only one HTML County
class TextExtractorHolder(PDFTextExtractor.TextExtractorHolder):

    #Store WebsiteTable Root (HTML) instead of cutter (PDF)
    def __init__(self, filename, session):
        # Check if the filename is a local file (cache) or a URL
        if filename.startswith('http'):
            # It's a URL, fetch content directly
            response = requests.get(filename)
            html = response.content
        else:
            # It's a local file, read it
            with open(filename, 'r', encoding='utf-8') as file:
                html = file.read().replace('\n', '')
        
        websiteRoot = etree.fromstring(html)

        # The session content is now in a different structure
        self.websiteRoot = websiteRoot
        self.session = session
        self.sessionNumber = int(self.session['number'])

    #Hotswap Rules for finding TOP and extracting Senat/BR Text w.r.t. session number and TOP
    #Out: (SenatText, BRText) Tuple
    #Called by scraper.ipynb
    def _getSenatsAndBRTextsForCurrentTOP(self, currentTOP, nextTOP):
        # Extract the TOP number without the dot and subpart
        top_number = currentTOP.split('.')[0].strip()
        
        # Find the content for this TOP in the HTML
        top_content = self._findTOPContent(top_number, currentTOP)
        
        if top_content is None:
            return "", ""
            
        return self._extractSenatBRTextsFromContent(top_content, currentTOP)
    
    def _findTOPContent(self, top_number, currentTOP):
        # Look for content that starts with the TOP number
        # The new structure has TOP content in paragraphs
        
        # First try to find content with explicit TOP number
        top_elements = self.websiteRoot.xpath(f'//p[contains(text(), "TOP: {top_number}.")]')
        
        if not top_elements:
            # Try to find content that mentions the TOP number in a different format
            top_elements = self.websiteRoot.xpath(f'//p[contains(text(), "{currentTOP}")]')
        
        if not top_elements:
            # If still not found, look for any content that might be related to this TOP
            # This is a fallback and might not be accurate
            return None
            
        # Return the first matching element
        return top_elements[0]
    
    def _extractSenatBRTextsFromContent(self, top_content, currentTOP):
        # Get the full text content
        full_text = top_content.text_content()
        
        # Look for "NRW:" which separates BR text from Senats text
        if "NRW:" in full_text:
            parts = full_text.split("NRW:")
            br_text = parts[0].strip()
            senats_text = "NRW:" + parts[1].strip() if len(parts) > 1 else ""
        else:
            # If no "NRW:" marker, assume all is BR text
            br_text = full_text.strip()
            senats_text = ""
            
        return senats_text, br_text
