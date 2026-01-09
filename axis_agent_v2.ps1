# =============================================================================
# AXIS AGENT V2 - Agent PowerShell amélioré pour MS-01
# ICI Dordogne - 09/01/2026
# =============================================================================
# Améliorations:
# - Polling toutes les 2 secondes (au lieu de 5)
# - Exécution asynchrone des commandes longues
# - Timeout configurable par commande
# - Meilleure gestion des erreurs
# - Logs détaillés
# =============================================================================

param(
    [string]$Token = "ici-dordogne-2026",
    [string]$Url = "https://baby-axys-production.up.railway.app",
    [int]$PollInterval = 2,
    [int]$CommandTimeout = 120
)

$ErrorActionPreference = "Continue"
$Host.UI.RawUI.WindowTitle = "AXIS Agent V2"

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $color = switch($Level) {
        "INFO" { "White" }
        "SUCCESS" { "Green" }
        "WARNING" { "Yellow" }
        "ERROR" { "Red" }
        default { "White" }
    }
    Write-Host "[$timestamp] [$Level] $Message" -ForegroundColor $color
}

function Send-Result {
    param(
        [string]$CmdId,
        [string]$Result,
        [bool]$Success = $true
    )
    try {
        $body = @{
            result = $Result
            success = $Success
        } | ConvertTo-Json -Compress
        
        $response = Invoke-RestMethod -Uri "$Url/agent/result/$CmdId" `
            -Method POST `
            -Headers @{ "X-Agent-Token" = $Token } `
            -Body $body `
            -ContentType "application/json" `
            -TimeoutSec 10 `
            -ErrorAction Stop
        
        return $true
    }
    catch {
        Write-Log "Erreur envoi résultat: $_" "ERROR"
        return $false
    }
}

function Execute-Command {
    param(
        [string]$CmdId,
        [string]$Command
    )
    
    Write-Log "Exécution: $Command" "INFO"
    
    try {
        # Exécution avec timeout
        $job = Start-Job -ScriptBlock {
            param($cmd)
            Invoke-Expression $cmd 2>&1 | Out-String
        } -ArgumentList $Command
        
        $completed = Wait-Job $job -Timeout $CommandTimeout
        
        if ($completed) {
            $result = Receive-Job $job
            Remove-Job $job -Force
            Write-Log "Commande terminée" "SUCCESS"
            Send-Result -CmdId $CmdId -Result $result -Success $true
        }
        else {
            Stop-Job $job
            Remove-Job $job -Force
            Write-Log "Timeout après ${CommandTimeout}s" "WARNING"
            Send-Result -CmdId $CmdId -Result "Timeout après ${CommandTimeout}s" -Success $false
        }
    }
    catch {
        $errorMsg = $_.Exception.Message
        Write-Log "Erreur: $errorMsg" "ERROR"
        Send-Result -CmdId $CmdId -Result "Erreur: $errorMsg" -Success $false
    }
}

# Banner
Write-Host ""
Write-Host "  ╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "  ║  🤖 AXIS AGENT V2 - ICI Dordogne                          ║" -ForegroundColor Cyan
Write-Host "  ║  Pilotage distant MS-01                                   ║" -ForegroundColor Cyan
Write-Host "  ╚═══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Log "Démarrage agent..." "INFO"
Write-Log "URL: $Url" "INFO"
Write-Log "Poll: ${PollInterval}s | Timeout: ${CommandTimeout}s" "INFO"
Write-Host ""

# Vérification connexion
try {
    $status = Invoke-RestMethod -Uri "$Url/agent/status" `
        -Headers @{ "X-Agent-Token" = $Token } `
        -TimeoutSec 5
    Write-Log "Connecté à Railway ✓" "SUCCESS"
}
catch {
    Write-Log "Impossible de se connecter à Railway" "ERROR"
    Write-Log "Vérifiez l'URL et le token" "ERROR"
    exit 1
}

# Boucle principale
Write-Log "En attente de commandes... (Ctrl+C pour arrêter)" "INFO"
Write-Host ""

$lastPoll = [DateTime]::MinValue

while ($true) {
    try {
        # Poll les commandes en attente
        $response = Invoke-RestMethod -Uri "$Url/agent/pending" `
            -Headers @{ "X-Agent-Token" = $Token } `
            -TimeoutSec 5 `
            -ErrorAction Stop
        
        if ($response.commands -and $response.commands.Count -gt 0) {
            foreach ($cmd in $response.commands) {
                Write-Host ""
                Write-Log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" "INFO"
                Write-Log "Nouvelle commande: $($cmd.id)" "INFO"
                Execute-Command -CmdId $cmd.id -Command $cmd.command
                Write-Log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" "INFO"
                Write-Host ""
            }
        }
    }
    catch {
        # Erreur silencieuse (réseau, etc.)
        Write-Host "." -NoNewline -ForegroundColor DarkGray
    }
    
    Start-Sleep -Seconds $PollInterval
}
