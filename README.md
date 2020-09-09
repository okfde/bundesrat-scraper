# Bundesrat Voting Scraper

This repo collects the votes in the Bundesrat. This Scraper is unofficial, the `Bundesrat` has nothing to do with it. There is no warranty that the scraped data is correct or complete.

The plan:

- `bundesrat` contains a scraper that gets the sessions and their agenda items (TOPs) and puts them in a file called `sessions.json`.
- The actual voting behaviour of the states is [located on the respective states website](https://www.bundesrat.de/DE/plenum/abstimmung/abstimmung-node.html). The scrapers put the texts into a `$STATE/sessions_tops.json` file, together with the links to the original documents in `$STATE/sessions_urls.json`
- Each state has its own Scraper in the according folder in form of a Jupyter file.

## Setup 

Everything is tested unter Python 3.6.8, so please install anacando to use this version of python. It is optimized for Arch Linux, but should work with other Linux Distros as well. The `pdftohtml` dependency is required for the `pdfcutter` tool to work

```
  pip install --user jupyter
  yay -S anaconda --noconfirm #Or your package manager
  yay -S poppler --noconfirm #Or your package manager, need pdftohtml program
  source /opt/anaconda/bin/activate root
  conda create -n py368 python=3.6 ipykernel
  sudo conda install -y nb_conda_kernels
  conda activate py368
  sudo conda install -y lxml
  pip install --user pdfcutter requests lxml
  sudo ipython3 kernel install #Otherwise Jupyter can't find kernel
```

## Usage

To scrape the sessions and their agends items, open the bundesrat-scraper with:

```
  source /opt/anaconda/bin/activate py368
  jupyter notebook bundesrat-scraper/bundesrat/bundesrat_scraper.ipynb
```

, and start the code. You want to do this if there was a new bundesrat session you want to scrape. Before this, you might have to delete the `session.json` file and the `_cache` folder.

To scrape the Abstimmungsverhalten of a state, do:

```
  source /opt/anaconda/bin/activate py368
  jupyter notebook bundesrat-scraper/$STATE/scraper.ipynb
```

, and start the code. If the bundesrat `session.json` was extended, the Scraper will look for the Abstimmungsverhalten of the new sessions

## Environment

### Files

- Each state has its own Scraper in the according folder in form of a Jupyter file. The Jupyter file is a wrapper around the actual `scraper_$STATE.py` file. This file extends the `PDFTextExtractor.py` file, which is the code base for the Scrapers. 
- The `Glossary.md` file explains the used terminology used in the code and comments
- The `MainBoilerPlate.py` contains the code base for collecting the links to the documents of the states.
- The `helper.py` file includes some common methods and adaptations of the `pdfcutter` library.
- The `selectionVisualizer.py` File contains a method for doing graphical debugging of the `pdfcutter` without the need of using Jupyter, but your browser of choice (e.g. Firefox). See Tips section for more information on that
- If you want to know more about the files, look into the comments inside the according file.

### Scraping

The scraping of the states behaviours consists of four parts:

1. Collect the URLs to the documents (done by an extension of `MainBoilerPlate.py/MainExtractorMethod`)
2. Determine the position of the TOPs in the documents (done by an extension of `PDFTextExtractor.py/DefaultTOPPositionFinder`). Some common implementations are available in the same file.
3. Scrape the text between TOPs by the according rules (done by an extension of `PDFTextExtractor.py/AbstractSenatsAndBRTextExtractor`). Some common implementations are available in the same file.
4. Put all three classes together (done by an extension of `PDFTextExtractor.py/TextExtractorHolder`), where you can also define different scraping rules for step 2 and 3 according to the current session and TOP.

- If you want to know more about the files or see some example classes, look into the comments inside the according file.



## Tips

### Execute Scraper without Jupyter
If you want to execute the scraper without Jupyter, you can do

```
  jupyter nbconvert --to script scraper.ipynb
```
, remove the following lines from the beginning of the new python file:


```
  get_ipython().run_line_magic('load_ext', 'autoreload')
  get_ipython().run_line_magic('autoreload', '2')
```

and execute the python file (after enabling anaconda).

### Graphical Debug PDFCutter with Jupyter

Assuming you have a `selection` from your `pdfcutter` instance, you can execute the following code to see the selected text parts in a picture:

```
#import pdfcutter
#cutter=pdfcutter.PDFCutter(filename='./_cache/_download_136845')
debugger = cutter.get_debugger()
#selection = cutter.all().filter(...)
debugger.debug(page).draw(17) # Shows picture of the selected text of `selection` on page 17
```

### Graphical Debug PDFCutter without Jupyter

Assuming you have a `selection` from your `pdfcutter` instance, you can execute the following code to see the selected text parts in a picture inside a browser (e.g. Firefox):

```
#import pdfcutter
#cutter=pdfcutter.PDFCutter(filename='./_cache/_download_136845')
import selectionVisualizer as dVis
#selection = cutter.all().filter(...)
dVis.showCutter(selection, pageNumber=17) # Shows picture of the selected text of `selection` on page 17
```

### Get XML output from PDF

If you want to see the direct out that `pdfcutter` is working on (e.g. for seeing which words form a chuck or see coordinates for lines ), use

```
pdftohtml $DOCUMENT.pdf -xml
```

### Debug Output Collection Document Links

If you want to see the PDF links the `MainBoilerPlate` file sends to the `TextExtractorHolder`, use:

```
  print(list(MainExtractorMethod(None)._get_pdf_urls()))
```

### Debug only one session

If you want to debug a scraping error inside one session (say 973), you can add the following to lines to the scraper jupyter file (cell 8):


```
#  if str(num) in session_tops:
#    continue
  if str(num) != "973":
    continue
```

Alternatively, you can remove session 973 from the `session_tops.py` file and rerun the Jupyter file.
