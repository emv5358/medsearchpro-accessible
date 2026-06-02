"""
enrich_medications.py
=====================
Enriches medications.json with data from three APIs:

  1. RXNorm  – canonical drug identifier (rxcui) and drug class
  2. FDA openFDA  – structured label data (warnings, dosage, indications)
  3. MedlinePlus Connect  – patient-friendly considerations / user guidelines
                           (this is the PRIMARY source for `considerations`)

Usage
-----
  python enrich_medications.py                  # enriches all 540 drugs
  python enrich_medications.py --limit 10       # quick test on first 10 drugs
  python enrich_medications.py --resume         # skip already-enriched entries

Output
------
  medications_enriched.json   (same folder as this script)

API references
--------------
  RXNorm:       https://lhncbc.nlm.nih.gov/RxNav/APIs/api-RxNorm.getApproximateMatch.html
  openFDA:      https://open.fda.gov/apis/drug/label/
  MedlinePlus:  https://medlineplus.gov/medlineplus-connect/web-service/
"""

import json
import time
import argparse
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

# ── paths ──────────────────────────────────────────────────────────────────
HERE = Path(__file__).parent
INPUT_FILE  = HERE / "medications.json"
OUTPUT_FILE = HERE / "medications_enriched.json"

# ── rate-limit helpers ──────────────────────────────────────────────────────
DELAY = 0.4   # seconds between API calls (be polite to free public APIs)


