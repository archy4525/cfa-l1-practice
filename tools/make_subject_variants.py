"""Verified calculation variants for subjects other than Quantitative Methods.

Each item uses new inputs and is recomputed in this file. A displayed choice is
kept only when the rounded true value is unique and strictly closest to the
correct choice. Concept variants are not generated: stacking a second question
on the original stem, or treating a rejected option as globally false, does not
leave one defensible answer. QM variants stay in variant_questions.json.
"""

from __future__ import annotations

import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def qplace(places: int) -> Decimal:
    return Decimal(1).scaleb(-places)


def rhu(value: Decimal, places: int) -> Decimal:
    return Decimal(value).quantize(qplace(places), rounding=ROUND_HALF_UP)


def show(value: Decimal, places: int, suffix: str = "") -> str:
    return f"{rhu(value, places):,.{places}f}{suffix}"


def require_unique(true: Decimal, raw: dict[str, Decimal], correct: str, places: int, label: str) -> None:
    shown = {letter: rhu(value, places) for letter, value in raw.items()}
    if len(set(shown.values())) != 3:
        raise RuntimeError(f"{label}: displayed choices overlap {shown}")
    if shown[correct] != rhu(true, places):
        raise RuntimeError(f"{label}: {shown[correct]} != {rhu(true, places)}")
    for letter, value in raw.items():
        if letter != correct and abs(true - raw[correct]) >= abs(true - value):
            raise RuntimeError(f"{label}: true value is not strictly closest to {correct}")


def blank_question(meta: dict, qid: str, subtopic: str, qtype: str, level: str, stem: str, choices: dict[str, str], based_on: str) -> dict:
    return {
        "id": qid,
        "origin": "variant",
        "topic_id": meta["study_section"],
        "topic_en": meta["title_en"],
        "topic_zh": meta["title_zh"],
        "subtopic": subtopic,
        "qtype": qtype,
        "level": level,
        "stem": stem,
        "choices": choices,
        "source": {
            "question_pdf": "new inputs or a new question angle; the underlying relation is from this project's files",
            "question_ref": qid,
            "study_pdf": "CFA_L1_Study_Book_FINAL_2026.pdf",
            "study_chapter": meta["source_chapter"],
            "study_section": subtopic,
            "answer_pdf": "the subject answer book for the original item",
            "based_on": based_on,
        },
    }


def blank_solution(qid: str, meta: dict, subtopic: str, correct: str, reasoning: str, steps: str, final_answer: str, why: dict, zh: str, core: str, formula: str, based_on: str) -> dict:
    return {
        "id": qid,
        "correct": correct,
        "reasoning": reasoning,
        "steps": steps,
        "final_answer": final_answer,
        "why_wrong": why,
        "zh": zh,
        "core_idea": core,
        "study_section": subtopic,
        "formula": formula,
        "exam_trap": "",
        "calculator": "",
        "source_note": "這題使用新的數字，並在本專案依講義裡的同一條關係重新計算。",
        "topic_id": meta["study_section"],
        "subtopic": subtopic,
        "based_on": based_on,
    }


def numeric_item(meta: dict, number: int, subtopic: str, stem: str, choices: dict[str, str], correct: str, steps: str, final_answer: str, why: dict, zh: str, core: str, formula: str, based_on: str) -> tuple[dict, dict]:
    qid = f"VAR-{meta['subject_id']}-{meta['study_section']}-{number:02d}"
    return (
        blank_question(meta, qid, subtopic, "Calculation", "L2 Standard", stem, choices, based_on),
        blank_solution(qid, meta, subtopic, correct, steps, steps, final_answer, why, zh, core, formula, based_on),
    )


