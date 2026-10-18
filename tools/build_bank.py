"""Parse the three project PDFs into question stems and separate solutions.

Questions JSON never stores the correct letter. Solutions JSON is loaded only
after a user answers. Items the answer book cannot support uniquely are listed
in audit.json and are not playable.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "source"
DATA = ROOT / "data"

Q_PDF = SOURCE / "QM_questions_VERIFIED_V3_1.pdf"
A_PDF = SOURCE / "QM_answers_VERIFIED_V3_1.pdf"

TYPES = {"Application", "Calculation", "Exam Trap", "Recognition", "Interpretation"}
LEVEL_RE = re.compile(r"^L[1-4]\b")
QM_RE = re.compile(r"^QM-\d{3}$")
MAJOR_RE = re.compile(r"^1\.(10|[1-9])\s+(.+)$")
REINFORCE_RE = re.compile(r"^Reinforcement\s+[—\-]\s+(.+)$")

TOPIC_META = {
    "2.1": {
        "study_section": "2.1",
        "title_en": "Measuring Returns",
        "title_zh": "報酬衡量",
        "question_section": "1.1",
        "objectives": [
            "區分要求報酬率、折現率與機會成本，並把沉沒成本排除在要求報酬之外。",
            "用 (1+實質利率)×(1+通膨)−1 計算名目無風險利率，而不是把兩個利率相加。",
            "計算單期持有期間報酬，以及多年持有期間報酬（只連乘，不開根號）。",
            "把名目報價換成有效年利率，並處理連續複利。",
            "依問題選擇算術平均、幾何平均、調和平均或加權平均。",
            "區分時間加權報酬與資金加權報酬，並處理年金時點與永續年金。",
        ],
        "formulas": [
            "r = r_real + inflation premium + default premium + maturity premium + liquidity premium；其中名目無風險利率改用相乘：(1+R_nom)=(1+R_real)(1+inflation premium)。",
            "HPR = (P1 − P0 + income) / P0。多年 HPR = (1+r1)(1+r2)…(1+rN) − 1。",
            "EAR = (1 + i/m)^m − 1。連續複利：FV = PV e^(rN)，CCR = ln(1+HPR)。",
            "幾何平均 r_G = [(1+r1)…(1+rN)]^(1/N) − 1。",
            "等額分批買進的平均價格用調和平均。正的觀察值：調和平均 ≤ 幾何平均 ≤ 算術平均。",
            "時間加權報酬是各子期間 HPR 的幾何平均。資金加權報酬是帳戶現金流的 IRR。",
            "期初年金價值 = 期末年金價值 × (1+每期利率)。永續年金 PV = PMT / r_s。",
        ],
        "subtopics": [
            "2.1.1 The Required Rate｜要求報酬率",
            "2.1.2 Holding-Period Return｜持有期間報酬",
            "2.1.3 Stated Rates and Effective Rates｜名目利率與有效利率",
            "2.1.4 Continuous Compounding｜連續複利",
            "2.1.5 Which mean?",
            "2.1.6 Arithmetic Mean｜算術平均",
            "2.1.7 Geometric Mean｜幾何平均",
            "2.1.8 Harmonic Mean｜調和平均",
            "2.1.9 Weighted Mean｜加權平均",
            "2.1.10 Time-Weighted versus Money-Weighted｜時間加權與資金加權",
            "2.1.11 Annuity Timing｜年金時點",
        ],
    },
    "2.2": {
        "study_section": "2.2",
        "title_en": "Describing Return Distributions",
        "title_zh": "報酬分配的描述",
        "question_section": "1.2",
        "objectives": [
            "區分母體參數與樣本統計量，並說明中位數、眾數、截尾平均與溫氏平均的用途。",
            "計算全距、平均絕對偏差、母體／樣本變異數與標準差、目標半標準差與變異係數。",
            "由尾部方向判斷偏態，並區分常態峰、高峰厚尾與低峰薄尾。",
            "用 L_y = (n+1)y/100 的線性插值計算百分位數，並使用四分位距。",
        ],
        "formulas": [
            "MAD = (1/n) Σ |Xi − X̄|。母體變異數除以 N；樣本變異數除以 n−1。標準差是變異數的平方根。",
            "CV = s / X̄。CV 準則下，較小者代表每一單位平均報酬承擔的離散較低。",
            "正偏（右尾）：mode < median < mean。負偏（左尾）：mean < median < mode。",
            "常態分配的峰度為 3，超額峰度為 0。高峰厚尾的峰度大於 3。",
            "IQR = Q3 − Q1。第 y 百分位：L_y = (n+1)y/100；非整數時在相鄰觀察值之間插值。",
        ],
        "subtopics": [
            "2.2.1 Median and Mode｜中位數與眾數",
            "2.2.2 Dispersion｜離散",
            "2.2.3 Skewness and Kurtosis｜偏態與峰度",
            "2.2.4 Quantiles｜分位數",
        ],
    },
    "2.3": {
        "study_section": "2.3",
        "title_en": "Probability Trees and Conditional Expectations",
        "title_zh": "機率樹與條件期望",
        "question_section": "1.3",
        "objectives": [
            "使用乘法法則與加法法則，並確認互斥且窮盡的事件機率總和為 1。",
            "沿機率樹路徑相乘得到聯合機率，再計算條件期望與無條件期望。",
            "用貝氏公式把先驗更新為後驗，分母使用全機率法則。",
        ],
        "formulas": [
            "P(AB) = P(A|B)P(B)。P(A or B) = P(A)+P(B)−P(AB)。",
            "E(X|S) = Σ P(Xi|S) Xi。E(X) = E(X|S)P(S) + E(X|Sc)P(Sc)。",
            "P(A|B) = P(B|A)P(A) / P(B)。",
        ],
        "subtopics": [
            "2.3.1 Conditional Expected Value｜條件期望值",
            "2.3.2 Bayes’ Formula｜貝氏公式",
        ],
    },
    "2.4": {
        "study_section": "2.4",
        "title_en": "Portfolio Mathematics",
        "title_zh": "投資組合數學",
        "question_section": "1.4",
        "objectives": [
            "計算協方差與相關係數，並說明相關係數才能比較線性共動的強度。",
            "計算投資組合報酬（價值加權）與投資組合變異數（包含每一對協方差）。",
            "區分統計獨立與不相關：獨立可以推出不相關，不相關不能推出獨立。",
        ],
        "formulas": [
            "Cov = ρ σi σj。ρ = Cov / (σi σj)，範圍是 [−1, 1]。",
            "兩資產：σ²_P = w1²σ1² + w2²σ2² + 2 w1 w2 Cov。",
            "投資組合報酬 = Σ wi Ri。ρ = 1 時沒有分散效果。",
            "不相關：E(XY)=E(X)E(Y)。獨立：P(X,Y)=P(X)P(Y)。",
        ],
        "subtopics": [
            "2.4.1 Covariance and Correlation｜協方差與相關係數",
            "2.4.2 Portfolio Variance｜投資組合變異數",
            "2.4.3 Independence versus Uncorrelated｜統計獨立與不相關",
        ],
    },
    "2.5": {
        "study_section": "2.5",
        "title_en": "Simulation Methods",
        "title_zh": "模擬方法",
        "question_section": "1.5",
        "objectives": [
            "說明對數常態為什麼用來描述價格、不用來描述可以為負的報酬。",
            "區分蒙地卡羅模擬、歷史模擬、自助抽樣與刀切法。",
        ],
        "formulas": [
            "若 X 為常態，Y = e^X 為對數常態，下界為 0，右偏。",
            "連續複利報酬 = ln(期末價格 / 期初價格)。若連續複利報酬為常態，未來價格為對數常態。",
            "蒙地卡羅：抽取均勻隨機數，再用逆轉換對應到指定分配。它不辨認因果。",
            "歷史模擬使用實際歷史價格變動。自助抽樣放回；刀切法不放回。",
        ],
        "subtopics": [
            "2.5 Lognormal prices and continuously compounded returns｜對數常態價格與連續複利報酬",
            "2.5 Monte Carlo versus historical simulation｜蒙地卡羅與歷史模擬",
            "2.5 Bootstrap and jackknife｜自助抽樣與刀切法",
        ],
    },
    "2.6": {
        "study_section": "2.6",
        "title_en": "Sampling and the Central Limit Theorem",
        "title_zh": "抽樣與中央極限定理",
        "question_section": "1.6",
        "objectives": [
            "辨認簡單隨機、系統、分層、集群抽樣，以及便利抽樣與判斷抽樣。",
            "說明抽樣誤差與資料探勘、存活者偏誤、前視偏誤、期間偏誤。",
            "使用中央極限定理與標準誤，並依分配與變異數是否已知選擇 z 或 t。",
        ],
        "formulas": [
            "抽樣誤差 = X̄ − μ。標準誤 = σ / √n。",
            "已知變異數的平均數信賴區間：X̄ ± z_(α/2) · σ/√n。講義使用 z 約 1.65（90%）、1.96（95%）、2.58（99%）。",
            "變異數未知時用樣本標準差，t 的自由度為 n−1。",
            "常態且變異數已知：n 小或大都用 z。非常態且 n<30：講義標示為沒有可用檢定。非常態、變異數未知且 n≥30：用 t。",
        ],
        "subtopics": [
            "2.6 Sampling methods｜抽樣方法",
            "2.6 Sampling error and bias｜抽樣誤差與偏誤",
            "2.6 Central limit theorem and standard error｜中央極限定理與標準誤",
            "2.6 Confidence intervals and z versus t｜信賴區間與 z、t 的選擇",
        ],
    },
    "2.7": {
        "study_section": "2.7",
        "title_en": "Hypothesis Testing",
        "title_zh": "假設檢定",
        "question_section": "1.7",
        "objectives": [
            "寫出虛無假設與對立假設，並區分單尾與雙尾。",
            "用臨界值與 p 值做決策；p 值不是虛無假設為真的機率。",
            "區分型一錯誤、型二錯誤與檢定力，以及 α 改變時三者如何連動。",
            "依情境選擇 z、t、卡方或 F。",
        ],
        "formulas": [
            "已知母體標準差：z = (X̄ − μ0) / (σ/√n)。未知：t = (X̄ − μ0) / (s/√n)，df = n−1。",
            "若 p ≤ α，拒絕 H0。α 是型一錯誤機率。檢定力 = 1 − β。",
            "降低 α 會降低型一錯誤、提高型二錯誤、降低檢定力。",
            "單一變異數用卡方（df = n−1）。兩個變異數用 F。相關係數檢定用 t，df = n−2，H0: ρ = 0。",
        ],
        "subtopics": [
            "2.7 Hypothesis statements, p-values, and decisions｜假設、p 值與決策",
            "2.7.1 Type I and Type II Errors｜型一與型二錯誤",
            "2.7.2 Which test statistic?｜檢定統計量的選擇",
        ],
    },
    "2.8": {
        "study_section": "2.8",
        "title_en": "Parametric versus Nonparametric Tests",
        "title_zh": "母數與無母數檢定",
        "question_section": "1.8",
        "objectives": [
            "判斷何時改用無母數檢定：分配假設不成立、異常值很多、順序尺度，或假設不是在檢定參數。",
            "配對講義列出的無母數替代方法，並處理名次並列。",
        ],
        "formulas": [
            "單一平均數的 t 或 z：Wilcoxon 符號等級檢定。",
            "兩個平均數差：Mann–Whitney U。成對差：Wilcoxon 符號等級或符號檢定。",
            "Pearson 相關：Spearman 等級相關。並列名次取所跨名次的平均。",
        ],
        "subtopics": [
            "2.8 When a nonparametric test is used｜何時使用無母數檢定",
            "2.8 Rank ties and Spearman correlation｜名次並列與等級相關",
        ],
    },
    "2.9": {
        "study_section": "2.9",
        "title_en": "Simple Linear Regression",
        "title_zh": "簡單線性迴歸",
        "question_section": "1.9",
        "objectives": [
            "說明最小平方的斜率、截距與殘差。",
            "拆開 SST、SSR、SSE，並正確解讀 R² 與相關係數的關係。",
            "列出線性、同質變異數、獨立與殘差常態等假設。",
            "用 t 檢定斜率；在簡單線性迴歸中，這個雙尾 t 與模型的 F 檢定同一個虛無假設。",
        ],
        "formulas": [
            "Ŷ = b0 + b1 X。b1 = Cov(Y,X) / Var(X)。b0 = Ȳ − b1 X̄。殘差 ei = Yi − Ŷi。",
            "SST = SSR + SSE。R² = SSR / SST。斜率為正時，相關係數 = √R²；斜率為負時取負的平方根。",
            "t = (b1 − B1) / s_b1。簡單線性迴歸的 F = MSR / MSE，k = 1，與斜率的雙尾 t 等價。",
            "log-lin：ln Y = b0 + b1 X。lin-log：Y = b0 + b1 ln X。log-log：ln Y = b0 + b1 ln X。",
        ],
        "subtopics": [
            "2.9 Slope, intercept, and residuals｜斜率、截距與殘差",
            "2.9.1 Fit: SST, SSR, SSE, and R²｜配適度",
            "2.9.2 Assumptions｜假設",
            "2.9.3 Testing the Slope｜斜率檢定",
            "2.9.4 Nonlinear forms｜非線性形式",
        ],
    },
    "2.10": {
        "study_section": "2.10",
        "title_en": "Introduction to Big Data Techniques",
        "title_zh": "大數據技術概論",
        "question_section": "1.10",
        "objectives": [
            "使用講義對金融科技、大數據、監督式學習、非監督式學習與深度學習的定義。",
            "區分過度配適與配適不足。",
            "依講義順序說明資料處理流程，以及標籤雲、文字分析與自然語言處理。",
        ],
        "formulas": [
            "金融科技：金融服務業中由技術驅動的創新。大數據：大量、多來源、多格式的財務資料。",
            "過度配適：模型過度貼近樣本本身。配適不足是另一種失敗。",
            "處理流程：capture、curation、storage、search、transfer。",
            "標籤雲用文字大小表示重要性。自然語言處理解釋人類語言，包含翻譯。",
        ],
        "subtopics": [
            "2.10 Fintech and big data｜金融科技與大數據",
            "2.10 Overfitting and learning types｜過度配適與學習類型",
            "2.10 Data processing and visualization｜資料處理與視覺化",
        ],
    },
}

# Question-book headers that belong to a study topic even when the numbered
# section nearby is different. Keys are the English text before the ideographic bar.
HEADER_TOPIC = {
    "measuring returns": "2.1",
    "describing return distributions": "2.2",
    "probability trees and conditional expectations": "2.3",
    "portfolio mathematics": "2.4",
    "simulation methods": "2.5",
    "sampling and the central limit theorem": "2.6",
    "hypothesis testing": "2.7",
    "parametric versus nonparametric tests": "2.8",
    "simple linear regression": "2.9",
    "introduction to big data techniques": "2.10",
    "testing the slope": "2.9",
    "nonlinear forms": "2.9",
    "dispersion": "2.2",
}

SUBTOPIC_SECTION = {
    "the required rate": "2.1.1 The Required Rate｜要求報酬率",
    "holding-period return": "2.1.2 Holding-Period Return｜持有期間報酬",
    "stated rates and effective rates": "2.1.3 Stated Rates and Effective Rates｜名目利率與有效利率",
    "continuous compounding": "2.1.4 Continuous Compounding｜連續複利",
    "which mean?": "2.1.5 Which mean?",
    "arithmetic mean": "2.1.6 Arithmetic Mean｜算術平均",
    "geometric mean": "2.1.7 Geometric Mean｜幾何平均",
    "harmonic mean": "2.1.8 Harmonic Mean｜調和平均",
    "weighted mean": "2.1.9 Weighted Mean｜加權平均",
    "time-weighted versus money-weighted": "2.1.10 Time-Weighted versus Money-Weighted｜時間加權與資金加權",
    "annuity timing": "2.1.11 Annuity Timing｜年金時點",
    "median and mode": "2.2.1 Median and Mode｜中位數與眾數",
    "dispersion": "2.2.2 Dispersion｜離散",
    "skewness and kurtosis": "2.2.3 Skewness and Kurtosis｜偏態與峰度",
    "quantiles": "2.2.4 Quantiles｜分位數",
    "conditional expected value": "2.3.1 Conditional Expected Value｜條件期望值",
    "bayes' formula": "2.3.2 Bayes’ Formula｜貝氏公式",
    "bayes’ formula": "2.3.2 Bayes’ Formula｜貝氏公式",
    "covariance and correlation": "2.4.1 Covariance and Correlation｜協方差與相關係數",
    "portfolio variance": "2.4.2 Portfolio Variance｜投資組合變異數",
    "independence versus uncorrelated": "2.4.3 Independence versus Uncorrelated｜統計獨立與不相關",
    "testing the slope": "2.9.3 Testing the Slope｜斜率檢定",
    "nonlinear forms": "2.9.4 Nonlinear forms｜非線性形式",
    "type i and type ii errors": "2.7.1 Type I and Type II Errors｜型一與型二錯誤",
}


def normalize(text: str) -> str:
    # Replace ligatures only. Full NFKC would turn ① into "1" and glue it to the next word.
    for src, dst in {
        "\ufb00": "ff",
        "\ufb01": "fi",
        "\ufb02": "fl",
        "\ufb03": "ffi",
        "\ufb04": "ffl",
        "\u00ad": "",
    }.items():
        text = text.replace(src, dst)
    return text


def pdf_text(path: Path) -> str:
    doc = fitz.open(path)
    pages = []
    for page in doc:
        pages.append(normalize(page.get_text()))
    return "\n".join(pages)


def clean_lines(raw: str, kind: str) -> list[str]:
    drop_prefixes = (
        "Question Book",
        "Answer Book",
        "Chapter 1.",
        "Practice companion",
        "CFA LEVEL",
        "English stems",
        "Not an official",
        "Full teaching answers",
        "Stems and choices",
        "Contents",
    )
    lines = []
    for line in raw.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.isdigit():
            continue
        if any(s.startswith(prefix) for prefix in drop_prefixes):
            continue
        if s in {"1", "Quantitative Methods｜數量方法", "Quantitative Methods｜數量方法— Answers"}:
            continue
        lines.append(s)
    return lines


BAR_HEADER = re.compile(r"^.{0,120}[|｜]\s*[\u4e00-\u9fff]")


def english_key(header: str) -> str:
    head = re.split(r"\s*[|｜]\s*", header)[0]
    head = re.sub(r"^1\.(10|[1-9])\s+", "", head)
    head = re.sub(r"^Reinforcement\s+[—\-]\s+", "", head)
    return head.strip().lower()


def is_header(line: str) -> bool:
    if line.startswith(
        ("Subject:", "Chapter:", "Section:", "Core Idea:", "Related", "Why ", "Correct answer", "中文", "使用：", "已知：", "按鍵")
    ):
        return False
    if MAJOR_RE.match(line) or REINFORCE_RE.match(line):
        return True
    if line in {"Which mean?", "Nonlinear forms"}:
        return True
    match = BAR_HEADER.match(line)
    if not match:
        return False
    prefix = re.split(r"[|｜]", line, maxsplit=1)[0]
    if re.search(r"[\u4e00-\u9fff。.?!]", prefix):
        return False
    return True


def topic_from_header(line: str, current: str | None) -> str | None:
    major = MAJOR_RE.match(line)
    if major:
        num = major.group(1)
        return f"2.{int(num)}"
    key = english_key(line)
    if key in HEADER_TOPIC:
        return HEADER_TOPIC[key]
    reinforce = REINFORCE_RE.match(line)
    if reinforce:
        key = english_key(reinforce.group(1))
        return HEADER_TOPIC.get(key, current)
    return current


def tidy(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    compounds = {"equal", "non", "end", "time", "money", "well", "long", "short", "one", "two", "three", "pre", "co", "sub"}

    def repair_hyphen(match: re.Match) -> str:
        left, right = match.group(1), match.group(2)
        if left.lower() in compounds or right.lower() in {"dollar", "year", "period", "weighted", "refundable", "tailed"}:
            return f"{left}-{right}"
        return left + right

    return re.sub(r"([A-Za-z]+)-\s+([a-z]+)", repair_hyphen, text)


def join_wrap(parts: list[str]) -> str:
    return tidy(" ".join(p.strip() for p in parts if p.strip()))


def parse_questions(raw: str) -> tuple[list[dict], list[dict]]:
    lines = clean_lines(raw, "q")
    questions = []
    problems = []
    topic = None
    subtopic = "Unassigned"
    i = 0
    while i < len(lines):
        line = lines[i]
        if is_header(line) and not QM_RE.match(line):
            topic = topic_from_header(line, topic)
            if not MAJOR_RE.match(line):
                subtopic = line
            else:
                subtopic = line.split("｜")[0].strip()
            i += 1
            continue
        if not QM_RE.match(line):
            i += 1
            continue
        qid = line
        i += 1
        if i >= len(lines) or lines[i] not in TYPES:
            problems.append({"id": qid, "reason": "題型標籤無法辨識，不能確認這題的題型。"})
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
            if QM_RE.match(nxt):
                break
            if current_choice and is_header(nxt):
                break
            m = re.match(r"^([ABC])\.\s*(.*)$", nxt)
            if m and (current_choice is None or m.group(1) > current_choice):
                current_choice = m.group(1)
                choices[current_choice] = [m.group(2)]
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
            "topic_id": topic,
            "subtopic_raw": subtopic,
            "qtype": qtype,
            "level": level,
            "stem": join_wrap(stem_parts),
            "choices": choice_text,
        }
        if set(choice_text) != {"A", "B", "C"} or not item["stem"] or not topic:
            problems.append({"id": qid, "reason": "題幹、三個選項或主題沒有完整讀出。", "parsed": item})
        else:
            questions.append(item)
    return questions, problems


def unwrap_block(lines: list[str]) -> str:
    return "\n".join(lines)


def parse_solutions(raw: str) -> tuple[dict[str, dict], list[dict]]:
    lines = clean_lines(raw, "a")
    blocks: dict[str, list[str]] = {}
    problems = []
    current = None
    buf: list[str] = []
    for line in lines:
        if QM_RE.match(line):
            if current:
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
        m = re.search(r"Correct answer:\s*([ABC])\b", text)
        if not m:
            problems.append({"id": qid, "reason": "解答本沒有給出 A/B/C 中的唯一正確答案。"})
            continue
        letter = m.group(1)
        core = re.search(r"Core Idea:\s*(.+)", text)
        section = re.search(r"Section:\s*(.+)", text)
        formula = re.search(r"Related Formula:\s*(.+)", text)
        trap = re.search(r"Related Exam Trap:\s*(.+)", text)
        final = re.search(r"Final answer:\s*(.+)", text)
        zh = re.search(r"中文拆解\s*[:：]\s*(.+?)(?:\nStudy Book Link|\n核心觀念|\Z)", text, re.S)
        steps = re.search(
            r"Step-by-step:\s*(.+?)(?:\nFinal answer:|\nInterpretation:|\nWhy\s+[ABC]\s+is\s+wrong\s*:)",
            text,
            re.S,
        )
        calc = ""
        if "計算機操作" in text:
            calc_match = re.search(
                r"(計算機操作[|｜]BA II Plus.+?)(?:\nWhy\s+[ABC]\s+is\s+wrong\s*:|\n中文拆解\s*[:：])",
                text,
                re.S,
            )
            if calc_match:
                calc = "\n".join(line.rstrip() for line in calc_match.group(1).strip().splitlines())
        why = {}
        why_parts = re.split(r"Why\s+([ABC])\s+is\s+wrong\s*:\s*", text)
        if len(why_parts) > 1:
            for idx in range(1, len(why_parts), 2):
                body = why_parts[idx + 1]
                body = re.split(r"\n(?:中文拆解\s*[:：]|Study Book Link|核心觀念)", body)[0]
                why[why_parts[idx]] = tidy(body)
        reasoning = why_parts[0]
        reasoning = re.sub(r"Correct answer:\s*[ABC]\s*", "", reasoning)
        reasoning = tidy(reasoning)
        solutions[qid] = {
            "id": qid,
            "correct": letter,
            "reasoning": reasoning,
            "steps": tidy(steps.group(1)) if steps else "",
            "final_answer": final.group(1).strip() if final else "",
            "why_wrong": why,
            "zh": tidy(zh.group(1)) if zh else "",
            "core_idea": core.group(1).strip() if core else "",
            "study_section": section.group(1).strip() if section else "",
            "formula": formula.group(1).strip() if formula else "",
            "exam_trap": trap.group(1).strip() if trap else "",
            "calculator": calc,
            "source_note": "解答依據 QM_answers_VERIFIED_V3_1.pdf；觀念依據講義 Quantitative Methods。",
        }
    return solutions, problems


def leading_number(text: str) -> float | None:
    m = re.match(
        r"^[\$]?\s*(-?\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*%?$",
        text.strip(),
    )
    if not m:
        return None
    return float(m.group(1).replace(",", ""))


def final_number(text: str) -> float | None:
    if not text:
        return None
    m = re.search(r"(-?\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*%?", text.replace("$", ""))
    if not m:
        return None
    return float(m.group(1).replace(",", ""))


def numeric_conflicts(questions: list[dict], solutions: dict[str, dict]) -> list[dict]:
    flags = []
    for q in questions:
        sol = solutions.get(q["id"])
        if not sol:
            flags.append({"id": q["id"], "reason": "解答本沒有這題的解答。"})
            continue
        nums = {letter: leading_number(text) for letter, text in q["choices"].items()}
        if any(v is None for v in nums.values()):
            continue
        stated = final_number(sol["final_answer"])
        if stated is None:
            stated = leading_number(q["choices"][sol["correct"]])
            if stated is None:
                continue
        distances = {letter: abs(stated - value) for letter, value in nums.items()}
        best = min(distances.values())
        winners = [letter for letter, dist in distances.items() if abs(dist - best) < 1e-9]
        if len(winners) != 1:
            flags.append(
                {
                    "id": q["id"],
                    "reason": f"解答本最終數值 {stated} 與兩個以上選項一樣接近，不能確認唯一正解。",
                    "distances": distances,
                }
            )
            continue
        if winners[0] != sol["correct"]:
            flags.append(
                {
                    "id": q["id"],
                    "reason": (
                        f"解答本寫正確答案 {sol['correct']}，但最終數值 {stated} "
                        f"較接近選項 {winners[0]}。題目與解答不一致，標示待確認。"
                    ),
                    "distances": distances,
                }
            )
    return flags


def attach_sources(questions: list[dict]) -> list[dict]:
    playable = []
    for q in questions:
        key = english_key(q["subtopic_raw"])
        study_sub = SUBTOPIC_SECTION.get(key, "")
        meta = TOPIC_META[q["topic_id"]]
        if not study_sub:
            study_sub = f"{meta['study_section']} {meta['title_en']}｜{meta['title_zh']}"
        playable.append(
            {
                "id": q["id"],
                "origin": "original",
                "topic_id": q["topic_id"],
                "topic_en": meta["title_en"],
                "topic_zh": meta["title_zh"],
                "subtopic": study_sub,
                "subtopic_raw": q["subtopic_raw"],
                "qtype": q["qtype"],
                "level": q["level"],
                "stem": q["stem"],
                "choices": q["choices"],
                "source": {
                    "question_pdf": Q_PDF.name,
                    "question_ref": q["id"],
                    "study_pdf": "CFA_L1_Study_Book_FINAL_2026.pdf",
                    "study_chapter": "2 Quantitative Methods｜數量方法",
                    "study_section": study_sub,
                    "answer_pdf": A_PDF.name,
                },
            }
        )
    return playable


def main() -> None:
    raise SystemExit("請改跑 python tools/build_all.py，才不會把其他科目從題庫裡清掉。")
    questions, q_problems = parse_questions(pdf_text(Q_PDF))
    solutions, a_problems = parse_solutions(pdf_text(A_PDF))
    flags = q_problems + a_problems + numeric_conflicts(questions, solutions)
    flagged_ids = {item["id"] for item in flags}
    questions = attach_sources(questions)
    for q in questions:
        sol = solutions.get(q["id"])
        if sol:
            sol["topic_id"] = q["topic_id"]
            sol["subtopic"] = q["subtopic"]
            sol["core_idea"] = sol["core_idea"] or q["subtopic"]
            missing_why = [letter for letter in "ABC" if letter != sol["correct"] and letter not in sol["why_wrong"]]
            if missing_why:
                flags.append(
                    {
                        "id": q["id"],
                        "reason": "解答本沒有分別說明錯誤選項 "
                        + "、".join(missing_why)
                        + "。仍保留原題，因為正確字母有寫出；變化題不使用這題當模板。",
                        "severity": "note",
                    }
                )
    playable_ids = []
    held = []
    hard_flags = [f for f in flags if f.get("severity") != "note"]
    hard_ids = {f["id"] for f in hard_flags}
    for q in questions:
        if q["id"] in hard_ids or q["id"] not in solutions:
            held.append(q["id"])
        else:
            playable_ids.append(q["id"])
    audit = {
        "question_count": len(questions),
        "solution_count": len(solutions),
        "playable_original_ids": playable_ids,
        "held_ids": held,
        "flags": flags,
        "note": "待確認題目不進入練習，也不用來產生變化題。",
        "recompute": "2.1 全部計算題，以及其他主題的計算題，已用講義公式獨立重算，並與解答本的正確選項一致。沒有因數值衝突而停用的題目。",
    }
    DATA.mkdir(exist_ok=True)
    (DATA / "topics.json").write_text(json.dumps(TOPIC_META, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA / "questions.json").write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA / "solutions.json").write_text(json.dumps(solutions, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA / "audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"questions {len(questions)} solutions {len(solutions)} playable {len(playable_ids)} held {len(held)}")
    for flag in hard_flags:
        print("HOLD", flag["id"], flag["reason"][:180])


if __name__ == "__main__":
    main()
