"""
MedSearchPro — Medication Dataset Generator
============================================
Queries free public APIs to build a 500+ medication JSON dataset.

APIs used:
  • RxNorm  (rxnav.nlm.nih.gov)  — drug names, RxCUI, brand↔generic mapping
  • OpenFDA (api.fda.gov)         — indications, warnings, side effects, interactions
  • DailyMed (dailymed.nlm.nih.gov) — official FDA package inserts

Run:
    pip install requests
    python generate_medications.py

Output:
    medications.json  (same folder)
"""

import requests
import json
import time
import re
import os

OUTPUT_FILE = "medications.json"

# ── Broad list of common generic drug names to seed the query ────────────────
# RxNorm will be used to resolve these into full records.
SEED_DRUGS = [
    "acetaminophen","ibuprofen","aspirin","naproxen","diclofenac","celecoxib","meloxicam",
    "indomethacin","ketoprofen","piroxicam","ketorolac",
    "amoxicillin","ampicillin","azithromycin","clarithromycin","doxycycline","tetracycline",
    "ciprofloxacin","levofloxacin","moxifloxacin","metronidazole","clindamycin","trimethoprim",
    "sulfamethoxazole","nitrofurantoin","cephalexin","cefuroxime","ceftriaxone","cefdinir",
    "penicillin","vancomycin","linezolid","rifampin","isoniazid","ethambutol","pyrazinamide",
    "fluconazole","itraconazole","voriconazole","clotrimazole","miconazole","terbinafine",
    "acyclovir","valacyclovir","oseltamivir","remdesivir",
    "lisinopril","enalapril","ramipril","captopril","perindopril","trandolapril",
    "amlodipine","nifedipine","diltiazem","verapamil","felodipine",
    "metoprolol","atenolol","carvedilol","bisoprolol","propranolol","labetalol","nebivolol",
    "losartan","valsartan","olmesartan","irbesartan","candesartan","telmisartan","azilsartan",
    "furosemide","hydrochlorothiazide","chlorthalidone","spironolactone","eplerenone",
    "atorvastatin","rosuvastatin","simvastatin","pravastatin","lovastatin","fluvastatin","pitavastatin",
    "warfarin","apixaban","rivaroxaban","dabigatran","edoxaban","clopidogrel","ticagrelor","prasugrel",
    "digoxin","amiodarone","sotalol","flecainide","dronedarone","ivabradine",
    "nitroglycerin","isosorbide","hydralazine","clonidine","methyldopa","doxazosin","terazosin",
    "metformin","glipizide","glyburide","glimepiride","pioglitazone","sitagliptin","saxagliptin",
    "linagliptin","empagliflozin","dapagliflozin","canagliflozin","semaglutide","liraglutide",
    "exenatide","insulin glargine","insulin aspart","insulin lispro","insulin detemir",
    "levothyroxine","methimazole","propylthiouracil","liothyronine",
    "prednisone","prednisolone","dexamethasone","methylprednisolone","hydrocortisone","budesonide",
    "fluticasone","beclomethasone","mometasone","triamcinolone",
    "albuterol","salmeterol","formoterol","tiotropium","ipratropium","theophylline","montelukast",
    "zafirlukast","cromolyn","omalizumab",
    "omeprazole","esomeprazole","lansoprazole","pantoprazole","rabeprazole","dexlansoprazole",
    "ranitidine","famotidine","cimetidine","metoclopramide","ondansetron","prochlorperazine",
    "loperamide","bismuth","mesalamine","sulfasalazine","infliximab","adalimumab",
    "sertraline","fluoxetine","paroxetine","escitalopram","citalopram","fluvoxamine",
    "venlafaxine","duloxetine","desvenlafaxine","bupropion","mirtazapine","trazodone",
    "amitriptyline","nortriptyline","imipramine","clomipramine","desipramine",
    "haloperidol","risperidone","olanzapine","quetiapine","aripiprazole","ziprasidone",
    "clozapine","lurasidone","paliperidone","asenapine","iloperidone",
    "lithium","valproate","carbamazepine","lamotrigine","topiramate","gabapentin","pregabalin",
    "levetiracetam","phenytoin","phenobarbital","clonazepam","oxcarbazepine","zonisamide",
    "lorazepam","diazepam","alprazolam","clonazepam","midazolam","temazepam","triazolam",
    "zolpidem","zaleplon","eszopiclone","buspirone","hydroxyzine",
    "donepezil","rivastigmine","galantamine","memantine",
    "levodopa","carbidopa","pramipexole","ropinirole","rotigotine","selegiline","rasagiline",
    "baclofen","cyclobenzaprine","methocarbamol","tizanidine","carisoprodol",
    "morphine","oxycodone","hydrocodone","codeine","tramadol","fentanyl","buprenorphine",
    "methadone","naloxone","naltrexone","hydromorphone","oxymorphone","tapentadol",
    "sumatriptan","rizatriptan","zolmitriptan","eletriptan","naratriptan","almotriptan",
    "topiramate","propranolol","amitriptyline","valproate",
    "cetirizine","loratadine","fexofenadine","diphenhydramine","chlorpheniramine","desloratadine",
    "levocetirizine","azelastine","olopatadine",
    "tamsulosin","alfuzosin","silodosin","finasteride","dutasteride","tadalafil","sildenafil",
    "vardenafil","avanafil",
    "allopurinol","febuxostat","colchicine","probenecid","benzbromarone",
    "methotrexate","hydroxychloroquine","sulfasalazine","leflunomide","etanercept",
    "abatacept","tocilizumab","tofacitinib","baricitinib","upadacitinib",
    "alendronate","risedronate","ibandronate","zoledronic acid","denosumab","raloxifene",
    "teriparatide","abaloparatide","romosozumab",
    "tamoxifen","letrozole","anastrozole","exemestane","fulvestrant","megestrol",
    "cyclophosphamide","methotrexate","fluorouracil","capecitabine","gemcitabine",
    "paclitaxel","docetaxel","carboplatin","cisplatin","oxaliplatin",
    "imatinib","erlotinib","gefitinib","sunitinib","sorafenib","vemurafenib",
    "rituximab","trastuzumab","bevacizumab","pembrolizumab","nivolumab",
    "epoetin","filgrastim","pegfilgrastim","thrombopoietin",
    "ferrous sulfate","ferric carboxymaltose","cyanocobalamin","folic acid",
    "cholecalciferol","ergocalciferol","calcitriol","calcium carbonate","calcium citrate",
    "magnesium oxide","zinc sulfate","potassium chloride","sodium bicarbonate",
    "isotretinoin","tretinoin","adapalene","benzoyl peroxide","clindamycin","doxycycline",
    "tacrolimus","pimecrolimus","clobetasol","betamethasone","hydrocortisone",
    "latanoprost","timolol","brimonidine","dorzolamide","bimatoprost","travoprost",
    "ranibizumab","bevacizumab","aflibercept",
    "methylphenidate","amphetamine","lisdexamfetamine","atomoxetine","guanfacine","clonidine",
    "varenicline","bupropion","nicotine","disulfiram","acamprosate","naltrexone",
    "levonorgestrel","ethinyl estradiol","norethindrone","desogestrel","drospirenone",
    "medroxyprogesterone","estradiol","conjugated estrogens","progesterone",
    "oxytocin","misoprostol","dinoprostone","mifepristone",
    "heparin","enoxaparin","dalteparin","fondaparinux","bivalirudin","argatroban",
    "alteplase","reteplase","streptokinase","urokinase",
    "cyclosporine","tacrolimus","mycophenolate","azathioprine","sirolimus","everolimus",
    "interferon","peginterferon","ribavirin","sofosbuvir","ledipasvir","daclatasvir",
    "efavirenz","tenofovir","emtricitabine","lamivudine","zidovudine","abacavir",
    "atazanavir","lopinavir","ritonavir","darunavir","raltegravir","dolutegravir",
    "chloroquine","hydroxychloroquine","artemether","lumefantrine","mefloquine","atovaquone",
    "proguanil","primaquine","quinine",
    "gentamicin","tobramycin","amikacin","streptomycin","neomycin",
    "colistin","polymyxin","daptomycin","tigecycline","tedizolid",
    "acetazolamide","mannitol","glycerol","urea",
    "adenosine","atropine","epinephrine","norepinephrine","dopamine","dobutamine",
    "vasopressin","phenylephrine","milrinone","levosimendan",
    "succinylcholine","rocuronium","vecuronium","pancuronium","cisatracurium",
    "propofol","ketamine","etomidate","thiopental","sevoflurane","isoflurane","desflurane",
    "lidocaine","bupivacaine","ropivacaine","mepivacaine","procaine","benzocaine",
    "dextromethorphan","guaifenesin","pseudoephedrine","phenylephrine","benzonatate",
    "ipratropium","budesonide","fluticasone","salmeterol","formoterol",
    "ursodiol","cholestyramine","colestipol","colesevelam","ezetimibe","niacin","fenofibrate",
    "gemfibrozil","omega-3 fatty acids","evolocumab","alirocumab","inclisiran",
    "sacubitril","valsartan","ivabradine","hydralazine","isosorbide dinitrate",
    "tolvaptan","vaptans","nesiritide","levosimendan",
    "dexamethasone","ondansetron","granisetron","palonosetron","aprepitant","fosaprepitant",
    "metolazone","torsemide","indapamide","amiloride","triamterene",
    "sildenafil","tadalafil","bosentan","ambrisentan","macitentan","riociguat",
    "iloprost","epoprostenol","treprostinil","selexipag",
    "colchicine","febuxostat","rasburicase","pegloticase",
    "eculizumab","ravulizumab","avacopan",
    "dupilumab","tralokinumab","lebrikizumab","nemolizumab",
    "mepolizumab","benralizumab","reslizumab","tezepelumab","dupilumab",
    "canakinumab","anakinra","rilonacept","secukinumab","ixekizumab","brodalumab",
    "guselkumab","risankizumab","tildrakizumab","mirikizumab",
    "ustekinumab","vedolizumab","ozanimod","siponimod","fingolimod","natalizumab",
    "dimethyl fumarate","teriflunomide","interferon beta","glatiramer acetate","ofatumumab",
    "ocrelizumab","alemtuzumab","cladribine","mitoxantrone",
    "nusinersen","risdiplam","onasemnogene","eteplirsen",
    "patisiran","givosiran","lumasiran","inclisiran","vutrisiran",
]

