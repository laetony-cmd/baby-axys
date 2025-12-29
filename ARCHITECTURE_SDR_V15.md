# ARCHITECTURE SDR V15 BLINDÉE - PROTOCOLE SWEEPBRIGHT

*Date: 29/12/2025*
*Version: 15.0*
*Statut: DÉPLOYÉ*

---

## 🎯 RÈGLE D'OR

> **"Si une demande arrive avec un prix X, le bien EXISTE OBLIGATOIREMENT sur le site à ce prix X. Si Axis ne le trouve pas, c'est qu'Axis est aveugle, pas que le bien n'existe pas."**

---

## 🔧 CORRECTIONS CRITIQUES V15

### BUG RÉSOLU: Limite de pagination

| Avant (V14) | Après (V15) |
|-------------|-------------|
| Scraping pages 1-10 | Scraping jusqu'à HTTP 404 |
| REF 41604 (page 12) RATÉE | REF 41604 TROUVÉE ✅ |
| ~120 biens indexés | ~180 biens indexés |

### Code corrigé:

```python
while True:
    url = BASE_URL if page == 1 else f"{BASE_URL}page/{page}/"
    # ... scrape ...
    page += 1
    if page > 50:  # Sécurité max
        break
    # Arrêt naturel: HTTP 404 ou 0 biens trouvés
```

---

## 📊 ALGORITHME DE MATCHING "LUDO"

### Entonnoir de Précision

```
┌─────────────────────────────────────────────────────────────┐
│  ENTRÉE: Demande prospect (prix, surface, pièces, ville)    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 1: PRIX EXACT (Pivot Absolu)                         │
│  ─────────────────────────────────                          │
│  • Tolérance: 0€ (STRICT)                                   │
│  • SELECT * FROM cache WHERE prix = X                       │
│  • Si 0 résultat → SCRAPING D'URGENCE puis retry            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 2: TRI (si plusieurs résultats)                      │
│  ─────────────────────────────────────                      │
│  1. Filtre SURFACE (±5m² tolérance)                         │
│  2. Filtre VILLE du bien                                    │
│  3. Filtre PIÈCES si disponible                             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 3: TRELLO (Recherche proprio)                        │
│  ───────────────────────────────────                        │
│  Priorité 1: REF dans titres (boards BIENS + VENTES)        │
│  Priorité 2: URL site dans descriptions                     │
│  Priorité 3: Recherche globale Trello                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  SORTIE: {bien_site, bien_trello, proprio}                  │
│  OU                                                         │
│  FAIL-SAFE: Carte "NON IDENTIFIÉ" (jamais de faux positif)  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🌐 ENDPOINTS V15

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/sync-site` | GET | Force synchronisation cache site |
| `/match-test?prix=X&surface=Y` | GET | Test matching V15 |
| `/status` | GET | Statut général + infos V15 |

### Exemple:

```bash
# Sync cache
curl https://baby-axys-production.up.railway.app/sync-site

# Test matching
curl "https://baby-axys-production.up.railway.app/match-test?prix=118250&surface=140"
```

---

## 📁 STRUCTURE CODE

```
main.py (V15)
├── ScraperV15              # Scraper exhaustif (while jusqu'à 404)
│   ├── scrape_all_pages()  # Scan complet
│   ├── find_by_prix_exact()# Recherche prix strict
│   └── cache[]             # Cache local des biens
│
├── MatchingEngineV15       # Moteur matching
│   ├── match_prospect()    # Algorithme LUDO
│   ├── _find_trello()      # Recherche proprio
│   └── sync()              # Force sync
│
├── get_matching_v15()      # Singleton
│
└── workflow_sdr_complet()  # Intègre matching V15
```

---

## 🧪 TESTS VALIDÉS

| Test | Prix | Surface | REF Attendue | Résultat |
|------|------|---------|--------------|----------|
| Marie bnmy | 118 250€ | 140m² | 41604 | ✅ |
| Lajoe | 81 750€ | 80m² | 41712 | ✅ |
| PERINOT | 56 100€ | - | 41671 | ✅ |

---

## 🚨 FAIL-SAFES

1. **Scraping d'urgence**: Si prix non trouvé dans cache → re-scrape complet
2. **Limite 50 pages**: Évite boucle infinie
3. **Timeout 15s**: Par requête HTTP
4. **Carte "NON IDENTIFIÉ"**: Si matching échoue après toutes tentatives
5. **JAMAIS de faux positif**: Mieux vaut carte vide que mauvais match

---

## 📅 HISTORIQUE

| Date | Version | Action |
|------|---------|--------|
| 29/12/2025 | V15.0 | Scraping exhaustif (while 404), algo LUDO |
| 27/12/2025 | V14.6 | FORTERESSE (normalisation champs) |
| 24/12/2025 | V10 | Code unifié (chat + veilles) |

---

## 🔑 PRINCIPE SWEEPBRIGHT

> Sweepbright synchronise Pubs + Site. Si prospect clique sur annonce → bien existe sur site au même prix.
> 
> **Conséquence**: Tolérance prix = 0€. Pas d'approximation.

---

*Document maintenu par Axis pour Ludo - ICI Dordogne*