def _get(url: str, timeout: int = 10) -> dict | None:
    """GET a JSON URL; return parsed dict or None on failure."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MedSearchPro/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════
# 1. RXNorm
# ══════════════════════════════════════════════════════════════════════════

def get_rxcui(drug_name: str) -> str | None:
    """Return the best-match RxCUI for a drug name."""
    encoded = urllib.parse.quote(drug_name)
    url = (
        f"https://rxnav.nlm.nih.gov/REST/approximateTerm.json"
        f"?term={encoded}&maxEntries=1&option=0"
    )
    data = _get(url)
    try:
        candidates = data["approximateGroup"]["candidate"]
        if candidates:
            return candidates[0]["rxcui"]
    except (TypeError, KeyError, IndexError):
        pass
    return None


def get_rxnorm_drug_class(rxcui: str) -> list[str]:
    """Return ATC/EPC drug class names for a given RxCUI."""
    url = f"https://rxnav.nlm.nih.gov/REST/rxclass/class/byRxcui.json?rxcui={rxcui}&relaSource=ATC"
    data = _get(url)
    classes = []
    try:
        groups = data["rxclassDrugInfoList"]["rxclassDrugInfo"]
        for g in groups:
            name = g["rxclassMinConceptItem"]["className"]
            if name and name not in classes:
                classes.append(name)
    except (TypeError, KeyError):
        pass
    return classes[:3]  # cap at 3


# ══════════════════════════════════════════════════════════════════════════
# 2. FDA openFDA drug label
# ══════════════════════════════════════════════════════════════════════════

def get_fda_label(drug_name: str) -> dict:
    """
    Fetch structured FDA label sections for a drug.
    Returns a dict with keys: fdaDescription, fdaWarnings, fdaDosage, fdaIndicationsUsage
    """
    result = {
        "fdaDescription": None,
        "fdaWarnings": None,
        "fdaDosage": None,
        "fdaIndicationsUsage": None,
    }
    encoded = urllib.parse.quote(f'"{drug_name}"')
    url = (
        f"https://api.fda.gov/drug/label.json"
        f"?search=openfda.generic_name:{encoded}&limit=1"
    )
    data = _get(url)
    try:
        label = data["results"][0]
        result["fdaDescription"]       = _first(label.get("description"))
        result["fdaWarnings"]          = _first(label.get("warnings") or label.get("warnings_and_cautions"))
        result["fdaDosage"]            = _first(label.get("dosage_and_administration"))
        result["fdaIndicationsUsage"]  = _first(label.get("indications_and_usage"))
    except (TypeError, KeyError, IndexError):
        pass
    return result


def _first(value) -> str | None:
    """Pull first element from a list or return the string as-is."""
    if isinstance(value, list) and value:
        return value[0][:2000]   # cap length
    if isinstance(value, str):
        return value[:2000]
    return None


# ══════════════════════════════════════════════════════════════════════════
# 3. MedlinePlus Connect  ← PRIMARY source for `considerations`
# ══════════════════════════════════════════════════════════════════════════

def get_medlineplus(drug_name: str, rxcui: str | None = None) -> dict:
    """
    Query MedlinePlus Connect web service.
    Returns a dict with keys:
      medlineplusUrl        – canonical MedlinePlus page URL
      medlineplusTitle      – article title
      considerations        – list of patient-friendly guideline sentences
      userGuidelines        – structured object {storage, pregnancy, interactions, notes}
    """
    result = {
        "medlineplusUrl": None,
        "medlineplusTitle": None,
        "considerations": [],
        "userGuidelines": {
            "storage": None,
            "pregnancy": None,
            "interactions": None,
            "importantNotes": None,
        },
    }

    # Build query – prefer rxcui for precision, fall back to name
    if rxcui:
        params = urllib.parse.urlencode({
            "mainSearchCriteria.v.cs": "2.16.840.1.113883.6.88",  # RxNorm OID
            "mainSearchCriteria.v.c": rxcui,
            "mainSearchCriteria.v.dn": drug_name,
            "informationRecipient": "PROV",
            "knowledgeResponseType": "application/json",
        })
    else:
        params = urllib.parse.urlencode({
            "mainSearchCriteria.v.dn": drug_name,
            "informationRecipient": "PROV",
            "knowledgeResponseType": "application/json",
        })

    url = f"https://connect.medlineplus.gov/service?{params}"
    data = _get(url)

    try:
        feed = data["feed"]
        entry = feed.get("entry", [{}])[0]

        result["medlineplusTitle"] = entry.get("title", {}).get("_value")
        result["medlineplusUrl"]   = _extract_link(entry)

        # Full summary text → parse into considerations + guidelines
        summary_html = entry.get("summary", {}).get("_value", "")
        if summary_html:
            considerations, guidelines = _parse_medlineplus_summary(summary_html)
            result["considerations"]          = considerations
            result["userGuidelines"].update(guidelines)

    except (TypeError, KeyError, IndexError):
        pass

    return result


def _extract_link(entry: dict) -> str | None:
    links = entry.get("link", [])
    if isinstance(links, list):
        for lnk in links:
            href = lnk.get("href") or lnk.get("url")
            if href:
                return href
    elif isinstance(links, dict):
        return links.get("href") or links.get("url")
    return None


def _parse_medlineplus_summary(html: str) -> tuple[list[str], dict]:
    """
    Strip HTML tags and split the MedlinePlus summary into:
      - considerations: general use/safety sentences (patient guidelines)
      - guidelines dict: storage, pregnancy, interactions, importantNotes
    """
    import re

    # Strip HTML
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Split into sentences
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 20]

    # Keywords for each guideline category
    keyword_map = {
        "storage":        ["store", "storage", "temperature", "refrigerat", "keep in"],
        "pregnancy":      ["pregnan", "breastfeed", "nursing", "fetal", "birth"],
        "interactions":   ["interact", "drug interaction", "alcohol", "other medication"],
        "importantNotes": ["important", "do not", "avoid", "consult your doctor",
                           "contact your", "emergency", "overdose"],
    }

    guidelines = {k: [] for k in keyword_map}
    considerations = []

    for sent in sentences:
        lower = sent.lower()
        matched = False
        for category, kws in keyword_map.items():
            if any(kw in lower for kw in kws):
                guidelines[category].append(sent)
                matched = True
                break
        if not matched:
            considerations.append(sent)

    # Flatten lists to single strings (or None)
    flat_guidelines = {
        k: " ".join(v) if v else None
        for k, v in guidelines.items()
    }

    return considerations[:10], flat_guidelines  # cap considerations at 10


# ══════════════════════════════════════════════════════════════════════════
# Main enrichment loop
# ══════════════════════════════════════════════════════════════════════════

def enrich(medications: list[dict], limit: int | None = None, resume: bool = False) -> list[dict]:
    total = len(medications) if not limit else min(limit, len(medications))
    enriched = []

    for i, med in enumerate(medications[:total]):
        name = med["name"]

        # resume mode: skip if already has medlineplusUrl
        if resume and med.get("medlineplusUrl"):
            enriched.append(med)
            continue

        print(f"[{i+1}/{total}] {name}")

        # ── Step 1: RXNorm ──────────────────────────────────────────────
        rxcui = get_rxcui(name)
        time.sleep(DELAY)

        drug_classes = []
        if rxcui:
            drug_classes = get_rxnorm_drug_class(rxcui)
            time.sleep(DELAY)

        # ── Step 2: FDA label ───────────────────────────────────────────
        fda = get_fda_label(name)
        time.sleep(DELAY)

        # ── Step 3: MedlinePlus (considerations come from here) ─────────
        mlp = get_medlineplus(name, rxcui)
        time.sleep(DELAY)

        # ── Merge into record ───────────────────────────────────────────
        enriched_med = {
            **med,

            # RXNorm
            "rxcui":       rxcui,
            "drugClasses": drug_classes if drug_classes else med.get("drugClasses", []),

            # FDA openFDA
            "fdaIndicationsUsage": fda["fdaIndicationsUsage"] or med.get("description"),
            "fdaWarnings":         fda["fdaWarnings"],
            "fdaDosage":           fda["fdaDosage"],

            # MedlinePlus  ← replaces the raw `considerations` with patient-friendly text
            "considerations":    mlp["considerations"] if mlp["considerations"] else med["considerations"],
            "userGuidelines":    mlp["userGuidelines"],
            "medlineplusUrl":    mlp["medlineplusUrl"],
            "medlineplusTitle":  mlp["medlineplusTitle"],

            # API source tracking
            "apiSources": {
                "rxnorm":       f"https://rxnav.nlm.nih.gov/REST/approximateTerm.json?term={urllib.parse.quote(name)}",
                "fda":          f"https://api.fda.gov/drug/label.json?search=openfda.generic_name:{urllib.parse.quote(name)}",
                "medlineplus":  mlp["medlineplusUrl"] or f"https://medlineplus.gov/druginfo/meds/{name.lower().replace(' ', '_')}.html",
            },
        }

        enriched.append(enriched_med)

    # Append any remaining records (if limit set)
    if limit and limit < len(medications):
        enriched.extend(medications[limit:])

    return enriched


# ══════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enrich medications.json with FDA/RXNorm/MedlinePlus data")
    parser.add_argument("--limit",  type=int, default=None, help="Only process first N drugs (for testing)")
    parser.add_argument("--resume", action="store_true",    help="Skip already-enriched entries")
    args = parser.parse_args()

    print(f"Loading {INPUT_FILE} …")
    with open(INPUT_FILE) as f:
        medications = json.load(f)

    print(f"Enriching {args.limit or len(medications)} medications …\n")
    enriched = enrich(medications, limit=args.limit, resume=args.resume)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(enriched, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Saved {len(enriched)} records → {OUTPUT_FILE}")
