"""Collapse the reference field onto one canonical name+edition per textbook.

The bank had accumulated 719 distinct reference strings for roughly 25 real books: the same
text appeared as "KDT 8e", "KD Tripathi", "KD Tripathi 8e" and "KD Tripathi Essentials of
Medical Pharmacology 8e", and several books were cited at two different editions at once
(Bailey & Love 27e and 28e, Dhingra 7e and 8e, Ananthanarayan 10e and 11e). A student cannot
tell those apart, and an inconsistent edition makes a page reference unusable.

Only the book part of the string is rewritten. Anything after the first comma (the chapter) is
preserved verbatim, as is any reference that matches no known book.

    python3 tools/normalise_refs.py            # dry run, prints what would change
    python3 tools/normalise_refs.py --commit
"""
import argparse, json, os, re, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BANK = os.path.join(ROOT, "qbank.json")

# (regex matched against the book part, canonical replacement)
# Editions are the ones that actually exist; where two were in use the more recent real
# edition is kept, except where the older one was overwhelmingly dominant.
CANON = [
    (r"^(HARR|Harrison'?s?)\b.*", "Harrison's Principles of Internal Medicine 21e"),
    (r"^Park'?s?\b.*|^Park \d+e.*", "Park's Textbook of Preventive and Social Medicine 27e"),
    (r"^(KDT|KD Tripathi)\b.*", "KD Tripathi Essentials of Medical Pharmacology 8e"),
    (r"^Robbins.*", "Robbins & Cotran Pathologic Basis of Disease 10e"),
    (r"^Harper'?s?\b.*", "Harper's Illustrated Biochemistry 32e"),
    (r"^(OP Ghai|Ghai)\b.*", "OP Ghai Essential Pediatrics 9e"),
    (r"^Ananthanarayan.*|^Paniker'?s?\b.*", "Ananthanarayan and Paniker's Textbook of Microbiology 11e"),
    (r"^(Guyton|Hall Textbook of Medical Physiology).*", "Guyton and Hall Textbook of Medical Physiology 14e"),
    (r"^(DC Dutta|Dutta).*", "DC Dutta's Textbook of Obstetrics 9e"),
    (r"^Bailey.*", "Bailey & Love's Short Practice of Surgery 28e"),
    (r"^Shaw'?s?\b.*", "Shaw's Textbook of Gynaecology 17e"),
    (r"^Ganong.*", "Ganong's Review of Medical Physiology 26e"),
    (r"^Dhingra.*", "Dhingra Diseases of Ear, Nose and Throat 8e"),
    (r"^Nelson.*", "Nelson Textbook of Pediatrics 21e"),
    (r"^Snell'?s?\b.*", "Snell's Clinical Anatomy by Regions 10e"),
    (r"^(Reddy|Narayan Reddy).*", "Reddy's The Essentials of Forensic Medicine and Toxicology 34e"),
    (r"^Maheshwari'?s?\b.*", "Maheshwari Essential Orthopaedics 6e"),
    (r"^Vasudevan.*", "Vasudevan Textbook of Biochemistry for Medical Students 9e"),
    (r"^(AK Khurana|A\.K\. Khurana|Khurana'?s?)\b.*", "AK Khurana Comprehensive Ophthalmology 8e"),
    (r"^IADVL.*", "IADVL Textbook of Dermatology 5e"),
    (r"^(Neena Khanna|Khanna)\b.*", "Neena Khanna Illustrated Synopsis of Dermatology 6e"),
    (r"^Ahuja.*", "Ahuja A Short Textbook of Psychiatry 8e"),
    (r"^(Kaplan|Sadock).*", "Kaplan & Sadock's Synopsis of Psychiatry 12e"),
    (r"^(Morgan|Morgan and Mikhail|Morgan & Mikhail).*", "Morgan & Mikhail's Clinical Anesthesiology 6e"),
    (r"^Miller'?s?\b.*Anesth.*", "Miller's Anesthesia 9e"),
    # Sutton's Textbook of Radiology and Imaging has no 8th edition; 49 items cited one.
    (r"^Sutton'?s?\b.*", "Sutton's Textbook of Radiology and Imaging 7e"),
    (r"^Williams Obstet.*", "Williams Obstetrics 26e"),
    (r"^Lippincott.*", "Lippincott Illustrated Reviews: Biochemistry 8e"),
    (r"^Langman.*", "Langman's Medical Embryology 14e"),
    (r"^(BD Chaurasia|Chaurasia).*", "BD Chaurasia's Human Anatomy 9e"),
    (r"^(Vishram Singh|Vishram).*", "Vishram Singh Clinical and Surgical Anatomy 3e"),
    (r"^Jawetz.*", "Jawetz Medical Microbiology 28e"),
    (r"^Katzung.*", "Katzung Basic and Clinical Pharmacology 15e"),
    (r"^Apurba.*", "Apurba Sastry Essentials of Medical Microbiology 3e"),
    (r"^(Sabiston|Schwartz).*Surg.*", "Sabiston Textbook of Surgery 21e"),
    (r"^SRB'?s?\b.*", "SRB's Manual of Surgery 6e"),
    (r"^Parsons'?\b.*", "Parsons' Diseases of the Eye 23e"),
    (r"^Modi'?s?\b.*", "Modi's A Textbook of Medical Jurisprudence and Toxicology 26e"),
    # "Niraj Ahuja" is the same author as the psychiatry text already canonicalised above,
    # but the bare surname pattern does not reach a "Niraj Ahuja" prefix.
    (r"^Niraj Ahuja.*", "Ahuja A Short Textbook of Psychiatry 8e"),
    (r"^Campbell'?s?\b.*Orthop.*", "Campbell's Operative Orthopaedics 14e"),
    (r"^Harsh Mohan.*", "Harsh Mohan Textbook of Pathology 8e"),
    (r"^Mahajan'?s?\b.*", "Mahajan's Methods in Biostatistics 9e"),
    (r"^Apley.*", "Apley & Solomon's System of Orthopaedics and Trauma 10e"),
    (r"^Gray'?s?\b.*Anatomy.*", "Gray's Anatomy for Students 4e"),
    (r"^Moore'?s?\b.*Anatomy.*", "Moore's Clinically Oriented Anatomy 8e"),
    (r"^Nandy.*", "Nandy Principles of Forensic Medicine and Toxicology 4e"),
    (r"^Goodman.*", "Goodman & Gilman's The Pharmacological Basis of Therapeutics 14e"),
    (r"^AHA Guidelines.*", "AHA Guidelines for CPR and ECC 2020"),
    (r"^NTEP Technical.*", "NTEP Technical and Operational Guidelines for TB Control in India 2023"),
]
COMPILED = [(re.compile(p, re.I), r) for p, r in CANON]


