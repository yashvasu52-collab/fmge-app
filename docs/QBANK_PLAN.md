# FMGE Question Bank — Coverage & Build Plan

**Status:** DRAFT · **Version:** 1.0 · **Date:** 2026-08-31 · **Owner:** Yash
**Scope:** `qbank.json` — the study material. Not the app shell, which is functionally complete.

---

## 0. Why this document exists

The app works. The bank doesn't cover the exam.

`qbank.json` holds **2,196 questions across 19 subjects and 119 topics** with zero duplicate
stems — real work, and the PYQ recalls in it are the most valuable asset in the repo. But it was
built by filling each topic up to 30 questions rather than by exam weight: **44 of 119 topics sit
at exactly 30**. That ceiling produced inverted coverage. Ophthalmology (5 marks in a 300-mark
paper) has 120 questions. Medicine (39 marks — the single heaviest subject) has 166. ENT, worth
2× Ophthalmology, has 35.

Separately, **1,239 of 2,196 questions (56%) carry `verified: "N"`** — AI-generated and never
fact-checked. The app already renders an "⚠ AI-generated · unverified" badge for them, which is
honest but not a bank you can revise from.

This plan fixes coverage, depth, taxonomy and trust, in blueprint-weighted order.

---

## 1. Blueprint & allocation

### 1.1 Where the weights come from

Not from a syllabus PDF. The bank already contains **658 recalled real-exam questions**
(`Q_PYQ_FMGE_*`: FMGE 2024 Jan/Jun, 2025 Jan P1+P2, 2025 Jul P1+P2, 2026 Jan, 2026 Jun). Their
subject distribution *is* the blueprint, measured from the exam itself. `tools/blueprint.py`
regenerates the table below from `qbank.json` alone, so every new recall you add re-corrects the
targets automatically:

```
python3 tools/blueprint.py            # human-readable
python3 tools/blueprint.py --csv      # for a spreadsheet
python3 tools/blueprint.py --depth 15 # re-scope the whole bank with one flag
```

### 1.2 Depth: the one constant that sizes everything

```python
DEPTH = 20   # authored questions per blueprint-question   →  ~6,040-question bank
```

**Decided: 20×.** It lives as a single constant in `tools/blueprint.py`. A re-scope later is a
one-line change, not a re-plan.

### 1.3 The allocation table

| Subject | Blueprint /300 | Target Q | Have | Gap | Topics now | Topics target | Q/topic | Unverified |
|---|---|---|---|---|---|---|---|---|
| Medicine | 39 | 780 | 166 | **+614** | 12 | 39 | 20 | 38 |
| Obstetrics & Gynaecology | 25 | 500 | 91 | **+409** | 7 | 25 | 20 | 12 |
| PSM (Community Medicine) | 25 | 500 | 187 | +313 | 9 | 25 | 20 | 108 |
| Microbiology | 23 | 460 | 155 | +305 | 9 | 23 | 20 | 80 |
| Pathology | 28 | 560 | 257 | +303 | 12 | 28 | 20 | 159 |
| Pediatrics | 18 | 360 | 59 | **+301** | 4 | 18 | 20 | 9 |
| Physiology | 17 | 340 | 79 | +261 | 6 | 17 | 20 | 27 |
| Surgery | 18 | 360 | 116 | +244 | 7 | 20 | 18 | 58 |
| Pharmacology | 23 | 460 | 245 | +215 | 13 | 23 | 20 | 159 |
| Biochemistry | 17 | 340 | 131 | +209 | 6 | 17 | 20 | 81 |
| ENT | 11 | 220 | 35 | **+185** | 3 | 11 | 20 | 6 |
| Anatomy | 15 | 300 | 157 | +143 | 7 | 15 | 20 | 107 |
| Forensic Medicine (FMT) | 11 | 220 | 93 | +127 | 5 | 11 | 20 | 62 |
| Psychiatry | 7 | 140 | 48 | +92 | 3 | 7 | 20 | 28 |
| Radiology | 5 | 100 | 45 | +55 | 3 | 8 | 13 | 30 |
| Anaesthesia | 6 | 120 | 73 | +47 | 3 | 6 | 20 | 57 |
| Dermatology | 5 | 100 | 71 | +29 | 3 | 9 | 11 | 56 |
| Orthopedics | 4 | 80 | 68 | +12 | 3 | 9 | 9 | 56 |
| Ophthalmology | 5 | 100 | 120 | **−20** | 4 | 10 | 10 | 106 |
| **Total** | **300** | **6,040** | **2,196** | **+3,844** | **119** | **321** | — | **1,239** |

### 1.4 Why 321 topics and not ~250

Depth follows exam weight. **Breadth cannot** — a 4-mark subject still has a full syllabus, and a
question can only be asked about a topic that exists in the taxonomy. So topic counts are set by
syllabus breadth and depth-per-topic absorbs the difference:

- **Weight-bearing subjects** (Medicine → Anaesthesia): **~20 Q/topic.**
- **Small clinical subjects** (Ophthalmology, Radiology, Dermatology, Orthopedics): **9–13 Q/topic**
  — the syllabus is wide but the exam samples it thinly, so cover everything shallowly rather
  than three topics deeply. This is the direct fix for Ophthalmology's 4 topics × 30.

