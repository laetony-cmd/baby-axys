"""
MODULE TRELLO - AXI V19.4
=========================
Synchronisation bidirectionnelle Trello <-> v19_biens
Matching intelligent Biens -> Acquéreurs

Auteur: Axis (Claude)
Date: 7 janvier 2026
Version: 1.0.0
"""

import os
import re
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
import requests

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("trello")

# =============================================================================
# CONFIGURATION
# =============================================================================

TRELLO_KEY = os.getenv("TRELLO_KEY")
TRELLO_TOKEN = os.getenv("TRELLO_TOKEN")
TRELLO_BASE_URL = "https://api.trello.com/1"

# Vérification au démarrage
if not TRELLO_KEY or not TRELLO_TOKEN:
    logger.warning("⚠️ TRELLO_KEY ou TRELLO_TOKEN non configuré - Module Trello désactivé")

# IDs des boards et listes
BOARD_BIENS = "6249623e53c07a131c916e59"
BOARD_ACQUEREURS = "5c51537bea012805e27d5bc6"
LIST_BIENS_EN_LIGNE = "5df28632d1672c6ec13ded52"
LIST_ACQUEREURS_SUIVI = "5c5153b9dc7fe6093018849c"
LIST_ACQUEREURS_VISITES = "5ebd5702f68664068fa17c7e"

# Custom Fields
CF_BUDGET_ACQUEREUR = "5c51542db3fed40679e0ce82"

# Labels
LABEL_OPPORTUNITE = None  # À créer si n'existe pas

# Seuils de matching
BUDGET_TOLERANCE_MIN = 0.85  # Prospect peut payer 85% du prix
BUDGET_TOLERANCE_MAX = 1.10  # Prospect peut payer 110% du prix

# =============================================================================
# 🔇 MODE SILENCIEUX - CONSIGNE LUMO 07/01/2026
# =============================================================================
# NE PAS MODIFIER SANS ACCORD LUDO
# - True = Les commentaires "🔔 MATCH" sont postés sur Trello
# - False = Les matchs sont juste loggés, aucune notification
ENABLE_NOTIFICATIONS = False  # ⚠️ DÉSACTIVÉ - En attente ordre Ludo


# =============================================================================
# RÉFÉRENTIEL SECTEURS (chargé depuis PostgreSQL)
# =============================================================================

SECTEURS_DEFAULT = [
    {"keyword": "triangle d'or", "zip_codes": ["24260", "24510", "24480"]},
    {"keyword": "triangle d or", "zip_codes": ["24260", "24510", "24480"]},
    {"keyword": "vergt", "zip_codes": ["24380", "24330", "24520", "24140"]},
    {"keyword": "le bugue", "zip_codes": ["24260", "24510", "24480", "24150"]},
    {"keyword": "bugue", "zip_codes": ["24260", "24510", "24480", "24150"]},
    {"keyword": "périgord noir", "zip_codes": ["24200", "24220", "24250", "24290"]},
    {"keyword": "perigord noir", "zip_codes": ["24200", "24220", "24250", "24290"]},
    {"keyword": "périgord vert", "zip_codes": ["24310", "24340", "24350"]},
    {"keyword": "perigord vert", "zip_codes": ["24310", "24340", "24350"]},
    {"keyword": "ribérac", "zip_codes": ["24600"]},
    {"keyword": "riberac", "zip_codes": ["24600"]},
    {"keyword": "bergerac", "zip_codes": ["24100"]},
    {"keyword": "sarlat", "zip_codes": ["24200"]},
    {"keyword": "montignac", "zip_codes": ["24290"]},
    {"keyword": "terrasson", "zip_codes": ["24120"]},
    {"keyword": "périgueux", "zip_codes": ["24000", "24650", "24750"]},
    {"keyword": "perigueux", "zip_codes": ["24000", "24650", "24750"]},
    {"keyword": "trémolat", "zip_codes": ["24510"]},
    {"keyword": "tremolat", "zip_codes": ["24510"]},
    {"keyword": "limeuil", "zip_codes": ["24510"]},
    {"keyword": "lalinde", "zip_codes": ["24150"]},
    {"keyword": "st cyprien", "zip_codes": ["24220"]},
    {"keyword": "saint cyprien", "zip_codes": ["24220"]},
]

