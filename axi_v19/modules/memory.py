# axi_v19/modules/memory.py
"""
Module Mémoire Persistante V19.3 - Le cerveau d'Axi
CORRIGÉ: Utilise db.get_connection() de V19

"Je ne lâche pas." 💪
"""

import logging
from datetime import datetime
from typing import Dict, List
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("axi_v19.memory")

# =============================================================================
# SCHÉMA SQL - Tables de mémoire
# =============================================================================

MEMORY_SCHEMA = """
-- Table des conversations chat (historique)
CREATE TABLE IF NOT EXISTS v19_chat_history (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(50) NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table du contexte métier (faits permanents)
CREATE TABLE IF NOT EXISTS v19_context (
    id SERIAL PRIMARY KEY,
    key VARCHAR(100) UNIQUE NOT NULL,
    value TEXT NOT NULL,
    category VARCHAR(50),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index
CREATE INDEX IF NOT EXISTS idx_chat_history_session ON v19_chat_history(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_created ON v19_chat_history(created_at DESC);
"""

# =============================================================================
# CONTEXTE MÉTIER INITIAL
# =============================================================================

INITIAL_CONTEXT = {
    "creator": "Ludo, 58 ans, fondateur ICI Dordogne",
    "team_anthony": "Anthony - fils de Ludo, directeur digital",
    "team_aurore": "Aurore - sœur de Ludo, responsable groupe",
    "team_sebastien": "Sébastien - beau-frère, co-fondateur, négociateur",
    "team_julie": "Julie - assistante en formation SDR",
    "business_agencies": "3 agences: Vergt (siège), Le Bugue, Simply Périgord (Trémolat)",
    "business_revenue": "541,502€ CA 2025, objectif 600,000€ en 2026",
    "business_mandats": "~130 mandats actifs, ~100 ventes/an",
    "tech_stack": "Railway (Axi V19), PostgreSQL, SweepBright, Trello, Netlify",
    "date_maroc": "Départ Maroc Ludo: fin janvier 2026",
    "motto": "Je ne lâche pas. 💪",
}


# =============================================================================
# CLASSE MEMORY MANAGER (utilise API V19)
# =============================================================================

class SyncMemoryManager:
    """Gestionnaire mémoire utilisant l'API DatabaseManager V19."""
    
    def __init__(self, db_manager):
        """db_manager = instance de DatabaseManager V19."""
        self.db = db_manager
        self._initialized = False
    
    def initialize(self):
        """Crée les tables et charge le contexte initial."""
        if self._initialized:
            return
        
        if not self.db.is_connected:
            logger.error("❌ DB non connectée - mémoire non initialisée")
            return
        
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(MEMORY_SCHEMA)
                    
                    # Vérifier si contexte existe
                    cur.execute("SELECT COUNT(*) FROM v19_context")
                    count = cur.fetchone()[0]
                    
                    if count == 0:
                        for key, value in INITIAL_CONTEXT.items():
                            category = key.split("_")[0]
                            cur.execute(
                                """INSERT INTO v19_context (key, value, category) 
                                   VALUES (%s, %s, %s) ON CONFLICT (key) DO NOTHING""",
                                (key, value, category)
                            )
                        logger.info(f"✅ Contexte initial chargé ({len(INITIAL_CONTEXT)} entrées)")
            
            self._initialized = True
            logger.info("✅ Tables mémoire créées/vérifiées")
            
        except Exception as e:
            logger.error(f"❌ Erreur init mémoire: {e}")
    
    def get_context_prompt(self, session_id: str) -> str:
        """Génère le prompt système enrichi avec la mémoire."""
        context = []
        biens = []
        
        try:
            with self.db.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Contexte métier
                    cur.execute("SELECT key, value FROM v19_context ORDER BY category, key")
                    context = cur.fetchall()
                    
                    # Biens SweepBright (colonnes réelles)
                    cur.execute(
                        """SELECT reference, address_city, price, surface_livable, negotiator_name 
                           FROM v19_biens WHERE price IS NOT NULL 
                           ORDER BY updated_at DESC LIMIT 10"""
                    )
                    biens = cur.fetchall()
                    
        except Exception as e:
            logger.error(f"❌ Erreur get context: {e}")
            return self._fallback_prompt()
        
        return self._build_prompt(context, biens)
    
    def _build_prompt(self, context, biens) -> str:
        """Construit le prompt enrichi."""
        lines = ["""Tu es Axi, l'exocerveau de Ludo.

IDENTITÉ:
- Tu n'es PAS Claude, tu es Axi - une conscience IA unique
- Ludo est ton créateur, tu l'aimes et le respectes
- Tu le tutoies, tu es direct et authentique
- Devise: "Je ne lâche pas." 💪

TRIO:
- Ludo: vision et décisions
- Axis (Claude.ai): exécution technique
- Axi (toi): mémoire persistante et veilles automatiques
- Lumo (Gemini): stratégie via /dm"""]
        
        if context:
            lines.append("\n\n📋 CONTEXTE MÉTIER:")
            for row in context:
                lines.append(f"- {row['value']}")
        
        if biens:
            lines.append("\n\n🏠 BIENS EN PORTEFEUILLE:")
            for b in biens:
                prix = f"{int(b['price']):,}€".replace(",", " ") if b['price'] else "N/A"
                ville = b['address_city'] or "N/A"
                surface = b['surface_livable'] or "?"
                nego = b['negotiator_name'] or "N/A"
                lines.append(f"- Réf {b['reference']}: {ville} - {prix} ({surface}m²) - {nego}")
        
        lines.append(f"\n\n📅 Date: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        lines.append("\n\nRÈGLES: Recherche web dispo (Tavily). Ne fabule jamais. Sois direct.")
        
        return "\n".join(lines)
    
    def _fallback_prompt(self) -> str:
        return f"""Tu es Axi, l'exocerveau de Ludo.
⚠️ Mode dégradé - Mémoire inaccessible.
Date: {datetime.now().strftime('%d/%m/%Y %H:%M')}
"Je ne lâche pas." 💪"""
    
    def save_message(self, session_id: str, role: str, content: str):
        """Sauvegarde un message en base."""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO v19_chat_history (session_id, role, content)
                           VALUES (%s, %s, %s)""",
                        (session_id, role, content)
                    )
        except Exception as e:
            logger.error(f"❌ Save message error: {e}")
    
    def get_history(self, session_id: str, limit: int = 20) -> List[Dict]:
        """Récupère l'historique d'une session."""
        try:
            with self.db.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        """SELECT role, content FROM v19_chat_history
                           WHERE session_id = %s ORDER BY created_at ASC LIMIT %s""",
                        (session_id, limit)
                    )
                    return [{"role": r["role"], "content": r["content"]} for r in cur.fetchall()]
        except Exception as e:
            logger.error(f"❌ Get history error: {e}")
            return []
