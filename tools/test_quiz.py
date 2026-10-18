"""Check that answers stay hidden and a short quiz can be graded."""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import quiz_logic


def main() -> None:
    for name in ("questions.json", "variant_questions.json", "subject_variant_questions.json"):
        payload = json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))
        for question in payload:
            assert "correct" not in question, question["id"]
            assert "why_wrong" not in question, question["id"]
            assert set(question["choices"]) == {"A", "B", "C"}

    bank = quiz_logic.load_bank()
    assert "2.1" in bank["topics"]
    assert len(bank["topics"]) > 10
    quiz = quiz_logic.draw_set(bank, "2.1", "variant", 5, random.Random(1))
    assert len(quiz) == 5
    assert all("correct" not in item for item in quiz)
    info = quiz_logic.briefing(bank, "2.1", quiz)
    assert info["count"] == 5
    assert info["objectives"]
    assert info["formulas"]
    assert "Quantitative Methods" in info["source_chapter"]

    eco = quiz_logic.draw_set(bank, "3.5", "variant", 1, random.Random(2))
    assert len(eco) == 1
    assert eco[0]["qtype"] == "Calculation"
    assert "inconsistent with the study notes" not in eco[0]["stem"]
    eco_info = quiz_logic.briefing(bank, "3.5", eco)
    assert "Economics" in eco_info["source_chapter"]

    first = quiz[0]
    right = bank["solutions"][first["id"]]["correct"]
    wrong = next(letter for letter in "ABC" if letter != right)
    good = quiz_logic.grade(bank, first["id"], right)
    bad = quiz_logic.grade(bank, first["id"], wrong)
    assert good["is_correct"] and not bad["is_correct"]
    assert bad["why_wrong"]
    summary = quiz_logic.summarize([good, bad])
    assert summary["correct_count"] == 1
    assert summary["wrong"][0]["id"] == first["id"]
    assert summary["review_concepts"]

    for topic_id in bank["topics"]:
        originals = quiz_logic.questions_for(bank, topic_id, "original")
        assert originals, topic_id
        for item in quiz_logic.questions_for(bank, topic_id, "variant"):
            assert item["id"] in bank["solutions"]
            assert bank["solutions"][item["id"]]["correct"] in item["choices"]
            assert "inconsistent with the study notes" not in item["stem"]
    print("quiz flow ok", len(bank["questions"]), "playable", len(bank["topics"]), "topics")


if __name__ == "__main__":
    main()
