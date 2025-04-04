import re
import pdb
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

# Base URL for PDF downloads
BASE_URL = 'https://www.saarland.de'
PDF_URL_TEMPLATE = 'https://www.saarland.de/SharedDocs/Downloads/DE/Landesvertretung_Berlin/Bundesratsbeschl%C3%BCsse/{year}/Beschl%C3%BCsse_{session}.Sitzung'
NUM_RE = re.compile(r'(\d+)[.]?[ ]?Sitzung') #Space is sometimes missing between number and "Sitzung"
BR_TEXT_RE = re.compile(r'^Ergebnis BR:')

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):

    #Out: Dict of {sessionNumberOfBR: PDFWebLink} entries
    def _get_pdf_urls(self):
        # Start with the most recent session (as of April 2025)
        current_session = 1052
        current_year = 2025
        
        while True:
            # Construct the URL for the current session
            session_url = PDF_URL_TEMPLATE.format(year=current_year, session=current_session)
            
            # Try to access the session page
            try:
                print(f"Trying session {current_session} ({current_year}): {session_url}")
                session_response = requests.get(session_url)
                
                # If page doesn't exist, try the previous year or decrement session
                if session_response.status_code == 404:
                    print(f"404 for session {current_session} ({current_year})")
                    
                    # Try the same session in the previous year
                    prev_year = current_year - 1
                    prev_year_url = PDF_URL_TEMPLATE.format(year=prev_year, session=current_session)
                    
                    print(f"Trying previous year: {prev_year_url}")
                    prev_year_response = requests.get(prev_year_url)
                    
                    if prev_year_response.status_code == 200:
                        # Found in previous year
                        current_year = prev_year
                        session_response = prev_year_response
                        session_url = prev_year_url
                        print(f"Found in previous year: {current_year}")
                    else:
                        # Not found in previous year either, decrement session
                        current_session -= 1
                        if current_session < 900:  # Lower limit
                            break
                        continue
                
                # Parse the page to find the PDF link
                session_root = etree.fromstring(session_response.content)
                
                # Use the correct class name 'downloadLink' to find the PDF link
                pdf_link_elements = session_root.xpath('//a[@class="downloadLink"]')
                
                if not pdf_link_elements:
                    print(f"Warning: Could not find PDF link for session {current_session}")
                    current_session -= 1
                    continue
                
                pdf_link = pdf_link_elements[0].attrib['href']
                if not pdf_link.startswith('http'):
                    pdf_link = BASE_URL + pdf_link
                
                print(f"Found PDF for session {current_session} ({current_year}): {pdf_link}")
                yield current_session, pdf_link
                
                # Move to the previous session
                current_session -= 1
                
            except Exception as e:
                print(f"Error processing session {current_session}: {str(e)}")
                current_session -= 1
                # If we encounter too many errors, we might want to stop
                if current_session < 900:  # Arbitrary lower limit
                    break

#Senats/BR Texts and TOPS in SL all have same formatting
class SenatsAndBRTextExtractor(PDFTextExtractor.AbstractSenatsAndBRTextExtractor):

    def __init__(self, cutter, senatsTextPrefix="Haltung\sSL:"):
        self.senatsTextPrefix = senatsTextPrefix
        super().__init__(cutter)

    def _extractSenatBRTexts(self, selectionCurrentTOP, selectionNextTOP):
        page_heading = 73 #Bottom of heading on each page
        page_footer = 1260 #Upper of footer on each page

        #Get indented Text, Senats/BR text is everything below it, need to check below this because otherwise I also filter Name of TOP

        #Because selectionNextTOP is never empty (but could be empty selector), I can use it without checking if it is None or empty
        senatTitleSelection = self.cutter.all().filter(auto_regex="^{}".format(self.senatsTextPrefix)).below(selectionCurrentTOP)
        BRTitleSelection = self.cutter.all().filter(auto_regex="^Ergebnis\sBR:").below(selectionCurrentTOP)
        if selectionNextTOP: #Otherwise Always empty text if no next TOP
            senatTitleSelection = senatTitleSelection.above(selectionNextTOP)
            BRTitleSelection = BRTitleSelection.above(selectionNextTOP)

        senats_text = self.cutter.all().filter(
                doc_top__gte = senatTitleSelection.doc_top-1 #Senats Text starts next to title
        )
        if BRTitleSelection: #Otherwise Always empty text if BRTitleSelection empty
            senats_text = senats_text.above(BRTitleSelection)

        br_text = self.cutter.all().filter(
                doc_top__gte = BRTitleSelection.doc_top-1, #BR Text starts next to title
                auto_regex="^[^_]+" #Each TOP ends with ----- line, filter this one out
        )
        if selectionNextTOP: #Otherwise Always empty text if no next TOP
            br_text = br_text.above(selectionNextTOP)

        senats_text = senats_text.clean_text()
        br_text = br_text.clean_text()

        # Although in 973 TOP 9, senats_text ends with many blank lines, in JSON they are somehow striped
        return senats_text, br_text

#Senats/BR Texts and TOPS in SL all have same formatting
class TextExtractorHolder(PDFTextExtractor.TextExtractorHolder):

    def _getRightTOPPositionFinder(self, top):
        if self.sessionNumber <= 992:
            if self.sessionNumber == 992 and top in ["23. b)", "69. b)", "69. d)"]:
                return PDFTextExtractor.CustomTOPFormatPositionFinder(self.cutter, formatSubpartTOP="{number}{subpart}") #Somehow dot not in same chunk as number and subpart
            if self.sessionNumber == 992 and "40" in top: #992 40 a,b,c are very weird (all TOPs before the text, would have to take 41 as next TOP, dont have upper bound for text ...), need this for right Text 39 (nextTop is 40a
                return PDFTextExtractor.DefaultTOPPositionFinder(self.cutter)

            return PDFTextExtractor.CustomTOPFormatPositionFinder(self.cutter, formatSubpartTOP="{number}{subpart}.") #25a.
        elif self.sessionNumber >= 993:
            return PDFTextExtractor.CustomTOPFormatPositionFinder(self.cutter, formatNumberOnlyTOP="{number}", formatSubpartTOP="{number}{subpart}", TOPRight=100)


    # Decide if I need custom rules for special session/TOP cases because PDF format isn't consistent
    #In BW all Text Rules are consistent
    def _getRightSenatBRTextExtractor(self, top, cutter): 
        if self.sessionNumber == 992 and "40" in top: #992 40 a,b,c are very weird (all TOPs before the text, would have to take 41 as next TOP, dont have upper bound for text ...), therefore do this statically
            senatsText = "Stellungnahme gemäß Drs. 295/1/20 (Enthaltung zu Ziffern 13, 31, 32," # For all subparts same
            brText = "Stellungnahme gemäß Drs. 295/1/20 ohne Ziffern 20, 26, 32 sowie 40 bis 44 (Sammelabstimmung zu Ziffern 1 bis 7, 9, 10, 14 bis 18, 21 bis 24, 28 bis 30, 33 bis 38 und 47 bis 50)"
            return PDFTextExtractor.StaticTextSenatsAndBRTextExtractor(cutter, senatsText, brText)
        if self.sessionNumber == 984 and top == "26.":
            return SenatsAndBRTextExtractor(cutter, senatsTextPrefix="Haltung") #Forgot "SL:" 984 26 , only reason for this parameter
        return SenatsAndBRTextExtractor(cutter)
