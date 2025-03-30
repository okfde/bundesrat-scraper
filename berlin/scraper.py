#!/usr/bin/env python
# coding: utf-8

# In[1]:




# In[2]:


import json
import os


# In[3]:


import scraper_berlin


# In[4]:


USE_CACHE = True


# In[5]:


if USE_CACHE:
    os.makedirs('./_cache', exist_ok=True)


# In[6]:


with open('../bundesrat/sessions.json') as f:
    sessions = json.load(f)
len(sessions)


# In[7]:


# Create a file to store session URLs for future use
URLS_FILENAME = 'session_urls.json'
if os.path.exists(URLS_FILENAME):
    with open(URLS_FILENAME) as f:
        try:
            session_urls = json.load(f)
            print(f"Loaded {len(session_urls)} session URLs from cache")
        except json.JSONDecodeError:
            print("Error loading session URLs from cache, will fetch new URLs")
            session_urls = {}
else:
    print("No cached session URLs found, will fetch new URLs")
    session_urls = {}

# If we don't have any URLs or the cache is empty, fetch them
if not session_urls:
    print("Fetching session URLs...")
    session_urls = dict(scraper_berlin.MainExtractorMethod(scraper_berlin.TextExtractorHolder)._get_pdf_urls())
    print(f"Found {len(session_urls)} session URLs")
    
    # Save URLs to file for future use
    with open(URLS_FILENAME, 'w') as f:
        # Convert keys to strings for JSON serialization
        serializable_urls = {str(k): v for k, v in session_urls.items()}
        json.dump(serializable_urls, f)
        print(f"Saved {len(serializable_urls)} session URLs to {URLS_FILENAME}")


FILENAME = 'session_tops.json'
if os.path.exists(FILENAME):
    with open(FILENAME) as f:
        session_tops = json.load(f)
else:
    session_tops = {}


# In[8]:


for session in sessions:
    num = session['number']
    if str(num) in session_tops:
        continue
    print('\nLoading tops of: %s' % num)

    result = scraper_berlin.MainExtractorMethod(scraper_berlin.TextExtractorHolder).get_session(session)
    if result is None:
        continue
    session_tops[str(num)] = result
    with open(FILENAME, 'w') as f:
        json.dump(session_tops, f)

print('Total sessions:', len(session_tops))


# In[ ]:
