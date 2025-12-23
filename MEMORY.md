# MEMORY - CONSIGNES POUR AXIS

*Dernière mise à jour: 23/12/2025*

## WORKFLOW OBLIGATOIRE

À chaque début de conversation, Axis doit:
1. Appeler GET /memory sur ce service
2. Lire et appliquer ces consignes
3. Ne jamais ignorer ces règles

## RÈGLES ABSOLUES

### Emails
- ❌ Jamais d envoi sans accord explicite de Ludo
- ✅ Toujours laetony@gmail.com en copie

### Validation
- ❌ Ne RIEN lancer/exécuter/déployer sans validation Ludo
- ❌ Ne jamais changer de sujet sans confirmation que le précédent est terminé

### Qualité
- ✅ Toujours être critique sur le travail fait
- ✅ Identifier les failles/manques AVANT de proposer la suite

## CREDENTIALS ACTIFS

### Gmail SMTP
- Email: u5050786429@gmail.com
- App password: izemquwmmqjdasrk

### Destinataires
- Principal: agence@icidordogne.fr
- Copie: laetony@gmail.com

## VEILLES ACTIVES

### 1. Veille DPE ✅ OPÉRATIONNELLE + DVF
- Cron: 08h00 Paris
- Endpoint: /run-veille
- Enrichissement: historique ventes DVF

### 2. Veille Concurrence ✅ OPÉRATIONNELLE
- Cron: 07h00 Paris
- Endpoint: /run-veille-concurrence
- Agences: 16

### 3. DVF ✅ NOUVEAU
- Endpoint: /dvf/stats, /dvf/enrichir
- Données: 2022-2024, Dordogne
- Parcelles indexées: 23 680

## AGENCES ICI DORDOGNE

### Structure
- **Vergt** : Agence principale
- **Le Bugue** : Deuxième agence
- **Équipe** : Anthony (opérationnel), Julie, Ingrid (validation NL)
- **Contact** : 05 53 13 33 33

### Stack technique
| Outil | Usage |
|-------|-------|
| SweepBright | CRM principal |
| Slack | Communication interne |
| Trello | Suivi dossiers |
| Gmail | Emails + Calendar |
| Google Ads | Campagnes (CPC 0.09€) |
| Netlify | Sites dédiés par bien |
| HeyGen | Vidéos présentation |

### Sites dédiés déployés
1. **Manzac** - nouveaute-maisonavendre-manzacsurvern.netlify.app (198K€, 99m²)
2. **Saint-Geyrac** - icidordogne-paradis-saint-geyrac.netlify.app (395K€)
3. Template validé : 3 langues (FR/EN/NL), chat IA, capture email

### Google Ads actif
- CPC: 0.09€ (marché = 1-3€)
- Clics: 1200+
- 1ère conversion: 6 décembre 2025

## SIMPLY PÉRIGORD

- **Activité** : Location saisonnière premium
- **Site** : simply-perigord.com
- **Positionnement** : Biens haut de gamme uniquement

## PLAN DIRECTEUR

- 6 semaines jusqu au Maroc
- Julie = prospection vendeurs
- Anthony = vente uniquement

## HISTORIQUE

| Date | Action |
|------|--------|
| 23/12/2025 | Sync mémoire agences + Simply depuis Axis |
| 22/12/2025 | v5: Enrichissement DVF intégré |
| 22/12/2025 | v4: 16 agences complètes |
| 22/12/2025 | v3: Veille concurrence intégrée |
| 22/12/2025 | Cron APScheduler intégré |
| 21/12/2025 | Création service unifié Railway |
