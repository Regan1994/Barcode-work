# 驗收清單

- [ ] 新電腦依 README 可建立環境並在 127.0.0.1 啟動。
- [ ] 可建立機型與 E-01～E-10，且語意顯示 unknown。
- [ ] 可用連續範圍與非連續多選建立批次。
- [ ] 每個 job_run 有成對 START／FINISH Code128，重新列印識別碼不變。
- [ ] USB HID 掃描可完成 created → started → finished。
- [ ] 重複掃描、未 START 直接 FINISH、無效 payload 有正確提示且不誤改資料。
- [ ] Excel 單一工作表包含機型、製號、狀態、開始時間、結束時間、時長、組裝人員。
- [ ] 備份檔可通過 SQLite integrity_check。
- [ ] 無網路時仍可建立、掃描、列印與匯出。
- [ ] D01～D06 均有現場確認結果後，才把決策寫入 decision-log.md。

