# INTJR 條碼報工系統｜目前狀態與新對話交接

更新日期：2026-10-16

## 專案位置

```text
C:\Users\TJR_\Documents\ChatGPT\報工
```

主要程式：

- `app.py`：Flask 啟動入口
- `app/services.py`：報工、條碼、掃描、報表、備份核心邏輯
- `app/routes.py`：網頁路由
- `app/db.py`：SQLite schema、migration、資料庫連線
- `app/barcode.py`：Code128 SVG 產生器
- `templates/`：網頁畫面
- `static/`：CSS 與掃描頁 JavaScript
- `instance/intjr.db`：本機資料庫
- `instance/app.log`：本機記錄檔
- `docs/decision-log.md`：D01～D06 決策紀錄

## 啟動方式

在 PowerShell 執行：

```powershell
Set-Location "C:\Users\TJR_\Documents\ChatGPT\報工"
& "C:\Users\TJR_\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" app.py
```

瀏覽器開啟：

```text
http://127.0.0.1:5000
```

若要安裝套件：

```powershell
& "C:\Users\TJR_\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m pip install -r requirements.txt
```

示例資料建立：

```powershell
& "C:\Users\TJR_\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" scripts\seed_demo_data.py
```

示例資料包含 HR-255、FAR-210、RC-210，以及 HR-255 的 E-01～E-10；編號語意維持 `unknown`。

## 已完成的功能

- 機型主檔新增、編輯、停用。
- 機台主檔規則產生與單筆建立，可停用與修改。
- 連續範圍與非連續多選建立報工批次。
- 一個批次可包含多台機台，資料庫仍保存每台 `job_run` 明細。
- 預設整批報工：一個批次只列印一張 START 與一張 FINISH。
- 整批 START 掃描一次，同步更新批次內所有機台為 `started`。
- 整批 FINISH 掃描一次，同步更新批次內所有機台為 `finished`。
- 報表仍保留每台機台的逐筆明細。
- Code128 短版條碼，條碼內容為固定短前綴、批次短代碼與校驗碼；完整資料留在 SQLite。
- A4 列印預覽；整批條碼版面約 4.5 公分寬。
- USB HID 掃描器即時上傳、Enter 結束輸入、掃描成功／重複／錯誤提示。
- Excel 明細、機型彙總、機台彙總、異常掃描清單。
- SQLite 備份、完整性檢查、還原前安全備份與還原稽核。
- `audit_log`、`scan_event`、`app.log`。

## 掃描器目前設定

使用者提供的設置卡標示「無線條碼掃描槍設置卡 V6.0」。原本掃描器在「存儲模式」，所以不會即時把內容傳給電腦。

已解決方式：掃描設置卡第一張最上方的：

```text
即時上傳模式
```

不要掃描：

- `存儲模式`
- `立即關機`
- `清零（謹慎使用）`

第二張卡的 `數據上傳` 是把儲存模式中的資料批次傳出，不是切換即時模式。

掃描頁：

```text
http://127.0.0.1:5000/scan
```

## 目前已確認的使用流程

1. 建立一批，例如選 E-01～E-10。
2. 列印新的整批 START／FINISH 條碼。
3. 開啟掃描頁並保持輸入焦點。
4. 掃一次 START，整批開始。
5. 工作完成後掃一次 FINISH，整批完成。
6. 到報表查看逐台明細。

舊版長條碼不要繼續使用；程式已改成短版條碼，需重新建立批次並重新列印。列印時使用「實際大小／100%」，不要縮放至頁面。

## 決策與限制

- E-01～E-10 只是示例。
- D01 尚未確認前，絕對不要自行判定 E-01 是永久資產號或批次流水號。
- `number_semantics` 預設為 `unknown`，可配置 `asset` 或 `serial`，但必須等現場確認。
- 歷史報工保存 model、machine、number semantics snapshot，不因主檔改名而改寫。
- 系統預設整批掃描，但設定頁仍保留逐台 `job_run` 模式作為備用。

## D01～D06 狀態

| 編號 | 狀態 |
|---|---|
| D01 | 待確認；E-01 語意維持 `unknown` |
| D02 | 待確認；預設同機台同工單只允許一筆進行中報工 |
| D03 | 待確認；目前使用單一製程欄位 |
| D04 | 待確認；工單號與產品批號可為空 |
| D05 | 待確認；FINISH 預設完成量等於計畫量，可稽核更正 |
| D06 | 待確認；目前先提供標準 Excel 欄位與日期篩選 |

另有一項已由使用者確認的流程變更：同一張報工單選多台機台時，只需要一張 START 與一張 FINISH，掃描後同步更新該批次所有機台。詳見 `docs/decision-log.md`。

## 測試狀態

目前自動化測試結果：

```text
6 passed
```

已涵蓋短版整批條碼、checksum、整批 START／FINISH、重複掃描、未 START 直接 FINISH、重複選取機台防呆、機台編號語意驗證、列印預覽、備份與還原驗證。

## 新對話建議開場文字

```text
請先閱讀 docs/current-status.md，這是 INTJR 條碼報工系統目前的交接狀態。核心流程已可用，接下來只修改我指定的細項。請保留整批一張 START／一張 FINISH、掃描器即時上傳模式，以及 E-01 編號語意 unknown 的限制。
```

