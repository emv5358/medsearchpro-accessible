# MedSearchPro — Project Explanation
---

## HIGH LEVEL
### For the General Public / Patients

- We built a **free medication reference website** called MedSearchPro
- Anyone can search for a medication by name and instantly see what it does
- Every medication page shows:
  - What the medication is used for
  - Common side effects
  - Important things to be careful about
- The website works on **any device** — phone, tablet, or computer
- No login, no subscription, completely free to use
- Information comes from **official government sources** (FDA)
- Designed so that patients leaving the hospital can look up their medications easily
- Built by two students — Hasti (nursing) and Parshan (physiology) — who saw firsthand how confusing medication instructions can be

---

## MIDDLE LEVEL
### For Academic / Professors

- Built a **single-page web application** using HTML, CSS, and JavaScript — no frameworks required
- **Data source:** 30 common medications manually curated from the official FDA dataset, with plans to expand to 500+ using automated API queries
- **Search system:** Real-time prefix-first search — results update as the user types, with name matches ranked highest
- **Filtering:** Users can filter by 9 drug categories (Analgesic, Cardiovascular, Antidiabetic, etc.) and browse alphabetically using an A–Z index
- **Detail view:** Each medication opens a modal showing full clinical information — description, trade names, adverse effects, and numbered clinical considerations
- **Medication images:** Sourced from Wikimedia Commons using the public Wikipedia API, displayed in each detail view
- **Accessibility:** Includes screen reader support (ARIA live regions), keyboard navigation, and a Read Aloud feature powered by the browser's Web Speech API
- **Data pipeline:** A Python script queries the OpenFDA Drug Label API and RxNorm API to automatically generate a structured JSON dataset of 500+ medications
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
  "icon": "💊",
  "img": "img/acetaminophen.jpg",
  "description": "Relieves pain and reduces fever.",
  "sideEffects": ["Nausea", "Liver damage in high doses"],
  "considerations": ["Follow recommended dosage.", "Avoid alcohol."]
}
```

#### Image Strategy
- Local `img/` folder for offline use → `img/acetaminophen.jpg`
- Wikimedia Commons fallback via `Special:FilePath` redirect URL
- `onerror` handler on `<img>` shows "No image available" gracefully

#### Data Pipeline (Python)
- **Input:** 500+ seed drug names (hand-curated list)
- **Step 1:** Query OpenFDA `/drug/label.json` → extracts `indications_and_usage`, `adverse_reactions`, `warnings_and_cautions`, `precautions`
- **Step 2:** Query RxNorm `/rxcui` + `/related?tty=BN` → resolves brand names
- **Step 3:** Auto-classify category using keyword matching rules against drug name + description
- **Step 4:** Clean text (strip HTML tags, truncate, split into bullet arrays)
- **Output:** `medications.json` — array of structured medication objects
- Checkpoint save every 50 entries; rate-limited to 0.25s per request

#### APIs Used
| API | Endpoint | Purpose |
|-----|----------|---------|
| OpenFDA | `api.fda.gov/drug/label.json` | Drug label data |
| RxNorm | `rxnav.nlm.nih.gov/REST/rxcui` | Drug normalization |
| RxNorm | `rxnav.nlm.nih.gov/REST/rxcui/{id}/related` | Brand names |
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
