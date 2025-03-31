import re
import pdb
from lxml import html as etree

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

# Primary source - Transparenzportal
INDEX_URL = 'http://suche.transparenz.hamburg.de/?q=Bundesrat&limit=200&sort=score+desc%2Ctitle_sort+asc&extras_registerobject_type=senatmitteil'
BASE_URL = 'http://suche.transparenz.hamburg.de/'

# Secondary source - Hamburg Landesvertretung
SECONDARY_URL = 'https://www.hamburg.de/politik-und-verwaltung/behoerden/senatskanzlei/einrichtungen/landesvertretung-hamburg/bundesrat/abstimmungsverhalten'

NUM_RE = re.compile(r'.*-bundesrat-(\d+)\-sitzung-.*')
NUM_RE_ALT = re.compile(r'.*bundesrat.*?(\d+).*?sitzung.*', re.IGNORECASE)  # More flexible regex for the secondary site
# Specific regex for the secondary site headers
SESSION_NUM_RE = re.compile(r'(\d+)\.\s+Sitzung\s+des\s+Bundesrates\s+am', re.IGNORECASE)
BR_TEXT_RE = re.compile(r'^Ergebnis BR:')

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):

    #Out: Dict of {sessionNumberOfBR: PDFWebLink} entries
    def _get_pdf_urls(self):
        """
        Get PDF URLs from both primary and secondary sources.
        Returns a generator of (session_number, pdf_url) tuples.
        """
        # Dictionary to track found PDFs to avoid duplicates
        found_pdfs = {}
        
        # 1. Get PDFs from Transparenzportal
        print("Fetching PDFs from Transparenzportal...")
        for num, pdf_link in self._get_transparenzportal_pdfs():
            found_pdfs[num] = pdf_link
            print(f"Found session {num} from Transparenzportal")
            
        # 2. Get PDFs from Hamburg Landesvertretung website
        print("Fetching PDFs from Hamburg Landesvertretung...")
        for num, pdf_link in self._get_landesvertretung_pdfs():
            # Only add if not already found or replace if better source
            found_pdfs[num] = pdf_link #Want to override, because these are the better "Abstimmungsverhalten" with more information
            print(f"Found session {num} from Landesvertretung")
        
        print(f"Total unique sessions found: {len(found_pdfs)}")
        
        # Return all found PDFs
        for num, pdf_link in sorted(found_pdfs.items()):
            yield int(num), pdf_link
    
    def _get_transparenzportal_pdfs(self):
        """
        Get PDF URLs from the Transparenzportal Hamburg.
        Returns a generator of (session_number, pdf_url) tuples.
        """
        try:
            response = requests.get(INDEX_URL)
            root = etree.fromstring(response.content)
            
            # Updated XPath to match the new structure of the Hamburg transparency portal
            # Find all links to dataset pages
            dataset_links = root.xpath('//h3/a[contains(@href, "/dataset/abstimmverhalten")]')
            
            for dataset_link in dataset_links:
                redirectLink = dataset_link.attrib['href']
                if not redirectLink.startswith('http'):
                    redirectLink = BASE_URL + redirectLink
                    
                maybeNum = NUM_RE.search(redirectLink)
                if not maybeNum: # Doesn't link to Bundesrat session
                    continue
                num = int(maybeNum.group(1))

                redirectResponse = requests.get(redirectLink)
                redirectRoot = etree.fromstring(redirectResponse.content)
                
                # Updated XPath to find PDF links on the detail page
                pdf_links = redirectRoot.xpath('//a[contains(@href, ".PDF") or contains(@href, ".pdf")]')
                
                if pdf_links:
                    pdfLink = pdf_links[0].attrib['href']
                    yield int(num), pdfLink
        except Exception as e:
            print(f"Error fetching from Transparenzportal: {e}")
    
    def _get_landesvertretung_pdfs(self):
        """
        Get PDF URLs from the Hamburg Landesvertretung website.
        Returns a generator of (session_number, pdf_url) tuples.
        """
        try:
            print("Requesting secondary source URL...")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(SECONDARY_URL, headers=headers)
            print(f"Response status code: {response.status_code}")
            
            if response.status_code != 200:
                print(f"Failed to fetch secondary source: HTTP {response.status_code}")
                return
                
            # Parse the HTML content
            root = etree.fromstring(response.content)
            
            # Get all the h3 headers containing session information
            session_headers = root.xpath('//h3[contains(text(), "Sitzung des Bundesrates")]')
            print(f"Found {len(session_headers)} session headers")
            
            for header in session_headers:
                # Extract session number from header text
                header_text = header.text_content().strip()
                session_match = SESSION_NUM_RE.search(header_text)
                
                if not session_match:
                    continue
                    
                session_num = int(session_match.group(1))
                
                # Find the PDF link that follows this header
                pdf_link = header.xpath('./following-sibling::a[1][contains(@href, ".pdf") or contains(@href, ".PDF")]')
                
                if not pdf_link:
                    continue
                    
                pdf_url = pdf_link[0].attrib['href']
                
                # Make sure it's a full URL
                if not pdf_url.startswith('http'):
                    if pdf_url.startswith('/'):
                        pdf_url = 'https://www.hamburg.de' + pdf_url
                    else:
                        pdf_url = 'https://www.hamburg.de/' + pdf_url
                
                print(f"Found PDF for session {session_num}: {pdf_url}")
                yield int(session_num), pdf_url
                
        except Exception as e:
            print(f"Error fetching from secondary source: {str(e)}")
            import traceback
            traceback.print_exc()

