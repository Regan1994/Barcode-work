# 測試報告

執行命令：`pytest -q`

測試範圍：payload round trip、checksum、固定寬度機台範圍、機台編號語意驗證、重複選取機台防呆、非連續選擇、START／FINISH 狀態機與掃描冪等性、snapshot 保留、Excel 匯出、資料庫 foreign keys。

目前結果：6 passed。

實機 Windows 印表機與 USB HID 掃描器測試需在現場硬體可用後補登結果。