Total questions is unchanged at **6,040**; only the partitioning differs.

---

## 2. Schema v2 for `qbank.json`

**Additive only.** Every field below is new; nothing is renamed or removed, so the current
`index.html` keeps working untouched and the app can adopt fields one at a time.

Current shape (v1) — keep exactly as is:

```json
{"id":"Q_c1_001","subject":"Pathology","topic":"Cell injury, adaptation, necrosis vs apoptosis",
 "part":"A","difficulty":"E","stem":"…","options":["…","…","…","…"],"correct":1,
 "concept":"…","reference":"Robbins & Cotran 10e, Ch.2 (Cell Injury)","verified":"Y"}
```

New fields (v2):

| Field | Type | Purpose |
|---|---|---|
| `source` | `"pyq"` \| `"authored"` \| `"ai"` | Provenance as data, not an `id`-prefix convention. Lets the app offer a "real PYQs only" mode and lets the validator hold AI content to a stricter bar. |
| `source_ref` | string | Paper token for `pyq` (e.g. `FMGE_2025JULP1`), else author initials. |
| `verified_by` / `verified_on` | string / ISO date | Who checked it and when. `verified` stays `"Y"`/`"N"`. |
| `verify_note` | string | What was corrected. Cheap institutional memory when a question is queried later. |
| `image` | string | Path into `fmge-study-assets` (e.g. `Q_c1d_001.png`). **Unblocks the 12 orphan PNGs sitting in that repo and image-based questions, which are a real FMGE format the bank currently cannot represent at all.** |
| `explanation` | object | Structured teaching content: `{"why_correct": "…", "why_wrong": {"0":"…","2":"…","3":"…"}, "takeaway": "…"}`. `concept` stays as the short one-paragraph form the app renders today. |
| `tags` | string[] | `#high-yield`, `#PYQ`, `#image-based`, `#formula`, `#DoC`. The solution reader already has tag-chip styling (`.tag`) waiting. |

**Distractor-level explanation is the field that turns a question bank into study material.**
Knowing *why B is wrong* is most of the learning; `concept` alone can't carry it. It is also what
makes `Learn this concept` (currently `alert('(mockup) …')`) worth wiring up.

---
## 3. Topic taxonomy — 119 → 321 topics

**Legend:** ✓ = exists in `qbank.json` today (name reproduced **verbatim** — see §3.1) · ＋ = new.

> ### 3.1 Existing topic names are frozen
> The app groups the QBank screen by the raw `subject`/`topic` strings (`renderSubjects()`,
> `index.html:351`), and the weak-topic table in `fmge-study-assets` keys off the same strings.
> **Renaming an existing topic silently breaks both.** Awkward names (`CNS tumors & basics`,
> `Bone tumours; CTEV, DDH`) are therefore kept as-is; where one is doing too much work, the new
> sibling topics narrow it by absorbing its overflow rather than by renaming it.

### Part A — Pre & Para-clinical

**Anatomy — 15 topics · 300 Q**
1. ✓ Inguinal canal, GIT relations
2. ✓ Pharyngeal arches, germ-layer derivatives
3. ✓ Spinal cord tracts & lesions
4. ✓ Mediastinum, heart & great vessels
5. ✓ Cranial nerves & nuclei
6. ✓ Brachial plexus & nerve injuries (radial/median/ulnar)
7. ✓ Lower limb: femoral/sciatic nerve, foot drop
8. ＋ Upper limb: axilla, cubital fossa, hand spaces
9. ＋ Thorax: lungs, pleura, diaphragm
10. ＋ Abdomen: peritoneum, liver & biliary, portal system
11. ＋ Pelvis & perineum: pelvic floor, urogenital triangle
12. ＋ Head & neck: triangles, thyroid, parotid, TMJ
13. ＋ Skull base, cavernous sinus & meninges
14. ＋ Cerebrum: blood supply, internal capsule, basal ganglia, cerebellum
15. ＋ General embryology & histology: fertilisation, placenta, epithelia

**Physiology — 17 topics · 340 Q**
1. ✓ Synapses, reflexes, ascending/descending pathways
2. ✓ Hormone actions & feedback
3. ✓ GFR, clearance, urine concentration
4. ✓ Action potential & neuromuscular junction
5. ✓ O2/CO2 transport, hypoxia
6. ✓ Cardiac cycle, ECG basis, BP regulation
7. ＋ Cell membrane transport & body fluid compartments
8. ＋ Muscle physiology: skeletal, smooth & cardiac contraction
9. ＋ Blood: haemopoiesis, haemostasis, blood groups
10. ＋ Cardiac output, regional circulations & exercise
11. ＋ Lung volumes, compliance, V/Q & mechanics of breathing
12. ＋ Respiratory regulation, high altitude & diving
13. ＋ Renal tubular transport, acid-base regulation & micturition
14. ＋ GIT secretions, motility & absorption
15. ＋ Thyroid, adrenal, pancreas & calcium homeostasis
16. ＋ Reproductive physiology, pregnancy & lactation
17. ＋ Special senses, CSF, temperature regulation & sleep

