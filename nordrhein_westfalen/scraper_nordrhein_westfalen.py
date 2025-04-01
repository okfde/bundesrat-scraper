import re
import pdb

import requests
from lxml import html as etree

# Import relative Parent Directory for Helper Classes
import os, sys
sys.path.insert(0, os.path.abspath('..')) #Used when call is ` python3 file.py`
sys.path.insert(0, os.path.abspath('.')) #Used when call is ` python3 $COUNTY/file.py`
import PDFTextExtractor
import MainBoilerPlate

INDEX_URL = 'https://mbeim.nrw/nrw-beim-bund/nordrhein-westfalen-im-bundesrat/abstimmverhalten-im-bundesrat'
BASE_URL = 'https://mbeim.nrw/'
NUM_RE = re.compile(r'(\d+)-sitzung')
SESSION_URL_FORMAT_NEW = 'https://mbeim.nrw/{}-sitzung-des-bundesrates-abstimmverhalten-des-landes-nordrhein-westfalen'
SESSION_URL_FORMAT_OLD = 'https://mbeim.nrw/{}-sitzung-des-bundesrates-am-24-november-2023'

class MainExtractorMethod(MainBoilerPlate.MainExtractorMethod):

    #Out: Dict of {sessionNumberOfBR: WebLink} entries
    #Now gets HTML pages for sessions instead of .odt files
    def _get_pdf_urls(self):
        response = requests.get(INDEX_URL)
        root = etree.fromstring(response.content)

        # Get all links that contain session numbers in the text
        session_links = root.xpath('//a[contains(text(), "Sitzung des Bundesrates")]')
        
        for link in session_links:
            # Extract session number from the text
            text = link.text_content()
            match = re.search(r'(\d+)\.\s+Sitzung', text)
            if match:
                num = int(match.group(1))
                
                # Use different URL formats based on session number
                if num == 1038:
                    session_url = SESSION_URL_FORMAT_OLD.format(num)
                else:
                    session_url = SESSION_URL_FORMAT_NEW.format(num)
                    
                yield num, session_url

