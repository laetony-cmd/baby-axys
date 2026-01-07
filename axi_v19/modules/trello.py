"""
MODULE TRELLO - AXI V19.4
=========================
Synchronisation Trello <-> v19_biens + Matching Biens -> Acquéreurs

Version: 1.0.0
Date: 7 janvier 2026
Auteur: Axis

MODES:
- SYNC: Enrichit v19_biens avec données Trello (proprio, contact, TF...)
- MATCH: Trouve les prospects compatibles avec les biens
- NOTIFICATIONS: Désactivé par défaut (ENABLE_NOTIFICATIONS=False)
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

# ⚠️ FLAG SÉCURITÉ - Notifications désactivées par défaut
ENABLE_NOTIFICATIONS = os.getenv("TRELLO_NOTIFICATIONS", "false").lower() == "true"

# IDs Trello
BOARD_BIENS = "6249623e53c07a131c916e59"
BOARD_ACQUEREURS = "5c51537bea012805e27d5bc6"
LIST_BIENS_EN_LIGNE = "5df28632d1672c6ec13ded52"
LIST_MANDATS_SIGNES = "624963ce8956e060a5187b6d"
LIST_ACQUEREURS_SUIVI = "5c5153b9dc7fe6093018849c"
LIST_ACQUEREURS_VISITES = "5ebd5702f68664068fa17c7e"
CF_BUDGET_ACQUEREUR = "5c51542db3fed40679e0ce82"

# Seuils matching
BUDGET_TOLERANCE_MIN = 0.85
BUDGET_TOLERANCE_MAX = 1.10

# Référentiel secteurs par défaut
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
    {"keyword": "périgueux", "zip_codes": ["24000", "24650", "24750"]},
    {"keyword": "perigueux", "zip_codes": ["24000", "24650", "24750"]},
    {"keyword": "trémolat", "zip_codes": ["24510"]},
    {"keyword": "tremolat", "zip_codes": ["24510"]},
    {"keyword": "limeuil", "zip_codes": ["24510"]},
    {"keyword": "lalinde", "zip_codes": ["24150"]},
    {"keyword": "st cyprien", "zip_codes": ["24220"]},
    {"keyword": "saint cyprien", "zip_codes": ["24220"]},
]

_secteurs_cache: List[Dict] = []


# =============================================================================
# API TRELLO
# =============================================================================

def trello_get(endpoint: str, params: dict = None) -> Optional[Any]:
    """GET vers API Trello"""
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
    """POST vers API Trello"""
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
    """Extrait REF SweepBright (4XXXX)"""
    m = re.search(r'\b(4\d{4})\b', text)
    return m.group(1) if m else None


def extract_phone(text: str) -> Optional[str]:
    """Extrait téléphone"""
    patterns = [
        r'\*\*Tél\*\*\s*:\s*([0-9\s\+\.]+)',
        r'Tél\s*:\s*([0-9\s\+\.]+)',
        r'(\+?\d[\d\s\.]{9,})',
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            phone = re.sub(r'[^\d\+]', '', m.group(1))
            if len(phone) >= 10:
                return phone
    return None


def extract_email(text: str) -> Optional[str]:
    """Extrait email"""
    m = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    return m.group(0) if m else None


def extract_chambres(text: str) -> Optional[int]:
    """Extrait nombre de chambres"""
    m = re.search(r'\*\*Nb de chambres\*\*\s*:\s*(\d+)', text, re.IGNORECASE)
    return int(m.group(1)) if m else None


def extract_chauffage(text: str) -> Optional[str]:
    """Extrait type de chauffage"""
    m = re.search(r'\*\*Chauffage\*\*\s*:\s*([^\n\*]+)', text, re.IGNORECASE)
    return m.group(1).strip() if m else None


def extract_taxe_fonciere(text: str) -> Optional[int]:
    """Extrait taxe foncière"""
    for p in [r'TF\s*:\s*(\d[\d\s]*)', r'taxe fonci[eè]re\s*:\s*(\d[\d\s]*)']:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            tf = re.sub(r'\s', '', m.group(1))
            if tf.isdigit():
                return int(tf)
    return None


def extract_budget_text(text: str) -> Optional[int]:
    """Extrait budget d'un texte libre (parsing défensif)"""
    patterns = [
        r'(\d{2,3})\s*(\d{3})\s*[€e]',
        r'(\d{2,3})\s*k',
        r'(?:budget|apport|prêt|pret)\s*[:\s]*(\d{2,3})\s*(?:000|k)?',
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
    """Retourne les codes postaux pour les mots-clés secteur trouvés"""
    text_lower = text.lower()
    zips = set()
    secteurs = _secteurs_cache or SECTEURS_DEFAULT
    for s in secteurs:
        if s["keyword"].lower() in text_lower:
            zips.update(s.get("zip_codes", []))
    # Codes postaux directs
    for cp in re.findall(r'\b(24\d{3})\b', text):
        zips.add(cp)
    return list(zips)


# =============================================================================
# POSTGRESQL
# =============================================================================

def init_tables(pool) -> bool:
    """Crée les tables v19_secteurs et colonnes enrichissement si nécessaires"""
    try:
        conn = pool.getconn()
        cur = conn.cursor()
        
        # Table secteurs
        cur.execute("""
            CREATE TABLE IF NOT EXISTS v19_secteurs (
                id SERIAL PRIMARY KEY,
                keyword VARCHAR(100) UNIQUE NOT NULL,
                zip_codes JSONB NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        
        # Remplir si vide
        cur.execute("SELECT COUNT(*) FROM v19_secteurs")
        if cur.fetchone()[0] == 0:
            for s in SECTEURS_DEFAULT:
                cur.execute(
                    "INSERT INTO v19_secteurs (keyword, zip_codes) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (s["keyword"], json.dumps(s["zip_codes"]))
                )
            logger.info(f"Référentiel secteurs initialisé: {len(SECTEURS_DEFAULT)} entrées")
        
        # Colonnes enrichissement sur v19_biens
        columns_to_add = [
            ("proprietaire_nom", "VARCHAR(200)"),
            ("proprietaire_tel", "VARCHAR(50)"),
            ("proprietaire_email", "VARCHAR(200)"),
            ("nb_chambres", "INTEGER"),
            ("chauffage", "VARCHAR(100)"),
            ("taxe_fonciere", "INTEGER"),
            ("trello_card_id", "VARCHAR(50)"),
            ("trello_card_url", "TEXT"),
            ("trello_synced_at", "TIMESTAMP"),
        ]
        
        for col, dtype in columns_to_add:
            try:
                cur.execute(f"ALTER TABLE v19_biens ADD COLUMN IF NOT EXISTS {col} {dtype}")
            except:
                pass
        
        conn.commit()
        pool.putconn(conn)
        return True
    except Exception as e:
        logger.error(f"init_tables: {e}")
        return False


def load_secteurs(pool) -> List[Dict]:
    """Charge le référentiel secteurs depuis PostgreSQL"""
    global _secteurs_cache
    try:
        conn = pool.getconn()
        cur = conn.cursor()
        cur.execute("SELECT keyword, zip_codes FROM v19_secteurs")
        _secteurs_cache = [{"keyword": r[0], "zip_codes": r[1]} for r in cur.fetchall()]
        pool.putconn(conn)
        return _secteurs_cache
    except Exception as e:
        logger.error(f"load_secteurs: {e}")
        _secteurs_cache = SECTEURS_DEFAULT
        return _secteurs_cache


def update_bien_trello(pool, reference: str, data: Dict) -> bool:
    """Met à jour un bien avec les données Trello"""
    try:
        conn = pool.getconn()
        cur = conn.cursor()
        
        updates = []
        values = []
        
        mapping = {
            "proprietaire_nom": "proprietaire_nom",
            "proprietaire_tel": "proprietaire_tel",
            "proprietaire_email": "proprietaire_email",
            "nb_chambres": "nb_chambres",
            "chauffage": "chauffage",
            "taxe_fonciere": "taxe_fonciere",
            "trello_card_id": "trello_card_id",
            "trello_card_url": "trello_card_url",
        }
        
        for key, col in mapping.items():
            if key in data and data[key] is not None:
                updates.append(f"{col} = %s")
                values.append(data[key])
        
        if not updates:
            pool.putconn(conn)
            return False
        
        updates.append("trello_synced_at = NOW()")
        values.append(reference)
        
        cur.execute(f"UPDATE v19_biens SET {', '.join(updates)} WHERE reference = %s", values)
        affected = cur.rowcount
        conn.commit()
        pool.putconn(conn)
        return affected > 0
    except Exception as e:
        logger.error(f"update_bien_trello {reference}: {e}")
        return False


def get_biens(pool) -> List[Dict]:
    """Récupère les biens actifs de v19_biens"""
    try:
        conn = pool.getconn()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, reference, titre, prix, surface_habitable, ville, code_postal, negociateur
            FROM v19_biens WHERE statut IS NULL OR statut != 'vendu'
        """)
        cols = [d[0] for d in cur.description]
        biens = [dict(zip(cols, r)) for r in cur.fetchall()]
        pool.putconn(conn)
        return biens
    except Exception as e:
        logger.error(f"get_biens: {e}")
        return []


# =============================================================================
# SYNC TRELLO -> v19_biens
# =============================================================================

def sync_biens_from_trello(pool, dry_run: bool = False) -> Dict:
    """
    Synchronise les infos Trello vers v19_biens
    Mode LIVE par défaut (dry_run=False)
    """
    logger.info("=" * 60)
    logger.info(f"SYNC TRELLO -> v19_biens | Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    logger.info("=" * 60)
    
    stats = {"scanned": 0, "refs_found": 0, "enriched": 0, "not_in_db": 0, "details": []}
    
    # Scanner les listes actives
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
            
            # Extraire nom proprio du titre (avant le premier -)
            proprio_nom = None
            if "-" in card["name"]:
                proprio_nom = card["name"].split("-")[0].strip()
            
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
            
            # Filtrer None
            enrichment = {k: v for k, v in enrichment.items() if v is not None}
            
            if len(enrichment) <= 2:  # Juste card_id/url
                continue
            
            detail = {"ref": ref, **{k: v for k, v in enrichment.items() if k not in ["trello_card_id", "trello_card_url"]}}
            
            if dry_run:
                logger.info(f"  [DRY] REF {ref}: {detail}")
                stats["enriched"] += 1
            else:
                if update_bien_trello(pool, ref, enrichment):
                    logger.info(f"  [OK] REF {ref} enrichi")
                    stats["enriched"] += 1
                else:
                    logger.warning(f"  [!] REF {ref} non trouvé en base")
                    stats["not_in_db"] += 1
            
            stats["details"].append(detail)
    
    logger.info("-" * 60)
    logger.info(f"RÉSULTAT: {stats['enriched']} biens enrichis sur {stats['refs_found']} REFs")
    return stats


# =============================================================================
# MATCHING BIENS -> PROSPECTS
# =============================================================================

def get_prospects() -> List[Dict]:
    """Récupère tous les prospects avec critères"""
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
            
            # Budget Custom Field
            budget = None
            for cf in card.get("customFieldItems", []):
                if cf.get("idCustomField") == CF_BUDGET_ACQUEREUR:
                    val = cf.get("value", {}).get("number")
                    if val:
                        budget = int(float(val))
            
            # Budget texte si pas CF
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
            
            # Check budget
            if not (prix * BUDGET_TOLERANCE_MIN <= budget <= prix * BUDGET_TOLERANCE_MAX):
                continue
            
            score = 20
            reasons = [f"Budget {budget:,}€ vs Prix {prix:,}€"]
            
            # REF citée
            if ref in prospect.get("refs_citees", []):
                score += 50
                reasons.append(f"REF {ref} citée")
            
            # Secteur
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
                "prospect_url": prospect["url"],
                "prospect_budget": budget,
                "score": score,
                "type": "FORT" if score >= 50 else "FAIBLE",
                "reasons": reasons,
            })
    
    return sorted(matches, key=lambda x: x["score"], reverse=True)