**Biochemistry — 17 topics · 340 Q**
1. ✓ Amino acid metabolism & urea cycle
2. ✓ Glycolysis, TCA, gluconeogenesis (key enzymes)
3. ✓ Lipid metabolism & lipoproteins
4. ✓ DNA/RNA, replication, mutations
5. ✓ Vitamins & deficiency diseases
6. ✓ Inborn errors of metabolism
7. ＋ Enzymes: kinetics, regulation & clinical enzymology
8. ＋ Carbohydrate chemistry, glycogen metabolism & HMP shunt
9. ＋ Protein structure, collagen & haemoglobin variants
10. ＋ Nucleotide metabolism: purine/pyrimidine, gout
11. ＋ Transcription, translation & post-translational modification
12. ＋ Gene regulation & molecular techniques (PCR, blotting)
13. ＋ Oxidative phosphorylation, ETC & free radicals
14. ＋ Minerals, trace elements & acid-base biochemistry
15. ＋ Integration of metabolism: fed/fasting, diabetes, ketosis
16. ＋ Haem synthesis, porphyrias & bilirubin metabolism
17. ＋ Cancer biology, oncogenes & tumour biochemistry

**Pathology — 28 topics · 560 Q**
1. ✓ Cell injury, adaptation, necrosis vs apoptosis
2. ✓ Acute & chronic inflammation, healing/repair
3. ✓ Neoplasia: grading vs staging, tumor markers
4. ✓ Hypersensitivity, autoimmunity, amyloidosis
5. ✓ Anemias (micro/macro/hemolytic)
6. ✓ Leukemias (acute/chronic) & basic classification
7. ✓ Lymphomas (Hodgkin vs NHL), Reed-Sternberg
8. ✓ Bleeding & coagulation disorders
9. ✓ Atherosclerosis, MI, vasculitis
10. ✓ Glomerulonephritis, nephrotic vs nephritic
11. ✓ Cirrhosis, hepatitis, jaundice patterns
12. ✓ CNS tumors & basics
13. ＋ Haemodynamics: oedema, thrombosis, embolism, infarction, shock
14. ＋ Genetic & chromosomal disorders
15. ＋ Carcinogenesis, molecular basis & metastasis
16. ＋ Immunodeficiency, transplant rejection & HLA
17. ＋ Plasma cell dyscrasias & myeloproliferative neoplasms
18. ＋ Myelodysplasia, marrow failure & transfusion medicine
19. ＋ Lung: COPD, pneumonia, carcinoma lung, occupational lung disease
20. ＋ GIT: PUD, IBD, colorectal carcinoma, malabsorption
21. ＋ Renal: tubulointerstitial, cystic disease, renal tumours
22. ＋ Male & female genital tract pathology
23. ＋ Breast pathology
24. ＋ Endocrine pathology: thyroid, adrenal, pituitary, MEN
25. ＋ Bone & soft tissue tumours
26. ＋ Skin pathology & melanoma
27. ＋ Granulomatous disease & TB pathology
28. ＋ Cytopathology, IHC, autopsy & lab techniques

**Microbiology — 23 topics · 460 Q**
1. ✓ Sterilization, disinfection, stains, culture media
2. ✓ Gram-positive: Staph, Strep, toxins
3. ✓ Gram-negative: E.coli, Salmonella, Vibrio, Pseudomonas
4. ✓ Mycobacteria (TB, leprosy) & lab diagnosis
5. ✓ Hepatitis viruses (serology markers)
6. ✓ HIV: virology, diagnosis, opportunistic infections
7. ✓ Immunoglobulins, complement, hypersensitivity
8. ✓ Malaria & other protozoa
9. ✓ Medically important fungi
10. ＋ Bacterial structure, growth, genetics & antimicrobial resistance
11. ＋ Clostridia & anaerobes (tetanus, gas gangrene, botulism)
12. ＋ Corynebacterium, Bacillus, Listeria, Nocardia, Actinomyces
13. ＋ Neisseria, Haemophilus, Bordetella, Brucella
14. ＋ Spirochaetes: syphilis, leptospira, borrelia
15. ＋ Rickettsia, Chlamydia, Mycoplasma
16. ＋ Herpesviruses, CMV & EBV
17. ＋ Respiratory viruses: influenza, SARS-CoV-2, measles, mumps, rubella
18. ＋ Arboviruses: dengue, chikungunya, JE, Zika
19. ＋ Rabies, polio & enteroviruses
20. ＋ Helminths: intestinal & tissue nematodes, cestodes, trematodes
21. ＋ Innate & adaptive immunity, antigen-antibody reactions, vaccines
22. ＋ Hospital-acquired infection, biomedical waste & infection control
23. ＋ Specimen collection, serology & molecular diagnostics

