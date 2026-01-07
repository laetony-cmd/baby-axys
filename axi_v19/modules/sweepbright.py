# axi_v19/modules/sweepbright.py
"""
Module SweepBright - Webhook et API
Reçoit les publications de biens et les stocke dans PostgreSQL

Architecture PUSH:
1. Publication dans SweepBright → Webhook appelé
2. On récupère les détails du bien (fenêtre 60 min)
3. On stocke dans v19_biens (permanent)
"""

import os
import json
import logging
import httpx
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger("axi_v19.sweepbright")

# =============================================================================
# CONFIGURATION
# =============================================================================

SWEEPBRIGHT_CONFIG = {
    "base_url": "https://website.sweepbright.com/api",
    "client_id": os.environ.get("SWEEPBRIGHT_CLIENT_ID", "766"),
    "client_secret": os.environ.get("SWEEPBRIGHT_CLIENT_SECRET", "IyuH9EKO6whBPF34JqeOlQimSv9fRmx4XeVIUzTv"),
    "api_version": "20241030"
}

# Token cache
_token_cache = {
    "access_token": None,
    "expires_at": None
}

# =============================================================================
# AUTHENTIFICATION
# =============================================================================

def get_access_token() -> str:
    """Obtient un token valide (avec cache)."""
    global _token_cache
    
    # Vérifier le cache
    if _token_cache["access_token"] and _token_cache["expires_at"]:
        if datetime.now().timestamp() < _token_cache["expires_at"] - 300:  # 5 min marge
            return _token_cache["access_token"]
    
    # Nouveau token
    logger.info("🔄 Refresh token SweepBright...")
    
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            f"{SWEEPBRIGHT_CONFIG['base_url']}/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": SWEEPBRIGHT_CONFIG["client_id"],
                "client_secret": SWEEPBRIGHT_CONFIG["client_secret"]
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if response.status_code != 200:
            logger.error(f"❌ Auth SweepBright failed: {response.status_code}")
            raise Exception(f"Auth failed: {response.text}")
        
        data = response.json()
        _token_cache["access_token"] = data["access_token"]
        _token_cache["expires_at"] = datetime.now().timestamp() + data.get("expires_in", 3600)
        
        logger.info("✅ Token SweepBright obtenu")
        return _token_cache["access_token"]

# =============================================================================
# API CLIENT
# =============================================================================

def fetch_estate(estate_id: str) -> Optional[Dict[str, Any]]:
    """Récupère les détails d'un bien depuis l'API SweepBright."""
    token = get_access_token()
    
    with httpx.Client(timeout=30.0) as client:
        response = client.get(
            f"{SWEEPBRIGHT_CONFIG['base_url']}/estates/{estate_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": f"application/vnd.sweepbright.v{SWEEPBRIGHT_CONFIG['api_version']}+json"
            }
        )
        
        if response.status_code == 404:
            logger.warning(f"⚠️ Bien {estate_id} non trouvé (expiré ou non publié)")
            return None
        
        if response.status_code != 200:
            logger.error(f"❌ Erreur API: {response.status_code} - {response.text[:200]}")
            return None
        
        return response.json()

# =============================================================================
# DATABASE
# =============================================================================

def init_sweepbright_tables(db):
    """Crée les tables SweepBright si nécessaire."""
    try:
        db.execute_safe("""
            CREATE TABLE IF NOT EXISTS v19_biens (
                id VARCHAR(100) PRIMARY KEY,
                reference VARCHAR(50),
                title VARCHAR(500),
                description TEXT,
                price NUMERIC,
                price_type VARCHAR(50),
                status VARCHAR(50),
                type VARCHAR(50),
                subtype VARCHAR(50),
                address_street VARCHAR(500),
                address_city VARCHAR(200),
                address_postal_code VARCHAR(20),
                address_country VARCHAR(50),
                latitude NUMERIC,
                longitude NUMERIC,
                surface_livable NUMERIC,
                surface_land NUMERIC,
                bedrooms INTEGER,
                bathrooms INTEGER,
                rooms INTEGER,
                energy_class VARCHAR(10),
                ghg_class VARCHAR(10),
                construction_year INTEGER,
                images JSONB DEFAULT '[]',
                features JSONB DEFAULT '{}',
                raw_data JSONB,
                webhook_received_at TIMESTAMP,
                synced_at TIMESTAMP DEFAULT NOW(),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """, table_name="v19_biens")
        
        db.execute_safe("""
            CREATE TABLE IF NOT EXISTS v19_sweepbright_webhooks (
                id SERIAL PRIMARY KEY,
                event_type VARCHAR(100),
                estate_id VARCHAR(100),
                payload JSONB,
                processed BOOLEAN DEFAULT FALSE,
                error_message TEXT,
                received_at TIMESTAMP DEFAULT NOW(),
                processed_at TIMESTAMP
            )
        """, table_name="v19_sweepbright_webhooks")
        
        logger.info("✅ Tables SweepBright initialisées")
        return True
    except Exception as e:
        logger.error(f"❌ Erreur init tables SweepBright: {e}")
        return False

def save_estate(db, estate: Dict[str, Any], webhook_time: datetime = None) -> bool:
    """Sauvegarde un bien dans la base."""
    try:
        # Extraire les données - Format SweepBright réel
        location = estate.get("location", {})
        geo = location.get("geo", {})
        sizes = estate.get("sizes", {})
        price = estate.get("price", {})
        legal = estate.get("legal", {})
        energy = legal.get("energy", {})
        
        # Description - peut être string ou dict multilangue
        desc_raw = estate.get("description", {})
        if isinstance(desc_raw, dict):
            description = desc_raw.get("fr") or desc_raw.get("en") or ""
        else:
            description = str(desc_raw) if desc_raw else ""
        
        # Titre
        title_raw = estate.get("description_title", {})
        if isinstance(title_raw, dict):
            title = title_raw.get("fr") or title_raw.get("en") or ""
        else:
            title = str(title_raw) if title_raw else ""
        
        # Images
        images = []
        for img in estate.get("images", []):
            if isinstance(img, dict) and img.get("url"):
                images.append({
                    "url": img["url"],
                    "type": img.get("type", "image")
                })
        
        # Compter les chambres depuis la clé directe ou rooms
        bedrooms = estate.get("bedrooms")
        if bedrooms is None:
            bedrooms = len([r for r in estate.get("rooms", []) if r.get("type") == "bedrooms"])
        
        bathrooms = estate.get("bathrooms")
        if bathrooms is None:
            bathrooms = len([r for r in estate.get("rooms", []) if r.get("type") in ["bathrooms", "shower_rooms"]])
        
        db.execute_safe("""
            INSERT INTO v19_biens 
            (id, reference, title, description, price, price_type, status, type, subtype,
             address_street, address_city, address_postal_code, address_country,
             latitude, longitude, surface_livable, surface_land,
             bedrooms, bathrooms, rooms, energy_class, ghg_class, construction_year,
             images, features, raw_data, webhook_received_at, synced_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (id) DO UPDATE SET
                reference = EXCLUDED.reference,
                title = EXCLUDED.title,
                description = EXCLUDED.description,
                price = EXCLUDED.price,
                price_type = EXCLUDED.price_type,
                status = EXCLUDED.status,
                type = EXCLUDED.type,
                subtype = EXCLUDED.subtype,
                address_street = EXCLUDED.address_street,
                address_city = EXCLUDED.address_city,
                address_postal_code = EXCLUDED.address_postal_code,
                address_country = EXCLUDED.address_country,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                surface_livable = EXCLUDED.surface_livable,
                surface_land = EXCLUDED.surface_land,
                bedrooms = EXCLUDED.bedrooms,
                bathrooms = EXCLUDED.bathrooms,
                rooms = EXCLUDED.rooms,
                energy_class = EXCLUDED.energy_class,
                ghg_class = EXCLUDED.ghg_class,
                construction_year = EXCLUDED.construction_year,
                images = EXCLUDED.images,
                features = EXCLUDED.features,
                raw_data = EXCLUDED.raw_data,
                webhook_received_at = COALESCE(EXCLUDED.webhook_received_at, v19_biens.webhook_received_at),
                synced_at = NOW(),
                updated_at = NOW()
        """, (
            estate.get("id"),
            estate.get("mandate", {}).get("reference") if isinstance(estate.get("mandate"), dict) else None,
            title,
            description,
            price.get("amount"),
            "sale",  # Par défaut
            estate.get("status"),
            estate.get("type"),
            estate.get("sub_type"),
            location.get("street"),
            location.get("city"),
            location.get("postal_code"),
            location.get("country"),
            geo.get("latitude"),
            geo.get("longitude"),
            sizes.get("liveable_area", {}).get("size") if isinstance(sizes.get("liveable_area"), dict) else None,
            sizes.get("plot_area", {}).get("size") if isinstance(sizes.get("plot_area"), dict) else None,
            bedrooms,
            bathrooms,
            len(estate.get("rooms", [])),
            energy.get("epc_value") or energy.get("dpe"),
            energy.get("greenhouse_emissions") or energy.get("co2_value"),
            estate.get("features", {}).get("construction_year") if isinstance(estate.get("features"), dict) else None,
            json.dumps(images),
            json.dumps(estate.get("features", {})),
            json.dumps(estate),
            webhook_time
        ), table_name="v19_biens")
        
        logger.info(f"✅ Bien {estate.get('id')} sauvegardé ({location.get('city', 'ville inconnue')})")
        return True
    except Exception as e:
        logger.error(f"❌ Erreur sauvegarde bien: {e}")
        return False

def log_webhook(db, event_type: str, estate_id: str, payload: dict, error: str = None):
    """Log un webhook reçu."""
    try:
        db.execute_safe("""
            INSERT INTO v19_sweepbright_webhooks (event_type, estate_id, payload, processed, error_message)
            VALUES (%s, %s, %s, %s, %s)
        """, (event_type, estate_id, json.dumps(payload), error is None, error), 
        table_name="v19_sweepbright_webhooks")
    except Exception as e:
        logger.error(f"❌ Erreur log webhook: {e}")

