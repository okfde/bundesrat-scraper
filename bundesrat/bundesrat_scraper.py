#!/usr/bin/env python
# coding: utf-8

# In[1]:



# In[2]:


import json
import os


# In[3]:


import bundesrat


# In[4]:


USE_CACHE = True


# In[5]:


if USE_CACHE:
    os.makedirs('./_cache', exist_ok=True)


# In[6]:


sessions = []
if os.path.exists('sessions.json'):
    with open('sessions.json') as f:
        sessions = json.load(f)


# In[7]:


if not sessions:
    sessions = (
        #list(bundesrat.get_sessions_this_year(cache=USE_CACHE)) + #By now, archive also includes the sessions of the current year
        list(bundesrat.get_sessions_archive(cache=USE_CACHE))
    )
    with open('sessions.json', 'w') as f:
        json.dump(sessions, f)


# In[8]:


for session in sessions:
    if 'tops' in session:
        continue
    print('\nLoading tops of: %s' % session['number'])

    session['tops'] = list(bundesrat.get_session_tops(session['number']))
    with open('sessions.json', 'w') as f:
        json.dump(sessions, f)


# In[ ]:




