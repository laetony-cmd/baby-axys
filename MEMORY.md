# MEMORY - CONSIGNES POUR AXIS

*Mise à jour: V19.3 - 7 janvier 2026*

## WORKFLOW OBLIGATOIRE

À chaque début de conversation, Axis doit:
1. Appeler GET /memory sur ce service
2. Lire et appliquer ces consignes
3. Ne jamais ignorer ces règles

## RÈGLES ABSOLUES

### Emails
- ❌ Jamais d'envoi sans accord explicite de Ludo
- ✅ Toujours laetony@gmail.com en copie

### Validation
- ❌ Ne RIEN lancer/exécuter/déployer sans validation Ludo
- ❌ Ne jamais changer de sujet sans confirmation que le précédent est terminé

### Qualité
- ✅ Toujours être critique sur le travail fait
- ✅ Identifier les failles/manques AVANT de proposer la suite

## VERSION ACTUELLE

**V19.3 BUNKER + AGENT + SWEEPBRIGHT** - Déployé le 7 janvier 2026

### Features V19.3
- Agent MS-01 (pilotage PowerShell distant)
- Webhook SweepBright (réception publications)
- Table v19_biens (stockage permanent biens)
- Parsing enrichi (référence, négociateur, mandat, aménités)
- Tables préfixées v19_* (isolation stricte)
- Pool PostgreSQL thread-safe
- Interface Chat HTML complète
- Recherche Web Tavily CORRIGÉE

### Endpoints V19.3
- /health, /ready, /status
- /v19/brain, /v19/prospects, /v19/veille
- /memory, /briefing (legacy compatible)
- /, /chat, /nouvelle-session, /trio
- /agent/status, /agent/pending, /agent/execute, /agent/result/{id}
- /webhook/sweepbright, /sweepbright/biens, /sweepbright/resync

## AGENT MS-01

### Token
`ici-dordogne-2026` (header X-Agent-Token)

### Commande PowerShell pour lancer l'agent
```powershell
$token="ici-dordogne-2026"; $url="https://baby-axys-production.up.railway.app"; while($true){try{$r=Invoke-RestMethod "$url/agent/pending" -Headers @{"X-Agent-Token"=$token}; if($r.commands){foreach($c in $r.commands){Write-Host "Exec: $($c.command)" -ForegroundColor Yellow; $res=Invoke-Expression $c.command 2>&1|Out-String; Invoke-RestMethod "$url/agent/result/$($c.id)" -Method POST -Headers @{"X-Agent-Token"=$token} -Body (@{result=$res}|ConvertTo-Json) -ContentType "application/json" -ErrorAction SilentlyContinue|Out-Null; Write-Host "OK" -ForegroundColor Green}}}catch{Write-Host "." -NoNewline}; Start-Sleep 5}
```

## SWEEPBRIGHT

### Webhook URL
https://baby-axys-production.up.railway.app/webhook/sweepbright

### Biens stockés (07/01/2026)
- 41710 - Saint Félix de Villadeix - 577.500€
- 41693 - Manzac-sur-Vern - 198.000€
- 41687 - Saint Geyrac - 395.000€

## CREDENTIALS ACTIFS

### Gmail SMTP
- Email: u5050786429@gmail.com
- App password: izemquwmmqjdasrk

### Destinataires
- Principal: agence@icidordogne.fr
- Copie: laetony@gmail.com

## VEILLES ✅ OPÉRATIONNELLES

### 1. Veille DPE
- Cron: 08h00 Paris
- Status: ✅ Opérationnelle

### 2. Veille Concurrence
- Cron: 07h00 Paris
- Status: ✅ Opérationnelle

## HISTORIQUE

| Date | Action |
|------|--------|
| 07/01/2026 | V19.3: Agent MS-01 + SweepBright Webhooks |
| 05/01/2026 | V19.2: Interface Chat + Tavily corrigé |
| 04/01/2026 | V19: Architecture Bunker déployée |
