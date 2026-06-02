# MedSearchPro — Project Explanation
---

## HIGH LEVEL
### For the General Public / Patients

- We built a **free medication reference website** called MedSearchPro
- Anyone can search for a medication by name and instantly see what it does
- Every medication page shows:
  - What the medication is used for
  - Common side effects
  - Important things to be careful about — written in plain patient-friendly language
- The website works on **any device** — phone, tablet, or computer
- No login, no subscription, completely free to use
- Information comes from **official government sources** — the FDA, the National Library of Medicine (RXNorm), and MedlinePlus (NIH)
- Designed so that patients leaving the hospital can look up their medications easily
- Built by two students — Hasti (nursing) and Parshan (physiology) — who saw firsthand how confusing medication instructions can be

---

## MIDDLE LEVEL
### For Academic / Professors

- Built a **single-page web application** using HTML, CSS, and JavaScript — no frameworks required
- **Data source:** 540 medications enriched from three official government APIs: FDA openFDA, RXNorm (NLM), and MedlinePlus Connect (NIH)
- **Search system:** Real-time prefix-first search — results update as the user types, with name matches ranked highest
- **Filtering:** Users can filter by 9 drug categories (Analgesic, Cardiovascular, Antidiabetic, etc.) and browse alphabetically using an A–Z index
- **Detail view:** Each medication opens a modal showing full clinical information — description, trade names, adverse effects, and numbered clinical considerations
- **Medication images:** Sourced from Wikimedia Commons using the public Wikipedia API, displayed in each detail view
- **Accessibility:** Includes screen reader support (ARIA live regions), keyboard navigation, and a Read Aloud feature powered by the browser's Web Speech API
- **Data pipeline:** A Python script (`enrich_medications.py`) queries RXNorm, FDA openFDA, and MedlinePlus Connect in sequence to automatically enrich a structured JSON dataset of 540 medications
- **Considerations field:** Patient-friendly considerations and user guidelines are sourced exclusively from **MedlinePlus Connect** — the NIH's patient-facing drug information service
- **No backend required:** Entire application runs client-side — can be deployed as a static website or opened directly as an HTML file

---

## DETAILED LEVEL
### For Developers / Technical Audience

#### Architecture
- **Single-file SPA** — all HTML, CSS, and JavaScript in one `index.html` file
- Page switching via CSS class toggling (`.page` / `.page.active`) — no routing library
- State managed with plain JavaScript variables: `currentQuery`, `currentCategory`, `currentSort`, `currentLetter`
- Glossary initialized once with `window._glossaryInit` flag to prevent duplicate event listener attachment

#### Search Algorithm
- **Tier 1 (score 4):** Medication name starts with query → shown first
- **Tier 2 (score 3):** Trade name starts with query
- **Tier 3 (score 2):** Medication name contains query
- **Tier 4 (score 1):** Trade name contains query
- **Tier 5 (score 0):** Fallback — matches description, side effects, or considerations
- Results sorted by score descending, then alphabetically within same score
- Filtering by category and A–Z letter applied before text scoring

#### Data Structure
```json
{
  "id": 1,
  "name": "Acetaminophen",
  "tradeNames": ["Tylenol", "Panadol"],
  "category": "Analgesic",
  "description": "Relieves pain and reduces fever.",
  "sideEffects": ["Nausea", "Liver damage in high doses"],

  "rxcui": "161",
  "drugClasses": ["Anilides", "Antipyretics"],

  "fdaIndicationsUsage": "Temporarily relieves minor aches and pains...",
  "fdaWarnings": "Liver warning: This product contains acetaminophen...",
  "fdaDosage": "Adults and children 12 years and over: take 2 caplets...",

  "considerations": [
    "Take acetaminophen exactly as directed on the label.",
    "Do not take more acetaminophen than recommended."
  ],
  "userGuidelines": {
    "storage": "Store at room temperature between 68–77°F...",
    "pregnancy": "Tell your doctor if you are pregnant...",
    "interactions": "Avoid alcohol while taking acetaminophen...",
    "importantNotes": "In case of overdose, contact Poison Control immediately."
  },
  "medlineplusUrl": "https://medlineplus.gov/druginfo/meds/a681004.html",
  "medlineplusTitle": "Acetaminophen",
  "apiSources": {
    "rxnorm": "https://rxnav.nlm.nih.gov/REST/approximateTerm.json?term=Acetaminophen",
    "fda": "https://api.fda.gov/drug/label.json?search=openfda.generic_name:Acetaminophen",
    "medlineplus": "https://medlineplus.gov/druginfo/meds/a681004.html"
  }
}
```

#### Image Strategy
- Local `img/` folder for offline use → `img/acetaminophen.jpg`
- Wikimedia Commons fallback via `Special:FilePath` redirect URL
- `onerror` handler on `<img>` shows "No image available" gracefully

#### Data Pipeline (Python — `enrich_medications.py`)
- **Input:** `medications.json` — 540 seed drug records
- **Step 1 — RXNorm Approximate Match:** Query `/REST/approximateTerm.json?term=...&maxEntries=1&option=0` → resolves canonical `rxcui`
- **Step 2 — RXNorm Drug Class:** Query `/REST/rxclass/class/byRxcui.json?rxcui=...&relaSource=ATC` → extracts `drugClasses` (ATC classification, capped at 3); skipped if Step 1 returns no rxcui
- **Step 3 — FDA openFDA Drug Label:** Query `/drug/label.json?search=openfda.generic_name:"..."&limit=1` → extracts `fdaIndicationsUsage` (indications_and_usage), `fdaWarnings` (warnings / warnings_and_cautions), `fdaDosage` (dosage_and_administration); each field capped at 2,000 characters
- **Step 4 — MedlinePlus Connect ★ PRIMARY:** Query `connect.medlineplus.gov/service` using rxcui (RxNorm OID) when available, otherwise drug name → parses summary HTML to extract `considerations` (up to 10 patient-friendly sentences), `userGuidelines` (storage, pregnancy, interactions, importantNotes), `medlineplusUrl`, `medlineplusTitle`
- **Merge:** All API results merged into a single flat object per drug via `{ **original, rxnorm_fields, fda_fields, medlineplus_fields }`; `considerations` from MedlinePlus takes precedence over original; `fdaIndicationsUsage` falls back to original `description` if FDA returns null
- **Output:** `medications_enriched.json` — array of 540 complete objects
- Rate-limited to **0.4s delay between API calls**; supports `--limit N` for testing and `--resume` to skip already-enriched entries

#### APIs Used
| API | Endpoint | Purpose |
|-----|----------|---------|
| RXNorm | `rxnav.nlm.nih.gov/REST/approximateTerm.json` | Resolve canonical rxcui from drug name |
| RXNorm | `rxnav.nlm.nih.gov/REST/rxclass/class/byRxcui.json` | ATC drug classification |
| FDA openFDA | `api.fda.gov/drug/label.json` | Indications, warnings, dosage |
| MedlinePlus Connect | `connect.medlineplus.gov/service` | Patient-friendly considerations and user guidelines ★ |
| Wikimedia | `commons.wikimedia.org/wiki/Special:FilePath/` | Medication images |

#### Accessibility Features
- Skip navigation link
- ARIA live regions for dynamic search result announcements
- `aria-pressed` on filter chips, `aria-current` on nav links
- Full keyboard navigation (Enter/Space to open, Escape to close modal)
- Read Aloud via `window.speechSynthesis` with start/stop controls
- High contrast media query support

#### Favicon
- Inline SVG data URI — no external file dependency
- Two-leaf V-shape logo in solid green (`#2d8a3e`, `#4caf50`)