def run_matching(pool, notify: bool = False) -> Dict:
    """
    Lance le matching Biens -> Prospects
    notify=False par défaut (mode silencieux)
    """
    logger.info("=" * 60)
    logger.info(f"MATCHING | Notifications: {'ON' if notify else 'OFF'}")
    logger.info("=" * 60)
    
    load_secteurs(pool)
    
    biens = get_biens(pool)
    logger.info(f"Biens en base: {len(biens)}")
    
    prospects = get_prospects()
    with_budget = [p for p in prospects if p.get("budget")]
    logger.info(f"Prospects: {len(prospects)} (avec budget: {len(with_budget)})")
    
    matches = find_matches(biens, prospects)
    forts = [m for m in matches if m["type"] == "FORT"]
    faibles = [m for m in matches if m["type"] == "FAIBLE"]
    
    logger.info(f"Matchs FORTS: {len(forts)} | Matchs faibles: {len(faibles)}")
    
    # Log des matchs forts
    for m in forts[:20]:
        logger.info(f"  🔔 {m['bien_ref']} ({m['bien_ville']}) -> {m['prospect_name']}")
        logger.info(f"     Prix: {m['bien_prix']:,}€ | Budget: {m['prospect_budget']:,}€")
        logger.info(f"     Raisons: {', '.join(m['reasons'])}")
    
    # Notifications (désactivées par défaut)
    notified = 0
    if notify and ENABLE_NOTIFICATIONS:
        for m in forts:
            if notify_prospect(m["prospect_id"], m):
                notified += 1
        logger.info(f"Notifications envoyées: {notified}")
    elif notify:
        logger.warning("⚠️ Notifications demandées mais ENABLE_NOTIFICATIONS=False")
    
    return {
        "biens": len(biens),
        "prospects": len(prospects),
        "prospects_with_budget": len(with_budget),
        "matches_forts": len(forts),
        "matches_faibles": len(faibles),
        "notified": notified,
        "top_matches": forts[:20],
    }


