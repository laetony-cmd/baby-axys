import os
import psycopg2
from psycopg2.extras import RealDictCursor

# Configuration de la Base de Données
# Sur Railway, DATABASE_URL est fournie automatiquement
DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    """Établit une connexion à la base de données PostgreSQL."""
    try:
        if DATABASE_URL:
            # MODE PROD (RAILWAY)
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
            return conn
        else:
            # MODE LOCAL (DEV) - Fallback
            print("⚠️ [DB] DATABASE_URL introuvable, tentative localhost...")
            return psycopg2.connect(
                host="localhost",
                database="axi_db",
                user="postgres",
                password="password",
                cursor_factory=RealDictCursor
            )
    except Exception as e:
        print(f"❌ [DB] Erreur CRITIQUE de connexion : {e}")
        return None

def init_db():
    """Initialise la table si elle n'existe pas."""
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS memory (
                        id SERIAL PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        user_input TEXT,
                        axis_response TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        metadata JSONB
                    );
                """)
                conn.commit()
            print("✅ [DB] Table 'memory' vérifiée/créée.")
        except Exception as e:
            print(f"❌ [DB] Erreur init table: {e}")
        finally:
            conn.close()
