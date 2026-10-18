"""Parse every subject question book and answer book in this folder.

Question JSON never stores the correct letter. Solutions stay in a separate file.
Items whose answer is missing or not unique are listed in audit.json and are not playable.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from build_bank import (  # noqa: E402
    SUBTOPIC_SECTION,
    TOPIC_META,
    final_number,
    join_wrap,
    leading_number,
    normalize,
    numeric_conflicts,
    tidy,
)

SOURCE = ROOT / "data" / "source"
DATA = ROOT / "data"

TYPES = {
    "Application",
    "Calculation",
    "Exam Trap",
    "Recognition",
    "Interpretation",
    "Integration",
    "Multi-Step",
    "Reverse Reasoning",
}
LEVEL_RE = re.compile(r"^L[1-5]\b")
MAJOR_RE = re.compile(r"^1\.(\d{1,2})\s+(\S.+)$")
BAR_HEADER = re.compile(r"^.{0,180}[|｜][^|\n｜]{0,24}[\u4e00-\u9fff]")
TOC_DOTS = re.compile(r"(?:\.\s*){4,}")

SUBJECTS = [
    {
        "code": "ETH",
        "chapter": 1,
        "title_en": "Ethical and Professional Standards",
        "title_zh": "倫理與專業標準",
        "study_key": "ethical and professional standards",
    },
    {
        "code": "QM",
        "chapter": 2,
        "title_en": "Quantitative Methods",
        "title_zh": "數量方法",
        "study_key": "quantitative methods",
    },
    {
        "code": "ECO",
        "chapter": 3,
        "title_en": "Economics",
        "title_zh": "經濟學",
        "study_key": "economics",
    },
    {
        "code": "CI",
        "chapter": 4,
        "title_en": "Corporate Issuers",
        "title_zh": "公司發行人",
        "study_key": "corporate issuers",
    },
    {
        "code": "FSA",
        "chapter": 5,
        "title_en": "Financial Statement Analysis",
        "title_zh": "財務報表分析",
        "study_key": "financial statement analysis",
    },
    {
        "code": "EQ",
        "chapter": 6,
        "title_en": "Equity Investments",
        "title_zh": "權益投資",
        "study_key": "equity investments",
    },
    {
        "code": "FI",
        "chapter": 7,
        "title_en": "Fixed Income",
        "title_zh": "固定收益",
        "study_key": "fixed income",
    },
    {
        "code": "DER",
        "chapter": 8,
        "title_en": "Derivatives",
        "title_zh": "衍生性商品",
        "study_key": "derivatives",
    },
    {
        "code": "AI",
        "chapter": 9,
        "title_en": "Alternative Investments",
        "title_zh": "另類投資",
        "study_key": "alternative investments",
    },
    {
        "code": "PM",
        "chapter": 10,
        "title_en": "Portfolio Management",
        "title_zh": "投資組合管理",
        "study_key": "portfolio management",
    },
    {
        "code": "INT",
        "chapter": None,
        "title_en": "Cross-Chapter Integration",
        "title_zh": "跨章整合",
        "study_key": None,
    },
    {
        "code": "SIM",
        "chapter": None,
        "title_en": "Exam Simulation",
        "title_zh": "模擬測驗",
        "study_key": None,
    },
]


def pdf_text(path: Path) -> str:
    doc = fitz.open(path)
    return "\n".join(normalize(page.get_text()) for page in doc)


def norm_title(text: str) -> str:
    head = re.split(r"[|｜]", text, maxsplit=1)[0]
    head = re.sub(r"^(\d+\.)+\d*\s*", "", head)
    head = re.sub(r"(?:\s*\.){2,}.*$", "", head)
    head = re.sub(r"[^a-z0-9]+", " ", head.lower())
    return " ".join(head.split())


def english_key(header: str) -> str:
    head = re.split(r"\s*[|｜]\s*", header)[0]
    head = re.sub(r"^1\.\d{1,2}\s+", "", head)
    head = re.sub(r"^Reinforcement\s+[—\-]\s+", "", head, flags=re.I)
    head = TOC_DOTS.sub("", head)
    return re.sub(r"\s+", " ", head).strip().lower()


def is_toc_line(line: str) -> bool:
    return bool(TOC_DOTS.search(line))


def is_header(line: str) -> bool:
    if is_toc_line(line):
        return False
    if line.startswith(
        (
            "Subject:",
            "Chapter:",
            "Chapter ",
            "Section:",
            "Core Idea:",
            "Related",
            "Why ",
            "Correct answer",
            "中文",
            "使用：",
            "已知：",
            "按鍵",
            "Mistake Code",
            "Study Book",
            "Question Book",
            "Answer Book",
            "Answer &",
            "Full teaching",
            "Stems and",
            "EXTRA PRACTICE",
            "Not part of the main",
        )
    ):
        return False
    if re.match(r"^\d+\s+[A-Za-z]", line):
        return False
    if MAJOR_RE.match(line):
        return True
    if line in {"Which mean?", "Nonlinear forms"}:
        return True
    if re.match(r"^[A-Z][A-Za-z'’\-]{2,40}(?:\s+[A-Z][A-Za-z'’\-]{2,40})?\?$", line):
        return True
    match = BAR_HEADER.match(line)
    if not match:
        return False
    prefix = re.split(r"[|｜]", line, maxsplit=1)[0].strip()
    if re.search(r"[\u4e00-\u9fff？?！!]", prefix):
        return False
    words = prefix.split()
    if prefix[:1].islower() or len(words) > 16:
        return False
    if len(words) < 2 and not re.fullmatch(r"[A-Z][A-Za-z'’\-]{3,}", prefix):
        return False
    return True


def split_glued(line: str) -> list[str]:
    """Separate a bilingual heading that the PDF glued onto the end of a choice."""
    bar = re.search(r"[|｜][^|\n｜]{0,24}[\u4e00-\u9fff]", line)
    if not bar:
        return [line]
    prefix_region = line[: bar.start()]
    found = re.search(r"(?:^|[.?!)]\s+)((?:[A-Z]|[IVX]+\.)[^|｜]{2,140})$", prefix_region)
    if not found:
        return [line]
    header = (found.group(1) + line[bar.start() :]).strip()
    prefix = re.split(r"[|｜]", header, maxsplit=1)[0].strip()
    kept = line[: found.start(1)].rstrip()
    words = prefix.split()
    one_word = len(words) == 1 and re.fullmatch(r"[A-Z][A-Za-z'’\-]{3,}", prefix) and re.search(r"[.?!)]\s*$", kept)
    if len(words) > 14 or prefix[:1].islower() or re.search(r"[\u4e00-\u9fff？?！!]", prefix):
        return [line]
    if len(words) < 2 and not one_word:
        return [line]
    if len(kept) < 2:
        return [line]
    return [kept, header]


def clean_lines(raw: str) -> list[str]:
    drop_prefixes = (
        "Question Book",
        "Answer Book",
        "Answer & Teaching",
        "Chapter ",
        "Practice companion",
        "CFA LEVEL",
        "English stems",
        "Not an official",
        "Full teaching answers",
        "Contents",
        "Mistake Code",
    )
    lines = []
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.isdigit():
            continue
        if any(s.startswith(prefix) for prefix in drop_prefixes):
            continue
        if "Not part of the main core coverage" in s:
            continue
        lines.append(s)
    exploded = []
    for line in lines:
        exploded.extend(split_glued(line))
    return exploded


def id_re(code: str) -> re.Pattern[str]:
    return re.compile(rf"^{code}-\d{{3}}$")


def body_lines(lines: list[str]) -> list[str]:
    for index, line in enumerate(lines):
        if line.startswith("Stems and choices"):
            return lines[index + 1 :]
    return lines


def section_index_for(key: str, key_to_index: dict[str, int], allow_contains: bool = False) -> int | None:
    if key in key_to_index:
        return key_to_index[key]
    if not allow_contains:
        return None
    if not any(word in key for word in ("practice", "reinforcement", "extra", "legacy", "appendix")):
        return None
    contained = [known for known in key_to_index if len(known) > 10 and known in key]
    if not contained:
        return None
    return key_to_index[max(contained, key=len)]


def scan_sections(lines: list[str], code: str) -> tuple[list[dict], dict[str, int]]:
    sections: list[dict] = []
    key_to_index: dict[str, int] = {}
    current = None
    for line in body_lines(lines):
        if not is_header(line) or id_re(code).match(line):
            continue
        major = MAJOR_RE.match(line)
        key = norm_title(line)
        if major:
            number = int(major.group(1))
            existing = next((idx for idx, section in enumerate(sections) if section["num"] == number), None)
            if existing is None:
                current = {"num": number, "title": tidy(line), "key": key, "subs": []}
                sections.append(current)
                key_to_index[key] = len(sections) - 1
            else:
                current = sections[existing]
                key_to_index[key] = existing
            continue
        if current is None:
            continue
        mapped = section_index_for(key, key_to_index, allow_contains=True)
        if mapped is not None and mapped != sections.index(current):
            current = sections[mapped]
            label = tidy(line)
            if label not in current["subs"]:
                current["subs"].append(label)
            continue
        if key not in key_to_index:
            key_to_index[key] = sections.index(current)
        label = tidy(line)
        if label not in current["subs"]:
            current["subs"].append(label)
    return sections, key_to_index


def parse_questions(raw: str, code: str, sections: list[dict], key_to_index: dict[str, int]) -> tuple[list[dict], list[dict]]:
    lines = body_lines(clean_lines(raw))
    questions = []
    problems = []
    topic_idx = None
    subtopic = "Unassigned"
    matcher = id_re(code)
    i = 0
    while i < len(lines):
        line = lines[i]
        if is_header(line) and not matcher.match(line):
            key = norm_title(line)
            mapped = section_index_for(key, key_to_index, allow_contains=True)
            if mapped is not None and (MAJOR_RE.match(line) or topic_idx is None or mapped != topic_idx):
                topic_idx = mapped
            if not MAJOR_RE.match(line):
                subtopic = tidy(line)
            elif topic_idx is not None:
                subtopic = sections[topic_idx]["title"]
            i += 1
            continue
        if not matcher.match(line):
            i += 1
            continue
        qid = line
        i += 1
        if i >= len(lines) or lines[i] not in TYPES:
            problems.append({"id": qid, "reason": f"題型標籤無法辨識（讀到 {lines[i][:80] if i < len(lines) else '檔案結束'}）。"})
            continue
        qtype = lines[i]
        i += 1
        if i >= len(lines) or not LEVEL_RE.match(lines[i]):
            problems.append({"id": qid, "reason": "難度標籤無法辨識。"})
            continue
        level = lines[i]
        i += 1
        stem_parts: list[str] = []
        choices: dict[str, list[str]] = {}
        current_choice = None
        while i < len(lines):
            nxt = lines[i]
            if matcher.match(nxt):
                break
            if current_choice and is_header(nxt):
                break
            choice_match = re.match(r"^([ABC])\.\s*(.*)$", nxt)
            if choice_match and (current_choice is None or choice_match.group(1) > current_choice):
                current_choice = choice_match.group(1)
                choices[current_choice] = [choice_match.group(2)]
                i += 1
                continue
            if current_choice is None:
                stem_parts.append(nxt)
            else:
                choices[current_choice].append(nxt)
            i += 1
        choice_text = {k: join_wrap(v) for k, v in choices.items()}
        item = {
            "id": qid,
            "origin": "original",
            "topic_idx": topic_idx,
            "subtopic_raw": subtopic,
            "qtype": qtype,
            "level": level,
            "stem": join_wrap(stem_parts),
            "choices": choice_text,
        }
        if set(choice_text) != {"A", "B", "C"} or not item["stem"]:
            problems.append({"id": qid, "reason": "題幹或三個選項沒有完整讀出。", "parsed": item})
        else:
            questions.append(item)
    return questions, problems


NEXT_FIELD = (
    r"Correct answer|Reasoning|Why\s+[ABC]\s+is\s+wrong|中文拆解|Study Book Link|"
    r"Subject|Chapter|Section|Core Idea|Related Formula|Related Exam Trap|"
    r"Given|Asked|Final answer|Interpretation|Formula|Reasonableness check|"
    r"Why this formula|Step-by-step|Variables"
)


def labeled_field(text: str, name: str, keep_lines: bool = False) -> str:
    """Read a labeled answer-book field, including lines wrapped by the PDF.

    Formulas keep their line breaks. Joining a stacked fraction into one line
    would turn a quotient into a product.
    """
    match = re.search(
        rf"{name}\s*[:：]\s*(.+?)(?=\n(?:{NEXT_FIELD})\s*[:：]|\Z)",
        text,
        re.S,
    )
    if not match:
        return ""
    if keep_lines:
        return "\n".join(line.strip() for line in match.group(1).splitlines() if line.strip())
    return tidy(match.group(1))


def parse_solutions(raw: str, code: str, answer_name: str, subject_title: str) -> tuple[dict[str, dict], list[dict]]:
    lines = clean_lines(raw)
    matcher = id_re(code)
    blocks: dict[str, list[str]] = {}
    problems = []
    current = None
    buf: list[str] = []
    for line in lines:
        if matcher.match(line):
            if current:
                if current in blocks:
                    problems.append({"id": current, "reason": "解答本出現重複題號。"})
                blocks[current] = buf
            current = line
            buf = []
            continue
        if current and is_header(line):
            continue
        if current:
            buf.append(line)
    if current:
        blocks[current] = buf

    solutions = {}
    for qid, blines in blocks.items():
        text = "\n".join(blines)
        found = re.search(r"Correct answer\s*[:：]\s*([ABC])\b", text)
        if not found:
            problems.append({"id": qid, "reason": "解答本沒有給出 A/B/C 中的唯一正確答案。"})
            continue
        letter = found.group(1)
        core = labeled_field(text, "Core Idea")
        section = labeled_field(text, "Section")
        formula = labeled_field(text, "Related Formula", keep_lines=True)
        trap = labeled_field(text, "Related Exam Trap")
        final = labeled_field(text, "Final answer")
        zh = re.search(r"中文拆解\s*[:：]\s*(.+?)(?:\nStudy Book Link|\n核心觀念|\Z)", text, re.S)
        steps = re.search(
            r"Step-by-step\s*[:：]\s*(.+?)(?:\nFinal answer\s*[:：]|\nInterpretation\s*[:：]|\nWhy\s+[ABC]\s+is\s+wrong\s*[:：])",
            text,
            re.S,
        )
        interpretation = re.search(
            r"Interpretation\s*[:：]\s*(.+?)(?:\nWhy\s+[ABC]\s+is\s+wrong\s*[:：]|\n中文拆解\s*[:：])",
            text,
            re.S,
        )
        calc = ""
        if "計算機操作" in text:
            calc_match = re.search(
                r"(計算機操作[|｜]BA II Plus.+?)(?:\nWhy\s+[ABC]\s+is\s+wrong\s*[:：]|\n中文拆解\s*[:：])",
                text,
                re.S,
            )
            if calc_match:
                calc = "\n".join(line.rstrip() for line in calc_match.group(1).strip().splitlines())
        why = {}
        why_parts = re.split(r"Why\s+([ABC])\s+is\s+wrong\s*[:：]\s*", text)
        if len(why_parts) > 1:
            for idx in range(1, len(why_parts), 2):
                body = why_parts[idx + 1]
                body = re.split(r"\n(?:中文拆解\s*[:：]|Study Book Link|核心觀念)", body)[0]
                why[why_parts[idx]] = tidy(body)
        reasoning = why_parts[0]
        reasoning = re.sub(r"Correct answer\s*[:：]\s*[ABC]\s*", "", reasoning)
        reasoning = re.split(r"\bStep-by-step\s*[:：]", reasoning)[0]
        reasoning = re.split(r"\bFinal answer\s*[:：]", reasoning)[0]
        reasoning = tidy(reasoning)
        if interpretation:
            extra = tidy(interpretation.group(1))
            if extra and extra not in reasoning:
                reasoning = f"{reasoning} {extra}".strip()
        solutions[qid] = {
            "id": qid,
            "correct": letter,
            "reasoning": reasoning,
            "steps": tidy(steps.group(1)) if steps else "",
            "final_answer": final,
            "why_wrong": why,
            "zh": tidy(zh.group(1)) if zh else "",
            "core_idea": core,
            "study_section": section,
            "formula": formula,
            "exam_trap": trap,
            "calculator": calc,
            "source_note": f"解答依據 {answer_name}；觀念依據講義 {subject_title}。",
        }
    return solutions, problems


def study_index(doc: fitz.Document) -> list[dict]:
    chapters = []
    current = None
    for level, title, page in doc.get_toc():
        if level == 1:
            current = {"title": title, "key": norm_title(title), "page": page, "sections": []}
            chapters.append(current)
        elif level == 2 and current is not None:
            current["sections"].append({"title": title, "key": norm_title(title), "page": page, "subs": []})
        elif level == 3 and current and current["sections"]:
            current["sections"][-1]["subs"].append({"title": title, "key": norm_title(title), "page": page})
    return chapters


def heading_excerpt(doc: fitz.Document, start: int, end: int, title: str) -> str:
    last = min(doc.page_count, max(end - 1, start))
    raw = normalize("\n".join(doc[p].get_text() for p in range(start - 1, last)))
    english = re.split(r"[|｜]", title, maxsplit=1)[0]
    words = [word for word in re.split(r"[^A-Za-z0-9]+", english) if len(word) > 2][:5]
    if len(words) < 2:
        words = [word for word in re.split(r"[^A-Za-z0-9]+", english) if word][:4]
    if not words:
        return ""
    gap = r"(?:\W+(?:of|the|and|a|an|to|for|vs|versus|in|is|on|by)\W+|\W+)"
    pattern = r"(?:^|\n)\s*\d+(?:\.\d+)+\s+" + gap.join(re.escape(word) for word in words)
    match = re.search(pattern, raw, re.I)
    if not match:
        return ""
    line_end = raw.find("\n", match.end())
    start_at = line_end + 1 if line_end >= 0 else match.end()
    body = raw[start_at : start_at + 1600]
    body = re.sub(r"CFA Level I Study Book", " ", body)
    body = re.sub(r"Chapter \d+\.[^\n]{0,80}", " ", body)
    nxt = re.search(r"\n\s*\d+\.\d+\s+[A-Z]", body)
    if nxt and nxt.start() > 40:
        body = body[: nxt.start()]
    return tidy(body.replace("\n", " "))


def opening_points(body: str) -> list[str]:
    parts = re.split(r"(?<=[.?!])\s+(?=[A-Z0-9])", body)
    kept = []
    for part in parts:
        sentence = part.strip(" -|")
        if not (60 <= len(sentence) <= 320):
            continue
        if sentence.lower().startswith(("high yield", "contents", "chapter ")):
            continue
        if "study book" in sentence.lower() or "source-bound" in sentence.lower():
            continue
        if re.match(r"^\d+\.\d+", sentence) or re.match(r"^\d+\.?$", sentence.strip()):
            continue
        if sentence.count("｜") > 2:
            continue
        kept.append(sentence)
        if len(kept) == 3:
            break
    return kept


def formula_lines(body: str) -> list[str]:
    found = []
    for match in re.finditer(r"(?<![A-Za-z])([A-Za-z][A-Za-z0-9_()/]{0,18}\s*=\s*[A-Za-z0-9_().+\-−×/^ ]{1,48})", body):
        piece = tidy(match.group(1)).strip(" ;,")
        words = [word for word in piece.split() if word != "="]
        if len(words) > 8 or len(piece) < 5 or len(piece) > 80:
            continue
        if piece.count("(") != piece.count(")") or piece.count("[") != piece.count("]"):
            continue
        if re.search(r"\b(May|Helps|None|Advertising|Downward)\b", piece):
            continue
        if not any(len(word) <= 12 for word in words):
            continue
        if piece not in found:
            found.append(piece)
        if len(found) == 4:
            break
    return found


def align_study(subject: dict, sections: list[dict], chapters: list[dict], toc_entries: list[tuple]) -> dict[int, dict]:
    if not subject["study_key"]:
        return {}
    chapter = next((item for item in chapters if item["key"] == subject["study_key"]), None)
    if chapter is None:
        return {}
    study_sections = [item for item in chapter["sections"] if "mixed practice" not in item["key"] and "terminology" not in item["key"]]
    targets = []
    for study in study_sections:
        targets.append(study)
        targets.extend(study["subs"])
    aligned = {}
    for section in sections:
        exact = [item for item in targets if item["key"] == section["key"]]
        if exact:
            hit = exact[0]
        else:
            loose = [
                item
                for item in targets
                if min(len(item["key"]), len(section["key"])) > 12
                and (item["key"] in section["key"] or section["key"] in item["key"])
            ]
            if not loose:
                continue
            hit = max(loose, key=lambda item: len(item["key"]))
        later = [page for _key, _title, page, level in toc_entries if page > hit["page"] and level <= 3]
        end = later[0] if later else hit["page"] + 2
        next_title = next((title for _key, title, page, level in toc_entries if page == end and level <= 3), None)
        parent = hit if "subs" in hit else next(study for study in study_sections if any(sub["key"] == hit["key"] for sub in study["subs"]))
        later_chapters = [page for _key, _title, page, level in toc_entries if level == 1 and page > chapter["page"]]
        chapter_end = later_chapters[0] if later_chapters else 999
        aligned[section["num"]] = {
            "page": hit["page"],
            "end": end,
            "chapter_start": chapter["page"],
            "chapter_end": chapter_end,
            "next_title": next_title,
            "title": hit["title"],
            "study_subs": [sub["title"] if isinstance(sub, dict) else sub for sub in parent.get("subs", [])],
        }
    return aligned


def topic_id_for(subject: dict, number: int) -> str:
    if subject["chapter"] is None:
        return f"{subject['code']}.{number}"
    return f"{subject['chapter']}.{number}"


def source_chapter(subject: dict) -> str:
    if subject["chapter"] is None:
        return f"題庫 {subject['title_en']}｜{subject['title_zh']}。這一科不是講義的獨立章，題目使用講義各章已經寫明的關係。"
    return f"講義第 {subject['chapter']} 章 {subject['title_en']}｜{subject['title_zh']}"


def display_subtopic(topic_id: str, raw: str) -> str:
    key = english_key(raw)
    if key in SUBTOPIC_SECTION:
        return SUBTOPIC_SECTION[key]
    cleaned = re.sub(r"^1\.\d{1,2}\s+", "", tidy(raw))
    if cleaned.startswith(topic_id):
        return cleaned
    return f"{topic_id} {cleaned}"


def build_topic_meta(
    subject: dict,
    section: dict,
    doc: fitz.Document,
    aligned: dict[int, dict],
    question_subs: list[str],
) -> dict:
    topic_id = topic_id_for(subject, section["num"])
    title_line = re.sub(r"^1\.\d{1,2}\s+", "", section["title"])
    title_en, _, title_zh = title_line.partition("｜")
    title_en = title_en.strip()
    title_zh = title_zh.strip() or title_en
    objectives: list[str] = []
    formulas: list[str] = []
    study_subs: list[str] = []
    link = aligned.get(section["num"])
    if link and subject["code"] != "QM":
        body = heading_excerpt(doc, link["chapter_start"], link["chapter_end"], link["title"])
        objectives = opening_points(body)
        formulas = formula_lines(body)
        study_subs = [f"{topic_id} {tidy(name)}" for name in link["study_subs"]]
    if subject["code"] == "QM" and topic_id in TOPIC_META:
        base = dict(TOPIC_META[topic_id])
        objectives = list(base["objectives"])
        formulas = list(base["formulas"])
        study_subs = list(base["subtopics"])
        title_en = base["title_en"]
        title_zh = base["title_zh"]
    if not objectives:
        if subject["chapter"] is None:
            objectives = [
                f"本組是{subject['title_zh']}的「{title_en}｜{title_zh}」。",
                "每題仍須回到解答本寫明的講義章節；講義沒有支持的關係就不當作正解。",
            ]
        else:
            objectives = [f"本組對應講義「{title_en}｜{title_zh}」。只使用這一節已經寫明的關係。"]
    if not formulas:
        formulas = ["本節沒有另列需要代入的單一計算式；判斷以講義該節的定義與比較為準。"]
    subs = study_subs or question_subs or [f"{topic_id} {title_en}｜{title_zh}"]
    return {
        "study_section": topic_id,
        "title_en": title_en,
        "title_zh": title_zh,
        "question_section": f"1.{section['num']}",
        "subject_id": subject["code"],
        "subject_en": subject["title_en"],
        "subject_zh": subject["title_zh"],
        "source_chapter": source_chapter(subject),
        "objectives": objectives,
        "formulas": formulas,
        "subtopics": subs,
    }


def copy_sources() -> None:
    SOURCE.mkdir(parents=True, exist_ok=True)
    for path in ROOT.glob("*_VERIFIED_V3_1.pdf"):
        dest = SOURCE / path.name
        if not dest.exists() or dest.stat().st_size != path.stat().st_size:
            shutil.copy2(path, dest)


def main() -> None:
    copy_sources()
    study = fitz.open(SOURCE / "CFA_L1_Study_Book_FINAL_2026.pdf")
    chapters = study_index(study)
    toc_entries = [(norm_title(title), title, page, level) for level, title, page in study.get_toc()]
    old_questions = json.loads((DATA / "questions.json").read_text(encoding="utf-8"))
    old_solutions = json.loads((DATA / "solutions.json").read_text(encoding="utf-8"))
    old_q = {item["id"]: item for item in old_questions}

    all_questions = []
    all_solutions: dict[str, dict] = {}
    topics: dict[str, dict] = {}
    flags: list[dict] = []
    preview = []
    by_subject = []

    for subject in SUBJECTS:
        code = subject["code"]
        q_path = SOURCE / f"{code}_questions_VERIFIED_V3_1.pdf"
        a_path = SOURCE / f"{code}_answers_VERIFIED_V3_1.pdf"
        q_lines = clean_lines(pdf_text(q_path))
        sections, key_to_index = scan_sections(q_lines, code)
        questions, q_problems = parse_questions(pdf_text(q_path), code, sections, key_to_index)
        solutions, a_problems = parse_solutions(pdf_text(a_path), code, a_path.name, subject["title_en"])
        for problem in q_problems + a_problems:
            problem["subject"] = code
            flags.append(problem)
        for question in questions:
            solution = solutions.get(question["id"])
            if question["topic_idx"] is None and solution:
                key = norm_title(solution.get("study_section") or "")
                mapped = section_index_for(key, key_to_index, allow_contains=True)
                if mapped is not None:
                    question["topic_idx"] = mapped
            if question["topic_idx"] is None:
                flags.append({"id": question["id"], "subject": code, "reason": "無法對應到題庫章節，標示待確認。"})
        local_flags = numeric_conflicts(questions, solutions)
        for problem in local_flags:
            problem["subject"] = code
            flags.append(problem)
        aligned = align_study(subject, sections, chapters, toc_entries)
        subs_by_idx: dict[int, list[str]] = {idx: [] for idx in range(len(sections))}
        for question in questions:
            if question["topic_idx"] is None:
                continue
            label = display_subtopic(topic_id_for(subject, sections[question["topic_idx"]]["num"]), question["subtopic_raw"])
            if label not in subs_by_idx[question["topic_idx"]]:
                subs_by_idx[question["topic_idx"]].append(label)
        for section in sections:
            idx = sections.index(section)
            topic_id = topic_id_for(subject, section["num"])
            topics[topic_id] = build_topic_meta(subject, section, study, aligned, subs_by_idx.get(idx, []))
            if section["num"] not in aligned and subject["chapter"] is not None and subject["code"] != "QM":
                flags.append(
                    {
                        "id": topic_id,
                        "subject": code,
                        "reason": f"題庫章節 {section['title']} 沒有對上講義目錄的同名節。仍保留題目，學習目標只用章節名稱。",
                        "severity": "note",
                    }
                )
        chapter_label = source_chapter(subject)
        for question in questions:
            if question["topic_idx"] is None:
                continue
            section = sections[question["topic_idx"]]
            topic_id = topic_id_for(subject, section["num"])
            meta = topics[topic_id]
            subtopic = display_subtopic(topic_id, question["subtopic_raw"])
            all_questions.append(
                {
                    "id": question["id"],
                    "origin": "original",
                    "topic_id": topic_id,
                    "topic_en": meta["title_en"],
                    "topic_zh": meta["title_zh"],
                    "subtopic": subtopic,
                    "subtopic_raw": question["subtopic_raw"],
                    "qtype": question["qtype"],
                    "level": question["level"],
                    "stem": question["stem"],
                    "choices": question["choices"],
                    "source": {
                        "question_pdf": q_path.name,
                        "question_ref": question["id"],
                        "study_pdf": "CFA_L1_Study_Book_FINAL_2026.pdf",
                        "study_chapter": chapter_label,
                        "study_section": subtopic,
                        "answer_pdf": a_path.name,
                    },
                }
            )
            solution = solutions.get(question["id"])
            if not solution:
                continue
            solution["topic_id"] = topic_id
            solution["subtopic"] = subtopic
            solution["core_idea"] = solution["core_idea"] or subtopic
            missing_why = [letter for letter in "ABC" if letter != solution["correct"] and letter not in solution["why_wrong"]]
            if missing_why:
                flags.append(
                    {
                        "id": question["id"],
                        "subject": code,
                        "reason": "解答本沒有分別說明錯誤選項 " + "、".join(missing_why) + "。原題仍保留。",
                        "severity": "note",
                    }
                )
            all_solutions[question["id"]] = solution
        preview.append(f"## {code} sections {len(sections)} questions {len(questions)} solutions {len(solutions)}")
        for section in sections:
            topic_id = topic_id_for(subject, section["num"])
            meta = topics[topic_id]
            count = sum(1 for q in questions if q["topic_idx"] is not None and sections[q["topic_idx"]]["num"] == section["num"])
            preview.append(f"{topic_id} n={count} {meta['title_en']}｜{meta['title_zh']} aligned={section['num'] in aligned or subject['code']=='QM'}")
            for obj in meta["objectives"]:
                preview.append(f"  obj: {obj[:180]}")
            for formula in meta["formulas"][:3]:
                preview.append(f"  fx: {formula[:160]}")
        by_subject.append(
            {
                "code": code,
                "questions": len(questions),
                "solutions": len(solutions),
                "sections": [topic_id_for(subject, section["num"]) for section in sections],
            }
        )

    hard_flags = [flag for flag in flags if flag.get("severity") != "note"]
    hard_ids = {flag["id"] for flag in hard_flags}
    playable = []
    held = []
    kept_questions = []
    for question in all_questions:
        if "correct" in question or "why_wrong" in question:
            raise RuntimeError(question["id"])
        if question["id"] in hard_ids or question["id"] not in all_solutions:
            held.append(question["id"])
            continue
        playable.append(question["id"])
        kept_questions.append(question)
    # Questions that never entered all_questions because topic was missing still need a held id.
    seen = {question["id"] for question in all_questions}
    for subject in SUBJECTS:
        code = subject["code"]
        for flag in hard_flags:
            if flag.get("subject") == code and flag["id"] not in seen and flag["id"] not in held and re.match(rf"^{code}-\d{{3}}$", flag["id"]):
                held.append(flag["id"])

    order = {item["code"]: index for index, item in enumerate(SUBJECTS)}

    def topic_sort(item: tuple[str, dict]) -> tuple:
        topic_id, meta = item
        return (order[meta["subject_id"]], int(topic_id.split(".")[-1]))

    topics = dict(sorted(topics.items(), key=topic_sort))
    kept_questions.sort(key=lambda question: (order[question["id"].split("-")[0]], int(question["id"].split("-")[1])))
    all_questions.sort(key=lambda question: (order[question["id"].split("-")[0]], int(question["id"].split("-")[1])))

    qm_diffs = []
    for qid, old in old_q.items():
        if not qid.startswith("QM-"):
            continue
        new = next((item for item in all_questions if item["id"] == qid), None)
        if new is None:
            qm_diffs.append(f"{qid} missing")
            continue
        if new["topic_id"] != old["topic_id"]:
            qm_diffs.append(f"{qid} topic {old['topic_id']} -> {new['topic_id']}")
        if new["stem"] != old["stem"]:
            qm_diffs.append(f"{qid} stem\n OLD {old['stem'][:240]}\n NEW {new['stem'][:240]}")
        if new["choices"] != old["choices"]:
            qm_diffs.append(f"{qid} choices\n OLD {old['choices']}\n NEW {new['choices']}")
        old_letter = old_solutions[qid]["correct"]
        new_letter = all_solutions.get(qid, {}).get("correct")
        if new_letter != old_letter:
            qm_diffs.append(f"{qid} letter {old_letter} -> {new_letter}")
    (ROOT / "_extract").mkdir(exist_ok=True)
    extract = ROOT / "_extract"
    extract.mkdir(exist_ok=True)
    (extract / "qm_diff.txt").write_text("\n".join(qm_diffs) if qm_diffs else "no qm diffs", encoding="utf-8")
    (ROOT / "_extract" / "topics_preview.txt").write_text("\n".join(preview), encoding="utf-8")

    audit = {
        "question_count": len(all_questions),
        "solution_count": len(all_solutions),
        "playable_original_ids": playable,
        "held_ids": held,
        "flags": flags,
        "by_subject": by_subject,
        "qm_diff_count": len(qm_diffs),
        "note": "待確認題目不進入練習，也不用來產生變化題。",
        "recompute": "選項若三個都是單一數字，已核對解答本最終數值是否只對上它所寫的正確字母。不一致或無法分出唯一接近選項者標示待確認。變化題另外逐題重算。",
    }
    DATA.mkdir(exist_ok=True)
    (DATA / "topics.json").write_text(json.dumps(topics, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA / "questions.json").write_text(json.dumps(kept_questions, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA / "solutions.json").write_text(json.dumps(all_solutions, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"questions {len(all_questions)} kept {len(kept_questions)} solutions {len(all_solutions)} "
        f"playable {len(playable)} held {len(held)} qm_diffs {len(qm_diffs)} topics {len(topics)}"
    )
    for flag in hard_flags[:40]:
        print("HOLD", flag.get("id"), flag.get("reason", "")[:160])


if __name__ == "__main__":
    main()
