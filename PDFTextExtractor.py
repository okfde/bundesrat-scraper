import pdfcutter
import helper
import selectionVisualizer as dVis

#Helper Class for SenatAndBRTextParser
#Rules for finding position(Selection) of given TOP in a PDF
#These positions are necessary for parsing Senat/BR Text for given TOP
#Rules different for each County, so Counties can derive this class
#Default: Search for first occurance TOP Number (1.) 
#and if TOP has Subpart, then return first Selection containing Subpart (b)) (not stricty) below TOP Number, else return TOP Number Selection
class DefaultTOPPositionFinder:

    #TOPRight = max px where TOP can *start*. Useful if TOP has very broad format (like HE 992 30,31,55 or MV), which would match a lot of (false) things besides TOP. Used mostly with VerticalSenatsAndBRTextExtractor 
    #page_heading = bottom of page header in px (from pdftohtml) . Useful when number format very broad (e.g. TH 986 "1") and there is some number in header that matches TOP Number (e.g. TH 986 the TOP Number "9" matches "986" session number in header
    def __init__(self, cutter, TOPRight = None, page_heading=0):
        if TOPRight is None:
            TOPRight = cutter.all().right

        self.cutter = cutter #Needed everywhere, so store it here
        self.TOPRight = TOPRight
        self.page_heading = page_heading

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
        allSelectionsNumber = self.cutter.filter(auto_regex='^{}'.format(escapedNum)).filter( # Returns all Selections that have Chunks which start with the number
                left__lte = self.TOPRight, #Can't do anything if whole line is one chunk (therefore right__lte bad), but it should at least start before TOPRight
                top__gte=self.page_heading,
        )
        highestSelection = self._getHighestSelection(allSelectionsNumber)
        #dVis.showCutter(highestSelection)
        return highestSelection

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
        allSelectionsSubpartNonStrictBelowNumber = numberUpperBorder.filter(auto_regex=escapedSubpart).filter( #46. b) -> b\) because of regex brackets
                left__gte = self.TOPRight, #Can't do anything if whole line is one chunk (therefore right__lte bad), but it should at least start before TOPRight
                top__gte=self.page_heading,
        )
        #Return highest of these
        #INFO adding number chunk as upperbound can break this when subpart chunk == number chunk
        return self._getHighestSelection(allSelectionsSubpartNonStrictBelowNumber) 

#Sometimes you cant uncouple TOP Number from Subpart (e.g. BA 985 8a). instead of 8. a))
#Or TOPs look minimaly different than usual ("9 a)" instead of "9. a)")
#Then take this class
#In: cutter, formatString for top with only number "{number}" and formatString for TOP with subpart e.g. "{number}{subpart})." which tells where to add number/subpart (not escaped)
#For TOPs without subpart, same behavior as DefaultTOPPositionFinder
class CustomTOPFormatPositionFinder(DefaultTOPPositionFinder):

    #Default Formats like shown in Glossary
    def __init__(self, cutter, TOPRight = None, page_heading=0, formatNumberOnlyTOP="{number}.", formatSubpartTOP="{number}. {subpart})", padTOPNumberToLength=0): #padTOPNumberToLength only needed for BRE 938- , 0 means no padding

        self.formatNumberOnlyTOP = formatNumberOnlyTOP
        self.formatSubpartTOP = formatSubpartTOP
        self.padTOPNumberToLength = padTOPNumberToLength
        super().__init__(cutter, TOPRight, page_heading)

    #Look for number with given formatNumberOnlyTOP String at *beginning* of selections
    #Used e.g. HA 985 "TOP 4"
    def _getNumberSelection(self, number):
        onlyNumber = number[:-1] #46. -> 46
        paddedNumber = onlyNumber.zfill(self.padTOPNumberToLength) #Left pad with 0s, only needed for BRE 938-
        topRightFormat = self.formatNumberOnlyTOP.format(number=paddedNumber)
        return super()._getNumberSelection(topRightFormat)


    #Subpart not always inside same chunk as number, so first get selection s for number, then return selection s2 for first chunk containing subpart that is (non-strict) below s
    #Chunk of TOP := Chunk of Subpart
    #In: formatString has "number" and "subpart" placeholder, search for TOPs with Subpart directly by this given format
    def _getTOPSubpartSelection(self, top):
        number, subpart = top.split() #46. b) -> [46., b)]
        onlyNumber = number[:-1] #46. -> 46
        onlySubpart = subpart[:-1] #b) -> b
        paddedNumber = onlyNumber.zfill(self.padTOPNumberToLength) #Left pad with 0s, only needed for BRE 938-
        topRightFormat = self.formatSubpartTOP.format(number = paddedNumber, subpart = onlySubpart)
        topSelection = self._getPrefixStringSelection(topRightFormat)
        #dVis.showCutter(topSelection)
        return topSelection

    #Returns highest selection that *starts* with string s (Not-Escaped)
    def _getPrefixStringSelection(self, s):
        return super()._getNumberSelection(s) #Not always only number, but still works


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