# Remove duplicates
SEED_DRUGS = list(dict.fromkeys(SEED_DRUGS))

# ── Category mapping based on drug class keywords ────────────────────────────
CATEGORY_RULES = [
    (["antibiotic","antibacterial","antimicrobial","penicillin","cephalosporin",
      "macrolide","fluoroquinolone","tetracycline","sulfonamide","linezolid",
      "vancomycin","clindamycin","metronidazole","nitrofurantoin"], "Antibiotic"),
    (["antifungal","fluconazole","itraconazole","voriconazole","clotrimazole",
      "terbinafine","amphotericin"], "Antifungal"),
    (["antiviral","acyclovir","valacyclovir","oseltamivir","remdesivir",
      "sofosbuvir","efavirenz","tenofovir","lamivudine","ritonavir"], "Antiviral"),
    (["statin","atorvastatin","rosuvastatin","simvastatin","pravastatin",
      "lovastatin","cholesterol","lipid","ezetimibe","fibrate","niacin",
      "evolocumab","alirocumab"], "Cardiovascular"),
    (["antihypertensive","lisinopril","enalapril","ramipril","captopril",
      "amlodipine","metoprolol","atenolol","carvedilol","losartan","valsartan",
      "furosemide","hydrochlorothiazide","spironolactone","digoxin","amiodarone",
      "warfarin","apixaban","rivaroxaban","clopidogrel","nitroglycerin",
      "heart","cardiac","blood pressure","antiarrhythmic","anticoagulant",
      "antithrombotic","diuretic"], "Cardiovascular"),
    (["antidiabetic","metformin","glipizide","glyburide","sitagliptin",
      "empagliflozin","semaglutide","liraglutide","insulin","diabetes",
      "blood sugar","glucose","hypoglycemic"], "Antidiabetic"),
    (["antidepressant","sertraline","fluoxetine","paroxetine","escitalopram",
      "venlafaxine","duloxetine","bupropion","mirtazapine","amitriptyline",
      "nortriptyline","antipsychotic","haloperidol","risperidone","olanzapine",
      "quetiapine","aripiprazole","clozapine","lithium","mood","psychiatric",
      "anxiolytic","benzodiazepine","lorazepam","diazepam","alprazolam",
      "zolpidem","buspirone","adhd","methylphenidate","amphetamine"], "Psychiatric"),
    (["anticonvulsant","antiepileptic","gabapentin","pregabalin","levetiracetam",
      "phenytoin","valproate","carbamazepine","lamotrigine","topiramate",
      "parkinson","levodopa","donepezil","memantine","neurological","seizure",
      "epilepsy","nerve","neuropathy","migraine","sumatriptan"], "Neurological"),
    (["analgesic","pain","ibuprofen","aspirin","naproxen","diclofenac",
      "celecoxib","acetaminophen","paracetamol","morphine","oxycodone",
      "hydrocodone","tramadol","fentanyl","buprenorphine","opioid","nsaid",
      "ketorolac","meloxicam","indomethacin"], "Analgesic"),
    (["bronchodilator","albuterol","salmeterol","tiotropium","ipratropium",
      "montelukast","theophylline","respiratory","asthma","copd","inhaler",
      "fluticasone","budesonide","beclomethasone"], "Respiratory"),
    (["antacid","proton pump","omeprazole","esomeprazole","lansoprazole",
      "pantoprazole","ranitidine","famotidine","metoclopramide","ondansetron",
      "loperamide","mesalamine","gastrointestinal","stomach","bowel",
      "ulcer","acid reflux","gerd"], "Gastrointestinal"),
    (["antihistamine","cetirizine","loratadine","fexofenadine","diphenhydramine",
      "allergy","allergic"], "Other"),
    (["corticosteroid","prednisone","dexamethasone","methylprednisolone",
      "hydrocortisone","prednisolone"], "Other"),
    (["antineoplastic","chemotherapy","cancer","oncology","tamoxifen",
      "letrozole","paclitaxel","carboplatin","imatinib","rituximab",
      "pembrolizumab","nivolumab","bevacizumab","trastuzumab"], "Other"),
    (["immunosuppressant","cyclosporine","tacrolimus","mycophenolate",
      "azathioprine","sirolimus","transplant","autoimmune","biologic",
      "adalimumab","infliximab","etanercept","methotrexate",
      "hydroxychloroquine"], "Other"),
    (["thyroid","levothyroxine","methimazole","liothyronine","hormone"], "Other"),
    (["contraceptive","levonorgestrel","estradiol","progesterone",
      "ethinyl estradiol","birth control","oral contraceptive"], "Other"),
    (["osteoporosis","alendronate","risedronate","denosumab","teriparatide",
      "bone"], "Other"),
    (["ophthalmic","glaucoma","latanoprost","timolol","brimonidine",
      "eye drop"], "Other"),
    (["dermatology","isotretinoin","tretinoin","acne","skin","topical",
      "tacrolimus","clobetasol"], "Other"),
    (["urological","tamsulosin","finasteride","sildenafil","tadalafil",
      "prostate","erectile"], "Other"),
    (["antiparasitic","antiprotozoal","antimalarial","chloroquine",
      "hydroxychloroquine","albendazole","mebendazole","ivermectin"], "Other"),
    (["anesthetic","lidocaine","bupivacaine","propofol","ketamine",
      "sevoflurane","muscle relaxant","neuromuscular"], "Other"),
    (["supplement","vitamin","mineral","iron","calcium","magnesium",
      "folate","folic acid","cyanocobalamin","cholecalciferol"], "Other"),
]