**Pharmacology — 23 topics · 460 Q**
1. ✓ Pharmacokinetics/dynamics, receptors
2. ✓ ADRs, enzyme inducers/inhibitors
3. ✓ Cholinergic & anticholinergic drugs
4. ✓ Adrenergic agonists/antagonists
5. ✓ Antihypertensives
6. ✓ Heart failure, antiarrhythmics, antianginals
7. ✓ Antiepileptics
8. ✓ General & local anaesthetics, opioids
9. ✓ Antipsychotics, antidepressants
10. ✓ Antibiotics: classes, MOA, resistance, DoC
11. ✓ Anti-TB drugs & ADRs
12. ✓ Antivirals, antifungals, antimalarials, anticancer
13. ✓ Insulin/OHAs, thyroid, corticosteroids
14. ＋ Skeletal muscle relaxants & drugs for Parkinsonism
15. ＋ NSAIDs, analgesics, antipyretics & drugs for gout
16. ＋ Diuretics & drugs acting on the kidney
17. ＋ Anticoagulants, antiplatelets, thrombolytics & hypolipidaemics
18. ＋ Asthma & COPD drugs, antitussives & antihistamines
19. ＋ GIT drugs: antiemetics, antacids/PPIs, laxatives, antidiarrhoeals
20. ＋ Sex hormones, contraceptives, uterine & bone drugs
21. ＋ Anthelmintics, antileprotics & antiamoebics
22. ＋ Immunosuppressants, biologicals, vitamins & chelators
23. ＋ Clinical trials, pharmacovigilance, prescription writing & drug schedules

**Forensic Medicine (FMT) — 11 topics · 220 Q**
1. ✓ Death, postmortem changes (rigor/livor/algor)
2. ✓ Asphyxial deaths (hanging, drowning)
3. ✓ Wounds, firearm & mechanical injuries
4. ✓ Legal procedure, consent, key IPC sections
5. ✓ Common poisons (OPC, corrosives, snakebite)
6. ＋ Identification: age, sex, dactylography, DNA, anthropometry
7. ＋ Thermal, electrical & lightning injuries; burns
8. ＋ Sexual offences, infanticide & abortion law
9. ＋ Medical jurisprudence: negligence, consumer protection, PC-PNDT, MTP & transplantation acts
10. ＋ Forensic psychiatry, general toxicology & autopsy technique
11. ＋ Alcohol, opioids, sedatives & drugs of abuse (medico-legal)

**PSM (Community Medicine) — 25 topics · 500 Q**
1. ✓ Study designs; incidence vs prevalence
2. ✓ Screening: sensitivity/specificity/PPV
3. ✓ Biostatistics: tests & distributions
4. ✓ Epidemiology & control: TB, malaria, HIV
5. ✓ Demography, family planning, MCH indicators
6. ✓ National health programs (NHM, NTEP, etc.)
7. ✓ National immunization schedule
8. ✓ Nutritional requirements & deficiency diseases
9. ✓ Water/waste, biomedical waste, vital statistics
10. ＋ Concepts of health & disease, natural history, levels of prevention
11. ＋ Association & causation, bias, confounding, measures of risk
12. ＋ Respiratory & vaccine-preventable disease epidemiology (measles, diphtheria, polio)
13. ＋ Vector-borne disease: dengue, chikungunya, filaria, kala-azar
14. ＋ Diarrhoeal disease, enteric fever, hepatitis & helminths
15. ＋ Zoonoses: rabies, plague, leptospirosis, brucellosis
16. ＋ Non-communicable disease epidemiology: CVD, diabetes, cancer, tobacco
17. ＋ Maternal health, RCH & safe motherhood programmes
18. ＋ Child health programmes, IMNCI & school health
19. ＋ Nutrition programmes, food fortification & food hygiene
20. ＋ Occupational health & industrial diseases
21. ＋ Environmental health: air, noise, housing, climate
22. ＋ Health planning, committees & health policy
23. ＋ Health economics, insurance, Ayushman Bharat & financing
24. ＋ Health care delivery: PHC/CHC, HWC, ASHA & IPHS
25. ＋ International health, WHO, SDGs & disaster management

### Part B — Clinical

**Medicine — 39 topics · 780 Q**
1. ✓ IHD / acute MI: diagnosis & management
2. ✓ Heart failure & valvular disease
3. ✓ COPD & asthma
4. ✓ Pulmonary TB: diagnosis & regimens
5. ✓ AKI/CKD & electrolyte/acid-base disorders
6. ✓ Stroke, epilepsy, meningitis
7. ✓ Muscular dystrophies & neuromuscular disorders
8. ✓ Diabetes mellitus: diagnosis, complications, mgmt
9. ✓ Thyroid disorders
10. ✓ Adrenal disorders: Cushing's, Conn's, Addison's
11. ✓ Cirrhosis, hepatitis, GI bleed, IBD/PUD
12. ✓ Dengue, malaria, enteric fever
13. ＋ Hypertension: evaluation, secondary causes, management
14. ＋ Arrhythmias & ECG interpretation
15. ＋ Infective endocarditis, rheumatic fever & pericardial disease
16. ＋ Cardiomyopathies & adult congenital heart disease
17. ＋ Pneumonia, bronchiectasis & lung abscess
18. ＋ Pleural effusion, pneumothorax & interstitial lung disease
19. ＋ Pulmonary embolism, pulmonary hypertension & sleep apnoea
20. ＋ Anaemias & haematinic deficiencies
21. ＋ Leukaemias, lymphomas & plasma cell disorders
22. ＋ Bleeding disorders, thrombophilia & anticoagulation
23. ＋ Glomerular disease & nephrotic syndrome
24. ＋ Tubulointerstitial disease, RTA & renal replacement therapy
25. ＋ Peripheral neuropathy, GBS & myasthenia gravis
26. ＋ Movement disorders, Parkinson's disease & dementia
27. ＋ Demyelinating disease, spinal cord syndromes & headache
28. ＋ Coma, raised intracranial pressure & brain death
29. ＋ HIV/AIDS: staging, ART & opportunistic infections
30. ＋ Sepsis, fever of unknown origin & antimicrobial stewardship
31. ＋ Leptospirosis, rickettsial & scrub typhus; zoonoses
32. ＋ Pituitary, parathyroid & calcium disorders
33. ＋ Obesity, dyslipidaemia & metabolic syndrome
34. ＋ Rheumatoid arthritis, SLE & connective tissue disease
35. ＋ Spondyloarthritis, gout & the vasculitides
36. ＋ Pancreatitis, malabsorption & acute liver failure
37. ＋ Poisoning & envenomation: emergency management
38. ＋ Geriatrics, palliative care & end-of-life issues
39. ＋ Nutritional & vitamin deficiency states in adults

