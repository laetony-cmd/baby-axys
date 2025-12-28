# ARCHITECTURE SDR V14 - ICI DORDOGNE
## Système de Matching & Engagement Prospect Automatisé

**Version:** 14.3 (28/12/2025)  
**Auteur:** Axis (Claude) + Ludo + Lumo  
**Repository:** `laetony-cmd/baby-axys`

---

## 1. VUE D'ENSEMBLE DU FLUX

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│   SOURCES       │     │   IMPORT     │     │   MATCHING      │
│                 │     │              │     │   ENGINE        │
│ • Leboncoin     │────▶│ Webhook      │────▶│                 │
│ • Email         │     │ /webhook/    │     │ find_best_match │
│ • Site ICI      │     │ mail-acquereur│    │ scoring SQL     │
└─────────────────┘     └──────────────┘     └────────┬────────┘
                                                      │
                                                      ▼
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│   CHATBOT       │◀────│   EMAIL      │◀────│   TRELLO        │
│                 │     │   HOOK       │     │                 │
│ /chat/card/{id} │     │              │     │ Carte Acquéreur │
│ Optimistic UI   │     │ send_hook_   │     │ + Labels        │
│ Golden Ticket   │     │ email()      │     │ + Checklists    │
└─────────────────┘     └──────────────┘     └─────────────────┘
```

### Chemin complet d'un prospect :

1. **Entrée** : Prospect contacte via Leboncoin/Email/Site
2. **Import** : Script externe ou webhook `/webhook/mail-acquereur` 
3. **Matching** : `process_prospect()` → `find_best_match()` 
4. **Stockage** : Insertion dans `biens_cache` (PostgreSQL)
5. **Trello** : `creer_carte_acquereur()` → Carte dans liste TEST ACQUÉREURS
6. **Email** : `send_hook_email()` → Email personnalisé au prospect
7. **Chatbot** : Prospect clique → `/chat/card/{trello_id}` → Conversation IA

---

## 2. LE MOTEUR DE MATCHING (V14 Forteresse)

### 2.1 Table `biens_cache` (PostgreSQL)

```sql
CREATE TABLE biens_cache (
    id SERIAL PRIMARY KEY,
    trello_id VARCHAR(50) UNIQUE NOT NULL,
    trello_url VARCHAR(200),
    proprietaire VARCHAR(200),
    description TEXT,
    refs_trouvees TEXT[],           -- REF ICI Dordogne (ex: ['41437', '33895'])
    prix INTEGER,
    surface INTEGER,
    commune VARCHAR(100),
    commune_normalisee VARCHAR(100), -- Via normaliser_commune()
    mots_cles TEXT[],               -- ['piscine', 'grange', 'vue']
    attachments_names TEXT[],
    site_url VARCHAR(300),          -- URL icidordogne.fr (V14)
    site_prix INTEGER,
    site_surface INTEGER,
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 2.2 Fonction de Matching : `find_best_match(criteres)`

**Fichier:** `matching_engine.py`

**Input:**
```python
criteres = {
    "ref": "41437",           # REF exacte (prioritaire)
    "prix": 250000,           # Budget max
    "surface": 100,           # Surface min
    "commune": "Douville",    # Localisation
    "mots_cles": ["piscine"]  # Critères bonus
}
```

**Output:**
```python
{
    "score": 1000,            # Score total
    "confidence": "HIGH",     # HIGH / MEDIUM / LOW
    "needs_verification": False,
    "bien": { ... },          # Données du bien matché
    "details": ["🎫 GOLDEN TICKET: REF exacte trouvée"]
}
```

### 2.3 Système de Scoring

| Critère | Points | Condition |
|---------|--------|-----------|
| **GOLDEN TICKET** | 1000 | REF exacte trouvée OU prix unique dans le stock |
| Prix exact | 300 | Écart < 5% |
| Prix proche | 200 | Écart < 15% |
| Prix acceptable | 100 | Écart < 30% |
| Surface exacte | 200 | Écart < 10% |
| Surface proche | 100 | Écart < 25% |
| Commune exacte | 300 | Match après normalisation |
| Commune proche | 150 | Même canton/secteur |
| Mot-clé trouvé | 50/mot | "piscine", "grange", "vue"... |

### 2.4 Niveaux de Confiance

```python
if score >= 900:
    confidence = "HIGH"
    needs_verification = False
elif score >= 500:
    confidence = "MEDIUM"  
    needs_verification = True
else:
    confidence = "LOW"
    needs_verification = True
```

### 2.5 Labels Trello Automatiques

| Label | Couleur | Condition |
|-------|---------|-----------|
| `GOLDEN_TICKET_GREEN` | 🟢 Vert | Score ≥ 90% (900+) |
| `MATCH_INCERTAIN_RED` | 🔴 Rouge | Score < 90% |

**Fonction:** `creer_carte_acquereur()` applique automatiquement le label.

### 2.6 Synchronisation des Sources

**Fonction:** `sync_biens_from_trello()`

```python
# Appelé via POST /admin/sync
# 1. Récupère toutes les cartes du board BIENS
# 2. Extrait: REF, prix, surface, commune, mots-clés
# 3. Extrait site_url depuis:
#    - Attachments Trello (si contient icidordogne.fr)
#    - Description (pattern "Lien site : https://...")
# 4. Upsert dans biens_cache
```

**Pattern d'extraction site_url:**
```python
# Méthode 1: Attachments
if 'icidordogne.fr' in att_url:
    site_url = att_url

# Méthode 2: Description
site_match = re.search(
    r'(?:Lien site|Site)\s*:\s*\[?(https?://[^\s\]]+icidordogne\.fr[^\s\]]*)',
    desc, re.IGNORECASE
)
```

---

## 3. LE CHATBOT & ROUTAGE (V14.3)

### 3.1 Route Magique : `/chat/card/{trello_id}`

**Fichier:** `main.py` (ligne ~1780)

**Logique:**
```python
# 1. Chercher dans le cache prospects.json (PRIORITAIRE)
prospects = charger_prospects_sdr()
token = prospects.get(f"card_{card_shortid}")

if token and token in prospects:
    # Prospect trouvé - utiliser ces données
    prospect = prospects[token]
else:
    # Fallback: récupérer depuis Trello API
    # (pour anciennes cartes non cachées)
```

### 3.2 Génération du Template : `generer_page_chat_prospect()`

**Variables injectées dans `chat_prospect.html`:**

| Variable | Description | Exemple |
|----------|-------------|---------|
| `__TOKEN__` | ID unique prospect | `6bd22fb77cc75d2c` |
| `__BIEN_TITRE__` | Titre descriptif | `Maison 112m²` |
| `__BIEN_COMMUNE__` | Localisation | `Douville` |
| `__BIEN_PRIX__` | Prix formaté | `242 000€` |
| `__PRENOM__` | Prénom prospect | `Laurent` |
| `__BIEN_IDENTIFIE__` | Boolean JS | `true` / `false` |
| `__MATCH_SCORE__` | Score numérique | `1000` |
| `__SITE_URL__` | URL icidordogne.fr | `https://www.icidordogne.fr/immobilier/...` |
| `__SITE_HIDDEN__` | Classe CSS | `` (vide) ou `hidden` |

### 3.3 Optimistic UI (Fix écran blanc)

**Problème résolu:** Le fetch asynchrone bloquait l'affichage.

**Solution V14.3:**
```javascript
// ÉTAPE 1: Afficher IMMÉDIATEMENT le message (0.1s)
addMessage('assistant', MSG_ACCUEIL);

// ÉTAPE 2: Charger l'historique en arrière-plan
fetch('/api/prospect-chat/history?token=' + TOKEN)
    .then(data => {
        if (data.messages.length > 0 && hasUserMessage) {
            // Conversation engagée - remplacer par historique
            chat.innerHTML = '';
            messages.forEach(m => addMessage(m.role, m.content));
        }
        // Sinon: garder MSG_ACCUEIL déjà affiché
    });
```

### 3.4 Messages d'Accueil Contextuels

| Condition | Message |
|-----------|---------|
| `BIEN_IDENTIFIE && MATCH_SCORE >= 90` | 🎉 **Golden Ticket** - "Excellente nouvelle : j'ai trouvé le bien..." |
| `BIEN_IDENTIFIE && MATCH_SCORE < 90` | 👋 Match partiel - "J'ai identifié un bien qui pourrait correspondre..." |
| `!BIEN_IDENTIFIE` | 👋 Qualification - "Pour affiner ma recherche, pourriez-vous me préciser..." |

### 3.5 Fix DNS / URL Base

**Problème:** Les liens relatifs cassaient hors Railway.

**Solution:**
```python
BASE_URL = "https://baby-axys-production.up.railway.app"
chat_link = f"{BASE_URL}/chat/card/{card_shortid}"
```

---

## 4. LE HOOK EMAIL (Engagement)

### 4.1 Déclenchement

**Fichier:** `matching_engine.py` → `process_prospect()`

```python
# Après création carte Trello
if result.get("success") and prospect_email:
    send_hook_email(
        to_email=prospect_email,
        prenom=prospect_prenom,
        bien_titre=bien_titre,
        bien_prix=bien_prix,
        chat_link=f"{BASE_URL}/chat/card/{card_shortid}",
        match_score=match_score
    )
```

### 4.2 Templates Email

#### Template SUCCESS (Score ≥ 90)

```
Sujet: 🏠 Bonne nouvelle {prenom} ! Votre bien à {prix} vous attend

Bonjour {prenom},

Excellente nouvelle ! J'ai trouvé un bien qui correspond 
parfaitement à votre recherche :

🏠 {bien_titre}
💰 {bien_prix}

➜ [DÉCOUVRIR LE BIEN] → {chat_link}

Je suis disponible pour organiser une visite.

Axis - ICI Dordogne
```

#### Template DOUTE (Score < 90)

```
Sujet: 🔍 {prenom}, j'ai peut-être trouvé votre bien

Bonjour {prenom},

J'ai identifié un bien qui pourrait vous intéresser.
Pour m'assurer qu'il correspond à vos attentes, 
j'aurais quelques questions.

➜ [DISCUTONS-EN] → {chat_link}

Axis - ICI Dordogne
```

### 4.3 Configuration SMTP

```python
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "u5050786429@gmail.com"  # Compte Axi
SMTP_PASS = "izemquwmmqjdasrk"        # App password
```

---

## 5. FICHIERS CLÉS

| Fichier | Rôle |
|---------|------|
| `main.py` | Serveur HTTP, routes, génération HTML |
| `matching_engine.py` | Logique matching, scoring, Trello API |
| `chat_prospect.html` | Template chatbot (Optimistic UI) |
| `prospects.json` | Cache prospects (Railway Volume) |
| `conversations.json` | Historique chats (Railway Volume) |

---

## 6. ENDPOINTS API

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/match-bien` | Matching complet + création carte |
| POST | `/admin/sync` | Sync Trello → PostgreSQL |
| POST | `/admin/cleanup-test-cards` | Supprimer cartes TEST |
| GET | `/chat/card/{id}` | Chatbot prospect |
| GET | `/api/prospect-chat/history` | Historique conversation |
| POST | `/api/prospect-chat` | Envoyer message / sauvegarder |
| GET | `/debug-card/{id}` | Debug carte Trello |

---

## 7. VARIABLES D'ENVIRONNEMENT

```bash
# PostgreSQL
DATABASE_URL=postgresql://...

# Trello
TRELLO_KEY=5cc8ef3e8f8e4218c99e0e9c73e3c5e1
TRELLO_TOKEN=ATTAff6f81c3b...

# Anthropic (pour IA chat)
ANTHROPIC_API_KEY=sk-ant-...

# IDs Trello
BOARD_BIENS=5a4e22b5a...
LIST_TEST_ACQUEREURS=694f52e6238e9746b814cae9
JULIE_ID=5e5f...
```

---

## 8. RÈGLES D'OR (NE PAS OUBLIER)

1. **Source de vérité = PostgreSQL** (`biens_cache`), pas Trello
2. **Butler Trello écrase les descriptions** → Stocker dans `prospects.json`
3. **Optimistic UI** : Toujours afficher quelque chose IMMÉDIATEMENT
4. **Pas de test d'image asynchrone** : Ça bloque le JS
5. **site_url vient de Trello** (attachments ou description), pas de la carte acquéreur
6. **Sync obligatoire** après modif Trello : `POST /admin/sync`

---

## 9. HISTORIQUE DES VERSIONS

| Version | Date | Changements |
|---------|------|-------------|
| V13.1 | 27/12 | Matching Engine PostgreSQL, scoring hybrid |
| V13.2 | 28/12 | Hook email, liens corrigés |
| V13.3 | 28/12 | Route `/chat/card/{id}` |
| V13.5 | 28/12 | Force update description Trello |
| V14.0 | 28/12 | Extraction site_url depuis description |
| V14.3 | 28/12 | Optimistic UI, fix écran blanc, logo fixe |

---

*Document généré le 28/12/2025 - Session Axis/Ludo/Lumo*
