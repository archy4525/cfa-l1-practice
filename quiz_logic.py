"""Quiz flow. Question records never include the correct letter."""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

QUESTION_FIELDS = (
    "id",
    "origin",
    "topic_id",
    "topic_en",
    "topic_zh",
    "subtopic",
    "qtype",
    "level",
    "stem",
    "choices",
    "source",
)


def _read(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def _read_list(name: str) -> list:
    path = DATA / name
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        raise RuntimeError(f"{name} should be a list of questions")
    return payload


def load_bank() -> dict:
    questions = _read_list("questions.json") + _read_list("variant_questions.json") + _read_list("subject_variant_questions.json")
    original_solutions = _read("solutions.json")
    if isinstance(original_solutions, dict):
        solutions = dict(original_solutions)
    else:
        solutions = {item["id"]: item for item in original_solutions}
    solutions.update({item["id"]: item for item in _read("variant_solutions.json")})
    extra = DATA / "subject_variant_solutions.json"
    if extra.exists():
        solutions.update({item["id"]: item for item in json.loads(extra.read_text(encoding="utf-8"))})
    audit = _read("audit.json")
    held = set(audit.get("held_ids", []))
    playable = []
    for question in questions:
        if "correct" in question or "why_wrong" in question:
            raise RuntimeError(f"{question.get('id')} exposes the answer in the question file")
        if question["id"] in held or question["id"] not in solutions:
            continue
        playable.append({field: question[field] for field in QUESTION_FIELDS})
    return {
        "topics": _read("topics.json"),
        "questions": {item["id"]: item for item in playable},
        "solutions": solutions,
        "audit": audit,
    }


def questions_for(bank: dict, topic_id: str, mode: str) -> list[dict]:
    items = [q for q in bank["questions"].values() if q["topic_id"] == topic_id]
    if mode == "original":
        return [q for q in items if q["origin"] == "original"]
    if mode == "variant":
        return [q for q in items if q["origin"] == "variant"]
    if mode == "mixed":
        return items
    raise ValueError(mode)


def draw_set(bank: dict, topic_id: str, mode: str, count: int, rng: random.Random | None = None) -> list[dict]:
    pool = questions_for(bank, topic_id, mode)
    if count < 1:
        raise ValueError("count")
    rng = rng or random.Random()
    if len(pool) <= count:
        picked = list(pool)
        rng.shuffle(picked)
        return picked
    return rng.sample(pool, count)


def briefing(bank: dict, topic_id: str, quiz: list[dict]) -> dict:
    topic = bank["topics"][topic_id]
    levels = Counter(item["level"] for item in quiz)
    types = Counter(item["qtype"] for item in quiz)
    subtopics = []
    for item in quiz:
        if item["subtopic"] not in subtopics:
            subtopics.append(item["subtopic"])
    return {
        "topic_id": topic_id,
        "title_en": topic["title_en"],
        "title_zh": topic["title_zh"],
        "question_section": topic["question_section"],
        "objectives": topic["objectives"],
        "formulas": topic["formulas"],
        "subtopics": subtopics,
        "count": len(quiz),
        "levels": dict(levels),
        "types": dict(types),
        "source_chapter": topic.get("source_chapter") or "講義",
    }


def grade(bank: dict, question_id: str, choice: str) -> dict:
    if choice not in {"A", "B", "C"}:
        raise ValueError("choice")
    solution = bank["solutions"][question_id]
    question = bank["questions"][question_id]
    return {
        "id": question_id,
        "choice": choice,
        "correct_letter": solution["correct"],
        "is_correct": choice == solution["correct"],
        "correct_text": question["choices"][solution["correct"]],
        "chosen_text": question["choices"][choice],
        "reasoning": solution["reasoning"],
        "steps": solution["steps"],
        "final_answer": solution["final_answer"],
        "why_wrong": solution["why_wrong"],
        "zh": solution["zh"],
        "core_idea": solution["core_idea"],
        "study_section": solution.get("study_section") or question["subtopic"],
        "formula": solution.get("formula") or "",
        "calculator": solution.get("calculator") or "",
        "source_note": solution.get("source_note") or "",
        "based_on": solution.get("based_on") or question["source"].get("based_on", ""),
        "question_ref": question["source"].get("question_ref", question_id),
        "stem": question["stem"],
        "subtopic": question["subtopic"],
    }


def summarize(results: list[dict]) -> dict:
    wrong = [item for item in results if not item["is_correct"]]
    concepts = []
    for item in wrong:
        label = item["core_idea"] or item["subtopic"]
        if label not in concepts:
            concepts.append(label)
    return {
        "total": len(results),
        "correct_count": sum(item["is_correct"] for item in results),
        "wrong": wrong,
        "review_concepts": concepts,
    }
