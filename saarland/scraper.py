#!/usr/bin/env python
# coding: utf-8

# In[1]:




# In[2]:


import json
import os


# In[3]:


import scraper_saarland


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

    #Get Warning e.g. 944,948 "Invalid least number of objects reading page offset hints table"
    #But doesn't seem to be a problem problem for extraction at all
    #Need class for later init, don't have all params by now
    result = scraper_saarland.MainExtractorMethod(scraper_saarland.TextExtractorHolder).get_session(session)
    if result is None:
        continue
    session_tops[str(num)] = result
    with open(FILENAME, 'w') as f:
        json.dump(session_tops, f)

print('Total sessions:', len(session_tops))


# In[ ]:




