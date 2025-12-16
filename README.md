# VaxScope: VAERS Interactive Explorer

**VaxScope** is an interactive analytics dashboard for exploring Vaccine Adverse Event Reporting System (VAERS) data. It provides researchers and the public with tools to search reports, analyze onset intervals, visualize geographic distributions, and detect statistical safety signals using Proportional Reporting Ratio (PRR) algorithms.

## ⚠️ Important Disclaimer
**VAERS is a passive reporting system.** Reports found in this tool do not prove causality. A report of an adverse event to VAERS does not guarantee that a vaccine caused the event. This tool is intended for hypothesis generation and data exploration only.

---

## Project Structure

This overview highlights the core source code, excluding virtual environment and cache files:

```text
VAERS_Interactive/
├── backend/
│   ├── api/                 # Flask Blueprints (Endpoints)
│   │   ├── search.py        # Search logic & filtering
│   │   ├── signals.py       # PRR/ROR Statistical calculations
│   │   ├── trends.py        # Time-series analysis
│   │   ├── onset.py         # Onset interval analysis
│   │   ├── outcomes.py      # Outcome severity KPIs
│   │   └── ...
│   ├── db/                  # Database connection logic (MongoDB)
│   ├── scripts/             # ETL & Data Preprocessing
│   │   ├── load_full.py     # Script to load CSV data into MongoDB
│   │   └── text_normalizer.py
│   ├── services/            # Helper services (Cache, Query Filters)
│   ├── app.py               # Main Flask Application entry point
│   └── requirements.txt     # Python dependencies
├── data/
│   └── processed/           # Cleaned CSV/JSON data files
├── docs/                    # User Manuals and Data Guides
├── frontend/
│   ├── static/              # Assets
│   │   ├── css/app.css      # Styling
│   │   └── js/app.js        # Frontend logic (D3.js charts, filters)
│   └── templates/
│       └── index.html       # Main Dashboard HTML
├── .env                     # Database credentials (Not verified in git)
└── README.md

---

## Prerequisites

Before running this application, ensure you have the following installed:

- **Python 3.11+**
- **MongoDB Access:** You must have connection details for a MongoDB instance (Local or Cloud) containing the VAERS dataset.

---

## Installation & Setup

### 1. Environment Setup
Clone the repository and create a virtual environment to keep dependencies isolated:

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac/Linux
python3 -m venv venv
source venv/bin/activate

---
### 2. Install Dependencies
Install the required packages listed in the backend folder:

```bash
pip install -r backend/requirements.txt

---
### 3. Database Configuration
Create a `.env` file in the root directory and add your MongoDB connection string as `MONGO_URI`. Refer to the User Manual in the `docs/` folder for the required credentials and setup details.

---
## Running the Application

To start the server, run the main Flask application file from the project root:

```bash
python backend/app.py

---
Open your web browser and navigate to: http://127.0.0.1:5002

---
---

## Features & Usage Guide

### 1. Search Tab (Discovery)
**Goal:** Find specific individual reports or geographic hotspots.

**Visuals:** The US Map updates automatically to show report density. The table lists individual cases with symptom text snippets.

**Key Filters:** State, Year, Symptom Term.

### 2. Onset Tab (Temporal Causality)
**Goal:** Analyze the time lag (days) between vaccination and symptom onset.

**Filters:** Use Onset Days Min/Max to focus on immediate vs. delayed reactions.

**Interpretation:** Spikes at Day 0 or 1 often indicate immediate reactogenicity (e.g., pain, fever).

### 3. Outcomes Tab (Severity Analysis)
**Goal:** View the breakdown of serious outcomes (Death, Hospitalization, Disability).

**Context:** Filter by Year and Age Group to see how severity profiles change across populations.

### 4. Trends Tab (Longitudinal)
**Goal:** Spot reporting volume spikes over months or years.

**Visualization:** Interactive bar/line charts showing report counts over time.

**Control:** Use "Last N Months" to zoom into recent data.

### 5. Signals Tab (Statistical Detection)
**Goal:** Detect disproportionate reporting of specific symptoms for specific vaccines.

**Auto-Optimization:** When you switch to this tab, filters for Vaccine Type, Manufacturer, and Symptom Term are automatically hidden. This is intentional to ensure the statistical "background comparison group" remains intact (preventing the "Universe Trap").

**Visualization:**
- **X-Axis:** Frequency (Count).
- **Y-Axis:** PRR (Signal Strength).
- **Red Bubbles:** Statistically significant signals (Lower CI > 1).

---

## Troubleshooting

### ServerSelectionTimeoutError / [WinError 10061]
The application cannot reach the MongoDB server.

**Fix:** Check your internet connection. If using a cloud database (GCP/Atlas), ensure your current IP Address is whitelisted in the cloud provider's firewall settings.

### BSON document too large
You are trying to request too much data at once.

**Fix:** Use the sidebar filters (e.g., Year, State, or limit) to narrow your query.

---

## License
MIT
