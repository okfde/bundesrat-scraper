import json
import re
import os
import sys
import requests
from lxml import html as etree
from datetime import datetime


# Import relative Parent Directory for Helper Classes
sys.path.insert(0, os.path.abspath('..')) #Used when call is ` python3 file.py`
sys.path.insert(0, os.path.abspath('.')) #Used when call is ` python3 $COUNTY/file.py`
# Add pdfcutter path
sys.path.insert(0, os.path.abspath('/home/nwuensche/pdfcutter'))
import pdfcutter 
import helper
import PDFTextExtractor

# Base URLs
SACHSEN_URL = "https://www.landesvertretung.sachsen.de"
SACHSEN_BR_BASE = "https://www.landesvertretung.sachsen.de/Bundesrat.html"

def get_sitzungen_years():
    """Get all available years for Bundesrat sessions from the Sachsen website."""
    print("Fetching available years for Bundesrat sessions...")
    response = requests.get(SACHSEN_BR_BASE)
    root = etree.fromstring(response.content)
    
    # Find all links in the side menu that might lead to years
    years_links = []
    
    # Look for links that might contain years in the text or URL
    all_links = root.xpath('//a')
    for link in all_links:
        href = link.attrib.get('href', '')
        text = link.text_content().strip()
        
        # Check if the link text or URL contains a year (2020-2025)
        year_match = re.search(r'20\d\d', text) or re.search(r'20\d\d', href)
        if year_match:
            years_links.append((text, href))
            print(f"Found potential year link: {text} -> {href}")
    
    return years_links

def get_sessions_for_year(year_url):
    """Get all session links for a specific year."""
    if not year_url.startswith('http'):
        year_url = f"{SACHSEN_URL}{year_url}"
    
    print(f"Fetching sessions for year URL: {year_url}")
    response = requests.get(year_url)
    root = etree.fromstring(response.content)
    
    # Find all links that might lead to Bundesrat sessions
    session_links = []
    all_links = root.xpath('//a')
    
    for link in all_links:
        href = link.attrib.get('href', '')
        text = link.text_content().strip()
        
        # Look for links with session numbers (e.g., "1052. Sitzung")
        session_match = re.search(r'(\d+)\.\s*(?:Bundesratssitzung|Sitzung)', text)
        if session_match:
            session_num = int(session_match.group(1))
            session_links.append((session_num, href, text))
            print(f"Found session link: {text} -> {href}")
    
    return session_links

def get_pdf_from_session_page(session_url):
    """Extract Abstimmungsverhalten PDF links from a session page."""
    if not session_url.startswith('http'):
        session_url = f"{SACHSEN_URL}{session_url}"
    
    print(f"Checking session page: {session_url}")
    try:
        response = requests.get(session_url)
        root = etree.fromstring(response.content)
        
        # Look for PDF links that might be Abstimmungsverhalten
        pdf_links = root.xpath('//a[contains(@href, ".pdf")]')
        for link in pdf_links:
            href = link.attrib.get('href', '')
            text = link.text_content().strip()
            
            # Check if this is an Abstimmungsverhalten PDF
            if 'abstimmung' in href.lower() or 'abstimmung' in text.lower() or 'verhalten' in href.lower() or 'verhalten' in text.lower():
                print(f"  Found Abstimmungsverhalten PDF: {text} -> {href}")
                full_url = href if href.startswith('http') else f"{SACHSEN_URL}{href}"
                return full_url
        
        # If no specific Abstimmungsverhalten PDF found, return any PDF
        if pdf_links:
            href = pdf_links[0].attrib.get('href', '')
            text = pdf_links[0].text_content().strip()
            print(f"  Found PDF (might not be Abstimmungsverhalten): {text} -> {href}")
            full_url = href if href.startswith('http') else f"{SACHSEN_URL}{href}"
            return full_url
        
        print("  No PDF links found on this page")
    except Exception as e:
        print(f"  Error processing session page: {e}")
    
    return None

