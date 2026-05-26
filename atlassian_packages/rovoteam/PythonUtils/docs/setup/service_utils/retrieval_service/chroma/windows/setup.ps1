# ChromaDB Setup Script for Windows
# ChromaDB is an embedded library — no server required.

Write-Host "=== ChromaDB Setup ===" -ForegroundColor Cyan

Write-Host "Installing Python package..." -ForegroundColor Green
pip install chromadb

Write-Host "`nVerifying installation..." -ForegroundColor Yellow
python -c "import chromadb; c = chromadb.Client(); print('ChromaDB version:', chromadb.__version__)"

Write-Host "`n=== ChromaDB setup complete ===" -ForegroundColor Green
Write-Host "ChromaDB runs embedded — no server needed."
Write-Host "The default embedding model (all-MiniLM-L6-v2) downloads on first use."
