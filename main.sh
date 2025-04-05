#!/bin.sh

set -e

VENV="venv"

if [ ! -f $VENV/bin/activate ]; then
    echo "Create venv"
    python -m venv $VENV
fi

source $VENV/bin/activate
echo "Install requirements"
#pip install -r requirements.txt

#echo "Load new Sessions from bundesrat"
#(cd bundesrat && trash sessions.json &&  python bundesrat_scraper.py)


(cd bayern && trash session_urls.json &&  python scraper.py)
(cd berlin && trash session_urls.json &&  python scraper.py)
(cd brandenburg && trash session_urls.json &&  python scraper.py)
(cd bremen && trash session_urls.json &&  python scraper.py)
(cd hamburg && trash session_urls.json &&  python scraper.py)
(cd hessen && trash session_urls.json &&  python scraper.py)
(cd mecklenburg_vorpommern && trash session_urls.json &&  python scraper.py)
(cd niedersachsen && trash session_urls.json &&  python scraper.py)
(cd nordrhein_westfalen && trash session_urls.json &&  python scraper.py)
(cd rheinland_pfalz && trash session_urls.json &&  python scraper.py)
(cd saarland && trash session_urls.json &&  python scraper.py)
(cd sachsen && trash session_urls.json &&  python scraper.py)
(cd sachsen_anhalt && trash session_urls.json &&  python scraper.py)
(cd schleswig_holstein && trash session_urls.json &&  python scraper.py)
(cd thueringen && trash session_urls.json &&  python scraper.py)
