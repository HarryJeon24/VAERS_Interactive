# VAERS_Interactive

````md
# VaxScope (VAERS_Interactive)

VaxScope turns the VAERS public CSVs into a queryable MongoDB dataset and exposes a Flask API + lightweight frontend to explore:
- **AE–vaccine signal ranking** (PRR/ROR with confidence intervals)
- **Unified search/filtering** shared across endpoints
- (Planned) onset distributions, serious outcomes, subgroup comparisons, and time trends

> **Important guardrail:** VAERS is a *passive surveillance* system. Outputs are **hypothesis-generating signals**, not incidence rates and not evidence of causality.

---

## Current Status (What’s Done vs Planned)

### ✅ Implemented
Backend
- Flask app bootstrapped and serving API + frontend
- MongoDB connector
- Shared filter builder (`services/filters.py`)
- TTL caching helper (`services/cache.py`)
- `/api/search` endpoint
- `/api/signals` endpoint (PRR/ROR with continuity correction + CIs)
- Subsample maker + loader scripts (load typed data + build indexes)

Frontend
- Single-page UI (`frontend/templates/index.html`) with JS (`frontend/static/js/signal.js`) + CSS (`frontend/static/css/app.css`) for signals exploration

### 🔜 Planned (Teammates can pick these up)
- `/api/onset` + onset histogram pipeline (NUMDAYS derived from `ONSET_DATE - VAX_DATE`)
- `/api/outcomes` serious outcome proportions (DIED/HOSPITAL/L_THREAT/DISABLE/RECOVD)
- `/api/subgroup` stratified summaries (by VAX_MANU, VAX_DOSE_SERIES, AGE_YRS bands, SEX)
- `/api/trends` monthly/seasonal trends (ONSET_DATE/RECVDATE)

---

## Repo Structure (Lean)

```text
VAERS_Interactive/
  backend/
    app.py
    config.py
    requirements.txt
    api/
      search.py
      signals.py
    db/
      mongo.py
    services/
      filters.py
      cache.py
    scripts/
      make_subsample.py
      load_subsample.py
  frontend/
    templates/
      index.html
    static/
      css/app.css
      js/signal.js
  data/
    raw/          # VAERS yearly CSVs (not tracked in git)
    subsample/    # devVAERS*.csv outputs (not tracked in git)
  docs/
    VAERSDataUseGuide_en_March2025.pdf
````

---

## What Preprocessing We Already Do (So You Don’t Need to Reload)

When loading the subsample CSVs into MongoDB, we already:

* Trim whitespace; convert empty strings to `null`
* Parse types:

  * `VAERS_ID`, `YEAR` → integer
  * `AGE_YRS`, `NUMDAYS` → float
  * `VAX_DATE`, `ONSET_DATE`, `RECVDATE`, `RPT_DATE`, `DATEDIED` → datetime
* Upsert in batches to avoid duplicates
* Create indexes on key fields (VAERS_ID, dates, demographics, vaccine fields, symptoms)

We do **not** do NLP cleaning of text narratives or heavy standardization of manufacturer strings. If needed later, we’ll do it on-the-fly in aggregation pipelines or via targeted in-place updates (no full reload).

---

## Requirements

* Python 3.10+ (3.11 is fine)
* MongoDB (local or Atlas)
* Disk space for VAERS CSVs (raw data is large)

---

## Setup Instructions (Teammate Onboarding)

### 1) Clone and create a virtual environment

```bash
git clone <YOUR_REPO_URL>
cd VAERS_Interactive

python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
```

### 2) Install backend dependencies

```bash
pip install -r backend/requirements.txt
```

### 3) Create a `.env` file at the repo root

Create `VAERS_Interactive/.env`:

```env
# Flask
FLASK_ENV=development
FLASK_DEBUG=1

# Mongo
MONGO_URI=mongodb://localhost:27017
MONGO_DB=vaers_interactive

# Optional: dev settings
# DEV_YEARS=2020,2021,2022,2023,2024,2025
```

> If you use MongoDB Atlas, set `MONGO_URI` to the Atlas connection string.

### 4) Prepare VAERS CSV data

Put VAERS raw files into:

```text
data/raw/
  2024VAERSDATA.csv
  2024VAERSVAX.csv
  2024VAERSSYMPTOMS.csv
  ...
