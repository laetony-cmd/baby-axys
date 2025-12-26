"""
AXI DATABASE LAYER - Version V4.1 Railway Compatible + Auto-Init
Compatible avec init_schema_v4_final.sql
Supporte: DATABASE_URL, variables PG*, et variables locales
Auto-initialise les tables au premier démarrage
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import json
import os
from datetime import datetime
from urllib.parse import urlparse

# === CONFIGURATION RAILWAY/LOCAL ===
def get_db_config():
    print("[DB-DEBUG] Variables ENV disponibles:")
    for k in sorted(os.environ.keys()):
        if 'PG' in k or 'DATABASE' in k or 'DB' in k:
            v = os.environ[k]
            print(f"  {k}={v[:20]}..." if len(v) > 20 else f"  {k}={v}")

    """Parse DATABASE_URL, ou PG vars, ou variables locales"""
    database_url = os.environ.get("DATABASE_URL")
    
    if database_url:
        parsed = urlparse(database_url)
        config = {
            "dbname": parsed.path[1:],
            "user": parsed.username,
            "password": parsed.password,
            "host": parsed.hostname,
            "port": parsed.port or 5432
        }
        print(f"[DB] Mode PROD détecté (DATABASE_URL) - Host: {config['host']}")
        return config
    
    elif os.environ.get("PGHOST"):
        config = {
            "host": os.environ.get("PGHOST"),
            "port": os.environ.get("PGPORT", "5432"),
            "dbname": os.environ.get("PGDATABASE"),
            "user": os.environ.get("PGUSER"),
            "password": os.environ.get("PGPASSWORD")
        }
        print(f"[DB] Mode PROD détecté (PG vars) - Host: {config['host']}")
        return config
    
    else:
        config = {
            "dbname": os.environ.get("AXI_DB_NAME", "axis_db"),
            "user": os.environ.get("AXI_DB_USER", "axis_user"),
            "password": os.environ.get("AXI_DB_PASSWORD", "ton_password_ici"),
            "host": os.environ.get("AXI_DB_HOST", "localhost"),
            "port": os.environ.get("AXI_DB_PORT", "5432")
        }
        print(f"[DB] Mode LOCAL détecté - Host: {config['host']}")
        return config

DB_CONFIG = get_db_config()

class AxiDB:
    def __init__(self):
        self.conn = None
        self._schema_initialized = False

    def connect(self):
        """Établit la connexion et initialise le schéma si nécessaire"""
        try:
            if self.conn is None or self.conn.closed:
                self.conn = psycopg2.connect(**DB_CONFIG)
                print("✅ [DB] Connexion PostgreSQL établie")
                # Auto-init schema
                if not self._schema_initialized:
                    self.init_schema()
                    self._schema_initialized = True
        except Exception as e:
            print(f"❌ [DB] Erreur connexion: {e}")
            self.conn = None
        return self.conn is not None

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def init_schema(self):
        """Initialise les tables si elles n'existent pas"""
        print("[DB] Vérification/Initialisation du schéma...")
        try:
            cur = self.conn.cursor()
            
            # Table relations
            cur.execute("""
                CREATE TABLE IF NOT EXISTS relations (
                    id SERIAL PRIMARY KEY,
                    nom VARCHAR(200) NOT NULL,
                    type VARCHAR(50),
                    email VARCHAR(200),
                    telephone VARCHAR(50),
                    adresse TEXT,
                    profil_psychologique TEXT,
                    details JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            
            # Table biens
            cur.execute("""
                CREATE TABLE IF NOT EXISTS biens (
                    id SERIAL PRIMARY KEY,
                    reference_interne VARCHAR(200) UNIQUE NOT NULL,
                    statut VARCHAR(50) DEFAULT 'veille',
                    adresse_brute TEXT,
                    code_postal VARCHAR(10),
                    ville VARCHAR(100),
                    id_parcelle VARCHAR(50),
                    latitude DECIMAL(10, 8),
                    longitude DECIMAL(11, 8),
                    type_bien VARCHAR(50) DEFAULT 'maison',
                    prix_affiche INTEGER,
                    prix_estime INTEGER,
                    surface_habitable DECIMAL(10, 2),
                    surface_terrain DECIMAL(12, 2),
                    pieces INTEGER,
                    dpe_lettre CHAR(1),
                    ges_lettre CHAR(1),
                    dpe_valeur INTEGER,
                    source_initiale VARCHAR(100),
                    url_source TEXT,
                    proprietaire_id INTEGER REFERENCES relations(id),
                    details JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            
            # Table souvenirs
            cur.execute("""
                CREATE TABLE IF NOT EXISTS souvenirs (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMPTZ DEFAULT NOW(),
                    type VARCHAR(50) NOT NULL,
                    source VARCHAR(100),
                    contenu TEXT NOT NULL,
                    relation_id INTEGER REFERENCES relations(id),
                    bien_id INTEGER REFERENCES biens(id),
                    importance INTEGER DEFAULT 5,
                    metadata JSONB DEFAULT '{}'
                )
            """)
            
            # Table faits
            cur.execute("""
                CREATE TABLE IF NOT EXISTS faits (
                    id SERIAL PRIMARY KEY,
                    sujet VARCHAR(200) NOT NULL,
                    predicat VARCHAR(200) NOT NULL,
                    objet TEXT NOT NULL,
                    confiance DECIMAL(3, 2) DEFAULT 1.00,
                    valide BOOLEAN DEFAULT TRUE,
                    source_souvenir_id INTEGER REFERENCES souvenirs(id),
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            
            # Table documents
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id SERIAL PRIMARY KEY,
                    hash_fichier VARCHAR(64) UNIQUE NOT NULL,
                    nom_original VARCHAR(255),
                    chemin_stockage TEXT,
                    type_mime VARCHAR(100),
                    taille_octets BIGINT,
                    bien_id INTEGER REFERENCES biens(id),
                    relation_id INTEGER REFERENCES relations(id),
                    statut_traitement VARCHAR(50) DEFAULT 'en_attente',
                    extraction_json JSONB,
                    contenu_texte TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    processed_at TIMESTAMPTZ
                )
            """)
            
            # Table sessions
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id SERIAL PRIMARY KEY,
                    titre VARCHAR(500),
                    resume TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            
            # Table messages
            cur.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    session_id INTEGER REFERENCES sessions(id),
                    role VARCHAR(20) NOT NULL,
                    contenu TEXT NOT NULL,
                    timestamp TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            
            # Créer Ludo s'il n'existe pas
            cur.execute("""
                INSERT INTO relations (nom, type, profil_psychologique, details)
                SELECT 'Ludo', 'famille', 'Père créateur. Tutoyer toujours.', '{"age": 58, "lieu": "Peyrebrune"}'::jsonb
                WHERE NOT EXISTS (SELECT 1 FROM relations WHERE nom = 'Ludo')
            """)
            
            self.conn.commit()
            cur.close()
            print("✅ [DB] Schéma V4 initialisé avec succès")
            
        except Exception as e:
            print(f"⚠️ [DB] Erreur init schema: {e}")
            try:
                self.conn.rollback()
            except:
                pass

    def _query(self, sql, params=None, fetch=False, fetch_one=False):
        """Exécute une requête SQL"""
        if not self.connect():
            return None
        try:
            cur = self.conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(sql, params)
            
            if fetch_one:
                result = cur.fetchone()
            elif fetch:
                result = cur.fetchall()
            else:
                self.conn.commit()
                result = cur.rowcount
            
            cur.close()
            return result
        except Exception as e:
            print(f"⚠️ [DB] Erreur: {e}")
            try:
                self.conn.rollback()
            except:
                pass
            return None

    # === RELATIONS ===
    def get_relation(self, nom):
        return self._query(
            "SELECT * FROM relations WHERE nom ILIKE %s LIMIT 1;",
            (f"%{nom}%",), fetch_one=True
        )

    def add_relation(self, nom, type_rel='contact', email=None, telephone=None, profil=None, details=None):
        existing = self.get_relation(nom)
        if existing:
            return existing['id']
        return self._query("""
            INSERT INTO relations (nom, type, email, telephone, profil_psychologique, details)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id;
        """, (nom, type_rel, email, telephone, profil, json.dumps(details or {})), fetch_one=True)

    # === BIENS ===

    def trouver_ou_creer_relation(self, nom, type_rel="contact", email=None, telephone=None, profil=None, details=None):
        """Trouve une relation existante ou en crée une nouvelle, retourne le dict complet"""
        existing = self.get_relation(nom)
        if existing:
            return existing
        # Créer la relation
        self.add_relation(nom, type_rel, email, telephone, profil, details)
        # Retourner la relation créée
        return self.get_relation(nom)
    def add_bien(self, reference, **kwargs):
        existing = self._query(
            "SELECT id FROM biens WHERE reference_interne = %s;",
            (reference,), fetch_one=True
        )
        if existing:
            return None  # Déjà existant
        
        return self._query("""
            INSERT INTO biens (reference_interne, statut, adresse_brute, code_postal, ville,
                              type_bien, prix_affiche, surface_habitable, dpe_lettre, ges_lettre,
                              source_initiale, url_source, details)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """, (
            reference,
            kwargs.get('statut', 'veille'),
            kwargs.get('adresse'),
            kwargs.get('code_postal'),
            kwargs.get('ville'),
            kwargs.get('type_bien', 'maison'),
            kwargs.get('prix'),
            kwargs.get('surface'),
            kwargs.get('dpe'),
            kwargs.get('ges'),
            kwargs.get('source', 'manuel'),
            kwargs.get('url'),
            json.dumps(kwargs.get('details', {}))
        ), fetch_one=True)

    def stats_biens_par_dpe(self):
        result = self._query("""
            SELECT dpe_lettre, COUNT(*) as count 
            FROM biens 
            WHERE dpe_lettre IS NOT NULL
            GROUP BY dpe_lettre 
            ORDER BY dpe_lettre;
        """, fetch=True)
        return result or []

    # === SOUVENIRS ===
    def add_souvenir(self, type_souvenir, source, contenu, importance=5, metadata=None):
        return self._query("""
            INSERT INTO souvenirs (type, source, contenu, importance, metadata)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id;
        """, (type_souvenir, source, contenu, importance, json.dumps(metadata or {})), fetch_one=True)

    def get_souvenirs(self, limit=50, type_filter=None, source_filter=None):
        sql = "SELECT * FROM souvenirs WHERE 1=1"
        params = []
        
        if type_filter:
            sql += " AND type = %s"
            params.append(type_filter)
        if source_filter:
            sql += " AND source = %s"
            params.append(source_filter)
        
        sql += " ORDER BY timestamp DESC LIMIT %s;"
        params.append(limit)
        
        return self._query(sql, params, fetch=True) or []

    def search_souvenirs(self, query, limit=20):
        return self._query("""
            SELECT *, ts_rank(to_tsvector('french', contenu), plainto_tsquery('french', %s)) as rank
            FROM souvenirs
            WHERE to_tsvector('french', contenu) @@ plainto_tsquery('french', %s)
            ORDER BY rank DESC, timestamp DESC
            LIMIT %s;
        """, (query, query, limit), fetch=True) or []

    # === FAITS ===
    def add_fait(self, sujet, predicat, objet, confiance=1.0):
        return self._query("""
            INSERT INTO faits (sujet, predicat, objet, confiance)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            RETURNING id;
        """, (sujet, predicat, objet, confiance), fetch_one=True)

    def get_faits(self, sujet=None, limit=100):
        if sujet:
            return self._query(
                "SELECT * FROM faits WHERE sujet ILIKE %s AND valide = TRUE ORDER BY confiance DESC LIMIT %s;",
                (f"%{sujet}%", limit), fetch=True
            ) or []
        return self._query(
            "SELECT * FROM faits WHERE valide = TRUE ORDER BY created_at DESC LIMIT %s;",
            (limit,), fetch=True
        ) or []

    # === SESSIONS ===
    def create_session(self, titre=None):
        result = self._query("""
            INSERT INTO sessions (titre, created_at)
            VALUES (%s, NOW())
            RETURNING id, created_at;
        """, (titre,), fetch_one=True)
        return result

    def get_sessions(self, limit=20):
        return self._query("""
            SELECT s.*, 
                   (SELECT COUNT(*) FROM messages WHERE session_id = s.id) as message_count
            FROM sessions s
            ORDER BY updated_at DESC
            LIMIT %s;
        """, (limit,), fetch=True) or []

    def get_session(self, session_id):
        return self._query(
            "SELECT * FROM sessions WHERE id = %s;",
            (session_id,), fetch_one=True
        )

    def update_session(self, session_id, titre=None, resume=None):
        updates = []
        params = []
        if titre:
            updates.append("titre = %s")
            params.append(titre)
        if resume:
            updates.append("resume = %s")
            params.append(resume)
        updates.append("updated_at = NOW()")
        params.append(session_id)
        
        return self._query(
            f"UPDATE sessions SET {', '.join(updates)} WHERE id = %s;",
            params
        )

    # === MESSAGES ===
    def add_message(self, session_id, role, contenu):
        self._query(
            "UPDATE sessions SET updated_at = NOW() WHERE id = %s;",
            (session_id,)
        )
        return self._query("""
            INSERT INTO messages (session_id, role, contenu)
            VALUES (%s, %s, %s)
            RETURNING id;
        """, (session_id, role, contenu), fetch_one=True)

    def get_messages(self, session_id, limit=100):
        return self._query("""
            SELECT * FROM messages
            WHERE session_id = %s
            ORDER BY timestamp ASC
            LIMIT %s;
        """, (session_id, limit), fetch=True) or []



    def log_systeme(self, message, metadata=None):
        """Log un événement système dans les souvenirs"""
        return self.add_souvenir(
            type_souvenir="systeme",
            source="axi",
            contenu=message,
            importance=3,
            metadata=metadata
        )

    def formater_historique_pour_llm(self, session_id=None, limit=50):
        """Formate l'historique des messages pour le LLM"""
        if session_id:
            messages = self.get_messages(session_id, limit)
        else:
            # Récupérer les messages récents toutes sessions confondues
            messages = self._query(
                "SELECT role, contenu, created_at FROM messages ORDER BY created_at DESC LIMIT %s;",
                (limit,), fetch=True
            ) or []
        
        # Formater pour le LLM
        historique = []
        for msg in reversed(messages):  # Ordre chronologique
            role = msg.get('role', 'user')
            contenu = msg.get('contenu', '')
            historique.append(f"[{role.upper()}]: {contenu}")
        
        return "\n".join(historique)

# === INSTANCE GLOBALE ===
_db_instance = None

def get_db():
    global _db_instance
    if _db_instance is None:
        _db_instance = AxiDB()
    return _db_instance


# === TEST DE CONNEXION ===
def test_connection():
    """Test la connexion à la base"""
    db = get_db()
    if db.connect():
        print("[DB] ✅ Connexion PostgreSQL validée")
        return True
    print("[DB] ❌ Connexion PostgreSQL échouée")
    return False
