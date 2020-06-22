import pdfcutter
import helper

#get_session is main method for parsing session to Senats/Bundesrats Texts dict
class MainExtractorMethod:

    #In: Can't init TextExtractorHolder before (missing paras in get_beschluesse_text), so have class as input in init
    def __init__(self, textExtractorHolderSubclass):
        self.textExtractorHolderSubclass = textExtractorHolderSubclass #Needed for get_beschluesse_text and no cyclic dependencies

    #In: Session Dict
    #Out: Dict of "TOP: {'senat': senatsText, 'bundesrat': BRText}" entries
    def get_session(self, session):
        PDF_URLS = dict(self._get_pdf_urls())
        try:
            filename = helper.get_session_pdf_filename(session, PDF_URLS)
        except KeyError:
            return
        return self.get_beschluesse_text(session, filename)

    #Out: Dict of {sessionNumberOfBR: PDFWebLink} entries
    #For each County very different, so implement it new each time
    def _get_pdf_urls(self):
        raise NotImplementedError()

    #Out: Dict of "TOP: {'senat': senatsText, 'bundesrat': BRText}" entries
    #Extraction work done in AbstractSenatsAndBRTextExtractor Subclasses
    def get_beschluesse_text(self, session, filename):
        extractor = self.textExtractorHolderSubclass(filename, session)
        return dict(extractor.getSenatsAndBRTextsForAllSessionTOPs())


