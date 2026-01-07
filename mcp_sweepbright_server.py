"""
MCP Server SweepBright - ICI Dordogne
=====================================
Serveur MCP pour connecter Claude/Axi à SweepBright
avec stockage local PostgreSQL sur AXIS Station (MS-01)

Auteur: Axis
Date: 7 janvier 2026
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Optional
import httpx
import psycopg2
from psycopg2.extras import RealDictCursor

# Configuration logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

SWEEPBRIGHT_CONFIG = {
    "base_url": "https://website.sweepbright.com/api",
    "client_id": "766",
    "client_secret": "IyuH9EKO6whBPF34JqeOlQimSv9fRmx4XeVIUzTv",
    "api_version": "20230901"
}

POSTGRES_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "axi",
    "user": "postgres",
    "password": "axisstation"
}

# =============================================================================
# GESTIONNAIRE DE TOKEN SWEEPBRIGHT
# =============================================================================

class SweepBrightTokenManager:
    """Gère l'authentification SweepBright avec auto-refresh"""
    
    def __init__(self):
        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self.refresh_margin = timedelta(minutes=10)  # Refresh 10 min avant expiration
    
    async def get_token(self) -> str:
        """Obtient un token valide, le refresh si nécessaire"""
        if self._token_needs_refresh():
            await self._refresh_token()
        return self.access_token
    
    def _token_needs_refresh(self) -> bool:
        """Vérifie si le token doit être rafraîchi"""
        if not self.access_token or not self.token_expires_at:
            return True
        return datetime.now() >= (self.token_expires_at - self.refresh_margin)
    
    async def _refresh_token(self):
        """Obtient un nouveau token depuis SweepBright"""
        logger.info("🔄 Refresh token SweepBright...")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SWEEPBRIGHT_CONFIG['base_url']}/oauth/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": SWEEPBRIGHT_CONFIG["client_id"],
                    "client_secret": SWEEPBRIGHT_CONFIG["client_secret"]
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code != 200:
                raise Exception(f"Erreur auth SweepBright: {response.status_code} - {response.text}")
            
            data = response.json()
            self.access_token = data["access_token"]
            expires_in = data.get("expires_in", 3600)  # 1h par défaut
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            logger.info(f"✅ Token obtenu, expire à {self.token_expires_at.strftime('%H:%M:%S')}")

# Instance globale
token_manager = SweepBrightTokenManager()

# =============================================================================
# CLIENT API SWEEPBRIGHT
# =============================================================================

class SweepBrightClient:
    """Client API SweepBright"""
    
    def __init__(self):
        self.base_url = SWEEPBRIGHT_CONFIG["base_url"]
        self.api_version = SWEEPBRIGHT_CONFIG["api_version"]
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Effectue une requête authentifiée vers SweepBright"""
        token = await token_manager.get_token()
        
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Sweepbright-Version": self.api_version,
            "Accept": "application/json",
            **kwargs.pop("headers", {})
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method,
                f"{self.base_url}{endpoint}",
                headers=headers,
                **kwargs
            )
            
            if response.status_code == 401:
                # Token expiré, force refresh et réessaie
                await token_manager._refresh_token()
                token = await token_manager.get_token()
                headers["Authorization"] = f"Bearer {token}"
                response = await client.request(
                    method,
                    f"{self.base_url}{endpoint}",
                    headers=headers,
                    **kwargs
                )
            
            response.raise_for_status()
            return response.json() if response.text else {}
    
    async def get_estates(self, page: int = 1, per_page: int = 50) -> dict:
        """Récupère la liste des biens"""
        return await self._request("GET", f"/estates?page={page}&per_page={per_page}")
    
    async def get_estate(self, estate_id: str) -> dict:
        """Récupère les détails d'un bien"""
        return await self._request("GET", f"/estates/{estate_id}")
    
    async def get_contacts(self, page: int = 1, per_page: int = 50) -> dict:
        """Récupère la liste des contacts"""
        return await self._request("GET", f"/contacts?page={page}&per_page={per_page}")
    
    async def get_contact(self, contact_id: str) -> dict:
        """Récupère les détails d'un contact"""
        return await self._request("GET", f"/contacts/{contact_id}")
    
    async def create_contact(self, data: dict) -> dict:
        """Crée un nouveau contact"""
        return await self._request("POST", "/contacts", json=data)
    
    async def get_negotiations(self, estate_id: str = None) -> dict:
        """Récupère les négociations"""
        endpoint = f"/estates/{estate_id}/negotiations" if estate_id else "/negotiations"
        return await self._request("GET", endpoint)

