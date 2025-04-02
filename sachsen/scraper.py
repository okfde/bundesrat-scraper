#!/usr/bin/env python
# coding: utf-8

import json
import os
import sys
import scraper_sachsen

# Ensure we have the necessary directories
os.makedirs('./_cache', exist_ok=True)

# Load sessions from the bundesrat directory
print("Loading sessions from bundesrat/sessions.json...")
with open('../bundesrat/sessions.json') as f:
    sessions = json.load(f)
print(f"Loaded {len(sessions)} sessions from sessions.json")

# Load or create session_tops.json
FILENAME = 'session_tops.json'
if os.path.exists(FILENAME):
    with open(FILENAME) as f:
        session_tops = json.load(f)
    print(f"Loaded {len(session_tops)} existing session tops from {FILENAME}")
else:
    session_tops = {}
    print(f"No existing session tops found, creating new file: {FILENAME}")

# Process each session
print("\nStarting to process sessions...")
for session in sessions:
    num = session['number']
#    if str(num) in session_tops: TODO
#        print(f"Session {num} already processed, skipping")
#        continue
    if num > 1035:
        continue
    
    print(f'\nProcessing session: {num}')
    result = scraper_sachsen.get_session(session)
    
    if result is None:
        print(f"No data found for session {num}")
        continue
    
    print(f"Successfully processed session {num}")
    session_tops[str(num)] = result
    
    # Save after each successful session to avoid losing progress
    with open(FILENAME, 'w') as f:
        json.dump(session_tops, f)
    print(f"Saved data for session {num}")

print(f'\nProcessing complete. Total sessions processed: {len(session_tops)}')
