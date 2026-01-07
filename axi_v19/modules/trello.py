"""
MODULE TRELLO - AXI V19.5
=========================
Synchronisation bidirectionnelle Trello <-> v19_biens
Matching intelligent Biens -> Acquéreurs

Auteur: Axis (Claude)
Date: 7 janvier 2026
Version: 2.0.0 (Fix: aucune exécution à l'import)

RÈGLE D'OR: Ce module ne doit RIEN exécuter lors de l'import.
Tout le code actif est encapsulé dans des fonctions.
"""

import os
import re
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

# =============================================================================
# CONFIGURATION (constantes uniquement - pas d'exécution)
# =============================================================================

# Logger configuré mais pas utilisé à l'import
logger = logging.getLogger("trello")

# Variables d'environnement (lues mais pas validées à l'import)
TRELLO_KEY = os.getenv("TRELLO_KEY")
TRELLO_TOKEN = os.getenv("TRELLO_TOKEN")
TRELLO_BASE_URL = "https://api.trello.com/1"

# IDs des boards et listes
BOARD_BIENS = "6249623e53c07a131c916e59"
BOARD_ACQUEREURS = "5c51537bea012805e27d5bc6"
LIST_BIENS_EN_LIGNE = "5df28632d1672c6ec13ded52"
LIST_BIENS_MANDATS_SIGNES = "624963ce8956e060a5187b6d"
LIST_ACQUEREURS_SUIVI = "5c5153b9dc7fe6093018849c"
LIST_ACQUEREURS_VISITES = "5ebd5702f68664068fa17c7e"

# Custom Fields
CF_BUDGET_ACQUEREUR = "5c51542db3fed40679e0ce82"

# Seuils de matching
BUDGET_TOLERANCE_MIN = 0.85
BUDGET_TOLERANCE_MAX = 1.10

# =============================================================================
# 🔇 MODE SILENCIEUX - CONSIGNE LUMO 07/01/2026
# =============================================================================
ENABLE_NOTIFICATIONS = False  # NE PAS MODIFIER SANS ACCORD LUDO

# =============================================================================
# RÉFÉRENTIEL SECTEURS (données statiques)
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

# Cache du référentiel (initialisé vide, rempli à la demande)
_secteurs_cache: List[Dict] = []


# =============================================================================
# FONCTIONS UTILITAIRES API TRELLO
# =============================================================================

def _check_credentials() -> bool:
    """Vérifie que les credentials Trello sont configurés."""
    if not TRELLO_KEY or not TRELLO_TOKEN:
        logger.warning("⚠️ TRELLO_KEY ou TRELLO_TOKEN non configuré")
        return False
    return True


def trello_get(endpoint: str, params: dict = None) -> Optional[dict]:
    """GET request vers l'API Trello."""
    if not _check_credentials():
        return None
    
    # Import lazy de requests
    import requests
    
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
    """POST request vers l'API Trello."""
    if not _check_credentials():
        return None
    
    import requests
    
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
    """Extrait la REF SweepBright du nom de carte (ex: 'POMMIER - 41710')."""
    match = re.search(r'\b(4\d{4})\b', card_name)
    return match.group(1) if match else None


def extract_phone(text: str) -> Optional[str]:
    """Extrait le numéro de téléphone de la description."""
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
    """Extrait l'email de la description."""
    match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    return match.group(0) if match else None


def extract_chambres(text: str) -> Optional[int]:
    """Extrait le nombre de chambres."""
    match = re.search(r'\*\*Nb de chambres\*\*\s*:\s*(\d+)', text, re.IGNORECASE)
    return int(match.group(1)) if match else None


