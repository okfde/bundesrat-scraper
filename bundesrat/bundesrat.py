from collections import defaultdict
from datetime import datetime

import os
import re
from urllib.parse import urlsplit, urlunsplit, parse_qs, urlencode

import requests
from lxml import html as etree

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.110 Safari/537.36'
BASE_HOST = 'www.bundesrat.de'
BASE_URL = 'https://www.bundesrat.de/'
START_PATH = 'DE/plenum/to-plenum/to-plenum-node.html'
TO_URL = 'https://www.bundesrat.de/SharedDocs/TO/{num}/to-node.html'
TOP_URL = 'https://www.bundesrat.de/SharedDocs/TO/{num}/tops/{top}.html?view=render[StandardBody]'

SESSION_NUM_RE = re.compile(r'(\d+)\. Plenarsitzung')
DATE_RE = re.compile(r'(\d{2}\.\d{2}\.\d{4})')
TIME_RE = re.compile(r'(\d{2}:\d{2}) Uhr')
TOP_NUMBER_RE = re.compile(r'TOP (\d+[a-z]?)')
TOP_SIMPLE_NUMBER_RE = re.compile(r'TOP ([a-z]?)')
# BR 3/18(B)  Beschlussdrucksache  (PDF, 112KB)
DOC_TITLE = re.compile(r'(?:(?P<doc_id>[A-Z]{2,}.*)\s{2})?(?P<doc_kind>.*)\s{2}\((?P<doc_filetype>[A-Z]{3,}),?\s+(?P<doc_filesize>\d+[KMGT]B)\)')

START_URL_ARCHIVE = "DE/service/archiv/to-archiv/to-archiv-node.html"
SESSION_NUM_RE_ARCHIVE = re.compile(r'.* \| (\d+)\. .*')
DATE_RE_ARCHIVE = re.compile(r'(\d{2}\.\d{2}\.\d{4})')

STATES = [
    'Schleswig-Holstein',
    'Hamburg',
    'Mecklenburg-Vorpommern',
    'Niedersachsen',
    'Bremen',
    'Berlin',
    'Brandenburg',
    'Sachsen',
    'Sachsen-Anhalt',
    'Thüringen',
    'Hessen',
    'Nordrhein-Westfalen',
    'Rheinland-Pfalz',
    'Saarland',
    'Baden-Württemberg',
    'Bayern'
]

JSESSIONID_PATH = ';jsessionid='
FILESIZE_PREFIX = {
    'K': 1024 ** 1,
    'M': 1024 ** 2,
    'G': 1024 ** 3,
}


def get(url, cache=True):
    if cache:
        filename = url.split('bundesrat.de/')[1].split('?')[0]
        filename = filename.replace('/', '_')
        filename = os.path.join('./_cache', filename)
        if os.path.exists(filename):
            with open(filename) as f:
                return f.read()
    text = requests.get(url, headers={'User-Agent': UA}).text
    if cache:
        with open(filename, 'w') as f:
            f.write(text)
    return text


def get_sessions_this_year(cache=True):
    root = etree.fromstring(get(BASE_URL + START_PATH, cache=cache))
    for table in root.xpath('.//table'):
        for row in table.xpath('.//tr'):
            cols = row.xpath('./td')
            if len(cols) != 2:
                # Wrong table
                break
            path = cols[0].xpath('.//a')[0].attrib['href']
            path = path.split(';jsessionid=')[0]
            # path is relative to base url
            url = BASE_URL + path
            title = cols[0].text_content()
            session_num = SESSION_NUM_RE.search(title)
            if session_num is None:
                continue
            num = int(session_num.group(1))
            date_time = cols[1].text_content()
            date = DATE_RE.search(date_time).group(1)
            time = TIME_RE.search(date_time).group(1)
            timestamp = datetime.strptime('{} {}'.format(date, time), '%d.%m.%Y %H:%M')
            yield {
                'number': num,
                'timestamp': timestamp.isoformat(),
                'url': url,
            }


