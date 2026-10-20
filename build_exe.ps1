$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

Write-Host "Running tests..."
python -m pytest -q --basetemp .pytest-tmp

Write-Host "Building INTJR onedir package..."
python -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --name INTJR `
    --contents-directory . `
    --add-data "templates;templates" `
    --add-data "static;static" `
    app.py

New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot "dist\INTJR\instance\backups") | Out-Null

Write-Host ""
Write-Host "Build complete: $PSScriptRoot\dist\INTJR"
Write-Host "Run: .\dist\INTJR\INTJR.exe"
