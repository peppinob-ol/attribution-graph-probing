# Circuit Analysis Pipeline - Full Execution
# Esegue l'intera pipeline di analisi antropologica delle feature

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Circuit Analysis Pipeline - Full Run" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# Verifica prerequisiti
Write-Host "`nVerifica prerequisiti..." -ForegroundColor Yellow

$requiredFiles = @(
    "output\example_graph.pt",
    "output\graph_feature_static_metrics (1).csv",
    "output\acts_compared.csv"
)

$missing = @()
foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        $sizeMB = [math]::Round((Get-Item $file).Length / 1MB, 1)
        Write-Host "  OK $file ($sizeMB MB)" -ForegroundColor Green
    } else {
        Write-Host "  MANCANTE $file" -ForegroundColor Red
        $missing += $file
    }
}

if ($missing.Count -gt 0) {
    Write-Host "`nErrore: File mancanti! Scaricali da Colab prima di continuare." -ForegroundColor Red
    exit 1
}

Write-Host "`nTutti i prerequisiti presenti. Avvio pipeline...`n" -ForegroundColor Green

# Step 1: Anthropological Basic
Write-Host "Step 1: Anthropological Basic Analysis..." -ForegroundColor Cyan
python scripts\01_anthropological_basic.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "Errore in Step 1" -ForegroundColor Red
    exit 1
}

# Step 2: Compute Thresholds
Write-Host "`nStep 2: Compute Robust Thresholds..." -ForegroundColor Cyan
python scripts\02_compute_thresholds.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "Errore in Step 2" -ForegroundColor Red
    exit 1
}

# Step 3: Cicciotti Supernodes
Write-Host "`nStep 3: Cicciotti Supernodes (Semantic)..." -ForegroundColor Cyan
python scripts\03_cicciotti_supernodes.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "Errore in Step 3" -ForegroundColor Red
    exit 1
}

# Step 4: Final Clustering
Write-Host "`nStep 4: Final Optimized Clustering..." -ForegroundColor Cyan
python scripts\04_final_optimized_clustering.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "Errore in Step 4" -ForegroundColor Red
    exit 1
}

# Step 5: Verify Logit Influence
Write-Host "`nStep 5: Verify Logit Influence..." -ForegroundColor Cyan
python scripts\05_verify_logit_influence.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "Errore in Step 5" -ForegroundColor Red
    exit 1
}

# Step 6: Visualizzazioni (opzionale)
Write-Host "`nStep 6: Visualizzazioni ed Export..." -ForegroundColor Cyan

if (Test-Path "scripts\visualization\visualize_feature_space_3d.py") {
    Write-Host "  - Visualizzazione 3D..." -ForegroundColor Gray
    python scripts\visualization\visualize_feature_space_3d.py
}

if (Test-Path "scripts\visualization\neuronpedia_export.py") {
    Write-Host "  - Export Neuronpedia..." -ForegroundColor Gray
    python scripts\visualization\neuronpedia_export.py
}

# Riepilogo finale
Write-Host "`n=========================================" -ForegroundColor Cyan
Write-Host "PIPELINE COMPLETATA CON SUCCESSO" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Cyan

# Mostra risultati
Write-Host "`nRisultati:" -ForegroundColor Yellow

if (Test-Path "output\logit_influence_validation.json") {
    $validation = Get-Content "output\logit_influence_validation.json" | ConvertFrom-Json
    Write-Host "  Coverage: $($validation.coverage_percentage)% ($($validation.rating))" -ForegroundColor Green
}

if (Test-Path "output\final_anthropological_optimized.json") {
    $final = Get-Content "output\final_anthropological_optimized.json" | ConvertFrom-Json
    $nSemantic = ($final.semantic_supernodes | Get-Member -MemberType NoteProperty).Count
    $nComputational = ($final.computational_supernodes | Get-Member -MemberType NoteProperty).Count
    Write-Host "  Supernodi: $($nSemantic + $nComputational) ($nSemantic semantic + $nComputational computational)" -ForegroundColor Green
}

Write-Host "`nFile di output in: output\" -ForegroundColor Cyan
Write-Host "Consulta circuit_analysis_pipeline.ipynb per analisi dettagliata.`n" -ForegroundColor Cyan
