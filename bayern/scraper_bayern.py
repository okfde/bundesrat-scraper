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
NUM_RE = re.compile(r'.*/.*[Aa]bstimmung[^0-9]*(\d+).*.pdf$') #E.g. 1012 has an extra -1 at the end of the link, hence want first number in link

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):

    #Out: Dict of {sessionNumberOfBR: PDFWebLink} entries
    #There is no better way than to use the "search" pagination from the page, take all links, go to next page, take all links there.. There is no single list with all pdfs anymore and I couldn't find a way to increase the page size itsel
    def _get_pdf_urls(self):
        page_num = 0

        while True:
            # Set up headers and cookies for the AJAX request

            cookies = {
                'BYDE_pagi': str(page_num)
            }

            data = {
                'action': 'byde_load_data',
                'kategorien': '[93]',
                'seitenid': '48110',
                'pagi': str(page_num + 1)
            }

            # Make the AJAX request
            response = requests.post(AJAX_URL, cookies=cookies, data=data)

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

                    # Find the first PDF that matches the NUM_RE regex
                    matching_pdf = None
                    for link in pdf_links:
                        pdf_link = link.get('href')
                        if NUM_RE.search(pdf_link):
                            matching_pdf = pdf_link
                            break

                    if matching_pdf:
                        # Extract the session number from the PDF filename
                        num_match = NUM_RE.search(matching_pdf)
                        if num_match:
                            num = int(num_match.group(1))
                            print(num)

                            # Ensure the link is absolute
                            if not matching_pdf.startswith('http'):
                                if matching_pdf.startswith('/'):
                                    matching_pdf = BASE_URL + matching_pdf
                                else:
                                    matching_pdf = BASE_URL + '/' + matching_pdf

                            yield num, matching_pdf
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