**Surgery — 20 topics · 360 Q**
1. ✓ Trauma, shock, ATLS basics
2. ✓ Hernias (inguinal, femoral)
3. ✓ Thyroid swellings & surgery
4. ✓ Acute abdomen, appendicitis, obstruction
5. ✓ Gallstones, pancreatitis
6. ✓ Breast lumps & carcinoma breast
7. ✓ Urinary stones, BPH, hematuria
8. ＋ Wound healing, surgical site infection & sutures
9. ＋ Fluid, electrolyte & nutritional support in surgery
10. ＋ Blood transfusion & coagulation in surgery
11. ＋ Burns & basics of plastic surgery
12. ＋ Head injury & neurosurgical emergencies
13. ＋ Chest trauma & thoracic surgery
14. ＋ Salivary glands, neck swellings & oral cavity carcinoma
15. ＋ Oesophagus, stomach & gastric carcinoma
16. ＋ Colon, rectum & anal canal disorders
17. ＋ Liver, spleen & portal hypertension surgery
18. ＋ Urology: renal, bladder & testicular tumours; hydrocele, phimosis
19. ＋ Vascular surgery, varicose veins & peripheral arterial disease
20. ＋ Paediatric surgery: intussusception, pyloric stenosis, hypospadias

**Obstetrics & Gynaecology — 25 topics · 500 Q**
1. ✓ Antenatal care & normal labour
2. ✓ Preeclampsia/eclampsia, APH
3. ✓ Postpartum haemorrhage
4. ✓ Abortion, ectopic pregnancy, recurrent pregnancy loss
5. ✓ Contraception
6. ✓ Menstrual disorders, PCOS, fibroids
7. ✓ Ca cervix / endometrium / ovary; screening
8. ＋ Physiological changes in pregnancy & fetal development
9. ＋ Diagnosis of pregnancy, antenatal imaging & fetal surveillance
10. ＋ Multiple pregnancy, polyhydramnios & IUGR
11. ＋ Medical disorders in pregnancy: anaemia, diabetes, heart disease
12. ＋ Infections in pregnancy & Rh isoimmunisation
13. ＋ Abnormal labour: malpresentation, obstructed labour, CPD
14. ＋ Induction, augmentation & operative obstetrics (forceps, vacuum, LSCS)
15. ＋ Preterm labour, PROM & post-term pregnancy
16. ＋ Third-stage complications, retained placenta & uterine inversion
17. ＋ Puerperium, lactation & puerperal sepsis
18. ＋ Obstetric analgesia & anaesthesia; maternal mortality
19. ＋ Puberty, amenorrhoea & abnormal uterine bleeding
20. ＋ Infertility & assisted reproduction
21. ＋ Endometriosis, adenomyosis & chronic pelvic pain
22. ＋ Genital infections, PID & STIs in women
23. ＋ Prolapse, urogynaecology & genital fistula
24. ＋ Menopause, HRT & osteoporosis
25. ＋ Gestational trophoblastic disease & vulvo-vaginal lesions

**Pediatrics — 18 topics · 360 Q**
1. ✓ Growth & development milestones
2. ✓ PEM, breastfeeding, micronutrients
3. ✓ Neonatal jaundice, sepsis, resuscitation
4. ✓ Immunization & common infections
5. ＋ Newborn assessment, prematurity & low birth weight
6. ＋ Respiratory distress in the newborn & neonatal seizures
7. ＋ Inborn errors, newborn screening & chromosomal syndromes
8. ＋ Fluid & electrolyte therapy and diarrhoeal disease in children
9. ＋ Acute respiratory infection, pneumonia & bronchiolitis
10. ＋ Childhood tuberculosis & paediatric HIV
11. ＋ Congenital & rheumatic heart disease in children
12. ＋ Paediatric nephrology: nephrotic syndrome, UTI, AGN
13. ＋ Paediatric neurology: seizures, cerebral palsy, meningitis
14. ＋ Paediatric haematology-oncology: anaemias, thalassaemia, leukaemia
15. ＋ Paediatric endocrinology: short stature, hypothyroidism, diabetes
16. ＋ Paediatric GIT, liver disease & malabsorption
17. ＋ Behavioural & developmental disorders; adolescent health
18. ＋ Paediatric emergencies, poisoning & IMNCI