#HA don't have all TOPs in PDF, and them again in non-linear order
class SenatsAndBRTextExtractor(PDFTextExtractor.AbstractSenatsAndBRTextExtractor):
    def _extractSenatBRTexts(self, selectionCurrentTOP, selectionNextTOP):
        #TODO Cut Footer
        page_heading = 73 #Bottom of heading on each page
        page_footer = 1195 #Upper of footer on each page
#        if not selectionCurrentTOP: #TOP not in PDF -> empty texts
#            return "", ""

        #As e.g. HA 985 TOPs not consecutive (After TOP 4 directly TOP 7), one has to find next direct TOP which is lower bound for text
        #Get indented Text, Senats text is everything intended before next TOP
        TOPRightIndented = self.cutter.all().filter(
            doc_top__gte = selectionCurrentTOP.doc_top -10, #Start with line where TOP stands
            left__gte = selectionCurrentTOP.left + 30,
            top__gte=page_heading, #Ignore Page header
            bottom__lt=page_footer, #Ignore Page Footer
        )

        if selectionNextTOP: #Next TOP as lower bound
            TOPRightIndented = TOPRightIndented.above(selectionNextTOP)

        #dVis.showCutter(TOPRightIndented)
        senats_text = helper.cleanTextOrderedByDocTop(TOPRightIndented)  #Else, pdfcutter orders by top, not by doc_top, making multi-site selection strangely sorted
        br_text = senats_text #Whole Text where senat and br and both mentioned, so just copy it
        if not senats_text.strip():
            print('empty')
        return senats_text, br_text

    #Fork of DefaultTOPPositionFinder class in PDFTextExtractor File, but need it now for finding alternative next TOP as well, so just copy-pasted it and added not empty Selecion Check.
    def _getHighestSelectionNotEmpty(self, selections): 
        notEmptySelecions = selections.filter(regex="[^ ]+")
        if len(notEmptySelecions) == 0: #min throws error for empty set
            return selections
        return min(notEmptySelecions, key= lambda x: x.doc_top)

#Somehow, with ^ (beginning of selection) when searching for  "TOP 9a" 985 HA, never get any selection. Therefore, remove ^ from regex for Hamburg
class CustomTOPFormatPositionFinderNoPrefix(PDFTextExtractor.CustomTOPFormatPositionFinder):
    #Fork of DefaultTOPPositionFinder._getNumberSelection, only difference regex no "^"
    def _getPrefixStringSelection(self, s):
        escapedS = helper.escapeForRegex(s)
        allSelectionsS = self.cutter.filter(auto_regex='{}'.format(escapedS))# Returns all Selections that have Chunks which *contain* s
        return self._getHighestSelection(allSelectionsS)

#Senats/BR Texts and TOPS in HA all have same formatting
class TextExtractorHolder(PDFTextExtractor.TextExtractorHolder):
    #Can't uncouple Subpart from number TOP (e.g. HA 985 "9a" ) , so use EntwinedNumberSubpartTOPPositionFinder for this
    # Also search for TOPs with prefix "TOP", because only number (e.g. HA 985 TOP 4) is to general to get right selection
    def _getRightTOPPositionFinder(self, top):
        if self.sessionNumber <= 984: #Don't have "Abstimmungsverhalten" for these, but rather "Ergebnisse" which have a totally different layout considering TIP numbers
            formatTOPsOnlyNumber="TOP {number}[ :]*$" #e.g. HA 985 4 is "TOP 4". Use $ to not match "TOP 1" with "TOP 11", but allow spaces and colons. TODO This $,[] is hacky, because . and ) get escaped by me in DefaultTOPPositionFinder , but $,[],* doesn't and I abuse this.
            #TODO Are there even TOPs in HA with ":" after TOP Number/Subpart? Think so, but couldn't find them anymore
            formatTOPsWithSubpart="{number}{subpart}" #e.g. HA 985 9. a) is "TOP 9a" (Has to start with TOP because I check for prefix) TODO This [] is hacky, because . and ) get escaped by me in DefaultTOPPositionFinder , but [],* doesn't and I abuse this.
            return CustomTOPFormatPositionFinderNoPrefix(self.cutter, formatNumberOnlyTOP= formatTOPsOnlyNumber, formatSubpartTOP= formatTOPsWithSubpart)

        return PDFTextExtractor.DefaultTOPPositionFinder(self.cutter) #TODO Go on here


    # Decide if I need custom rules for special session/TOP cases because PDF format isn't consistent
    #In HA all Text Rules are consistent
    def _getRightSenatBRTextExtractor(self, top, cutter): 
        return SenatsAndBRTextExtractor(cutter)
