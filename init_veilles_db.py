#!/usr/bin/env python3
"""
INIT_VEILLES_DB.PY - Creation des tables PostgreSQL pour les veilles
"""
import os
import psycopg2

def get_db_connection():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL non definie !")
    return psycopg2.connect(database_url)

def init_tables():
    conn = get_db_connection()
    cur = conn.cursor()
    
    print("[DB] Creation des tables veilles...")
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS dpe_connus (
            numero_dpe VARCHAR(50) PRIMARY KEY,
            date_detection TIMESTAMP DEFAULT NOW(),
            code_postal VARCHAR(10),
            commune VARCHAR(100),
            etiquette VARCHAR(5),
            surface NUMERIC,
            data JSONB
        );
        CREATE INDEX IF NOT EXISTS idx_dpe_date ON dpe_connus(date_detection);
        CREATE INDEX IF NOT EXISTS idx_dpe_cp ON dpe_connus(code_postal);
        CREATE INDEX IF NOT EXISTS idx_dpe_etiquette ON dpe_connus(etiquette);
    """)
    print("[DB] Table dpe_connus creee")
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS concurrence_connue (
            id SERIAL PRIMARY KEY,
            url_annonce VARCHAR(500) UNIQUE NOT NULL,
            agence VARCHAR(100) NOT NULL,
            prix INTEGER,
            code_postal VARCHAR(10),
            date_detection TIMESTAMP DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_conc_agence ON concurrence_connue(agence);
        CREATE INDEX IF NOT EXISTS idx_conc_date ON concurrence_connue(date_detection);
        CREATE INDEX IF NOT EXISTS idx_conc_cp ON concurrence_connue(code_postal);
    """)
    print("[DB] Table concurrence_connue creee")
    
    conn.commit()
    cur.close()
    conn.close()
    print("[DB] INITIALISATION TERMINEE")

if __name__ == "__main__":
    init_tables()