```

You can also include:

* `NonDomesticVAERSDATA.csv`, `NonDomesticVAERSVAX.csv`, `NonDomesticVAERSSYMPTOMS.csv`

> The repo should not track these files in git. Keep them local.

---

## Running the Project (Dev)

### Step A) Make a subsample (recommended for development)

This generates:

* `data/subsample/devVAERSDATA.csv`
* `data/subsample/devVAERSVAX.csv`
* `data/subsample/devVAERSSYMPTOMS.csv`

Run:

```bash
python backend/scripts/make_subsample.py
```

If your script accepts args (sample size / years), see the top of the file or modify constants inside.

### Step B) Load the subsample into MongoDB

```bash
python backend/scripts/load_subsample.py
```

This will:

* parse types
* upsert documents
* create indexes

### Step C) Start the Flask server

```bash
python backend/app.py
```

By default, open the app in your browser:

* Frontend: `http://127.0.0.1:5000/`
* API:

  * `http://127.0.0.1:5000/api/search`
  * `http://127.0.0.1:5000/api/signals`

---

## How to Use the UI

* Open `http://127.0.0.1:5000/`
* Use the filter panel (vaccine type/manufacturer, symptom, age/sex, date range, etc.)
* The signals table should populate and allow sorting

If signals show nothing:

* confirm Mongo is running and `MONGO_URI/MONGO_DB` are correct
* confirm you loaded the subsample
* confirm the `vaers_data`, `vaers_vax`, `vaers_symptoms` collections exist

---

## API Overview

### `/api/search`

Purpose:

* Unified filtering and basic exploration. Returns matching events/docs for the UI.

Inputs:

* Filter params (vaccine type/manufacturer, symptom term(s), age, sex, state, date ranges, etc.)

### `/api/signals`

Purpose:

* Compute PRR/ROR (with continuity correction and confidence intervals) for vaccine–symptom pairs under current filters.

Notes:

* Uses the shared filter builder
* Uses caching to reduce repeated heavy aggregations

---

## Development Conventions

### Where to add new features

* Add endpoint in `backend/api/<feature>.py`
* Reuse `services/filters.py` to respect the same filter semantics everywhere
* Keep “math / metrics” as pure functions where possible for testability

### Common gotchas

* Symptom term matching is sensitive to exact strings if using direct equality matches.
* Large aggregations can be slow on full data without careful indexes.
* If you add new derived fields, prefer:

  1. pipeline-time computation first (no DB rewrite)
  2. then targeted in-place backfill if performance becomes an issue

---

## Team Task Board (Pick One)

### Backend Tasks

1. **Onset endpoint** (`/api/onset`)

* Compute `NUMDAYS = ONSET_DATE - VAX_DATE` in pipeline
* Return histogram buckets + summary stats
* Ensure missing dates are handled safely

2. **Outcomes endpoint** (`/api/outcomes`)

* Group by vaccine/manufacturer or demographic strata
* Return numerator/denominator for DIED/HOSPITAL/L_THREAT/DISABLE/RECOVD

3. **Subgroup endpoint** (`/api/subgroup`)

* Stratify by:

  * vaccine manufacturer (`VAX_MANU`)
  * dose series (`VAX_DOSE_SERIES`)
  * age bands and sex
* Return counts + proportions for side-by-side comparisons

4. **Trends endpoint** (`/api/trends`)

* Monthly counts by `ONSET_DATE` (and optionally `RECVDATE`)
* Optional stratification (vaccine type, manufacturer, symptom)

5. **Index management**

* Add a unified `backend/db/indexes.py` that creates exactly the indexes we rely on
* Document which indexes are required for which endpoints

### Frontend Tasks

1. Add nav/tabs for:

* Signals (already done)
* Onset
* Outcomes
* Subgroup
* Trends

2. Add charts:

* histogram for onset
* stacked bars for outcomes
* line chart for trends

3. Add guardrails UX:

* visible disclaimers on every view
* tooltips for PRR/ROR interpretation

---

## Testing (Optional but Recommended)

* Keep unit tests for:

  * filter building correctness
  * PRR/ROR math edge cases (zero counts, continuity correction, CI behavior)

Example usage (if using pytest):

```bash
pytest -q
```

---

## Troubleshooting

### Mongo connection errors

* Verify Mongo is running:

  * local: `mongod`
  * Atlas: IP allowlist + correct URI
* Validate `.env` values

### Very slow signals

* Confirm indexes exist
* Reduce filter scope (use smaller year range)
* Use subsample for dev

### Empty results

* Confirm data loaded into the correct DB name
* Confirm CSV columns exist and were parsed (especially date fields)

---

## License / Data Notes

* VAERS data is public and comes with usage guidance; see `docs/VAERSDataUseGuide_en_March2025.pdf`.
* VaxScope provides analytical tooling, not medical advice.

---

```
```
