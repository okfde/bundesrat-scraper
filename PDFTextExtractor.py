import pdfcutter
import helper

#Helper Class for SenatAndBRTextParser
#Rules for finding position(Selection) of given TOP in a PDF
#These positions are necessary for parsing Senat/BR Text for given TOP
#Rules different for each County, so Counties can derive this class
class DefaultTOPPositionFinder:

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

#Main Task for this class is returning Senats/BR Texts
#Still have to implement _extractSenatBRTexts, _getRightTOPPositionFinder methods
class AbstractSenatsAndBRTextExtractor:
    def __init__(self, cutter):
        self.cutter = cutter


    #Parse out Senat and BR Texts for given current TOP and next TOP Selections
    #Next Selection could be none
    #Position/Format of Texts very different for each County, so implement it there
    #Out: tuple of clean_text of senats/BR Text
    def _extractSenatBRTexts(self, selectionCurrentTOP, selectionNextTOP):
        raise NotImplementedError()


#Class that only holds a DefaultTOPPositionFinder and AbstractSenatsAndBRTextExtractor Subclass instance so that one can hot swap it when format PDF switches
#If Different Find TOP Rules, override _getRightTOPPositionFinder
#If Different Senat/BR Text Rules, override _getRightSenatBRTextExtractor method
class TextExtractorHolder:

    def __init__(self, filename, session):
        self.cutter = pdfcutter.PDFCutter(filename=filename)# Always use same for resource management
        self.session = session
        self.sessionNumber = int(self.session['number']) #Often needed to check if I need special parse rules

    #In: Session dict
    #Out: Lazy Dict of "TOP: {'senat': senatsText, 'bundesrat': BRText}" entries
    def getSenatsAndBRTextsForAllSessionTOPs(self):
        #e.g. "1b", ("1. b)", "2.")
        #Reformat TOPs because easier form for searching in PDFs
        for top, (currentTOPReformated, nextTOPReformated) in helper.extractOriginalAndReformatedTOPNumbers(self.session):
            senats_text, br_text = self._getSenatsAndBRTextsForCurrentTOP(currentTOPReformated, nextTOPReformated)
            yield top, {'senat': senats_text, 'bundesrat': br_text}

    #In: curr/next TOP String in form r"""[0-9]+\.( [a-z]\))?"""
    #next TOP String could be none if current TOP last TOP in PDF
    #Hotswap Rules for finding TOP and extracting Senat/BR Text w.r.t. session number and TOP
    #Out: (SenatText, BRText) Tuple
    def _getSenatsAndBRTextsForCurrentTOP(self, currentTOP, nextTOP):
        currentTOPPositionFinder = self._getRightTOPPositionFinder(currentTOP)
        selectionCurrentTOP = currentTOPPositionFinder.getTOPSelection(currentTOP)

        selectionNextTOP = None
        #next TOP present or current TOP last one in PDF?
        if nextTOP:
            nextTOPPositionFinder = self._getRightTOPPositionFinder(nextTOP)
            selectionNextTOP = nextTOPPositionFinder.getTOPSelection(nextTOP)

        senatBRTextExtractor = self._getRightSenatBRTextExtractor(currentTOP, self.cutter)
        return senatBRTextExtractor._extractSenatBRTexts(selectionCurrentTOP, selectionNextTOP)

    #In: curr/next TOP String in form r"""[0-9]+\.( [a-z]\))?""", number of session (e.g. 970) (inside self)
    #Out: Subclass of DefaultTOPPositionFinder with right rules for this TOP in this session
    #When TOP Format changes in County, override this method
    def _getRightTOPPositionFinder(self, top):
        return DefaultTOPPositionFinder(self.cutter)

    #In: curr/next TOP String in form r"""[0-9]+\.( [a-z]\))?""", number of session (e.g. 970) (inside self)
    #Out: Subclass of AbstractSenatsAndBRTextExtractor with right rules for this TOP in this session
    #Change AbstractSenatsAndBRTextExtractor Subclass depending on self.session_number and TOP
    #Reuse cutter for better resource management
    def _getRightSenatBRTextExtractor(self, top, cutter):
        raise NotImplementedError()
