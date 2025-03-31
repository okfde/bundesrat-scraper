import re
import pdb

import requests
from lxml import html

import pdfcutter

# Import relative Parent Directory for Helper Classes
import os, sys
sys.path.insert(0, os.path.abspath('..')) #Used when call is ` python3 file.py`
sys.path.insert(0, os.path.abspath('.')) #Used when call is ` python3 $COUNTY/file.py`
import helper
import selectionVisualizer as dVis
import PDFTextExtractor
import MainBoilerPlate

INDEX_URL = 'https://www.niedersachsen.de/politik_staat/bundesrat/abstimmungsverhalten_niedersachsen_im_bundesrat/abstimmungsverhalten-niedersachsen-im-bundesrat-157696.html'

NUM_RE = re.compile(r'(\d+)\. .*Sitzung des Bundesrates') #991 has "(Sonder-) Sitzung in name"
LINK_TEXT_RE = re.compile(r'Abstimm(?:ung)?sverhalten und Beschlüsse vom.*') #In 2020 added "Abstimmungsverhalten und Beschlüsse des Bundesrates durch seine Europakammer am 21. April 2020" that I dont want, so added "vom" to regex
SENAT_TEXT_RE = re.compile(r'^Haltung\sNI\s*:\s*(.*)')
BR_TEXT_RE = re.compile(r'^Ergebnis\sBR\s*:\s*(.*)')

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):

    #Out: Dict of {sessionNumberOfBR: PDFWebLink} entries
    def _get_pdf_urls(self):
        response = requests.get(INDEX_URL)
        
        # Get the HTML content as text
        content = response.text
        
        # Split the content into lines for easier processing
        lines = content.split('\n')
        
        result_dict = {}
        
        # Process each line
        for i, line in enumerate(lines):
            # Look for lines containing session numbers
            session_match = re.search(r'(\d+)\.\s+Sitzung', line)
            if session_match:
                current_session = int(session_match.group(1))
                print(f"Found session number: {current_session}")
                
                # Check if this line already has an href
                href_match = re.search(r'href="(https://www\.niedersachsen\.de/download/\d+)"', line)
                if href_match:
                    # If href is in the same line, use it
                    link = href_match.group(1)
                    print(f"Found link in same line for session {current_session}: {link}")
                    result_dict[current_session] = link
                else:
                    # Otherwise, look for href in the next line
                    if i + 1 < len(lines):
                        next_line = lines[i + 1]
                        href_match = re.search(r'href="(https://www\.niedersachsen\.de/download/\d+)"', next_line)
                        if href_match:
                            link = href_match.group(1)
                            print(f"Found link in next line for session {current_session}: {link}")
                            result_dict[current_session] = link
                        else:
                            # If not found in the next line, look a few more lines ahead
                            for j in range(2, 5):
                                if i + j < len(lines):
                                    next_line = lines[i + j]
                                    href_match = re.search(r'href="(https://www\.niedersachsen\.de/download/\d+)"', next_line)
                                    if href_match and ('Abstimm' in next_line or 'Beschlüsse' in next_line):
                                        # Make sure there's no other session number between
                                        found_another_session = False
                                        for k in range(1, j):
                                            if i + k < len(lines):
                                                intermediate_line = lines[i + k]
                                                if re.search(r'(\d+)\.\s+Sitzung', intermediate_line):
                                                    found_another_session = True
                                                    break
                                        
                                        if not found_another_session:
                                            link = href_match.group(1)
                                            print(f"Found link in line {j} ahead for session {current_session}: {link}")
                                            result_dict[current_session] = link
                                            break
        
        # Handle special case for session 1040 - verify it has the correct URL
        if 1040 in result_dict:
            # The URL for session 1040 should contain "202513" (from the webpage)
            if "202513" not in result_dict[1040]:
                # Search specifically for the correct URL
                for line in lines:
                    if "1040. Sitzung" in line or "15. Dezember 2023" in line:
                        href_match = re.search(r'href="(https://www\.niedersachsen\.de/download/202513)"', line)
                        if href_match:
                            correct_url = href_match.group(1)
                            print(f"Correcting URL for session 1040: {correct_url}")
                            result_dict[1040] = correct_url
                            break
        
        print(f"Total matches found: {len(result_dict)}")
        
        # Return the results
        for session_num, url in sorted(result_dict.items(), reverse=True):
            print(f"Yielding: {session_num} -> {url}")
            yield session_num, url

