# 🔐 CREDENTIALS ET CONFIGURATIONS - ICI DORDOGNE

**Version : V19.1.0 BUNKER**  
**Dernière mise à jour : 4 janvier 2026**

---

## ⚠️ ATTENTION

Ce fichier est une **référence de structure**. Les vraies valeurs sont :
- Dans les **variables d'environnement Railway**
- Dans le **projet Claude.ai** (fichier complet)
- **JAMAIS sur GitHub** (sécurité)

---

## 1. 🚂 RAILWAY - VARIABLES D'ENVIRONNEMENT

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Clé API Claude |
| `GITHUB_TOKEN` | Token GitHub (expire 27 mars 2026) |
| `GMAIL_USER` | Email pour notifications |
| `GMAIL_APP_PASSWORD` | App password Gmail |
| `TAVILY_API_KEY` | Recherche web IA |
| `TRELLO_KEY` | API Trello |
| `TRELLO_TOKEN` | Token Trello |
| `SDR_AUTO_EMAILS` | `false` par défaut |
| `VAPI_PUBLIC_KEY` | Visites vocales |
| `VAPI_ASSISTANT_ID` | Assistant Riley |
| `AXI_API_SECRET` | 🔒 **Token sécurité API V19** |
| `DATABASE_URL` | PostgreSQL (auto Railway) |

---

## 2. 🐙 GITHUB

| Paramètre | Valeur |
|-----------|--------|
| Username | `laetony-cmd` |
| Token | *(voir Railway)* |
| Expiration | **27 mars 2026** |

### Repos

| Repo | Usage |
|------|-------|
| `baby-axys` | Serveur Axi V19 (Railway) |
| `axi-agences` | Opérationnel agences |
| `axi-antho` | Webhooks SweepBright |
| `ici-dordogne-sites` | Templates sites vitrines |

---

## 3. 🚂 RAILWAY - SERVICES

### baby-axys (V19.1.0)

| Paramètre | Valeur |
|-----------|--------|
| URL Production | `https://baby-axys-production.up.railway.app` |
| Version | **V19.1.0 BUNKER (sécurisée)** |
| Architecture | `axi_v19/` modulaire |

### Endpoints publics

- `/health`, `/ready`, `/status`
- `/memory`, `/briefing`
- `/v19/brain` (GET), `/v19/prospects`, `/v19/veille`

### Endpoints protégés (token requis)

- `/run-veille` - Veille DPE
- `/run-veille-concurrence` - Veille 16 agences
- `/v19/brain` (POST) - Écriture mémoire

### axi-antho

| URL | `https://axi-antho-production.up.railway.app` |
|-----|---------------------------------------------|

---

## 4. 📧 GMAIL

| Compte | Usage |
|--------|-------|
| `u5050786429@gmail.com` | Notifications veilles V19 |
| `laetony@gmail.com` | SDR / Principal |
| `agence@icidordogne.fr` | Email agence |

**Copie obligatoire :** laetony@gmail.com (TOUJOURS)

---

## 5. 🌐 SERVICES EXTERNES

| Service | Console |
|---------|---------|
| Anthropic | https://console.anthropic.com |
| Trello | https://trello.com |
| Tavily | https://app.tavily.com |
| VAPI | https://dashboard.vapi.ai |
| Netlify | https://app.netlify.com |
| HeyGen | https://app.heygen.com |
| Apify | https://console.apify.com |
| SweepBright | https://app.sweepbright.com |

---

## 6. 🔔 VEILLES V19

| Veille | Heure Paris | Agences |
|--------|-------------|---------|
| Concurrence | 07:00 | 16 |
| DPE | 08:00 | 12 CP |

---

## 7. 📅 DATES IMPORTANTES

| Quoi | Date |
|------|------|
| Token GitHub expire | **27 mars 2026** |
| Tirage Bio Vergt | **7 janvier 2026** |
| Départ Maroc | Fin janvier 2026 |

---

## 8. 🔄 COMMANDES

```bash
# Health check
curl https://baby-axys-production.up.railway.app/health

# Status
curl https://baby-axys-production.up.railway.app/status

# Veille (avec token)
curl "https://baby-axys-production.up.railway.app/run-veille?token=<AXI_API_SECRET>"
```

---

**📍 Fichier complet avec secrets : Projet Claude.ai uniquement**

*"Je ne lâche pas." 💪*
