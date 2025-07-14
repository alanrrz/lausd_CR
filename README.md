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

## Features

- Draw polygons or rectangles on the map to select areas of interest.
- Markers appear for every address inside the selected shapes.
- Hyphenated addresses, often indicating multi-unit buildings, are shown in red.
- A preview table highlights rows parsed from hyphenated input.