def get_sessions_archive(cache=True):
    root = etree.fromstring(get(BASE_URL + START_URL_ARCHIVE, cache=cache))
    for table in root.xpath('.//ul[@class="link-list"]'):
        for row in table.xpath('.//li'):
            path = row.xpath('.//a')[0].attrib['href']
            path = path.split(';jsessionid=')[0]
            # path is relative to base url
            url = BASE_URL + path
            title = row.text_content()
            session_num = SESSION_NUM_RE_ARCHIVE.search(title)
            if session_num is None:
                continue
            num = int(session_num.group(1))
            # In archive, date and time are visible only on the detailed page of a meeting
            details = etree.fromstring(get(BASE_URL + path))
            # they used a different website layout for this meeting
            if num == 955:
                tableD = details.xpath('//*[@id="super-content"]/main/div[1]/article/div/div[2]/div/p[1]')
                TIME_RE_ARCHIVE = re.compile(r'(\d{2}:\d{2})')
            else:
                # Updated XPath for the date and time information
                # Try different possible XPath patterns based on website structure changes
                tableD = details.xpath('//h1[contains(@class, "no-border")]/em')
                if not tableD:
                    tableD = details.xpath('//h1/em')
                if not tableD:
                    tableD = details.xpath('//*[contains(text(), "Beginn:")]')
                if not tableD:
                    # If we still can't find it, try a more generic approach
                    tableD = details.xpath('//*[contains(text(), "Sitzung des Bundesrates")]')
                
                # they used only one digit for 9 o'clock
                TIME_RE_ARCHIVE = re.compile(r'Beginn: (\d{2}:\d{2}|\d{1}:\d{2})')

            # Check if tableD is not empty before accessing its elements
            if not tableD:
                print(f"Warning: Could not find date/time information for session {num}")
                # Use a default date and time if we can't find the actual information
                date = "01.01.2000"  # Default date
                time = "00:00"       # Default time
            else:
                date_time = str(etree.tostring(tableD[0], pretty_print=True))
                date_match = DATE_RE_ARCHIVE.search(date_time)
                time_match = TIME_RE_ARCHIVE.search(date_time)
                
                if date_match:
                    date = date_match.group(1)
                else:
                    print(f"Warning: Could not find date for session {num}")
                    date = "01.01.2000"  # Default date
                
                if time_match:
                    time = time_match.group(1)
                else:
                    print(f"Warning: Could not find time for session {num}")
                    time = "00:00"  # Default time
            
            timestamp = datetime.strptime('{} {}'.format(date, time), '%d.%m.%Y %H:%M')
            yield {
                'number': num,
                'timestamp': timestamp.isoformat(),
                'url': url
            }


def fix_url(url):
    result = urlsplit(url)
    parts = list(result)
    if result.scheme == '':
        parts[0] = 'https'
    if result.netloc == '':
        parts[1] = BASE_HOST
    if JSESSIONID_PATH in result.path:
        # Remove session id
        parts[2] = result.path.split(JSESSIONID_PATH)[0]

    if parts[1] == BASE_HOST:
        # Remove useless 'nn' query param
        qs = parse_qs(result.query)
        qs.pop('nn', None)
        parts[3] = urlencode(qs, doseq=True)
    return urlunsplit(parts)


def text_extract(elements):
    return '\n'.join(e.text_content() for e in elements).strip()


def press_release(elements):
    data = {}
    for el in elements:
        if el.tag == 'ul':
            data['links'] = list(link_list_extract(el))
        else:
            data.update(link_extract(el))
    return data


def extract_links(element, transform=None):
    a_els = element.xpath('.//a')
    for a in a_els:
        data = {
            'title': a.text_content(),
            'url': fix_url(a.attrib['href'])
        }
        if transform:
            data = transform(data)
        yield data


def link_list_extract(elements, transform=None):
    for el in elements:
        yield from extract_links(el, transform=transform)


def link_extract(elements):
    return list(link_list_extract(elements))