def build_numeric(topics: dict) -> list[tuple[dict, dict]]:
    items = []

    def add(topic_id: str, **kwargs) -> None:
        items.append(numeric_item(topics[topic_id], 2, **kwargs))

    # HHI
    shares = [Decimal(40), Decimal(30), Decimal(20), Decimal(10)]
    hhi = sum(part ** 2 for part in shares)
    raw = {"A": Decimal(100), "B": Decimal(1600), "C": hhi}
    require_unique(hhi, raw, "C", 0, "HHI")
    add(
        "3.5",
        subtopic="3.5 Monopoly and Concentration｜獨占與集中度",
        stem="Four firms have market shares of 40%, 30%, 20%, and 10%. Using percentage points, the Herfindahl–Hirschman Index is closest to:",
        choices={"A": "100", "B": "1,600", "C": "3,000"},
        correct="C",
        steps="40²+30²+20²+10² = 1,600+900+400+100 = 3,000。100 只是市占率相加。1,600 只平方了最大的那一家。",
        final_answer="3,000",
        why={"A": "Adds the shares instead of summing squared percentage points.", "B": "Squares only the largest share."},
        zh="HHI 是每家市占率（百分點）的平方和，不是市占率直接相加。",
        core="HHI sums squared market-share percentage points",
        formula="HHI = Σ (share in percentage points)²",
        based_on="ECO-028",
    )

    injection = Decimal(100)
    mpc = Decimal("0.80")
    first = (1 - mpc) * injection
    require_unique(first, {"A": first, "B": mpc * injection, "C": injection}, "A", 0, "AD")
    add(
        "3.9",
        subtopic="3.9 Fiscal Policy｜財政政策",
        stem="Government spending on domestic goods rises by 100 and is financed by an equal tax increase. The marginal propensity to consume is 0.80. The first-round change in aggregate demand is closest to:",
        choices={"A": "20", "B": "80", "C": "100"},
        correct="A",
        steps="第一輪是 (1−0.80)×100 = 20。80 是被稅收拿走的消費。100 是政府支出本身，沒有扣掉增稅。",
        final_answer="20",
        why={"B": "This is the consumption cut, not the net first-round change.", "C": "This is the spending increase before the tax effect."},
        zh="平衡預算的第一輪需求變化是 (1−MPC)×ΔG，不是整筆政府支出。",
        core="Balanced-budget first round is (1−MPC) times the spending increase",
        formula="ΔAD1 = (1−c)ΔG",
        based_on="ECO-056",
    )

    neutral = Decimal("3.0") + Decimal("2.5")
    policy = Decimal("6.5")
    add(
        "3.10",
        subtopic="3.10 Monetary Policy｜貨幣政策",
        stem="Long-run trend real growth is 3.0% and long-run expected inflation is 2.5%. The policy rate is 6.5%. Relative to the neutral rate in the notes, policy is:",
        choices={"A": "tight, because 6.5% is above the 5.5% neutral rate.", "B": "neutral, because the policy rate equals trend growth plus inflation.", "C": "loose, because any positive policy rate is stimulative."},
        correct="A",
        steps="中性利率 = 3.0% + 2.5% = 5.5%。政策利率 6.5% 高於 5.5%，所以偏緊。",
        final_answer="tight; neutral rate 5.5%",
        why={"B": "3.0% + 2.5% is 5.5%, not 6.5%.", "C": "The notes compare the policy rate with the neutral rate; a positive rate is not automatically loose."},
        zh="中性利率是長期實質成長加長期預期通膨。政策利率高於中性利率就是偏緊。",
        core="Neutral rate = trend real growth + expected inflation",
        formula="rneutral = gtrend + πe",
        based_on="ECO-067",
    )

    change = Decimal("1.08") / Decimal("1.20") - 1
    reverse = Decimal("1.20") / Decimal("1.08") - 1
    difference = Decimal("-0.12")
    require_unique(change, {"A": change, "B": difference, "C": reverse}, "A", 4, "FX")
    add(
        "3.16",
        subtopic="3.16 Quotes, participants, and the real rate",
        stem="USD/EUR falls from 1.20 to 1.08. The percentage change in the euro is closest to:",
        choices={"A": "-10.00%", "B": "-12.00%", "C": "11.11%"},
        correct="A",
        steps="1.08/1.20 − 1 = 0.90 − 1 = −10.00%。−12% 是兩個報價直接相減。11.11% 是把期初和期末對調。",
        final_answer="-10.00%",
        why={"B": "Subtracts the quotes instead of dividing.", "C": "Divides the old quote by the new quote."},
        zh="報價變動百分比是新報價除以期初報價再減 1。",
        core="Percentage change in the quote is S1/S0 − 1",
        formula="S1/S0 − 1",
        based_on="ECO-100",
    )

    forward = Decimal("1.2500") * Decimal("1.05") / Decimal("1.03")
    flipped = Decimal("1.2500") * Decimal("1.03") / Decimal("1.05")
    additive = Decimal("1.2500") * Decimal("1.02")
    require_unique(forward, {"A": flipped, "B": forward, "C": additive}, "B", 4, "FWD")
    add(
        "3.17",
        subtopic="3.17 Forwards and Covered Interest｜遠期與拋補利率",
        stem="The spot quote S_f/d is 1.2500. The domestic risk-free rate is 3% and the foreign risk-free rate is 5%, each for a full year. The no-arbitrage forward F_f/d is closest to:",
        choices={"A": show(flipped, 4), "B": show(forward, 4), "C": show(additive, 4)},
        correct="B",
        steps=f"F = 1.2500 × 1.05 / 1.03 = {show(forward, 4)}。A 把本國與外國利率放反。C 只用利率差去乘。",
        final_answer=show(forward, 4),
        why={"A": "Swaps the foreign and domestic rates.", "C": "Adds the rate spread instead of using the covered-interest ratio."},
        zh="無套利遠期是即期乘上 (1+外國利率)/(1+本國利率)。",
        core="F_f/d = S_f/d × (1+rf)/(1+rd)",
        formula="Ff/d = Sf/d(1+rf)/(1+rd)",
        based_on="ECO-109",
    )

    trade = (Decimal(90) - Decimal(140)) + (Decimal(35) - Decimal(50))
    saving_only = Decimal(90) - Decimal(140)
    flipped_gov = (Decimal(90) - Decimal(140)) - (Decimal(35) - Decimal(50))
    require_unique(trade, {"A": saving_only, "B": trade, "C": flipped_gov}, "B", 0, "TB")
    add(
        "3.18",
        subtopic="3.18 Regimes and the trade balance",
        stem="Private saving is 90, investment is 140, taxes net of transfers are 35, and government spending is 50. Using X−M = (S−I)+(T−G), the trade balance is closest to:",
        choices={"A": "-50", "B": "-65", "C": "-35"},
        correct="B",
        steps="(90−140)+(35−50) = −50 + −15 = −65。−50 只算了儲蓄減投資。−35 把政府餘額的符號放反。",
        final_answer="-65",
        why={"A": "Uses only S−I.", "C": "Subtracts the government balance instead of adding it."},
        zh="貿易餘額是民間儲蓄缺口加上政府餘額。",
        core="X−M = (S−I)+(T−G)",
        formula="X−M=(S−I)+(T−G)",
        based_on="ECO-119",
    )

    ccc = Decimal(40) + Decimal(25) - Decimal(20)
    add(
        "4.4",
        subtopic="4.4 Liquidity｜流動性",
        stem="A firm has 40 days of inventory, 25 days of receivables, and 20 days of payables. The cash conversion cycle is closest to:",
        choices={"A": "65 days", "B": "45 days", "C": "20 days"},
        correct="B",
        steps="營業週期 = 40+25 = 65。現金轉換週期 = 65−20 = 45。",
        final_answer="45 days",
        why={"A": "Stops at the operating cycle and does not subtract payables.", "C": "Reports payables alone."},
        zh="現金轉換週期是存貨天數加應收天數，再減應付天數。",
        core="CCC = inventory days + receivable days − payable days",
        formula="CCC = DOH + DSO − DPO",
        based_on="CI-025",
    )

    incremental = (Decimal(20) - Decimal(6)) * Decimal("0.70")
    require_unique(incremental, {"A": Decimal(20) * Decimal("0.70"), "B": incremental, "C": (Decimal(20) - Decimal(6)) * Decimal("0.30")}, "B", 1, "CF")
    add(
        "4.5",
        subtopic="4.5 Capital Allocation｜資本配置",
        stem="New-product pretax cash is 20 per year. The launch diverts old-product pretax cash of 6 per year. The tax rate is 30%. No other externalities. Annual incremental after-tax operating cash is closest to:",
        choices={"A": "14.0", "B": "9.8", "C": "4.2"},
        correct="B",
        steps="增量稅前 = 20−6 = 14。稅後 = 14×(1−0.30) = 9.8。14 沒有扣稅。4.2 用了稅率而不是 (1−稅率)。",
        final_answer="9.8",
        why={"A": "Taxes the new product only and ignores the diverted cash.", "C": "Multiplies the incremental pretax cash by the tax rate."},
        zh="增量稅後現金是 (新產品稅前 − 被排擠的舊產品稅前) × (1−稅率)。",
        core="Incremental after-tax cash uses the lost old cash flow and one minus the tax rate",
        formula="CF = (1−t)(new pretax − lost old pretax)",
        based_on="CI-042",
    )

    wacc = Decimal("0.20") * Decimal("8") * Decimal("0.75") + Decimal("0.80") * Decimal("11")
    pretax = Decimal("0.20") * Decimal("8") + Decimal("0.80") * Decimal("11")
    require_unique(wacc, {"A": pretax, "B": wacc, "C": Decimal(11)}, "B", 2, "WACC")
    add(
        "4.6",
        subtopic="4.6 Cost of Capital｜資金成本",
        stem="Market values are debt 40 and equity 160. There is no preferred stock. The market yield on debt is 8%, the tax rate is 25%, and the cost of equity is 11%. WACC is closest to:",
        choices={"A": show(pretax, 2, "%"), "B": show(wacc, 2, "%"), "C": "11.00%"},
        correct="B",
        steps="權重用市值：負債 40/200 = 0.20，權益 0.80。稅後負債成本 = 8%×(1−0.25) = 6%。WACC = 0.20×6% + 0.80×11% = 10.00%。",
        final_answer=show(wacc, 2, "%"),
        why={"A": "Uses the pretax yield on debt.", "C": "Uses the cost of equity alone."},
        zh="WACC 用市值權重，負債成本要乘 (1−稅率)。",
        core="WACC = wd×rd×(1−t) + we×re",
        formula="rWACC = wd rd (1−t) + we re",
        based_on="CI-089",
    )

    re_mm = Decimal(10) + (Decimal(10) - Decimal(6)) * Decimal("0.50")
    require_unique(re_mm, {"A": Decimal(10), "B": re_mm, "C": Decimal(10) + Decimal(6) * Decimal("0.50")}, "B", 1, "MM")
    add(
        "4.7",
        subtopic="4.7 Capital Structure｜資本結構",
        stem="Assume MM with no taxes. r0 is 10%, rd is 6%, and D/E is 0.50. The cost of equity is closest to:",
        choices={"A": "10.0%", "B": "12.0%", "C": "13.0%"},
        correct="B",
        steps="re = 10% + (10%−6%)×0.50 = 12.0%。10% 是無槓桿成本。13% 用了 rd 而不是 (r0−rd)。",
        final_answer="12.0%",
        why={"A": "Reports the unlevered cost of capital.", "C": "Adds rd×D/E instead of (r0−rd)×D/E."},
        zh="沒有稅的 MM 裡，權益成本 = r0 + (r0−rd)×D/E。",
        core="re = r0 + (r0−rd)(D/E) when taxes are zero",
        formula="re = r0 + (r0−rd)D/E",
        based_on="CI-109",
    )

    fifo = Decimal(5000) + Decimal(600)
    add(
        "5.4",
        subtopic="5.4 Inventory｜存貨",
        stem="LIFO inventory is 5,000 and the LIFO reserve is 600. FIFO inventory is closest to:",
        choices={"A": "4,400", "B": "5,000", "C": "5,600"},
        correct="C",
        steps="FIFO 存貨 = LIFO 存貨 + LIFO reserve = 5,000 + 600 = 5,600。",
        final_answer="5,600",
        why={"A": "Subtracts the reserve.", "B": "Leaves the inventory on the LIFO carrying amount."},
        zh="FIFO 存貨 = LIFO 存貨 + LIFO reserve。",
        core="LIFO reserve = FIFO inventory − LIFO inventory",
        formula="FIFO inventory = LIFO inventory + LIFO reserve",
        based_on="FSA-063",
    )

    ddb = Decimal(2) * (Decimal(1) / Decimal(4)) * Decimal(8000)
    straight = (Decimal(8000) - Decimal(500)) / Decimal(4)
    half = ddb / 2
    require_unique(ddb, {"A": straight, "B": half, "C": ddb}, "C", 0, "DDB")
    add(
        "5.5",
        subtopic="5.5 Long-Lived Assets and Intangibles｜長期資產與無形資產",
        stem="Cost is 8,000, salvage is 500, and the life is four years. Year-1 double-declining-balance depreciation is closest to:",
        choices={"A": show(straight, 0), "B": show(half, 0), "C": show(ddb, 0)},
        correct="C",
        steps="直線率 = 1/4 = 25%，雙倍餘額遞減率 = 50%。第 1 年 = 0.50×8,000 = 4,000。帳面 4,000 仍高於殘值 500，不受殘值下限約束。",
        final_answer="4,000",
        why={"A": "Uses straight-line depreciation of (cost−salvage)/life.", "B": "Uses the straight-line rate on cost, not the doubled rate."},
        zh="雙倍餘額遞減第 1 年是 2×(1/n)×成本，殘值只在帳面碰到下限時才限制。",
        core="DDB year 1 = 2 × (1/n) × opening carrying amount",
        formula="DDBt = 2 × (1/n) × carrying amount",
        based_on="FSA-085",
    )

    net_liability = Decimal(2100) - Decimal(1800)
    add(
        "5.8",
        subtopic="5.8 Pensions and Share-Based Compensation｜退休金與股份基礎酬勞",
        stem="Plan assets are 1,800 at fair value and the present value of the defined-benefit obligation is 2,100. The balance sheet reports:",
        choices={"A": "a net pension liability of 300.", "B": "a net pension asset of 300.", "C": "a pension amount of 3,900."},
        correct="A",
        steps="2,100 − 1,800 = 300，義務較大，所以是淨負債 300。3,900 是兩者相加。",
        final_answer="net liability 300",
        why={"B": "Reverses the sign: assets are below the obligation.", "C": "Adds the two amounts instead of netting them."},
        zh="淨退休金負債 = 義務現值 − 計畫資產公允價值。",
        core="Net pension liability when the obligation exceeds plan assets",
        formula="Net pension = plan assets − PV(obligation)",
        based_on="FSA-138",
    )

    collected = Decimal(900) - Decimal(40)
    add(
        "5.9",
        subtopic="5.9 Cash Flows and How the Statements Connect｜現金流量與報表勾稽",
        stem="Revenue is 900 and accounts receivable increase by 40. Cash collected from customers is closest to:",
        choices={"A": "860", "B": "900", "C": "940"},
        correct="A",
        steps="向客戶收現 = 收入 − 應收增加 = 900 − 40 = 860。",
        final_answer="860",
        why={"B": "Stops at revenue.", "C": "Adds the receivable increase."},
        zh="應收增加代表有一部分收入還沒收到現金。",
        core="Cash from customers = revenue − increase in receivables",
        formula="Cash from customers = Revenue − ΔAR",
        based_on="FSA-155",
    )

    daily = Decimal(730) / Decimal(365)
    interval = Decimal(120) / daily
    require_unique(interval, {"A": interval, "B": Decimal(730) / Decimal(120), "C": Decimal(120)}, "A", 0, "DI")
    add(
        "5.11",
        subtopic="5.11 Ratio Analysis｜比率分析",
        stem="Cash, short-term securities, and receivables total 120. Annual cash operating expenditure is 730. Using 365 days, the defensive interval is closest to:",
        choices={"A": "60 days", "B": "6 days", "C": "120 days"},
        correct="A",
        steps="每日現金支出 = 730/365 = 2。防衛區間 = 120/2 = 60 天。",
        final_answer="60 days",
        why={"B": "Divides annual expenditure by liquid assets and ignores the day count.", "C": "Reports the liquid-asset balance."},
        zh="防衛區間 = 流動資產 / (全年現金支出 / 365)。",
        core="Defensive interval = liquid assets / daily cash expenditure",
        formula="Defensive interval = liquid assets / (cash expenses/365)",
        based_on="FSA-182",
    )

    equity = Decimal(3000)
    margin = equity / Decimal(8000)
    require_unique(margin, {"A": Decimal("0.50"), "B": margin, "C": equity / Decimal(10000)}, "B", 3, "MARGIN")
    add(
        "6.1",
        subtopic="6.1 Market Organization and Structure｜市場組織與結構",
        stem="An investor buys 200 shares at 50. The initial margin requirement is 50%, and the loan balance does not change. The price then falls to 40. The margin percentage is closest to:",
        choices={"A": "50.0%", "B": "37.5%", "C": "30.0%"},
        correct="B",
        steps="最初市值 10,000，自有資金 5,000，借款 5,000。現在市值 8,000，權益 = 8,000−5,000 = 3,000。保證金比例 = 3,000/8,000 = 37.5%。",
        final_answer="37.5%",
        why={"A": "Repeats the initial margin.", "C": "Divides current equity by the original market value."},
        zh="保證金比例是目前權益除以目前市值。借款餘額不變時，跌價會同時降低權益和市值。",
        core="Margin percentage = equity / current market value",
        formula="equity = current market value − loan",
        based_on="EQ-008",
    )

    level = Decimal(400) * Decimal("1.10") * Decimal("0.95")
    add(
        "6.2",
        subtopic="6.2 Security Market Indexes｜證券市場指數",
        stem="A total-return index starts at 400. Year 1 total return is 10% and Year 2 total return is −5%. The index level at the end of Year 2 is closest to:",
        choices={"A": "418.00", "B": "420.00", "C": "440.00"},
        correct="A",
        steps="400×1.10 = 440。440×0.95 = 418。420 是把兩年報酬相加後再乘。440 停在第 1 年。",
        final_answer="418.00",
        why={"B": "Adds the returns, 10%−5%, instead of compounding.", "C": "Stops after the first year."},
        zh="總報酬指數要逐年連乘，負報酬用 (1+報酬) 而不是把百分比相加。",
        core="Total-return index compounds each period's total return",
        formula="Level_T = Level_0 × (1+R1) × (1+R2)",
        based_on="EQ-030",
    )

    variable = Decimal("0.04") / Decimal("0.10")
    require_unique(variable, {"A": variable, "B": 1 - variable, "C": Decimal("0.10") / Decimal("0.04")}, "A", 2, "VC")
    add(
        "6.5",
        subtopic="6.5 Industry and Company Analysis｜產業與公司分析",
        stem="Revenue rises 10%. Cost of revenue plus operating expenses rises 4%. The notes’ simple variable-cost estimate is closest to:",
        choices={"A": "0.40", "B": "0.60", "C": "2.50"},
        correct="A",
        steps="變動成本估計 = 4% / 10% = 0.40。",
        final_answer="0.40",
        why={"B": "Reports one minus that ratio.", "C": "Divides the revenue change by the cost change."},
        zh="講義的簡單變動成本估計是成本變動百分比除以收入變動百分比。",
        core="Variable-cost estimate = percent change in costs / percent change in revenue",
        formula="%Δ(cost of revenue + opex) / %Δrevenue",
        based_on="EQ-112",
    )

    preferred = Decimal("3.00") / Decimal("0.08")
    add(
        "6.6",
        subtopic="6.6 Equity Valuation｜權益估值",
        stem="A preferred share has par 50 and a 6% annual dividend that does not grow. The required return on similar preferred is 8%. Intrinsic value is closest to:",
        choices={"A": "37.50", "B": "50.00", "C": "4.00"},
        correct="A",
        steps="股利 = 0.06×50 = 3.00。因為不成長，V0 = 3.00/0.08 = 37.50。",
        final_answer="37.50",
        why={"B": "Reports par.", "C": "Multiplies par by the required return."},
        zh="固定股利、沒有到期日的特別股，價值是股利除以要求報酬率。",
        core="Perpetual preferred value = dividend / required return",
        formula="V0 = D / r",
        based_on="EQ-119",
    )

    repo = Decimal(100) * (1 + Decimal("0.036") * Decimal(45) / Decimal(360))
    year_rate = Decimal(100) * Decimal("1.036")
    day_365 = Decimal(100) * (1 + Decimal("0.036") * Decimal(45) / Decimal(365))
    require_unique(repo, {"A": repo, "B": year_rate, "C": day_365}, "A", 2, "REPO")
    add(
        "7.1",
        subtopic="7.1 Issuance, Markets, and Credit Labels｜發行、市場與信用標籤",
        stem="A dealer sells a note today for 100 and agrees to repurchase it in 45 days. The repo rate is 3.60% on a 360-day year. The repurchase price is closest to:",
        choices={"A": show(repo, 2), "B": show(year_rate, 2), "C": show(day_365, 2)},
        correct="A",
        steps="利息因子 = 0.036×45/360 = 0.0045。買回價格 = 100×1.0045 = 100.45。",
        final_answer=show(repo, 2),
        why={"B": "Applies the annual rate to the whole year.", "C": "Uses a 365-day year."},
        zh="附買回價格 = 賣價 × [1 + 利率 × 天數/360]。",
        core="Repurchase price uses the stated day-count fraction",
        formula="Repurchase price = P0 × [1 + repo rate × days/360]",
        based_on="FI-019",
    )

    def bond_price(coupon: Decimal, ytm: Decimal, years: int) -> Decimal:
        total = Decimal(0)
        for t in range(1, years + 1):
            cash = coupon if t < years else coupon + Decimal(100)
            total += cash / (1 + ytm) ** t
        return total

    price = bond_price(Decimal(4), Decimal("0.06"), 3)
    principal_only = Decimal(100) / (Decimal("1.06") ** 3)
    require_unique(price, {"A": principal_only, "B": price, "C": Decimal(100)}, "B", 2, "BOND")
    add(
        "7.2",
        subtopic="7.2 Valuation and Yields｜評價與殖利率",
        stem="A 3-year annual-pay bond has a 4% coupon, par 100, and a yield to maturity of 6%. There is no accrued interest. The price is closest to:",
        choices={"A": show(principal_only, 2), "B": show(price, 2), "C": "100.00"},
        correct="B",
        steps=f"價格 = 4/1.06 + 4/1.06² + 104/1.06³ = {show(price, 2)}。",
        final_answer=show(price, 2),
        why={"A": "Discounts par only and omits the coupons.", "C": "Prices the bond at par, which would require the yield to equal the coupon."},
        zh="票息低於殖利率時，價格低於面額。每期現金流都要用殖利率折現。",
        core="Bond price is the present value of coupons and par at the yield",
        formula="PV of the coupon annuity plus PV of par",
        based_on="FI-031",
    )

    fwd = (Decimal("1.04") ** 3) / (Decimal("1.03") ** 2) - 1
    require_unique(fwd, {"A": Decimal("0.01"), "B": Decimal("0.035"), "C": fwd}, "C", 4, "IFR")
    add(
        "7.3",
        subtopic="7.3 Spot, Par, and Forward｜即期、平價與遠期利率",
        stem="The 2-year spot rate is 3.00% and the 3-year spot rate is 4.00%, both effective annual rates. The one-year forward two years from now is closest to:",
        choices={"A": "1.00%", "B": "3.50%", "C": show(fwd * 100, 2, "%")},
        correct="C",
        steps=f"(1.04)³/(1.03)² − 1 = {show(fwd * 100, 2, '%')}。1% 是兩個即期利率相減。3.50% 是兩者平均。",
        final_answer=show(fwd * 100, 2, "%"),
        why={"A": "Subtracts the spot rates.", "B": "Averages the spot rates."},
        zh="遠期利率由兩段即期利率的成長因子相除得出，不是相減或平均。",
        core="(1+z3)³ = (1+z2)² × (1+2y1y)",
        formula="(1+ZA)^A × (1+forward) = (1+ZB)^B",
        based_on="FI-101",
    )

    horizon = (Decimal(110) / Decimal(95)).sqrt() - 1
    simple = (Decimal(110) - Decimal(95)) / Decimal(2) / Decimal(95)
    holding = Decimal(110) / Decimal(95) - 1
    require_unique(horizon, {"A": horizon, "B": simple, "C": holding}, "A", 4, "HY")
    add(
        "7.4",
        subtopic="7.4 Interest-Rate Risk: Horizon, Duration, Convexity｜利率風險：投資期間、存續期間與凸性",
        stem="An investor pays 95 today. Over a 2-year horizon, reinvested coupons plus the sale price total 110. The annualized realized horizon yield is closest to:",
        choices={"A": show(horizon * 100, 2, "%"), "B": show(simple * 100, 2, "%"), "C": show(holding * 100, 2, "%")},
        correct="A",
        steps=f"(110/95)^(1/2) − 1 = {show(horizon * 100, 2, '%')}。",
        final_answer=show(horizon * 100, 2, "%"),
        why={"B": "Spreads the gain evenly without compounding.", "C": "Reports the two-year holding-period return."},
        zh="實現的期間殖利率是把整段持有報酬開根號成年化。",
        core="Horizon yield = (ending value / price)^(1/T) − 1",
        formula="r = (FV/PV)^(1/T) − 1",
        based_on="FI-115",
    )

    el = Decimal("0.02") * Decimal("0.40")
    add(
        "7.5",
        subtopic="7.5 Credit Analysis｜信用分析",
        stem="The probability of default is 2.00% and the loss given default is 40%. The expected-loss rate is closest to:",
        choices={"A": "0.80%", "B": "2.00%", "C": "42.00%"},
        correct="A",
        steps="預期損失率 = 2.00% × 40% = 0.80%。",
        final_answer="0.80%",
        why={"B": "Reports the probability of default alone.", "C": "Adds the two percentages."},
        zh="預期損失率 = 違約機率 × 違約損失率。",
        core="Expected-loss rate = PD × LGD",
        formula="EL rate = PD × LGD rate",
        based_on="FI-152",
    )

    add(
        "8.1",
        subtopic="8.1 Forwards and Futures｜遠期契約與期貨",
        stem="A long forward was initiated at 60. At maturity the spot price is 55. The long’s payoff is closest to:",
        choices={"A": "−5", "B": "5", "C": "0"},
        correct="A",
        steps="多方到期報酬 = 55 − 60 = −5。",
        final_answer="-5",
        why={"B": "Reverses the long’s sign.", "C": "Treats the contract as still worth zero at maturity."},
        zh="遠期多方到期價值是當時現貨減當初的遠期價格。",
        core="Long forward payoff at maturity = spot − forward price",
        formula="VT(T) = ST − F0(T)",
        based_on="DER-009",
    )

    add(
        "8.2",
        subtopic="8.2 Option payoffs and time value｜選擇權到期損益與時間價值",
        stem="An investor writes a call with strike 30 and receives a premium of 4. At expiration the underlying is 36. The writer’s profit is closest to:",
        choices={"A": "−6", "B": "−2", "C": "4"},
        correct="B",
        steps="賣權方的到期報酬 = −(36−30) = −6。利潤 = −6 + 4 = −2。",
        final_answer="-2",
        why={"A": "Stops at the payoff and ignores the premium received.", "C": "Reports the premium and ignores the payoff."},
        zh="賣出買權的利潤是收到的權利金減去到期時付給多方的內含價值。",
        core="Writer profit = premium − max(0, ST − strike)",
        formula="Profit = −max(0, ST−X) + premium",
        based_on="DER-054",
    )

    forward_price = Decimal(100) * (Decimal("1.05") ** Decimal("0.5"))
    full_year = Decimal(100) * Decimal("1.05")
    half_add = Decimal(100) * Decimal("1.025")
    require_unique(forward_price, {"A": forward_price, "B": half_add, "C": full_year}, "A", 2, "FPRICE")
    add(
        "8.4",
        subtopic="8.4 Arbitrage, carry, and forward pricing｜套利、持有成本與遠期定價",
        stem="A six-month forward is written on a non-dividend-paying share. Spot is 100. The risk-free rate is 5% with annual compounding. The no-arbitrage forward price is closest to:",
        choices={"A": show(forward_price, 2), "B": show(half_add, 2), "C": show(full_year, 2)},
        correct="A",
        steps=f"F = 100×(1.05)^0.5 = {show(forward_price, 2)}。",
        final_answer=show(forward_price, 2),
        why={"B": "Adds half of the annual rate instead of compounding for half a year.", "C": "Compounds for a full year."},
        zh="沒有股利時，遠期價格是現貨乘上 (1+年利率) 的期間次方。",
        core="F0(T) = S0(1+r)^T for a non-dividend share",
        formula="F0(T) = S0(1+r)^T",
        based_on="DER-100",
    )

    fra = Decimal("0.008") * Decimal(5000000) * Decimal("0.25")
    add(
        "8.5",
        subtopic="8.5 Interest-rate forwards and swaps｜利率遠期與交換契約",
        stem="A long FRA has notional 5,000,000 and covers a 90-day period counted as 90/360 of a year. The contract rate is 3.20%. At settlement the market reference rate is 4.00%. The long’s settlement amount, before any further discounting, is closest to:",
        choices={"A": "10,000", "B": "40,000", "C": "8,000"},
        correct="A",
        steps="利差 = 4.00%−3.20% = 0.80%。5,000,000×0.008 = 40,000 是一整年。再乘 90/360 = 10,000。",
        final_answer="10,000",
        why={"B": "Omits the 90/360 year fraction.", "C": "Uses 0.80% of a 1,000,000 notional."},
        zh="FRA 結算是 (參考利率−契約利率) × 名目本金 × 期間分數。",
        core="FRA settlement = (reference − contract) × notional × year fraction",
        formula="(MRR − IFR) × notional × period",
        based_on="DER-121",
    )

    put = Decimal("6") + Decimal(48) / Decimal("1.04") - Decimal(50)
    no_pv = Decimal(6) + Decimal(48) - Decimal(50)
    require_unique(put, {"A": put, "B": no_pv, "C": Decimal(6)}, "A", 2, "PARITY")
    add(
        "8.6",
        subtopic="8.6 Put-Call Parity and a One-Period Binomial｜買賣權平價與單期二元樹",
        stem="A non-dividend share is 50. A one-year European call with strike 48 costs 6. The risk-free rate is 4% with annual compounding. The European put with the same strike and expiration is closest to:",
        choices={"A": show(put, 2), "B": show(no_pv, 2), "C": "6.00"},
        correct="A",
        steps=f"履約價現值 = 48/1.04。賣權 = 6 + 48/1.04 − 50 = {show(put, 2)}。",
        final_answer=show(put, 2),
        why={"B": "Uses the strike instead of its present value.", "C": "Sets the put equal to the call."},
        zh="無股利歐式買賣權平價：賣權 = 買權 + 履約價現值 − 股價。",
        core="p0 = c0 + X/(1+r)^T − S0",
        formula="p0 = c0 + PV(X) − S0",
        based_on="DER-134",
    )

    investor = (Decimal(130) - Decimal(100) - Decimal("2.6") - Decimal(6)) / Decimal(100)
    omit_incentive = (Decimal(30) - Decimal("2.6")) / Decimal(100)
    gross = Decimal(30) / Decimal(100)
    require_unique(investor, {"A": investor, "B": omit_incentive, "C": gross}, "A", 3, "GP")
    add(
        "9.1",
        subtopic="9.1 Structures and Economics｜結構與經濟機制",
        stem="A fund begins the year at 100 and ends at 130 before fees. The management fee is 2% of ending value. The incentive fee is 20% of the gain and is calculated independently of the management fee. The investor’s return after both fees is closest to:",
        choices={"A": "21.4%", "B": "27.4%", "C": "30.0%"},
        correct="A",
        steps="管理費 = 130×0.02 = 2.6。激勵費 = 30×0.20 = 6。投資人報酬 = (30−2.6−6)/100 = 21.4%。",
        final_answer="21.4%",
        why={"B": "Subtracts only the management fee.", "C": "Ignores both fees."},
        zh="兩種費用各自計算時，投資人報酬要同時扣掉管理費和激勵費。",
        core="Investor return nets both the management fee and the incentive fee",
        formula="Return = (ending − beginning − fees) / beginning",
        based_on="AI-011",
    )

    add(
        "9.2",
        subtopic="9.2 Measuring Alternative Returns｜另類報酬衡量",
        stem="Realized value is 50, unrealized value is 30, and invested capital is 40. MOIC is closest to:",
        choices={"A": "1.25×", "B": "2.00×", "C": "1.00×"},
        correct="B",
        steps="MOIC = (50+30)/40 = 2.00×。",
        final_answer="2.00×",
        why={"A": "Uses realized value only.", "C": "Subtracts invested capital from the numerator."},
        zh="MOIC 的分子是已實現加未實現，分母是投入資本。",
        core="MOIC = (realized + unrealized) / invested capital",
        formula="MOIC = (realized value + unrealized value) / invested capital",
        based_on="AI-026",
    )

    add(
        "9.4",
        subtopic="9.4 Real Estate｜不動產",
        stem="Stabilized net operating income is 12 and the capitalization rate is 8%. The implied property value is closest to:",
        choices={"A": "96", "B": "150", "C": "15"},
        correct="B",
        steps="價值 = 12 / 0.08 = 150。",
        final_answer="150",
        why={"A": "Multiplies NOI by 8.", "C": "Divides NOI by 0.80."},
        zh="收益法的穩定價值 = NOI / 資本化率。",
        core="Value = NOI / capitalization rate",
        formula="Value = NOI / cap rate",
        based_on="AI-066",
    )

    futures = Decimal(40) * Decimal("1.05") + Decimal(2) - Decimal(1)
    add(
        "9.6",
        subtopic="9.6 Natural Resources and Commodities｜自然資源與商品",
        stem="Spot is 40. The risk-free return over the contract life is 5%. Storage cost is 2 and the convenience yield is 1, both in price units. Using the notes’ discrete form, the futures price is closest to:",
        choices={"A": "42", "B": "43", "C": "45"},
        correct="B",
        steps="40×1.05 = 42。加倉儲 2 得 44，再減便利收益 1 得 43。",
        final_answer="43",
        why={"A": "Stops at spot grown at the risk-free rate.", "C": "Adds the convenience yield instead of subtracting it."},
        zh="期貨價格 ≈ 現貨×(1+無風險利率) + 倉儲 − 便利收益。",
        core="Futures price adds storage and subtracts convenience yield",
        formula="F ≈ S(1+rf) + storage − convenience yield",
        based_on="AI-076",
    )

    ratio = Decimal(12) / Decimal(18)
    require_unique(ratio, {"A": ratio, "B": Decimal(18) / Decimal(12), "C": Decimal(6)}, "A", 2, "DIV")
    add(
        "10.1",
        subtopic="10.1 The Portfolio Perspective｜投資組合觀點",
        stem="The average stand-alone standard deviation is 18%. An equal-weighted portfolio of the same stocks has standard deviation 12%. The diversification ratio is closest to:",
        choices={"A": "0.67", "B": "1.50", "C": "6.00"},
        correct="A",
        steps="分散比率 = 12/18 = 0.67。",
        final_answer="0.67",
        why={"B": "Divides the stand-alone volatility by the portfolio volatility.", "C": "Subtracts the two standard deviations."},
        zh="分散比率 = 投資組合標準差 / 平均個股標準差。",
        core="Diversification ratio = portfolio standard deviation / average stand-alone standard deviation",
        formula="diversification ratio = σportfolio / σaverage security",
        based_on="PM-002",
    )

    port = Decimal("0.40") * Decimal(10) + Decimal("0.60") * Decimal(5)
    add(
        "10.2",
        subtopic="10.2 Risk, Return, and the Frontier｜風險、報酬與前緣",
        stem="A portfolio is 40% in an asset with expected return 10% and 60% in an asset with expected return 5%. The portfolio expected return is closest to:",
        choices={"A": "5.0%", "B": "7.0%", "C": "7.5%"},
        correct="B",
        steps="0.40×10% + 0.60×5% = 4.0% + 3.0% = 7.0%。",
        final_answer="7.0%",
        why={"A": "Reports the lower asset return.", "C": "Averages 10% and 5% without the weights."},
        zh="組合期望報酬是權重乘上各資產期望報酬的和。",
        core="Portfolio expected return is the value-weighted sum",
        formula="E(Rp) = w1 E(R1) + w2 E(R2)",
        based_on="PM-019",
    )

    sharpe = (Decimal(9) - Decimal(2)) / Decimal(14)
    require_unique(sharpe, {"A": sharpe, "B": Decimal(9) / Decimal(14), "C": Decimal(7) / Decimal(100)}, "A", 2, "CAL")
    add(
        "10.3",
        subtopic="10.3 CAL, CML, and Two-Fund Separation｜CAL、CML 與兩基金分離",
        stem="A fund has expected return 9% and standard deviation 14%. The risk-free rate is 2%. The slope of the capital allocation line that uses this fund is closest to:",
        choices={"A": "0.50", "B": "0.64", "C": "0.07"},
        correct="A",
        steps="斜率 = (9%−2%)/14% = 0.50。",
        final_answer="0.50",
        why={"B": "Divides the total expected return, not the excess return, by volatility.", "C": "Writes the excess return as 0.07 and does not divide by volatility."},
        zh="CAL 斜率是超額報酬除以標準差。",
        core="CAL slope = (E(R) − Rf) / σ",
        formula="Sharpe = (E(Ri) − Rf) / σi",
        based_on="PM-034",
    )

    variance = (Decimal("1.5") ** 2) * (Decimal("0.10") ** 2) + (Decimal("0.12") ** 2)
    total_sd = variance.sqrt()
    require_unique(total_sd, {"A": Decimal("0.15"), "B": total_sd, "C": Decimal("0.12")}, "B", 4, "BETA")
    add(
        "10.4",
        subtopic="10.4 What Is Priced: CAPM, SML, and Performance｜定價：CAPM、SML 與績效",
        stem="A stock has beta 1.50, market standard deviation 10%, and residual standard deviation 12%. Using σ² = β²σm² + σe², the stock’s total standard deviation is closest to:",
        choices={"A": "15.00%", "B": show(total_sd * 100, 2, "%"), "C": "12.00%"},
        correct="B",
        steps=f"系統變異 = 1.50²×0.10² = 0.0225。殘差變異 = 0.12² = 0.0144。總變異 = 0.0369。標準差 = {show(total_sd * 100, 2, '%')}。",
        final_answer=show(total_sd * 100, 2, "%"),
        why={"A": "Multiplies beta by the market standard deviation and ignores residual risk.", "C": "Reports the residual standard deviation."},
        zh="總變異是系統變異加殘差變異，標準差是總變異的平方根。",
        core="Total variance = beta² × market variance + residual variance",
        formula="σi² = βi²σm² + σe²",
        based_on="PM-060",
    )

    growth = (Decimal(180) / Decimal(100)) ** (Decimal(1) / Decimal(6)) - 1
    arithmetic = Decimal("0.80") / Decimal(6)
    require_unique(growth, {"A": Decimal("0.80"), "B": arithmetic, "C": growth}, "C", 4, "IPS")
    add(
        "10.5",
        subtopic="10.5 Planning, Vehicles, and Behaviour｜規劃、工具與行為",
        stem="An IPS return objective is the annual rate that turns 100,000 into 180,000 in 6 years, with no deposits or withdrawals. That annual rate is closest to:",
        choices={"A": "80.00%", "B": show(arithmetic * 100, 2, "%"), "C": show(growth * 100, 2, "%")},
        correct="C",
        steps=f"(180,000/100,000)^(1/6) − 1 = {show(growth * 100, 2, '%')}。",
        final_answer=show(growth * 100, 2, "%"),
        why={"A": "Reports the total six-year growth.", "B": "Divides the total growth by 6 without compounding."},
        zh="沒有中途現金流時，要求年報酬是終值除以期初值，再開期間數的根，然後減 1。",
        core="Required annual rate = (FV/PV)^(1/N) − 1",
        formula="FV = PV(1+r)^N",
        based_on="PM-098",
    )

    ear = (Decimal("1.015") ** 4) - 1
    continuous = Decimal("0.06").exp() - 1
    require_unique(ear, {"A": Decimal("0.06"), "B": ear, "C": continuous}, "B", 4, "EAR")
    add(
        "SIM.1",
        subtopic="SIM.1 Session 1 (SIM-001–SIM-045)",
        stem="A bank quotes a 6% stated annual rate with quarterly compounding. The effective annual rate is closest to:",
        choices={"A": "6.00%", "B": show(ear * 100, 2, "%"), "C": show(continuous * 100, 2, "%")},
        correct="B",
        steps=f"每期利率 = 6%/4 = 1.5%。EAR = (1.015)^4 − 1 = {show(ear * 100, 2, '%')}。",
        final_answer=show(ear * 100, 2, "%"),
        why={"A": "Reports the stated annual rate.", "C": "Uses continuous compounding, e^0.06 − 1."},
        zh="名目年利率按季複利時，有效年利率是 (1+名目/4)^4 − 1。",
        core="EAR = (1 + stated/m)^m − 1",
        formula="EAR = (1 + i/m)^m − 1",
        based_on="SIM-017",
    )

    add(
        "SIM.2",
        subtopic="SIM.2 Session 2 (SIM-046–SIM-090)",
        stem="Days of inventory are 50, days of receivables are 40, and days of payables are 25. The cash conversion cycle is closest to:",
        choices={"A": "90 days", "B": "65 days", "C": "25 days"},
        correct="B",
        steps="50+40−25 = 65 天。90 天沒有減應付。",
        final_answer="65 days",
        why={"A": "Adds inventory and receivables only.", "C": "Reports payables only."},
        zh="現金轉換週期 = 存貨天數 + 應收天數 − 應付天數。",
        core="CCC = inventory days + receivable days − payable days",
        formula="CCC = DOH + DSO − DPO",
        based_on="SIM-047",
    )
    return items


def main() -> None:
    topics = json.loads((DATA / "topics.json").read_text(encoding="utf-8"))
    numeric = build_numeric(topics)
    variants = [question for question, _solution in numeric]
    answers = [solution for _question, solution in numeric]
    ids = [item["id"] for item in variants]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate variant id")
    for question in variants:
        if "correct" in question or set(question["choices"]) != {"A", "B", "C"}:
            raise SystemExit(question["id"])
        if len(set(question["choices"].values())) != 3:
            raise SystemExit(question["id"])
    (DATA / "subject_variant_questions.json").write_text(json.dumps(variants, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA / "subject_variant_solutions.json").write_text(json.dumps(answers, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"subject variants {len(variants)} numeric {len(numeric)}")


if __name__ == "__main__":
    main()
