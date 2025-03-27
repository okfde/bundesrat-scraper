import re
import pdb
import json

import requests
from lxml import html as etree
from bs4 import BeautifulSoup

import pdfcutter

# Import relative Parent Directory for Helper Classes
import os, sys
sys.path.insert(0, os.path.abspath('..')) #Used when call is ` python3 file.py`
sys.path.insert(0, os.path.abspath('.')) #Used when call is ` python3 $COUNTY/file.py`
import helper
import selectionVisualizer as dVis
import PDFTextExtractor
import MainBoilerPlate

INDEX_URL = 'https://www.bayern.de/staatskanzlei/bayern-in-berlin/plenarsitzungen-im-bundesrat/'
BASE_URL = 'https://www.bayern.de'
AJAX_URL = 'https://www.bayern.de/wp-content/themes/bayernde/functions.ajax.php'
NUM_RE = re.compile(r'.*/.*[Aa]bstimmungsverhalten-(\d+).*.pdf$')

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):

    #Out: Dict of {sessionNumberOfBR: PDFWebLink} entries
    #There is no better way than to use the "search" pagination from the page, take all links, go to next page, take all links there... . There is no single list with all pdfs anymore and I couldn't find a way to increase the page size itself
    def _get_pdf_urls(self):
        page_num = 0
        
        while True:
            # Set up headers and cookies for the AJAX request
            headers = {
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9,de-DE;q=0.8,de;q=0.7',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Origin': 'https://www.bayern.de',
                'Pragma': 'no-cache',
                'Referer': 'https://www.bayern.de/staatskanzlei/bayern-in-berlin/plenarsitzungen-im-bundesrat/',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
                'X-Requested-With': 'XMLHttpRequest',
                'sec-ch-ua': '"Not:A-Brand";v="24", "Chromium";v="134"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Linux"'
            }
            
            cookies = {
                'BYDE_pagi': str(page_num)
            }
            
            data = {
                'action': 'byde_load_data',
                'kategorien': '[93]',
                'sb': '',
                'd1': '',
                'd2': '',
                'seitenid': '48110',
                'anzeige_3_spalte': 'ja',
                'inhalt_3_spalte': 'cat',
                'pagi': str(page_num + 1)
            }
            
            # Make the AJAX request
            response = requests.post(AJAX_URL, headers=headers, cookies=cookies, data=data)
            
            # Check if we got a valid response
            if response.status_code != 200 or not response.text:
                break
                
            # Parse the HTML content from the AJAX response
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all search result titles
            search_titles = soup.select('.item-search-title a')
            
            if not search_titles:
                break
                
            # Process each search result
            for title in search_titles:
                detail_url = title.get('href')
                
                # Ensure detail_url has the proper scheme
                if not detail_url.startswith('http'):
                    if detail_url.startswith('/'):
                        detail_url = BASE_URL + detail_url
                    else:
                        detail_url = BASE_URL + '/' + detail_url
                
                try:
                    # Get the detail page to find the PDF link
                    detail_response = requests.get(detail_url)
                    detail_soup = BeautifulSoup(detail_response.content, 'html.parser')
                    
                    # Find all PDF links on the detail page
                    pdf_links = detail_soup.select('a[href$=".pdf"]')
                    
                    if pdf_links:
                        # Get the last PDF link on the page
                        pdf_link = pdf_links[-1].get('href')
                        
                        # Extract the session number from the PDF filename
                        num_match = NUM_RE.search(pdf_link)
                        if num_match:
                            num = int(num_match.group(1))
                            print(num)
                            
                            # Ensure the link is absolute
                            if not pdf_link.startswith('http'):
                                if pdf_link.startswith('/'):
                                    pdf_link = BASE_URL + pdf_link
                                else:
                                    pdf_link = BASE_URL + '/' + pdf_link
                                
                            yield num, pdf_link
                except Exception as e:
                    print(f"Error processing detail URL {detail_url}: {e}")
                    continue
            
            # Move to the next page
            page_num += 1

#Senats/BR Texts and TOPS in BA  all have same formatting
class TextExtractorHolder(PDFTextExtractor.TextExtractorHolder):

    #Can't uncouple Subpart from number TOP (e.g. BA 985 "9a)." ) , so use CustomTOPFormatPositionFinder for this
    #Still use default format for number only TOPs
    def _getRightTOPPositionFinder(self, top):
        formatTOPsWithSubpart="{number}{subpart})." #e.g. BA 985 9. a) is "9a)."
        if self.sessionNumber == 940 and top == "6. b)":
            formatTOPsWithSubpart="{number}{subpart})" #e.g. 6b) in BA 940
        elif self.sessionNumber in [982, 983]:
            formatTOPsWithSubpart="{number}{subpart})" #e.g. 2a) in BA 982
        elif self.sessionNumber == 984:
            formatTOPsWithSubpart="{number}{subpart}." #e.g. 45a. in BA 984
        elif self.sessionNumber == 992 and top == "70. b)" :
            formatTOPsWithSubpart="{number}.{subpart})." #e.g. 70.b). in BA 992
        return PDFTextExtractor.CustomTOPFormatPositionFinder(self.cutter, formatSubpartTOP=formatTOPsWithSubpart)

    # Decide if I need custom rules for special session/TOP cases because PDF format isn't consistent
    #In BA all Text Rules are consistent
    def _getRightSenatBRTextExtractor(self, top, cutter): 
        return PDFTextExtractor.VerticalSenatsAndBRTextExtractor(cutter,
                # Taken from pdftohtml -xml output
                page_heading = 129,
                page_footer = 773,
                senatLeft = 565,
                brLeft = 855,
         )
