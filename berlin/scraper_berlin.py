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
INDEX_URL = 'https://www.berlin.de/rbmskzl/politik/senatskanzlei/bundesangelegenheiten/aktuelles/artikel.1364168.php'

# Updated regex to match the session number format
LINK_TEXT_RE = re.compile(r'(\d+)\. Sitzung am')

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):
    def _get_pdf_urls(self):
        print("Fetching PDF URLs from Berlin website...")
        response = requests.get(INDEX_URL)
        # Use the html.fromstring method to parse HTML
        tree = html.fromstring(response.content)
        
        # Dictionary to store session number to URL mapping
        session_urls = {}
        
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
                        session_urls[session_num] = pdf_url
        
        # If no URLs were found, try an alternative approach
        if not session_urls:
            print("No URLs found with primary method, trying alternative approach...")
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
                    session_urls[session_num] = pdf_url
        
        # Print summary of found URLs
        print(f"Total PDF URLs found: {len(session_urls)}")
        
        # Return all found session URLs
        for num, url in session_urls.items():
            yield num, url

class TextExtractorHolder(PDFTextExtractor.TextExtractorHolder):
    def _getRightSenatBRTextExtractor(self, top, cutter): 
        return PDFTextExtractor.VerticalSenatsAndBRTextExtractor(cutter,
            # Taken from pdftohtml -xml output
            page_heading = 135,
            page_footer = 806,
            senatLeft = 585,
            brLeft = 910,
        )
