# LanceDB Setup Script for Windows
# LanceDB is an embedded database — no server required.

Write-Host "=== LanceDB Setup ===" -ForegroundColor Cyan

Write-Host "Installing LanceDB..." -ForegroundColor Green
pip install lancedb

Write-Host "`nInstalling tantivy (optional, enables hybrid BM25+vector search)..." -ForegroundColor Yellow
pip install tantivy 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  tantivy install failed (optional). Vector-only search will still work." -ForegroundColor Yellow
}

Write-Host "`nVerifying installation..." -ForegroundColor Yellow
python -c "import lancedb; print('LanceDB version:', lancedb.__version__)"

Write-Host "`n=== LanceDB setup complete ===" -ForegroundColor Green
Write-Host "LanceDB runs embedded — no server needed."
Write-Host "An embedding_function is required when constructing LanceDBRetrievalService."
