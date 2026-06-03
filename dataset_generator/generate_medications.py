"""
enrich_medications.py
=====================
Enriches medications.json with data from four APIs:

  1. RXNorm        – canonical drug identifier (rxcui) and ATC drug class
  2. FDA openFDA   – structured label data (warnings, dosage, indications,
                     boxed warning, patient counseling)
  3. MedlinePlus Connect – patient-friendly considerations / user guidelines
                           (PRIMARY source for `considerations`)
  4. DailyMed (NLM) – full SPL label sections including patient counseling,
                       boxed warning, pregnancy, nursing, drug interactions
                       (PRIMARY source for `patientTeaching`)

Usage
-----
  python enrich_medications.py                  # enriches all medications
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
  DailyMed:     https://dailymed.nlm.nih.gov/dailymed/app-support-web-services.cfm
"""

import json
import re
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

# ── rate-limit ──────────────────────────────────────────────────────────────
DELAY = 0.4   # seconds between API calls


def _get(url: str, timeout: int = 12) -> dict | None:
    """GET a JSON URL; return parsed dict or None on failure."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MedSearchPro/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _strip_html(html: str) -> str | None:
    """Strip HTML tags and clean whitespace."""
    if not html:
        return None
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text if text else None


def _first(value, cap: int = 3000) -> str | None:
    """Pull first element from a list or return the string as-is."""
    if isinstance(value, list) and value:
        return value[0][:cap]
    if isinstance(value, str):
        return value[:cap]
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
    """Return ATC drug class names for a given RxCUI (capped at 3)."""
    url = (
        f"https://rxnav.nlm.nih.gov/REST/rxclass/class/byRxcui.json"
        f"?rxcui={rxcui}&relaSource=ATC"
    )
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
    return classes[:3]


# ══════════════════════════════════════════════════════════════════════════
# 2. FDA openFDA drug label
# ══════════════════════════════════════════════════════════════════════════

def get_fda_label(drug_name: str) -> dict:
    """
    Fetch structured FDA label sections.
    Returns: fdaIndicationsUsage, fdaWarnings, fdaDosage,
             fdaBoxedWarning, fdaPatientCounseling
    """
    result = {
        "fdaIndicationsUsage":   None,
        "fdaWarnings":           None,
        "fdaDosage":             None,
        "fdaBoxedWarning":       None,
        "fdaPatientCounseling":  None,
    }
    encoded = urllib.parse.quote(f'"{drug_name}"')
    url = (
        f"https://api.fda.gov/drug/label.json"
        f"?search=openfda.generic_name:{encoded}&limit=1"
    )
    data = _get(url)
    try:
        label = data["results"][0]
        result["fdaIndicationsUsage"]  = _first(label.get("indications_and_usage"))
        result["fdaWarnings"]          = _first(label.get("warnings") or label.get("warnings_and_cautions"))
        result["fdaDosage"]            = _first(label.get("dosage_and_administration"))
        result["fdaBoxedWarning"]      = _first(label.get("boxed_warning"))
        result["fdaPatientCounseling"] = _first(label.get("patient_counseling_information") or
                                                label.get("information_for_patients"))
    except (TypeError, KeyError, IndexError):
        pass
    return result


# ══════════════════════════════════════════════════════════════════════════
# 3. MedlinePlus Connect  ← PRIMARY source for `considerations`
# ══════════════════════════════════════════════════════════════════════════

def get_medlineplus(drug_name: str, rxcui: str | None = None) -> dict:
    """
    Query MedlinePlus Connect web service.
    Returns: medlineplusUrl, medlineplusTitle, considerations, userGuidelines
    """
    result = {
        "medlineplusUrl":   None,
        "medlineplusTitle": None,
        "considerations":   [],
        "userGuidelines": {
            "storage":        None,
            "pregnancy":      None,
            "interactions":   None,
            "importantNotes": None,
        },
    }

    if rxcui:
        params = urllib.parse.urlencode({
            "mainSearchCriteria.v.cs": "2.16.840.1.113883.6.88",
            "mainSearchCriteria.v.c":  rxcui,
            "mainSearchCriteria.v.dn": drug_name,
            "informationRecipient":    "PROV",
            "knowledgeResponseType":   "application/json",
        })
    else:
        params = urllib.parse.urlencode({
            "mainSearchCriteria.v.dn": drug_name,
            "informationRecipient":    "PROV",
            "knowledgeResponseType":   "application/json",
        })

    data = _get(f"https://connect.medlineplus.gov/service?{params}")

    try:
        entry = data["feed"].get("entry", [{}])[0]
        result["medlineplusTitle"] = entry.get("title", {}).get("_value")
        result["medlineplusUrl"]   = _extract_link(entry)

        summary_html = entry.get("summary", {}).get("_value", "")
        if summary_html:
            considerations, guidelines = _parse_medlineplus_summary(summary_html)
            result["considerations"] = considerations
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
    """Parse MedlinePlus HTML summary into considerations + structured guidelines."""
    text = _strip_html(html) or ""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 20]

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

    return considerations[:10], {k: " ".join(v) if v else None for k, v in guidelines.items()}


# ══════════════════════════════════════════════════════════════════════════
# 4. DailyMed  ← PRIMARY source for `patientTeaching`
# ══════════════════════════════════════════════════════════════════════════

# SPL LOINC section codes
_SPL = {
    "34066-1": "boxedWarning",
    "34076-0": "patientCounseling",       # Information for Patients
    "34080-2": "nursingMothers",
    "42228-7": "pregnancy",
    "34073-7": "drugInteractions",
    "34068-7": "dosageAdministration",
    "34084-4": "adverseReactions",
    "43685-7": "warningsAndPrecautions",
}


def get_dailymed(drug_name: str) -> dict:
    """
    Query DailyMed for full SPL label sections.
    Returns: dailymedSetId, dailymedUrl, patientTeaching (structured),
             dailymedBoxedWarning, dailymedPregnancy, dailymedNursing,
             dailymedDrugInteractions, dailymedAdverseReactions
    """
    result = {
        "dailymedSetId":          None,
        "dailymedUrl":            None,
        "patientTeaching":        None,   # patient counseling / information for patients
        "dailymedBoxedWarning":   None,
        "dailymedPregnancy":      None,
        "dailymedNursing":        None,
        "dailymedDrugInteractions": None,
        "dailymedAdverseReactions": None,
    }

    # ── Step 1: search by drug name to get setid ────────────────────────
    encoded = urllib.parse.quote(drug_name)
    search_url = (
        f"https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json"
        f"?drug_name={encoded}&pagesize=1"
    )
    search_data = _get(search_url)
    try:
        setid = search_data["data"][0]["setid"]
    except (TypeError, KeyError, IndexError):
        return result

    result["dailymedSetId"] = setid
    result["dailymedUrl"]   = f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={setid}"
    time.sleep(DELAY)

    # ── Step 2: fetch all SPL sections ─────────────────────────────────
    sections_url = (
        f"https://dailymed.nlm.nih.gov/dailymed/services/v2/spls/{setid}/sections.json"
    )
    sections_data = _get(sections_url)
    try:
        sections = sections_data["data"]["sections"]
    except (TypeError, KeyError):
        return result

    field_map = {
        "34066-1": "dailymedBoxedWarning",
        "34076-0": "patientTeaching",
        "34080-2": "dailymedNursing",
        "42228-7": "dailymedPregnancy",
        "34073-7": "dailymedDrugInteractions",
        "34084-4": "dailymedAdverseReactions",
        "43685-7": "dailymedWarnings",
    }

    for section in sections:
        code  = section.get("loinc_code", "")
        html  = section.get("value", "")
        field = field_map.get(code)
        if field and html:
            clean = _strip_html(html)
            if clean:
                result[field] = clean[:3000]

    return result


# ══════════════════════════════════════════════════════════════════════════
# Main enrichment loop
# ══════════════════════════════════════════════════════════════════════════

def enrich(medications: list[dict], limit: int | None = None, resume: bool = False) -> list[dict]:
    total = min(limit, len(medications)) if limit else len(medications)
    enriched = []

    for i, med in enumerate(medications[:total]):
        name = med["name"]

        # resume: skip if already fully enriched
        if resume and med.get("dailymedSetId"):
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

        # ── Step 2: FDA openFDA ─────────────────────────────────────────
        fda = get_fda_label(name)
        time.sleep(DELAY)

        # ── Step 3: MedlinePlus ─────────────────────────────────────────
        mlp = get_medlineplus(name, rxcui)
        time.sleep(DELAY)

        # ── Step 4: DailyMed ────────────────────────────────────────────
        dm = get_dailymed(name)
        time.sleep(DELAY)

        # ── Merge ───────────────────────────────────────────────────────
        enriched_med = {
            **med,

            # RXNorm
            "rxcui":       rxcui,
            "drugClasses": drug_classes if drug_classes else med.get("drugClasses", []),

            # FDA openFDA
            "fdaIndicationsUsage":  fda["fdaIndicationsUsage"] or med.get("description"),
            "fdaWarnings":          fda["fdaWarnings"],
            "fdaDosage":            fda["fdaDosage"],
            "fdaBoxedWarning":      fda["fdaBoxedWarning"],
            "fdaPatientCounseling": fda["fdaPatientCounseling"],

            # MedlinePlus ← PRIMARY for considerations
            "considerations":   mlp["considerations"] if mlp["considerations"] else med.get("considerations", []),
            "userGuidelines":   mlp["userGuidelines"],
            "medlineplusUrl":   mlp["medlineplusUrl"],
            "medlineplusTitle": mlp["medlineplusTitle"],

            # DailyMed ← PRIMARY for patientTeaching
            "patientTeaching":          dm["patientTeaching"],
            "dailymedBoxedWarning":      dm["dailymedBoxedWarning"],
            "dailymedPregnancy":         dm["dailymedPregnancy"],
            "dailymedNursing":           dm["dailymedNursing"],
            "dailymedDrugInteractions":  dm["dailymedDrugInteractions"],
            "dailymedAdverseReactions":  dm["dailymedAdverseReactions"],
            "dailymedSetId":             dm["dailymedSetId"],
            "dailymedUrl":               dm["dailymedUrl"],

            # Source tracking
            "apiSources": {
                "rxnorm":      f"https://rxnav.nlm.nih.gov/REST/approximateTerm.json?term={urllib.parse.quote(name)}",
                "fda":         f"https://api.fda.gov/drug/label.json?search=openfda.generic_name:{urllib.parse.quote(name)}",
                "medlineplus": mlp["medlineplusUrl"] or f"https://medlineplus.gov/druginfo/meds/{name.lower().replace(' ', '_')}.html",
                "dailymed":    dm["dailymedUrl"] or f"https://dailymed.nlm.nih.gov/dailymed/search.cfm?query={urllib.parse.quote(name)}",
            },
        }

        enriched.append(enriched_med)
        print(f"    rxcui={rxcui}  dailymed={'✓' if dm['dailymedSetId'] else '✗'}  mlp={'✓' if mlp['medlineplusUrl'] else '✗'}")

    # preserve un-processed records when using --limit
    if limit and limit < len(medications):
        enriched.extend(medications[limit:])

    return enriched


# ══════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Enrich medications.json with RXNorm, FDA openFDA, MedlinePlus, and DailyMed data"
    )
    parser.add_argument("--limit",  type=int, default=None, help="Only process first N drugs (for testing)")
    parser.add_argument("--resume", action="store_true",    help="Skip already-enriched entries (checks dailymedSetId)")
    args = parser.parse_args()

    print(f"Loading {INPUT_FILE} …")
    with open(INPUT_FILE) as f:
        medications = json.load(f)

    print(f"Enriching {args.limit or len(medications)} medications …")
    print("APIs: RXNorm → FDA openFDA → MedlinePlus Connect → DailyMed\n")

    enriched = enrich(medications, limit=args.limit, resume=args.resume)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(enriched, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Saved {len(enriched)} records → {OUTPUT_FILE}")
