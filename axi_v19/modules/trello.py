"""
MODULE TRELLO - AXI V19.4
=========================
Synchronisation Trello <-> v19_biens + Matching Biens -> Acquéreurs

Version: 1.0.1 (fix db.execute_safe)
Date: 7 janvier 2026
"""

import os
import re
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
import requests

logger = logging.getLogger("axi.trello")

# =============================================================================
# CONFIGURATION
# =============================================================================

TRELLO_KEY = os.getenv("TRELLO_KEY")
TRELLO_TOKEN = os.getenv("TRELLO_TOKEN")
TRELLO_BASE_URL = "https://api.trello.com/1"

# FLAG SÉCURITÉ - Notifications désactivées par défaut
ENABLE_NOTIFICATIONS = os.getenv("TRELLO_NOTIFICATIONS", "false").lower() == "true"

# IDs Trello
BOARD_BIENS = "6249623e53c07a131c916e59"
BOARD_ACQUEREURS = "5c51537bea012805e27d5bc6"
LIST_BIENS_EN_LIGNE = "5df28632d1672c6ec13ded52"
LIST_MANDATS_SIGNES = "624963ce8956e060a5187b6d"
LIST_ACQUEREURS_SUIVI = "5c5153b9dc7fe6093018849c"
LIST_ACQUEREURS_VISITES = "5ebd5702f68664068fa17c7e"
CF_BUDGET_ACQUEREUR = "5c51542db3fed40679e0ce82"

BUDGET_TOLERANCE_MIN = 0.85
BUDGET_TOLERANCE_MAX = 1.10

SECTEURS_DEFAULT = [
    {"keyword": "triangle d'or", "zip_codes": ["24260", "24510", "24480"]},
    {"keyword": "vergt", "zip_codes": ["24380", "24330", "24520", "24140"]},
    {"keyword": "le bugue", "zip_codes": ["24260", "24510", "24480", "24150"]},
    {"keyword": "bugue", "zip_codes": ["24260", "24510", "24480", "24150"]},
    {"keyword": "périgord noir", "zip_codes": ["24200", "24220", "24250", "24290"]},
    {"keyword": "périgord vert", "zip_codes": ["24310", "24340", "24350"]},
    {"keyword": "ribérac", "zip_codes": ["24600"]},
    {"keyword": "bergerac", "zip_codes": ["24100"]},
    {"keyword": "sarlat", "zip_codes": ["24200"]},
    {"keyword": "périgueux", "zip_codes": ["24000", "24650", "24750"]},
    {"keyword": "trémolat", "zip_codes": ["24510"]},
    {"keyword": "limeuil", "zip_codes": ["24510"]},
    {"keyword": "lalinde", "zip_codes": ["24150"]},
]

_secteurs_cache: List[Dict] = []
_db_ref = None  # Référence globale à db


# =============================================================================
# API TRELLO
# =============================================================================

def trello_get(endpoint: str, params: dict = None) -> Optional[Any]:
    if not TRELLO_KEY or not TRELLO_TOKEN:
        logger.error("TRELLO_KEY ou TRELLO_TOKEN non configuré")
        return None
    url = f"{TRELLO_BASE_URL}{endpoint}"
    params = params or {}
    params["key"] = TRELLO_KEY
    params["token"] = TRELLO_TOKEN
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Trello GET {endpoint}: {e}")
        return None


