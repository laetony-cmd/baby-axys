# 🚨 PRA - PLAN DE REPRISE D'ACTIVITÉ
## ICI Dordogne - Système Axi

**Version:** 1.0  
**Date:** 12 janvier 2026  
**Contact principal:** Ludo - laetony@gmail.com

---

## 📞 CONTACTS URGENCE

| Qui | Email | Rôle |
|-----|-------|------|
| Ludo | laetony@gmail.com | Décisions |
| Anthony | dorleanthony@gmail.com | Support technique |

---

## 🚦 SURVEILLANCE AUTOMATIQUE

### Healthchecks.io
- **URL Dashboard:** https://healthchecks.io (compte laetony@gmail.com)
- **Check MS-01:** Ping toutes les 15 minutes
- **Check Railway Veille DPE:** Ping toutes les 24h (après exécution veille)

### Alertes automatiques
- **Email:** laetony@gmail.com
- **Si veille plante:** Email automatique + ping Healthchecks FAIL

---

## 🔴 SCÉNARIO 1 : Railway ne répond plus

### Diagnostic
```bash
curl https://baby-axys-production.up.railway.app/health
```

### Actions
1. Vérifier https://railway.app (connexion GitHub laetony-cmd)
2. Vérifier les logs du service baby-axys
3. Redémarrer le service si nécessaire (Redeploy)
4. Si DOWN >1h : contacter support Railway

### Impact
- ❌ Veilles DPE/Concurrence arrêtées
- ❌ Chat Axi indisponible
- ✅ Données PostgreSQL préservées chez Railway

---

## 🟠 SCÉNARIO 2 : MS-01 ne répond plus

### Symptômes
- Healthchecks.io passe au rouge (check MS-01)
- Agent PowerShell timeout

### Actions
1. Contacter quelqu'un sur place (Peyrebrune) pour vérifier/redémarrer le PC
2. Vérifier/redémarrer la box internet si nécessaire
3. Bureau à distance : axiludo.duckdns.org:3389

### Impact
- ❌ Gmail Scraper arrêté
- ❌ Agent PowerShell indisponible
- ✅ Railway continue de fonctionner (veilles OK)

---

## 🟡 SCÉNARIO 3 : Veille DPE ne s'exécute pas

### Symptômes
- Pas de ping Healthchecks depuis >26h
- Email d'alerte "VEILLE DPE PLANTÉE"

### Diagnostic
```bash
# Vérifier les stats
curl "https://baby-axys-production.up.railway.app/veille/dpe/stats"

# Test manuel
curl "https://baby-axys-production.up.railway.app/veille/dpe/test-enrichie?token=<TOKEN>"
```

### Actions selon l'erreur
- **API ADEME down:** Attendre quelques heures
- **Erreur PostgreSQL:** Redémarrer service Railway
- **Erreur Trello:** Vérifier token Trello, cartes créées au prochain run

---

## 💾 PROCÉDURE BACKUP MANUEL

```bash
# Exporter les DPE
curl "https://baby-axys-production.up.railway.app/backup/dpe?token=<TOKEN>" > backup_dpe.json

# Vérifier le backup
curl "https://baby-axys-production.up.railway.app/backup/status?token=<TOKEN>"
```

Stocker sur Google Drive (dossier AXI_BACKUP) ou s'envoyer par email.

---

## 🔧 ACCÈS TECHNIQUES

> ⚠️ **Les tokens et mots de passe sont dans le fichier CREDENTIALS sécurisé**

### URLs principales
- **Railway:** https://baby-axys-production.up.railway.app
- **Railway Dashboard:** https://railway.app
- **GitHub Repo:** https://github.com/laetony-cmd/baby-axys
- **MS-01 DuckDNS:** axiludo.duckdns.org

---

## ✅ CHECKLIST AVANT DÉPART MAROC

- [ ] Healthchecks.io montre vert pour MS-01 et Railway
- [ ] Backup récent sur Google Drive
- [ ] Test veille DPE fonctionne
- [ ] Email alerte configuré sur laetony@gmail.com
- [ ] Quelqu'un peut intervenir physiquement sur MS-01 si besoin

---

*"Je ne lâche pas." 💪*
