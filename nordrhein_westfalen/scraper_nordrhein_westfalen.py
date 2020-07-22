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

INDEX_URL = 'https://www.mbei.nrw/de/abstimmverhalten'
BASE_URL='https://www.mbei.nrw/'
NUM_RE = re.compile(r'/de/(\d+)-sitzung')

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):

    #Out: Dict of {sessionNumberOfBR: WebLink} entries
    #No PDF but html Links, but still works
    def _get_pdf_urls(self):
        response = requests.get(INDEX_URL)
        root = etree.fromstring(response.content)

        names = root.xpath('/html/body/div[2]/div/div[1]/div/div[2]/div/div[2]/div/div/div/div/div[1]/div/div[1]/div/article/div/div[3]/div/div/p/a') #NRW adds Texts for future sessions, but this xpath doesn't match them
        for name in names:
            link = name.attrib['href']
            num = int(NUM_RE.search(link).group(1))
            if "http" in link : #already full path in a tag (e.g. BA 951), else append to absolute path
               realLink = link
            else:
               realLink = BASE_URL + link 
            yield num, realLink

#Don't have to change scraper.ipynb when derive TextExtractorHolder. But basically re-implement everything for HTML Parsing
#Also have TOPFinder and TextExtractor all in here, didn't want to add new classes for only one HTML County
class TextExtractorHolder(PDFTextExtractor.TextExtractorHolder):

    #Store WebsiteTable Root (HTML) instead of cutter (PDF)
    def __init__(self, filename, session):
        #request.get with local file doesn't work
        html=""
        with open(filename, 'r') as file:
            html = file.read().replace('\n', '') 
        websiteRoot = etree.fromstring(html)

        topsTable = websiteRoot.xpath('//table') # More clever xpaths don't work again
        if len(topsTable) != 1: #More than one table on website, have to adjust something
            raise Exception()
        self.topsTable = topsTable[0]
        self.session = session
        self.sessionNumber = int(self.session['number']) #Often needed to check if I need special parse rules

    #Hotswap Rules for finding TOP and extracting Senat/BR Text w.r.t. session number and TOP
    #Out: (SenatText, BRText) Tuple
    #Called by scraper.ipynb
    #First find right row for currentTOP, then extract BR/SenatsTexts
    #Don't need nextTOP for NRW HTML, but don't need to adjust scraper.ipynb when using this class
    def _getSenatsAndBRTextsForCurrentTOP(self, currentTOP, nextTOP):
        currentTOPRow = self._getTOPTableRow(currentTOP)
        return self._extractSenatBRTexts(currentTOPRow, currentTOP)

    #In: currentTOP e.g. "12. a)"
    #Out: etree row corresponding to TOP, else None
    def _getTOPTableRow(self, currentTOP):
        if self.missingTOPInTable(currentTOP):
            return None
        if self.subpartIsListValue(currentTOP): #Subpart by list value attribute, not directly written in table
            return self._getTOPTableRowSubpartAsListValue(currentTOP)
        if self.sessionNumber == 984 and currentTOP == "51. b)": #Have to add extra offset because 51. b) is mistakenly 51. c) in table
            return self._getTOPTableRowSubpartAsListValue(currentTOP, offsetSubpart = 1)
        if self.sessionNumber == 961 and len(currentTOP.split()) == 2: #Subparts in 961 are bold, so have to add extra tag to find right tags where "NRW:" stays
            return self._getTOPTableRowDefault(currentTOP, xpathSenatTextNRWLabelInRow="td/strong")
        return self._getTOPTableRowDefault(currentTOP)

    #NRW Forgot to add these TOPs in corresponding table
    def missingTOPInTable(self, currentTOP):
        return (self.sessionNumber == 973 and int(currentTOP.split()[0][:-1]) >= 47) or (self.sessionNumber == 969 and int(currentTOP.split()[0][:-1]) >= 69)

    #Subpart by list value attribute, not directly written in table
    def subpartIsListValue(self, currentTOP):
        return (self.sessionNumber == 992 and len(currentTOP.split()) == 2 and int(currentTOP.split()[0][:-1]) >= 69) or (self.sessionNumber == 991) or (self.sessionNumber == 984 and currentTOP in ["45. a)", "45. b)"] ) or (self.sessionNumber == 980 and "80" in currentTOP ) or (self.sessionNumber == 976 and "39" in currentTOP) or (self.sessionNumber == 966 and "37" in currentTOP )


    #xpathSenatTextNRWLabelInRow only for 961 subpart TOPs different than "td", because subparts in 961 are bold, so have to add extra tag to find right tags where "NRW:" stays
    #Subpart is always written inside table
    def _getTOPTableRowDefault(self, currentTOP, xpathSenatTextNRWLabelInRow="td"):
        splitTOP = currentTOP.split()# "46. b) -> ["46.", "b)"]

        if len(splitTOP) == 1:#TOP only number
            allRows = self.topsTable.xpath('//td[text()="{}"]'.format(currentTOP)) #Find td (cell) with TOP number as text
            if len(allRows) != 1: #More than one td/cell with this TOP number in table, have to do something different
                raise Exception()
            row = allRows[0].xpath('..')[0] #Find corresponding parent row (tr) of TOP Number cell (td)
            return row

        #Here, TOP always has Number + Subpart
        number, subpart = splitTOP #"46.", "b)"
        allRows = self.topsTable.xpath('//td[text()="{}"]'.format(number)) #Find td (cell) with TOP number as text

        if len(allRows) != 1: #More than one td/cell with this TOP number in table, have to do something different
            raise Exception()
        if subpart == "a)": #Number row == TOP with subpart a) row -> Return this
            row = allRows[0].xpath('..')[0] #Find corresponding parent row (tr) of TOP Number cell (td)
            return row

        # Number + subpart > a)
        number_row = allRows[0].xpath('..')[0] #Find corresponding parent row (tr) of TOP Number cell (td)
        subpart_cell = number_row.xpath('./following-sibling::tr/{}[starts-with(text(), "{}")]'.format(xpathSenatTextNRWLabelInRow, subpart))[0] #Find Tags that are below number row and start with subpart as text. First Match is cell of right subpart
        xpathBackToTrParent = "/".join([".."] * len(xpathSenatTextNRWLabelInRow.split("/"))) #Find corresponding parent row (tr) of TOP Number cell (td or td/strong). Can happen that 2 "levels" below tr, so use .. as often as needed, e.g. td -> ".." , td/strong -> "../.."
        subpart_row = subpart_cell.xpath(xpathBackToTrParent)[0] #Compute tr parent
        return(subpart_row)

    #Subpart is given as list attribute e.g. 992 69 b). b) is marked only as <list value = 2>. value = 3 -> c) and so on.
    #However, a) is always <list>, without any "value" number
    #currentTOP always a subpart TOP
    #offsetSubpart only used for 984 51 b), because "51. b)" has mistakenly value = 3 , which corresponds to c)
    def _getTOPTableRowSubpartAsListValue(self, currentTOP, offsetSubpart = 0):
        # Number + Subpart
        number, subpart = currentTOP.split()
        allRows = self.topsTable.xpath('//td[text()="{}"]'.format(number)) #Find td (cell) with TOP number as text
        number_row = allRows[0].xpath('..')[0] #Find corresponding parent row (tr) of TOP Number cell (td)
        if subpart == "a)": #Number Row == Subpart a) row
            return number_row

        #li value == 2 means writes "b.", == 3 means "c." ....
        #li no value -> a. (Catched above)
        #Therefore, get ascii number of subpart (ord(char)) and transform in right number (-96)
        subpartLetterOnly = subpart[:-1] #b) -> b
        subpartLetterNumber = ord(subpartLetterOnly) - 96 # b = 98 - 96 = 2 , c = 98 - 96 = 3 ...
        subpart_cell = number_row.xpath('./following-sibling::tr/td/ol/li[@value="{}"]'.format(subpartLetterNumber + offsetSubpart))[0] #Find Tags that are below number row and start with subpart as text inside a cell/list/list. First Match is cell of right subpartmore than one
        subpart_row = subpart_cell.xpath('../../..')[0] #ol -> td -> tr like in _getTOPTableRowDefault Method
        return(subpart_row)
