# INTJR 報工系統｜EXE 打包前交接文件

這份文件提供給下一個對話使用。下一個對話請先閱讀本文件，再開始任何打包或程式修改。

## 目前專案

- 專案路徑：`C:\Users\TJR_\Documents\ChatGPT\報工`
- 分支：`codex/five-axis-assembly-flow`
- 系統：Windows 本機使用的 Flask + SQLite 條碼報工系統
- 本機資料庫：`instance/intjr.db`
- 目前程式修改尚未提交；請保留現有修改，不要 reset、checkout 或覆蓋使用者檔案。
- `instance/` 被 `.gitignore` 排除，絕對不要把本機資料庫或備份提交到 Git。

## 目前已完成的功能

### 首頁與模組

- 首頁使用大型模組方塊：
  - `01 條碼建立`
  - `02 報工掃描`
  - `03 最近批次`
  - `04 報表與匯出`
  - `05 機型主檔`
  - `06 組裝人員`
- `01 條碼建立` 與 `02 報工掃描` 不需要密碼。
- 報工掃描已是獨立頁面，不再直接放在首頁輸入。
- `設定` 與 `清除資料` 保留在上方導覽列，沒有放進首頁模組卡片。
- 首頁狀態卡片旁已放置「資料安全」資訊。

### 密碼保護

- 需要密碼的功能：最近批次、報表與匯出、機型主檔、組裝人員、設定、清除資料。
- 初始管理密碼：`TJR`。
- 密碼以 Werkzeug hash 儲存於 `app_settings`，不儲存明文。
- 從管理頁返回首頁後，解鎖狀態會清除；再次進入受保護功能必須重新輸入密碼。
- 設定頁可以更改管理密碼。
- 設定頁有「功能密碼」開關，暫時取消勾選可方便排查；排查完成後要重新勾選啟用。

### 五軸與報表

- 五軸機型名稱以 `F` 開頭，建立報工時必須選擇：旋轉軸、傾斜軸、尾座或組合。
- 同一五軸製號可以建立不同組裝階段，但同一製號同一階段不可重複。
- 報表新增「組裝階段」欄位：
  - `旋` 顯示為「旋轉軸」
  - `傾` 顯示為「傾斜軸」
  - `尾` 顯示為「尾座」
  - `組` 顯示為「組合」
  - 標準四軸顯示「—」
- Excel 匯出也包含「組裝階段」欄位。

### 其他已完成項目

- 產品製號批次建立、連號生成及重複防護。
- START／FINISH 報工掃描與階段條碼驗證。
- 最近批次重新列印。
- 機型主檔與組裝人員主檔。
- 報表日期、機型、製號、狀態及組裝人員篩選。
- SQLite 備份、刪除保護及操作稽核。
- 畫面與 Excel 時間顯示為台灣時間 `YYYY-MM-DD HH:mm:ss`。

## 啟動方式

在 PowerShell 執行：

```powershell
Set-Location "C:\Users\TJR_\Documents\ChatGPT\報工"
$env:INTJR_PORT = "5000"
python app.py
```

瀏覽器網址：`http://127.0.0.1:5000`。

目前若已有伺服器執行，修改程式後先在該視窗按 `Ctrl+C`，再重新執行 `python app.py`。不要同時開多個 Flask 伺服器。

## 驗證結果

最近一次執行：

```powershell
python -m pytest -q --basetemp .pytest-tmp
```

結果：`36 passed`。

`git diff --check` 已通過；顯示的 LF/CRLF 訊息是 Windows 換行格式警告，不是內容錯誤。

## 下一個對話的目標：打包成 Windows EXE

使用者下一步要把系統帶到其他電腦測試。建議先製作 PyInstaller `--onedir` 資料夾版，不要直接做 `--onefile`。

建議輸出結構：

```text
dist\INTJR\
├── INTJR.exe
├── templates\
├── static\
└── instance\
    ├── intjr.db
    └── backups\
```

打包時必須注意：

1. `templates`、`static` 必須能被 EXE 找到。
2. SQLite 資料庫要放在 EXE 外部的可寫入資料夾，不能放在唯讀的打包資源區。
3. 不要覆蓋或清除目前的 `instance/intjr.db`。
4. 先檢查 Python、PyInstaller、Flask、openpyxl 及專案啟動路徑，再建立建置腳本。
5. 建議讓 EXE 啟動 Flask 後開啟瀏覽器，仍使用 `127.0.0.1:5000`。
6. 建置完成後，使用新的乾淨 Windows 資料夾測試，不依賴開發機的 Python 或套件。
7. 至少測試：登入密碼、報工建立、掃描、五軸階段、報表、Excel、備份及資料庫 migration。

## 新對話可以直接貼上的指令

```text
請先完整閱讀 docs/handoff-2026-10-20-exe.md，再檢查目前工作樹與測試結果。我想把 INTJR Flask + SQLite 報工系統打包成可在其他 Windows 電腦執行的 EXE。請先檢查目前 Python、PyInstaller、專案結構與資料路徑，優先實作穩定的 PyInstaller --onedir 版本。不要清除、reset、覆蓋或提交 instance/intjr.db，也不要直接做 --onefile。
```