**ENT — 11 topics · 220 Q**
1. ✓ Otitis media, CSOM, hearing loss
2. ✓ Sinusitis, epistaxis, DNS
3. ✓ Tonsillitis, carcinoma larynx
4. ＋ Anatomy & physiology of the ear; audiological tests
5. ＋ External & middle ear disease: otitis externa, otosclerosis
6. ＋ Vertigo, Meniere's disease & facial nerve palsy
7. ＋ Complications of ear disease & CSF leak
8. ＋ Nasal polyps, granulomatous disease & tumours of nose and PNS
9. ＋ Oral cavity, salivary gland & pharyngeal disease
10. ＋ Larynx: hoarseness, stridor, vocal cord palsy, tracheostomy
11. ＋ Neck spaces, deep neck infection & aerodigestive foreign bodies

**Ophthalmology — 10 topics · 100 Q**
1. ✓ Refractive errors
2. ✓ Cataract
3. ✓ Glaucoma
4. ✓ Diabetic retinopathy, retinal detachment
5. ＋ Cornea: keratitis, ulcers, dystrophies & corneal transplant
6. ＋ Conjunctiva, lids & lacrimal apparatus
7. ＋ Uveitis, scleritis & ocular inflammation
8. ＋ Retina & vitreous: vascular occlusions, ARMD, retinoblastoma
9. ＋ Squint, amblyopia & neuro-ophthalmology (optic nerve, pupil, fields)
10. ＋ Ocular trauma, orbit, ocular pharmacology & blindness control

**Orthopedics — 9 topics · 80 Q**
1. ✓ Specific fractures (Colles, NOF, supracondylar) & healing
2. ✓ Osteomyelitis & TB spine
3. ✓ Bone tumours; CTEV, DDH
4. ＋ Fracture principles, complications & compartment syndrome
5. ＋ Upper limb injuries: shoulder, humerus, elbow, wrist
6. ＋ Lower limb & pelvic injuries; hip dislocation
7. ＋ Spine injury, disc prolapse & spinal deformity
8. ＋ Arthritis, avascular necrosis & joint replacement
9. ＋ Nerve injuries, implants, splints & rehabilitation

**Dermatology — 9 topics · 100 Q**
1. ✓ Leprosy (types, lepra reactions)
2. ✓ Psoriasis, lichen planus
3. ✓ Pemphigus vs pemphigoid; STDs
4. ＋ Structure of skin & approach to dermatological diagnosis
5. ＋ Bacterial, fungal & viral skin infections; scabies, pediculosis
6. ＋ Eczema, atopic & contact dermatitis, urticaria
7. ＋ Acne, rosacea, hair & nail disorders
8. ＋ Pigmentary disorders (vitiligo, melasma) & genodermatoses
9. ＋ Drug reactions (SJS/TEN), skin tumours & melanoma; topical therapy

**Psychiatry — 7 topics · 140 Q**
1. ✓ Schizophrenia & psychosis
2. ✓ Depression & bipolar disorder
3. ✓ Anxiety disorders & substance use
4. ＋ Psychiatric history, mental status examination & classification (ICD/DSM)
5. ＋ Delirium, dementia & organic mental disorders
6. ＋ Somatoform, dissociative, personality & sexual disorders
7. ＋ Child psychiatry, psychopharmacology, ECT & psychotherapies

**Anaesthesia — 6 topics · 120 Q**
1. ✓ Preop assessment (ASA), airway management
2. ✓ Local anaesthetics (max doses, toxicity)
3. ✓ CPR / BLS-ACLS basics
4. ＋ General anaesthetics: IV induction & inhalational agents
5. ＋ Muscle relaxants, monitoring, anaesthesia machine & breathing circuits
6. ＋ Regional, spinal & epidural anaesthesia; postoperative care, pain & complications

**Radiology — 8 topics · 100 Q**
1. ✓ Radiation safety & principles
2. ✓ Choice of imaging modality; contrast
3. ✓ Chest X-ray signs
4. ＋ Skeletal radiology & classic bone signs
5. ＋ Abdominal & GIT imaging; acute abdomen signs
6. ＋ CNS imaging: CT/MRI in stroke, trauma & space-occupying lesions
7. ＋ Obstetric, breast & pelvic imaging
8. ＋ Nuclear medicine, radiotherapy basics & interventional radiology

**Taxonomy totals:** 119 existing (all preserved) + 202 new = **321 topics**.

---
## 4. Correction: Part A / Part B is not a pre-clinical / clinical split

**This is the one structural error in the current content model, and it changes how mocks are built.**

`index.json` labels the two papers *"Pre & Para-clinical"* (Part A) and *"Clinical"* (Part B), and
`part` in `qbank.json` is a fixed function of subject — Anatomy is always `A`, Medicine always `B`,
for all 2,196 questions. The real papers don't work that way. Measured from the recalls, splitting
subjects into pre/para vs clinical:

| Real paper | Questions recalled | Pre/para | Clinical |
|---|---|---|---|
| FMGE 2025 Jul · Paper 1 | 130 | 26 | 104 |
| FMGE 2025 Jul · Paper 2 | 138 | 86 | 52 |
| FMGE 2025 Jan · Paper 1 | 123 | 61 | 62 |
| FMGE 2025 Jan · Paper 2 | 108 | 36 | 72 |

