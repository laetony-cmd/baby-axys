# ============================================================
# BACKUP AXI - PostgreSQL dans Docker
# ============================================================
# Ludo - ICI Dordogne - 24/12/2025
# ============================================================

# === CONFIGURATION ===
$CONTAINER = "postgres-axi"
$DB_USER = "postgres"
$DB_NAME = "axi"
$DB_PASSWORD = "axisstation"

# Chemins
$BACKUP_DIR = "C:\Users\laeto\Backups_Axi"
$USB_DESTINATION = "D:\Backups_Axi"  # Adapter selon ta clé USB

# Date pour le nom de fichier
$TIMESTAMP = Get-Date -Format "yyyy-MM-dd_HH-mm"
$FILENAME = "axi_backup_$TIMESTAMP.sql"

# === CRÉATION DU DOSSIER LOCAL SI ABSENT ===
if (!(Test-Path -Path $BACKUP_DIR)) { 
    New-Item -ItemType Directory -Path $BACKUP_DIR | Out-Null
    Write-Host "Dossier créé: $BACKUP_DIR" -ForegroundColor Yellow
}

# === 1. VÉRIFICATION CONTAINER ===
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  BACKUP AXI - PostgreSQL" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$containerRunning = docker ps --filter "name=$CONTAINER" --format "{{.Names}}"
if ($containerRunning -ne $CONTAINER) {
    Write-Host "❌ Container $CONTAINER non trouvé !" -ForegroundColor Red
    Write-Host "Lance: docker start $CONTAINER" -ForegroundColor Yellow
    exit 1
}
Write-Host "✅ Container $CONTAINER actif" -ForegroundColor Green

# === 2. EXÉCUTION DU DUMP VIA DOCKER ===
Write-Host ""
Write-Host "[$TIMESTAMP] Démarrage backup..." -ForegroundColor Cyan

# Dump dans le container puis copie vers Windows
docker exec $CONTAINER pg_dump -U $DB_USER -d $DB_NAME -F c -f /tmp/$FILENAME
docker cp ${CONTAINER}:/tmp/$FILENAME "$BACKUP_DIR\$FILENAME"
docker exec $CONTAINER rm /tmp/$FILENAME

if (Test-Path "$BACKUP_DIR\$FILENAME") {
    $size = (Get-Item "$BACKUP_DIR\$FILENAME").Length / 1KB
    Write-Host "✅ Dump réussi : $FILENAME ($([math]::Round($size,1)) KB)" -ForegroundColor Green
    
    # === 3. COPIE VERS USB / CLOUD ===
    if (Test-Path -Path $USB_DESTINATION) {
        if (!(Test-Path -Path $USB_DESTINATION)) {
            New-Item -ItemType Directory -Path $USB_DESTINATION | Out-Null
        }
        Copy-Item -Path "$BACKUP_DIR\$FILENAME" -Destination $USB_DESTINATION
        Write-Host "✅ Copie vers USB réussie: $USB_DESTINATION" -ForegroundColor Green
    } else {
        Write-Host "⚠️ USB non branchée ($USB_DESTINATION) - backup local uniquement" -ForegroundColor Yellow
    }
    
    # === 4. NETTOYAGE VIEUX BACKUPS (garde 7 derniers) ===
    $oldBackups = Get-ChildItem "$BACKUP_DIR\axi_backup_*.sql" | Sort-Object LastWriteTime -Descending | Select-Object -Skip 7
    if ($oldBackups) {
        $oldBackups | Remove-Item -Force
        Write-Host "🧹 Nettoyage: $($oldBackups.Count) vieux backups supprimés" -ForegroundColor Gray
    }
    
} else {
    Write-Host "❌ Erreur lors du dump" -ForegroundColor Red
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  BACKUP TERMINÉ" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Fichier: $BACKUP_DIR\$FILENAME" -ForegroundColor White
Write-Host ""
