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

def reformat_top_num(top_num):
    try:
        num = int(top_num)
        return str(num) + "."
    except ValueError: # Happens when top_num e.g. 48 a or 56 b
        return '{}{}.'.format(top_num[:-1], top_num[-1] + ")")

def get_reformatted_tops(top_nums):
    return [reformat_top_num(t) for t in top_nums]

def get_beschluesse_text(session, filename):
    cutter = pdfcutter.PDFCutter(filename=filename)
    session_number = int(session['number'])

    top_nums = [t['number'] for t in session['tops'] if t['top_type'] == 'normal'] # 1, 2, 3a, 3b, 4,....
    reformatted_top_nums = get_reformatted_tops(top_nums) #1., 2., 3a)., 3b)., 4.,...

    #e.g. "1b", ("1b).", "2.")
    for top_num, (current, next_) in zip(top_nums, helper.with_next(reformatted_top_nums)):
        current_top = cutter.filter(auto_regex=r'^{}\.'.format(current[:-1].replace(')', r'\)'))) #Escape . in 46. because of regex

        #Sometimes they forgot the . after the TOP
        if not current_top:
            current_top = cutter.filter(auto_regex=r'^{}'.format(current[:-1].replace(')', r'\)')))

        next_top = None
        if next_ is not None: #There is a TOP after this one which we have to take as a lower border
            next_top = cutter.filter(auto_regex=r'^{}\.'.format(next_[:-1].replace(')', r'\)'))) #Escape . in 46. because of regex
            if not next_top:
                next_top = cutter.filter(auto_regex=r'^{}'.format(next_[:-1].replace(')', r'\)'))) #Escape . in 46. because of regex
        senats_text, br_text = getSenatsAndBrTextsForCurrentTOP(cutter, current_top, next_top)
        yield top_num, {'senat': senats_text, 'bundesrat': br_text}

def getSenatsAndBrTextsForCurrentTOP(cutter, current_top, next_top):
    page_heading = 111 #Right under the grey heading of each table
    page_number = 788 #Bottom of each page
    right_title = 616
    right_senat = 892
    right_br = 1160

    if next_top:
        senats_text = cutter.all().filter(
            doc_top__gte=current_top.doc_top -2 ,
            top__gte=page_heading,
            bottom__lt=page_number,
            doc_bottom__lt=next_top.doc_bottom -2,
            left__gt=right_title,
            right__lt=right_senat
        )
        br_text = cutter.all().filter(
            doc_top__gte=current_top.doc_top -2 ,
            top__gte=page_heading,
            doc_bottom__lt=next_top.doc_bottom -2,
            bottom__lt=page_number,
            left__gt=right_senat,
            right__lt=right_br
        )
    else:
        senats_text = cutter.all().filter(
            doc_top__gte=current_top.doc_top -2 ,
            top__gte=page_heading,
            bottom__lt=page_number,
            left__gt=right_title,
            right__lt=right_senat
        )
        br_text = cutter.all().filter(
            doc_top__gte=current_top.doc_top -2 ,
            top__gte=page_heading,
            bottom__lt=page_number,
            left__gt=right_senat,
            right__lt=right_br
        )

    if not senats_text.clean_text().strip():
        print('empty')
    return senats_text.clean_text(), br_text.clean_text()

def get_session(session):
    print(f"Processing session {session['number']}...")
    
    # Get PDF URLs for all sessions
    PDF_URLS = dict(get_pdf_urls())
    print(f"Found {len(PDF_URLS)} PDF URLs")
    
    # Create PDF Link JSON File
    URLFILENAME = "session_urls.json"
    with open(URLFILENAME, 'w') as f:
        json.dump(PDF_URLS, f)
    
    try:
        filename = helper.get_session_pdf_filename(session, PDF_URLS)
        print(f"Using PDF file: {filename}")
        return dict(get_beschluesse_text(session, filename))
    except KeyError:
        print(f"No PDF found for session {session['number']}")
        return None