def canonical(book):
    for rx, rep in COMPILED:
        if rx.match(book):
            return rep
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true")
    args = ap.parse_args()

    bank = json.load(open(BANK))
    qs = bank["questions"]
    changed = collections.Counter()
    unmatched = collections.Counter()

    for q in qs:
        ref = str(q.get("reference", "")).strip()
        if not ref or "real exam recall" in ref.lower():
            continue
        # Split book from chapter on an explicit chapter marker, NOT on the first comma:
        # canonical titles such as "Dhingra Diseases of Ear, Nose and Throat 8e" contain a
        # comma themselves, and splitting there corrupts the reference.
        m = re.split(r",\s*Ch\.\s*|,\s*Chapter\s*| — |;\s*", ref, maxsplit=1)
        book = m[0].strip()
        rest = m[1].strip() if len(m) > 1 else ""
        new_book = canonical(book)
        if new_book is None:
            unmatched[book] += 1
            continue
        new_ref = f"{new_book}, Ch. {rest}" if rest else new_book
        if new_ref != ref:
            changed[f"{book}  ->  {new_book}"] += 1
            if args.commit:
                q["reference"] = new_ref

    print(f"references rewritten: {sum(changed.values())}")
    for k, n in changed.most_common(30):
        print(f"  {n:5d}  {k}")
    print(f"\nunmatched book names left untouched: {sum(unmatched.values())} "
          f"({len(unmatched)} distinct)")
    for k, n in unmatched.most_common(15):
        print(f"  {n:5d}  {k}")

    if args.commit:
        os.replace(BANK, BANK + ".bak")
        json.dump(bank, open(BANK, "w"), indent=1, ensure_ascii=False)
        print("\n✓ written (backup at qbank.json.bak)")


if __name__ == "__main__":
    main()
