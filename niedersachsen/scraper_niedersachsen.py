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

INDEX_URL = 'https://niedersachsen.de/startseite/politik_staat/bundesrat/abstimmungsverhalten_niedersachsen_im_bundesrat/abstimmungsverhalten-niedersachsens-im-bundesrat-157696.html'

NUM_RE = re.compile(r'(\d+)\. Sitzung des Bundesrates')
LINK_TEXT_RE = re.compile(r'Abstimmungsverhalten und Beschlüsse vom.*') #In 2020 added "Abstimmungsverhalten und Beschlüsse des Bundesrates durch seine Europakammer am 21. April 2020" that I dont want, so added "vom" to regex
SENAT_TEXT_RE = re.compile(r'^Haltung NI\s*:\s*(.*)')
BR_TEXT_RE = re.compile(r'^Ergebnis BR\s*:\s*(.*)')

#Rules for parsing pdfs for Senats and BR text per TOP
#Mostly used as Namespace
#Rules different for each County, so Counties can derive this class
#Need self so that derived classes point to themself and not always to parent
class SelectionRules:

    def __init__(self, cutter):
        self.cutter = cutter #Needed everywhere, so store it here

    def getTOPSelection(self, top):

        if len(top.split()) == 2: #TOP has Subpart, Subpart not always inside same chunk as number
            return self._getTOPSubpartSelection(top)
        else: #TOP only has number
            return self._getNumberSelection(top)

    #Subpart not always inside same chunk as number, so first get selection s for number, then return selection s2 for first chunk containing subpart that is (non-strict) below s
    #Chunk of TOP := Chunk of Subpart
    def _getTOPSubpartSelection(self, top):
        number, subpart = top.split() #46. b) -> [46., b)]
        numberSelection = self._getNumberSelection(number)
        #dVis.showCutter(numberSelection)
        topSelection = self._getSubpartSelectionNonStrictBelowNumberSelection(subpart, numberSelection)
        #dVis.showCutter(topSelection)
        return topSelection

    def _getNumberSelection(self, number):
        escapedNum = helper.escapeForRegex(number)
        allSelectionsNumber = self.cutter.filter(auto_regex='^{}'.format(escapedNum))# Returns all Selections that have Chunks which start with the number
        return self._getHighestSelection(allSelectionsNumber)

    #pdfcutter sorts selections by height on page, not by absolute (doc_top) height. We do this here
    def _getHighestSelection(self, selections): 
        if len(selections) == 0: #min throws error for empty set
            return selections
        return min(selections, key= lambda x: x.doc_top)


    # Get Selection of first chunk below given number chunk that starts with subpart. As Subpart can (not must) be in same chunk as number, also consider numberSelection (non-strict)
    def _getSubpartSelectionNonStrictBelowNumberSelection(self, subpart,  numberSelection):
        escapedSubpart = helper.escapeForRegex(subpart)
        numberUpperBorder = self.cutter.all().filter(
            doc_top__gte=numberSelection.doc_top - 50 , #Return all Chunks below given numer chunk and the number chunk itself. subpart chunk could be same as number chunk
        ) # INFO a) for 1. a) NS 970 in same chunk, for 34. a) not

        # All Chunks non-strict below number chunk that contain given subpart
        allSelectionsSubpartNonStrictBelowNumber = numberUpperBorder.filter(auto_regex=escapedSubpart) #46. b) -> b\) because of regex brackets
        #Return highest of these
        #INFO adding number chunk as upperbound can break this when subpart chunk == number chunk
        return self._getHighestSelection(allSelectionsSubpartNonStrictBelowNumber) 

class SelectionRules970MultiDigitNumber(SelectionRules):
    # For Niedersachsen 970, All two digit Numbers of TOP are cut into two lines. Handle here for 10. to 97.
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

class SelectionRules970MultiDigitNumber2(SelectionRules970MultiDigitNumber):
    # For Niedersachsen 970, All tow digit Numbers of TOP from 10. are cut into two lines. Handle this for TOPs 98. until end
    def _getNumberSelection(self, number):
        #e.g. 98. -> 98\n. in NS 970 98.,
        firstTwoDigits = number[:2] # 123. -> 12, 10 -> 10
        lastPartNumber = number[2:] # 98. -> . , 107. -> 7.   (Only part in same chunk)

        # Do same as for 10-97 with different split of number
        return self._getNumberSelectionSplittedNumber(firstTwoDigits, lastPartNumber)
