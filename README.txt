MedsearchPro
Running the project locally : 
-	 /Users/test/Desktop/Ehsaneh/Business_Plan/medsearchpro-accessible
-	/Users/test/.nvm/versions/node/v20.19.6/bin/node ./node_modules/vite/bin/vite.js --host 0.0.0.0

Deploy changes:
Commit changes locally and then vercel will trigger a new build and deploy changes automatically 

NOTE : any changes on index.html for deployment new index.html should be overridden in dist


# ------------------------------------
# Prompt for organizing the json file :
# ------------------------------------

You are cleaning and transforming a medication JSON file.

Input: a JSON array of medication objects.

Task:
1. Remove the phrase “INDICATIONS AND USAGE” everywhere, including variants such as:
   - “1 INDICATIONS AND USAGE”
   - “1. INDICATIONS AND USAGE”
   - “INDICATIONS AND USAGE”
   Also remove related section numbers like “1.” or “1” only when they are part of that heading.

2. Clean `description` and `fdaIndicationsUsage`:
   - Keep only the actual use/indication text.
   - Remove FDA-style headings, section numbers, citations, and label references.
   - Use plain patient-friendly language.
   - Do not add any new use that is not already in the source text.

3. Clean `sideEffects`:
   - Convert adverse effects into very brief patient-language bullets.
   - Example style:
     - Nausea
     - Upset stomach
     - Skin rash
     - Kidney problems
     - Liver problems
     - Serious allergic reaction
   - Do not invent side effects.
   - Only include effects explicitly present in the original JSON fields such as `sideEffects`, `fdaWarnings`, `fdaBoxedWarning`, `fdaPatientCounseling`, or `dailymedAdverseReactions`.
   - No hallucination, no falsification, no fabrication.

4. Clean warnings:
   - Create or update `fdaWarningsBullets`.
   - Rewrite warnings as short bullet points in patient-friendly language.
   - Keep only information supported by the original text.
   - Remove FDA section numbers, references like “see Warnings and Precautions,” and legal/labeling language.
   - Do not add new warnings.

5. Life-threatening warnings:
   - If a warning mentions death, fatal risk, stroke, heart attack, severe bleeding, overdose, anaphylaxis, severe allergic reaction, liver failure, kidney failure, breathing trouble, or emergency medical help, mark it clearly.
   - Use this JSON structure:
     {
       "text": "May cause serious bleeding.",
       "severity": "life-threatening",
       "color": "red"
     }
   - For non-life-threatening warnings:
     {
       "text": "Take with food if stomach upset occurs.",
       "severity": "standard",
       "color": "normal"
     }

6. Preserve the original JSON structure and all existing fields unless cleaning that field is requested.
7. Process every medication item in the file.
8. Output valid JSON only. No markdown, no explanation, no comments.
9. Add this field to each item:
   "groundingNote": "This item was cleaned only from the existing source text in this JSON. No new medical facts were added."

Return the full cleaned JSON array.

#-------------------------------------------
# Medication list troubleshooting
#--------------------------------------------
To see the medication list online "medication.json" should be available on "public" folder