def trello_post(endpoint: str, data: dict = None) -> Optional[Any]:
    if not TRELLO_KEY or not TRELLO_TOKEN:
        return None
    url = f"{TRELLO_BASE_URL}{endpoint}"
    params = {"key": TRELLO_KEY, "token": TRELLO_TOKEN}
    try:
        resp = requests.post(url, params=params, data=data, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Trello POST {endpoint}: {e}")
        return None


# =============================================================================
# PARSING
# =============================================================================

def extract_ref(text: str) -> Optional[str]:
    m = re.search(r'\b(4\d{4})\b', text)
    return m.group(1) if m else None


def extract_phone(text: str) -> Optional[str]:
    for p in [r'\*\*Tél\*\*\s*:\s*([0-9\s\+\.]+)', r'(\+?\d[\d\s\.]{9,})']:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            phone = re.sub(r'[^\d\+]', '', m.group(1))
            if len(phone) >= 10:
                return phone
    return None


def extract_email(text: str) -> Optional[str]:
    m = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    return m.group(0) if m else None


def extract_chambres(text: str) -> Optional[int]:
    m = re.search(r'\*\*Nb de chambres\*\*\s*:\s*(\d+)', text, re.IGNORECASE)
    return int(m.group(1)) if m else None


def extract_chauffage(text: str) -> Optional[str]:
    m = re.search(r'\*\*Chauffage\*\*\s*:\s*([^\n\*]+)', text, re.IGNORECASE)
    return m.group(1).strip() if m else None


def extract_taxe_fonciere(text: str) -> Optional[int]:
    for p in [r'TF\s*:\s*(\d[\d\s]*)', r'taxe fonci[eè]re\s*:\s*(\d[\d\s]*)']:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            tf = re.sub(r'\s', '', m.group(1))
            if tf.isdigit():
                return int(tf)
    return None


def extract_budget_text(text: str) -> Optional[int]:
    patterns = [
        r'(\d{2,3})\s*(\d{3})\s*[€e]',
        r'(\d{2,3})\s*k',
        r'(?:budget|apport|prêt)\s*[:\s]*(\d{2,3})\s*(?:000|k)?',
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            groups = m.groups()
            if len(groups) == 2 and groups[1]:
                val = int(groups[0] + groups[1])
            else:
                val = int(groups[0])
                if val < 1000:
                    val *= 1000
            if 50000 <= val <= 2000000:
                return val
    return None


def get_secteur_zips(text: str) -> List[str]:
    text_lower = text.lower()
    zips = set()
    for s in _secteurs_cache or SECTEURS_DEFAULT:
        if s["keyword"].lower() in text_lower:
            zips.update(s.get("zip_codes", []))
    for cp in re.findall(r'\b(24\d{3})\b', text):
        zips.add(cp)
    return list(zips)


# =============================================================================
# DATABASE (utilise db.execute_safe comme les autres modules)
# =============================================================================

def init_tables(db) -> bool:
    """Crée les tables nécessaires"""
    try:
        # Table secteurs
        db.execute_safe("""
            CREATE TABLE IF NOT EXISTS v19_secteurs (
                id SERIAL PRIMARY KEY,
                keyword VARCHAR(100) UNIQUE NOT NULL,
                zip_codes JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """, table_name="v19_secteurs")
        
        # Remplir si vide
        result = db.execute_safe("SELECT COUNT(*) as count FROM v19_secteurs", table_name="v19_secteurs")
        if result and result[0].get('count', 0) == 0:
            for s in SECTEURS_DEFAULT:
                db.execute_safe(
                    "INSERT INTO v19_secteurs (keyword, zip_codes) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (s["keyword"], json.dumps(s["zip_codes"])),
                    table_name="v19_secteurs"
                )
            logger.info(f"Référentiel secteurs initialisé: {len(SECTEURS_DEFAULT)} entrées")
        
        # Colonnes enrichissement sur v19_biens
        for col, dtype in [
            ("proprietaire_nom", "VARCHAR(200)"),
            ("proprietaire_tel", "VARCHAR(50)"),
            ("proprietaire_email", "VARCHAR(200)"),
            ("nb_chambres", "INTEGER"),
            ("chauffage", "VARCHAR(100)"),
            ("taxe_fonciere", "INTEGER"),
            ("trello_card_id", "VARCHAR(50)"),
            ("trello_card_url", "TEXT"),
            ("trello_synced_at", "TIMESTAMP"),
        ]:
            try:
                db.execute_safe(f"ALTER TABLE v19_biens ADD COLUMN IF NOT EXISTS {col} {dtype}", table_name="v19_biens")
            except:
                pass
        
        return True
    except Exception as e:
        logger.error(f"init_tables: {e}")
        return False


def load_secteurs(db) -> List[Dict]:
    """Charge le référentiel secteurs"""
    global _secteurs_cache
    try:
        result = db.execute_safe("SELECT keyword, zip_codes FROM v19_secteurs", table_name="v19_secteurs")
        if result:
            _secteurs_cache = [{"keyword": r["keyword"], "zip_codes": r["zip_codes"]} for r in result]
        return _secteurs_cache
    except Exception as e:
        logger.error(f"load_secteurs: {e}")
        _secteurs_cache = SECTEURS_DEFAULT
        return _secteurs_cache


def update_bien_trello(db, reference: str, data: Dict) -> bool:
    """Met à jour un bien avec les données Trello"""
    try:
        updates = []
        values = []
        
        for key in ["proprietaire_nom", "proprietaire_tel", "proprietaire_email", 
                    "nb_chambres", "chauffage", "taxe_fonciere", 
                    "trello_card_id", "trello_card_url"]:
            if key in data and data[key] is not None:
                updates.append(f"{key} = %s")
                values.append(data[key])
        
        if not updates:
            return False
        
        updates.append("trello_synced_at = NOW()")
        values.append(reference)
        
        db.execute_safe(
            f"UPDATE v19_biens SET {', '.join(updates)} WHERE reference = %s",
            tuple(values),
            table_name="v19_biens"
        )
        return True
    except Exception as e:
        logger.error(f"update_bien_trello {reference}: {e}")
        return False


def get_biens(db) -> List[Dict]:
    """Récupère les biens actifs"""
    try:
        result = db.execute_safe("""
            SELECT id, reference, titre, prix, surface_habitable, ville, code_postal, negociateur
            FROM v19_biens WHERE statut IS NULL OR statut != 'vendu'
        """, table_name="v19_biens")
        return result or []
    except Exception as e:
        logger.error(f"get_biens: {e}")
        return []


# =============================================================================
# SYNC TRELLO -> v19_biens
# =============================================================================

def sync_biens_from_trello(db, dry_run: bool = False) -> Dict:
    """Synchronise les infos Trello vers v19_biens"""
    logger.info("=" * 60)
    logger.info(f"SYNC TRELLO -> v19_biens | Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    logger.info("=" * 60)
    
    stats = {"scanned": 0, "refs_found": 0, "enriched": 0, "not_in_db": 0, "details": []}
    
    for list_id in [LIST_BIENS_EN_LIGNE, LIST_MANDATS_SIGNES]:
        cards = trello_get(f"/lists/{list_id}/cards", {"fields": "id,name,desc,url"})
        if not cards:
            continue
        
        for card in cards:
            stats["scanned"] += 1
            ref = extract_ref(card["name"])
            if not ref:
                continue
            
            stats["refs_found"] += 1
            desc = card.get("desc", "")
            
            proprio_nom = card["name"].split("-")[0].strip() if "-" in card["name"] else None
            
            enrichment = {
                "proprietaire_nom": proprio_nom,
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
            
            detail = {"ref": ref, **{k: v for k, v in enrichment.items() if "trello_" not in k}}
            
            if dry_run:
                logger.info(f"  [DRY] REF {ref}: {detail}")
                stats["enriched"] += 1
            else:
                if update_bien_trello(db, ref, enrichment):
                    logger.info(f"  [OK] REF {ref} enrichi")
                    stats["enriched"] += 1
                else:
                    stats["not_in_db"] += 1
            
            stats["details"].append(detail)
    
    logger.info(f"RÉSULTAT: {stats['enriched']} biens enrichis sur {stats['refs_found']} REFs")
    return stats


# =============================================================================
# MATCHING
# =============================================================================

def get_prospects() -> List[Dict]:
    """Récupère les prospects avec critères"""
    prospects = []
    
    for list_id in [LIST_ACQUEREURS_SUIVI, LIST_ACQUEREURS_VISITES]:
        cards = trello_get(f"/lists/{list_id}/cards", {
            "fields": "id,name,desc,url",
            "customFieldItems": "true"
        })
        if not cards:
            continue
        
        for card in cards:
            desc = card.get("desc", "")
            budget = None
            
            for cf in card.get("customFieldItems", []):
                if cf.get("idCustomField") == CF_BUDGET_ACQUEREUR:
                    val = cf.get("value", {}).get("number")
                    if val:
                        budget = int(float(val))
            
            if not budget:
                budget = extract_budget_text(desc)
            
            prospects.append({
                "id": card["id"],
                "name": card["name"],
                "url": card["url"],
                "budget": budget,
                "secteur_zips": get_secteur_zips(desc),
                "refs_citees": list(set(re.findall(r'\b(4\d{4})\b', desc))),
            })
    
    return prospects


def find_matches(biens: List[Dict], prospects: List[Dict]) -> List[Dict]:
    """Trouve les matchs Biens -> Prospects"""
    matches = []
    
    for bien in biens:
        prix = bien.get("prix")
        if not prix:
            continue
        
        cp = bien.get("code_postal", "")
        ref = str(bien.get("reference", ""))
        
        for prospect in prospects:
            budget = prospect.get("budget")
            if not budget:
                continue
            
            if not (prix * BUDGET_TOLERANCE_MIN <= budget <= prix * BUDGET_TOLERANCE_MAX):
                continue
            
            score = 20
            reasons = [f"Budget {budget:,}€ vs Prix {prix:,}€"]
            
            if ref in prospect.get("refs_citees", []):
                score += 50
                reasons.append(f"REF {ref} citée")
            
            if cp and cp in prospect.get("secteur_zips", []):
                score += 30
                reasons.append(f"Secteur {cp}")
            
            matches.append({
                "bien_ref": ref,
                "bien_titre": bien.get("titre", ""),
                "bien_prix": prix,
                "bien_ville": bien.get("ville", ""),
                "prospect_name": prospect["name"],
                "prospect_id": prospect["id"],
                "prospect_budget": budget,
                "score": score,
                "type": "FORT" if score >= 50 else "FAIBLE",
                "reasons": reasons,
            })
    
    return sorted(matches, key=lambda x: x["score"], reverse=True)


def run_matching(db, notify: bool = False) -> Dict:
    """Lance le matching"""
    logger.info("=" * 60)
    logger.info(f"MATCHING | Notifications: {'ON' if notify and ENABLE_NOTIFICATIONS else 'OFF'}")
    logger.info("=" * 60)
    
    load_secteurs(db)
    
    biens = get_biens(db)
    logger.info(f"Biens en base: {len(biens)}")
    
    prospects = get_prospects()
    with_budget = [p for p in prospects if p.get("budget")]
    logger.info(f"Prospects: {len(prospects)} (avec budget: {len(with_budget)})")
    
    matches = find_matches(biens, prospects)
    forts = [m for m in matches if m["type"] == "FORT"]
    faibles = [m for m in matches if m["type"] == "FAIBLE"]
    
    logger.info(f"Matchs FORTS: {len(forts)} | Matchs faibles: {len(faibles)}")
    
    for m in forts[:10]:
        logger.info(f"  🔔 {m['bien_ref']} ({m['bien_ville']}) -> {m['prospect_name']}")
    
    return {
        "biens": len(biens),
        "prospects": len(prospects),
        "prospects_with_budget": len(with_budget),
        "matches_forts": len(forts),
        "matches_faibles": len(faibles),
        "top_matches": forts[:20],
    }


# =============================================================================
# FLASK ROUTES
# =============================================================================

def register_routes(app, db):
    """Enregistre les routes Trello"""
    global _db_ref
    _db_ref = db
    
    from flask import jsonify, request
    
    # Init tables au démarrage
    init_tables(db)
    
    @app.route("/trello/status")
    def trello_status():
        return jsonify({
            "module": "trello",
            "version": "1.0.1",
            "notifications_enabled": ENABLE_NOTIFICATIONS,
            "trello_configured": bool(TRELLO_KEY and TRELLO_TOKEN),
        })
    
    @app.route("/trello/sync")
    def trello_sync():
        dry_run = request.args.get("dry_run", "false").lower() == "true"
        stats = sync_biens_from_trello(db, dry_run=dry_run)
        return jsonify({"status": "ok", "mode": "dry_run" if dry_run else "live", "stats": stats})
    
    @app.route("/trello/match")
    def trello_match():
        notify = request.args.get("notify", "false").lower() == "true"
        result = run_matching(db, notify=notify)
        return jsonify({"status": "ok", "notifications_enabled": ENABLE_NOTIFICATIONS, "result": result})
    
    @app.route("/trello/full")
    def trello_full():
        sync_stats = sync_biens_from_trello(db, dry_run=False)
        match_result = run_matching(db, notify=False)
        return jsonify({"status": "ok", "sync": sync_stats, "matching": match_result})
    
    logger.info("✅ Routes Trello enregistrées: /trello/status, /trello/sync, /trello/match, /trello/full")
