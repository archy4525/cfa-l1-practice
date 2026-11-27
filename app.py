"""CFA practice workbench: verified local bank plus a DeepSeek tutor."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import date, datetime, timedelta

import streamlit as st
from dotenv import load_dotenv

import classic_quiz
import quiz_logic
import tutor_engine
from tutor_engine import TutorError

load_dotenv()

TAGS = ("易錯陷阱", "重要觀念", "計算不熟")
SHORTCUTS = ("用白話解釋", "拆解計算與選項", "這題合不合考場口味")


def secret_value(name: str) -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    if value:
        return str(value)
    return os.getenv(name, "") or ""


def init() -> None:
    if "tutor_record" not in st.session_state:
        try:
            st.session_state.tutor_record = tutor_engine.load_record()
        except TutorError as exc:
            st.session_state.tutor_record = tutor_engine.empty_record()
            st.session_state.tutor_boot_error = str(exc)
    st.session_state.setdefault("current_followups", [])
    st.session_state.setdefault("auth_ok", False)
    st.session_state.setdefault("tutor_api_key", "")
    st.session_state.setdefault("tutor_error", "")
    st.session_state.setdefault("tutor_retry", None)
    st.session_state.setdefault("tutor_diagnosis", "")


def record() -> dict:
    return st.session_state.tutor_record


def session_usage() -> dict:
    usage = record().get("tokens") or {}
    if "token_baseline" not in st.session_state:
        st.session_state.token_baseline = {
            "prompt": int(usage.get("prompt", 0)),
            "completion": int(usage.get("completion", 0)),
            "total": int(usage.get("total", 0)),
        }
    base = st.session_state.token_baseline
    return {
        key: max(0, int(usage.get(key, 0)) - int(base.get(key, 0)))
        for key in ("prompt", "completion", "total")
    }


def persist() -> None:
    try:
        tutor_engine.save_record(record())
    except OSError as exc:
        st.warning(f"本地紀錄沒有寫入：{exc}")


def api_key() -> str:
    saved = secret_value("DEEPSEEK_API_KEY")
    return saved or st.session_state.get("tutor_api_key", "")


def selected_series() -> dict | None:
    series_id = st.session_state.get("tutor_series_id")
    for series in record().get("series", []):
        if series["series_id"] == series_id:
            return series
    rows = record().get("series", [])
    return rows[0] if rows else None


def show_error(exc: Exception, retry: dict | None) -> None:
    st.session_state.tutor_error = str(exc)
    st.session_state.tutor_retry = retry


def clear_error() -> None:
    st.session_state.tutor_error = ""
    st.session_state.tutor_retry = None


def settings() -> tuple[str, float]:
    return st.session_state.get("tutor_model", "deepseek-chat"), float(
        st.session_state.get("tutor_temperature", 0.3)
    )


def password_gate() -> bool:
    password = secret_value("APP_PASSWORD")
    if not password:
        return True
    if st.session_state.auth_ok:
        return True
    st.title("CFA 練習工作台")
    st.caption("這個網址設了密碼，避免金鑰額度被公開連結用掉。")
    typed = st.text_input("密碼", type="password")
    if st.button("進入"):
        same_length = len(typed) == len(password)
        if same_length and hmac.compare_digest(typed.encode(), password.encode()):
            st.session_state.auth_ok = True
            st.rerun()
        st.error("密碼不對。")
    return False


def consume_stream(stream) -> str:
    box = st.empty()
    parts: list[str] = []
    usage = None
    try:
        for chunk in stream:
            usage = getattr(chunk, "usage", None) or usage
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            delta = getattr(choices[0].delta, "content", None) or ""
            if delta:
                parts.append(delta)
                box.markdown("".join(parts))
    except Exception as exc:
        raise TutorError(tutor_engine.friendly_api_error(exc)) from exc
    tutor_engine.add_usage(record(), usage)
    return "".join(parts)


def call_chat(messages: list[dict], stream: bool = False):
    model, temperature = settings()
    return tutor_engine.chat(api_key(), model, temperature, messages, record(), stream=stream)


def store_generated(series: dict, payload, parent_history_id: str = "") -> list[dict]:
    level = tutor_engine.level_for(record(), series["series_id"])
    rows = payload if isinstance(payload, list) else [payload]
    made = []
    for raw in rows:
        if isinstance(raw, dict) and parent_history_id:
            raw = {**raw, "parent_history_id": parent_history_id}
        item = tutor_engine.normalize_question(raw, series, level)
        item["angle"] = item.get("angle") or tutor_engine.next_angle(record(), series["series_id"])
        tutor_engine.remember(record(), series["series_id"], item["angle"], item["los_focus"])
        made.append(item)
    record().setdefault("pool", []).extend(made)
    return made


def activate(item: dict) -> None:
    record()["current_item"] = item
    st.session_state.current_followups = []
    st.session_state.tutor_answered = False
    persist()


def sidebar(bank: dict) -> None:
    with st.sidebar:
        st.header("連線")
        st.selectbox("模型", ("deepseek-chat", "deepseek-reasoner"), key="tutor_model")
        st.caption("chat 直接回答，比較快。reasoner 會先逐步推理，比較慢，適合計算。拉桿只影響 chat。")
        st.slider("temperature", 0.0, 1.5, 0.3, 0.1, key="tutor_temperature")
        if not secret_value("DEEPSEEK_API_KEY"):
            st.session_state.tutor_api_key = st.text_input(
                "暫時的 DeepSeek API 金鑰",
                type="password",
                help="只留在這個瀏覽器工作階段，不會寫進紀錄檔。",
            )
        else:
            st.caption("已讀到 DEEPSEEK_API_KEY。")
        usage = session_usage()
        st.caption(
            f"本輪 Token：輸入 {usage.get('prompt', 0)}　輸出 {usage.get('completion', 0)}　合計 {usage.get('total', 0)}"
        )
        st.divider()
        if st.session_state.tutor_error:
            st.error(st.session_state.tutor_error)
            if st.session_state.tutor_retry and st.button("重試剛才的請求", width="stretch"):
                rerun_retry(bank)


def gathered_text() -> tuple[str, int]:
    parts = []
    pasted = (st.session_state.get("tutor_paste") or "").strip()
    if pasted:
        parts.append(pasted)
    for upload in st.session_state.get("tutor_uploads") or []:
        parts.append(tutor_engine.read_upload(upload.name, upload.getvalue()))
    text = "\n\n".join(part for part in parts if part.strip())
    return text, len(text)


def classify(bank: dict) -> None:
    clear_error()
    try:
        text, total = gathered_text()
        if not text.strip():
            raise TutorError("請先貼上教材，或上傳文字、Markdown、PDF。")
        catalog = tutor_engine.topic_catalog(bank["topics"])
        pieces = [text[index : index + 18000] for index in range(0, len(text), 18000)] or [text]
        merged: dict[str, dict] = {}
        for piece in pieces:
            raw = call_chat(tutor_engine.classify_messages(piece, catalog))
            payload = tutor_engine.parse_json_payload(raw)
            rows = tutor_engine.as_rows(payload)
            for row in rows:
                series = tutor_engine.normalize_series(row, bank["topics"])
                merged[series["title"]] = series
        record()["series"] = list(merged.values()) + [
            row for row in record().get("series", []) if row.get("origin") == "local-outline"
        ]
        persist()
        st.success(f"已分成 {len(merged)} 個系列。這次送出 {min(total, 18000 * len(pieces))} / {total} 字。")
    except TutorError as exc:
        show_error(exc, {"kind": "classify"})


def add_local_series(bank: dict) -> None:
    existing = {row["series_id"] for row in record().get("series", [])}
    added = [row for row in tutor_engine.series_from_topics(bank["topics"]) if row["series_id"] not in existing]
    record().setdefault("series", []).extend(added)
    persist()
    st.success(f"已加入 {len(added)} 個既有題庫系列。這一步沒有呼叫 API。")


def rerun_retry(bank: dict) -> None:
    action = st.session_state.tutor_retry or {}
    kind = action.get("kind")
    clear_error()
    if kind == "classify":
        classify(bank)
    elif kind == "generate":
        generate(
            bank,
            int(action.get("count") or 1),
            action.get("extra") or "",
            action.get("parent") or "",
        )
    elif kind == "follow":
        ask_follow(
            action.get("ask") or "",
            action.get("item"),
            bool(action.get("reveal", True)),
            action.get("bucket") or "current_followups",
        )
    elif kind == "audit":
        run_audit(action.get("item") or {})
    elif kind == "diagnosis":
        diagnose(action.get("rows") or [])
    elif kind == "variant":
        variant_from(action.get("row") or {}, bank)


def generate(bank: dict, count: int, extra: str = "", parent_history_id: str = "") -> None:
    clear_error()
    series = selected_series()
    if series is None:
        show_error(TutorError("請先建立並選定一個系列。"), None)
        return
    try:
        with st.spinner("正在出題"):
            raw = call_chat(tutor_engine.generation_messages(series, bank, record(), count, extra))
            payload = tutor_engine.as_rows(tutor_engine.parse_json_payload(raw))
            made = store_generated(series, payload, parent_history_id)
        if made:
            activate(made[0])
        persist()
        st.success(f"已放入 {len(made)} 題。")
    except TutorError as exc:
        show_error(exc, {"kind": "generate", "count": count, "extra": extra, "parent": parent_history_id})


def take_next(bank: dict) -> None:
    series = selected_series()
    if series is None:
        st.warning("請先在側邊欄建立系列。")
        return
    if st.session_state.get("tutor_mixed", True):
        unseen = tutor_engine.unseen_local(record(), series, bank)
        if unseen:
            question, solution = unseen[0]
            item = tutor_engine.local_item(
                question, solution, series, tutor_engine.level_for(record(), series["series_id"])
            )
            tutor_engine.mark_seen(record(), series["series_id"], question["id"])
            tutor_engine.remember(record(), series["series_id"], item["angle"], item["los_focus"])
            activate(item)
            return
    pool = record().get("pool") or []
    same = [item for item in pool if item.get("series_id") == series["series_id"]]
    if same:
        item = same[0]
        record()["pool"] = [row for row in pool if row.get("item_id") != item.get("item_id")]
        activate(item)
        return
    st.info("這個系列的本地未做題和本輪題池都空了。可以產生 AI 新題。")


def save_note(text: str, series: dict | None, kind: str) -> None:
    clean = (text or "").strip()
    if not clean:
        return
    record().setdefault("saved_notes", []).append(
        {
            "note_id": tutor_engine.new_id("note"),
            "series_id": series["series_id"] if series else "",
            "series_title": series["title"] if series else "未分類",
            "text": clean,
            "kind": kind,
            "created": tutor_engine.now_stamp(),
        }
    )
    persist()
    st.toast("已存入重點筆記")


def star_current(item: dict, tag: str, note: str) -> None:
    record().setdefault("starred_questions", []).append(
        {
            "star_id": tutor_engine.new_id("star"),
            "created": tutor_engine.now_stamp(),
            "tag": tag,
            "note": note.strip(),
            "item": item,
        }
    )
    persist()
    st.toast("已收藏這題")


def tab_build(bank: dict) -> None:
    series = selected_series()
    st.subheader("系列與出題")
    st.caption("練習由你的教材和既有題庫生成，不是 CFA Institute 官方題。")
    rows = record().get("series", [])
    if not rows:
        st.info("側邊欄可以按「用既有題庫主題建立系列」。這一步不會花 Token。")
    current_id = series["series_id"] if series else ""
    for row in rows:
        with st.expander(row["title"], expanded=row["series_id"] == current_id):
            st.write(row.get("summary") or "")
            for point in row.get("key_points") or []:
                st.markdown(f"- {point}")
            if st.button("把這個系列的重點存進筆記", key=f"keep-{row['series_id']}"):
                text = row["title"] + "\n" + "\n".join(row.get("key_points") or [])
                save_note(text, row, "series")
    if series is None:
        return
    level = tutor_engine.level_for(record(), series["series_id"])
    unseen = len(tutor_engine.unseen_local(record(), series, bank))
    pooled = sum(1 for item in record().get("pool", []) if item.get("series_id") == series["series_id"])
    st.write(f"目前主線：{series['title']}　Lv.{level}　本地未做 {unseen} 題　題池 {pooled} 題")
    if st.button("下一題（先用本地）", width="stretch"):
        take_next(bank)


def render_item(item: dict) -> None:
    st.markdown(item["question"])
    for letter, text in item["options"].items():
        st.markdown(f"**{letter}.** {text}")


def tab_answer(bank: dict) -> None:
    st.subheader("作答")
    item = record().get("current_item")
    if not item:
        st.info("到「系列與出題」取下一題，或生成新題。")
        if st.button("取下一題"):
            take_next(bank)
        return
    st.caption(
        f"{item.get('series_title', '')}　Lv.{item.get('level', 1)}　"
        f"{item.get('los_focus') or '未標考點'}　{item.get('angle') or ''}"
    )
    render_item(item)
    if item.get("source") == "local":
        st.caption("這一題來自已驗算的本地題庫，選項維持原本的 A/B/C。")
    answered = st.session_state.get("tutor_answered") and st.session_state.get("tutor_answer_for") == item.get("item_id")
    if not answered:
        choice = st.radio("選項", list(item["options"]), key=f"pick-{item.get('item_id')}")
        if st.button("提交答案"):
            grade(item, choice)
            st.rerun()
        render_question_chat(item, reveal_answer=False, bucket="current_followups")
        return
    correct = st.session_state.get("tutor_last_correct")
    st.success("答對了。") if correct else st.error(
        f"答錯了。正確選項是 {item['correct_option']}。"
    )
    st.markdown("**白話講邏輯**")
    st.write(item.get("explanation_plain") or "這題沒有另外的白話說明。")
    st.markdown("**逐步拆解與選項陷阱**")
    st.write(item.get("explanation_steps") or "")
    st.markdown("**一句話記憶重點**")
    st.write(item.get("memory_hook") or "")
    if st.button("★ 存為重點筆記", key="note-explain"):
        blob = "\n".join(
            [
                item.get("explanation_plain") or "",
                item.get("explanation_steps") or "",
                item.get("memory_hook") or "",
            ]
        )
        save_note(blob, selected_series(), "explanation")
    tag = st.selectbox("收藏標籤", TAGS, key="star-tag")
    note = st.text_input("短備註", key="star-note")
    if st.button("⭐ 收藏這題"):
        star_current(item, tag, note)
    render_question_chat(item, reveal_answer=True, bucket="current_followups")
    if st.button("下一題"):
        take_next(bank)
        st.rerun()


def grade(item: dict, choice: str) -> None:
    correct = choice == item["correct_option"]
    row = tutor_engine.history_row(item, choice, correct)
    record().setdefault("question_history", []).append(row)
    tutor_engine.update_level(record(), item["series_id"], correct)
    if correct and item.get("parent_history_id"):
        tutor_engine.mark_mastered(record(), item["parent_history_id"])
    st.session_state.tutor_answered = True
    st.session_state.tutor_answer_for = item.get("item_id")
    st.session_state.tutor_last_correct = correct
    persist()


def render_question_chat(item: dict, reveal_answer: bool, bucket: str) -> None:
    history = st.session_state.setdefault(bucket, [])
    st.divider()
    st.markdown("**問 DeepSeek 這題**")
    st.caption("在對話框打字，問這一題哪裡不懂。回覆用繁體中文。")
    if not api_key():
        st.info("側邊欄先填 DeepSeek API 金鑰，對話框才會回覆。")
    for index, row in enumerate(history):
        st.markdown(f"**你：** {row['ask']}")
        st.write(row["answer"])
        if st.button("★ 存為重點筆記", key=f"note-{bucket}-{index}"):
            save_note(
                f"{row['ask']}\n{row['answer']}",
                {"series_id": item.get("series_id") or "", "title": item.get("series_title") or "未分類"},
                "followup",
            )
    columns = st.columns(3)
    for column, shortcut in zip(columns, SHORTCUTS):
        if column.button(shortcut, key=f"short-{bucket}-{shortcut}"):
            ask_follow(shortcut, item, reveal_answer, bucket)
            st.rerun()
    nonce = st.session_state.get(f"{bucket}-nonce", 0)
    typed = st.text_area(
        "對話框",
        placeholder="例如：為什麼不能選 A？這一步的公式怎麼來的？",
        key=f"chat-{bucket}-{nonce}",
        height=90,
    )
    if st.button("送出", key=f"send-{bucket}") and typed.strip():
        ask_follow(typed.strip(), item, reveal_answer, bucket)
        if not st.session_state.tutor_error:
            st.session_state[f"{bucket}-nonce"] = nonce + 1
        st.rerun()


def ask_follow(ask: str, item: dict | None = None, reveal_answer: bool = True, bucket: str = "current_followups") -> None:
    item = item or record().get("current_item")
    if not item or not ask:
        return
    history = st.session_state.setdefault(bucket, [])
    clear_error()
    try:
        with st.spinner("助教回覆中"):
            stream = call_chat(
                tutor_engine.followup_messages(item, history, ask, reveal_answer),
                stream=True,
            )
            answer = consume_stream(stream).strip()
        if not answer:
            raise TutorError("追問沒有收到文字。")
        history.append({"ask": ask, "answer": answer})
        persist()
    except TutorError as exc:
        show_error(
            exc,
            {"kind": "follow", "ask": ask, "reveal": reveal_answer, "bucket": bucket, "item": item},
        )


def wrong_rows() -> list[dict]:
    preset = st.session_state.get("review_span", "過去 7 天")
    today = date.today()
    if preset == "過去 14 天":
        start = datetime.combine(today - timedelta(days=14), datetime.min.time())
    elif preset == "自訂":
        start = datetime.combine(st.session_state.get("review_start") or today, datetime.min.time())
        today = st.session_state.get("review_end") or today
    else:
        start = datetime.combine(today - timedelta(days=7), datetime.min.time())
    end = datetime.combine(today, datetime.min.time())
    series = selected_series()
    series_id = series["series_id"] if series and st.session_state.get("review_this_series") else ""
    return tutor_engine.filter_wrongs(
        record(), start, end, series_id, bool(st.session_state.get("review_open", True))
    )


def tab_review(bank: dict) -> None:
    st.subheader("錯題複習")
    st.selectbox("時段", ("過去 7 天", "過去 14 天", "自訂"), key="review_span")
    if st.session_state.review_span == "自訂":
        left, right = st.columns(2)
        left.date_input("開始", value=date.today() - timedelta(days=7), key="review_start")
        right.date_input("結束", value=date.today(), key="review_end")
    st.checkbox("只看目前系列", key="review_this_series")
    st.checkbox("只看尚未攻克", value=True, key="review_open")
    rows = wrong_rows()
    st.write(f"篩出 {len(rows)} 題錯題。")
    if not rows:
        return
    labels = {
        row["history_id"]: f"{row['timestamp'][:16]}　{row.get('series_title', '')}　{row.get('los_focus') or row['question'][:40]}"
        for row in rows
    }
    chosen = st.selectbox("挑一題出變形題", list(labels), format_func=lambda key: labels[key])
    target = next(row for row in rows if row["history_id"] == chosen)
    if st.button("時段錯題白話總診斷"):
        diagnose(rows)
    if st.session_state.tutor_diagnosis:
        st.markdown(st.session_state.tutor_diagnosis)
        if st.button("把這份診斷存入重點筆記"):
            save_note(st.session_state.tutor_diagnosis, selected_series(), "diagnosis")


def variant_from(row: dict, bank: dict) -> None:
    clear_error()
    series = next((item for item in record().get("series", []) if item["series_id"] == row.get("series_id")), None)
    series = series or selected_series()
    if series is None:
        show_error(TutorError("找不到這題所屬系列。"), None)
        return
    extra = (
        f"請針對這個考點出一題變形題：{row.get('los_focus') or ''}。"
        f"要保留的陷阱類型：{row.get('angle') or ''}。"
        "情境和數字都必須換成新的，不可沿用舊題幹。"
    )
    try:
        with st.spinner("正在出變形題"):
            raw = call_chat(tutor_engine.generation_messages(series, bank, record(), 1, extra))
            payload = tutor_engine.as_rows(tutor_engine.parse_json_payload(raw))
            made = store_generated(series, payload, row.get("history_id") or "")
        if made:
            activate(made[0])
            st.success("變形題已放進作答區。答對後，原本那題會標成已攻克。")
    except TutorError as exc:
        show_error(exc, {"kind": "variant", "row": row})


def diagnose(rows: list[dict]) -> None:
    clear_error()
    if not rows:
        return
    try:
        with st.spinner("正在整理錯題"):
            raw = call_chat(tutor_engine.diagnosis_messages(rows))
        note = f"這次送出 {min(len(rows), 20)} / {len(rows)} 題。\n\n{raw}"
        st.session_state.tutor_diagnosis = note
        persist()
    except TutorError as exc:
        show_error(exc, {"kind": "diagnosis", "rows": rows[:20]})


def tab_library() -> None:
    st.subheader("收藏、筆記與紀錄")
    stars = record().get("starred_questions", [])
    tag = st.selectbox("收藏篩選", ("全部", *TAGS), key="star-filter")
    shown = [row for row in stars if tag == "全部" or row.get("tag") == tag]
    for row in shown:
        item = row.get("item") or {}
        with st.container(border=True):
            st.markdown(f"**{row.get('tag') or '未標籤'}**　{item.get('series_title', '')}")
            if row.get("note"):
                st.caption(row["note"])
            st.write(item.get("question") or "")
            st.caption(f"答案 {item.get('correct_option', '')}　{item.get('memory_hook') or ''}")
            if st.button("移除收藏", key=f"drop-{row['star_id']}"):
                record()["starred_questions"] = [
                    kept for kept in stars if kept.get("star_id") != row["star_id"]
                ]
                persist()
                st.rerun()
    st.divider()
    st.markdown("**重點筆記**")
    titles = ["全部"] + sorted({row.get("series_title") or "未分類" for row in record().get("saved_notes", [])})
    pick = st.selectbox("依系列看筆記", titles, key="note-filter")
    visible = [
        row for row in record().get("saved_notes", []) if pick == "全部" or row.get("series_title") == pick
    ]
    for row in visible:
        st.markdown(f"*{row.get('series_title')} · {row.get('kind')}*")
        st.write(row.get("text") or "")
    draft = st.text_area("手動新增筆記")
    if st.button("加入筆記") and draft.strip():
        save_note(draft, selected_series(), "manual")
    markdown = "\n\n".join(
        f"## {row.get('series_title')}\n\n{row.get('text')}" for row in record().get("saved_notes", [])
    )
    left, right = st.columns(2)
    left.download_button("匯出筆記 Markdown", markdown or "（尚無筆記）", file_name="cfa-notes.md")
    payload = json.dumps(record(), ensure_ascii=False, indent=2)
    right.download_button("匯出完整紀錄 JSON", payload, file_name="cfa_gamebook_data.json", mime="application/json")
    st.caption(f"作答紀錄 {len(record().get('question_history', []))} 筆。本地檔會寫入 cfa_gamebook_data.json。")
    uploaded = st.file_uploader("匯入完整紀錄 JSON", type=["json"], key="import-record")
    confirm = st.checkbox("我確定要用這份檔案覆蓋目前紀錄")
    if uploaded and confirm and st.button("覆蓋匯入"):
        try:
            incoming = json.loads(uploaded.getvalue().decode("utf-8"))
            if not isinstance(incoming, dict):
                raise TutorError("這份 JSON 不是紀錄物件。")
            fresh = tutor_engine.empty_record()
            fresh.update({key: incoming.get(key, value) for key, value in fresh.items()})
            st.session_state.tutor_record = fresh
            st.session_state.token_baseline = {
                "prompt": int(fresh.get("tokens", {}).get("prompt", 0)),
                "completion": int(fresh.get("tokens", {}).get("completion", 0)),
                "total": int(fresh.get("tokens", {}).get("total", 0)),
            }
            persist()
            st.success("已覆蓋目前紀錄。")
        except (UnicodeDecodeError, json.JSONDecodeError, TutorError) as exc:
            st.error(f"匯入失敗：{exc}")


@st.cache_resource
def cached_bank() -> dict:
    return quiz_logic.load_bank()


def review_context(audit: dict) -> str:
    return "\n".join(
        part
        for part in (
            audit.get("verdict") or "",
            audit.get("los_assessment") or "",
            audit.get("option_review") or "",
            audit.get("study_note") or "",
        )
        if part
    )


def show_audit(audit: dict) -> None:
    verdict = audit.get("verdict") or ""
    if verdict.startswith("高度"):
        st.success(verdict)
    elif verdict.startswith("部分"):
        st.warning(verdict)
    else:
        st.error(verdict)
    st.markdown("**考點與題型評估**")
    st.write(audit.get("los_assessment") or "")
    st.markdown("**選項與陷阱檢視**")
    st.write(audit.get("option_review") or "")
    st.markdown("**學習／改寫提醒**")
    st.write(audit.get("study_note") or "")
    st.caption("這是問法風格的比對，不是 CFA Institute 的官方判定。")


def run_audit(item: dict) -> None:
    if not item or not item.get("question"):
        show_error(TutorError("請先選定或貼上一題。"), None)
        return
    clear_error()
    try:
        with st.spinner("正在審核這一題"):
            raw = call_chat(tutor_engine.audit_messages(item))
            audit = tutor_engine.normalize_audit(tutor_engine.parse_json_payload(raw))
        st.session_state.setdefault("bench_reviews", {})[item["item_id"]] = audit
        persist()
    except TutorError as exc:
        show_error(exc, {"kind": "audit", "item": item})


def pasted_item() -> dict | None:
    stem = st.text_area("題幹", key="bench_stem", height=140)
    letters = {}
    for letter in "ABCD":
        text = st.text_input(f"選項 {letter}", key=f"bench_opt_{letter}").strip()
        if text:
            letters[letter] = text
    available = list(letters) or ["A"]
    correct = st.selectbox("參考答案", available, key="bench_correct")
    explanation = st.text_area("參考解析", key="bench_explain", height=100)
    if not stem.strip() or len(letters) < 2:
        return None
    if correct not in letters:
        correct = next(iter(letters))
    digest = hashlib.sha1(f"{stem}|{correct}|{explanation}".encode("utf-8")).hexdigest()[:10]
    return {
        "item_id": f"paste-{digest}",
        "question": stem.strip(),
        "options": letters,
        "correct_option": correct,
        "explanation_plain": explanation.strip(),
        "explanation_steps": "",
        "series_id": "paste",
        "series_title": "貼上的題目",
    }


def show_topic_intro(bank: dict, topic_id: str, pool: list[dict]) -> None:
    info = quiz_logic.briefing(bank, topic_id, pool)
    with st.expander(
        f"本系列學習目標：{info['topic_id']} {info['title_en']}｜{info['title_zh']}",
        expanded=True,
    ):
        st.markdown("**本組子主題**")
        for subtopic in info["subtopics"]:
            st.markdown(f"- {subtopic}")
        st.markdown("**本組學習目標**")
        for objective in info["objectives"]:
            st.markdown(f"- {objective}")
        st.markdown("**會用到的公式或觀念**")
        for formula in info["formulas"]:
            st.markdown(f"- {formula}")
        level_text = "、".join(f"{name} {count} 題" for name, count in info["levels"].items())
        type_text = "、".join(f"{name} {count} 題" for name, count in info["types"].items())
        st.markdown(f"**題數** {info['count']}　**難度** {level_text}　**題型** {type_text}")
        st.markdown(
            f"**來源** {info['source_chapter']}；題庫章節 {info['question_section']}。"
            "變化題使用同一章的觀念，數字與問法已更換。"
        )


def bank_choice_item(bank: dict) -> dict | None:
    subjects = classic_quiz.subject_ids(bank)
    subject_id = st.selectbox(
        "科目",
        subjects,
        format_func=lambda key: classic_quiz.subject_label(bank, key),
        key="bench_subject",
    )
    topic_ids = classic_quiz.topics_in(bank, subject_id)
    topic_id = st.selectbox(
        "主題",
        topic_ids,
        format_func=lambda key: classic_quiz.topic_label(bank, key),
        key=f"bench-topic-{subject_id}",
    )
    pool = [question for question in bank["questions"].values() if question["topic_id"] == topic_id]
    pool.sort(key=lambda question: question["id"])
    if not pool:
        st.info("這個主題沒有題目。")
        return None
    if st.session_state.get("bench_last_topic") != topic_id:
        st.session_state.bench_last_topic = topic_id
        st.session_state[f"bench_ready_{topic_id}"] = False
    show_topic_intro(bank, topic_id, pool)
    if not st.session_state.get(f"bench_ready_{topic_id}"):
        if st.button("開始作答", type="primary", key=f"bench-start-{topic_id}"):
            st.session_state[f"bench_ready_{topic_id}"] = True
            st.rerun()
        st.caption("先看完上面的學習目標，再按開始作答。")
        return None
    ids = [question["id"] for question in pool]
    if st.session_state.get("bench_jump") in ids:
        st.session_state.bench_qid = st.session_state.pop("bench_jump")
    elif st.session_state.get("bench_qid") not in ids:
        st.session_state.bench_qid = ids[0]
    qid = st.selectbox(
        "題目",
        ids,
        format_func=lambda key: f"{key}　{bank['questions'][key]['stem'][:42]}",
        key="bench_qid",
    )
    position = ids.index(qid)
    previous, nxt, again = st.columns(3)
    if previous.button("上一題", disabled=position == 0, width="stretch"):
        st.session_state.bench_jump = ids[position - 1]
        st.rerun()
    if nxt.button("下一題", disabled=position + 1 >= len(ids), width="stretch"):
        st.session_state.bench_jump = ids[position + 1]
        st.rerun()
    if again.button("再看學習目標", width="stretch"):
        st.session_state[f"bench_ready_{topic_id}"] = False
        st.rerun()
    question = bank["questions"][qid]
    solution = bank["solutions"].get(qid) or {}
    why = solution.get("why_wrong") or {}
    why_text = "\n".join(f"{letter}. {text}" for letter, text in why.items() if text)
    steps = "\n\n".join(
        part for part in (solution.get("steps") or "", solution.get("reasoning") or "", why_text) if part
    )
    return {
        "item_id": qid,
        "question": question["stem"],
        "options": {letter: question["choices"][letter] for letter in "ABCD" if letter in question["choices"]},
        "correct_option": solution.get("correct") or "",
        "explanation_plain": solution.get("zh") or solution.get("core_idea") or "",
        "explanation_steps": steps,
        "series_id": question.get("topic_id") or "",
        "series_title": question.get("topic_zh") or question.get("topic_en") or "",
    }


def tab_workbench(bank: dict) -> None:
    st.subheader("刷題與審題")
    st.caption("這裡只使用題庫裡的題，或你貼上的題。不會自動另出新題。")
    mode = st.radio("題目來源", ("從題庫選", "貼上一題"), horizontal=True, key="bench_mode")
    item = bank_choice_item(bank) if mode == "從題庫選" else pasted_item()
    if item is None:
        if mode == "貼上一題":
            st.info("貼上題幹和至少兩個選項後，就可以作答、審核和提問。")
        return
    if st.session_state.get("bench_for") != item["item_id"]:
        st.session_state.bench_for = item["item_id"]
        st.session_state.bench_followups = []
    st.markdown(item["question"])
    for letter, text in item["options"].items():
        st.markdown(f"**{letter}.** {text}")
    if not item["correct_option"]:
        st.warning("這一題沒有參考答案，仍可審核和提問。")
    else:
        picked = st.radio("我的答案", list(item["options"]), key=f"bench-pick-{item['item_id']}")
        if st.button("顯示／比對參考答案"):
            st.session_state[f"bench-show-{item['item_id']}"] = True
        if st.session_state.get(f"bench-show-{item['item_id']}"):
            correct = item["correct_option"]
            if picked == correct:
                st.success(f"和參考答案一致：{correct}")
            else:
                st.error(f"你選了 {picked}。參考答案是 {correct}。")
            if item.get("explanation_plain"):
                st.write(item["explanation_plain"])
            if item.get("explanation_steps"):
                st.write(item["explanation_steps"])
    if st.button("🔍 審核這題是否符合 CFA 真題"):
        run_audit(item)
    audit = st.session_state.get("bench_reviews", {}).get(item["item_id"])
    if audit:
        show_audit(audit)
        item = {**item, "review_text": review_context(audit)}
    render_question_chat(item, reveal_answer=True, bucket="bench_followups")


def main() -> None:
    st.set_page_config(page_title="CFA 刷題與審題", layout="centered")
    init()
    if not password_gate():
        return
    bank = cached_bank()
    if st.session_state.get("tutor_boot_error"):
        st.warning(st.session_state.tutor_boot_error)
    sidebar(bank)
    st.title("CFA 刷題與審題")
    st.caption("題目來自已整理的題庫，或你這次貼上的內容。DeepSeek 只在你按審核或提問時才會呼叫。")
    workbench, classic, library = st.tabs(("刷題與審題", "驗算題庫", "收藏與筆記"))
    with workbench:
        tab_workbench(bank)
    with classic:
        classic_quiz.render_classic(bank)
    with library:
        tab_library()


if __name__ == "__main__":
    main()
