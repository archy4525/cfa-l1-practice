# CFA Level I 練習

這是依據使用者提供資料編寫的 CFA Level I 練習。資料不是 CFA Institute 官方出版物，題目不是官方原題，也不表示一定會出現在官方考試中。檔名雖含 2026，正文沒有標示適用的考試年度，因此程式沒有年度選單。

科目包含講義裡的倫理、數量方法、經濟學、公司發行人、財務報表分析、權益、固定收益、衍生性商品、另類投資、投資組合管理，以及題庫裡的跨章整合和模擬測驗。

## 啟動

```bash
pip install -r requirements.txt
streamlit run app.py
```

雲端版由 Streamlit Community Cloud 從 GitHub 啟動，進入點是 `app.py`。原始 PDF 只留在本機，不放進倉庫。

若要從 PDF 重建題庫，另外安裝 `requirements-build.txt`。

## 資料

題幹與答案分開存放。作答前不會看到正確選項。非數量方法的變化題只保留重新計算過、而且四捨五入後只有一個選項最接近的計算題。

若要從 PDF 重建：

```bash
python tools/build_all.py
python tools/make_variants.py
python tools/make_subject_variants.py
```
