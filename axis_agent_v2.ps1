# AXIS AGENT V2 - Agent PowerShell pour MS-01
# ICI Dordogne - 09/01/2026

param(
    [string]$Token = "ici-dordogne-2026",
    [string]$Url = "https://baby-axys-production.up.railway.app",
    [int]$PollInterval = 2,
    [int]$CommandTimeout = 120
)

$ErrorActionPreference = "Continue"

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
        
        Invoke-RestMethod -Uri "$Url/agent/result/$CmdId" -Method POST -Headers @{ "X-Agent-Token" = $Token } -Body $body -ContentType "application/json" -TimeoutSec 10 -ErrorAction Stop | Out-Null
        return $true
    }
    catch {
        Write-Log "Erreur envoi resultat: $_" "ERROR"
        return $false
    }
}

function Execute-Command {
    param(
        [string]$CmdId,
        [string]$Command
    )
    
    Write-Log "Exec: $Command" "INFO"
    
    try {
        $result = Invoke-Expression $Command 2>&1 | Out-String
        Write-Log "OK" "SUCCESS"
        Send-Result -CmdId $CmdId -Result $result -Success $true
    }
    catch {
        $errorMsg = $_.Exception.Message
        Write-Log "Erreur: $errorMsg" "ERROR"
        Send-Result -CmdId $CmdId -Result "Erreur: $errorMsg" -Success $false
    }
}

# Banner
Write-Host ""
Write-Host "  =========================================" -ForegroundColor Cyan
Write-Host "  AXIS AGENT V2 - ICI Dordogne" -ForegroundColor Cyan
Write-Host "  Pilotage distant MS-01" -ForegroundColor Cyan
Write-Host "  =========================================" -ForegroundColor Cyan
Write-Host ""
Write-Log "Demarrage agent..." "INFO"
Write-Log "URL: $Url" "INFO"
Write-Log "Poll: ${PollInterval}s" "INFO"
Write-Host ""

# Verification connexion
try {
    $status = Invoke-RestMethod -Uri "$Url/agent/status" -Headers @{ "X-Agent-Token" = $Token } -TimeoutSec 5
    Write-Log "Connecte a Railway" "SUCCESS"
}
catch {
    Write-Log "Impossible de se connecter a Railway" "ERROR"
    exit 1
}

Write-Log "En attente de commandes... (Ctrl+C pour arreter)" "INFO"
Write-Host ""

# Boucle principale
while ($true) {
    try {
        $response = Invoke-RestMethod -Uri "$Url/agent/pending" -Headers @{ "X-Agent-Token" = $Token } -TimeoutSec 5 -ErrorAction Stop
        
        if ($response.commands -and $response.commands.Count -gt 0) {
            foreach ($cmd in $response.commands) {
                Write-Host ""
                Write-Log "Nouvelle commande: $($cmd.id)" "INFO"
                Execute-Command -CmdId $cmd.id -Command $cmd.command
                Write-Host ""
            }
        }
    }
    catch {
        # Silencieux
    }
    
    Start-Sleep -Seconds $PollInterval
}