def notify_prospect(card_id: str, match: Dict) -> bool:
    """
    Poste un commentaire sur la carte prospect
    ⚠️ Ne s'exécute que si ENABLE_NOTIFICATIONS=True
    """
    if not ENABLE_NOTIFICATIONS:
        logger.debug(f"Notification skipped (disabled): {card_id}")
        return False
    
    comment = f"""🔔 **NOUVEAU BIEN CORRESPONDANT**

**{match.get('bien_titre', 'Bien')}** - REF {match.get('bien_ref')}
- Prix: {match.get('bien_prix', 0):,}€
- Ville: {match.get('bien_ville', '')}

_Notification automatique Axi_
"""
    return trello_post(f"/cards/{card_id}/actions/comments", {"text": comment}) is not None


# =============================================================================
# ENDPOINTS FLASK
# =============================================================================

def register_routes(app, pool):
    """Enregistre les routes Trello dans l'app Flask"""
    from flask import jsonify, request
    
    @app.route("/trello/status")
    def trello_status():
        return jsonify({
            "module": "trello",
            "version": "1.0.0",
            "notifications_enabled": ENABLE_NOTIFICATIONS,
            "boards": {
                "biens": BOARD_BIENS,
                "acquereurs": BOARD_ACQUEREURS,
            }
        })
    
    @app.route("/trello/sync")
    def trello_sync():
        """Lance la synchronisation Trello -> v19_biens"""
        dry_run = request.args.get("dry_run", "false").lower() == "true"
        stats = sync_biens_from_trello(pool, dry_run=dry_run)
        return jsonify({
            "status": "ok",
            "mode": "dry_run" if dry_run else "live",
            "stats": stats
        })
    
    @app.route("/trello/match")
    def trello_match():
        """Lance le matching Biens -> Prospects"""
        notify = request.args.get("notify", "false").lower() == "true"
        result = run_matching(pool, notify=notify)
        return jsonify({
            "status": "ok",
            "notifications_enabled": ENABLE_NOTIFICATIONS,
            "notify_requested": notify,
            "result": result
        })
    
    @app.route("/trello/full")
    def trello_full():
        """Sync + Matching complet"""
        sync_stats = sync_biens_from_trello(pool, dry_run=False)
        match_result = run_matching(pool, notify=False)
        return jsonify({
            "status": "ok",
            "sync": sync_stats,
            "matching": match_result
        })
    
    logger.info("Routes Trello enregistrées: /trello/status, /trello/sync, /trello/match, /trello/full")
