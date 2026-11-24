"""DeepSeek tutor calls, local-bank matching, and the saved study record.

Question text is produced only at runtime from the user's notes and the
existing local bank. This module does not ship generated items.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RECORD_PATH = ROOT / "cfa_gamebook_data.json"
DEEPSEEK_BASE = "https://api.deepseek.com"
ANGLES = ("基礎觀念", "數值計算與敏感度", "準則/方法比較", "情境判斷", "常見陷阱辨識")
LEVELS = (1, 2, 3, 4, 5)

FIXED_RULES = """你是 CFA Level I 練習助教。只根據這次訊息裡給的系列摘要、重點，以及附上的範例題來出題或講解。
這些練習不是 CFA Institute 官方題，也不表示會出現在官方考試。
選擇題題幹使用英文，語氣接近 Most likely / Least likely。選項必須是 A、B、C、D 四個，而且只有一個正確。
範例只用來對齊語氣、長度和干擾項的寫法。必須更換情境與數字，不可照抄範例。
計算要能從題幹的數字重算。白話解釋用繁體中文。
只回傳要求的 JSON，不要加開場白。數學式用 $...$。"""


class TutorError(Exception):
    """A user-visible failure. The app keeps running."""


def now_stamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def empty_record() -> dict:
    return {
        "series": [],
        "levels": {},
        "recent": [],
        "seen_local": {},
        "pool": [],
        "question_history": [],
        "starred_questions": [],
        "saved_notes": [],
        "tokens": {"prompt": 0, "completion": 0, "total": 0},
    }


def load_record() -> dict:
    if not RECORD_PATH.exists():
        return empty_record()
    try:
        payload = json.loads(RECORD_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TutorError(f"讀不到本地紀錄 {RECORD_PATH.name}：{exc}") from exc
    base = empty_record()
    if isinstance(payload, dict):
        base.update({key: payload.get(key, value) for key, value in base.items()})
    return base


def save_record(record: dict) -> None:
    temporary = RECORD_PATH.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(RECORD_PATH)


def topic_catalog(topics: dict) -> str:
    lines = []
    for topic_id, topic in topics.items():
        lines.append(f"{topic_id} | {topic.get('subject_zh', '')} | {topic.get('title_zh', '')}")
    return "\n".join(lines)


def series_from_topics(topics: dict) -> list[dict]:
    grouped: dict[str, list[tuple[str, dict]]] = {}
    for topic_id, topic in topics.items():
        grouped.setdefault(topic.get("subject_id", "QM"), []).append((topic_id, topic))
    built = []
    for subject_id, items in grouped.items():
        sample = items[0][1]
        points = []
        for _topic_id, topic in items:
            for objective in topic.get("objectives") or []:
                text = str(objective).strip()
                if text and text not in points:
                    points.append(text[:180])
                if len(points) >= 8:
                    break
            if len(points) >= 8:
                break
        built.append(
            {
                "series_id": f"local-{subject_id}",
                "title": f"{sample.get('subject_zh') or subject_id}",
                "summary": f"這個系列對應專案裡已經整理好的{sample.get('subject_zh') or subject_id}題庫。",
                "key_points": points or [sample.get("title_zh") or subject_id],
                "source_excerpt": "",
                "local_topic_ids": [topic_id for topic_id, _topic in items],
                "origin": "local-outline",
            }
        )
    return built


def _words(text: str) -> set[str]:
    return {part.lower() for part in re.findall(r"[A-Za-z]{3,}|[\u4e00-\u9fff]{2,}", text or "")}


def bind_topics(series: dict, topics: dict) -> list[str]:
    hinted = series.get("local_topic_ids") or []
    if isinstance(series.get("local_topic_id"), str):
        hinted = [series["local_topic_id"], *hinted]
    valid = [topic_id for topic_id in hinted if topic_id in topics]
    if valid:
        return valid
    target = _words(" ".join([series.get("title", ""), series.get("summary", ""), " ".join(series.get("key_points") or [])]))
    scored = []
    for topic_id, topic in topics.items():
        hay = _words(f"{topic.get('title_en', '')} {topic.get('title_zh', '')} {topic.get('subject_zh', '')}")
        overlap = len(target & hay)
        if overlap:
            scored.append((overlap, topic_id))
    scored.sort(reverse=True)
    return [topic_id for _score, topic_id in scored[:2]]


def normalize_series(raw: dict, topics: dict) -> dict:
    title = str(raw.get("title") or "").strip()
    if not title:
        raise TutorError("分類結果少了系列名稱。")
    points = raw.get("key_points") or []
    if isinstance(points, str):
        points = [part.strip() for part in points.split("\n") if part.strip()]
    points = [str(point).strip() for point in points if str(point).strip()][:8]
    series = {
        "series_id": str(raw.get("series_id") or new_id("series")),
        "title": title[:80],
        "summary": str(raw.get("summary") or "")[:500],
        "key_points": points,
        "source_excerpt": str(raw.get("source_excerpt") or "")[:600],
        "local_topic_ids": bind_topics(raw, topics),
        "origin": "ai",
    }
    return series


def level_for(record: dict, series_id: str) -> int:
    try:
        level = int(record.get("levels", {}).get(series_id, 1))
    except (TypeError, ValueError):
        level = 1
    return min(5, max(1, level))


def update_level(record: dict, series_id: str, correct: bool) -> int:
    levels = record.setdefault("levels", {})
    streaks = record.setdefault("streaks", {})
    level = level_for(record, series_id)
    streak = int(streaks.get(series_id, 0) or 0)
    if correct:
        streak += 1
        if streak >= 2 and level < 5:
            level += 1
            streak = 0
    else:
        streak = 0
        level = max(1, level - 1)
    levels[series_id] = level
    streaks[series_id] = streak
    return level


def recent_for(record: dict, series_id: str) -> list[dict]:
    rows = [row for row in record.get("recent", []) if row.get("series_id") == series_id]
    return rows[-6:]


def remember(record: dict, series_id: str, angle: str, los_focus: str) -> None:
    record.setdefault("recent", []).append(
        {"series_id": series_id, "angle": str(angle)[:40], "los_focus": str(los_focus)[:80]}
    )
    record["recent"] = record["recent"][-40:]


def next_angle(record: dict, series_id: str) -> str:
    used = [row.get("angle") for row in recent_for(record, series_id)]
    for angle in ANGLES:
        if angle not in used[-3:]:
            return angle
    return ANGLES[len(used) % len(ANGLES)]


def as_rows(payload) -> list:
    if isinstance(payload, dict):
        for key in ("series", "questions", "items", "data"):
            if isinstance(payload.get(key), list):
                return payload[key]
        return [payload]
    if isinstance(payload, list):
        return payload
    raise TutorError("回傳不是題目或系列清單。")


def parse_json_payload(text: str):
    raw = (text or "").strip()
    if not raw:
        raise TutorError("模型沒有回傳內容。")
    fenced = re.search(r"```(?:json)?\s*(.+?)```", raw, re.S | re.I)
    if fenced:
        raw = fenced.group(1).strip()
    start_obj = raw.find("{")
    start_arr = raw.find("[")
    starts = [pos for pos in (start_obj, start_arr) if pos >= 0]
    if not starts:
        raise TutorError("回傳不是 JSON。請再試一次。")
    raw = raw[min(starts) :]
    end_obj = raw.rfind("}")
    end_arr = raw.rfind("]")
    end = max(end_obj, end_arr)
    if end >= 0:
        raw = raw[: end + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TutorError(f"JSON 無法解析：{exc}") from exc


def _as_dict(payload):
    if isinstance(payload, list):
        if not payload:
            raise TutorError("模型回傳了空清單。")
        payload = payload[0]
    if not isinstance(payload, dict):
        raise TutorError("模型回傳的不是一個題目物件。")
    return payload


def normalize_question(raw: dict, series: dict, level: int) -> dict:
    raw = _as_dict(raw)
    options = raw.get("options") or {}
    if isinstance(options, list):
        options = {letter: text for letter, text in zip("ABCD", options)}
    if not isinstance(options, dict):
        raise TutorError("選項格式不對。")
    cleaned = {}
    for letter in "ABCD":
        text = str(options.get(letter) or "").strip()
        if text:
            cleaned[letter] = text
    if set(cleaned) != set("ABCD"):
        raise TutorError("生成題必須有 A、B、C、D 四個選項。")
    correct = str(raw.get("correct_option") or "").strip().upper()[:1]
    if correct not in cleaned:
        raise TutorError("正確選項不在 A 到 D。")
    question = str(raw.get("question") or "").strip()
    if len(question) < 20:
        raise TutorError("題幹太短，已捨棄這次回傳。")
    return {
        "item_id": new_id("ai"),
        "source": "ai",
        "local_id": "",
        "series_id": series["series_id"],
        "series_title": series["title"],
        "level": level,
        "los_focus": str(raw.get("los_focus") or "")[:120],
        "angle": str(raw.get("angle") or next_angle({"recent": []}, ""))[:40],
        "question": question,
        "options": cleaned,
        "correct_option": correct,
        "explanation_plain": str(raw.get("explanation_plain") or "").strip(),
        "explanation_steps": str(raw.get("explanation_steps") or "").strip(),
        "memory_hook": str(raw.get("memory_hook") or "").strip()[:160],
        "parent_history_id": raw.get("parent_history_id") or "",
    }


def local_item(question: dict, solution: dict, series: dict, level: int) -> dict:
    options = {letter: question["choices"][letter] for letter in "ABC" if letter in question["choices"]}
    why = solution.get("why_wrong") or {}
    why_text = "\n".join(f"{letter}. {text}" for letter, text in why.items() if text)
    steps = "\n\n".join(part for part in (solution.get("steps") or "", solution.get("reasoning") or "", why_text) if part)
    return {
        "item_id": new_id("local"),
        "source": "local",
        "local_id": question["id"],
        "series_id": series["series_id"],
        "series_title": series["title"],
        "level": level,
        "los_focus": (solution.get("core_idea") or question.get("subtopic") or "")[:120],
        "angle": question.get("qtype") or "情境判斷",
        "question": question["stem"],
        "options": options,
        "correct_option": solution["correct"],
        "explanation_plain": solution.get("zh") or solution.get("core_idea") or "",
        "explanation_steps": steps,
        "memory_hook": solution.get("core_idea") or "",
        "parent_history_id": "",
    }


def unseen_local(record: dict, series: dict, bank: dict) -> list[dict]:
    seen = set(record.get("seen_local", {}).get(series["series_id"], []))
    topic_ids = set(series.get("local_topic_ids") or [])
    found = []
    for question in bank["questions"].values():
        if topic_ids and question["topic_id"] not in topic_ids:
            continue
        if question["id"] in seen:
            continue
        solution = bank["solutions"].get(question["id"])
        if solution:
            found.append((question, solution))
    return found


def mark_seen(record: dict, series_id: str, local_id: str) -> None:
    if not local_id:
        return
    bucket = record.setdefault("seen_local", {}).setdefault(series_id, [])
    if local_id not in bucket:
        bucket.append(local_id)


def few_shot(series: dict, bank: dict, limit: int = 2) -> str:
    topic_ids = set(series.get("local_topic_ids") or [])
    picked = []
    for question in bank["questions"].values():
        if topic_ids and question["topic_id"] not in topic_ids:
            continue
        solution = bank["solutions"].get(question["id"])
        if not solution:
            continue
        picked.append((question, solution))
        if len(picked) >= limit:
            break
    if not picked:
        return "這個系列沒有可對照的既有例題。"
    blocks = []
    for index, (question, solution) in enumerate(picked, start=1):
        choices = "\n".join(f"{letter}. {question['choices'][letter]}" for letter in "ABC" if letter in question["choices"])
        idea = (solution.get("core_idea") or "")[:180]
        blocks.append(
            f"範例 {index}（只對齊寫法，不可照抄）\n{question['stem'][:700]}\n{choices}\n正確選項：{solution['correct']}\n考點：{idea}"
        )
    return "\n\n".join(blocks)


def series_prefix(series: dict) -> str:
    points = "\n".join(f"- {point}" for point in series.get("key_points") or [])
    excerpt = series.get("source_excerpt") or ""
    return (
        f"系列：{series['title']}\n摘要：{series.get('summary') or '（沒有摘要）'}\n重點：\n{points or '- （沒有另列重點）'}"
        + (f"\n文本片段：{excerpt}" if excerpt else "")
    )


def question_schema_hint(count: int) -> str:
    one = (
        '{"los_focus":"", "angle":"", "question":"", "options":{"A":"", "B":"", "C":"", "D":""}, '
        '"correct_option":"A", "explanation_plain":"", "explanation_steps":"", "memory_hook":""}'
    )
    if count == 1:
        return f"回傳一個 JSON 物件：{one}"
    return f"回傳一個 JSON 陣列，裡面有 {count} 個物件。每個物件是：{one}"


def generation_messages(series: dict, bank: dict, record: dict, count: int, extra: str = "") -> list[dict]:
    level = level_for(record, series["series_id"])
    angle = next_angle(record, series["series_id"])
    avoid = "；".join(f"{row['angle']} / {row['los_focus']}" for row in recent_for(record, series["series_id"])) or "無"
    dynamic = "\n\n".join(
        [
            few_shot(series, bank),
            f"本輪難度 Lv.{level}。優先切入角度：{angle}。",
            f"最近已經用過的角度與考點，請避開：{avoid}",
            extra,
            f"請產生 {count} 題。{question_schema_hint(count)}",
        ]
    )
    return [
        {"role": "system", "content": FIXED_RULES},
        {"role": "user", "content": series_prefix(series)},
        {"role": "assistant", "content": "已記住這個系列，之後只會用這些重點。"},
        {"role": "user", "content": dynamic},
    ]


def classify_messages(text: str, catalog: str) -> list[dict]:
    clipped = text[:18000]
    note = ""
    if len(text) > 18000:
        note = "\n文本較長，這一次只處理前 18000 字。"
    ask = (
        "把下面的教材分成 2 到 6 個學習系列。每個系列用 JSON 物件，欄位為 "
        "series_id、title、summary、key_points、source_excerpt、local_topic_id。"
        "key_points 要是 CFA 考試會考的計算、比較、情境判斷或陷阱，不要只列名詞定義。"
        "local_topic_id 必須從下面的既有主題編號選一個最接近的，對不上就留空字串。\n"
        f"既有主題：\n{catalog}\n\n教材：\n{clipped}{note}\n回傳 JSON 陣列。"
    )
    return [
        {"role": "system", "content": FIXED_RULES},
        {"role": "user", "content": ask},
    ]


def followup_messages(item: dict, followups: list[dict], ask: str) -> list[dict]:
    options = "\n".join(f"{letter}. {text}" for letter, text in item["options"].items())
    stable = (
        f"題目：{item['question']}\n{options}\n"
        f"正確答案：{item['correct_option']}\n"
        f"白話：{item.get('explanation_plain', '')[:400]}\n"
        f"拆解：{item.get('explanation_steps', '')[:700]}"
    )
    prior = followups[-3:]
    prior_text = "\n".join(f"問：{row['ask']}\n答：{row['answer']}" for row in prior) or "（還沒有追問）"
    dynamic = (
        f"本題最近追問：\n{prior_text}\n\n新的追問：{ask}\n"
        "只用繁體中文，直接回答，150 到 250 字。不要重寫整題。"
    )
    return [
        {"role": "system", "content": "你是 CFA Level I 白話助教。只根據這題已給的題幹、選項和詳解回答，不另加題庫外的考點。"},
        {"role": "user", "content": stable},
        {"role": "assistant", "content": "只根據這一題回答。"},
        {"role": "user", "content": dynamic},
    ]


def diagnosis_messages(rows: list[dict]) -> list[dict]:
    compact = []
    for row in rows[:20]:
        compact.append(
            {
                "series": row.get("series_title"),
                "los_focus": row.get("los_focus"),
                "angle": row.get("angle"),
                "chosen": row.get("choice"),
                "correct": row.get("correct_option"),
                "question": str(row.get("question") or "")[:280],
            }
        )
    return [
        {"role": "system", "content": "你是 CFA Level I 白話助教。只根據列出的錯題做盲點整理，不新增這些題沒有的考點。"},
        {
            "role": "user",
            "content": "請用繁體中文寫一份錯題盲點分析，先講共同盲點，再逐題用三到五句說明。\n"
            + json.dumps(compact, ensure_ascii=False),
        },
    ]


def friendly_api_error(exc: Exception) -> str:
    text = str(exc)
    lowered = text.lower()
    if "timeout" in lowered or "timed out" in lowered:
        return "連線逾時。可以按重試。"
    if "api key" in lowered or "authentication" in lowered or "401" in lowered:
        return "API 金鑰被拒絕。請檢查側邊欄或 Streamlit secrets 的 DEEPSEEK_API_KEY。"
    if "connection" in lowered or "proxy" in lowered or "name or service" in lowered:
        return f"網路或 Proxy 連線失敗：{text[:240]}"
    return f"API 呼叫失敗：{text[:400]}"


def client_for(api_key: str):
    if not api_key.strip():
        raise TutorError("還沒有 DeepSeek API 金鑰。")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise TutorError("尚未安裝 openai 套件。請先 pip install -r requirements.txt。") from exc
    return OpenAI(api_key=api_key.strip(), base_url=DEEPSEEK_BASE, timeout=90)


def add_usage(record: dict, usage) -> None:
    if not usage:
        return
    prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion = int(getattr(usage, "completion_tokens", 0) or 0)
    total = int(getattr(usage, "total_tokens", 0) or (prompt + completion))
    bucket = record.setdefault("tokens", {"prompt": 0, "completion": 0, "total": 0})
    bucket["prompt"] = int(bucket.get("prompt", 0)) + prompt
    bucket["completion"] = int(bucket.get("completion", 0)) + completion
    bucket["total"] = int(bucket.get("total", 0)) + total


def chat(api_key: str, model: str, temperature: float, messages: list[dict], record: dict, stream: bool = False):
    client = client_for(api_key)
    kwargs = {"model": model, "messages": messages}
    if model != "deepseek-reasoner":
        kwargs["temperature"] = float(temperature)
    if stream:
        kwargs["stream"] = True
        kwargs["stream_options"] = {"include_usage": True}
    try:
        response = client.chat.completions.create(**kwargs)
    except Exception as first:
        if "stream_options" in kwargs:
            kwargs.pop("stream_options", None)
            try:
                response = client.chat.completions.create(**kwargs)
            except Exception as exc:
                raise TutorError(friendly_api_error(exc)) from exc
        else:
            raise TutorError(friendly_api_error(first)) from first
    if stream:
        return response
    add_usage(record, getattr(response, "usage", None))
    content = response.choices[0].message.content or ""
    return content


def read_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise TutorError("尚未安裝 pypdf，無法讀 PDF。") from exc
    from io import BytesIO

    try:
        reader = PdfReader(BytesIO(data))
        pages = []
        for page in reader.pages[:40]:
            pages.append(page.extract_text() or "")
        return "\n".join(pages)
    except Exception as exc:
        raise TutorError(f"PDF 讀取失敗：{exc}") from exc


def read_upload(name: str, data: bytes) -> str:
    lower = name.lower()
    if lower.endswith(".pdf"):
        return read_pdf(data)
    if lower.endswith((".txt", ".md", ".csv", ".json")):
        for encoding in ("utf-8", "utf-8-sig", "cp950"):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise TutorError(f"{name} 不是 UTF-8 或 Big5 文字。")
    raise TutorError(f"不支援的檔案：{name}")


def history_row(item: dict, choice: str, correct: bool) -> dict:
    return {
        "history_id": new_id("hist"),
        "timestamp": now_stamp(),
        "series_id": item["series_id"],
        "series_title": item["series_title"],
        "level": item["level"],
        "los_focus": item.get("los_focus") or "",
        "angle": item.get("angle") or "",
        "question": item["question"],
        "options": item["options"],
        "choice": choice,
        "correct_option": item["correct_option"],
        "is_correct": correct,
        "explanation_plain": item.get("explanation_plain") or "",
        "explanation_steps": item.get("explanation_steps") or "",
        "memory_hook": item.get("memory_hook") or "",
        "source": item.get("source") or "",
        "local_id": item.get("local_id") or "",
        "mastered_later": False,
        "parent_history_id": item.get("parent_history_id") or "",
        "item_id": item.get("item_id") or "",
    }


def filter_wrongs(record: dict, start: datetime, end: datetime, series_id: str, only_open: bool) -> list[dict]:
    rows = []
    end_mark = end + timedelta(days=1)
    for row in record.get("question_history", []):
        if row.get("is_correct"):
            continue
        if series_id and row.get("series_id") != series_id:
            continue
        if only_open and row.get("mastered_later"):
            continue
        try:
            stamp = datetime.fromisoformat(row["timestamp"])
        except (TypeError, ValueError):
            continue
        if start <= stamp < end_mark:
            rows.append(row)
    return rows


def mark_mastered(record: dict, history_id: str) -> None:
    if not history_id:
        return
    for row in record.get("question_history", []):
        if row.get("history_id") == history_id:
            row["mastered_later"] = True
