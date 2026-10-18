"""CFA Level I practice, built only from this project's files."""

from __future__ import annotations

import random

import streamlit as st

import quiz_logic

DISCLAIMER = (
    "這是依據使用者提供資料編寫的 CFA Level I 練習。"
    "資料不是 CFA Institute 官方出版物，題目不是官方原題，也不表示一定會出現在官方考試中。"
    "檔名雖含 2026，正文沒有標示適用的考試年度。"
)

MODE_LABELS = {
    "原題": "original",
    "已驗算變化題": "variant",
    "原題與變化題混合": "mixed",
}


def init_state() -> None:
    defaults = {
        "phase": "select",
        "topic_id": "2.1",
        "mode_label": "已驗算變化題",
        "count": 5,
        "quiz_ids": [],
        "index": 0,
        "results": [],
        "seed": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_to_start() -> None:
    st.session_state.phase = "select"
    st.session_state.quiz_ids = []
    st.session_state.results = []
    st.session_state.index = 0


def current_question(bank: dict) -> dict:
    qid = st.session_state.quiz_ids[st.session_state.index]
    return bank["questions"][qid]


def plain(text: str) -> str:
    # Streamlit treats $...$ as math. Money amounts must stay literal.
    return (text or "").replace("$", r"\$")


def md(text: str) -> None:
    st.markdown(plain(text))


def subject_ids(bank: dict) -> list[str]:
    found = []
    for topic in bank["topics"].values():
        subject_id = topic.get("subject_id", "QM")
        if subject_id not in found:
            found.append(subject_id)
    return found


def subject_label(bank: dict, subject_id: str) -> str:
    topic = next(item for item in bank["topics"].values() if item.get("subject_id", "QM") == subject_id)
    return f"{topic.get('subject_en', subject_id)}｜{topic.get('subject_zh', '')}"


def topics_in(bank: dict, subject_id: str) -> list[str]:
    return [topic_id for topic_id, topic in bank["topics"].items() if topic.get("subject_id", "QM") == subject_id]


def topic_label(bank: dict, topic_id: str) -> str:
    topic = bank["topics"][topic_id]
    return f"{topic_id} {topic['title_en']}｜{topic['title_zh']}"


def show_disclaimer() -> None:
    st.caption(DISCLAIMER)


def inject_style() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@430;600;700&family=Fraunces:opsz,wght@9..144,560;9..144,680&display=swap');
        html, body, [class*="css"] {
          font-family: "Source Sans 3", "Segoe UI", sans-serif;
        }
        h1, h2, h3, .brand-title {
          font-family: Fraunces, Georgia, serif;
          letter-spacing: -0.03em;
        }
        .block-container {
          padding-top: 1.4rem;
          max-width: 760px;
        }
        [data-testid="stHorizontalBlock"] {
          align-items: stretch;
          flex-wrap: wrap;
        }
        [data-testid="stColumn"] {
          min-width: 0 !important;
        }
        .brand {
          display: flex;
          gap: 0.85rem;
          align-items: center;
          margin-bottom: 0.2rem;
        }
        .mark {
          width: 3rem;
          height: 3rem;
          border-radius: 0.9rem;
          display: grid;
          place-items: center;
          background: #14352c;
          color: #f6f1e7;
          font-family: Fraunces, Georgia, serif;
          font-weight: 680;
          font-size: 1.15rem;
        }
        .brand-title {
          font-size: 1.85rem;
          line-height: 1.1;
          color: #1d1a16;
        }
        .brand-sub {
          color: #6d6458;
          font-size: 0.95rem;
          margin-top: 0.15rem;
        }
        div[data-testid="stButton"] > button {
          border-radius: 0.9rem;
          min-height: 2.8rem;
          border: 1px solid #ddd3c2;
          font-weight: 650;
          white-space: normal;
          line-height: 1.3;
        }
        div[data-testid="stButton"] > button[kind="primary"] {
          border-color: #0f6e56;
        }
        [data-testid="stMain"] div[data-testid="stRadio"] div[role="radiogroup"] > label {
          background: #fffdf8;
          border: 1px solid #e4dccb;
          border-radius: 0.95rem;
          padding: 0.8rem 0.95rem;
          margin: 0.35rem 0;
        }
        [data-testid="stMain"] div[data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked) {
          border-color: #0f6e56;
          background: #e7f3ee;
          box-shadow: inset 0 0 0 1px #0f6e56;
        }
        .pips {
          display: flex;
          gap: 0.4rem;
          margin: 0.2rem 0 0.8rem;
        }
        .pip {
          height: 0.55rem;
          flex: 1;
          border-radius: 999px;
          background: #e4dccb;
        }
        .pip.now { background: #1d1a16; }
        .pip.ok { background: #0f6e56; }
        .pip.bad { background: #a33b32; }
        section[data-testid="stSidebar"] {
          border-right: 1px solid #e4dccb;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def show_brand() -> None:
    st.markdown(
        """
        <div class="brand">
          <div class="mark">L1</div>
          <div>
            <div class="brand-title">CFA Level I 練習</div>
            <div class="brand-sub">挑一個科目，組成一小組來做。</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def subject_question_count(bank: dict, subject_id: str) -> int:
    topic_ids = set(topics_in(bank, subject_id))
    return sum(1 for question in bank["questions"].values() if question["topic_id"] in topic_ids)


def show_pips() -> None:
    total = len(st.session_state.quiz_ids)
    if not total:
        return
    results = st.session_state.results
    index = st.session_state.index
    phase = st.session_state.phase
    bits = []
    for step in range(total):
        if step < len(results):
            kind = "ok" if results[step]["is_correct"] else "bad"
        elif step == index and phase != "done":
            kind = "now"
        else:
            kind = "wait"
        bits.append(f'<span class="pip {kind}"></span>')
    st.markdown(f'<div class="pips">{"".join(bits)}</div>', unsafe_allow_html=True)


def show_run_status() -> None:
    total = len(st.session_state.quiz_ids)
    if st.session_state.phase == "select" or not total:
        return
    correct = sum(1 for item in st.session_state.results if item["is_correct"])
    answered = len(st.session_state.results)
    st.sidebar.caption(f"本組 {answered} / {total} 題已作答")
    st.sidebar.caption(f"目前答對 {correct} 題")


def show_briefing(bank: dict) -> None:
    quiz = [bank["questions"][qid] for qid in st.session_state.quiz_ids]
    info = quiz_logic.briefing(bank, st.session_state.topic_id, quiz)
    show_pips()
    st.subheader(f"{info['topic_id']} {info['title_en']}｜{info['title_zh']}")
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
    st.markdown(
        f"**題數** {info['count']}　**難度** {level_text}　**題型** {type_text}"
    )
    st.markdown(
        f"**來源** {info['source_chapter']}；題庫章節 {info['question_section']}。"
        "變化題使用同一章的觀念，數字與問法已更換。"
    )
    if st.button("開始作答", type="primary"):
        st.session_state.phase = "ask"
        st.rerun()


def show_question(bank: dict) -> None:
    question = current_question(bank)
    total = len(st.session_state.quiz_ids)
    show_pips()
    st.markdown(f"第 {st.session_state.index + 1} / {total} 題　{question['qtype']}　{question['level']}")
    st.markdown(f"**{question['subtopic']}**")
    with st.container(border=True):
        md(question["stem"])
    choice = st.radio(
        "選擇一個答案",
        ["A", "B", "C"],
        format_func=lambda letter: f"{letter}. {question['choices'][letter]}",
        key=f"choice-{question['id']}-{st.session_state.index}",
    )
    if st.button("送出答案", type="primary"):
        st.session_state.results.append(quiz_logic.grade(bank, question["id"], choice))
        st.session_state.phase = "reveal"
        st.rerun()


def show_reveal(bank: dict) -> None:
    result = st.session_state.results[-1]
    question = bank["questions"][result["id"]]
    if result["is_correct"]:
        st.success(plain(f"答對。正確答案是 {result['correct_letter']}. {result['correct_text']}"))
    else:
        st.error(
            plain(
                f"答錯。你選了 {result['choice']}. {result['chosen_text']}。"
                f"正確答案是 {result['correct_letter']}. {result['correct_text']}"
            )
        )
    st.markdown("**逐步解題**")
    if result["steps"]:
        md(result["steps"])
    if result["reasoning"]:
        md(result["reasoning"])
    if result["zh"]:
        md(result["zh"])
    st.markdown("**另外兩個選項為什麼不對**")
    for letter in "ABC":
        if letter == result["correct_letter"]:
            continue
        reason = result["why_wrong"].get(letter, "")
        md(f"- **{letter}. {question['choices'][letter]}**　{reason}")
    st.markdown("**本題測驗的核心觀念**")
    md(result["core_idea"] or result["subtopic"])
    if result["formula"]:
        st.markdown("**公式**")
        st.text(plain(result["formula"]))
    source_bits = [result["study_section"], result["question_ref"]]
    if result["based_on"]:
        source_bits.append(result["based_on"])
    st.markdown("**對應來源** " + "；".join(bit for bit in source_bits if bit))
    if result["calculator"]:
        st.markdown("**BA II Plus**")
        st.code(result["calculator"])
    last = st.session_state.index + 1 >= len(st.session_state.quiz_ids)
    label = "查看本組結果" if last else "下一題"
    if st.button(label, type="primary"):
        if last:
            st.session_state.phase = "done"
        else:
            st.session_state.index += 1
            st.session_state.phase = "ask"
        st.rerun()


def show_summary() -> None:
    summary = quiz_logic.summarize(st.session_state.results)
    show_pips()
    st.subheader("本組結果")
    st.metric("答對", f"{summary['correct_count']} / {summary['total']}")
    if summary["wrong"]:
        st.markdown("**錯題回顧**")
        for item in summary["wrong"]:
            st.markdown(f"**{item['id']}**　{item['subtopic']}")
            md(item["stem"])
            md(f"你的答案：{item['choice']}. {item['chosen_text']}")
            md(f"正確答案：{item['correct_letter']}. {item['correct_text']}")
            md(f"核心觀念：{item['core_idea']}")
            st.divider()
        st.markdown("**需要再複習的觀念**")
        for concept in summary["review_concepts"]:
            st.markdown(f"- {concept}")
    else:
        st.markdown("這一組沒有錯題。仍可以把同一主題換成另一種出題方式再練一次。")
    if st.button("回到開始"):
        reset_to_start()
        st.rerun()


def show_catalog(bank: dict) -> None:
    st.subheader("主題與題號")
    st.caption("這裡只列出主題、子主題、題型和難度，不顯示答案。")
    subject_id = st.selectbox("科目", subject_ids(bank), format_func=lambda key: subject_label(bank, key), key="catalog-subject")
    topic_ids = topics_in(bank, subject_id)
    topic_id = st.selectbox("主題", topic_ids, format_func=lambda key: topic_label(bank, key), key=f"catalog-topic-{subject_id}")
    topic = bank["topics"][topic_id]
    st.markdown("**講義子主題**")
    for subtopic in topic["subtopics"]:
        st.markdown(f"- {subtopic}")
    rows = [
        {
            "題號": question["id"],
            "來源": "變化題" if question["origin"] == "variant" else "原題",
            "子主題": question["subtopic"],
            "題型": question["qtype"],
            "難度": question["level"],
        }
        for question in bank["questions"].values()
        if question["topic_id"] == topic_id
    ]
    st.dataframe(rows, hide_index=True, width="stretch")


@st.cache_resource
def cached_bank() -> dict:
    return quiz_logic.load_bank()


def show_subject_cards(bank: dict) -> str:
    subjects = subject_ids(bank)
    if "practice_subject" not in st.session_state:
        current = bank["topics"].get(st.session_state.topic_id, {})
        st.session_state.practice_subject = current.get("subject_id", subjects[0])
    st.markdown("**科目**")
    columns = st.columns(2)
    for index, subject_id in enumerate(subjects):
        topic = next(item for item in bank["topics"].values() if item.get("subject_id", "QM") == subject_id)
        name = topic.get("subject_zh") or subject_id
        count = subject_question_count(bank, subject_id)
        selected = subject_id == st.session_state.practice_subject
        with columns[index % 2]:
            if st.button(
                f"{name}　{count}",
                key=f"pick-{subject_id}",
                type="primary" if selected else "secondary",
                width="stretch",
            ):
                st.session_state.practice_subject = subject_id
                st.rerun()
    return st.session_state.practice_subject


def main() -> None:
    st.set_page_config(page_title="CFA Level I 練習", layout="centered")
    init_state()
    inject_style()
    bank = cached_bank()
    show_brand()
    show_disclaimer()
    if st.sidebar.button("回到開始", width="stretch"):
        reset_to_start()
        st.session_state.page = "練習"
        st.rerun()
    page = st.sidebar.radio("頁面", ["練習", "題號對照"], key="page")
    show_run_status()
    if page == "題號對照":
        show_catalog(bank)
        return

    if st.session_state.phase == "select":
        subject_id = show_subject_cards(bank)
        topic_ids = topics_in(bank, subject_id)
        topic_id = st.selectbox(
            "主題",
            topic_ids,
            format_func=lambda key: topic_label(bank, key),
            key=f"practice-topic-{subject_id}",
        )
        mode_label = st.radio("出題方式", list(MODE_LABELS))
        count = st.slider("題數", min_value=1, max_value=8, value=5)
        mode = MODE_LABELS[mode_label]
        available = len(quiz_logic.questions_for(bank, topic_id, mode))
        st.caption(f"這個範圍目前有 {available} 題。若少於所選題數，會用全部題目。")
        if st.button("準備本組", type="primary", disabled=available == 0):
            rng = random.Random()
            quiz = quiz_logic.draw_set(bank, topic_id, mode, count, rng)
            st.session_state.topic_id = topic_id
            st.session_state.mode_label = mode_label
            st.session_state.count = count
            st.session_state.quiz_ids = [item["id"] for item in quiz]
            st.session_state.index = 0
            st.session_state.results = []
            st.session_state.phase = "brief"
            st.rerun()
        return

    if st.session_state.phase == "brief":
        show_briefing(bank)
    elif st.session_state.phase == "ask":
        show_question(bank)
    elif st.session_state.phase == "reveal":
        show_reveal(bank)
    elif st.session_state.phase == "done":
        show_summary()


if __name__ == "__main__":
    main()