def document_link_transform(data):
    title = data['title']
    match = DOC_TITLE.search(title)
    if match is not None:
        data.update(match.groupdict())
        if data.get('doc_filesize'):
            factor = FILESIZE_PREFIX[data['doc_filesize'][-2]]
            filesize = int(data['doc_filesize'][:-2])
            data['doc_filesize_bytes'] = filesize * factor
    return data


def document_links(elements):
    return list(link_list_extract(elements, transform=document_link_transform))


def url_extract(element):
    return [x['url'] for x in link_extract(element)]


def get_states(text):
    for state in STATES:
        if state in text:
            yield state


def states_involved(els):
    text = text_extract(els)
    return {
        'text': text,
        'states': list(get_states(text))
    }


def get_committees(els):
    committees = []
    for el in els:
        for abbr in el.xpath('./abbr'):
            text = abbr.text_content()
            if text == 'fdf':
                if not committees:
                    committees.append({
                        'abbreviation': el.text_content().split()[0],
                        'name': None,
                        'leading': False
                    })
                committees[-1]['leading'] = True
                continue
            committees.append({
                'name': abbr.attrib['title'],
                'abbreviation': text,
                'leading': False
            })
    return committees


def related_tops(els):
    for el in els:
        if el.tag != 'ul':
            continue
        links = link_list_extract(el)
        return [l['title'].replace('TOP ', '') for l in links]


def get_party(speech):
    '''
    It's possible that a person doesn't have a party
    '''
    partyTag = speech.xpath('.//p[not(@class)]')
    if len(partyTag) == 0:
        return None
    else:
        return speech.xpath('.//p[not(@class)]')[0].text_content()


def speech_parser(elements):
    element = elements[0]
    for speech in element.xpath('.//div[@class="rack-teaser"]'):
        data = {
            'name': speech.xpath('.//h3')[0].text_content(),
            'party': get_party(speech),
            'url': fix_url(speech.xpath('.//a')[0].attrib['href'])
        }
        try:
            data['state'] = speech.xpath('.//p[@class="bundesland"]')[0].text_content()
        except IndexError:
            pass
        try:
            data['ministry'] = speech.xpath('.//p[@class="ressort"]')[0].text_content()
        except IndexError:
            pass

        image = speech.xpath('.//img')
        if image:
            image = image[0]
            data['image_url'] = fix_url(image.attrib['src'])
            data['image_credit'] = image.attrib['title']
        yield data


def speech_parser_list(elements):
    return list(speech_parser(elements))


TOP_HEADINGS = {
    'Beschlusstenor': 'beschlusstenor',
    'BundesratKOMPAKT': 'press',
    'Vorgang in DIP': 'dip',
    'Drucksachen': 'documents',
    'Länderbeteiligung': 'states_involved',
    'Ausschusszuweisung': 'committee',
    'Bemerkungen': 'notes',
    'Gesetzeskategorie': 'law_category',
}

TOP_PARSERS = {
    'notes': text_extract,
    'beschlusstenor': text_extract,
    'press': press_release,
    'dip': url_extract,
    'documents': document_links,
    'states_involved': states_involved,
    'committee': get_committees,
    'related_tops': related_tops,
    'links': document_links,
    'speeches': speech_parser_list,
    'law_category': text_extract,
}