def extract_chauffage(text: str) -> Optional[str]:
    """Extrait le type de chauffage."""
    match = re.search(r'\*\*Chauffage\*\*\s*:\s*([^\n\*]+)', text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def extract_taxe_fonciere(text: str) -> Optional[int]:
    """Extrait la taxe foncière."""
    patterns = [r'TF\s*:\s*(\d[\d\s]*)', r'taxe fonci[eè]re\s*:\s*(\d[\d\s]*)']
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            tf = re.sub(r'\s', '', match.group(1))
            if tf.isdigit():
                return int(tf)
    return None


def extract_budget_from_text(text: str) -> Optional[int]:
    """Extrait le budget d'un texte libre (parsing défensif)."""
    patterns = [
        r'(\d{2,3})\s*(\d{3})\s*[€e]',
        r'(\d{2,3})\s*k',
        r'(?:budget|apport|prêt|pret)\s*[:\s]*(\d{2,3})\s*(?:000|k)?',
        r'\b(\d{6,7})\b',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            groups = match.groups()
            if len(groups) == 2 and groups[1]:
                budget = int(groups[0] + groups[1])
            elif len(groups) == 1:
                val = int(groups[0])
                budget = val * 1000 if val < 1000 else val
            else:
                continue
            
            if 50000 <= budget <= 2000000:
                return budget
    return None


def extract_secteur_keywords(text: str) -> List[str]:
    """Extrait les mots-clés de secteur d'un texte."""
    global _secteurs_cache
    text_lower = text.lower()
    found = []
    
    secteurs = _secteurs_cache if _secteurs_cache else SECTEURS_DEFAULT
    for secteur in secteurs:
        if secteur["keyword"].lower() in text_lower:
            found.append(secteur["keyword"])
    
    # Codes postaux directs
    cp_matches = re.findall(r'\b(24\d{3})\b', text)
    found.extend(cp_matches)
    
    return found


def get_zip_codes_for_keywords(keywords: List[str]) -> List[str]:
    """Retourne les codes postaux associés aux mots-clés secteur."""
    global _secteurs_cache
    zip_codes = set()
    
    secteurs = _secteurs_cache if _secteurs_cache else SECTEURS_DEFAULT
    
    for keyword in keywords:
        if re.match(r'^24\d{3}$', keyword):
            zip_codes.add(keyword)
            continue
        
        for secteur in secteurs:
            if secteur["keyword"].lower() == keyword.lower():
                zip_codes.update(secteur.get("zip_codes", []))
    
    return list(zip_codes)


# =============================================================================
# FONCTIONS POSTGRESQL
# =============================================================================

def init_secteurs_table(pool) -> bool:
    """Crée la table v19_secteurs si elle n'existe pas et la remplit."""
    try:
        conn = pool.getconn()
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS v19_secteurs (
                id SERIAL PRIMARY KEY,
                keyword VARCHAR(100) UNIQUE NOT NULL,
                zip_codes JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
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
    """Charge le référentiel secteurs depuis PostgreSQL."""
    global _secteurs_cache
    
    try:
        conn = pool.getconn()
        cur = conn.cursor()
        
        cur.execute("SELECT keyword, zip_codes FROM v19_secteurs")
        rows = cur.fetchall()
        
        _secteurs_cache = [{"keyword": row[0], "zip_codes": row[1]} for row in rows]
        
        pool.putconn(conn)
        logger.info(f"Référentiel secteurs chargé: {len(_secteurs_cache)} entrées")
        return _secteurs_cache
        
    except Exception as e:
        logger.error(f"Erreur load_secteurs_from_db: {e}")
        _secteurs_cache = SECTEURS_DEFAULT
        return _secteurs_cache


def get_biens_from_db(pool) -> List[Dict]:
    """Récupère tous les biens de v19_biens."""
    try:
        conn = pool.getconn()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, reference, titre, prix, surface_habitable, 
                   ville, code_postal, negociateur,
                   proprietaire_nom, proprietaire_tel, proprietaire_email,
                   trello_card_id
            FROM v19_biens
            WHERE statut IS NULL OR statut != 'vendu'
        """)
        
        columns = [desc[0] for desc in cur.description]
        biens = [dict(zip(columns, row)) for row in cur.fetchall()]
        
        pool.putconn(conn)
        return biens
        
    except Exception as e:
        logger.error(f"Erreur get_biens_from_db: {e}")
        return []


def update_bien_from_trello(pool, reference: str, data: Dict) -> bool:
    """Met à jour un bien avec les données Trello."""
    try:
        conn = pool.getconn()
        cur = conn.cursor()
        
        updates = []
        values = []
        
        field_mapping = {
            "proprietaire_nom": "proprietaire_nom",
            "proprietaire_tel": "proprietaire_tel",
            "proprietaire_email": "proprietaire_email",
            "nb_chambres": "nb_chambres",
            "chauffage": "chauffage",
            "taxe_fonciere": "taxe_fonciere",
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
        
        query = f"UPDATE v19_biens SET {', '.join(updates)} WHERE reference = %s"
        
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
    Synchronise les infos Trello vers v19_biens.
    Enrichit avec: proprio (nom/tel/email), chambres, chauffage, TF.
    """
    logger.info("=" * 60)
    logger.info(f"SYNC BIENS FROM TRELLO - Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    logger.info("=" * 60)
    
    stats = {
        "cartes_scannees": 0,
        "refs_trouvees": 0,
        "biens_enrichis": 0,
        "biens_non_trouves_db": 0,
        "details": []
    }
    
    # Récupérer les cartes des listes actives
    all_cards = []
    for list_id in [LIST_BIENS_EN_LIGNE, LIST_BIENS_MANDATS_SIGNES]:
        cards = trello_get(f"/lists/{list_id}/cards", {"fields": "id,name,desc,url"})
        if cards:
            all_cards.extend(cards)
    
    if not all_cards:
        logger.error("Impossible de récupérer les cartes Trello")
        return stats
    
    stats["cartes_scannees"] = len(all_cards)
    logger.info(f"Cartes scannées: {len(all_cards)}")
    
    for card in all_cards:
        ref = extract_ref_sweepbright(card["name"])
        if not ref:
            continue
        
        stats["refs_trouvees"] += 1
        
        desc = card.get("desc", "")
        enrichment = {
            "proprietaire_nom": card["name"].split("-")[0].strip() if "-" in card["name"] else None,
            "proprietaire_tel": extract_phone(desc),
            "proprietaire_email": extract_email(desc),
            "nb_chambres": extract_chambres(desc),
            "chauffage": extract_chauffage(desc),
            "taxe_fonciere": extract_taxe_fonciere(desc),
            "trello_card_id": card["id"],
            "trello_card_url": card["url"],
        }
        
        enrichment = {k: v for k, v in enrichment.items() if v is not None}
        
        if len(enrichment) <= 2:
            continue
        
        detail = {
            "ref": ref,
            "proprio": enrichment.get("proprietaire_nom"),
            "tel": enrichment.get("proprietaire_tel"),
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
    
    logger.info(f"RÉSULTAT: {stats['biens_enrichis']} enrichis / {stats['refs_trouvees']} REFs")
    return stats


# =============================================================================
# MATCHING BIENS -> ACQUÉREURS
# =============================================================================

def get_all_prospects() -> List[Dict]:
    """Récupère tous les prospects avec leurs critères."""
    prospects = []
    
    for list_id in [LIST_ACQUEREURS_SUIVI, LIST_ACQUEREURS_VISITES]:
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
            }
            
            # Budget depuis Custom Field
            for cf in card.get("customFieldItems", []):
                if cf.get("idCustomField") == CF_BUDGET_ACQUEREUR:
                    val = cf.get("value", {}).get("number")
                    if val:
                        prospect["budget"] = int(float(val))
            
            # Budget depuis description si pas de CF
            desc = card.get("desc", "")
            if not prospect["budget"]:
                prospect["budget"] = extract_budget_from_text(desc)
            
            # Secteurs et REFs
            prospect["secteurs"] = extract_secteur_keywords(desc)
            prospect["refs_citees"] = list(set(re.findall(r'\b(4\d{4})\b', desc)))
            
            prospects.append(prospect)
    
    return prospects


def find_matches(biens: List[Dict], prospects: List[Dict]) -> List[Dict]:
    """Trouve les matchs Biens -> Prospects."""
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
            
            if not (prix * BUDGET_TOLERANCE_MIN <= budget <= prix * BUDGET_TOLERANCE_MAX):
                continue
            
            score = 20
            reasons = [f"Budget {budget:,}€ vs Prix {prix:,}€"]
            
            if ref_bien in prospect.get("refs_citees", []):
                score += 50
                reasons.append(f"REF {ref_bien} déjà citée")
            
            prospect_zips = get_zip_codes_for_keywords(prospect.get("secteurs", []))
            if cp_bien and cp_bien in prospect_zips:
                score += 30
                reasons.append(f"Secteur {cp_bien} match")
            
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
    
    matches.sort(key=lambda x: x["score"], reverse=True)
    return matches


def run_matching_dry_run(pool) -> Dict:
    """Lance le matching en mode Dry Run (lecture seule)."""
    logger.info("=" * 60)
    logger.info("MATCHING BIENS -> ACQUÉREURS (DRY RUN)")
    logger.info("=" * 60)
    
    load_secteurs_from_db(pool)
    
    biens = get_biens_from_db(pool)
    logger.info(f"Biens en base: {len(biens)}")
    
    prospects = get_all_prospects()
    logger.info(f"Prospects Trello: {len(prospects)}")
    
    prospects_with_budget = [p for p in prospects if p.get("budget")]
    logger.info(f"Prospects avec budget: {len(prospects_with_budget)}")
    
    matches = find_matches(biens, prospects)
    
    matches_forts = [m for m in matches if m["type"] == "FORT"]
    matches_faibles = [m for m in matches if m["type"] == "FAIBLE"]
    
    logger.info(f"RÉSULTAT: {len(matches_forts)} FORTS, {len(matches_faibles)} FAIBLES")
    
    return {
        "biens_count": len(biens),
        "prospects_count": len(prospects),
        "prospects_with_budget": len(prospects_with_budget),
        "matches_forts": len(matches_forts),
        "matches_faibles": len(matches_faibles),
        "top_matches": matches_forts[:20],
    }


# =============================================================================
# NOTIFICATION (contrôlée par ENABLE_NOTIFICATIONS)
# =============================================================================

def notify_match_on_card(prospect_card_id: str, bien: Dict) -> bool:
    """Poste un commentaire sur la carte prospect pour notifier un match."""
    if not ENABLE_NOTIFICATIONS:
        logger.info(f"[SILENCIEUX] Notification ignorée: {bien.get('reference')} → {prospect_card_id[:8]}")
        return False
    
    comment = f"""🔔 **NOUVEAU BIEN CORRESPONDANT**

**{bien.get('titre', 'Bien')}**
- Prix: {bien.get('prix', 0):,}€
- Ville: {bien.get('ville', '')}
- REF: {bien.get('reference', '')}

_Notification automatique Axi_
"""
    
    result = trello_post(f"/cards/{prospect_card_id}/actions/comments", {"text": comment})
    return result is not None


# =============================================================================
# ENDPOINTS HTTP - REGISTRATION DES ROUTES
# =============================================================================


def register_routes(server, db):
    """
    Enregistre les routes Trello dans le serveur V19.
    
    Routes:
    - GET /trello/status
    - GET /trello/sync (dry run)
    - POST /trello/sync (live)
    - GET /trello/match
    - GET /trello/secteurs
    """
    logger.info("📋 Registering Trello routes...")
    
    # Récupérer le pool depuis l'objet db
    pool = db.pool if hasattr(db, 'pool') else db
    
    def trello_status():
        """Status du module Trello."""
        return {
            "module": "trello",
            "version": "2.0.0",
            "notifications_enabled": ENABLE_NOTIFICATIONS,
            "trello_configured": bool(TRELLO_KEY and TRELLO_TOKEN),
            "secteurs_loaded": len(_secteurs_cache),
        }
    
    def trello_sync_dry():
        """Synchronisation Trello -> v19_biens (DRY RUN)."""
        try:
            init_secteurs_table(pool)
            load_secteurs_from_db(pool)
            stats = sync_biens_from_trello(pool, dry_run=True)
            return {"status": "ok", "mode": "dry_run", "stats": stats}
        except Exception as e:
            logger.error(f"Erreur sync dry: {e}")
            return {"error": str(e)}
    
    def trello_sync_live():
        """Synchronisation Trello -> v19_biens (LIVE)."""
        try:
            init_secteurs_table(pool)
            load_secteurs_from_db(pool)
            stats = sync_biens_from_trello(pool, dry_run=False)
            return {"status": "ok", "mode": "live", "stats": stats}
        except Exception as e:
            logger.error(f"Erreur sync live: {e}")
            return {"error": str(e)}
    
    def trello_match():
        """Matching Biens -> Prospects (DRY RUN)."""
        try:
            init_secteurs_table(pool)
            load_secteurs_from_db(pool)
            result = run_matching_dry_run(pool)
            return {
                "status": "ok",
                "mode": "dry_run",
                "notifications": "DISABLED",
                "biens_count": result.get("biens_count", 0),
                "prospects_count": result.get("prospects_count", 0),
                "matches_forts": result.get("matches_forts", 0),
                "matches_faibles": result.get("matches_faibles", 0),
                "top_matches": result.get("top_matches", [])[:10]
            }
        except Exception as e:
            logger.error(f"Erreur matching: {e}")
            return {"error": str(e)}
    
    def trello_secteurs():
        """Liste le référentiel secteurs."""
        try:
            load_secteurs_from_db(pool)
            return {
                "status": "ok",
                "count": len(_secteurs_cache),
                "secteurs": _secteurs_cache
            }
        except Exception as e:
            return {"error": str(e)}
    
    # Enregistrement des routes via l'API serveur V19
    server.register_route("GET", "/trello/status", trello_status)
    server.register_route("GET", "/trello/sync", trello_sync_dry)
    server.register_route("POST", "/trello/sync", trello_sync_live)
    server.register_route("GET", "/trello/match", trello_match)
    server.register_route("GET", "/trello/secteurs", trello_secteurs)
    
    logger.info("✅ Routes Trello enregistrées: /trello/status, /trello/sync, /trello/match, /trello/secteurs")


# =============================================================================
# BLOC MAIN PROTÉGÉ (ne s'exécute JAMAIS lors d'un import)
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("TEST MODULE TRELLO (standalone)")
    print("=" * 60)
    print("Ce test nécessite TRELLO_KEY et TRELLO_TOKEN en variables d'env")
