import pdfcutter
import helper
import json #For writing PDF Link JSON File
import os #To check if PDF Link JSON File exists

#get_session is main method for parsing session to Senats/Bundesrats Texts dict
class MainExtractorMethod:

    #In: Can't init TextExtractorHolder before (missing paras in get_beschluesse_text), so have class as input in init
    def __init__(self, textExtractorHolderSubclass):
        self.textExtractorHolderSubclass = textExtractorHolderSubclass #Needed for get_beschluesse_text and no cyclic dependencies

    #In: Session Dict
    #Out: Dict of "TOP: {'senat': senatsText, 'bundesrat': BRText}" entries
    def get_session(self, session):
        from_json=True
        URLFILENAME = "session_urls.json"
        PDF_URLS = {}
        
        # First try to load URLs from JSON file if from_json is True
        if from_json and os.path.exists(URLFILENAME):
            try:
                with open(URLFILENAME, 'r') as f:
                    PDF_URLS = json.load(f)
            except json.JSONDecodeError:
                # If JSON file is invalid, fall back to _get_pdf_urls()
                PDF_URLS = dict(self._get_pdf_urls())
        
        # If URL not found in JSON or from_json is False, get URLs from source
        if not PDF_URLS or str(session['number']) not in PDF_URLS:
            PDF_URLS = dict(self._get_pdf_urls())
            
            # Create or update the PDF Link JSON File
            with open(URLFILENAME, 'w') as f:
                json.dump(PDF_URLS, f)

        try:
            filename = helper.get_session_pdf_filename(session, PDF_URLS)
        except KeyError:
            return
        print(filename)
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