def parse_top(session_number, top_element, top_type='normal'):
    # Try to find the top number with the updated XPath
    top_number_elements = top_element.xpath('.//h2[@class="top-number"]')
    if not top_number_elements:
        # Try alternative XPath patterns
        top_number_elements = top_element.xpath('.//h2[contains(@class, "top-number")]')
    
    if not top_number_elements:
        # If still not found, try a more generic approach
        top_number_elements = top_element.xpath('.//*[contains(text(), "TOP")]')
    
    if not top_number_elements:
        print(f"Warning: Could not find TOP number for session {session_number}")
        # Use a default TOP number if we can't find the actual one
        top_number = "unknown"
    else:
        top_number = top_number_elements[0].text_content()
        
        if top_type == 'normal':
            match = TOP_NUMBER_RE.search(top_number)
            if match:
                top_number = match.group(1)
            else:
                print(f"Warning: Could not parse TOP number '{top_number}' for session {session_number}")
                top_number = "unknown"
        elif top_type == 'simple':
            # Their internal representation of simple top numbers
            match = TOP_SIMPLE_NUMBER_RE.search(top_number)
            if match:
                top_number = '999' + match.group(1)
            else:
                print(f"Warning: Could not parse simple TOP number '{top_number}' for session {session_number}")
                top_number = "999unknown"

    # Try to find the title with the updated XPath
    title_elements = top_element.xpath('.//div[@class="top-header-content-box"]//a')
    if not title_elements:
        # Try alternative XPath patterns
        title_elements = top_element.xpath('.//div[contains(@class, "top-header-content")]//a')
    
    if not title_elements:
        # If still not found, try a more generic approach
        title_elements = top_element.xpath('.//a')
    
    if not title_elements:
        print(f"Warning: Could not find title for TOP {top_number} in session {session_number}")
        title = f"Unknown title for TOP {top_number}"
    else:
        title = title_elements[0].text_content()

    data = {
        'number': top_number,
        'title': title,
        'top_type': top_type,
        'session_number': session_number,
    }
    print(top_number, end=' ')
    
    try:
        root = etree.fromstring(get(TOP_URL.format(num=session_number, top=top_number)))
        top_details = dict(parse_top_detail(root))
        data.update(top_details)
    except Exception as e:
        print(f"\nError processing TOP {top_number} in session {session_number}: {str(e)}")
    
    return data


TOP_SECTIONS = {
    'Beschlüsse im vereinfachten Verfahren': 'simple'
}


def get_session_tops(session_number):
    root = etree.fromstring(get(TO_URL.format(num=session_number)))
    sections = root.xpath('.//div[@class="module type-1 tops"]/div/*')
    top_type = 'normal'
    for section in sections:
        if section.tag == 'ul':
            top_elements = section.xpath('.//div[@class="top-header"]')
            for top_element in top_elements:
                yield parse_top(session_number, top_element, top_type=top_type)
        elif section.tag == 'h2':
            section_heading = section.text_content()
            top_type = TOP_SECTIONS[section_heading]
        else:
            raise Exception('Unexpected section tag {}'.format(section.tag))


def parse_top_detail(root):
    heading_elements = defaultdict(list)
    heading = None
    
    # Updated XPath to find the content elements
    content_elements = root.xpath('.//div[contains(@class, "top-content-full")]/*')
    if not content_elements:
        # Try alternative XPath patterns
        content_elements = root.xpath('.//*[contains(@class, "top-content")]/*')
    
    if not content_elements:
        # If still not found, try a more generic approach
        content_elements = root.xpath('.//*[contains(@class, "content")]/*')
    
    for element in content_elements:
        if element.tag == 'h3':
            title = element.text_content().strip()
            if title in TOP_HEADINGS:
                heading = TOP_HEADINGS[title]
            else:
                # Handle unknown headings
                print(f"Warning: Unknown heading '{title}'")
                heading = None
        elif element.tag == 'div' and 'class' in element.attrib and 'related-tops' in element.attrib['class']:
            heading = 'related_tops'
            heading_elements[heading].append(element)
        elif element.tag == 'div' and 'class' in element.attrib and 'ts-members' in element.attrib['class']:
            heading = 'speeches'
            heading_elements[heading].append(element)
        elif element.tag == 'ul' and 'class' in element.attrib and 'link-list doc-list' in element.attrib['class'] and heading != 'documents':
            heading = 'links'
            heading_elements[heading].append(element)
        elif heading is not None:
            heading_elements[heading].append(element)

    for kind, element_list in heading_elements.items():
        parser = TOP_PARSERS.get(kind)
        if parser is None:
            print('no parser for', kind)
            continue
        yield (kind, parser(element_list))