# Instance globale
sweepbright = SweepBrightClient()

# =============================================================================
# STOCKAGE POSTGRESQL
# =============================================================================

class PostgresStorage:
    """Gère le stockage local des données SweepBright"""
    
    def __init__(self):
        self.config = POSTGRES_CONFIG
        self._init_tables()
    
    def _get_connection(self):
        """Obtient une connexion PostgreSQL"""
        return psycopg2.connect(**self.config)
    
    def _init_tables(self):
        """Initialise les tables si nécessaires"""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Table des biens
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS sweepbright_estates (
                        id VARCHAR(100) PRIMARY KEY,
                        reference VARCHAR(50),
                        title VARCHAR(500),
                        price NUMERIC,
                        price_type VARCHAR(50),
                        status VARCHAR(50),
                        type VARCHAR(50),
                        subtype VARCHAR(50),
                        address_street VARCHAR(500),
                        address_city VARCHAR(200),
                        address_postal_code VARCHAR(20),
                        surface_livable NUMERIC,
                        surface_land NUMERIC,
                        bedrooms INTEGER,
                        bathrooms INTEGER,
                        energy_class VARCHAR(10),
                        raw_data JSONB,
                        synced_at TIMESTAMP DEFAULT NOW(),
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                
                # Table des contacts
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS sweepbright_contacts (
                        id VARCHAR(100) PRIMARY KEY,
                        first_name VARCHAR(200),
                        last_name VARCHAR(200),
                        email VARCHAR(300),
                        phone VARCHAR(50),
                        type VARCHAR(50),
                        status VARCHAR(50),
                        raw_data JSONB,
                        synced_at TIMESTAMP DEFAULT NOW(),
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                
                # Table de sync
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS sweepbright_sync_log (
                        id SERIAL PRIMARY KEY,
                        sync_type VARCHAR(50),
                        records_synced INTEGER,
                        started_at TIMESTAMP,
                        completed_at TIMESTAMP,
                        status VARCHAR(50),
                        error_message TEXT
                    )
                """)
                
                conn.commit()
                logger.info("✅ Tables PostgreSQL initialisées")
    
    def upsert_estate(self, estate: dict):
        """Insère ou met à jour un bien"""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Extraire les données
                address = estate.get("location", {}).get("address", {})
                features = estate.get("features", {})
                
                cur.execute("""
                    INSERT INTO sweepbright_estates 
                    (id, reference, title, price, price_type, status, type, subtype,
                     address_street, address_city, address_postal_code,
                     surface_livable, surface_land, bedrooms, bathrooms, energy_class,
                     raw_data, synced_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        reference = EXCLUDED.reference,
                        title = EXCLUDED.title,
                        price = EXCLUDED.price,
                        price_type = EXCLUDED.price_type,
                        status = EXCLUDED.status,
                        type = EXCLUDED.type,
                        subtype = EXCLUDED.subtype,
                        address_street = EXCLUDED.address_street,
                        address_city = EXCLUDED.address_city,
                        address_postal_code = EXCLUDED.address_postal_code,
                        surface_livable = EXCLUDED.surface_livable,
                        surface_land = EXCLUDED.surface_land,
                        bedrooms = EXCLUDED.bedrooms,
                        bathrooms = EXCLUDED.bathrooms,
                        energy_class = EXCLUDED.energy_class,
                        raw_data = EXCLUDED.raw_data,
                        synced_at = NOW(),
                        updated_at = NOW()
                """, (
                    estate.get("id"),
                    estate.get("reference"),
                    estate.get("description", {}).get("title"),
                    estate.get("price", {}).get("amount"),
                    estate.get("price", {}).get("type"),
                    estate.get("status"),
                    estate.get("type"),
                    estate.get("subtype"),
                    address.get("street"),
                    address.get("city"),
                    address.get("postal_code"),
                    features.get("living_area"),
                    features.get("plot_area"),
                    features.get("bedrooms"),
                    features.get("bathrooms"),
                    estate.get("legal", {}).get("energy", {}).get("epc_value"),
                    json.dumps(estate)
                ))
                conn.commit()
    
    def upsert_contact(self, contact: dict):
        """Insère ou met à jour un contact"""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO sweepbright_contacts 
                    (id, first_name, last_name, email, phone, type, status, raw_data, synced_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        email = EXCLUDED.email,
                        phone = EXCLUDED.phone,
                        type = EXCLUDED.type,
                        status = EXCLUDED.status,
                        raw_data = EXCLUDED.raw_data,
                        synced_at = NOW(),
                        updated_at = NOW()
                """, (
                    contact.get("id"),
                    contact.get("first_name"),
                    contact.get("last_name"),
                    contact.get("email"),
                    contact.get("phone"),
                    contact.get("type"),
                    contact.get("status"),
                    json.dumps(contact)
                ))
                conn.commit()
    
    def get_estates_local(self, status: str = None, limit: int = 100) -> list:
        """Récupère les biens depuis la base locale"""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = "SELECT * FROM sweepbright_estates"
                params = []
                if status:
                    query += " WHERE status = %s"
                    params.append(status)
                query += f" ORDER BY updated_at DESC LIMIT {limit}"
                cur.execute(query, params)
                return cur.fetchall()
    
    def get_contacts_local(self, limit: int = 100) -> list:
        """Récupère les contacts depuis la base locale"""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(f"SELECT * FROM sweepbright_contacts ORDER BY updated_at DESC LIMIT {limit}")
                return cur.fetchall()
    
    def log_sync(self, sync_type: str, records: int, status: str, error: str = None):
        """Log une synchronisation"""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO sweepbright_sync_log 
                    (sync_type, records_synced, started_at, completed_at, status, error_message)
                    VALUES (%s, %s, NOW(), NOW(), %s, %s)
                """, (sync_type, records, status, error))
                conn.commit()

# Instance globale
storage = PostgresStorage()

# =============================================================================
# OUTILS MCP
# =============================================================================

async def sync_all_estates() -> dict:
    """Synchronise tous les biens depuis SweepBright vers PostgreSQL"""
    logger.info("🔄 Synchronisation des biens SweepBright...")
    
    try:
        total_synced = 0
        page = 1
        
        while True:
            result = await sweepbright.get_estates(page=page, per_page=50)
            estates = result.get("data", [])
            
            if not estates:
                break
            
            for estate in estates:
                storage.upsert_estate(estate)
                total_synced += 1
            
            logger.info(f"  Page {page}: {len(estates)} biens")
            
            # Vérifier pagination
            if len(estates) < 50:
                break
            page += 1
        
        storage.log_sync("estates", total_synced, "success")
        logger.info(f"✅ {total_synced} biens synchronisés")
        
        return {"success": True, "synced": total_synced}
    
    except Exception as e:
        storage.log_sync("estates", 0, "error", str(e))
        logger.error(f"❌ Erreur sync: {e}")
        return {"success": False, "error": str(e)}


async def sync_all_contacts() -> dict:
    """Synchronise tous les contacts depuis SweepBright vers PostgreSQL"""
    logger.info("🔄 Synchronisation des contacts SweepBright...")
    
    try:
        total_synced = 0
        page = 1
        
        while True:
            result = await sweepbright.get_contacts(page=page, per_page=50)
            contacts = result.get("data", [])
            
            if not contacts:
                break
            
            for contact in contacts:
                storage.upsert_contact(contact)
                total_synced += 1
            
            logger.info(f"  Page {page}: {len(contacts)} contacts")
            
            if len(contacts) < 50:
                break
            page += 1
        
        storage.log_sync("contacts", total_synced, "success")
        logger.info(f"✅ {total_synced} contacts synchronisés")
        
        return {"success": True, "synced": total_synced}
    
    except Exception as e:
        storage.log_sync("contacts", 0, "error", str(e))
        logger.error(f"❌ Erreur sync: {e}")
        return {"success": False, "error": str(e)}


async def get_estate_details(estate_id: str) -> dict:
    """Récupère les détails d'un bien (API live)"""
    return await sweepbright.get_estate(estate_id)


async def search_estates_local(status: str = None, city: str = None, min_price: int = None, max_price: int = None) -> list:
    """Recherche des biens dans la base locale"""
    with storage._get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = "SELECT id, reference, title, price, status, address_city, address_postal_code, surface_livable, bedrooms, energy_class FROM sweepbright_estates WHERE 1=1"
            params = []
            
            if status:
                query += " AND status = %s"
                params.append(status)
            if city:
                query += " AND LOWER(address_city) LIKE LOWER(%s)"
                params.append(f"%{city}%")
            if min_price:
                query += " AND price >= %s"
                params.append(min_price)
            if max_price:
                query += " AND price <= %s"
                params.append(max_price)
            
            query += " ORDER BY price DESC LIMIT 50"
            cur.execute(query, params)
            return cur.fetchall()


# =============================================================================
# SERVEUR HTTP (pour tests et accès direct)
# =============================================================================

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(
    title="MCP SweepBright - ICI Dordogne",
    description="Serveur MCP pour connecter Claude/Axi à SweepBright",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "service": "MCP SweepBright",
        "version": "1.0.0",
        "status": "ok",
        "endpoints": [
            "/sync/estates",
            "/sync/contacts", 
            "/estates",
            "/estates/{id}",
            "/contacts",
            "/search"
        ]
    }

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.post("/sync/estates")
async def api_sync_estates():
    """Déclenche la synchronisation des biens"""
    result = await sync_all_estates()
    return result

@app.post("/sync/contacts")
async def api_sync_contacts():
    """Déclenche la synchronisation des contacts"""
    result = await sync_all_contacts()
    return result

@app.get("/estates")
async def api_get_estates(status: str = None, limit: int = 100):
    """Liste les biens depuis la base locale"""
    estates = storage.get_estates_local(status=status, limit=limit)
    return {"count": len(estates), "data": estates}

@app.get("/estates/{estate_id}")
async def api_get_estate(estate_id: str):
    """Détails d'un bien (API live)"""
    try:
        return await sweepbright.get_estate(estate_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/contacts")
async def api_get_contacts(limit: int = 100):
    """Liste les contacts depuis la base locale"""
    contacts = storage.get_contacts_local(limit=limit)
    return {"count": len(contacts), "data": contacts}

@app.get("/search")
async def api_search(
    status: str = None,
    city: str = None,
    min_price: int = None,
    max_price: int = None
):
    """Recherche de biens"""
    results = await search_estates_local(status, city, min_price, max_price)
    return {"count": len(results), "data": results}


# =============================================================================
# POINT D'ENTRÉE
# =============================================================================

if __name__ == "__main__":
    print("""
╔═══════════════════════════════════════════════════════════╗
║         MCP SWEEPBRIGHT SERVER - ICI DORDOGNE            ║
╠═══════════════════════════════════════════════════════════╣
║  Endpoints:                                               ║
║    GET  /              - Status                           ║
║    GET  /health        - Health check                     ║
║    POST /sync/estates  - Sync biens SweepBright → PG      ║
║    POST /sync/contacts - Sync contacts SweepBright → PG   ║
║    GET  /estates       - Liste biens (local)              ║
║    GET  /estates/{id}  - Détail bien (API live)           ║
║    GET  /contacts      - Liste contacts (local)           ║
║    GET  /search        - Recherche biens                  ║
╚═══════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(app, host="0.0.0.0", port=8500)