# For Niedersachsen 970, All two digit Numbers of TOP are cut into two lines. Handle here for 10. to 97.
class TOPPositionFinder970MultiDigitNumber(PDFTextExtractor.DefaultTOPPositionFinder):
    def _getNumberSelection(self, number):
        # Split by PDF Pattern 10-97
        firstDigits = number[:-2] # 123. -> 12
        lastDigitDot = number[-2:] # 12. -> 2. 
        return self._getNumberSelectionSplittedNumber(firstDigits, lastDigitDot)

    #Used when Number is split into different chunks/lines in PDF
    #e.g. 10. -> 1\n0. in NS 970 10.,
    #Chunk of TOP with only number is defined as highest chunk with *first* part of the number
    #Main Idea: Go through all chunks x starting with *last* part of number, from highest to lowest. If "slightly" above this chunk there is a line y that starts with *first* part of number, return the first satisfying y as number chunk (by Definition)
    def _getNumberSelectionSplittedNumber(self, firstPartNumber, lastPartNumber):
        escapedFirstPartNumber = helper.escapeForRegex(firstPartNumber) #Not super necessary, but doesn't hurt
        escapedLastPartNumber = helper.escapeForRegex(lastPartNumber) #Here necessary because of dot

        #Get all chunks that start with *last* part of number. 
        allSelectionsLastPartNumber = self.cutter.filter(auto_regex='^{}'.format(escapedLastPartNumber))# Returns all Selections that have Chunks which start with the number

        #Sort them from highest to lowest
        sortedAllSelecionsLastPartNumber = sorted(allSelectionsLastPartNumber, key= lambda x: x.doc_top) #Sort by appearance

        firstPartNumberSelection = None
        for selection in sortedAllSelecionsLastPartNumber: #Start with highest selection
            #All Chunks that are "slightly" (strict) above last part number chunk
            aboveSelections = self.cutter.all().filter(
                doc_top__gte=selection.doc_top - 50 ,
                doc_bottom__lte = selection.doc_top ,
            )
            #Any Chunk slightly above that starts with *first* part of number?
            maybeFirstPartNumberAboveSelection = aboveSelections.filter(auto_regex='^{}$'.format(escapedFirstPartNumber))

            if len(maybeFirstPartNumberAboveSelection) == 1: #There is exactly one such selection
                #Therefore. return it (per Definition) as number chunk and stop
                firstPartNumberSelection = maybeFirstPartNumberAboveSelection
                break
        return firstPartNumberSelection

# For Niedersachsen 970, All tow digit Numbers of TOP from 10. are cut into two lines. Handle this for TOPs 98. until end
class TOPPositionFinder970MultiDigitNumber2(TOPPositionFinder970MultiDigitNumber):
    def _getNumberSelection(self, number):
        #e.g. 98. -> 98\n. in NS 970 98.,
        firstTwoDigits = number[:2] # 123. -> 12, 10 -> 10
        lastPartNumber = number[2:] # 98. -> . , 107. -> 7.   (Only part in same chunk)

        # Do same as for 10-97 with different split of number
        return self._getNumberSelectionSplittedNumber(firstTwoDigits, lastPartNumber)

#Have problem here finding 18 b) TOP Position because ob "(LFG*B)" String in same TOP. Always marks this string, so forbid anychunk containing "G" for this exact TOP
class TOPPositionFinder985TOP18b(PDFTextExtractor.DefaultTOPPositionFinder):

    # Almost same as parent method, only forbid "G" in selection for this TOP
    def _getSubpartSelectionNonStrictBelowNumberSelection(self, subpart,  numberSelection):
        escapedSubpart = helper.escapeForRegex(subpart)
        numberUpperBorder = self.cutter.all().filter(
            doc_top__gte=numberSelection.doc_top - 50 ,
        ) 
        allSelectionsSubpartNonStrictBelowNumber = numberUpperBorder.filter(regex= "[^G]" + escapedSubpart) #Disallow G in Selection for TOP 18. b) because of "(LFGB)" getting attention too (although upper case?)
        return self._getHighestSelection(allSelectionsSubpartNonStrictBelowNumber) 

# For Niedersachsen e.g. 990 Format for TOP with Subpart is now e.g. 2.a and not 2. a) anymore
# Yes, 980 still uses old format
class TOPPositionFinderDifferentTOPSubpartFormat(PDFTextExtractor.DefaultTOPPositionFinder):
    #In this session, subpart always in same chunk as number with format e.g. 2.a
    #Chunk of TOP := Chunk of Subpart
    def _getTOPSubpartSelection(self, top):
        number, subpart = top.split() #46. b) -> [46., b)]
        formattedTOP = number + subpart[:-1] #[46., b)] -> "46.b"
        topSelection = self._getNumberSelection(formattedTOP) #Not only number, but still works
        return topSelection

#For Session 974, TOPs 53 to 57, they forgot to add point after TOP number
class TOPPositionFinder974ForgotNumberPoint(PDFTextExtractor.DefaultTOPPositionFinder):
    #Cut off . from e.g. before proceeding as usual
    def _getNumberSelection(self, number):
        numberWithoutPoint = number[:-1]
        escapedNum = helper.escapeForRegex(numberWithoutPoint)
        allSelectionsNumber = self.cutter.filter(auto_regex='^{}'.format(escapedNum))# Returns all Selections that have Chunks which start with the number
        return self._getHighestSelection(allSelectionsNumber)