#Don't have to change scraper.ipynb when derive TextExtractorHolder. But basically re-implement everything for HTML Parsing
#Also have TOPFinder and TextExtractor all in here, didn't want to add new classes for only one HTML County
class TextExtractorHolder(PDFTextExtractor.TextExtractorHolder):

    #Store WebsiteTable Root (HTML) instead of cutter (PDF)
    def __init__(self, filename, session):
        # Check if the filename is a local file (cache) or a URL
        if filename.startswith('http'):
            # It's a URL, fetch content directly
            response = requests.get(filename)
            html = response.content
        else:
            # It's a local file, read it
            with open(filename, 'r', encoding='utf-8') as file:
                html = file.read().replace('\n', '')
        
        websiteRoot = etree.fromstring(html)

        # The session content is now in a different structure
        self.websiteRoot = websiteRoot
        self.session = session
        self.sessionNumber = int(self.session['number'])
        
        # Store all text content for TOP lookup
        self.content_text = self.websiteRoot.xpath('//body')[0].text_content()
        
        # Try to find tables in the HTML
        self.tables = self.websiteRoot.xpath('//table')
        self.table = self.tables[0] if self.tables else None

    #Hotswap Rules for finding TOP and extracting Senat/BR Text w.r.t. session number and TOP
    #Out: (SenatText, BRText) Tuple
    #Called by scraper.ipynb
    def _getSenatsAndBRTextsForCurrentTOP(self, currentTOP, nextTOP):
        # Extract the TOP number and subpart if present
        parts = currentTOP.split('.')
        top_number = parts[0].strip()
        
        # Check if this is a subpart (e.g., "8. a)" or "8a")
        has_subpart = False
        subpart = None
        
        # Handle both formats: "8. a)" and "8a"
        if len(currentTOP.split()) > 1:
            # Format: "8. a)"
            has_subpart = True
            subpart = currentTOP.split()[1].strip()
        elif len(top_number) > 1 and top_number[-1].isalpha():
            # Format: "8a" (no space)
            has_subpart = True
            subpart = top_number[-1] + ")"
            top_number = top_number[:-1]
        
        # For TOP 1, use the table-based approach
        if top_number == "1" and not has_subpart and self.table is not None:
            try:
                top_row = self._findTOPRow(top_number, currentTOP)
                if top_row is not None:
                    return self._extractSenatBRTextsFromRow(top_row)
            except Exception as e:
                # If table approach fails, continue with text-based approach
                pass
        
        # For subparts like "8 a)", "19 a)", "8a", or "19b", use the text-based approach
        if has_subpart:
            # For subparts, directly look for the pattern in the text content
            # This is more reliable for subparts
            top_content = self._findSubpartContent(top_number, subpart, currentTOP)
            if top_content:
                return self._extractSenatBRTextsFromContent(top_content)
        
        # For other TOPs, try the table approach first
        if self.table is not None:
            try:
                top_row = self._findTOPRow(top_number, currentTOP)
                if top_row is not None:
                    return self._extractSenatBRTextsFromRow(top_row)
            except Exception as e:
                # If table approach fails, continue with text-based approach
                pass
        
        # Fallback to general text-based approach
        top_content = self._findTOPContent(top_number, subpart, currentTOP)
        
        if top_content is None:
            return "", ""
            
        return self._extractSenatBRTextsFromContent(top_content)
    
    def _findTOPRow(self, top_number, currentTOP):
        """Find the table row for a given TOP number"""
        if self.table is None:
            return None
            
        # Find all rows in the table
        rows = self.table.xpath('.//tr')
        
        # Skip the header row
        rows = rows[1:] if len(rows) > 0 else []
        
        # Check if this is a subpart TOP (e.g., "8. a)" or "8a")
        is_subpart = len(currentTOP.split()) > 1
        
        for row in rows:
            # Get the first cell (TD) which contains the TOP number
            cells = row.xpath('./td')
            if not cells or len(cells) < 2:
                continue
                
            top_cell = cells[0]
            top_text = top_cell.text_content().strip()
            
            # If this is a main TOP (e.g., "8.")
            if not is_subpart and top_text == top_number + '.':
                return row
                
            # If this is a subpart TOP (e.g., "8. a)" or "8a")
            if is_subpart:
                # Handle empty first cell for subparts (they often have no number)
                if not top_text and currentTOP.endswith('b)'):
                    # Check if previous row was the 'a)' subpart
                    prev_row_index = rows.index(row) - 1
                    if prev_row_index >= 0:
                        prev_row = rows[prev_row_index]
                        prev_cells = prev_row.xpath('./td')
                        if prev_cells and len(prev_cells) >= 2:
                            prev_top_text = prev_cells[0].text_content().strip()
                            if prev_top_text == top_number + '.':
                                # This is likely the 'b)' subpart
                                return row
                
                # Direct match for subparts that have their number in the first cell
                if top_text and currentTOP.replace(' ', '') in top_text.replace(' ', ''):
                    return row
                    
                # For cases like "19 a)" where multiple subparts share the same main number
                if top_text == subpart and top_number in self.content_text:
                    # Check if this is the correct subpart for the TOP number
                    # This is a heuristic and might need refinement
                    return row
        
        return None
    
    def _extractSenatBRTextsFromRow(self, row):
        """Extract Senats and BR texts from a table row"""
        # Get the second cell which contains the text content
        cells = row.xpath('./td')
        if len(cells) < 2:
            return "", ""
            
        content_cell = cells[1]
        content_text = content_cell.text_content()
        
        # Look for italic text elements which represent the Senats text
        italic_elements = content_cell.xpath('.//em | .//i')
        
        br_text = ""
        senats_text = ""
        
        if italic_elements:
            # Extract all italic text - this is all Senats text
            italic_texts = [elem.text_content().strip() for elem in italic_elements]
            # Filter out empty strings to avoid empty separator error
            italic_texts = [text for text in italic_texts if text]
            senats_text = "\n".join(italic_texts)
            
            # Find the position of the first italic text in the content
            if italic_texts:
                first_italic = italic_texts[0]
                first_pos = content_text.find(first_italic)
                if first_pos > 0:
                    # Everything before the first italic text is BR text
                    br_text = content_text[:first_pos].strip()
                else:
                    # If we can't find the first italic text or it's at the beginning,
                    # assume there's no BR text
                    br_text = ""
            else:
                # No valid italic texts found, assume all is BR text
                br_text = content_text.strip()
        else:
            # No italic elements found, assume all text is BR text
            br_text = content_text.strip()
            
        return senats_text, br_text
    
    def _findTOPContent(self, top_number, subpart, full_top):
        """Find content for a TOP using text patterns"""
        # For main TOPs (no subpart)
        if not subpart:
            # Look for patterns like "TOP: 1." or just the TOP number at the beginning of a line
            patterns = [
                f"{top_number}\\.",  # Just the number with dot
                f"TOP\\s*{top_number}\\."  # TOP: number.
            ]
        else:
            # For subparts, look for patterns like "a)" or "a) Text..."
            # Escape special characters in subpart
            safe_subpart = subpart.replace("(", "\\(").replace(")", "\\)")
            patterns = [
                f"{top_number}\\.\\s*{safe_subpart}",  # 8. a)
                f"\\b{safe_subpart}\\b"  # Just a) as a word boundary
            ]
        
        # Try to find the TOP content using the patterns
        for pattern in patterns:
            # Find all matches of the pattern in the content
            matches = re.finditer(pattern, self.content_text)
            for match in matches:
                # Get the position of the match
                start_pos = match.start()
                
                # Extract a chunk of text around the match
                # This is a heuristic approach - we take a reasonable amount of text
                # that should contain the full TOP content
                chunk_start = max(0, start_pos - 20)  # Some context before
                
                # For end position, find the next TOP or end of text
                if nextTOP := self._findNextTOPPosition(start_pos):
                    chunk_end = nextTOP
                else:
                    chunk_end = min(start_pos + 1000, len(self.content_text))  # Reasonable chunk size
                
                chunk = self.content_text[chunk_start:chunk_end]
                
                # For subparts, verify this is the correct subpart
                if subpart:
                    # For subparts like "a)", make sure we're not matching a different subpart
                    # with the same letter in a different context
                    if not re.search(f"\\b{safe_subpart}\\b", chunk[:100]):
                        continue
                    
                    # For cases like "19 a)" where multiple subparts share the same main number,
                    # check if the chunk contains the main number close to the subpart
                    if not re.search(f"{top_number}\\..*?\\b{safe_subpart}\\b", chunk[:200]) and not re.search(f"\\b{safe_subpart}\\b.*?{top_number}\\.", chunk[:200]):
                        # If main number isn't near the subpart, check if this is a standalone subpart
                        # that follows the main TOP (like "19. a)" after "19.")
                        prev_chunk = self.content_text[max(0, chunk_start - 500):chunk_start]
                        if not re.search(f"{top_number}\\.", prev_chunk[-200:]):
                            continue
                
                return chunk
                
        return None
    
    def _findNextTOPPosition(self, current_pos):
        """Find the position of the next TOP after the current position"""
        # Look for patterns that indicate the start of a new TOP
        patterns = [
            r"\d+\.\s+[A-Za-z]",  # Like "10. Gesetz"
            r"\d+\.\s*a\)",       # Like "10. a)"
            r"\s+a\)\s+",         # Like " a) "
            r"TOP\s*\d+",         # Like "TOP 10"
        ]
        
        min_pos = None
        
        for pattern in patterns:
            matches = re.finditer(pattern, self.content_text[current_pos:])
            for match in matches:
                pos = current_pos + match.start()
                if min_pos is None or pos < min_pos:
                    min_pos = pos
                break  # Just take the first match for each pattern
        
        return min_pos
    
    def _findSubpartContent(self, top_number, subpart, full_top):
        """Special method to find subpart content like '8 a)' or '8a'"""
        # Escape special characters in subpart
        safe_subpart = subpart.replace("(", "\\(").replace(")", "\\)")
        
        # Get the subpart letter without the parenthesis
        subpart_letter = subpart[0] if subpart else ""
        
        # For subparts, we need to look for specific patterns
        patterns = [
            f"{top_number}\\.\\s*{safe_subpart}",  # Like "8. a)"
            f"{top_number}\\.\\s*{subpart_letter}\\\\)",  # Like "8. b)"
            f"\\b{safe_subpart}\\s",               # Like "a) "
            f"\\b{subpart_letter}\\\\)\\s",          # Like "b) "
            f"{top_number}{subpart_letter}\\\\)",    # Like "8b)"
            f"{top_number}{subpart_letter}\\b",    # Like "8b"
            f"\\b{subpart_letter}\\\\)\\s",          # Just "b) " as standalone
        ]
        
        # Try each pattern
        for pattern in patterns:
            try:
                matches = list(re.finditer(pattern, self.content_text))
                for match in matches:
                    start_pos = match.start()
                    
                    # Get a chunk of text around the match
                    chunk_start = max(0, start_pos - 50)
                    
                    # Find the end of this TOP section
                    # Look for the next TOP or subpart marker
                    next_pos = None
                    for next_pattern in [
                        r"\d+\.\s+[A-Za-z]",  # Next main TOP
                        r"\d+\.\s*[a-z]\)",   # Next TOP with subpart
                        r"\bc\)\s",           # Next subpart (c)
                        r"NRW:",              # NRW marker
                    ]:
                        next_matches = list(re.finditer(next_pattern, self.content_text[start_pos + len(match.group(0)):]))
                        if next_matches:
                            pos = start_pos + len(match.group(0)) + next_matches[0].start()
                            if next_pos is None or pos < next_pos:
                                next_pos = pos
                    
                    chunk_end = next_pos if next_pos else min(start_pos + 1000, len(self.content_text))
                    chunk = self.content_text[chunk_start:chunk_end]
                    
                    # For debugging
                    #print(f"Found potential match for {top_number} {subpart} with pattern {pattern}")
                    
                    # Verify this is the correct subpart for this TOP number
                    # For subparts like "19 a)", check if the chunk or nearby text contains the TOP number
                    if not re.search(f"{top_number}\\.", chunk) and not re.search(f"{top_number}{subpart_letter}", chunk):
                        # If not found in the chunk, check nearby text
                        nearby_text = self.content_text[max(0, chunk_start - 200):chunk_start]
                        if not re.search(f"{top_number}\\.", nearby_text) and not re.search(f"{top_number}{subpart_letter}", nearby_text):
                            continue
                    
                    return chunk
            except Exception as e:
                print(f"Error with pattern {pattern}: {e}")
                continue
        
        # If we still haven't found the content, try a more aggressive approach for "b)" subparts
        # Sometimes "b)" appears without clear association to its TOP number
        if subpart_letter == "b":
            try:
                # Look for standalone "b)" after an "a)" section
                b_pattern = r"\bb\)\s"
                b_matches = list(re.finditer(b_pattern, self.content_text))
                
                for b_match in b_matches:
                    b_start = b_match.start()
                    
                    # Check if this "b)" is near the TOP number
                    nearby_text = self.content_text[max(0, b_start - 200):b_start]
                    if re.search(f"{top_number}\\.", nearby_text) or re.search(f"{top_number}a", nearby_text):
                        # This "b)" is likely associated with our TOP number
                        
                        # Find the end of this section
                        next_pos = None
                        for next_pattern in [
                            r"\d+\.\s+[A-Za-z]",  # Next main TOP
                            r"\d+\.\s*[a-z]\)",   # Next TOP with subpart
                            r"\bc\)\s",           # Next subpart (c)
                            r"NRW:",              # NRW marker
                        ]:
                            next_matches = list(re.finditer(next_pattern, self.content_text[b_start + b_match.end():]))
                            if next_matches:
                                pos = b_start + b_match.end() + next_matches[0].start()
                                if next_pos is None or pos < next_pos:
                                    next_pos = pos
                        
                        chunk_end = next_pos if next_pos else min(b_start + 1000, len(self.content_text))
                        chunk = self.content_text[max(0, b_start - 50):chunk_end]
                        
                        return chunk
            except Exception as e:
                print(f"Error with fallback approach: {e}")
        
        return None
    
    def _extractSenatBRTextsFromContent(self, content):
        """Extract Senats and BR texts from content text"""
        # First try to find HTML content with italic text
        try:
            # Parse the content as HTML to look for italic elements
            html_fragment = etree.fromstring(f"<div>{content}</div>", etree.HTMLParser())
            
            # Look for italic text elements which represent the Senats text
            italic_elements = html_fragment.xpath('.//em | .//i')
            
            if italic_elements:
                # Extract all italic text - this is all Senats text
                italic_texts = [elem.text_content().strip() for elem in italic_elements]
                # Filter out empty strings to avoid empty separator error
                italic_texts = [text for text in italic_texts if text]
                senats_text = "\n".join(italic_texts)
                
                # Get the full text content
                full_text = html_fragment.text_content()
                
                # Find the position of the first italic text in the content
                if italic_texts:
                    first_italic = italic_texts[0]
                    first_pos = full_text.find(first_italic)
                    if first_pos > 0:
                        # Everything before the first italic text is BR text
                        br_text = full_text[:first_pos].strip()
                    else:
                        # If we can't find the first italic text or it's at the beginning,
                        # assume there's no BR text
                        br_text = ""
                else:
                    # No valid italic texts found, assume all is BR text
                    br_text = full_text.strip()
                
                return senats_text, br_text
        except Exception as e:
            # If HTML parsing fails, continue with the text-based approach
            pass
        
        # Fallback to text-based approach using NRW: marker
        nrw_match = re.search(r'NRW:', content)
        
        if nrw_match:
            # Everything before NRW: is BR text
            br_text = content[:nrw_match.start()].strip()
            
            # Everything after NRW: is Senats text
            senats_text = content[nrw_match.start():].strip()
        else:
            # If no NRW: marker, assume all is BR text
            br_text = content.strip()
            senats_text = ""
            
        if not senats_text.strip():
            print('empty')
        return senats_text, br_text
