import json
import re

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

PREFIX="der"
INDEX_URL = 'https://www.{pre}bevollmaechtigte.bremen.de/bund/bundesratsbeschluesse-21671'
PDF_URL = 'https://www.{pre}bevollmaechtigte.bremen.de/sixcms/media.php/13/{number}.%20BR-Sitzung_Kurzbericht.pdf'#doesn't work anymore for e.g. Session 986
BASE_URL = 'https://www.{pre}bevollmaechtigte.bremen.de'

LINK_TEXT_RE = re.compile(r'(\d+)\. Sitzung')

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):
    def _get_pdf_urls(self):
        #Bremen switches it URL sometimes from "*die*bevollmaechtigte" to "*der*bevollmaechtige" and vise versa. Check which prefix is used today by checking which website is online
        try:
            requests.get(INDEX_URL.format(pre=PREFIX))
        except Exception:
            PREFIX = "die"

        response = requests.get(INDEX_URL.format(pre=PREFIX))
        root = etree.fromstring(response.content)
        
        # Find all news_liste elements which contain the session links
        news_lists = root.xpath('//ul[@class="news_liste"]')
        
        for news_list in news_lists:
            links = news_list.xpath('.//li/a')
            for link in links:
                text = link.xpath('./span/text()')[0] if link.xpath('./span/text()') else ''
                num = LINK_TEXT_RE.search(text)

                if num is None:
                    continue
                num = int(num.group(1))
                if num == 955: #Special Session, no PDF available
                    continue

                if "https" in link.attrib['href']: #Sometimes, they have relative href (e.g. 972) and sometimes absolute href (e.g. 971)
                    redirectLink = link.attrib['href']
                else:
                    redirectLink = BASE_URL.format(pre=PREFIX) + link.attrib['href']

                redirectResponse = requests.get(redirectLink)
                redirectRoot = etree.fromstring(redirectResponse.content)
                
                # Look for download links with PDF files
                pdf_links = redirectRoot.xpath('//a[@class="download"]')
                
                if pdf_links:
                    for pdf_link in pdf_links:
                        href = pdf_link.attrib['href']
                        # Check if it's a relative or absolute URL
                        if href.startswith('/'):
                            pdfLink = BASE_URL.format(pre=PREFIX) + href
                        elif href.startswith('http'):
                            pdfLink = href
                        else:
                            pdfLink = BASE_URL.format(pre=PREFIX) + '/' + href
                        #print(num)
                        yield num, pdfLink
                        break  # Just use the first PDF link found

#Default Text Extractor for BRE
class SenatsAndBRTextExtractor(PDFTextExtractor.AbstractSenatsAndBRTextExtractor):
    def _extractSenatBRTexts(self, selectionCurrentTOP, selectionNextTOP):
        column_two = 720 #start of third (and last) column on type 2 docs, don't need anything from this third column, so just look at the stuff left from it
        page_heading = 74 #Heading on each page in e.g. 962 (Ergebnisse der ...). Isn't there for e.g. 961, so had to hardcode it.
        page_number = 1260 #Page number at the bottom of each page in e.g. 962, Isn't there for e.g. 961, so had to hardcode it.
        senats = self.cutter.filter(auto_regex='^Senats-?') | self.cutter.filter(auto_regex='^Umlauf-?') | self.cutter.filter(auto_regex='^Beschluss$') #1049 - 55 calls them "Umlaufbeschluss" for some reason
        senats = senats.below(selectionCurrentTOP)
        if selectionNextTOP:
            senats = senats.above(selectionNextTOP)

        ergebnis_br = self.cutter.filter(auto_regex='^Ergebnis\sBR\s*$') | self.cutter.filter(auto_regex='^Ergebnis*$') | self.cutter.filter(auto_regex='^BR*$') #1031 has two lines for Ergebnis BR
        ergebnis_br = ergebnis_br.below(selectionCurrentTOP)

        if selectionNextTOP:
            ergebnis_br = ergebnis_br.above(selectionNextTOP)

        senats_text = self.cutter.all().filter(
            doc_top__gte=senats.doc_top - 1 ,
            top__gte=page_heading,
            bottom__lt=page_number,
            right__lt=column_two #TODO No third column for 934-937 sessions
        )

        br_text = self.cutter.all().filter(
            doc_top__gte=ergebnis_br.doc_top - 9 ,#Relative to all pages, biggest offset in 938.19
            top__gte=page_heading,
            bottom__lt=page_number,
            right__lt=column_two #TODO No third column for 934-937 sessions
        )

        if selectionNextTOP:
            br_text = br_text.above(selectionNextTOP)
            senats_text = senats_text.above(ergebnis_br)

        senats_text = senats_text.right_of(senats)
        br_text = br_text.right_of(ergebnis_br)
        if not senats_text.clean_text():
            print("empty")
        return senats_text.clean_text(), br_text.clean_text()

class TextExtractorHolder(PDFTextExtractor.TextExtractorHolder):

    # Type BRE 934-937: Page titles are of form "Beschlüsse der NUM. Sitzung...", TOPs of form \(NUM.|NUM. a)|b)|c)|...\)
    # Type BRE 938-: Page titles are of form "Ergebnisse der NUM. Sitzung ...", TOPs of form \(NUM|NUM a|NUM b|...\), but NUM is filled with zeros to length 3 or 2
    def _getRightTOPPositionFinder(self, top):
        padTOPNumberToLength = 3 #Default for BRE 939-
        formatSubpartTOP = "{number}\s{subpart}" #Default for BRE 939-
        if 934 <= self.sessionNumber <= 937:
            return PDFTextExtractor.DefaultTOPPositionFinder(self.cutter) #Need splitting again for these TOPs
        elif self.sessionNumber == 938:
            padTOPNumberToLength = 2
        elif self.sessionNumber == 992 and top in ["87. a)", "87. b)"]:
            formatSubpartTOP = "{number}{subpart}" #missing Space for there two subparts only
        elif self.sessionNumber == 1001:
            formatSubpartTOP = "{number}{subpart}" #missing Space for there two subparts only
        return PDFTextExtractor.CustomTOPFormatPositionFinder(self.cutter, formatNumberOnlyTOP = "{number}", formatSubpartTOP=formatSubpartTOP, padTOPNumberToLength = padTOPNumberToLength)

    def _getRightSenatBRTextExtractor(self, top, cutter): 
        return SenatsAndBRTextExtractor(cutter)
