import re

import requests
from lxml import html as etree

import pdfcutter
import helper

INDEX_URL = 'https://www.diebevollmaechtigte.bremen.de/service/bundesratsbeschluesse-17466'
PDF_URL = 'https://www.diebevollmaechtigte.bremen.de/sixcms/media.php/13/{number}.%20BR-Sitzung_Kurzbericht.pdf'

LINK_TEXT_RE = re.compile(r'(\d+)\. Sitzung')

def get_pdf_urls():
    response = requests.get(INDEX_URL)
    root = etree.fromstring(response.content)
    names = root.xpath('.//ul/li/a/span')
    for name in names:
        text = name.text_content()
        num = LINK_TEXT_RE.search(text)
        if num is None:
            continue
        num = int(num.group(1))
        yield num, PDF_URL.format(number=num)


#46a -> 046 a
def reformat_top_num_type2(top_num, top_length):
    try:
        num = int(top_num)
        return top_num.zfill(top_length)
    except ValueError: # Happens when top_num e.g. 48 a or 56 b
        return '{} {}'.format(top_num[:-1].zfill(top_length), top_num[-1])

#46a -> 46. a)
def reformat_top_num_type1(top_num):
    try:
        num = int(top_num)
        return str(num) + "."
    except ValueError: # Happens when top_num e.g. 48 a or 56 b
        return '{} {}'.format(top_num[:-1]+ ".", top_num[-1] + ")")

def get_reformatted_tops_type1(top_nums):
    return [reformat_top_num_type1(t) for t in top_nums]

def get_reformatted_tops_type2(top_nums, top_length):
    return [reformat_top_num_type2(t, top_length) for t in top_nums]

def get_beschluesse_text_type1(session, filename):
    cutter = pdfcutter.PDFCutter(filename=filename)
    session_number = int(session['number'])

    top_nums = [t['number'] for t in session['tops'] if t['top_type'] == 'normal'] # 1, 2, 3a, 3b, 4,....
    reformatted_top_nums = get_reformatted_tops_type1(top_nums) #1., 2., 3. a), 3. b), 4.,...

    #e.g. "1b", ("1. b)", "2.")
    for top_num, (current, next_) in zip(top_nums, helper.with_next(reformatted_top_nums)):
        if('a)' in current):
            current_top = cutter.filter(auto_regex='^{}\.$'.format(current.split()[0][:-1])) #46. a) -> 46
        elif(')' in current):
            #e.g. 46. b) problem: 46 isn't part of the TOP anymore. There, find the first line below 46 that is starting with b)
            current_top = cutter.filter(auto_regex='^{}'.format(current.split()[-1].replace(')', '\\)'))) #46. b) -> b\) because of regex brackets
            curr_num = current.split()[0] #46. b) -> 46.
            current_num = cutter.filter(auto_regex='^{}$'.format(curr_num)) #Find line beginning with 46.
            current_top = current_top.below(current_num)[0] #Find first line starting with b) below TOP 46.
        else:
            current_top = cutter.filter(auto_regex='^{}\.$'.format(current[:-1])) #Escape . in 46. because of regex

        next_top = None
        if next_ is not None: #There is a TOP after this one which we have to take as a lower border
            #Exactly the same as for the current_top
            if('a)' in next_):
                next_top = cutter.filter(auto_regex='^{}\.$'.format(next_.split()[0][:-1]))
            elif(')' in next_):
                next_top = cutter.filter(auto_regex='^{}'.format(next_.split()[-1].replace(')', '\\)')))
                next_top = next_top.below(current_top)[0] #Don't have to find TOP number line, because we can use current_top as a upper border
            else:
                next_top = cutter.filter(auto_regex='^{}\.$'.format(next_[:-1]))
        senats_text, br_text = getSenatsAndBrTextsForCurrentTOP(cutter, current_top, next_top)
        yield top_num, {'senat': senats_text, 'bundesrat': br_text}

def get_beschluesse_text_type2(session, filename, top_length):
    cutter = pdfcutter.PDFCutter(filename=filename)
    session_number = int(session['number'])

    top_nums = [t['number'] for t in session['tops'] if t['top_type'] == 'normal']# 1, 2, 3a, 3b, 4,....
    reformatted_top_nums = get_reformatted_tops_type2(top_nums, top_length)# 001, 002, 003 a, 003 b, 004,... or 01, 02, 03 a, 03 b, 04,...

    #e.g. 1, (001, 002)
    for top_num, (current, next_) in zip(top_nums, helper.with_next(reformatted_top_nums)):
        current_top = cutter.filter(auto_regex='^{}$'.format(current))

        next_top = None
        if next_ is not None:
            next_top = cutter.filter(auto_regex='^{}$'.format(next_))
        senats_text, br_text = getSenatsAndBrTextsForCurrentTOP(cutter, current_top, next_top)
        yield top_num, {'senat': senats_text, 'bundesrat': br_text}


def getSenatsAndBrTextsForCurrentTOP(cutter, current_top, next_top):
    column_two = 731 #start of third (and last) column on type 2 docs, don't need anything from this third column, so just look at the stuff left from it
    page_heading = 74 #Heading on each page in e.g. 962 (Ergebnisse der ...). Isn't there for e.g. 961, so had to hardcode it.
    page_number = 1260 #Page number at the bottom of each page in e.g. 962, Isn't there for e.g. 961, so had to hardcode it.
    senats = cutter.filter(auto_regex='^Senats-?') | cutter.filter(auto_regex='^Beschluss$')
    senats = senats.below(current_top)
    if next_top:
        senats = senats.above(next_top)

    ergebnis_br = cutter.filter(auto_regex='^Ergebnis BR$').below(current_top)

    if next_top:
        ergebnis_br = ergebnis_br.above(next_top)

    senats_text = cutter.all().filter(
        doc_top__gte=senats.doc_top - 1 ,
        top__gte=page_heading,
        bottom__lt=page_number,
        right__lt=column_two #TODO No third column for type1 docs
    )

    br_text = cutter.all().filter(
        doc_top__gte=ergebnis_br.doc_top - 9 ,#Relative to all pages, biggest offset in 938.19
        top__gte=page_heading,
        bottom__lt=page_number,
        right__lt=column_two #TODO No third column for type1 docs
    )

    if next_top:
        br_text = br_text.above(next_top)
        senats_text = senats_text.above(ergebnis_br)

    senats_text = senats_text.right_of(senats)
    br_text = br_text.right_of(ergebnis_br)
    return senats_text.clean_text(), br_text.clean_text()

# Type 1: Page titles are of form "Beschlüsse der NUM. Sitzung...", TOPs of form \(NUM.|NUM. a)|b)|c)|...\)
# Type 2: Page titles are of form "Ergebnisse der NUM. Sitzung ...", TOPs of form \(NUM|NUM a|NUM b|...\), but NUM is filled with zeros to length 3 or 2
def get_beschluesse_text(session, filename):
    session_number = int(session['number'])
    if(session_number >= 934 and session_number <= 937):
        return get_beschluesse_text_type1(session, filename)
    elif(session_number == 938):
        return get_beschluesse_text_type2(session, filename, 2)
    else:
        return get_beschluesse_text_type2(session, filename, 3)

def get_session(session):
    PDF_URLS = dict(get_pdf_urls())
    try:
        filename = helper.get_session_pdf_filename(session, PDF_URLS)
    except KeyError:
        return
    return dict(get_beschluesse_text(session, filename))
