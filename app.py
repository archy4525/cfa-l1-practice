"""CFA practice workbench: verified local bank plus a DeepSeek tutor."""

from __future__ import annotations

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
SHORTCUTS = ("換個更白話的例子", "把算式拆更細", "如果條件改變怎麼算")


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
        if st.button("用既有題庫主題建立系列", width="stretch"):
            add_local_series(bank)
        rows = record().get("series", [])
        if rows:
            labels = {row["series_id"]: row["title"] for row in rows}
            current = st.session_state.get("tutor_series_id") or rows[0]["series_id"]
            if current not in labels:
                current = rows[0]["series_id"]
            st.session_state.tutor_series_id = st.selectbox(
                "目前系列",
                list(labels),
                index=list(labels).index(current),
                format_func=lambda key: labels[key],
            )
        st.toggle("混合省流模式", value=True, key="tutor_mixed")
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
        ask_follow(action.get("ask") or "")
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
    left, middle, right = st.columns(3)
    if left.button("下一題（先用本地）", width="stretch"):
        take_next(bank)
    if middle.button("AI 生成 1 題", width="stretch"):
        generate(bank, 1)
    if right.button("AI 一次生成 3 題", width="stretch"):
        generate(bank, 3)


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
    st.divider()
    st.markdown("**針對本題追問**")
    for index, row in enumerate(st.session_state.current_followups):
        st.markdown(f"問：{row['ask']}")
        st.write(row["answer"])
        if st.button("★ 存為重點筆記", key=f"note-follow-{index}"):
            save_note(f"{row['ask']}\n{row['answer']}", selected_series(), "followup")
    for shortcut in SHORTCUTS:
        if st.button(shortcut, key=f"short-{shortcut}"):
            ask_follow(shortcut)
            st.rerun()
    typed = st.text_input("自己的追問", key=f"follow-box-{item.get('item_id')}")
    if st.button("送出追問") and typed.strip():
        ask_follow(typed.strip())
        st.rerun()
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


def ask_follow(ask: str) -> None:
    item = record().get("current_item")
    if not item or not ask:
        return
    clear_error()
    try:
        with st.spinner("助教回覆中"):
            stream = call_chat(
                tutor_engine.followup_messages(item, st.session_state.current_followups, ask),
                stream=True,
            )
            answer = consume_stream(stream).strip()
        if not answer:
            raise TutorError("追問沒有收到文字。")
        st.session_state.current_followups.append({"ask": ask, "answer": answer})
        persist()
    except TutorError as exc:
        show_error(exc, {"kind": "follow", "ask": ask})


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
    if st.button("針對錯題出變形題"):
        variant_from(target, bank)
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
            left, right = st.columns(2)
            if left.button("🔄 出類似變形題", key=f"var-{row['star_id']}"):
                fake = {
                    "history_id": "",
                    "series_id": item.get("series_id"),
                    "los_focus": item.get("los_focus"),
                    "angle": item.get("angle"),
                }
                variant_from(fake, cached_bank())
            if right.button("移除收藏", key=f"drop-{row['star_id']}"):
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


def main() -> None:
    st.set_page_config(page_title="CFA 練習工作台", layout="centered")
    init()
    if not password_gate():
        return
    bank = cached_bank()
    if st.session_state.get("tutor_boot_error"):
        st.warning(st.session_state.tutor_boot_error)
    sidebar(bank)
    st.title("CFA 練習工作台")
    st.caption("既有題庫是依你的教材驗算過的練習。AI 題只在你按下生成時，依選定系列的摘要現做。")
    build, answer, review, library, classic = st.tabs(
        ("系列與出題", "作答", "錯題複習", "收藏與筆記", "驗算題庫")
    )
    with build:
        tab_build(bank)
    with answer:
        tab_answer(bank)
    with review:
        tab_review(bank)
    with library:
        tab_library()
    with classic:
        classic_quiz.render_classic(bank)


if __name__ == "__main__":
    main()