#If parsing one TOP too hard (e.g.SAAR 992 40), then return Hand copied text
class StaticTextSenatsAndBRTextExtractor(AbstractSenatsAndBRTextExtractor):

    #Take static text as argument
    def __init__(self, cutter, senatsText, brText):
        self.senatsText = senatsText
        self.brText = brText
        super().__init__(cutter)

    #Always return tuple with same, static texts
    def _extractSenatBRTexts(self, selectionCurrentTOP, selectionNextTOP):
        return self.senatsText, self.brText


#Default Text Extractor for Tables where senat/br texts *right* to TOP (not below). Just give it the pixels where the Tables split and you are good to go
class VerticalSenatsAndBRTextExtractor(AbstractSenatsAndBRTextExtractor):

    #Send also column end/starts (Taken from pdftohtml -xml output
    #page_heading = px Bottom of heading on each page
    #page_footer = px Upper of footer on each page
    #offset = Look around x px to each side to catch text 
    def __init__(self, cutter, page_heading, page_footer , senatLeft, brLeft,  senatRight= None, brRight = None, offset=10 ): #Go to complete right in default br text
        #Can't depend on other parameters for default, so do it like this
        if senatRight is None:
            senatRight = brLeft
        if brRight is None:
            brRight = cutter.all().right

        self.page_heading = page_heading
        self.page_footer = page_footer

        self.senatLeft = senatLeft
        self.senatRight = senatRight
        self.brLeft = brLeft
        self.brRight = brRight
        self.offset = offset # Look around x px to each side to catch text
        super().__init__(cutter)

    #Out: tuple of clean_text of senats/BR Text
    def _extractSenatBRTexts(self, selectionCurrentTOP, selectionNextTOP):
        if selectionNextTOP is None:
            selectionNextTOP = selectionCurrentTOP.empty()
        #Need for some reason everywhere small offset, dont know why, but it works
        senats_text = self.cutter.all().filter(
                doc_top__gte = selectionCurrentTOP.doc_top - self.offset, #Also look at row with TOP in it
                doc_top__lt = selectionNextTOP.doc_top - self.offset, # Lower Bound

                top__gte=self.page_heading,
                bottom__lt=self.page_footer,

                left__gte = self.senatLeft - self.offset,
                right__lt = self.senatRight + self.offset,
        )
        br_text = self.cutter.all().filter(
                doc_top__gte = selectionCurrentTOP.doc_top - self.offset, #Also look at row with TOP in it
                doc_top__lt = selectionNextTOP.doc_top - self.offset, # Lower Bound

                top__gte=self.page_heading,
                bottom__lt=self.page_footer,

                left__gte = self.brLeft - self.offset,
                right__lt = self.brRight + self.offset,
        )
#        dVis.showCutter(selectionNextTOP)
#        dVis.showCutter(senats_text)
#        dVis.showCutter(br_text)

        senats_text = senats_text.clean_text()
        if not senats_text.strip():
            print('empty') #TODO
        br_text = br_text.clean_text()
        #print(senats_text)
        #print("1")
        #print(br_text)
        #print("--")
        return senats_text, br_text


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
