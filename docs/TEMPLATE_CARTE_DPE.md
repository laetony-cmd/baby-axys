# 🏠 TEMPLATE CARTE DPE - ICI DORDOGNE

**Carte modèle validée:** https://trello.com/c/bQXgtaMR  
**Date validation:** 12 janvier 2026  
**Version:** 1.0

---

## 📋 FORMAT DE LA DESCRIPTION

```markdown
🔥 **PASSOIRE ÉNERGÉTIQUE {DPE}/{GES}** {ALERTE_CHAUFFAGE}

📍 **Adresse** : {adresse}
📮 **Code postal** : {code_postal} {commune}

🏠 **Caractéristiques du bien** :
- Surface : **{surface} m²**
- Type : {type_batiment}
- Niveaux : {nb_niveaux}
- Période : {periode_construction} {EMOJI_PERIODE}
- Année : {annee_construction}

⚡ **Performance énergétique** :
- DPE : **{dpe_lettre}** ({dpe_valeur} kWh/m²/an)
- GES : **{ges_lettre}** ({ges_valeur} kg CO₂/m²/an)
- Chauffage : {type_chauffage}
- Confort été : {confort_ete}

💸 **Coûts annuels énergie** :
- Chauffage : **{cout_chauffage} €**
- Eau chaude : **{cout_ecs} €**
- **TOTAL : {cout_total} €/an**

📍 [Voir sur Google Maps]({lien_maps})
🛣️ [Voir Street View]({lien_streetview})

💰 **Historique DVF** :
- Dernière vente : {dvf_date}
- Prix d'achat : {dvf_prix}
- Nb mutations : {dvf_nb_mutations}

🎯 **Probabilité** : **{probable_vente_location}**
⚡ **Priorité** : **{priorite}** ({priorite_raisons})

---
📅 Visite diagnostiqueur : {date_visite}
📅 DPE reçu le : {date_reception}
🔢 N° DPE : {numero_dpe}
🤖 *Source : Veille DPE ADEME - Axis*
```

---

## 🚨 ALERTES CHAUFFAGE

| Type énergie | Alerte | Signification |
|--------------|--------|---------------|
| Fioul / Fuel | 🔴 FIOUL - Très motivé! | Interdiction location F/G, propriétaire très motivé |
| Électricité | 🟠 Électrique | Factures élevées, motivation moyenne |
| Gaz | 🟡 Gaz | Stable, moins de pression |
| Autre | (rien) | Pas d'alerte particulière |

---

## 🏛️ INTERPRÉTATION PÉRIODE CONSTRUCTION

| Période | Emoji | Signification |
|---------|-------|---------------|
| Avant 1948 | 🏛️ Charme/Ancien | Pierre, caractère, potentiel rénovation |
| 1949-1974 | ⚠️ Travaux probables | Amiante possible, isolation faible |
| 1975-1988 | ⚠️ Travaux probables | Réglementations faibles |
| Après 1989 | (rien) | Normes plus récentes |

---

## 🎯 SCORING PRIORITÉ

### P1 🔥 (Cible prioritaire)
- DPE F ou G
- + Chauffage fioul
- + Isolation insuffisante
- **Action:** Contact immédiat

### P2 ⚡ (Opportunité)
- DPE E, F ou G
- + Un facteur aggravant (chauffage électrique OU isolation insuffisante)
- **Action:** Contact sous 7 jours

### P3 💤 (Veille)
- DPE A à D
- Pas de facteur aggravant
- **Action:** Suivi passif

---

## 📊 CHAMPS OBLIGATOIRES

| Champ | Source | Obligatoire |
|-------|--------|-------------|
| numero_dpe | ADEME | ✅ |
| date_reception_dpe | ADEME | ✅ |
| date_visite_diagnostiqueur | ADEME | ✅ |
| adresse_brut / adresse_ban | ADEME | ✅ |
| code_postal_ban | ADEME | ✅ |
| nom_commune_ban | ADEME | ✅ |
| surface_habitable_logement | ADEME | ✅ |
| type_batiment | ADEME | ✅ |
| nombre_niveau_logement | ADEME | ⚠️ |
| periode_construction | ADEME | ⚠️ |
| etiquette_dpe | ADEME | ✅ |
| conso_5_usages_par_m2_ep | ADEME | ✅ |
| etiquette_ges | ADEME | ✅ |
| emission_ges_5_usages_par_m2 | ADEME | ✅ |
| type_energie_principale_chauffage | ADEME | ✅ |
| cout_chauffage | ADEME | ⚠️ |
| cout_ecs | ADEME | ⚠️ |
| cout_total_5_usages | ADEME | ✅ |
| indicateur_confort_ete | ADEME | ⚠️ |
| _geopoint | ADEME | ⚠️ |
| DVF (date, prix, mutations) | API DVF | ⚠️ |

---

## 🔧 CONFIGURATION TECHNIQUE

```python
# Liste Trello cible
TRELLO_LIST_DPE = "696479aba93c15e0703ae957"  # 🏠 Veille DPE ADEME

# Classes DPE surveillées
ETIQUETTES_DPE = ["A", "B", "C", "D", "E", "F", "G"]

# Date début collecte
DATE_DEBUT_COLLECTE = "2025-12-01"

# Codes postaux (12)
CODES_POSTAUX = {
    "Le Bugue": ["24510", "24150", "24480", "24260", "24620", "24220"],
    "Vergt": ["24330", "24110", "24520", "24140", "24380", "24750"]
}

# Cron Railway
# 01:00 Paris (00:00 UTC) → /veille/dpe/enrichie
```

---

## ⚠️ RÈGLES IMMUABLES

1. **JAMAIS de suppression** de DPE vus sans accord Ludo
2. **JAMAIS de modification** du format de carte sans validation
3. **Liste Trello dédiée** = pas de Butler/template qui écrase
4. **Délai 2 secondes** après création pour écraser le template si besoin

---

*Document créé le 12 janvier 2026 - ICI Dordogne*