#Senats/BR Texts in NS almost all have same formatting
class SenatsAndBRTextExtractor(PDFTextExtractor.AbstractSenatsAndBRTextExtractor):
    def _extractSenatBRTexts(self, selectionCurrentTOP, selectionNextTOP):
        page_heading = 73 #Bottom of heading on each page
        page_footer = 1260 #Upper of footer on each page
        senats = self.cutter.filter(auto_regex='^Haltung\sNI')
        senats = senats.below(selectionCurrentTOP)
        if selectionNextTOP:
            senats = senats.above(selectionNextTOP)

        #INFO Space relevant because without Rules broke because of "Ergebnisse" in NS 970 70a
        #INFO But can't filter 'Ergebnis BR' directly, because these two words are sometimes in different chunks
        ergebnis_br = self.cutter.filter(auto_regex='^Ergebnis\s[^kz]').below(selectionCurrentTOP) #976 26 "Ergebnis keine ..." makes problems, so forbid k after Ergebnis Regex + 976 46. "Ergebnis Zustimmung" makes problems as well


        if selectionNextTOP:
            ergebnis_br = ergebnis_br.above(selectionNextTOP)

        #cutter.above() is strict, can get it non strict by going a little bit higher
        senats_text = self.cutter.all().filter(
            doc_top__gte=senats.doc_top - 1 ,
            top__gte=page_heading,
            bottom__lt=page_footer,
        )


        br_text = self.cutter.all().filter(
            doc_top__gte=ergebnis_br.doc_top - 1 ,#Relative to all pages
            top__gte=page_heading,
            bottom__lt=page_footer,
        )

        if selectionNextTOP:
            br_text = br_text.above(selectionNextTOP)
            senats_text = senats_text.above(ergebnis_br)


        #Cut away "Haltung NI:" and "Ergebnis BR:" from text
    #    print("current_top", current_top.clean_text())

        senats_text = senats_text.clean_text()
    #    print("next top", next_top)
    #    print("senats_text", senats_text)
        if senats_text != "" and SENAT_TEXT_RE.search(senats_text): #Missing for 1048 TOP 10
            senats_text = SENAT_TEXT_RE.search(senats_text).group(1)

        br_text = br_text.clean_text()
    #    print("br_text", br_text)
        if br_text != "" and BR_TEXT_RE.search(br_text): #Missing for 1048 TOP 10
            br_text = BR_TEXT_RE.search(br_text).group(1)
        if not senats_text.strip():
            print('empty')

        return senats_text, br_text

#Session 988 for NS doesn't have all TOPs in it, skips the ones not discussed -> currentTOP/nextTOP can be empty! Have to compute next TOP out of current TOP alone as bottom border for texts
#Don't extend DefaultTOPPositionFinder here, because this one doesn't know if its currently searching for current or next TOP, so can't distiguish there
class SenatsAndBRTextExtractor988(SenatsAndBRTextExtractor):

    #If selection for current TOP is empty -> current TOP not discussed -> return empty strings for text
    #If selection for next TOP is empty -> Have to find alternative next TOP below current TOP as bottom border for texts
    def _extractSenatBRTexts(self, selectionCurrentTOP, selectionNextTOP):
        if len(selectionCurrentTOP) == 0:
            return "", "" #TOP not discussed -> No Senats/BR Text
        #Recomputer alternative next TOP if there exists one
        if len(selectionNextTOP) == 0:
            # All Strings below current TOP and in same column (left/right almost equal
            selectionsNextPDFTOPs = self.cutter.all().filter(
                    doc_top__gt  = selectionCurrentTOP.doc_top,
                    left__gte = selectionCurrentTOP.left - 10,
                    right__lte = selectionCurrentTOP.right + 30, #Offset for subpart
            )
            selectionDirectNextTOP = self._getHighestSelectionNotEmpty(selectionsNextPDFTOPs)# Could be empty, but this is handeled by super method as well
            return super()._extractSenatBRTexts(selectionCurrentTOP, selectionDirectNextTOP)

        #Both Selecions present -> proceed as usual
        return super()._extractSenatBRTexts(selectionCurrentTOP, selectionNextTOP)

    #Fork of DefaultTOPPositionFinder class in PDFTextExtractor File, but need it now for finding alternative next TOP as well, so just copy-pasted it and added not empty Selecion Check.
    def _getHighestSelectionNotEmpty(self, selections): 
        if len(selections) == 0: #min throws error for empty set
            return selections
        #notEmptySelecions = selections.filter(regex="[^ ]+")
