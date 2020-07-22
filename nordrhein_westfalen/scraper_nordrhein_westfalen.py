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

    #Decide for sessionNumber and currentTOP, which extractor needed for currentTOPRow
    #Out: (senats_text, br_text) tuple
    def _extractSenatBRTexts(self, currentTOPRow, currentTOP):
        if self.missingTOPInTable(currentTOP): #NRW Forgot them to add these TOPs -> No Text
            return "", ""

        if (self.sessionNumber == 986 and currentTOP == "2.") or (self.sessionNumber == 989 and (currentTOP == "58." or currentTOP == "66." )) or (self.sessionNumber == 992 and (currentTOP == "2." or currentTOP == "14.")) or (self.sessionNumber == 982 and currentTOP == "5." ) or (self.sessionNumber == 971 and currentTOP in ["61.", "64."]) or (self.sessionNumber == 962 and currentTOP in ["1.", "2."]) or (self.sessionNumber == 960 and "21" in currentTOP): #Senats and BR Text in two different p-tags
            return self._extractSenatBRTextsTwoPTags(currentTOPRow)

        if self.subpartIsListValue(currentTOP) or (self.sessionNumber == 984 and currentTOP == "51. b)"): #Subpart by list value attribute, not directly written in table, Need 984 51. b) extra wrt extractTOP - Part because 984 51. b) again a different case for TOP extraction, but not for text extraction
            return self._extractSenatBRTextsSubpartAsListValue(currentTOPRow)

        if (self.sessionNumber == 976 and currentTOP == "33.") or (self.sessionNumber == 962 and currentTOP == "9."): #two p-tags, but Senats and BR Text still both in the first one
            return self._extractSenatBRTextsDefault(currentTOPRow, secondPTagEmpty = True)

        if self.sessionNumber == 963 and currentTOP in ["11. a)", "11. b)", "11. c)"]: # 963 11. a) to c) have no br_text nor senats_text, therefore no p-tag -> would cause Error. So return no text directly. But, 963 11. d) back normal
            return "", "" 

        # INFO: Some TOPs of 962, 961 already already catched above!
        if self.sessionNumber == 962 or self.sessionNumber == 961: #"NRW:" not underlined, so need different method to find it
            return self._extractSenatBRTextsNRWNotUnderlined(currentTOPRow)

        if self.sessionNumber == 960 and currentTOP == "55.": #960 55. has two blocks with senat text (Start with "NRW:" -> Give hint to method that this is ok in this case
            return self._extractSenatBRTextsDefault(currentTOPRow, twoSenatsTextBlocks = True)

        return self._extractSenatBRTextsDefault(currentTOPRow)

    #Senats and BR Text both in same p-tag, seperate both texts on "NRW:" label
    #This "NRW:" label is underlined (inside <u> tag)
    #secondPTagEmpty = True only in 976 33. and 962 9. , there exists a second p-tag, but is is empty. Therefore, parsing like there is only one p-tag
    #twoSenatsTextBlocks = True only for 960 55. because there is one p-tag, but two "NRW:" labels.
    def _extractSenatBRTextsDefault(self, currentTOPRow, secondPTagEmpty = False, twoSenatsTextBlocks = False):
        senats_and_br_text = currentTOPRow.xpath('./td[2]/p') #Text

        if len(senats_and_br_text) != 1 and (not secondPTagEmpty) : #More than one text block in second row cell, have to do something different (except for 960 55. secondPTagEmpty == True)
            raise Exception()

        maybeNRWTag = senats_and_br_text[0].xpath('./u[text()="NRW:"]') #There is a senats_text iff underlined tag with "NRW:" is in row
        if len(maybeNRWTag) == 0: #No "NRW:" label in text -> Everything is BR text
            br_text = senats_and_br_text[0].text_content() #.text only has problems with text inside (tags inside tags). And "nicht" always underlined and therefore not found
            senats_text = ""
        elif len(maybeNRWTag) == 1 or (len(maybeNRWTag) == 2 and twoSenatsTextBlocks ): #Have a "NRW:" Label (or for 960 55. with twoSenatsTextBlocks == True even two such labels)  -> Senats text exists. 

            #Have [1] here because of the case where I have two NRW Labels. Otherwise, I could delete [1], but for two labels it's useful so that br_text doesn't contain first part Senats Text
            br_text = senats_and_br_text[0].xpath('./u[text()="NRW:"][1]/preceding-sibling::* | ./u[text()="NRW:"][1]/preceding-sibling::text() ') #br_text = Find all tags and free text (not inside any tag) that come before the "NRW:" Tag
            senats_text = senats_and_br_text[0].xpath('./u[text()="NRW:"][1]/following-sibling::* | ./u[text()="NRW:"][1]/following-sibling::text()')  #senats_text = Find all tags and free text (not inside any tag) that come after the "NRW:" Tag

            br_text = list(map(lambda x : x.text if type(x) == etree.HtmlElement else x, br_text)) #Extract text for all tags and keep text for all free texts in list
            senats_text = list(map(lambda x : x.text if type(x) == etree.HtmlElement else x, senats_text)) #Extract text for all tags and keep text for all free texts in list

            br_text = [x for x in br_text if x is not None ] #None would create problem with join() later
            senats_text = [x for x in senats_text if x is not None ] #None would create problem with join() later

            #Concat all texts
            br_text = "".join(br_text)
            senats_text = "".join(senats_text)

        else: #More than one "NRW:" Label in row, have to adjust something
            raise Exception()

        return senats_text, br_text

    #Like _extractSenatBRTextsDefault(),
    #but "NRW:" not underlined and not in extra tag anymore -> Have to search in free texts (text())
    #Happens for 962 and 961 (but not for 960 or 963)
    #See senats_text comment for why no merge with _extractSenatBRTextsDefault() + Parameter
    def _extractSenatBRTextsNRWNotUnderlined(self, currentTOPRow):
        senats_and_br_text = currentTOPRow.xpath('./td[2]/p') #Text

        if len(senats_and_br_text) != 1: #More than one text block in second row cell, have to do something different
            raise Exception()

        maybeNRWTag = senats_and_br_text[0].xpath('text()[contains(., "NRW:")]') #Nothing in tags, all free 
        if len(maybeNRWTag) != 1: #If no senats text, then proceed as in Default Case
            return self._extractSenatBRTextsDefault(currentTOPRow)
        # NRW: Label present -> Senats Text there
        # Analog separate text in _extractSenatBRTextsDefault()
        # Have to use contains instead of starts-with because of strange tabs before "NRW:"
        br_text = senats_and_br_text[0].xpath('text()[contains(., "NRW:")]/preceding-sibling::* | text()[contains(., "NRW:")]/preceding-sibling::text() ')
        senats_text = senats_and_br_text[0].xpath('text()[contains(., "NRW:")]  | text()[contains(., "NRW:")]/following-sibling::* | text()[contains(., "NRW:")]/following-sibling::text()') #Also have line with NRW: inside senats text because this text() also contains information. This is the reason I don't merge it with _extractSenatBRTextsDefault()

        #See _extractSenatBRTextsDefault() for explanation
        br_text = list(map(lambda x : x.text if type(x) == etree.HtmlElement else x, br_text))
        senats_text = list(map(lambda x : x.text if type(x) == etree.HtmlElement else x, senats_text))

        br_text = [x for x in br_text if x is not None ] #None would create problem with join() later
        senats_text = [x for x in senats_text if x is not None ] #None would create problem with join() later

        #Concat all texts
        br_text = "".join(br_text)
        senats_text = "".join(senats_text)

        return senats_text, br_text

    #BR Text and Senats Text in two separate p-tags
    #Just return content of these tags as texts
    def _extractSenatBRTextsTwoPTags(self, currentTOPRow):
        senats_and_br_text = currentTOPRow.xpath('./td[2]/p')
        br_text = senats_and_br_text[0].text_content() #underlined "nicht" doesn't works with .text
        senats_text = senats_and_br_text[1].text_content()
        return senats_text, br_text

    #br text is part of a list because of subpart as list tag attribute (see _getTOPTableRowSubpartAsListValue() for explaination) -> slightly different xpath to br_text, but senats_text stays same
    #BR Text and Senats Text in two separate tags, so
    #Just return content of these tags as texts
    def _extractSenatBRTextsSubpartAsListValue(self, currentTOPRow):
        br_text = currentTOPRow.xpath('./td[2]/ol/li/p[1]')[0].text_content() #Jump inside this list to find br_text

        #Senats Exists Check by checking if some tag exists, not by "NRW:" label. Tags more consistent
        maybe_senats_text =  currentTOPRow.xpath('./td[2]/p')
        if len(maybe_senats_text) == 1: #Tag exists -> Senat Text is content
            senats_text = maybe_senats_text[0].text_content()
        else: #No Senats Text for that TOP
            senats_text = ""

        return senats_text, br_text
