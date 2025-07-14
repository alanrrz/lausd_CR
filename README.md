# LAUSD Community Address Finder

This repo contains a Streamlit application for finding addresses near Los Angeles Unified School District (LAUSD) school sites. The app fetches school and address data from publicly available CSV files.

## Installation

Install Python dependencies using `pip`:

```bash
pip install -r requirements.txt
```

## Running the App

Start the Streamlit application with:

```bash
streamlit run app.py
```

The app will download data from remote URLs when it runs, so an internet connection is required.

After drawing shapes on the map and filtering, the app now displays markers for each
matching address. Addresses that originally contained a hyphenated unit range are
shown in **red**, while single addresses appear in **green**. The exported CSV includes
a new `Hyphenated` column so you can easily identify apartments or condos that were
expanded from a unit range.
