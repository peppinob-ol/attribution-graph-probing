# Build script for the arXiv paper
# Run this after ensuring MiKTeX is properly installed and on PATH

Write-Host "Building Automated Circuit Interpretation via Probe Prompting paper..." -ForegroundColor Green

# Check if pdflatex is available
$pdflatex = Get-Command pdflatex -ErrorAction SilentlyContinue
if (-not $pdflatex) {
    Write-Host "ERROR: pdflatex not found in PATH" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please ensure MiKTeX is installed and on PATH:" -ForegroundColor Yellow
    Write-Host "  1. Run: winget install MiKTeX.MiKTeX" -ForegroundColor Yellow
    Write-Host "  2. Close and reopen PowerShell" -ForegroundColor Yellow
    Write-Host "  3. Run this script again" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Or manually add MiKTeX to PATH and restart PowerShell" -ForegroundColor Yellow
    exit 1
}

Write-Host "Found pdflatex at: $($pdflatex.Source)" -ForegroundColor Cyan

# Navigate to paper directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# Clean previous build artifacts
Write-Host "Cleaning previous build..." -ForegroundColor Yellow
Remove-Item -Path "*.aux", "*.log", "*.out", "*.bbl", "*.blg", "*.toc" -ErrorAction SilentlyContinue

# First pass
Write-Host "Running pdflatex (pass 1/4)..." -ForegroundColor Yellow
pdflatex -interaction=nonstopmode main.tex | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: First pdflatex pass failed. Check main.log for details." -ForegroundColor Red
    exit 1
}

# BibTeX
Write-Host "Running bibtex..." -ForegroundColor Yellow
bibtex main | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "WARNING: bibtex failed. Continuing anyway..." -ForegroundColor Yellow
}

# Second pass
Write-Host "Running pdflatex (pass 2/4)..." -ForegroundColor Yellow
pdflatex -interaction=nonstopmode main.tex | Out-Null

# Third pass
Write-Host "Running pdflatex (pass 3/4)..." -ForegroundColor Yellow
pdflatex -interaction=nonstopmode main.tex | Out-Null

# Final pass
Write-Host "Running pdflatex (pass 4/4)..." -ForegroundColor Yellow
pdflatex -interaction=nonstopmode main.tex | Out-Null

if (Test-Path "main.pdf") {
    Write-Host ""
    Write-Host "SUCCESS! Paper built successfully." -ForegroundColor Green
    Write-Host "Output: main.pdf" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "To view the PDF:" -ForegroundColor Yellow
    Write-Host "  Invoke-Item main.pdf" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "ERROR: PDF was not generated. Check main.log for errors." -ForegroundColor Red
    exit 1
}







