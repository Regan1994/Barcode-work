# INTJR 條碼報工系統 V1.0

Windows 本機離線使用的 Flask + SQLite 條碼報工系統。預設只綁定 `127.0.0.1`，不需要網路服務。

## 啟動

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py app.py
```

瀏覽器開啟 `http://127.0.0.1:5000/`。資料庫位於 `instance/intjr.db`，備份位於 `instance/backups/`。可用 `INTJR_DATA_DIR` 指定資料目錄。

## 測試

```powershell
pytest -q
```

## 重要設計

- 機型與機台皆由主檔管理；示例 E-01～E-10 的編號語意預設為 `unknown`。
- 整批模式使用短 Code128 內容 `I1S/F + batch_token + checksum`；完整 batch、機型與機台資料留在 SQLite，讓條碼維持接近現場短標籤尺寸。
- 預設一個 production_batch 只列印一張 START 與一張 FINISH；掃描後同步更新批次內所有 job_run，報表仍保留逐台明細。可在設定中切換成逐台模式。
- 所有寫入集中在 service layer；歷史報工保存名稱、代碼、機台編號與語意 snapshot。
- 系統包含報表 Excel、備份驗證、掃描事件與稽核紀錄的基本實作。

## 分階段實作紀錄

- Phase 0：專案骨架、啟動、SQLite、決策紀錄。
- Phase 1：資料表、外鍵、索引與設定。
- Phase 2：機型／機台主檔與 `unknown`／`asset`／`serial` 設定。
- Phase 3：報工批次、連續／非連續機台選擇與 snapshot。
- Phase 4：Code128 payload、條碼 SVG 與 A4 列印版面。
- Phase 5：USB HID Enter 輸入、狀態機、冪等掃描與 scan_event。
- Phase 6：日期與條件篩選、單一工作表 Excel 明細匯出。
- Phase 7：SQLite 備份與完整性驗證；稽核紀錄。
- Phase 8：Windows 文件、測試與驗收清單。

