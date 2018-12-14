# Bundesrat Voting Scraper

This repo collects the votes in the Bundesrat.

The plan:

- `bundesrat` contains a scraper that gets the sessions and their agenda items (TOPs) and puts them in a file called `sessions.json`.
- The actual voting behaviour of the states is [located on the respective states website](https://www.bundesrat.de/DE/plenum/abstimmung/abstimmung-node.html).
- TODO: Scraping the 16 states in their various formats to determine voting behaviour for each of the TOPs.

If you want to work on a scraper, [please check the issues and assign yourself!](https://github.com/okfde/bundesrat-scraper/issues/)

For an example how to scrape the PDFs, [have a look at the Bremen scraper](https://github.com/okfde/bundesrat-scraper/blob/master/bremen/scraper.ipynb).
