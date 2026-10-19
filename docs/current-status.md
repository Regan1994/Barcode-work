# INTJR 條碼報工系統｜目前狀態

更新日期：2026-10-19

## 專案與啟動

專案位於 `C:\Users\TJR_\Documents\ChatGPT\報工`。主要程式為 `app/routes.py`、`app/services.py`、`app/db.py`，畫面位於 `templates/`，本機資料庫為 `instance/intjr.db`。

```powershell
Set-Location "C:\Users\TJR_\Documents\ChatGPT\報工"
$env:INTJR_PORT = "5000"
python app.py
```

請使用已安裝 Flask 的系統 Python；Codex bundled Python 環境沒有 Flask，會出現 `ModuleNotFoundError: No module named 'flask'`。目前系統 Python 為 3.14，已安裝 Flask 3.1.3 與 openpyxl 3.1.5。

瀏覽器網址：`http://127.0.0.1:5000`。

## 產品製號規則

- 產品由「機型 + 製號」識別；一個製號對應一個產品。
- 機型前綴：HR-255＝E、AR-210＝C、AR-170＝B、RC-210＝CR、RC-255＝ER。其他機型可在機型主檔設定製號字首。
- 年號為製作年份 + 1 的末兩位；例如 2026 年為 27。
- 格式為 `字首年號-流水號`，流水號至少兩位；例：HR-255 2026 年第 10 台是 `E27-10`。
- 新報工選擇組裝人員，並手動選製作年份、起始流水號與台數，系統連續產生製號。組裝人員可在「組裝人員」主檔新增或停用。既有產品數量不易回推，因此不自動猜起號；已使用製號不可重複建立。
- 一批產品各自保存一筆 `job_run`，但同一批共用一張 START、一張 FINISH。全批完成後才掃 FINISH；不在 FINISH 輸入數量。
- 工單號、產品批號、製程、計畫數量不再出現在新建、報表、列印或 Excel 操作流程。資料庫歷史欄位保留，舊資料不刪除。
- 新產品報工不依賴機台主檔；舊機台資料（例如 E-01）仍維持其原有歷史語意，不能當作產品製號。

## 已有功能

- 機型主檔與舊機台主檔管理；機型主檔新增製號字首。
- 產品製號批次建立、連號生成、重複製號防護與成對短版條碼列印。
- 整批 START／FINISH 同步更新本批每筆產品明細，並防止 FINISH 早於 START、重複掃描。
- 首頁狀態卡片與中文狀態、報表日期/機型/製號/狀態/組裝人員/批次篩選、運作時長。
- Excel 明細、機型台數彙總、異常掃描清單；SQLite 備份、還原與稽核。
- 資料庫 schema migration v3（由 `schema_migrations` 表追蹤）：舊報工欄位與 snapshot 保留，允許新產品明細不綁定機台，並為製號建立唯一索引；v4 新增組裝人員主檔。SQLite `PRAGMA user_version` 未用於版本管理。

## 掃描與列印

掃描頁：`http://127.0.0.1:5000/scan`。掃描器需設定為即時上傳模式，保持掃描頁輸入焦點；新批次先掃 START，該批所有產品完成後再掃 FINISH。條碼應以實際大小／100% 列印。

## 驗證

最近一次測試：2026-10-16 執行 `python -m pytest -q --basetemp .pytest-tmp`，16 passed；組裝人員主檔功能尚未重跑測試。尚待實機確認印表機及 USB HID 掃描器。

## 需求決策

製號規則及批次數量語意已由使用者確認，詳見 `docs/decision-log.md`。舊機台編號語意仍保留 unknown，不影響新的產品製號。
