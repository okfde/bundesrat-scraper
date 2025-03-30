import json
import re

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

BASE_URL = 'https://www.berlin.de'
# Main URL for current sessions
CURRENT_URL = 'https://www.berlin.de/rbmskzl/politik/senatskanzlei/bundesangelegenheiten/aktuelles/artikel.1364168.php'
# Additional URLs for older sessions
ARCHIVE_URLS = [
    'https://www.berlin.de/rbmskzl/politik/senatskanzlei/bundesangelegenheiten/aktuelles/artikel.1385011.php',  # 2019-2021
    'https://www.berlin.de/rbmskzl/politik/senatskanzlei/bundesangelegenheiten/aktuelles/artikel.1385006.php'   # 2016-2018
]

# Updated regex to match the session number format
LINK_TEXT_RE = re.compile(r'(\d+)\. Sitzung am')

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):
    def _get_pdf_urls(self):
        print("Fetching PDF URLs from Berlin website...")
        session_urls = {}
        
        # First fetch from the current sessions page
        current_urls = self._fetch_urls_from_page(CURRENT_URL)
        session_urls.update(current_urls)
        print(f"Found {len(current_urls)} session URLs from current page")
        
        # Then fetch from archive pages
        for archive_url in ARCHIVE_URLS:
            archive_urls = self._fetch_urls_from_page(archive_url)
            session_urls.update(archive_urls)
            print(f"Found {len(archive_urls)} additional session URLs from {archive_url}")
        
        # Print summary of found URLs
        print(f"Total PDF URLs found: {len(session_urls)}")
        
        # Return all found session URLs
        for num, url in session_urls.items():
            yield num, url
    
    def _fetch_urls_from_page(self, page_url):
        """Fetch session URLs from a specific page"""
        try:
            response = requests.get(page_url)
            # Use the html.fromstring method to parse HTML
            tree = html.fromstring(response.content)
            
            # Dictionary to store session number to URL mapping for this page
            page_urls = {}
            
            # Find all strong elements with titles containing session information
            session_titles = tree.xpath('//strong[contains(@class, "title") and contains(text(), "Sitzung am")]')
            
            for title in session_titles:
                title_text = title.text_content().strip()
                match = LINK_TEXT_RE.search(title_text)
                
                if match:
                    session_num = int(match.group(1))
                    
                    # Find the closest download link
                    # Navigate up to the list item, then find the download link within it
                    list_item = title
                    while list_item is not None and list_item.tag != 'li':
                        list_item = list_item.getparent()
                    
                    if list_item is not None:
                        download_link = list_item.xpath('.//a[contains(@class, "link--download")]')
                        if download_link:
                            pdf_url = download_link[0].attrib['href']
                            if not pdf_url.startswith('http'):
                                pdf_url = BASE_URL + pdf_url
                            
                            print(f"Found PDF for session {session_num}: {pdf_url}")
                            page_urls[session_num] = pdf_url
            
            # If no URLs were found, try an alternative approach
            if not page_urls:
                print(f"No URLs found with primary method on {page_url}, trying alternative approach...")
                # Try to find all download links and associate them with nearby session numbers
                download_links = tree.xpath('//a[contains(@class, "link--download")]')
                
                for link in download_links:
                    # Look for title attribute or nearby text containing session information
                    title_attr = link.get('title', '')
                    match = LINK_TEXT_RE.search(title_attr)
                    
                    if not match:
                        # Try to find nearby text with session information
                        parent = link.getparent().getparent().getparent()
                        nearby_text = parent.text_content()
                        match = LINK_TEXT_RE.search(nearby_text)
                    
                    if match:
                        session_num = int(match.group(1))
                        pdf_url = link.attrib['href']
                        if not pdf_url.startswith('http'):
                            pdf_url = BASE_URL + pdf_url
                        
                        print(f"Found PDF for session {session_num} (alt method): {pdf_url}")
                        page_urls[session_num] = pdf_url
            
            return page_urls
            
        except Exception as e:
            print(f"Error fetching URLs from {page_url}: {e}")
            return {}

class TextExtractorHolder(PDFTextExtractor.TextExtractorHolder):
    def _getRightSenatBRTextExtractor(self, top, cutter): 
        return PDFTextExtractor.VerticalSenatsAndBRTextExtractor(cutter,
            # Taken from pdftohtml -xml output
            page_heading = 80,
            page_footer = 806,
            senatLeft = 570,
            brLeft = 910,
        )
