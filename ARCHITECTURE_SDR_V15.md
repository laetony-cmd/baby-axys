# ARCHITECTURE SDR V15.3 - VERSION DÉFINITIVE

**Date:** 29/12/2025
**Commit:** 435bf5a

---

## 🎯 RÈGLES DÉFINITIVES CRÉATION CARTE ACQUÉREUR

| Règle | Valeur | Code |
|-------|--------|------|
| **Titre** | `NOM Prénom` | `nom.upper() + " " + prenom.capitalize()` |
| **Assignation** | Julie DUPERIER | `JULIE_MEMBER_ID = "59db340040eb2c01fb7d4851"` |
| **Échéance** | Aujourd'hui 18h (ou J+1 si >18h) | `due_date.replace(hour=18)` |
| **Liste** | TEST ACQUÉREURS (Pros LUDO) | `TRELLO_LIST_TEST_ACQUEREURS` |

---

## 📋 FORMAT DESCRIPTION (Compatible Butler)

```
**Tél :** [tel]
**Email :** [email]

**Source du contact :** [source]
**Adresse du bien :** [commune] - [titre] - [prix]€

**Moyen de visite :** 
**Moyen de compte-rendu :** 

**Nb de chambres :** 
**Chauffage :** 
**Voisinage :** 
**Travaux éventuels :** 

**Estimation :** :

**Informations complémentaires :**
💬 Message: "[message]"
🏠 REF: [ref]
👤 Proprio: [proprio]
📋 Trello BIENS: [url_trello]
🌐 Site: [url_site]

---

**Liens** :

- Localisation
- Sweepbright
- Site internet
- Visite virtuelle
```

---

## 🔧 CONTOURNEMENT BUTLER (FORTERESSE)

Butler écrase la description à la création avec son template vide.
**Solution V15.3:**
1. Créer la carte avec description complète
2. Attendre 1.5 secondes (Butler finit)
3. PUT description avec le même format mais valeurs renseignées

```python
time.sleep(1.5)  # Attendre que Butler finisse
update_url = f"https://api.trello.com/1/cards/{card_id}?..."
update_data = urllib.parse.urlencode({"desc": desc}).encode()
```

---

## ✅ ÉLÉMENTS AUTOMATIQUES À LA CRÉATION

1. **Titre:** NOM Prénom
2. **Description:** Format Butler avec coordonnées + bien identifié
3. **Assignation:** Julie
4. **Échéance:** 18h J+0 (ou J+1)
5. **Checklists:** "Avant la visite" + "Après la visite"
6. **Attachments:** Trello BIENS + Site icidordogne.fr

---

## 🔗 MATCHING V15 (BLINDÉ)

**Algorithme:**
1. Prix EXACT (0€ tolérance) sur site icidordogne.fr
2. Surface (±5m²) pour départager
3. Ville pour départager
4. Recherche Trello: REF dans titre → URL dans desc → Global

**Endpoints:**
- `GET /sync-site` - Synchronise cache site
- `GET /match-test?prix=X&surface=Y` - Test matching

---

## 📊 CONSTANTES

```python
TRELLO_LIST_TEST_ACQUEREURS = "694f52e6238e9746b814cae9"
JULIE_MEMBER_ID = "59db340040eb2c01fb7d4851"
TRELLO_BOARD_BIENS = "6249623e53c07a131c916e59"
TRELLO_BOARD_VENTES = "57b2d3e7d3cc8d150eeebddf"
```

---

## 🚀 DÉPLOIEMENT

- **GitHub:** laetony-cmd/baby-axys
- **Railway:** baby-axys-production.up.railway.app
- **Custom:** axi.symbine.fr

---

*Version validée par Ludo - 29/12/2025*
