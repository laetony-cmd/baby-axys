# MEMORY - CONSIGNES POUR AXIS

*Mise à jour: 09 janvier 2026*

## WORKFLOW OBLIGATOIRE

À chaque début de conversation, Axis doit:
1. Appeler GET /memory ou GET /briefing
2. Lire et appliquer ces consignes
3. Utiliser l'agent MS-01 pour les actions

## RÈGLES ABSOLUES

- ❌ Jamais d'envoi email sans accord explicite de Ludo
- ✅ Toujours laetony@gmail.com en copie
- ❌ Ne RIEN lancer/exécuter/déployer sans validation Ludo

## MS-01 (SERVEUR AXISSERVEUR)

### Agent V19
- Script: C:\axi-v19\axis_agent_v19.ps1
- Démarrage auto: ✅ Tâche planifiée "AXIS_Agent_V19"
- Auto-login Windows: ✅ Configuré

### Commande agent
```bash
curl -s -X POST -H "X-Agent-Token: ici-dordogne-2026" -H "Content-Type: application/json" -d '{"command": "COMMANDE"}' https://baby-axys-production.up.railway.app/agent/execute
```

### Hardware
- CPU: Intel i5-12600H, RAM: 32 GB
- Disque C: 951 GB, Disque D: 3.7 TB

## DRIVE WATCHER (Transcription Audio)

### Configuration
- Script: C:\axi-v19\drive_watcher_zip.py
- Dossier Drive: Audios_Terrain
- Folder ID: 1iKPgQa6NUJo8ETaMsM3MLNM7uKnZW5uJ
- Compte: agence@icidordogne.fr

### Commande transcription
```
python C:\axi-v19\drive_watcher_zip.py 1iKPgQa6NUJo8ETaMsM3MLNM7uKnZW5uJ --once
```

### Télécharger TOUS les fichiers (photos, zip, etc.)
```
python C:\axi-v19\download_all.py
```

### Résultats
- Transcriptions: C:\axi-v19\transcriptions\
- Downloads: C:\axi-v19\downloads\

## DOCKER CONTAINERS MS-01

- postgres-axi: Port 5432 ✅
- axi-agences: Port 8080 ✅  
- axi-v19: Actif ✅
- ollama: Port 11434

## VEILLES

- Veille DPE: 08h00 Paris ✅
- Veille Concurrence: 07h00 Paris ✅

## NOTES IMPORTANTES

1. Si agent timeout → faire exécuter directement sur MS-01
2. Dossier Audios_Terrain peut contenir: ZIP (audio), JPG (photos)
3. download_all.py télécharge TOUS les fichiers (pas juste audio)
4. Credentials dans fichier CREDENTIALS_REFERENCE.md séparé
