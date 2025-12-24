# ============================================================
# AXI V11 - INSTALLATION POSTGRESQL SUR MS-01
# ============================================================
# Exécuter dans PowerShell en tant qu'Administrateur
# ============================================================

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AXI V11 - INSTALLATION POSTGRESQL" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Vérifier Docker
Write-Host "[1/5] Vérification Docker..." -ForegroundColor Yellow
$dockerCheck = docker ps 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERREUR: Docker n'est pas lancé !" -ForegroundColor Red
    exit 1
}
Write-Host "Docker OK" -ForegroundColor Green

# 2. Vérifier postgres-axi
Write-Host "[2/5] Vérification container postgres-axi..." -ForegroundColor Yellow
$pgCheck = docker ps --filter "name=postgres-axi" --format "{{.Names}}"
if ($pgCheck -ne "postgres-axi") {
    Write-Host "Container postgres-axi non trouvé. Création..." -ForegroundColor Yellow
    docker run -d --name postgres-axi -e POSTGRES_PASSWORD=axisstation -e POSTGRES_DB=axi -p 5432:5432 -v pgdata:/var/lib/postgresql/data postgres:16
    Start-Sleep -Seconds 5
}
Write-Host "postgres-axi OK" -ForegroundColor Green

# 3. Télécharger le schéma SQL
Write-Host "[3/5] Téléchargement schéma SQL..." -ForegroundColor Yellow
$sqlUrl = "https://raw.githubusercontent.com/laetony-cmd/baby-axys/main/init_schema_v4_final.sql"
$sqlPath = "$env:USERPROFILE\init_schema.sql"
Invoke-WebRequest -Uri $sqlUrl -OutFile $sqlPath
Write-Host "Schéma téléchargé: $sqlPath" -ForegroundColor Green

# 4. Exécuter le schéma
Write-Host "[4/5] Création des tables PostgreSQL..." -ForegroundColor Yellow
Get-Content $sqlPath | docker exec -i postgres-axi psql -U postgres -d axi
Write-Host "Tables créées" -ForegroundColor Green

# 5. Vérifier les tables
Write-Host "[5/5] Vérification des tables..." -ForegroundColor Yellow
docker exec postgres-axi psql -U postgres -d axi -c "\dt"

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  INSTALLATION TERMINÉE !" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Tables créées:" -ForegroundColor Cyan
Write-Host "  - relations (personnes)" -ForegroundColor White
Write-Host "  - biens (DPE, annonces)" -ForegroundColor White
Write-Host "  - souvenirs (conversations)" -ForegroundColor White
Write-Host "  - faits (connaissances)" -ForegroundColor White
Write-Host "  - documents (OCR)" -ForegroundColor White
Write-Host ""
Write-Host "PostgreSQL prêt pour Axi v11 !" -ForegroundColor Green
Write-Host ""