def get_pdf_urls():
    """Get all Abstimmungsverhalten PDF URLs for Bundesrat sessions."""
    # Dictionary to store session number -> PDF URL
    pdf_urls = {}
    
    # First get all available years
    year_links = get_sitzungen_years()
    
    # If no year links found, try to search the main page directly
    if not year_links:
        print("No year links found, checking main page directly...")
        # Try to find session links directly on the main page
        session_links = get_sessions_for_year(SACHSEN_BR_BASE)
        
        for session_num, href, text in session_links:
            pdf_url = get_pdf_from_session_page(href)
            if pdf_url:
                pdf_urls[session_num] = pdf_url
    else:
        # Process each year to find session links
        for year_text, year_href in year_links:
            session_links = get_sessions_for_year(year_href)
            
            for session_num, href, text in session_links:
                pdf_url = get_pdf_from_session_page(href)
                if pdf_url:
                    pdf_urls[session_num] = pdf_url
    
    print(f"Total Abstimmungsverhalten PDFs found: {len(pdf_urls)}")
    # Return all found PDF URLs
    for session_num, url in sorted(pdf_urls.items()):
        yield session_num, url

class TextExtractorHolder(PDFTextExtractor.TextExtractorHolder):
    
    # Define the TOP position finder for Sachsen PDFs
    def _getRightTOPPositionFinder(self, top):
        # Default format for TOPs with subparts
        formatTOPsWithSubpart = "{number}{subpart})."
        if self.sessionNumber == 1038:
            formatTOPsWithSubpart = "{number}{subpart}.)"
        
        # Return the appropriate TOP position finder
        return PDFTextExtractor.CustomTOPFormatPositionFinder(self.cutter, formatSubpartTOP=formatTOPsWithSubpart)
    
    # Define the text extractor for Sachsen PDFs
    def _getRightSenatBRTextExtractor(self, top, cutter):
        # Parameters for the vertical extractor (based on PDF structure)
        page_heading = 111  # Bottom of heading on each page
        page_footer = 788   # Upper of footer on each page
        senat_left = 616    # Start of Senat column
        senat_right = 892   # End of Senat column
        br_left = 892       # Start of BR column
        br_right = 1160     # End of BR column
        
        # Return the vertical extractor with the appropriate parameters
        return PDFTextExtractor.VerticalSenatsAndBRTextExtractor(
            cutter,
            page_heading=page_heading,
            page_footer=page_footer,
            senatLeft=senat_left,
            senatRight=senat_right,
            brLeft=br_left,
            brRight=br_right
        )

def get_beschluesse_text(session, filename):
    # Create a TextExtractorHolder instance
    extractor_holder = TextExtractorHolder(filename, session)
    
    # Use the extractor holder to get texts for all TOPs
    return extractor_holder.getSenatsAndBRTextsForAllSessionTOPs()

def get_session(session):
    session_number = str(session['number'])
    print(f"Processing session {session_number}...")
    
    # Load existing PDF URLs if available
    URLFILENAME = "session_urls.json"
    if os.path.exists(URLFILENAME):
        with open(URLFILENAME, 'r') as f:
            PDF_URLS = json.load(f)
        print(f"Loaded {len(PDF_URLS)} existing PDF URLs")
    else:
        PDF_URLS = {}
        print(f"No existing PDF URLs found, creating new file: {URLFILENAME}")
    
    # Check if we already have the URL for this session
    if session_number in PDF_URLS:
        print(f"URL for session {session_number} already known, using cached URL")
    else:
        print(f"URL for session {session_number} not found, fetching new URLs...")
        # Get PDF URLs for all sessions
        new_urls = dict(get_pdf_urls())
        
        # Update our URL dictionary with any new URLs
        for num, url in new_urls.items():
            PDF_URLS[str(num)] = url
        
        # Save the updated URLs
        with open(URLFILENAME, 'w') as f:
            json.dump(PDF_URLS, f)
        print(f"Updated URL file with {len(new_urls)} URLs")
    
    try:
        filename = helper.get_session_pdf_filename(session, PDF_URLS)
        print(f"Using PDF file: {filename}")
        return dict(get_beschluesse_text(session, filename))
    except KeyError:
        print(f"No PDF found for session {session_number}")
        return None