# Cache du référentiel (chargé au démarrage)
_secteurs_cache: List[Dict] = []


# =============================================================================
# FONCTIONS UTILITAIRES API TRELLO
# =============================================================================

def trello_get(endpoint: str, params: dict = None) -> Optional[dict]:
    """GET request vers l'API Trello"""
    url = f"{TRELLO_BASE_URL}{endpoint}"
    params = params or {}
    params["key"] = TRELLO_KEY
    params["token"] = TRELLO_TOKEN
    
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Trello GET {endpoint} failed: {e}")
        return None


def trello_post(endpoint: str, data: dict = None) -> Optional[dict]:
    """POST request vers l'API Trello"""
    url = f"{TRELLO_BASE_URL}{endpoint}"
    params = {"key": TRELLO_KEY, "token": TRELLO_TOKEN}
    
    try:
        resp = requests.post(url, params=params, data=data, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Trello POST {endpoint} failed: {e}")
        return None


# =============================================================================
# PARSING DES CARTES
# =============================================================================

def extract_ref_sweepbright(card_name: str) -> Optional[str]:
    """Extrait la REF SweepBright du nom de carte (ex: 'POMMIER - 41710 - (maison)')"""
    match = re.search(r'\b(4\d{4})\b', card_name)
    return match.group(1) if match else None


def extract_phone(text: str) -> Optional[str]:
    """Extrait le numéro de téléphone de la description"""
    patterns = [
        r'\*\*Tél\*\*\s*:\s*([0-9\s\+\.]+)',
        r'\*\*Tél\s*:\s*\*\*\s*([0-9\s\+\.]+)',
        r'Tél\s*:\s*([0-9\s\+\.]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            phone = re.sub(r'[^\d\+]', '', match.group(1))
            if len(phone) >= 10:
                return phone
    return None


def extract_email(text: str) -> Optional[str]:
    """Extrait l'email de la description"""
    # Pattern pour emails (y compris dans les liens markdown)
    match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    return match.group(0) if match else None


def extract_chambres(text: str) -> Optional[int]:
    """Extrait le nombre de chambres"""
    match = re.search(r'\*\*Nb de chambres\*\*\s*:\s*(\d+)', text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def extract_chauffage(text: str) -> Optional[str]:
    """Extrait le type de chauffage"""
    match = re.search(r'\*\*Chauffage\*\*\s*:\s*([^\n\*]+)', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def extract_taxe_fonciere(text: str) -> Optional[int]:
    """Extrait la taxe foncière"""
    patterns = [
        r'TF\s*:\s*(\d[\d\s]*)',
        r'taxe fonci[eè]re\s*:\s*(\d[\d\s]*)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            tf = re.sub(r'\s', '', match.group(1))
            if tf.isdigit():
                return int(tf)
    return None


def extract_estimation(text: str) -> Optional[int]:
    """Extrait l'estimation de la description"""
    patterns = [
        r'\*\*Estimation[:\s\*]*(\d[\d\s]*)',
        r'Estimation\s*:\s*(\d[\d\s]*)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            est = re.sub(r'\s', '', match.group(1))
            if est.isdigit():
                return int(est) * 1000 if int(est) < 1000 else int(est)
    return None


def extract_budget_from_text(text: str) -> Optional[int]:
    """
    Extrait le budget d'un texte libre (parsing défensif)
    Patterns supportés: "250000€", "250 000", "250k", "budget 250"
    """
    patterns = [
        # 250000 ou 250 000 suivi de € ou eur
        r'(\d{2,3})\s*(\d{3})\s*[€e]',
        # 250k ou 250 k
        r'(\d{2,3})\s*k',
        # budget/apport suivi d'un nombre
        r'(?:budget|apport|prêt|pret)\s*[:\s]*(\d{2,3})\s*(?:000|k)?',
        # Nombre seul entre 50000 et 2000000
        r'\b(\d{6,7})\b',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            groups = match.groups()
            if len(groups) == 2 and groups[1]:
                # Format "250 000"
                budget = int(groups[0] + groups[1])
            elif len(groups) == 1:
                val = int(groups[0])
                # Si c'est un petit nombre (< 1000), c'est probablement en k€
                if val < 1000:
                    budget = val * 1000
                else:
                    budget = val
            else:
                continue
            
            # Validation: budget réaliste (50k - 2M)
            if 50000 <= budget <= 2000000:
                return budget
    
    return None


def extract_secteur_keywords(text: str) -> List[str]:
    """Extrait les mots-clés de secteur d'un texte"""
    text_lower = text.lower()
    found = []
    
    for secteur in _secteurs_cache or SECTEURS_DEFAULT:
        if secteur["keyword"].lower() in text_lower:
            found.append(secteur["keyword"])
    
    # Aussi chercher les codes postaux directs
    cp_matches = re.findall(r'\b(24\d{3})\b', text)
    found.extend(cp_matches)
    
    return found


def get_zip_codes_for_keywords(keywords: List[str]) -> List[str]:
    """Retourne les codes postaux associés aux mots-clés secteur"""
    zip_codes = set()
    
    for keyword in keywords:
        # Si c'est déjà un code postal
        if re.match(r'^24\d{3}$', keyword):
            zip_codes.add(keyword)
            continue
        
        # Chercher dans le référentiel
        for secteur in _secteurs_cache or SECTEURS_DEFAULT:
            if secteur["keyword"].lower() == keyword.lower():
                zip_codes.update(secteur["zip_codes"])
    
    return list(zip_codes)


# =============================================================================
# FONCTIONS POSTGRESQL
# =============================================================================

def init_secteurs_table(pool) -> bool:
    """Crée la table v19_secteurs si elle n'existe pas et la remplit"""
    try:
        conn = pool.getconn()
        cur = conn.cursor()
        
        # Créer la table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS v19_secteurs (
                id SERIAL PRIMARY KEY,
                keyword VARCHAR(100) UNIQUE NOT NULL,
                zip_codes JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Insérer les données par défaut si table vide
        cur.execute("SELECT COUNT(*) FROM v19_secteurs")
        count = cur.fetchone()[0]
        
        if count == 0:
            logger.info("Initialisation du référentiel secteurs...")
            for secteur in SECTEURS_DEFAULT:
                cur.execute("""
                    INSERT INTO v19_secteurs (keyword, zip_codes)
                    VALUES (%s, %s)
                    ON CONFLICT (keyword) DO NOTHING
                """, (secteur["keyword"], json.dumps(secteur["zip_codes"])))
            logger.info(f"  → {len(SECTEURS_DEFAULT)} secteurs insérés")
        
        conn.commit()
        pool.putconn(conn)
        return True
        
    except Exception as e:
        logger.error(f"Erreur init_secteurs_table: {e}")
        return False


def load_secteurs_from_db(pool) -> List[Dict]:
    """Charge le référentiel secteurs depuis PostgreSQL"""
    global _secteurs_cache
    
    try:
        conn = pool.getconn()
        cur = conn.cursor()
        
        cur.execute("SELECT keyword, zip_codes FROM v19_secteurs")
        rows = cur.fetchall()
        
        _secteurs_cache = [
            {"keyword": row[0], "zip_codes": row[1]}
            for row in rows
        ]
        
        pool.putconn(conn)
        logger.info(f"Référentiel secteurs chargé: {len(_secteurs_cache)} entrées")
        return _secteurs_cache
        
    except Exception as e:
        logger.error(f"Erreur load_secteurs_from_db: {e}")
        _secteurs_cache = SECTEURS_DEFAULT
        return _secteurs_cache


def get_biens_from_db(pool) -> List[Dict]:
    """Récupère tous les biens de v19_biens"""
    try:
        conn = pool.getconn()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, reference, titre, prix, surface_habitable, 
                   ville, code_postal, negociateur,
                   proprietaire_nom, proprietaire_tel, proprietaire_email,
                   trello_card_id
            FROM v19_biens
            WHERE statut != 'vendu'
        """)
        
        columns = [desc[0] for desc in cur.description]
        biens = [dict(zip(columns, row)) for row in cur.fetchall()]
        
        pool.putconn(conn)
        return biens
        
    except Exception as e:
        logger.error(f"Erreur get_biens_from_db: {e}")
        return []


def update_bien_from_trello(pool, reference: str, data: Dict) -> bool:
    """Met à jour un bien avec les données Trello"""
    try:
        conn = pool.getconn()
        cur = conn.cursor()
        
        # Construire la requête dynamiquement
        updates = []
        values = []
        
        field_mapping = {
            "proprietaire_nom": "proprietaire_nom",
            "proprietaire_tel": "proprietaire_tel", 
            "proprietaire_email": "proprietaire_email",
            "nb_chambres": "nb_chambres",
            "chauffage": "chauffage",
            "taxe_fonciere": "taxe_fonciere",
            "estimation_trello": "estimation_trello",
            "trello_card_id": "trello_card_id",
            "trello_card_url": "trello_card_url",
        }
        
        for key, column in field_mapping.items():
            if key in data and data[key] is not None:
                updates.append(f"{column} = %s")
                values.append(data[key])
        
        if not updates:
            pool.putconn(conn)
            return False
        
        updates.append("updated_at = NOW()")
        values.append(reference)
        
        query = f"""
            UPDATE v19_biens 
            SET {', '.join(updates)}
            WHERE reference = %s
        """
        
        cur.execute(query, values)
        affected = cur.rowcount
        conn.commit()
        pool.putconn(conn)
        
        return affected > 0
        
    except Exception as e:
        logger.error(f"Erreur update_bien_from_trello: {e}")
        return False


# =============================================================================
# SYNCHRONISATION TRELLO -> v19_biens
# =============================================================================

def sync_biens_from_trello(pool, dry_run: bool = True) -> Dict:
    """
    Synchronise les infos Trello vers v19_biens
    Enrichit avec: proprio (nom/tel/email), chambres, chauffage, TF
    
    Returns: Stats du sync
    """
    logger.info("=" * 60)
    logger.info("SYNC BIENS FROM TRELLO")
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    logger.info("=" * 60)
    
    stats = {
        "cartes_scannees": 0,
        "refs_trouvees": 0,
        "biens_enrichis": 0,
        "biens_non_trouves_db": 0,
        "details": []
    }
    
    # Récupérer les cartes du board BIENS
    cards = trello_get(f"/boards/{BOARD_BIENS}/cards", {
        "fields": "id,name,desc,url,labels,dateLastActivity"
    })
    
    if not cards:
        logger.error("Impossible de récupérer les cartes Trello")
        return stats
    
    stats["cartes_scannees"] = len(cards)
    logger.info(f"Cartes scannées: {len(cards)}")
    
    for card in cards:
        ref = extract_ref_sweepbright(card["name"])
        if not ref:
            continue
        
        stats["refs_trouvees"] += 1
        
        # Extraire les données de la description
        desc = card.get("desc", "")
        enrichment = {
            "proprietaire_nom": card["name"].split("-")[0].strip() if "-" in card["name"] else None,
            "proprietaire_tel": extract_phone(desc),
            "proprietaire_email": extract_email(desc),
            "nb_chambres": extract_chambres(desc),
            "chauffage": extract_chauffage(desc),
            "taxe_fonciere": extract_taxe_fonciere(desc),
            "estimation_trello": extract_estimation(desc),
            "trello_card_id": card["id"],
            "trello_card_url": card["url"],
        }
        
        # Filtrer les valeurs None
        enrichment = {k: v for k, v in enrichment.items() if v is not None}
        
        if len(enrichment) <= 2:  # Juste card_id et url
            continue
        
        detail = {
            "ref": ref,
            "proprio": enrichment.get("proprietaire_nom"),
            "tel": enrichment.get("proprietaire_tel"),
            "email": enrichment.get("proprietaire_email"),
            "chambres": enrichment.get("nb_chambres"),
            "tf": enrichment.get("taxe_fonciere"),
        }
        
        if dry_run:
            logger.info(f"  [DRY] REF {ref}: {detail}")
            stats["details"].append(detail)
            stats["biens_enrichis"] += 1
        else:
            if update_bien_from_trello(pool, ref, enrichment):
                logger.info(f"  [OK] REF {ref} enrichi")
                stats["biens_enrichis"] += 1
                stats["details"].append(detail)
            else:
                logger.warning(f"  [!] REF {ref} non trouvé en base")
                stats["biens_non_trouves_db"] += 1
    
    logger.info("-" * 60)
    logger.info(f"RÉSULTAT SYNC:")
    logger.info(f"  Cartes scannées: {stats['cartes_scannees']}")
    logger.info(f"  REFs trouvées: {stats['refs_trouvees']}")
    logger.info(f"  Biens enrichis: {stats['biens_enrichis']}")
    logger.info(f"  Non trouvés DB: {stats['biens_non_trouves_db']}")
    
    return stats


# =============================================================================
# MATCHING BIENS -> ACQUÉREURS
# =============================================================================

def get_all_prospects() -> List[Dict]:
    """Récupère tous les prospects avec leurs critères"""
    prospects = []
    
    # Listes à scanner
    lists_to_scan = [
        LIST_ACQUEREURS_SUIVI,
        LIST_ACQUEREURS_VISITES,
    ]
    
    for list_id in lists_to_scan:
        cards = trello_get(f"/lists/{list_id}/cards", {
            "fields": "id,name,desc,url,labels,dateLastActivity",
            "customFieldItems": "true"
        })
        
        if not cards:
            continue
        
        for card in cards:
            prospect = {
                "id": card["id"],
                "name": card["name"],
                "url": card["url"],
                "budget": None,
                "secteurs": [],
                "refs_citees": [],
                "last_activity": card.get("dateLastActivity"),
            }
            
            # 1. Budget depuis Custom Field
            for cf in card.get("customFieldItems", []):
                if cf.get("idCustomField") == CF_BUDGET_ACQUEREUR:
                    val = cf.get("value", {}).get("number")
                    if val:
                        prospect["budget"] = int(float(val))
            
            # 2. Si pas de budget CF, parser la description
            desc = card.get("desc", "")
            if not prospect["budget"]:
                prospect["budget"] = extract_budget_from_text(desc)
            
            # 3. Extraire secteurs
            prospect["secteurs"] = extract_secteur_keywords(desc)
            
            # 4. Extraire REFs citées (biens déjà vus)
            refs = re.findall(r'\b(4\d{4})\b', desc)
            prospect["refs_citees"] = list(set(refs))
            
            prospects.append(prospect)
    
    return prospects


def find_matches(biens: List[Dict], prospects: List[Dict]) -> List[Dict]:
    """
    Trouve les matchs Biens -> Prospects
    
    Règles:
    - MATCH FORT: Budget compatible ET (REF citée OU secteur match)
    - MATCH FAIBLE: Budget compatible seulement
    """
    matches = []
    
    for bien in biens:
        prix = bien.get("prix")
        if not prix:
            continue
        
        cp_bien = bien.get("code_postal", "")
        ref_bien = bien.get("reference", "")
        
        for prospect in prospects:
            budget = prospect.get("budget")
            if not budget:
                continue
            
            # Check budget dans la fourchette
            if not (prix * BUDGET_TOLERANCE_MIN <= budget <= prix * BUDGET_TOLERANCE_MAX):
                continue
            
            # Calculer le score de match
            score = 0
            reasons = []
            
            # +50 si REF déjà citée par le prospect
            if ref_bien in prospect.get("refs_citees", []):
                score += 50
                reasons.append(f"REF {ref_bien} déjà citée")
            
            # +30 si secteur match
            prospect_zips = get_zip_codes_for_keywords(prospect.get("secteurs", []))
            if cp_bien and cp_bien in prospect_zips:
                score += 30
                reasons.append(f"Secteur {cp_bien} match")
            
            # +20 pour budget compatible
            score += 20
            reasons.append(f"Budget {budget:,}€ vs Prix {prix:,}€")
            
            match_type = "FORT" if score >= 50 else "FAIBLE"
            
            matches.append({
                "bien_ref": ref_bien,
                "bien_titre": bien.get("titre", ""),
                "bien_prix": prix,
                "bien_ville": bien.get("ville", ""),
                "prospect_name": prospect["name"],
                "prospect_id": prospect["id"],
                "prospect_url": prospect["url"],
                "prospect_budget": budget,
                "score": score,
                "type": match_type,
                "reasons": reasons,
            })
    
    # Trier par score décroissant
    matches.sort(key=lambda x: x["score"], reverse=True)
    
    return matches


def run_matching_dry_run(pool) -> Dict:
    """
    Lance le matching en mode Dry Run (lecture seule)
    
    Returns: Stats et liste des matchs
    """
    logger.info("=" * 60)
    logger.info("MATCHING BIENS -> ACQUÉREURS (DRY RUN)")
    logger.info("=" * 60)
    
    # Charger le référentiel secteurs
    load_secteurs_from_db(pool)
    
    # Récupérer les biens
    biens = get_biens_from_db(pool)
    logger.info(f"Biens en base: {len(biens)}")
    
    # Récupérer les prospects
    prospects = get_all_prospects()
    logger.info(f"Prospects Trello: {len(prospects)}")
    
    # Prospects avec budget
    prospects_with_budget = [p for p in prospects if p.get("budget")]
    logger.info(f"Prospects avec budget: {len(prospects_with_budget)}")
    
    # Lancer le matching
    matches = find_matches(biens, prospects)
    
    # Séparer forts et faibles
    matches_forts = [m for m in matches if m["type"] == "FORT"]
    matches_faibles = [m for m in matches if m["type"] == "FAIBLE"]
    
    logger.info("-" * 60)
    logger.info(f"RÉSULTAT MATCHING:")
    logger.info(f"  Matchs FORTS: {len(matches_forts)}")
    logger.info(f"  Matchs FAIBLES: {len(matches_faibles)}")
    
    if matches_forts:
        logger.info("\n🔔 MATCHS FORTS:")
        for m in matches_forts[:10]:  # Top 10
            logger.info(f"  • {m['bien_ref']} ({m['bien_ville']}) {m['bien_prix']:,}€")
            logger.info(f"    → {m['prospect_name']} (budget {m['prospect_budget']:,}€)")
            logger.info(f"    → Raisons: {', '.join(m['reasons'])}")
    
    return {
        "biens_count": len(biens),
        "prospects_count": len(prospects),
        "prospects_with_budget": len(prospects_with_budget),
        "matches_forts": len(matches_forts),
        "matches_faibles": len(matches_faibles),
        "top_matches": matches_forts[:20],
        "all_matches": matches,
    }


# =============================================================================
# NOTIFICATION (pour usage futur, pas en dry run)
# =============================================================================

def notify_match_on_card(prospect_card_id: str, bien: Dict) -> bool:
    """
    Poste un commentaire sur la carte prospect pour notifier un match
    
    ⚠️ Contrôlé par ENABLE_NOTIFICATIONS
    """
    # 🔇 MODE SILENCIEUX - Vérification du flag
    if not ENABLE_NOTIFICATIONS:
        logger.info(f"[SILENCIEUX] Match ignoré (notif désactivée): {bien.get('reference')} → {prospect_card_id}")
        return False
    
    comment = f"""🔔 **NOUVEAU BIEN CORRESPONDANT**

**{bien.get('titre', 'Bien')}**
- Prix: {bien.get('prix', 0):,}€
- Ville: {bien.get('ville', '')}
- Surface: {bien.get('surface_habitable', '')}m²
- REF: {bien.get('reference', '')}

👉 [Voir sur SweepBright]({bien.get('lien_sweepbright', '#')})

_Notification automatique Axi_
"""
    
    result = trello_post(f"/cards/{prospect_card_id}/actions/comments", {
        "text": comment
    })
    
    return result is not None


# =============================================================================
# POINT D'ENTRÉE PRINCIPAL
# =============================================================================

def run_full_analysis(pool) -> Dict:
    """
    Lance l'analyse complète en Dry Run:
    1. Sync des biens depuis Trello
    2. Matching Biens -> Acquéreurs
    
    Returns: Rapport complet
    """
    logger.info("\n" + "=" * 70)
    logger.info("   AXI V19.4 - TRELLO ANALYSIS - DRY RUN")
    logger.info("   " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("=" * 70 + "\n")
    
    # Initialiser la table secteurs
    init_secteurs_table(pool)
    
    # 1. Sync biens
    sync_stats = sync_biens_from_trello(pool, dry_run=True)
    
    print("\n")
    
    # 2. Matching
    match_stats = run_matching_dry_run(pool)
    
    # Rapport final
    report = {
        "timestamp": datetime.now().isoformat(),
        "mode": "DRY_RUN",
        "sync": sync_stats,
        "matching": match_stats,
    }
    
    logger.info("\n" + "=" * 70)
    logger.info("   RAPPORT FINAL")
    logger.info("=" * 70)
    logger.info(f"   Biens enrichissables: {sync_stats['biens_enrichis']}")
    logger.info(f"   Matchs FORTS détectés: {match_stats['matches_forts']}")
    logger.info(f"   Matchs FAIBLES détectés: {match_stats['matches_faibles']}")
    logger.info("=" * 70 + "\n")
    
    return report


# =============================================================================
# ENDPOINTS HTTP - REGISTRATION DES ROUTES
# =============================================================================

def register_routes(app, pool):
    """
    Enregistre les routes Trello dans l'application Flask/Bottle
    
    Routes:
    - GET /trello/status - Status du module
    - GET /trello/sync - Lance la synchronisation (dry_run par défaut)
    - POST /trello/sync - Lance la synchronisation LIVE
    - GET /trello/match - Lance le matching (dry_run)
    - GET /trello/secteurs - Liste le référentiel secteurs
    """
    from bottle import request, response
    import json as json_lib
    
    logger.info("📋 Registering Trello routes...")
    
    @app.get('/trello/status')
    def trello_status():
        """Status du module Trello"""
        response.content_type = 'application/json'
        return json_lib.dumps({
            "module": "trello",
            "version": "1.0.0",
            "notifications_enabled": ENABLE_NOTIFICATIONS,
            "trello_configured": bool(TRELLO_KEY and TRELLO_TOKEN),
            "secteurs_loaded": len(_secteurs_cache),
        })
    
    @app.get('/trello/sync')
    def trello_sync_dry():
        """Synchronisation Trello -> v19_biens (DRY RUN)"""
        response.content_type = 'application/json'
        try:
            # Initialiser la table secteurs si nécessaire
            init_secteurs_table(pool)
            load_secteurs_from_db(pool)
            
            # Lancer le sync en dry run
            stats = sync_biens_from_trello(pool, dry_run=True)
            return json_lib.dumps({
                "status": "ok",
                "mode": "dry_run",
                "stats": stats
            })
        except Exception as e:
            logger.error(f"Erreur sync dry: {e}")
            response.status = 500
            return json_lib.dumps({"error": str(e)})
    
    @app.post('/trello/sync')
    def trello_sync_live():
        """Synchronisation Trello -> v19_biens (LIVE)"""
        response.content_type = 'application/json'
        try:
            # Initialiser la table secteurs si nécessaire
            init_secteurs_table(pool)
            load_secteurs_from_db(pool)
            
            # Lancer le sync en LIVE
            stats = sync_biens_from_trello(pool, dry_run=False)
            return json_lib.dumps({
                "status": "ok",
                "mode": "live",
                "stats": stats
            })
        except Exception as e:
            logger.error(f"Erreur sync live: {e}")
            response.status = 500
            return json_lib.dumps({"error": str(e)})
    
    @app.get('/trello/match')
    def trello_match():
        """Matching Biens -> Prospects (DRY RUN)"""
        response.content_type = 'application/json'
        try:
            # Initialiser et charger les secteurs
            init_secteurs_table(pool)
            load_secteurs_from_db(pool)
            
            # Lancer le matching
            result = run_matching_dry_run(pool)
            return json_lib.dumps({
                "status": "ok",
                "mode": "dry_run (notifications désactivées)",
                "biens_count": result.get("biens_count", 0),
                "prospects_count": result.get("prospects_count", 0),
                "matches_forts": result.get("matches_forts", 0),
                "matches_faibles": result.get("matches_faibles", 0),
                "top_matches": result.get("top_matches", [])[:10]
            })
        except Exception as e:
            logger.error(f"Erreur matching: {e}")
            response.status = 500
            return json_lib.dumps({"error": str(e)})
    
    @app.get('/trello/secteurs')
    def trello_secteurs():
        """Liste le référentiel secteurs"""
        response.content_type = 'application/json'
        try:
            load_secteurs_from_db(pool)
            return json_lib.dumps({
                "status": "ok",
                "count": len(_secteurs_cache),
                "secteurs": _secteurs_cache
            })
        except Exception as e:
            response.status = 500
            return json_lib.dumps({"error": str(e)})
    
    logger.info("✅ Trello routes registered: /trello/status, /trello/sync, /trello/match, /trello/secteurs")


# =============================================================================
# TEST STANDALONE
# =============================================================================

if __name__ == "__main__":
    """Test du module sans base de données (scan Trello uniquement)"""
    
    print("=" * 60)
    print("TEST MODULE TRELLO (standalone)")
    print("=" * 60)
    
    # Test récupération cartes BIENS
    print("\n1. Scan des cartes BIENS...")
    cards = trello_get(f"/boards/{BOARD_BIENS}/cards", {"fields": "id,name,desc"})
    if cards:
        print(f"   → {len(cards)} cartes trouvées")
        
        refs_found = 0
        proprios_found = 0
        
        for card in cards[:50]:  # Limite à 50 pour le test
            ref = extract_ref_sweepbright(card["name"])
            if ref:
                refs_found += 1
                desc = card.get("desc", "")
                tel = extract_phone(desc)
                email = extract_email(desc)
                if tel or email:
                    proprios_found += 1
        
        print(f"   → REFs SweepBright: {refs_found}")
        print(f"   → Proprios avec contact: {proprios_found}")
    
    # Test récupération prospects
    print("\n2. Scan des prospects ACQUÉREURS...")
    prospects = get_all_prospects()
    print(f"   → {len(prospects)} prospects trouvés")
    
    with_budget = [p for p in prospects if p.get("budget")]
    print(f"   → Avec budget: {len(with_budget)}")
    
    with_secteur = [p for p in prospects if p.get("secteurs")]
    print(f"   → Avec secteur: {len(with_secteur)}")
    
    # Afficher quelques exemples
    print("\n3. Exemples de prospects avec budget:")
    for p in with_budget[:5]:
        print(f"   • {p['name']}: {p['budget']:,}€")
        if p.get("secteurs"):
            print(f"     Secteurs: {', '.join(p['secteurs'])}")
    
    print("\n" + "=" * 60)
    print("TEST TERMINÉ")
    print("=" * 60)