#        return min(notEmptySelecions, key= lambda x: x.doc_top)
        return min(selections, key= lambda x: x.doc_top)

#NS forgot to add 31b), 33 in PDF of session 983, so for selection of 31. b) as next TOP, give 32. for 33) give 34.) , and as current TOP give Nothing
#Don't extend DefaultTOPPositionFinder here, because this one doesn't know if its currently searching for current or next TOP, so can't distinguish there
class SenatsAndBRTextExtractor983SpecialTOPs31b33(SenatsAndBRTextExtractor):

    #If selection for current TOP is empty -> current TOP not discussed -> return empty strings for text
    #If selection for next TOP is empty -> Have to find alternative next TOP below current TOP as bottom border for texts
    def _extractSenatBRTexts(self, selectionCurrentTOP, selectionNextTOP):

        #wrong 31. b) selection matches "(SGB)" Subtring (although upper case?) -> Return no text
        if "(SGB)" in selectionCurrentTOP.clean_text():
            return "", "" #TOP not discussed -> No Senats/BR Text
        #wrong 31. b) selection matches "(SGB)" Subtring (although upper case?) -> use TOP 32. as bottom border for texts

        #CurrentTOP is last in PDF, therefore selectionNextTOP is None -> Proceed as usual
        if selectionNextTOP == None:
            return super()._extractSenatBRTexts(selectionCurrentTOP, selectionNextTOP)

        if "(SGB)" in selectionNextTOP.clean_text():
            selecionNextTOP32 = PDFTextExtractor.DefaultTOPPositionFinder(self.cutter).getTOPSelection("32.") #Search for TOP 32 Chunk
            #Proceed as usual
            return super()._extractSenatBRTexts(selectionCurrentTOP, selecionNextTOP32)

        #wrong 33. selection selects nothing -> Return no text
        if len(selectionCurrentTOP) == 0:
            return "", "" #TOP not discussed -> No Senats/BR Text

        #wrong 33. selection selects nothing -> use TOP 34. as bottom border for texts
        if len(selectionNextTOP) == 0 :
            selecionNextTOP34 = PDFTextExtractor.DefaultTOPPositionFinder(self.cutter).getTOPSelection("34.") #Search for TOP 34 Chunk
            #Proceed as usual
            return super()._extractSenatBRTexts(selectionCurrentTOP, selecionNextTOP34)

        #Both Selections Good -> Proceed as usual
        return super()._extractSenatBRTexts(selectionCurrentTOP, selectionNextTOP)

class NSTextExtractorHolder(PDFTextExtractor.TextExtractorHolder):

    # Decide if I need custom rules for special session/TOP cases because PDF format isn't consistent
    # For NS I need custom TOP Finder Rules (but no custom Senats/BR Text Finder Rules)
    def _getRightTOPPositionFinder(self, top):
        if self.sessionNumber == 970 and 10 <= int(top.split()[0][:-1]) <= 97:
            return TOPPositionFinder970MultiDigitNumber(self.cutter)
        elif self.sessionNumber == 970 and int(top.split()[0][:-1]) >= 98 :
            return TOPPositionFinder970MultiDigitNumber2(self.cutter)
        elif self.sessionNumber in [990,982,981, 979]:
            return TOPPositionFinderDifferentTOPSubpartFormat(self.cutter)
        elif self.sessionNumber == 974 and 53 <= int(top.split()[0][:-1]) <= 57:
            return TOPPositionFinder974ForgotNumberPoint(self.cutter)
        elif self.sessionNumber == 985 and top == "18. b)":
            return TOPPositionFinder985TOP18b(self.cutter)
        elif self.sessionNumber == 992:
            return PDFTextExtractor.DefaultTOPPositionFinder(self.cutter, TOPRight = 140) #"3. Juli" in Header disrupts TOP 3. Finder
        elif self.sessionNumber == 1047:
             return PDFTextExtractor.CustomTOPFormatPositionFinder(self.cutter, formatSubpartTOP="{number}.{subpart}")
        elif self.sessionNumber == 1041:
             return PDFTextExtractor.CustomTOPFormatPositionFinder(self.cutter, formatSubpartTOP="{number}.{subpart})")

        return PDFTextExtractor.DefaultTOPPositionFinder(self.cutter)

    # Decide if I need custom rules for special session/TOP cases because PDF format isn't consistent
    #In NS all Text Rules almost are consistent except 988
    def _getRightSenatBRTextExtractor(self, top, cutter): 
        if self.sessionNumber == 988:
            return SenatsAndBRTextExtractor988(cutter)
        if self.sessionNumber == 983:
            return SenatsAndBRTextExtractor983SpecialTOPs31b33(cutter)
        return SenatsAndBRTextExtractor(cutter)
