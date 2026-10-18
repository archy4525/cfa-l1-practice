"""Cross-check every stored answer letter against the answer PDFs.

Also flag question-file damage and variant stems that ask two different questions.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_all import SUBJECTS, SOURCE, id_re, parse_solutions, pdf_text  # noqa: E402

DATA = ROOT / "data"
OUT = ROOT / "_audit"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    solutions = json.loads((DATA / "solutions.json").read_text(encoding="utf-8"))
    questions = json.loads((DATA / "questions.json").read_text(encoding="utf-8"))
    by_id = {item["id"]: item for item in questions}
    lines = []
    letter_mismatch = []
    missing_pdf = []
    extra_pdf = []
    for subject in SUBJECTS:
        code = subject["code"]
        path = SOURCE / f"{code}_answers_VERIFIED_V3_1.pdf"
        parsed, problems = parse_solutions(pdf_text(path), code, path.name, subject["title_en"])
        stored_ids = {qid for qid in solutions if qid.startswith(code + "-")}
        pdf_ids = set(parsed)
        for qid in sorted(stored_ids - pdf_ids):
            missing_pdf.append(qid)
        for qid in sorted(pdf_ids - stored_ids):
            extra_pdf.append(qid)
        for qid, item in parsed.items():
            stored = solutions.get(qid)
            if stored and stored["correct"] != item["correct"]:
                letter_mismatch.append(f"{qid} json {stored['correct']} pdf {item['correct']}")
        for problem in problems:
            lines.append(f"PARSE {code} {problem['id']} {problem['reason'][:120]}")
    damaged = []
    for question in questions:
        blob = " ".join(question["choices"].values()) + " " + question["stem"]
        if re.search(r"[|｜]\s*\S{0,16}[\u4e00-\u9fff]", blob):
            damaged.append(question["id"] + " bilingual-header-in-stem-or-choice")
        if re.search(r"\b(?:ETH|QM|ECO|FSA|CI|EQ|FI|DER|AI|PM|INT|SIM)-\d{3}\b", question["stem"]):
            damaged.append(question["id"] + " another-id-in-stem")
        for letter, text in question["choices"].items():
            if re.search(r"\b(?:ETH|QM|ECO|FSA|CI|EQ|FI|DER|AI|PM|INT|SIM)-\d{3}\b", text):
                damaged.append(f"{question['id']} choice {letter} contains an id")
            if not text.strip():
                damaged.append(f"{question['id']} empty {letter}")
        if question["id"] not in solutions:
            damaged.append(question["id"] + " no solution")
        else:
            correct = solutions[question["id"]]["correct"]
            if correct not in question["choices"]:
                damaged.append(question["id"] + " correct letter missing from choices")
    # Numeric originals: if all three choices are a single number, the stated final
    # number must be strictly closest to the stored correct letter.
    numeric_bad = []
    number = re.compile(r"^[\$]?\s*(-?\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*%?$")
    for question in questions:
        nums = {}
        ok = True
        for letter, text in question["choices"].items():
            match = number.match(text.strip())
            if not match:
                ok = False
                break
            nums[letter] = float(match.group(1).replace(",", ""))
        if not ok:
            continue
        solution = solutions[question["id"]]
        final = solution.get("final_answer") or ""
        found = re.search(r"(-?\d{1,3}(?:,\d{3})*(?:\.\d+)?)", final.replace("$", "").replace("−", "-"))
        stated = float(found.group(1).replace(",", "")) if found else nums[solution["correct"]]
        distances = {letter: abs(stated - value) for letter, value in nums.items()}
        winners = [letter for letter, dist in distances.items() if abs(dist - min(distances.values())) < 1e-9]
        if winners != [solution["correct"]]:
            numeric_bad.append(f"{question['id']} key {solution['correct']} winners {winners} stated {stated} choices {nums}")

    variants = json.loads((DATA / "subject_variant_questions.json").read_text(encoding="utf-8"))
    variant_solutions = {item["id"]: item for item in json.loads((DATA / "subject_variant_solutions.json").read_text(encoding="utf-8"))}
    double_question = []
    for item in variants:
        stem = item["stem"]
        marks = stem.count("?")
        if marks > 1 or (marks == 1 and "inconsistent" in stem and not stem.strip().endswith("?")):
            double_question.append(item["id"])
        elif marks >= 1 and "Which of the following statements is inconsistent" in stem and stem.find("?") < stem.rfind("?"):
            double_question.append(item["id"])
        # original stem already asks something, then we appended a second question
        if "inconsistent with the study notes" in stem and stem.split("Which of the following")[0].strip().endswith(("?", ":")):
            if item["id"] not in double_question:
                double_question.append(item["id"])
    report = [
        f"stored questions {len(questions)} stored solutions {len(solutions)}",
        f"letter mismatches {len(letter_mismatch)}",
        *letter_mismatch,
        f"missing from pdf parse {len(missing_pdf)} {missing_pdf[:20]}",
        f"pdf ids not stored {len(extra_pdf)} {extra_pdf[:20]}",
        f"damaged {len(damaged)}",
        *damaged[:40],
        f"numeric choice conflicts {len(numeric_bad)}",
        *numeric_bad,
        f"subject variants {len(variants)} double-question stems {len(double_question)}",
        f"variant solutions {len(variant_solutions)}",
    ]
    (OUT / "report.txt").write_text("\n".join(report + lines), encoding="utf-8")
    print("\n".join(report[:12]))


if __name__ == "__main__":
    main()
