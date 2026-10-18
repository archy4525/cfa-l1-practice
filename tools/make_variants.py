"""Build verified variant items. Every numeric item is recalculated here.

The script refuses to write a question if the displayed choices are not unique
or if the true value is not strictly closest to the correct choice.
"""

from __future__ import annotations

import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

QUESTIONS: list[dict] = []
SOLUTIONS: list[dict] = []


def Q(places: int) -> Decimal:
    return Decimal("1").scaleb(-places)


def rhu(value: Decimal, places: int) -> Decimal:
    return value.quantize(Q(places), rounding=ROUND_HALF_UP)


def pretty(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def fmt_num(value: Decimal, places: int, suffix: str = "") -> str:
    shown = rhu(value, places)
    text = f"{shown:,.{places}f}"
    return text + suffix


def irr(cashflows: list[Decimal]) -> Decimal:
    def npv(rate: Decimal) -> Decimal:
        total = Decimal(0)
        for t, cf in enumerate(cashflows):
            total += cf / (Decimal(1) + rate) ** t
        return total

    lo, hi = Decimal("-0.80"), Decimal("1.50")
    if npv(lo) * npv(hi) > 0:
        raise RuntimeError(f"IRR bracket does not change sign: {cashflows}")
    for _ in range(90):
        mid = (lo + hi) / 2
        if npv(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def require_unique(true: Decimal, raw: dict[str, Decimal], correct: str, places: int, label: str) -> dict[str, str]:
    shown = {letter: rhu(value, places) for letter, value in raw.items()}
    if len(set(shown.values())) != 3:
        raise RuntimeError(f"{label}: displayed choices overlap {shown}")
    if shown[correct] != rhu(true, places):
        raise RuntimeError(f"{label}: correct choice {shown[correct]} is not the rounded true value {rhu(true, places)}")
    for letter, value in raw.items():
        if letter == correct:
            continue
        if abs(true - raw[correct]) >= abs(true - value):
            raise RuntimeError(f"{label}: true value is not strictly closest to {correct}")
    return {letter: shown[letter] for letter in "ABC"}


def add_item(
    *,
    qid: str,
    topic_id: str,
    topic_en: str,
    topic_zh: str,
    subtopic: str,
    qtype: str,
    level: str,
    stem: str,
    choices: dict[str, str],
    correct: str,
    reasoning: str,
    steps: str,
    final_answer: str,
    why_wrong: dict[str, str],
    zh: str,
    core_idea: str,
    formula: str,
    calculator: str = "",
    based_on: str,
) -> None:
    if set(choices) != {"A", "B", "C"}:
        raise RuntimeError(qid)
    if len({choices["A"], choices["B"], choices["C"]}) != 3:
        raise RuntimeError(f"{qid}: duplicate choice text")
    if correct not in "ABC" or len(why_wrong) != 2:
        raise RuntimeError(qid)
    QUESTIONS.append(
        {
            "id": qid,
            "origin": "variant",
            "topic_id": topic_id,
            "topic_en": topic_en,
            "topic_zh": topic_zh,
            "subtopic": subtopic,
            "qtype": qtype,
            "level": level,
            "stem": stem,
            "choices": choices,
            "source": {
                "question_pdf": "derived from QM_questions_VERIFIED_V3_1.pdf concepts; inputs are new",
                "question_ref": qid,
                "study_pdf": "CFA_L1_Study_Book_FINAL_2026.pdf",
                "study_chapter": "2 Quantitative Methods｜數量方法",
                "study_section": subtopic,
                "answer_pdf": "QM_answers_VERIFIED_V3_1.pdf",
                "based_on": based_on,
            },
        }
    )
    SOLUTIONS.append(
        {
            "id": qid,
            "correct": correct,
            "reasoning": reasoning,
            "steps": steps,
            "final_answer": final_answer,
            "why_wrong": why_wrong,
            "zh": zh,
            "core_idea": core_idea,
            "study_section": subtopic,
            "formula": formula,
            "exam_trap": "",
            "calculator": calculator,
            "source_note": "變化題的數字在本專案重新計算。觀念只使用講義與解答本已經支持的關係。",
            "topic_id": topic_id,
            "subtopic": subtopic,
            "based_on": based_on,
        }
    )


def add_numeric(
    *,
    qid: str,
    topic_id: str,
    topic_en: str,
    topic_zh: str,
    subtopic: str,
    qtype: str,
    level: str,
    stem: str,
    true: Decimal,
    raw: dict[str, Decimal],
    correct: str,
    places: int,
    render,
    why_templates: dict[str, str],
    reasoning: str,
    steps: str,
    zh: str,
    core_idea: str,
    formula: str,
    calculator: str,
    based_on: str,
) -> None:
    shown = require_unique(true, raw, correct, places, qid)
    choices = {letter: render(shown[letter]) for letter in "ABC"}
    why = {letter: why_templates[letter] for letter in "ABC" if letter != correct}
    add_item(
        qid=qid,
        topic_id=topic_id,
        topic_en=topic_en,
        topic_zh=topic_zh,
        subtopic=subtopic,
        qtype=qtype,
        level=level,
        stem=stem,
        choices=choices,
        correct=correct,
        reasoning=reasoning,
        steps=steps,
        final_answer=render(shown[correct]),
        why_wrong=why,
        zh=zh,
        core_idea=core_idea,
        formula=formula,
        calculator=calculator,
        based_on=based_on,
    )


def pct_render(value: Decimal) -> str:
    return f"{value:.2f}%"


def money_render(value: Decimal) -> str:
    return f"${value:,.2f}"


def plain_render(places: int, suffix: str = ""):
    def render(value: Decimal) -> str:
        return f"{value:.{places}f}{suffix}"

    return render


T21 = ("2.1", "Measuring Returns", "報酬衡量")


def build() -> None:
    # --- 2.1 verified calculation set ---
    p0, p1, income = Decimal("62"), Decimal("64.50"), Decimal("1.86")
    hpr = (p1 - p0 + income) / p0 * 100
    price_only = (p1 - p0) / p0 * 100
    div_only = income / p0 * 100
    add_numeric(
        qid="VAR-2.1-01",
        topic_id=T21[0], topic_en=T21[1], topic_zh=T21[2],
        subtopic="2.1.2 Holding-Period Return｜持有期間報酬",
        qtype="Calculation", level="L2 Standard",
        stem="An investor buys a share at $62.00, receives a $1.86 dividend, and sells the share at $64.50. The holding-period return is closest to:",
        true=hpr,
        raw={"A": price_only, "B": hpr, "C": div_only},
        correct="B", places=2, render=pct_render,
        why_templates={
            "A": "Uses the price change only: (64.50 − 62.00) / 62.00 = 4.03%，漏掉股利。",
            "C": "Uses the dividend yield only: 1.86 / 62.00 = 3.00%，漏掉價格變動。",
        },
        reasoning="單期持有期間報酬是財富變動的百分比，現金收入要放進分子。",
        steps="分子 = 64.50 − 62.00 + 1.86 = 4.36。HPR = 4.36 / 62.00 = 0.07032258 = 7.03%。百分比四捨五入到小數點後兩位。",
        zh="持有期間報酬要把股利和價差一起除以期初價格。只看價差或只看股利，都會少算一塊財富變動。",
        core_idea="HPR includes both the price change and income received.",
        formula="HPR = (P1 − P0 + income) / P0",
        calculator="",
        based_on="講義 2.1.2；同一觀念見 QM-004。數字已更換並重算。",
    )

    real, infl = Decimal("0.032"), Decimal("0.025")
    nom = ((1 + real) * (1 + infl) - 1) * 100
    additive = (real + infl) * 100
    gap = (real - infl) * 100
    add_numeric(
        qid="VAR-2.1-02",
        topic_id=T21[0], topic_en=T21[1], topic_zh=T21[2],
        subtopic="2.1.1 The Required Rate｜要求報酬率",
        qtype="Calculation", level="L2 Standard",
        stem="The real risk-free rate is 3.2% and expected inflation is 2.5%. Ignoring other risk premiums, the nominal risk-free rate is closest to:",
        true=nom,
        raw={"A": additive, "B": gap, "C": nom},
        correct="C", places=2, render=pct_render,
        why_templates={
            "A": "把 3.2% 與 2.5% 直接相加，得到 5.70%，漏掉交叉項 3.2%×2.5%。",
            "B": "用 3.2% − 2.5% = 0.70%，方向和公式都不對。",
        },
        reasoning="名目無風險利率用相乘，因為通膨補償那一層也要再賺到實質利率。",
        steps="(1 + R_nom) = 1.032 × 1.025 = 1.0578。R_nom = 0.0578 = 5.78%。加法結果 5.70% 少了 0.08 個百分點。",
        zh="3.2% 和 2.5% 不能直接相加。1.032×1.025−1 才是名目無風險利率。",
        core_idea="(1+R_nom)=(1+R_real)(1+inflation premium).",
        formula="(1 + R_nom) = (1 + R_real)(1 + inflation premium)",
        calculator="",
        based_on="講義 2.1.1；同一觀念見 QM-002。數字已更換並重算。",
    )

    ear_q = ((1 + Decimal("0.08") / 4) ** 4 - 1) * 100
    ear_c = (Decimal("0.08").exp() - 1) * 100
    add_numeric(
        qid="VAR-2.1-03",
        topic_id=T21[0], topic_en=T21[1], topic_zh=T21[2],
        subtopic="2.1.3 Stated Rates and Effective Rates｜名目利率與有效利率",
        qtype="Calculation", level="L2 Standard",
        stem="A bank quotes an 8% stated annual rate with quarterly compounding. The effective annual rate is closest to:",
        true=ear_q,
        raw={"A": Decimal("8.00"), "B": ear_q, "C": ear_c},
        correct="B", places=2, render=pct_render,
        why_templates={
            "A": "把名目報價 8% 直接當成有效年利率。季複利時 EAR 會高於報價。",
            "C": "用了連續複利 e^0.08 − 1 = 8.33%，但題目是一年複利 4 次。",
        },
        reasoning="名目年利率要先除以一年的複利次數，再複利 m 次。",
        steps="每期利率 = 0.08 / 4 = 0.02。EAR = (1.02)^4 − 1 = 0.08243216 = 8.24%。",
        zh="8% 只是報價。季複利是每季 2%，一年 4 次，有效年利率是 8.24%。",
        core_idea="EAR = (1 + i/m)^m − 1. More frequent compounding raises EAR for a fixed stated rate.",
        formula="EAR = (1 + i/m)^m − 1",
        calculator="BA II Plus：2nd → ICONV → 8 ENTER（NOM）→ ↓ → 4 ENTER（C/Y）→ ↓ → CPT（EFF）。結果 EFF = 8.24。連續複利不要用 ICONV。",
        based_on="講義 2.1.3；同一觀念見 QM-013。數字與複利次數已更換並重算。",
    )

    cont = (Decimal("0.09").exp() - 1) * 100
    monthly = ((1 + Decimal("0.09") / 12) ** 12 - 1) * 100
    add_numeric(
        qid="VAR-2.1-04",
        topic_id=T21[0], topic_en=T21[1], topic_zh=T21[2],
        subtopic="2.1.4 Continuous Compounding｜連續複利",
        qtype="Calculation", level="L2 Standard",
        stem="A stated 9% rate is compounded continuously. The effective annual rate is closest to:",
        true=cont,
        raw={"A": monthly, "B": Decimal("9.00"), "C": cont},
        correct="C", places=2, render=pct_render,
        why_templates={
            "A": "用月複利 (1 + 0.09/12)^12 − 1 = 9.38%，不是連續複利。",
            "B": "把名目 9% 直接當成一年真正賺到的利率。",
        },
        reasoning="固定名目利率下，連續複利的有效年利率是 e^r − 1，會略高於月複利。",
        steps="EAR = e^0.09 − 1 = 0.09417428 = 9.42%。月複利是 9.38%，兩者在小數兩位不會重疊。",
        zh="連續複利用 e^0.09−1，不要拿月複利或名目利率來代替。",
        core_idea="Continuous EAR is e^(stated rate) − 1 and is not an ICONV output.",
        formula="EAR = e^r − 1",
        calculator="",
        based_on="講義 2.1.4；同一觀念見 QM-019。名目利率已更換並重算。",
    )

    ccr = (Decimal("1.12").ln()) * 100
    wrong_exp = (Decimal("0.12").exp() - 1) * 100
    add_numeric(
        qid="VAR-2.1-05",
        topic_id=T21[0], topic_en=T21[1], topic_zh=T21[2],
        subtopic="2.1.4 Continuous Compounding｜連續複利",
        qtype="Calculation", level="L2 Standard",
        stem="A stock’s holding-period return over one year is 12%. The continuously compounded return over that same year is closest to:",
        true=ccr,
        raw={"A": ccr, "B": Decimal("12.00"), "C": wrong_exp},
        correct="A", places=2, render=pct_render,
        why_templates={
            "B": "把 HPR 12% 直接當成連續複利報酬。CCR 是 ln(1+HPR)。",
            "C": "算成 e^0.12 − 1 = 12.75%。那是把 12% 當成名目利率再做連續複利，不是由 HPR 還原 CCR。",
        },
        reasoning="連續複利報酬是把持有期間的財富倍率取自然對數。",
        steps="CCR = ln(1.12) = 0.11332868 = 11.33%。",
        zh="看到 HPR 要求連續複利報酬時，用 ln(1+HPR)，不是再做一次 e^HPR−1。",
        core_idea="CCR = ln(1+HPR), and HPR = e^CCR − 1.",
        formula="CCR = ln(1 + HPR)",
        calculator="",
        based_on="講義 2.1.4；同一觀念見 QM-020。HPR 已更換並重算。",
    )

    gross = Decimal("1.10") * Decimal("0.96") * Decimal("1.07")
    hpr3 = (gross - 1) * 100
    gm3 = (gross ** (Decimal(1) / 3) - 1) * 100
    am3 = (Decimal("0.10") - Decimal("0.04") + Decimal("0.07")) / 3 * 100
    add_numeric(
        qid="VAR-2.1-06",
        topic_id=T21[0], topic_en=T21[1], topic_zh=T21[2],
        subtopic="2.1.2 Holding-Period Return｜持有期間報酬",
        qtype="Calculation", level="L3 Trap",
        stem="A fund earns +10%, −4%, and +7% in three successive full years, with no intra-year cash flows. The three-year holding-period return is closest to:",
        true=hpr3,
        raw={"A": gm3, "B": am3, "C": hpr3},
        correct="C", places=2, render=pct_render,
        why_templates={
            "A": "對財富倍率開三次方再減 1，那是幾何平均年報酬，不是三年持有期間報酬。",
            "B": "用算術平均 (10% − 4% + 7%) / 3 = 4.33%，既不是三年總報酬，也沒有複利。",
        },
        reasoning="多年持有期間報酬只把各年財富倍率連乘，然後減 1。不開根號。",
        steps=f"1.10 × 0.96 × 1.07 = {pretty(gross)}。三年 HPR = {pretty(gross)} − 1 = {rhu(hpr3, 2)}%。幾何平均是 {rhu(gm3, 2)}%，算術平均是 {rhu(am3, 2)}%。",
        zh="三年報酬是連乘後減 1。開根號得到的是每年的幾何平均，不是這三年總共賺多少。",
        core_idea="Multi-year HPR multiplies gross returns and stops. The root is the geometric mean.",
        formula="HPR_1→N = (1+r1)(1+r2)…(1+rN) − 1",
        calculator="",
        based_on="講義 2.1.2；同一觀念見 QM-005。報酬序列已更換並重算。",
    )

    gross_g = Decimal("1.18") * Decimal("0.95") * Decimal("1.04")
    gm = (gross_g ** (Decimal(1) / 3) - 1) * 100
    hpr_g = (gross_g - 1) * 100
    am_g = (Decimal("0.18") - Decimal("0.05") + Decimal("0.04")) / 3 * 100
    add_numeric(
        qid="VAR-2.1-07",
        topic_id=T21[0], topic_en=T21[1], topic_zh=T21[2],
        subtopic="2.1.7 Geometric Mean｜幾何平均",
        qtype="Calculation", level="L3 Trap",
        stem="Full-year total returns are +18%, −5%, and +4%. The geometric mean annual return is closest to:",
        true=gm,
        raw={"A": hpr_g, "B": gm, "C": am_g},
        correct="B", places=2, render=pct_render,
        why_templates={
            "A": "停在三年持有期間報酬，沒有取三次方根。",
            "C": "用算術平均 (18% − 5% + 4%) / 3。有波動時，算術平均不是複利成長率。",
        },
        reasoning="幾何平均是能重現同一條財富路徑的固定年率，所以要開 n 次方。",
        steps=f"財富倍率 = 1.18 × 0.95 × 1.04 = {gross_g}。幾何平均 = ({gross_g})^(1/3) − 1 = {rhu(gm, 2)}%。",
        zh="幾何平均先連乘，再取與年數相同的根，最後減 1。它不是三年總報酬，也不是三個報酬的普通平均。",
        core_idea="The geometric mean is the constant annual compound rate that reproduces the wealth path.",
        formula="r_G = [(1+r1)(1+r2)(1+r3)]^(1/3) − 1",
        calculator="",
        based_on="講義 2.1.7；同一觀念見 QM-025。報酬序列已更換並重算。",
    )

    prices = [Decimal("10"), Decimal("12.50"), Decimal("20")]
    spend = Decimal("10")
    shares = sum(spend / price for price in prices)
    harmonic = (spend * 3) / shares
    arithmetic_price = sum(prices) / 3
    geometric_price = (prices[0] * prices[1] * prices[2]) ** (Decimal(1) / 3)
    add_numeric(
        qid="VAR-2.1-08",
        topic_id=T21[0], topic_en=T21[1], topic_zh=T21[2],
        subtopic="2.1.8 Harmonic Mean｜調和平均",
        qtype="Calculation", level="L2 Standard",
        stem="An investor spends $10 at each of three prices: $10, $12.50, and $20. The average purchase price is closest to:",
        true=harmonic,
        raw={"A": harmonic, "B": geometric_price, "C": arithmetic_price},
        correct="A", places=2, render=money_render,
        why_templates={
            "B": "用三個價格的幾何平均。等額買進的平均價格用調和平均。",
            "C": "用三個價格的算術平均 (10 + 12.50 + 20) / 3 = 14.17，讓高價和低價一樣重要。",
        },
        reasoning="每一筆投入金額相同時，平均買進價格是總支出除以總股數，也就是價格的調和平均。",
        steps="股數 = 10/10 + 10/12.50 + 10/20 = 1 + 0.80 + 0.50 = 2.30。總支出 = 30。平均價格 = 30 / 2.30 = 13.04。",
        zh="同樣花 10 元，貴的時候買到的股數比較少，所以平均價格不是三個價格直接平均。",
        core_idea="Equal-dollar purchases use the harmonic mean of the prices.",
        formula="Average price = total dollars spent / total shares purchased",
        calculator="",
        based_on="講義 2.1.8；同一觀念見 QM-030。價格與每筆金額已更換並重算。",
    )

    twr = ((Decimal("1.10") * Decimal("0.95")) ** Decimal("0.5") - 1) * 100
    two_year = (Decimal("1.10") * Decimal("0.95") - 1) * 100
    am_tw = (Decimal("0.10") - Decimal("0.05")) / 2 * 100
    add_numeric(
        qid="VAR-2.1-09",
        topic_id=T21[0], topic_en=T21[1], topic_zh=T21[2],
        subtopic="2.1.10 Time-Weighted versus Money-Weighted｜時間加權與資金加權",
        qtype="Calculation", level="L3 Trap",
        stem="A portfolio begins at 500. After a +10% year it is worth 550. The client then deposits 50. The resulting 600 earns −5% in year 2 and ends at 570. The annualized time-weighted return is closest to:",
        true=twr,
        raw={"A": two_year, "B": am_tw, "C": twr},
        correct="C", places=2, render=pct_render,
        why_templates={
            "A": "報出兩年持有期間報酬 4.50%，沒有年化，也沒有先把外部存款從子期間報酬裡拿掉。",
            "B": "用兩個子期間報酬的算術平均 (10% − 5%) / 2 = 2.50%。年化時間加權報酬要用幾何平均。",
        },
        reasoning="時間加權報酬先算存款前後的兩個持有期間報酬，再取幾何平均。存款本身不進入報酬。",
        steps="第一年 HPR = 550/500 − 1 = 10%。存款發生在第一年報酬之後。第二年 HPR = 570/600 − 1 = −5%。年化 TWR = √(1.10 × 0.95) − 1 = 2.23%。",
        zh="客戶中途存錢會改變帳戶金額，但時間加權報酬只連乘兩段資產自己的報酬。年化時要開根號。",
        core_idea="Annualized TWR is the geometric mean of subperiod HPRs. External deposits are removed by splitting the periods.",
        formula="TWR = [(1+HPR1)(1+HPR2)]^(1/2) − 1",
        calculator="",
        based_on="講義 2.1.10；同一觀念見 QM-036。路徑已更換並重算。",
    )

    rate, n_per, pmt = Decimal("0.05"), 6, Decimal("150")
    pv_ord = pmt * (1 - (1 + rate) ** (-n_per)) / rate
    pv_due = pv_ord * (1 + rate)
    undiscounted = pmt * n_per
    add_numeric(
        qid="VAR-2.1-10",
        topic_id=T21[0], topic_en=T21[1], topic_zh=T21[2],
        subtopic="2.1.11 Annuity Timing｜年金時點",
        qtype="Calculation", level="L2 Standard",
        stem="A six-year ordinary annuity pays $150 at the end of each year. The discount rate is 5% per year. The present value is closest to:",
        true=pv_ord,
        raw={"A": undiscounted, "B": pv_due, "C": pv_ord},
        correct="C", places=2, render=money_render,
        why_templates={
            "A": "把六筆 150 直接加總成 900，完全沒有折現。",
            "B": "用期初年金：把期末年金現值再乘 1.05。題目的第一筆在第一年年底。",
        },
        reasoning="普通年金的第一筆在第一期期末。現值是六筆期末現金流的折現和。",
        steps=f"PV = 150 × [1 − (1.05)^(−6)] / 0.05 = {rhu(pv_ord, 2)}。期初年金才是這個數再乘 1.05。",
        zh="題目說 end of each year，所以是普通年金。期初年金會比較大，未折現的總額更大。",
        core_idea="Ordinary annuity: first payment at t=1. Annuity due is worth one extra period of compounding.",
        formula="PV_ordinary = PMT × [1 − (1+r)^(−N)] / r",
        calculator="BA II Plus：確認 END。2nd → CLR TVM → 6 N → 5 I/Y → 150 PMT → 0 FV → CPT PV。螢幕是負號，代表取得這串年金今天要付出的金額；金額取絕對值。算完保持 END。",
        based_on="講義 2.1.11；同一觀念見 QM-043。期數、付款與利率已更換並重算。",
    )

    div, rs = Decimal("4.50"), Decimal("0.075")
    perp = div / rs
    due_perp = div + perp
    times = div * Decimal("7.5")
    add_numeric(
        qid="VAR-2.1-11",
        topic_id=T21[0], topic_en=T21[1], topic_zh=T21[2],
        subtopic="2.1.11 Annuity Timing｜年金時點",
        qtype="Calculation", level="L2 Standard",
        stem="A share is expected to pay a $4.50 dividend every year forever, starting in one year, with no growth. The required return is 7.5%. The present value is closest to:",
        true=perp,
        raw={"A": times, "B": due_perp, "C": perp},
        correct="C", places=2, render=money_render,
        why_templates={
            "A": "用 4.50 × 7.5 = 33.75，把除法做成乘法。",
            "B": "多加了一筆今天就收到的股利 4.50，變成第一筆立即支付的永續年金。題目的第一筆在一年後。",
        },
        reasoning="第一筆在一年後的永續年金，現值是每期付款除以每期要求報酬。",
        steps="PV = 4.50 / 0.075 = 60.00。",
        zh="沒有成長、第一筆在一年後，就是 PMT / r。不要把利率乘回去，也不要多加今天的一筆。",
        core_idea="A level perpetuity with the first payment one period from now is PMT / r.",
        formula="PV = PMT / r_s",
        calculator="",
        based_on="講義 2.1.11；同一觀念見 QM-052。股利與要求報酬已更換並重算。",
    )

    # --- 2.2 ---
    observations = [Decimal("5"), Decimal("11"), Decimal("8")]
    mean = sum(observations) / 3
    sq = sum((x - mean) ** 2 for x in observations)
    sample_sd = (sq / 2).sqrt()
    pop_sd = (sq / 3).sqrt()
    mad = sum(abs(x - mean) for x in observations) / 3
    add_numeric(
        qid="VAR-2.2-01",
        topic_id="2.2", topic_en="Describing Return Distributions", topic_zh="報酬分配的描述",
        subtopic="2.2.2 Dispersion｜離散",
        qtype="Calculation", level="L2 Standard",
        stem="Treat returns of 5%, 11%, and 8% as a sample. The sample standard deviation is closest to:",
        true=sample_sd,
        raw={"A": pop_sd, "B": mad, "C": sample_sd},
        correct="C", places=2, render=pct_render,
        why_templates={
            "A": "除以 n = 3 再開根號，那是母體標準差。樣本標準差除以 n−1。",
            "B": "這是平均絕對偏差。標準差要先把偏差平方。",
        },
        reasoning="樣本變異數的分母是 n−1，標準差再把變異數開根號。",
        steps="平均 = (5+11+8)/3 = 8。平方偏差 = 9 + 9 + 0 = 18。樣本變異數 = 18 / 2 = 9。樣本標準差 = 3.00%。母體標準差 = √(18/3) = 2.45%。MAD = 2.00%。",
        zh="題目說 sample，分母用 2 不是 3。算完變異數還要開根號，才回到報酬的單位。",
        core_idea="Sample variance divides by n−1. Standard deviation is the square root.",
        formula="s = √[ Σ(Xi − X̄)^2 / (n − 1) ]",
        calculator="",
        based_on="講義 2.2.2；同一觀念見講義的 10%、30%、20% 例子與 QM-064。觀察值已更換並重算。",
    )

    ordered = [Decimal("4"), Decimal("8"), Decimal("11"), Decimal("15"), Decimal("21")]
    ly = (Decimal(len(ordered)) + 1) * Decimal("0.40")
    n_star, frac = 2, Decimal("0.4")
    p40 = ordered[n_star - 1] + frac * (ordered[n_star] - ordered[n_star - 1])
    stop_early = ordered[1]
    flipped = ordered[1] + (1 - frac) * (ordered[2] - ordered[1])
    add_numeric(
        qid="VAR-2.2-02",
        topic_id="2.2", topic_en="Describing Return Distributions", topic_zh="報酬分配的描述",
        subtopic="2.2.4 Quantiles｜分位數",
        qtype="Calculation", level="L2 Standard",
        stem="An ordered sample of n = 5 is 4, 8, 11, 15, 21. Using L_y = (n+1) × y/100 and linear interpolation, the 40th percentile is closest to:",
        true=p40,
        raw={"A": stop_early, "B": p40, "C": flipped},
        correct="B", places=1, render=plain_render(1),
        why_templates={
            "A": "只取位置 2 的觀察值 8，沒有使用小數部分 0.4。",
            "C": "把插值比例用成 0.6，從 8 往 11 走了太遠。",
        },
        reasoning="位置 L_40 = (5+1)×0.40 = 2.4，所以從第 2 個觀察值走向第 3 個的 40%。",
        steps="L_40 = 6 × 0.40 = 2.4。P_40 = 8 + 0.4 × (11 − 8) = 9.2。",
        zh="百分位先算 (n+1) 乘上比例。2.4 不是直接取第 2 個或第 3 個，而是兩者之間再走 0.4。",
        core_idea="Ly = (n+1)y/100, then interpolate the fractional part.",
        formula="P_y = X_n* + f (X_n*+1 − X_n*)",
        calculator="",
        based_on="講義 2.2.4；同一插值程序見 QM-076。樣本與結果已更換並重算。",
    )

    add_item(
        qid="VAR-2.2-03",
        topic_id="2.2", topic_en="Describing Return Distributions", topic_zh="報酬分配的描述",
        subtopic="2.2.3 Skewness and Kurtosis｜偏態與峰度",
        qtype="Recognition", level="L2 Standard",
        stem="A return distribution has a long right tail. The order of its mode, median, and mean is most accurately:",
        choices={
            "A": "mode < median < mean.",
            "B": "mean < median < mode.",
            "C": "mean = median = mode, because only a left tail can move the mean.",
        },
        correct="A",
        reasoning="極端正報酬把平均數往右拉。眾數幾乎不動，中位數移動較少，所以正偏是 mode < median < mean。",
        steps="講義：把右尾拉開時，平均數移到中位數右邊，中位數又在眾數右邊。",
        final_answer="A",
        why_wrong={
            "B": "這是左偏、長左尾的順序。題目是右尾。",
            "C": "右尾一樣會拉動平均數。只有對稱分配才是三個位置重疊。",
        },
        zh="長右尾是正偏。順序是眾數、中位數、平均數由小到大。",
        core_idea="Positive skew: mode < median < mean.",
        formula="Positive / right skew: mode < median < mean",
        based_on="講義 2.2.3。提問改成右尾的位置順序，沒有另加題庫沒有的分配性質。",
    )

    # --- 2.3 ---
    e_good = Decimal("0.40") * Decimal("2.40") + Decimal("0.60") * Decimal("2.00")
    e_poor = Decimal("0.25") * Decimal("1.20") + Decimal("0.75") * Decimal("0.80")
    e_uncond = e_good * Decimal("0.70") + e_poor * Decimal("0.30")
    e_equal = (e_good + e_poor) / 2
    add_numeric(
        qid="VAR-2.3-01",
        topic_id="2.3", topic_en="Probability Trees and Conditional Expectations", topic_zh="機率樹與條件期望",
        subtopic="2.3.1 Conditional Expected Value｜條件期望值",
        qtype="Calculation", level="L3 Trap",
        stem="A good economy has probability 0.70 and a poor economy has probability 0.30. Given a good economy, EPS is 2.40 with probability 0.40 and 2.00 with probability 0.60. Given a poor economy, EPS is 1.20 with probability 0.25 and 0.80 with probability 0.75. Branches at each node are mutually exclusive and exhaustive. Unconditional expected EPS is closest to:",
        true=e_uncond,
        raw={"A": e_good, "B": e_equal, "C": e_uncond},
        correct="C", places=2, render=plain_render(2),
        why_templates={
            "A": "只報好經濟的條件期望 2.16，沒有用全機率法則加回差經濟。",
            "B": "把兩個條件期望各乘 1/2。第一層機率是 0.70 和 0.30，不是相等。",
        },
        reasoning="先算每個經濟情境的條件期望，再用情境機率加權。",
        steps="E(EPS|good) = 0.40×2.40 + 0.60×2.00 = 2.16。E(EPS|poor) = 0.25×1.20 + 0.75×0.80 = 0.90。E(EPS) = 2.16×0.70 + 0.90×0.30 = 1.78。",
        zh="無條件期望不是只看好的那一枝，也不是兩個情境簡單平均。要用 0.70 和 0.30 加權。",
        core_idea="E(X) = E(X|S)P(S) + E(X|Sc)P(Sc).",
        formula="E(X) = E(X|S)P(S) + E(X|Sc)P(Sc)",
        calculator="",
        based_on="講義 2.3.1；同一程序見 QM-086 與 QM-087。機率與 EPS 已更換並重算。",
    )

    prior = Decimal("0.25")
    like = Decimal("0.90")
    like_not = Decimal("0.15")
    p_news = like * prior + like_not * (1 - prior)
    posterior = like * prior / p_news * 100
    add_numeric(
        qid="VAR-2.3-02",
        topic_id="2.3", topic_en="Probability Trees and Conditional Expectations", topic_zh="機率樹與條件期望",
        subtopic="2.3.2 Bayes’ Formula｜貝氏公式",
        qtype="Calculation", level="L3 Trap",
        stem="The prior probability of event E is 25%. A news item appears in 90% of cases when E occurs and in 15% of cases when E does not occur. Given that the news item appears, the posterior probability of E is closest to:",
        true=posterior,
        raw={"A": prior * 100, "B": like * 100, "C": posterior},
        correct="C", places=2, render=pct_render,
        why_templates={
            "A": "留下先驗 25%，沒有用新資訊更新。",
            "B": "報出概似 P(news|E) = 90%，把條件方向看反。",
        },
        reasoning="後驗的分子是聯合機率，分母是這則新聞的無條件機率。",
        steps="P(news) = 0.90×0.25 + 0.15×0.75 = 0.225 + 0.1125 = 0.3375。P(E|news) = 0.225 / 0.3375 = 2/3 = 66.67%。",
        zh="90% 是看到事件才出現新聞的機率，不是看到新聞之後事件的機率。後驗要除以所有會產生這則新聞的路徑。",
        core_idea="Posterior = likelihood × prior / unconditional probability of the information.",
        formula="P(E|news) = P(news|E)P(E) / P(news)",
        calculator="",
        based_on="講義 2.3.2 的併購例子與 QM-089、QM-090。先驗和概似已更換並重算。",
    )

    # --- 2.4 ---
    cov, sd_x, sd_y = Decimal("0.015"), Decimal("0.10"), Decimal("0.25")
    rho = cov / (sd_x * sd_y)
    one_sd = cov / sd_x
    ratio_sd = sd_x / sd_y
    add_numeric(
        qid="VAR-2.4-01",
        topic_id="2.4", topic_en="Portfolio Mathematics", topic_zh="投資組合數學",
        subtopic="2.4.1 Covariance and Correlation｜協方差與相關係數",
        qtype="Calculation", level="L2 Standard",
        stem="The covariance of two asset returns is 0.015. Their standard deviations are 10% and 25%. The correlation is closest to:",
        true=rho,
        raw={"A": one_sd, "B": rho, "C": ratio_sd},
        correct="B", places=2, render=plain_render(2),
        why_templates={
            "A": "只除以第一個標準差：0.015 / 0.10 = 0.15，少除了另一個標準差。",
            "C": "用兩個標準差相除：0.10 / 0.25 = 0.40，沒有用到協方差。",
        },
        reasoning="相關係數把協方差除以兩個標準差的乘積，所以落在 −1 到 1。",
        steps="ρ = 0.015 / (0.10 × 0.25) = 0.015 / 0.025 = 0.60。",
        zh="協方差還帶著單位。要比較線性關係的強度，要除以兩個標準差。",
        core_idea="Correlation = covariance / (σ1 σ2).",
        formula="ρ = Cov / (σX σY)",
        calculator="",
        based_on="講義 2.4.1。協方差與標準差是新數值，已重算。",
    )

    w1, w2 = Decimal("0.70"), Decimal("0.30")
    s1, s2, rho_p = Decimal("0.25"), Decimal("0.15"), Decimal("0.20")
    var_p = w1**2 * s1**2 + w2**2 * s2**2 + 2 * w1 * w2 * rho_p * s1 * s2
    sd_p = var_p.sqrt() * 100
    sd_one = (w1 * s1 + w2 * s2) * 100
    var_zero = w1**2 * s1**2 + w2**2 * s2**2
    sd_zero = var_zero.sqrt() * 100
    add_numeric(
        qid="VAR-2.4-02",
        topic_id="2.4", topic_en="Portfolio Mathematics", topic_zh="投資組合數學",
        subtopic="2.4.2 Portfolio Variance｜投資組合變異數",
        qtype="Calculation", level="L3 Trap",
        stem="A portfolio is 70% in Asset 1 and 30% in Asset 2. The standard deviations are 25% and 15%, and the correlation is 0.20. Weights sum to 1. The portfolio standard deviation is closest to:",
        true=sd_p,
        raw={"A": sd_one, "B": sd_zero, "C": sd_p},
        correct="C", places=2, render=pct_render,
        why_templates={
            "A": "用 ρ = 1 的加權標準差 0.70×25% + 0.30×15% = 22.00%。題目的相關是 0.20。",
            "B": "把相關設成 0，刪掉協方差項。題目的協方差項不是 0。",
        },
        reasoning="兩資產組合標準差要包含 2×w1×w2×ρ×σ1×σ2，最後再開根號。",
        steps=f"變異數 = 0.70²×0.25² + 0.30²×0.15² + 2×0.70×0.30×0.20×0.25×0.15 = {pretty(var_p)}。標準差 = √{pretty(var_p)} = {rhu(sd_p, 2)}%。",
        zh="組合報酬可以加權平均，組合標準差不行。相關 0.20 的結果會落在相關 0 和相關 1 之間。",
        core_idea="Portfolio variance includes the covariance term. Portfolio return is the value-weighted mean.",
        formula="σ²_P = w1²σ1² + w2²σ2² + 2 w1 w2 ρ σ1 σ2",
        calculator="",
        based_on="講義 2.4.2；同一公式見 QM-096。權重、波動與相關已更換並重算。",
    )

    add_item(
        qid="VAR-2.4-03",
        topic_id="2.4", topic_en="Portfolio Mathematics", topic_zh="投資組合數學",
        subtopic="2.4.3 Independence versus Uncorrelated｜統計獨立與不相關",
        qtype="Exam Trap", level="L3 Trap",
        stem="Two assets in a portfolio have a correlation of 0. Which statement is most accurate?",
        choices={
            "A": "The returns are statistically independent, because a correlation of 0 is the definition of independence.",
            "B": "The covariance term drops out of portfolio variance. A correlation of 0 does not establish that the returns are independent.",
            "C": "Portfolio variance is undefined when correlation is 0, because the formula requires a nonzero covariance.",
        },
        correct="B",
        reasoning="相關為 0 表示線性共動為 0，組合變異數的協方差項消失。獨立要求聯合機率等於兩個邊際機率的乘積，條件更強。",
        steps="ρ = 0 ⇒ Cov = 0 ⇒ 兩資產公式中的交叉項為 0。這不表示 P(X,Y) = P(X)P(Y)。",
        final_answer="B",
        why_wrong={
            "A": "不相關不能推出獨立。獨立可以推出不相關，方向相反。",
            "C": "相關為 0 時公式仍然成立，只是交叉項等於 0。",
        },
        zh="組合題裡 ρ=0 可以讓風險公式的交叉項消失。這不是兩個報酬彼此獨立的證明。",
        core_idea="Independence implies zero correlation. Zero correlation does not imply independence.",
        formula="Uncorrelated: Cov = 0. Independent: P(X,Y) = P(X)P(Y).",
        based_on="講義 2.4.3 的考試陷阱。問法改成「相關為 0 時可以確定什麼」。",
    )

    # --- 2.5 ---
    add_item(
        qid="VAR-2.5-01",
        topic_id="2.5", topic_en="Simulation Methods", topic_zh="模擬方法",
        subtopic="2.5 Lognormal prices and continuously compounded returns｜對數常態價格與連續複利報酬",
        qtype="Application", level="L2 Standard",
        stem="If a stock’s continuously compounded return is normally distributed, the future price is most accurately modeled as:",
        choices={
            "A": "normal, because the future price is the starting price multiplied by the return.",
            "B": "lognormal, because the price is the exponential of a normal variable and is bounded below by 0.",
            "C": "lognormal for the return and normal for the price.",
        },
        correct="B",
        reasoning="若連續複利報酬是常態，未來價格是 e 的指數，所以是對數常態。對數常態用來描述不能為負的價格，不用來描述可以為負的報酬。",
        steps="CCR = ln(期末 / 期初)。CCR 常態 ⇒ 期末價格對數常態。",
        final_answer="B",
        why_wrong={
            "A": "價格不是期初價格乘上普通報酬。連續複利模型是期初價格乘上 e^CCR。",
            "C": "方向相反。常態的是連續複利報酬，對數常態的是價格。",
        },
        zh="價格有 0 的下界，所以用對數常態。報酬可以是負的，不是這個模型的對象。",
        core_idea="A normal continuously compounded return makes the future price lognormal.",
        formula="If CCR is normal, future price = beginning price × e^CCR is lognormal.",
        based_on="講義 2.5；同一觀念見 QM-108。問的是價格模型而不是報酬模型。",
    )
    add_item(
        qid="VAR-2.5-02",
        topic_id="2.5", topic_en="Simulation Methods", topic_zh="模擬方法",
        subtopic="2.5 Monte Carlo versus historical simulation｜蒙地卡羅與歷史模擬",
        qtype="Application", level="L2 Standard",
        stem="An analyst repeatedly draws an actual past price change at random and applies that change to the current portfolio. This procedure is most accurately:",
        choices={
            "A": "Monte Carlo simulation, because every random draw is an inverse transformation.",
            "B": "historical simulation. Future changes need not follow that historical distribution.",
            "C": "a jackknife, because each draw permanently deletes one past observation.",
        },
        correct="B",
        reasoning="歷史模擬把實際發生過的價格變動隨機套到目前的投資組合。它不要求未來服從同一條歷史分配。",
        steps="蒙地卡羅是從均勻隨機數逆轉換到選定的分配。刀切法是對既有觀察值重新抽樣且不放回。題目用的是實際歷史變動。",
        final_answer="B",
        why_wrong={
            "A": "隨機本身不等於蒙地卡羅。蒙地卡羅要從選定的分配做逆轉換。",
            "C": "刀切法處理的是既有樣本的重抽，不是把歷史價格變動套到今天的組合。",
        },
        zh="拿過去真實的價格變動去套今天的組合，是歷史模擬。它沒有辨認出因果，也不保證未來照這條歷史走。",
        core_idea="Historical simulation applies actual past changes. It is not Monte Carlo and not a jackknife.",
        formula="Historical simulation uses realized past changes. Monte Carlo maps uniforms into an assumed distribution.",
        based_on="講義 2.5；同一區分見 QM-111。情境改成重複抽取歷史價格變動。",
    )

    # --- 2.6 ---
    sigma, n_se = Decimal("12"), Decimal("36")
    se = sigma / n_se.sqrt()
    by_n = sigma / n_se
    half = Decimal("1.96") * se
    add_numeric(
        qid="VAR-2.6-01",
        topic_id="2.6", topic_en="Sampling and the Central Limit Theorem", topic_zh="抽樣與中央極限定理",
        subtopic="2.6 Central limit theorem and standard error｜中央極限定理與標準誤",
        qtype="Calculation", level="L2 Standard",
        stem="A simple random sample of size 36 is drawn from a population with σ = 12%. The standard error of the sample mean is closest to:",
        true=se,
        raw={"A": by_n, "B": half, "C": se},
        correct="C", places=2, render=pct_render,
        why_templates={
            "A": "除以 n = 36，得到 0.33%。標準誤除以 √n。",
            "B": "用講義的 95% 臨界值 1.96 乘上標準誤，得到信賴區間的半寬 3.92%，不是標準誤本身。",
        },
        reasoning="樣本平均的標準誤是母體標準差除以樣本數的平方根。",
        steps="√36 = 6。標準誤 = 12% / 6 = 2.00%。",
        zh="n 從 36 再變成 144，標準誤才會再減半。不要除以 n，也不要把 1.96 乘進去。",
        core_idea="Standard error = σ / √n. Quadrupling n halves the standard error.",
        formula="σ_X̄ = σ / √n",
        calculator="",
        based_on="講義 2.6；同一公式見 QM-126。σ 與 n 已更換並重算。1.96 是講義給出的 95% 臨界值。",
    )
    add_item(
        qid="VAR-2.6-02",
        topic_id="2.6", topic_en="Sampling and the Central Limit Theorem", topic_zh="抽樣與中央極限定理",
        subtopic="2.6 Sampling methods｜抽樣方法",
        qtype="Recognition", level="L2 Standard",
        stem="A bond universe is divided into rating groups. Inside each group, the analyst draws a simple random sample whose size is proportional to the group. This design is most accurately:",
        choices={
            "A": "cluster sampling, because each rating group is a cluster.",
            "B": "stratified sampling.",
            "C": "systematic sampling, because the groups are ordered by rating.",
        },
        correct="B",
        reasoning="分層抽樣先把母體切開，再在每一層做簡單隨機抽樣，抽樣數通常按該層大小比例。",
        steps="集群抽樣是抽中整個集群。系統抽樣是隨機起點之後每第 k 個。題目是在每一個評等層內抽樣。",
        final_answer="B",
        why_wrong={
            "A": "集群抽樣抽的是整個集群，不是在每一層裡再做簡單隨機抽樣。",
            "C": "評等分組不會自動變成每第 k 個的系統抽樣。",
        },
        zh="先按評等分層，再按比例在層內隨機抽，是分層抽樣。",
        core_idea="Stratified sampling draws a simple random sample within each stratum, often in proportion to stratum size.",
        formula="Stratified: sample within strata. Cluster: select whole clusters. Systematic: every kth item.",
        based_on="講義 2.6 的抽樣表；同一區分見 QM-117。分層變項改成債券評等。",
    )
    add_item(
        qid="VAR-2.6-03",
        topic_id="2.6", topic_en="Sampling and the Central Limit Theorem", topic_zh="抽樣與中央極限定理",
        subtopic="2.6 Confidence intervals and z versus t｜信賴區間與 z、t 的選擇",
        qtype="Recognition", level="L2 Standard",
        stem="A sample of n = 40 is drawn from a nonnormal population. The population variance is unknown. For a test or confidence interval for the mean, the appropriate choice is:",
        choices={
            "A": "no test is available, because the population is nonnormal.",
            "B": "a t statistic.",
            "C": "a z statistic, because any n of at least 30 replaces t.",
        },
        correct="B",
        reasoning="講義的表：非常態、變異數未知、n ≥ 30，用 t。n < 30 才標成沒有可用檢定。",
        steps="n = 40 已達到表中的 30 門檻，但變異數仍然未知，所以不是改用 z。",
        final_answer="B",
        why_wrong={
            "A": "「沒有可用檢定」是非常態且 n < 30 那一列。這裡 n = 40。",
            "C": "n ≥ 30 而且變異數已知時才用 z。變異數未知時，表上仍是 t。",
        },
        zh="非常態不等於一定不能檢定。n 夠大但標準差要用樣本估計時，講義用 t。",
        core_idea="Nonnormal, unknown variance, n ≥ 30: use t. The same row is not available when n < 30.",
        formula="Unknown variance → t with df = n − 1, provided the table’s sample-size condition is met.",
        based_on="講義 2.6 的 z / t 選擇表。題目指定非常態、變異數未知、n=40。",
    )

    # --- 2.7 ---
    add_item(
        qid="VAR-2.7-01",
        topic_id="2.7", topic_en="Hypothesis Testing", topic_zh="假設檢定",
        subtopic="2.7.1 Type I and Type II Errors｜型一與型二錯誤",
        qtype="Application", level="L3 Trap",
        stem="Holding the rest of the sample fixed, a researcher raises the significance level from 1% to 5%. The most accurate effect is:",
        choices={
            "A": "P(Type I error) rises, P(Type II error) falls, and power rises.",
            "B": "both error probabilities fall, because the test has become more powerful.",
            "C": "P(Type I error) falls, because 5% is a stricter standard than 1%.",
        },
        correct="A",
        reasoning="α 就是型一錯誤的機率。把 α 從 1% 提高到 5%，比較容易拒絕虛無假設，所以型一錯誤上升、型二錯誤下降、檢定力上升。",
        steps="講義：降低 α 會降低型一錯誤、提高型二錯誤、降低檢定力。這裡是相反方向的調整。",
        final_answer="A",
        why_wrong={
            "B": "兩種錯誤不會一起下降。α 變寬時，型一錯誤變多。",
            "C": "5% 比 1% 更容易拒絕，不是更嚴格。",
        },
        zh="顯著水準調高，比較容易宣布有關係，也比較容易出現型一錯誤。漏掉真實關係的機會則下降。",
        core_idea="Raising α raises P(Type I), lowers P(Type II), and raises power.",
        formula="α = P(Type I). Power = 1 − β.",
        based_on="講義 2.7.1。原書的即時檢查是把 α 從 5% 降到 1%；這一題把方向反過來。",
    )
    add_item(
        qid="VAR-2.7-02",
        topic_id="2.7", topic_en="Hypothesis Testing", topic_zh="假設檢定",
        subtopic="2.7 Hypothesis statements, p-values, and decisions｜假設、p 值與決策",
        qtype="Exam Trap", level="L3 Trap",
        stem="A two-sided test produces a p-value of 0.02. Which statement is most accurate?",
        choices={
            "A": "H0 is rejected at both the 5% and 1% significance levels, because 0.02 is below 5%.",
            "B": "H0 is rejected at 5% and not at 1%. The 0.02 is not the probability that H0 is true.",
            "C": "P(H0 is true | data) = 0.02.",
        },
        correct="B",
        reasoning="p 值是在虛無假設下，這個統計量能夠被拒絕的最小顯著水準。0.02 ≤ 0.05，所以 5% 拒絕；0.02 > 0.01，所以 1% 不拒絕。",
        steps="比較的是 p 與事先選定的 α，不是把 p 讀成 P(H0 | 資料)。",
        final_answer="B",
        why_wrong={
            "A": "低於 5% 不表示每一個更小的 α 都會拒絕。1% 比 0.02 更小。",
            "C": "這是講義點名的錯誤：把 p 值讀成虛無假設為真的機率。",
        },
        zh="p=0.02 表示 α 設在 2% 或更寬就可以拒絕。它不是 H0 為真的機率。",
        core_idea="Reject H0 when p ≤ α. The p-value is not P(H0 is true).",
        formula="Reject if p ≤ α.",
        based_on="講義 2.7 的 p 值陷阱；同一觀念見 QM-171。p 值改為 0.02。",
    )

    xbar, mu0, s, n_t = Decimal("6.4"), Decimal("5.0"), Decimal("2.8"), Decimal("16")
    t_stat = (xbar - mu0) / (s / n_t.sqrt())
    raw_gap = (xbar - mu0) / s
    by_n_t = (xbar - mu0) / (s / n_t)
    add_numeric(
        qid="VAR-2.7-03",
        topic_id="2.7", topic_en="Hypothesis Testing", topic_zh="假設檢定",
        subtopic="2.7.2 Which test statistic?｜檢定統計量的選擇",
        qtype="Calculation", level="L2 Standard",
        stem="H0: μ = 5.0. A sample of n = 16 from a normal population has a sample mean of 6.4 and a sample standard deviation of 2.8. The population variance is unknown. The t-statistic is closest to:",
        true=t_stat,
        raw={"A": raw_gap, "B": by_n_t, "C": t_stat},
        correct="C", places=2, render=plain_render(2),
        why_templates={
            "A": "用 (6.4 − 5.0) / 2.8 = 0.50，分母用了樣本標準差，沒有除以 √n。",
            "B": "標準誤誤用 s/n 而不是 s/√n：(1.4) / (2.8/16) = 8.00。",
        },
        reasoning="變異數未知時，單一平均數用 t。分母是樣本標準差除以 √n。",
        steps="標準誤 = 2.8 / √16 = 2.8 / 4 = 0.70。t = (6.4 − 5.0) / 0.70 = 2.00。自由度是 15。這一題只問統計量，沒有給臨界值，所以不做拒絕決策。",
        zh="分子是樣本平均減去虛無假設的值。分母必須是標準誤。",
        core_idea="t = (X̄ − μ0) / (s / √n), df = n − 1, when the population variance is unknown.",
        formula="t = (X̄ − μ0) / (s / √n)",
        calculator="",
        based_on="講義 2.7.2。樣本平均、標準差與樣本數是新數值，已重算。",
    )

    # --- 2.8 ---
    add_item(
        qid="VAR-2.8-01",
        topic_id="2.8", topic_en="Parametric versus Nonparametric Tests", topic_zh="母數與無母數檢定",
        subtopic="2.8 When a nonparametric test is used｜何時使用無母數檢定",
        qtype="Application", level="L2 Standard",
        stem="An analyst wants to test a single mean. The return data contain many outliers, and the distributional assumptions of a t test are not met. The appropriate substitute named in the Study Book is:",
        choices={
            "A": "an F test of two variances, because outliers inflate variance.",
            "B": "the Wilcoxon signed-rank test.",
            "C": "a Pearson correlation test, because correlation is unaffected by outliers.",
        },
        correct="B",
        reasoning="講義把單一平均數的 z 或 t，對應到 Wilcoxon 符號等級檢定。異常值很多或分配假設不成立時，改用無母數檢定。",
        steps="F 檢定的是兩個變異數。Pearson 相關不是單一平均數的替代，而且異常值正是改用等級方法的理由之一。",
        final_answer="B",
        why_wrong={
            "A": "F 檢定比較的是兩個樣本變異數，不是單一平均數。",
            "C": "Pearson 相關檢定的是線性相關，而且它是母數方法。等級相關才是它的無母數替代。",
        },
        zh="單一平均數、分配假設站不住、異常值很多，講義給的替代是 Wilcoxon 符號等級檢定。",
        core_idea="For a single mean, the nonparametric substitute is the Wilcoxon signed-rank test.",
        formula="Parametric single mean → Wilcoxon signed-rank.",
        based_on="講義 2.8 的對照表。情境改成報酬資料有很多異常值。",
    )
    add_numeric(
        qid="VAR-2.8-02",
        topic_id="2.8", topic_en="Parametric versus Nonparametric Tests", topic_zh="母數與無母數檢定",
        subtopic="2.8 Rank ties and Spearman correlation｜名次並列與等級相關",
        qtype="Calculation", level="L2 Standard",
        stem="Two observations tie for the Spearman ranks that would otherwise have been 6 and 7. The rank assigned to each tied observation is closest to:",
        true=Decimal("6.5"),
        raw={"A": Decimal("6.5"), "B": Decimal("6.0"), "C": Decimal("7.0")},
        correct="A", places=1, render=plain_render(1),
        why_templates={
            "B": "把並列的兩個觀察值都編成較小的名次 6，沒有平均。",
            "C": "把兩個都編成較大的名次 7。講義是取所跨名次的平均。",
        },
        reasoning="名次並列時，每個觀察值都取得它們所跨名次的平均。",
        steps="名次 6 和 7 的平均 = (6 + 7) / 2 = 6.5。下一個觀察值接著用名次 8。",
        zh="兩筆並列就平均那兩個名次。講義的例子是名次 3 和 4 得到 3.5；這裡是 6 和 7，所以是 6.5。",
        core_idea="Tied ranks each receive the average of the ranks they span.",
        formula="Two-way tie at ranks j and j+1 → (2j+1)/2 each.",
        calculator="",
        based_on="講義 2.8。原例子是名次 3 與 4；這一題改成 6 與 7 後重算。",
    )

    # --- 2.9 ---
    r2 = Decimal("0.36")
    corr = r2.sqrt()
    add_numeric(
        qid="VAR-2.9-01",
        topic_id="2.9", topic_en="Simple Linear Regression", topic_zh="簡單線性迴歸",
        subtopic="2.9.1 Fit: SST, SSR, SSE, and R²｜配適度",
        qtype="Calculation", level="L2 Standard",
        stem="A simple linear regression has R² = 0.36 and a positive slope. The correlation between X and Y is closest to:",
        true=corr,
        raw={"A": r2, "B": -corr, "C": corr},
        correct="C", places=2, render=plain_render(2),
        why_templates={
            "A": "把 R² 本身 0.36 當成相關係數。斜率為正時，相關是 R² 的正平方根。",
            "B": "平方根的符號用反了。題目的斜率是正的，相關也是正的。",
        },
        reasoning="R² 是 Y 的變異中被這條直線解釋的比例。斜率為正時，相關係數是它的正平方根。",
        steps="√0.36 = 0.60。斜率為正，所以相關是 +0.60，不是 −0.60，也不是 0.36。",
        zh="0.36 是解釋比例，不是相關，也不是 X 造成 Y 的機率。",
        core_idea="With a positive slope, correlation = √R². With a negative slope, use the negative root.",
        formula="If b1 > 0, ρ = √R².",
        calculator="",
        based_on="講義 2.9.1；同一關係見 QM-163，但那題斜率為負。這裡改成正斜率與 R²=0.36。",
    )
    add_item(
        qid="VAR-2.9-02",
        topic_id="2.9", topic_en="Simple Linear Regression", topic_zh="簡單線性迴歸",
        subtopic="2.9.3 Testing the Slope｜斜率檢定",
        qtype="Calculation", level="L3 Trap",
        stem="An SLR slope estimate is 0.28 with standard error 0.10. The hypothesized slope is 0. The two-sided 5% critical t is given as 2.201. The researcher should:",
        choices={
            "A": "reject H0: b1 = 0, because |0.28 / 0.10| = 2.80, which is greater than 2.201.",
            "B": "fail to reject H0, because 0.28 is less than 2.201.",
            "C": "reject H0, because 0.28 is greater than 0.05.",
        },
        correct="A",
        reasoning="t = (估計斜率 − 0) / 斜率標準誤 = 0.28 / 0.10 = 2.80。2.80 大於題目給定的臨界值 2.201，所以拒絕斜率為 0。",
        steps="t = 2.80。決策比較的是 t 和 2.201，不是斜率和臨界值，也不是斜率和 α。",
        final_answer="A",
        why_wrong={
            "B": "拿斜率 0.28 去比臨界值 2.201，少除了標準誤。",
            "C": "拿斜率去比顯著水準 0.05。α 不是這個比較的對象。",
        },
        zh="檢驗用的是 t 統計量。臨界值 2.201 是題目給定的，用來和 2.80 比較。",
        core_idea="t = (b̂1 − B1) / s_b̂1. Compare that t with the critical value, not the slope with α.",
        formula="t = (b̂1 − B1) / s_b̂1",
        based_on="講義 2.9.3 的即時檢查；同一錯誤型態見 QM-167。斜率、標準誤與給定臨界值已更換，t 已重算。",
    )

    # --- 2.10 ---
    add_item(
        qid="VAR-2.10-01",
        topic_id="2.10", topic_en="Introduction to Big Data Techniques", topic_zh="大數據技術概論",
        subtopic="2.10 Overfitting and learning types｜過度配適與學習類型",
        qtype="Application", level="L2 Standard",
        stem="A model reproduces idiosyncrasies of the training sample and then performs poorly on a validation sample. This failure is most accurately described as:",
        choices={
            "A": "underfitting, because any miss on a validation sample means the model is too simple.",
            "B": "overfitting.",
            "C": "curation, because the validation sample must have been cleaned too aggressively.",
        },
        correct="B",
        reasoning="過度配適是模型貼得太緊，連樣本本身的特殊起伏都配進去，所以換到驗證樣本就失準。配適不足是另一種失敗。",
        steps="講義列出的兩個失敗是 overfitting 與 underfitting。curation 是資料處理裡的清理步驟，不是這個失敗的名稱。",
        final_answer="B",
        why_wrong={
            "A": "驗證樣本失準不一定是模型太簡單。題目說它把訓練樣本的特殊起伏也配進去了。",
            "C": "清理資料是 curation。它不是「訓練很貼、驗證很差」的名稱。",
        },
        zh="訓練樣本配得太緊、驗證樣本失敗，是過度配適。",
        core_idea="Overfitting means the model is too tightly fitted to the sample.",
        formula="Overfitting: too tight to the training sample. Underfitting is the other named failure.",
        based_on="講義 2.10；同一觀念見 QM-114。問法改成訓練與驗證的對照。",
    )
    add_item(
        qid="VAR-2.10-02",
        topic_id="2.10", topic_en="Introduction to Big Data Techniques", topic_zh="大數據技術概論",
        subtopic="2.10 Data processing and visualization｜資料處理與視覺化",
        qtype="Recognition", level="L2 Standard",
        stem="In the Study Book’s data-processing path, curation is most accurately:",
        choices={
            "A": "deleting all unstructured text before a model is trained.",
            "B": "cleaning data for quality.",
            "C": "interpreting human language, including translation.",
        },
        correct="B",
        reasoning="講義的處理順序是 capture、curation、storage、search、transfer。curation 是為了品質而清理。解釋人類語言是自然語言處理。",
        steps="標籤雲用文字大小表示重要性。自然語言處理包含翻譯。兩者都不是 curation 的定義。",
        final_answer="B",
        why_wrong={
            "A": "講義沒有把 curation 定義成刪除所有非結構化文字。文字分析仍然在資料科學的工具裡。",
            "C": "這是自然語言處理，不是 curation。",
        },
        zh="curation 是清理資料品質。翻譯和理解語言是 NLP。",
        core_idea="Processing runs through capture, curation, storage, search, and transfer. Curation cleans for quality.",
        formula="Capture → curation → storage → search → transfer.",
        based_on="講義 2.10；同一流程見 QM-115。這一題只問 curation 的定義。",
    )


def main() -> None:
    build()
    # Questions must not carry the correct letter.
    for question in QUESTIONS:
        if "correct" in question:
            raise RuntimeError(question["id"])
    (DATA / "variant_questions.json").write_text(json.dumps(QUESTIONS, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA / "variant_solutions.json").write_text(json.dumps(SOLUTIONS, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"variants {len(QUESTIONS)}")
    for question, solution in zip(QUESTIONS, SOLUTIONS):
        print(f"{question['id']} {solution['correct']} {solution['final_answer']}")


if __name__ == "__main__":
    main()
