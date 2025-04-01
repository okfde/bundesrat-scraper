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
        
        # Find the table containing the TOPs
        self.table = self.websiteRoot.xpath('//table')
        if not self.table:
            raise Exception("Could not find table with TOPs in the HTML")
        self.table = self.table[0]

    #Hotswap Rules for finding TOP and extracting Senat/BR Text w.r.t. session number and TOP
    #Out: (SenatText, BRText) Tuple
    #Called by scraper.ipynb
    def _getSenatsAndBRTextsForCurrentTOP(self, currentTOP, nextTOP):
        # Extract the TOP number without the dot and subpart
        top_number = currentTOP.split('.')[0].strip()
        
        # Find the row for this TOP in the table
        top_row = self._findTOPRow(top_number, currentTOP)
        
        if top_row is None:
            return "", ""
            
        return self._extractSenatBRTextsFromRow(top_row)
    
    def _findTOPRow(self, top_number, currentTOP):
        # Find all rows in the table
        rows = self.table.xpath('.//tr')
        
        # Skip the header row
        rows = rows[1:] if len(rows) > 0 else []
        
        # Check if this is a subpart TOP (e.g., "8. a)")
        is_subpart = len(currentTOP.split()) > 1
        
        for row in rows:
            # Get the first cell (TD) which contains the TOP number
            cells = row.xpath('./td')
            if not cells or len(cells) < 2:
                continue
                
            top_cell = cells[0]
            top_text = top_cell.text_content().strip()
            
            # If this is a main TOP (e.g., "8.")
            if not is_subpart and top_text == top_number + '.':
                return row
                
            # If this is a subpart TOP (e.g., "8. a)")
            if is_subpart:
                # Handle empty first cell for subparts (they often have no number)
                if not top_text and currentTOP.endswith('b)'):
                    # Check if previous row was the 'a)' subpart
                    prev_row_index = rows.index(row) - 1
                    if prev_row_index >= 0:
                        prev_row = rows[prev_row_index]
                        prev_cells = prev_row.xpath('./td')
                        if prev_cells and len(prev_cells) >= 2:
                            prev_top_text = prev_cells[0].text_content().strip()
                            if prev_top_text == top_number + '.':
                                # This is likely the 'b)' subpart
                                return row
                
                # Direct match for subparts that have their number in the first cell
                if top_text and currentTOP.replace(' ', '') in top_text.replace(' ', ''):
                    return row
        
        return None
    
    def _extractSenatBRTextsFromRow(self, row):
        # Get the second cell which contains the text content
        cells = row.xpath('./td')
        if len(cells) < 2:
            return "", ""
            
        content_cell = cells[1]
        content_text = content_cell.text_content()
        
        # Look for italic text elements which represent the Senats text
        italic_elements = content_cell.xpath('.//em | .//i')
        
        br_text = ""
        senats_text = ""
        
        if italic_elements:
            # Extract all italic text - this is all Senats text
            italic_texts = [elem.text_content().strip() for elem in italic_elements]
            # Filter out empty strings to avoid empty separator error
            italic_texts = [text for text in italic_texts if text]
            senats_text = "\n".join(italic_texts)
            
            # Find the position of the first italic text in the content
            if italic_texts:
                first_italic = italic_texts[0]
                first_pos = content_text.find(first_italic)
                if first_pos > 0:
                    # Everything before the first italic text is BR text
                    br_text = content_text[:first_pos].strip()
                else:
                    # If we can't find the first italic text or it's at the beginning,
                    # assume there's no BR text
                    br_text = ""
            else:
                # No valid italic texts found, assume all is BR text
                br_text = content_text.strip()
        else:
            # No italic elements found, assume all text is BR text
            br_text = content_text.strip()
            
        if not senats_text.strip():
            print('empty')
        return senats_text, br_text
