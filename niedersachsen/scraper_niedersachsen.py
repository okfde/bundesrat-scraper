import re

import requests
from lxml import html as etree

import pdfcutter
import helper

INDEX_URL = 'https://niedersachsen.de/startseite/politik_staat/bundesrat/abstimmungsverhalten_niedersachsen_im_bundesrat/abstimmungsverhalten-niedersachsens-im-bundesrat-157696.html'

NUM_RE = re.compile(r'(\d+)\. Sitzung des Bundesrates')
LINK_TEXT_RE = re.compile(r'Abstimmungsverhalten und Beschlüsse .*')
SENAT_TEXT_RE = re.compile(r'^Haltung NI\s*:\s*(.*)')
BR_TEXT_RE = re.compile(r'^Ergebnis BR\s*:\s*(.*)')

def get_pdf_urls():
    #Normal parsing is to hard because HTML is not formatted consistently
    response = requests.get(INDEX_URL)
    root = etree.fromstring(response.content)
    lines = response.text.split('\n')
    meeting_nums = [NUM_RE.search(l).group(1) for l in lines if NUM_RE.search(l)]
    pdf_links = [a.attrib['href'] for a in root.xpath('//a') if a.text != None and LINK_TEXT_RE.search(a.text)]
    for (num, link) in zip(meeting_nums, pdf_links):
        yield int(num), link

#46a -> 46. a)
def reformat_top_num(top_num):
    try:
        num = int(top_num)
        return str(num) + "."
    except ValueError: # Happens when top_num e.g. 48 a or 56 b
        return '{} {}'.format(top_num[:-1]+ ".", top_num[-1] + ")")

def get_reformatted_tops(top_nums):
    return [reformat_top_num(t) for t in top_nums]

def get_beschluesse_text(session, filename):
    cutter = pdfcutter.PDFCutter(filename=filename)
    session_number = int(session['number'])

    top_nums = [t['number'] for t in session['tops'] if t['top_type'] == 'normal'] # 1, 2, 3a, 3b, 4,....
    reformatted_top_nums = get_reformatted_tops(top_nums) #1., 2., 3. a), 3. b), 4.,...

    #e.g. "1b", ("1. b)", "2.")
    for top_num, (current, next_) in zip(top_nums, helper.with_next(reformatted_top_nums)):
        if(')' in current):
            #e.g. 46. a) problem: a) is on new line. There, find the first line below 46 that is starting with b)
            current_top = cutter.filter(auto_regex='^{}$'.format(current.split()[-1].replace(')', '\\)'))) #46. b) -> b\) because of regex brackets
            curr_num = current.split()[0] #46. b) -> 46.
            current_num = cutter.filter(auto_regex='^{}\.'.format(curr_num[:-1]))[0] #Find frst line beginning with 46.
            current_top = current_top.below(current_num)[0] #Find first line starting with b) below TOP 46.
        else:
            current_top = cutter.filter(auto_regex='^{}\.$'.format(current[:-1])) #Escape . in 46. because of regex

        next_top = None
        if next_ is not None: #There is a TOP after this one which we have to take as a lower border
            #Exactly the same as for the current_top
            if(')' in next_):
                next_top = cutter.filter(auto_regex='^{}$'.format(next_.split()[-1].replace(')', '\\)')))
                next_top = next_top.below(current_top)[0] #Don't have to find TOP number line, because we can use current_top as a upper border
            else:
                next_top = cutter.filter(auto_regex='^{}\.$'.format(next_[:-1]))

        senats_text, br_text = getSenatsAndBrTextsForCurrentTOP(cutter, current_top, next_top)
        yield top_num, {'senat': senats_text, 'bundesrat': br_text}


def getSenatsAndBrTextsForCurrentTOP(cutter, current_top, next_top):
    page_heading = 73 #Bottom of heading on each page
    page_footer = 1260 #Upper of footer on each page
    senats = cutter.filter(auto_regex='^Haltung NI')
    senats = senats.below(current_top)
    if next_top:
        senats = senats.above(next_top)

    ergebnis_br = cutter.filter(auto_regex='^Ergebnis').below(current_top) #Sometimes, BR is not part of Ergebnis in XML

    if next_top:
        ergebnis_br = ergebnis_br.above(next_top)

    senats_text = cutter.all().filter(
        doc_top__gte=senats.doc_top - 1 ,
        top__gte=page_heading,
        bottom__lt=page_footer,
    )

    br_text = cutter.all().filter(
        doc_top__gte=ergebnis_br.doc_top - 1 ,#Relative to all pages
        top__gte=page_heading,
        bottom__lt=page_footer,
    )

    if next_top:
        br_text = br_text.above(next_top)
        senats_text = senats_text.above(ergebnis_br)


    #Cut away "Haltung NI:" and "Ergebnis BR:" from text
    senats_text = senats_text.clean_text()
    if senats_text != "":
        senats_text = SENAT_TEXT_RE.search(senats_text).group(1)

    br_text = br_text.clean_text()
    if br_text != "":
        br_text = BR_TEXT_RE.search(br_text).group(1)
    return senats_text, br_text

def get_session(session):
    PDF_URLS = dict(get_pdf_urls())
    try:
        filename = helper.get_session_pdf_filename(session, PDF_URLS)
    except KeyError:
        return
    return dict(get_beschluesse_text(session, filename))
    #return dict()