# =============================================================================
# HANDLERS
# =============================================================================

def handle_webhook(body: dict, db) -> tuple:
    """
    Traite un webhook SweepBright.
    
    Types d'événements:
    - properties.publish : Nouvelle publication
    - properties.update : Mise à jour
    - properties.unpublish : Dépublication
    """
    event_type = body.get("event", "unknown")
    estate_id = body.get("estate_id") or body.get("property_id") or body.get("id")
    
    logger.info(f"📥 Webhook SweepBright: {event_type} - {estate_id}")
    
    if not estate_id:
        log_webhook(db, event_type, "unknown", body, "estate_id manquant")
        return 400, {"error": "estate_id manquant", "code": 400}
    
    webhook_time = datetime.now()
    
    # Dépublication
    if event_type in ["properties.unpublish", "unpublish"]:
        try:
            db.execute_safe(
                "UPDATE v19_biens SET status = 'unpublished', updated_at = NOW() WHERE id = %s",
                (estate_id,),
                table_name="v19_biens"
            )
            log_webhook(db, event_type, estate_id, body)
            return 200, {"status": "ok", "action": "unpublished", "estate_id": estate_id}
        except Exception as e:
            log_webhook(db, event_type, estate_id, body, str(e))
            return 500, {"error": str(e), "code": 500}
    
    # Publication ou mise à jour - récupérer les détails
    try:
        estate = fetch_estate(estate_id)
        
        if not estate:
            log_webhook(db, event_type, estate_id, body, "Impossible de récupérer les détails")
            # Retourner 200 pour que SweepBright ne réessaie pas
            return 200, {"status": "warning", "message": "Données non disponibles", "estate_id": estate_id}
        
        # Sauvegarder
        if save_estate(db, estate, webhook_time):
            log_webhook(db, event_type, estate_id, body)
            
            # Retourner l'URL pour SweepBright (requis pour compléter la publication)
            url = f"https://icidordogne.fr/biens/{estate_id}"
            return 200, {"url": url, "status": "ok", "estate_id": estate_id}
        else:
            log_webhook(db, event_type, estate_id, body, "Erreur sauvegarde")
            return 500, {"error": "Erreur sauvegarde", "code": 500}
    
    except Exception as e:
        log_webhook(db, event_type, estate_id, body, str(e))
        return 500, {"error": str(e), "code": 500}

def handle_get_biens(query: dict, db) -> tuple:
    """GET /sweepbright/biens - Liste les biens."""
    try:
        status = query.get("status", [None])[0]
        city = query.get("city", [None])[0]
        limit = int(query.get("limit", [50])[0])
        
        sql = "SELECT id, reference, title, price, status, address_city, surface_livable, bedrooms, energy_class, updated_at FROM v19_biens WHERE 1=1"
        params = []
        
        if status:
            sql += " AND status = %s"
            params.append(status)
        if city:
            sql += " AND LOWER(address_city) LIKE LOWER(%s)"
            params.append(f"%{city}%")
        
        sql += f" ORDER BY updated_at DESC LIMIT {limit}"
        
        biens = db.execute_safe(sql, tuple(params) if params else None, table_name="v19_biens")
        return 200, {"count": len(biens), "biens": biens}
    except Exception as e:
        return 500, {"error": str(e), "count": 0, "biens": []}

def handle_get_bien(estate_id: str, db) -> tuple:
    """GET /sweepbright/biens/{id} - Détail d'un bien."""
    try:
        biens = db.execute_safe(
            "SELECT * FROM v19_biens WHERE id = %s",
            (estate_id,),
            table_name="v19_biens"
        )
        if biens:
            return 200, biens[0]
        return 404, {"error": "Bien non trouvé", "code": 404}
    except Exception as e:
        return 500, {"error": str(e), "code": 500}

# =============================================================================
# ENREGISTREMENT DES ROUTES
# =============================================================================

def register_sweepbright_routes(server, db):
    """Enregistre les routes SweepBright."""
    logger.info("📡 Enregistrement des routes SweepBright...")
    
    # Initialiser les tables
    init_sweepbright_tables(db)
    
    # POST /webhook/sweepbright - Réception webhook
    def webhook_handler(query, body=None, headers=None):
        return handle_webhook(body or {}, db)
    server.register_route("POST", "/webhook/sweepbright", webhook_handler)
    
    # GET /sweepbright/biens - Liste des biens
    def biens_handler(query, headers=None):
        return handle_get_biens(query, db)
    server.register_route("GET", "/sweepbright/biens", biens_handler)
    
    # GET /sweepbright/biens/{id} - Détail d'un bien
    def bien_detail_handler(query, headers=None, path_params=None):
        estate_id = path_params.get("id", "") if path_params else ""
        return handle_get_bien(estate_id, db)
    server.register_route("GET", "/sweepbright/biens/{id}", bien_detail_handler)
    
    logger.info("✅ Routes SweepBright enregistrées: /webhook/sweepbright, /sweepbright/biens")