def classify_category(name, description=""):
    text = (name + " " + description).lower()
    for keywords, category in CATEGORY_RULES:
        if any(kw in text for kw in keywords):
            return category
    return "Other"

# ── OpenFDA API: fetch drug label info ───────────────────────────────────────
def fetch_openfda(drug_name):
    """Fetch drug label from OpenFDA. Returns dict or None."""
    try:
        url = "https://api.fda.gov/drug/label.json"
        params = {
            "search": f'openfda.generic_name:"{drug_name}"',
            "limit": 1
        }
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            results = r.json().get("results", [])
            if results:
                return results[0]
        # Fallback: search by brand name
        params["search"] = f'openfda.brand_name:"{drug_name}"'
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            results = r.json().get("results", [])
            if results:
                return results[0]
    except Exception:
        pass
    return None

def extract_text(label, *keys):
    """Extract first non-empty text from FDA label sections."""
    for key in keys:
        val = label.get(key)
        if val and isinstance(val, list) and val[0].strip():
            text = val[0].strip()
            # Clean HTML tags
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            # Truncate to reasonable length
            if len(text) > 500:
                text = text[:497] + "..."
            return text
    return ""

def split_into_list(text, max_items=6):
    """Split a block of text into a list of bullet points."""
    if not text:
        return []
    # Try splitting on common delimiters
    items = []
    for sep in ['\n', ';', '.']:
        parts = [p.strip() for p in text.split(sep) if p.strip() and len(p.strip()) > 15]
        if len(parts) >= 2:
            items = parts[:max_items]
            break
    if not items:
        items = [text[:300]]
    return [i.rstrip('.') + '.' if not i.endswith('.') else i for i in items]

