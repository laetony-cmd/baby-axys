# axi_v19/core/database.py
"""
Gestionnaire PostgreSQL thread-safe V19 - Architecture Bunker
Pool de connexions + Context Manager + Protection injection SQL

Plan Lumo V3 - Sections 3-4: Base de données sécurisée
"""

import re
import logging
import threading
from contextlib import contextmanager
from typing import Optional, List, Dict, Any, Generator

# Import conditionnel psycopg2
try:
    import psycopg2
    from psycopg2 import pool, sql
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_OK = True
except ImportError:
    PSYCOPG2_OK = False

from .config import settings, ALLOWED_TABLE_PATTERN, V19_TABLES

logger = logging.getLogger("axi_v19.database")


class DatabaseError(Exception):
    """Exception personnalisée pour les erreurs DB V19."""
    pass


class DatabaseManager:
    """
    Gestionnaire de base de données thread-safe pour V19.
    
    Caractéristiques (Plan Lumo V3):
    - Pool de connexions ThreadedConnectionPool
    - Context manager pour acquisition/libération automatique
    - Validation des noms de tables (whitelist regex)
    - Isolation stricte: tables v19_* uniquement
    """
    
    _instance: Optional['DatabaseManager'] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton thread-safe."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialisation du pool (une seule fois)."""
        if self._initialized:
            return
        
        self._pool: Optional[pool.ThreadedConnectionPool] = None
        self._initialized = True
        
        if not PSYCOPG2_OK:
            logger.error("❌ psycopg2 non disponible - DB désactivée")
            return
        
        if not settings.database_url:
            logger.warning("⚠️ DATABASE_URL vide - DB non initialisée")
            return
        
        try:
            self._pool = pool.ThreadedConnectionPool(
                minconn=settings.db_pool_min,
                maxconn=settings.db_pool_max,
                dsn=settings.database_url
            )
            logger.info(f"✅ Pool PostgreSQL initialisé ({settings.db_pool_min}-{settings.db_pool_max} connexions)")
        except Exception as e:
            logger.critical(f"❌ Échec initialisation pool DB: {e}")
            self._pool = None
    
    @property
    def is_connected(self) -> bool:
        """Vérifie si le pool est opérationnel."""
        return self._pool is not None
    
    @contextmanager
    def get_connection(self) -> Generator:
        """
        Context manager pour obtenir une connexion du pool.
        
        Usage:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT ...")
        """
        if not self._pool:
            raise DatabaseError("Pool de connexions non initialisé")
        
        conn = None
        try:
            conn = self._pool.getconn()
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Erreur DB: {e}")
            raise DatabaseError(str(e))
        finally:
            if conn:
                self._pool.putconn(conn)
    
    def _validate_table_name(self, table_name: str) -> bool:
        """
        Valide qu'un nom de table respecte le pattern V19.
        Protection contre l'injection SQL.
        """
        if not re.match(ALLOWED_TABLE_PATTERN, table_name):
            logger.warning(f"⚠️ Nom de table invalide rejeté: {table_name}")
            return False
        return True
    
    def execute_safe(self, query: str, params: tuple = None, table_name: str = None) -> List[Dict]:
        """
        Exécute une requête de manière sécurisée.
        
        Args:
            query: Requête SQL avec placeholders %s
            params: Tuple de paramètres (jamais de f-string!)
            table_name: Nom de table à valider (optionnel)
        
        Returns:
            Liste de dictionnaires (résultats)
        """
        if table_name and not self._validate_table_name(table_name):
            raise DatabaseError(f"Table non autorisée: {table_name}")
        
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(query, params)
                if cur.description:  # SELECT
                    return [dict(row) for row in cur.fetchall()]
                return []
    
    def execute_many(self, query: str, params_list: List[tuple]) -> int:
        """
        Exécute une requête en batch (INSERT multiple).
        
        Returns:
            Nombre de lignes affectées
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(query, params_list)
                return cur.rowcount
    
    # =========================================================================
    # MÉTHODES SPÉCIFIQUES V19 (Tables préfixées)
    # =========================================================================
    
    def init_v19_tables(self) -> bool:
        """
        Crée les tables V19 si elles n'existent pas.
        Ségrégation totale des données V18/V19.
        """
        if not self.is_connected:
            logger.error("DB non connectée - impossible de créer les tables")
            return False
        
        queries = [
            # Table prospects unifiés
            """
            CREATE TABLE IF NOT EXISTS v19_prospects (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                source VARCHAR(50) NOT NULL,
                reference_id VARCHAR(100),
                first_name VARCHAR(100),
                last_name VARCHAR(100),
                email VARCHAR(255),
                phone VARCHAR(20),
                address TEXT,
                zip_code VARCHAR(10),
                city VARCHAR(100),
                property_type VARCHAR(50),
                budget_min INTEGER,
                budget_max INTEGER,
                surface_min INTEGER,
                surface_max INTEGER,
                bedrooms_min INTEGER,
                dpe_letter CHAR(1),
                ges_letter CHAR(1),
                status VARCHAR(20) DEFAULT 'new',
                score INTEGER DEFAULT 0,
                last_contacted_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                raw_data JSONB
            )
            """,
            # Index prospects
            "CREATE INDEX IF NOT EXISTS idx_v19_prospects_zip ON v19_prospects(zip_code)",
            "CREATE INDEX IF NOT EXISTS idx_v19_prospects_status ON v19_prospects(status)",
            "CREATE INDEX IF NOT EXISTS idx_v19_prospects_ref ON v19_prospects(reference_id)",
            
            # Table conversations
            """
            CREATE TABLE IF NOT EXISTS v19_conversations (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                prospect_id UUID REFERENCES v19_prospects(id) ON DELETE SET NULL,
                session_id VARCHAR(100) NOT NULL,
                channel VARCHAR(50) DEFAULT 'web',
                messages JSONB DEFAULT '[]'::jsonb,
                summary TEXT,
                sentiment VARCHAR(20),
                tokens_input INTEGER DEFAULT 0,
                tokens_output INTEGER DEFAULT 0,
                model_used VARCHAR(50),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_v19_conv_session ON v19_conversations(session_id)",
            "CREATE INDEX IF NOT EXISTS idx_v19_conv_prospect ON v19_conversations(prospect_id)",
            
            # Table résultats veille
            """
            CREATE TABLE IF NOT EXISTS v19_veille_results (
                id SERIAL PRIMARY KEY,
                veille_type VARCHAR(50) NOT NULL,
                run_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                success BOOLEAN DEFAULT TRUE,
                items_found INTEGER DEFAULT 0,
                items_new INTEGER DEFAULT 0,
                duration_seconds FLOAT,
                error_message TEXT,
                details JSONB
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_v19_veille_type ON v19_veille_results(veille_type)",
            "CREATE INDEX IF NOT EXISTS idx_v19_veille_date ON v19_veille_results(run_date)",
            
            # Table brain (mémoire permanente)
            """
            CREATE TABLE IF NOT EXISTS v19_brain (
                id SERIAL PRIMARY KEY,
                category VARCHAR(50) NOT NULL,
                key VARCHAR(100) NOT NULL,
                value TEXT,
                metadata JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                UNIQUE(category, key)
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_v19_brain_cat ON v19_brain(category)",
        ]
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    for query in queries:
                        cur.execute(query)
            logger.info("✅ Tables V19 initialisées avec succès")
            return True
        except Exception as e:
            logger.error(f"❌ Erreur création tables V19: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Vérifie la santé de la connexion DB."""
        if not self.is_connected:
            return {"status": "disconnected", "pool": None}
        
        try:
            result = self.execute_safe("SELECT 1 as ok, NOW() as timestamp")
            return {
                "status": "connected",
                "pool": {
                    "min": settings.db_pool_min,
                    "max": settings.db_pool_max,
                },
                "timestamp": str(result[0]["timestamp"]) if result else None
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def close(self):
        """Ferme proprement le pool de connexions."""
        if self._pool:
            self._pool.closeall()
            logger.info("🔒 Pool PostgreSQL fermé")
            self._pool = None


# Instance globale
db = DatabaseManager()


if __name__ == "__main__":
    # Test standalone
    print("=== Test Database V19 ===")
    print(f"Connecté: {db.is_connected}")
    print(f"Health: {db.health_check()}")