Across all recalls every subject appears in **both** papers at comparable frequency (Medicine
P1=32 / P2=33; Pathology 16 / 26; Microbiology 18 / 20). FMGE Paper 1 and Paper 2 are simply **two
150-question halves, each drawn from the whole syllabus.** Only OBG (40/12) and Ophthalmology (8/2)
lean, and at those sample sizes that is noise.

**Consequences for this plan:**

1. A "Part A" mock of pre/para subjects only does not resemble any real paper. **Cycle 4's Part A/B
   papers are therefore not exam-like in structure**, however good the questions are.
2. `part` stays in the schema (the app reads it, `exportAnswers()` writes it into the answer file),
   but it is **demoted to a legacy label** — it is derivable from `subject` and carries no new
   information. Nothing new should be built on it.
3. Mocks become **blueprint-weighted samples across all 19 subjects, split into two halves of 150**.
   `index.json` subtitles change from "Pre & Para-clinical"/"Clinical" to "Paper 1"/"Paper 2".
4. Per-paper subject counts follow §1.3 halved: Medicine ~20/paper, Pathology ~14, OBG ~13,
   PSM ~13, Micro ~12, Pharm ~12, Surgery ~9, Peds ~9, Physio ~9, Biochem ~9, Anatomy ~8,
   ENT ~6, FMT ~6, Psych ~4, Anaesth ~3, Ophtho ~3, Derm ~3, Radiology ~3, Ortho ~2.

---

## 5. Verification protocol

### 5.1 Priority order

Priority = **unverified count × blueprint weight** — it costs the same to check any question, so
check the ones that carry the most marks first.

| Rank | Subject | Unverified | × bp | Score |
|---|---|---|---|---|
| 1 | Pathology | 159 | 28 | 4,452 |
| 2 | Pharmacology | 159 | 23 | 3,657 |
| 3 | PSM (Community Medicine) | 108 | 25 | 2,700 |
| 4 | Microbiology | 80 | 23 | 1,840 |
| 5 | Anatomy | 107 | 15 | 1,605 |
| 6 | Medicine | 38 | 39 | 1,482 |
| 7 | Biochemistry | 81 | 17 | 1,377 |
| 8 | Surgery | 58 | 18 | 1,044 |
| 9 | Forensic Medicine (FMT) | 62 | 11 | 682 |
| 10 | Ophthalmology | 106 | 5 | 530 |
| 11–19 | Physiology 459 · Anaesthesia 342 · OBG 300 · Dermatology 280 · Orthopedics 224 · Psychiatry 196 · Pediatrics 162 · Radiology 150 · ENT 66 | | | |

### 5.2 Nothing is retired wholesale

**Decided:** the over-built, barely-verified subjects — Ophthalmology (106 unverified),
Anaesthesia (57), Dermatology (56), Orthopedics (56) — get **fact-checked question by question,
and only demonstrably wrong questions are deleted.** This is a verification job, not a rewrite;
the volume already authored is kept wherever it survives a check.

Expect Ophthalmology to end *below* its 100 target once wrong questions are removed. That is the
correct outcome: the gap then gets refilled against the proper 10-topic list in §3, not the old
4 topics × 30.

### 5.3 Per-question checklist

A question flips to `verified: "Y"` only when all of these hold:

- [ ] **One defensible answer.** No second option arguable under a standard text.
- [ ] **Distractors are plausible** — a wrong option a real candidate would consider, not filler.
      (Watch for `["First option","Second option","Third option","Fourth option"]`-style placeholder
      sets, which the demo generator in `index.html:347` produces.)
- [ ] **Reference resolves** to a real chapter/section of a standard text: Robbins, KDT/Katzung,
      Harrison, Bailey & Love, Park, Ganong, Harper, Williams/Shaw, Nelson/Ghai, Dhingra, AK Khurana.
      A reference that can't be opened is not a reference.
- [ ] **`concept` explains, not restates.** It must say *why*, not repeat the correct option.
- [ ] **Not a concept-level duplicate** of an existing question (§6.2 catches near-duplicates
      that differ in wording — the bank has 0 exact duplicate stems but has never been checked
      for these).
- [ ] **Stem is self-contained** — no "as shown in the image" unless `image` is populated.
- [ ] `verified_by` and `verified_on` filled; any correction recorded in `verify_note`.

---

## 6. Authoring workflow

### 6.1 The per-subject loop

Subjects are done one at a time, largest gap first, never in parallel — merge conflicts in a
2 MB single-line-ish JSON file are not worth it.

1. **Pick** the next subject from the §7 milestone order.
2. **Expand** its topic list to §3, `qbank.json` untouched at this stage.
3. **Author** to the per-topic target (§1.3 `Q/topic`), tagging `source` honestly:
   `pyq` > `authored` > `ai`. AI-drafted content enters as `verified: "N"` and is not counted
   toward the target until checked.
4. **Verify** per §5.3.
5. **Merge** into `qbank.json` — one subject per commit, so a bad batch reverts cleanly.
6. **Validate** (§6.2). Green before the next subject starts.

### 6.2 Validator (`tools/validate_qbank.py`, to be written)

Hard failures — block the merge:

- Schema conformance; `id` unique; `subject`/`topic` in the §3 taxonomy (this is what stops the
  taxonomy drifting the moment a second author touches it).