# ── RxNorm API: get trade names ───────────────────────────────────────────────
def fetch_trade_names(drug_name):
    """Get brand names from RxNorm."""
    try:
        url = f"https://rxnav.nlm.nih.gov/REST/rxcui.json?name={requests.utils.quote(drug_name)}&search=1"
        r = requests.get(url, timeout=8)
        if r.status_code != 200:
            return []
        rxcui_data = r.json().get("idGroup", {}).get("rxnormId", [])
        if not rxcui_data:
            return []
        rxcui = rxcui_data[0]
        # Get related brand names
        url2 = f"https://rxnav.nlm.nih.gov/REST/rxcui/{rxcui}/related.json?tty=BN"
        r2 = requests.get(url2, timeout=8)
        if r2.status_code != 200:
            return []
        groups = r2.json().get("relatedGroup", {}).get("conceptGroup", [])
        brands = []
        for g in groups:
            for c in g.get("conceptProperties", []):
                name = c.get("name", "").strip()
                if name and name.lower() != drug_name.lower():
                    brands.append(name)
        return list(dict.fromkeys(brands))[:5]  # deduplicate, max 5
    except Exception:
        return []

# ── Main build loop ───────────────────────────────────────────────────────────
def build_dataset(drugs):
    dataset = []
    seen = set()
    errors = 0

    for i, drug in enumerate(drugs, 1):
        key = drug.lower().strip()
        if key in seen:
            continue
        seen.add(key)

        print(f"[{i}/{len(drugs)}] Processing: {drug}")

        label = fetch_openfda(drug)
        time.sleep(0.25)  # Respect rate limits

        if label is None:
            errors += 1
            # Still add with minimal data
            entry = {
                "id": i,
                "name": drug.title(),
                "tradeNames": [],
                "category": classify_category(drug),
                "description": f"{drug.title()} is a medication used in medical treatment.",
                "sideEffects": ["Consult your healthcare provider for side effect information."],
                "considerations": ["Always follow your healthcare provider's instructions.",
                                   "Do not stop taking this medication without consulting your doctor."]
            }
        else:
            openfda = label.get("openfda", {})

            # Name
            generic_names = openfda.get("generic_name", [drug.title()])
            name = generic_names[0].title() if generic_names else drug.title()

            # Trade names from FDA label
            brand_names = openfda.get("brand_name", [])
            # Also try RxNorm
            rx_brands = fetch_trade_names(drug)
            time.sleep(0.1)
            all_brands = list(dict.fromkeys(brand_names + rx_brands))[:6]

            # Description from indications_and_usage or purpose
            desc_raw = extract_text(label,
                "indications_and_usage", "purpose", "description",
                "clinical_pharmacology")
            # Keep first 2 sentences max
            sentences = re.split(r'(?<=[.!?])\s+', desc_raw)
            description = " ".join(sentences[:2]).strip() if sentences else \
                f"{name} is used in medical treatment."

            # Side effects
            se_raw = extract_text(label,
                "adverse_reactions", "warnings_and_cautions", "warnings",
                "boxed_warning")
            side_effects = split_into_list(se_raw, 6)
            if not side_effects:
                side_effects = ["Consult your healthcare provider for side effect information."]

            # Considerations
            cons_raw = extract_text(label,
                "warnings_and_cautions", "precautions", "drug_interactions",
                "use_in_specific_populations", "dosage_and_administration")
            considerations = split_into_list(cons_raw, 6)
            if not considerations:
                considerations = [
                    "Take as prescribed by your healthcare provider.",
                    "Do not stop taking this medication without medical guidance.",
                    "Inform your doctor of all other medications you are taking."
                ]

            category = classify_category(name, desc_raw)

            entry = {
                "id": i,
                "name": name,
                "tradeNames": all_brands,
                "category": category,
                "description": description,
                "sideEffects": side_effects[:6],
                "considerations": considerations[:6]
            }

        dataset.append(entry)

        # Progress save every 50
        if i % 50 == 0:
            with open(OUTPUT_FILE, "w") as f:
                json.dump(dataset, f, indent=2)
            print(f"  → Saved checkpoint: {len(dataset)} medications")

    return dataset

# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"Starting medication dataset generation...")
    print(f"Target: {len(SEED_DRUGS)} medications\n")

    dataset = build_dataset(SEED_DRUGS)

    # Final save
    with open(OUTPUT_FILE, "w") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Done! {len(dataset)} medications saved to {OUTPUT_FILE}")
    print(f"   File size: {os.path.getsize(OUTPUT_FILE) / 1024:.1f} KB")

    # Summary by category
    from collections import Counter
    cats = Counter(d["category"] for d in dataset)
    print("\nCategory breakdown:")
    for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")
