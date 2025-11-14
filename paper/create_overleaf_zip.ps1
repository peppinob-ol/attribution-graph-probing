# Create Overleaf-ready zip file
# Run this from the paper/ directory or parent directory

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$paperDir = $scriptDir
$outputZip = Join-Path (Split-Path -Parent $paperDir) "paper_overleaf.zip"

Write-Host "Creating Overleaf zip package..." -ForegroundColor Green
Write-Host "Source: $paperDir" -ForegroundColor Cyan
Write-Host "Output: $outputZip" -ForegroundColor Cyan

# Remove old zip if exists
if (Test-Path $outputZip) {
    Remove-Item $outputZip -Force
    Write-Host "Removed old zip file" -ForegroundColor Yellow
}

# Create zip excluding build artifacts and scripts
$excludeFiles = @("*.ps1", "*.mk", "*.aux", "*.log", "*.out", "*.bbl", "*.blg", "*.toc", "*.pdf", "build.ps1", "arxiv.mk", "create_overleaf_zip.ps1")

# Get all files to include
$filesToZip = Get-ChildItem -Path $paperDir -Recurse -File | Where-Object {
    $file = $_
    $shouldExclude = $false
    foreach ($pattern in $excludeFiles) {
        if ($file.Name -like $pattern) {
            $shouldExclude = $true
            break
        }
    }
    -not $shouldExclude
}

Write-Host "Files to include: $($filesToZip.Count)" -ForegroundColor Cyan

# Create temporary staging directory
$tempDir = Join-Path $env:TEMP "paper_staging_$(Get-Random)"
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

try {
    # Copy files maintaining structure
    foreach ($file in $filesToZip) {
        $relativePath = $file.FullName.Substring($paperDir.Length + 1)
        $destPath = Join-Path $tempDir $relativePath
        $destDir = Split-Path -Parent $destPath
        
        if (-not (Test-Path $destDir)) {
            New-Item -ItemType Directory -Path $destDir -Force | Out-Null
        }
        
        Copy-Item -Path $file.FullName -Destination $destPath -Force
    }
    
    # Create zip
    Compress-Archive -Path "$tempDir\*" -DestinationPath $outputZip -Force
    
    Write-Host ""
    Write-Host "SUCCESS! Overleaf package created." -ForegroundColor Green
    Write-Host "Location: $outputZip" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "  1. Go to https://www.overleaf.com" -ForegroundColor White
    Write-Host "  2. New Project > Upload Project" -ForegroundColor White
    Write-Host "  3. Upload: $outputZip" -ForegroundColor White
    Write-Host "  4. Compile and review" -ForegroundColor White
    Write-Host ""
    
    # Show zip contents
    Write-Host "Package contents:" -ForegroundColor Yellow
    $zipContents = Get-ChildItem -Path $tempDir -Recurse -File
    $zipContents | ForEach-Object {
        $rel = $_.FullName.Substring($tempDir.Length + 1)
        Write-Host "  $rel" -ForegroundColor Gray
    }
    
} finally {
    # Cleanup
    Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Zip file size: $([math]::Round((Get-Item $outputZip).Length / 1MB, 2)) MB" -ForegroundColor Cyan







