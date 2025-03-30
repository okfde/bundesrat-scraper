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

INDEX_URL = 'https://landesvertretung-brandenburg.de/bundesrat/abstimmungsverhalten-im-bundesrat/'
NUM_RE = re.compile(r'(\d+)\. Sitzung des Bundesrates')

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):

    #Out: Dict of {sessionNumberOfBR: PDFWebLink} entries
    def _get_pdf_urls(self):
        response = requests.get(INDEX_URL)
        root = etree.fromstring(response.content)

        #Have three completely different xpaths for year-tables
        #Therefore, filter (almost) all links (a)
        allLinks = root.xpath('//ul/li/a')
        for name in allLinks:
            text = name.text_content()
            maybeNum = NUM_RE.search(text) #Links to a Bundesrat-PDF?
            if maybeNum: #Also have e.g. "Mitglieder Brandenburgs im Bundesrat" as link -> Filter them out
                num = int(maybeNum.group(1))
                link = name.attrib['href']
                link = link.replace(" ", "%20") #Replace Space with HTML Escape Character
                yield int(num), link

#Senats/BR Texts and TOPS in BW  all have same formatting
class SenatsAndBRTextExtractor(PDFTextExtractor.AbstractSenatsAndBRTextExtractor):
    def _extractSenatBRTexts(self, selectionCurrentTOP, selectionNextTOP):
        page_heading = 73 #Bottom of heading on each page
        page_footer = 1160 #Upper of footer on each page

        #Get indented Text, Senats/BR text is everything below it, need to check below this because otherwise I also filter Name of TOP
        TOPRightIndented = self.cutter.all().below(selectionCurrentTOP).filter(
            left__gte = selectionCurrentTOP.left + 100,
            top__lt = page_footer# Match otherwise page number for e.g. 984 26
        )

        if selectionNextTOP:
            TOPRightIndented = TOPRightIndented.above(selectionNextTOP)

        last_indented_with_text = None
        #empty, but present lines below senat text can mess up parsing, so only watch for last non-empty
        for line in TOPRightIndented:
            if line.clean_text().strip(): #empty strings are falsy
                last_indented_with_text = line


        #dVis.showCutter(last_indented_with_text)
        senatsBR_text = self.cutter.all().below(last_indented_with_text)
        #dVis.showCutter(senatsBR_text)
        if selectionNextTOP:
            senatsBR_text = senatsBR_text.above(selectionNextTOP)

        br_text_title = senatsBR_text.filter(auto_regex='^Ergebnis Bundesrat:')
        if br_text_title: #Cut BR away, but above() always empty if no BR title exists
            senats_text = senatsBR_text.above(br_text_title).clean_text()
        else:
            senats_text = senatsBR_text.clean_text()

        #For some reason the BR Text is always empty when I do:
        #BR_text = senatsBR_text.below(BR_text_title).clean_text()
        br_text = senatsBR_text.filter(
            doc_top__gte=br_text_title.doc_top +1 ,
            top__lt = page_footer# Match otherwise page number for e.g. 984 26
        ).clean_text()

        if not senats_text.strip():
            print('empty') #TODO


        return senats_text, br_text

#Senats/BR Texts and TOPS in BW  all have same formatting
class TextExtractorHolder(PDFTextExtractor.TextExtractorHolder):
    def _getRightTOPPositionFinder(self, top):
        TOPRight=200
        if self.sessionNumber >= 1033:
            formatTOPsWithSubpart="{number}\s{subpart}" #e.g. BB 1051 is "19 c". For some reason, I can't use a normal space, but I also can't find the "right" space symbol
        elif self.sessionNumber == 1032:
            formatTOPsWithSubpart="{number}.\s{subpart}" #e.g. BB 1032 is 29. a
        elif self.sessionNumber >= 1020:
            formatTOPsWithSubpart="{number}\s{subpart}" #e.g. BB 1030 is "19 c". For some reason, I can't use a normal space, but I also can't find the "right" space symbol
        elif self.sessionNumber == 1019:
            formatTOPsWithSubpart="{number}{subpart}" #e.g. BB 1019 is "20a".
        elif self.sessionNumber >= 1015:
            formatTOPsWithSubpart="{number}\s{subpart}" #e.g. BB 1030 is "19 c". For some reason, I can't use a normal space, but I also can't find the "right" space symbol
        elif self.sessionNumber >= 999:
            formatTOPsWithSubpart="{number}{subpart}" #e.g. BB 1030 is "19 c". For some reason, I can't use a normal space, but I also can't find the "right" space symbol
        elif self.sessionNumber == 998:
            formatTOPsWithSubpart="{number}.{subpart})" #e.g. BB 1030 is "19 c". For some reason, I can't use a normal space, but I also can't find the "right" space symbol
        elif self.sessionNumber == 997:
            formatTOPsWithSubpart="{number}. {subpart})" #e.g. BB 1030 is "19 c". For some reason, I can't use a normal space, but I also can't find the "right" space symbol
        elif self.sessionNumber >= 993:
            formatTOPsWithSubpart="{number}{subpart}" #e.g. BB 1030 is "19 c". For some reason, I can't use a normal space, but I also can't find the "right" space symbol
        elif self.sessionNumber >= 986:
            formatTOPsWithSubpart="{number}{subpart}" #e.g. BB 992 23. a) is "23a"
        elif self.sessionNumber == 985:
            formatTOPsWithSubpart="{number} {subpart}" #e.g. BB 985 9. a) is "9 a"
        elif self.sessionNumber == 980 and top in ["2. a)", "2. b)", "25. a)", "25. b)"]: #980 80a is like the next case below again
            formatTOPsWithSubpart="{number} {subpart}" #e.g. BB 980 "2. a)" is "2 a"
        elif 974 <= self.sessionNumber <= 984:
            formatTOPsWithSubpart="{number}{subpart}" #e.g. BB 984 45. a) is "45a"
            if self.sessionNumber == 984:
                TOPRight = 145 # Else match 26. with "26. März..." of TOP 15

        elif 970 <= self.sessionNumber <= 973:
            formatTOPsWithSubpart="{number}{subpart}." #e.g. BB 973 25. a) is "25a."
        elif 968 <= self.sessionNumber <= 969:
            formatTOPsWithSubpart="{number} {subpart}" #e.g. BB 969 21. a) is "21 a"
        elif self.sessionNumber <= 967:
            formatTOPsWithSubpart="{number}{subpart}." #e.g. BB 967 3. a) is "3a."

        return PDFTextExtractor.CustomTOPFormatPositionFinder(self.cutter, formatSubpartTOP=formatTOPsWithSubpart, TOPRight=TOPRight) #945 13. in date would cause problems without TOPRight
    # Decide if I need custom rules for special session/TOP cases because PDF format isn't consistent
    #In BW all Text Rules are consistent
    def _getRightSenatBRTextExtractor(self, top, cutter): 
        return SenatsAndBRTextExtractor(cutter)