- Exactly 4 `options`, all non-empty and mutually distinct; `correct` an int in 0–3.
- `difficulty` in `E`/`M`/`H`; `verified` in `Y`/`N`; `source` in the enum.
- `verified: "Y"` requires non-empty `reference`, `verified_by`, `verified_on`.
- `image` path exists in `fmge-study-assets`.
- Placeholder-text detector (`"First option"`, `"Explanation coming soon"`, lorem).
- **Exact duplicate stems = 0** (holds today; keep it that way).

Warnings — report, don't block:

- **Concept-level near-duplicates:** normalise the stem (lowercase, strip punctuation/stopwords)
  and flag pairs above a similarity threshold *within the same topic*. The real risk at 6,000
  questions is 5 rewordings of one fact, and no check for it exists today.
- Per-topic count vs target; difficulty mix outside §6.3; answer-key skew (`correct` should be
  ~25% each of A/B/C/D per subject — a generator bias toward one letter is a real tell).

### 6.3 Difficulty balance

Current bank: **E 575 (26%) · M 1,084 (49%) · H 537 (24%)**.

Target **E 30% · M 50% · H 20%** → at 6,040: E ≈ 1,810, M ≈ 3,020, H ≈ 1,210. Enforced
*per topic*, not just per subject, so no topic ends up all-hard. FMGE is a 50% pass/fail
threshold exam, so a bank skewed hard trains for the wrong paper; the current 24% hard is
already slightly heavy.

---

## 7. Milestones

Ordered by blueprint weight × gap. Each phase ends with a green validator run and a commit.

| Phase | Work | Subjects | Adds |
|---|---|---|---|
| **P0** | Clinical catch-up — the heaviest exam weight sitting on the thinnest bank | Medicine, OBG, Pediatrics, ENT, Surgery | **+1,753 Q** |
| **P1** | Verification debt — turn existing volume into trustworthy volume | Pathology, Pharmacology, PSM, Anatomy | **533 questions verified** |
| **P2** | Pre/para depth | Physiology, Biochemistry, Microbiology | **+775 Q** |
| **P3** | Small-subject taxonomy fix + verification sweep — 3-topic subjects expanded to their real topic lists, and the ~275 unverified questions already in them fact-checked | Psychiatry, Radiology, Anaesthesia, Dermatology, Orthopedics, Ophthalmology | **+143 Q, 275 verified** |
| **P4** | Study material — `image` on image-based questions (starting with the 12 orphan PNGs in `fmge-study-assets`) and structured `explanation` on every verified question | all | lights up `Learn this concept` |
| **P5** | Mocks from the bank (§8) — cheap, since the Cycle 4 papers are already bank selections | — | new cycle = a selection, not new content |

P0 and P1 are independent and can be interleaved if fact-checking and authoring feel like
different kinds of work on different days.

---

## 8. Mocks generated from the bank

Today `tests/2026-08-18_c4_A.json` and `_B.json` hold their own copies of 300 questions, so a new
cycle means authoring 300 more and the bank and the papers drift apart.

Target: **a mock is a blueprint-weighted selection from `qbank.json`**, two halves of 150 across
all 19 subjects (§4), difficulty-mixed per §6.3, excluding anything the candidate has already seen
in a previous cycle. `index.json` stays the contract the app reads, so `startGrand()`
(`index.html:348`) needs no change — the files it fetches just become generated output rather than
hand-authored input.

**Measured 2026-08-31: all 300 Cycle 4 questions are already present in `qbank.json`
(150/150 stem-for-stem in each of Part A and Part B).** So the papers are *already* selections
from the bank — they are just frozen as static copies. Nothing needs merging and nothing would be
lost by regenerating them; P5 is purely a matter of replacing two hand-maintained files with a
generator. That makes P5 cheap, and it should be pulled forward if you want exam-like mocks
(§4) before the bank is finished.

---

## 9. Open questions

1. ~~Are the Cycle 4 papers' 300 questions already inside `qbank.json`?~~ **Answered: yes, all
   300.** No merge needed — see §8.
2. **Who verifies?** 1,239 questions at even 2 minutes each is ~41 hours. Realistically this is
   the binding constraint on the whole plan, not authoring.
3. **Is `fmge-study-assets` the right image host?** It's a public repo; question images are the
   most copyable asset in the project.
4. **Should `qbank.json` stay one 2 MB file?** The app fetches all of it on login
   (`preload()`, `index.html:350`). At 6,040 questions that is ~6 MB on every cold load. Splitting
   per subject would need a change to `preload()` — deliberately out of scope here, but it becomes
   a real problem around P2.

---

## 10. Definition of done

- [ ] 6,040 questions, per-subject counts within ±5% of §1.3.
- [ ] All 321 topics in §3 exist and hold at least their §6.3 difficulty mix.
- [ ] **`verified: "Y"` on 100% of the bank.** No unverified question ships; the app's
      "⚠ AI-generated · unverified" badge becomes dead code.
- [ ] `source` populated on every question; PYQ recalls identifiable without parsing `id`.
- [ ] Structured `explanation` on every question; `image` on every image-dependent one.
- [ ] `tools/validate_qbank.py` green.
- [ ] A generated mock is indistinguishable in structure from a real paper (§4, §8).
