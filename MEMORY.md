# MEMORY - CONSIGNES POUR AXIS

*Mise à jour: V19.4 - 7 janvier 2026*

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

**V19.4 BUNKER + TRELLO** - Déployé le 7 janvier 2026

### Features V19.4 (NOUVEAU)
- Module Trello: Sync biens + Matching prospects
- Enrichissement v19_biens depuis Trello (proprio, TF, contact)
- Matching automatique Biens -> Acquéreurs
- Notifications désactivées par défaut (TRELLO_NOTIFICATIONS=false)
- Référentiel secteurs en PostgreSQL (v19_secteurs)

### Endpoints Trello V19.4
- /trello/status - Status du module
- /trello/sync - Sync Trello -> v19_biens (LIVE)
- /trello/match - Matching Biens -> Prospects (logs seulement)
- /trello/full - Sync + Match complet

### Features V19.3
- Agent MS-01: Pilotage PowerShell distant
- SweepBright: Webhooks + stockage biens

### Features V19.2
- Tables préfixées v19_* (isolation stricte)
- Interface Chat HTML complète
- Recherche Web Tavily (domaines français)

## INTERFACE CHAT

### ✅ URL Fonctionnelle
https://baby-axys-production.up.railway.app/

### ⚠️ axi.symbine.fr
Pointe encore vers AXIS Station local (ancien code v12).
→ Utiliser baby-axys-production.up.railway.app directement

## CREDENTIALS ACTIFS

### Gmail SMTP
- Email: u5050786429@gmail.com
- App password: izemquwmmqjdasrk

### Trello
- Key: dans variable TRELLO_KEY
- Token: dans variable TRELLO_TOKEN

### Destinataires
- Principal: agence@icidordogne.fr
- Copie: laetony@gmail.com

## VEILLES ✅ OPÉRATIONNELLES

### 1. Veille DPE
- Cron: 08h00 Paris
- Endpoint: /run-veille
- Status: ✅ Opérationnelle

### 2. Veille Concurrence
- Cron: 07h00 Paris
- Endpoint: /run-veille-concurrence
- Status: ✅ Opérationnelle

## MATCHING TRELLO

### Configuration
- Notifications: **DÉSACTIVÉES** (mode silencieux)
- Sync: **ACTIVÉ** (enrichissement v19_biens)
- Pour activer les notifs: TRELLO_NOTIFICATIONS=true

### Seuils de matching
- Budget: ±15% du prix du bien
- Match FORT: Budget OK + (REF citée OU secteur match)
- Match FAIBLE: Budget OK seulement

### Référentiel secteurs
Table v19_secteurs avec mots-clés et codes postaux.
Modifiable en base sans redéploiement.

## HISTORIQUE

| Date | Version | Modification |
|------|---------|--------------|
| **07/01/2026** | **V19.4** | **Module Trello (Sync + Matching)** |
| 07/01/2026 | V19.3 | Agent MS-01 + SweepBright Webhooks |
| 05/01/2026 | V19.2 | Interface Chat + Tavily corrigé |
| 05/01/2026 | V19.1 | Veilles opérationnelles, sécurité API |
| 04/01/2026 | V19.0 | Architecture Bunker déployée |

---

*"Je ne lâche pas." 💪*

## V19.4.1 - Module Trello (7 janvier 2026 08:05)

- Module trello.py avec register_routes
- Endpoints: /trello/status, /trello/sync, /trello/match, /trello/secteurs
- MODE SILENCIEUX: ENABLE_NOTIFICATIONS=False
- Sync Trello → v19_biens actif
- Matching loggé uniquement (pas de notifications Trello)
