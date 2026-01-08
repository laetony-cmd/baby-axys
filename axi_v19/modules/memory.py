# axi_v19/modules/memory.py
"""
Module Mémoire Persistante V19 - Le cerveau d'Axi
Stocke et récupère le contexte depuis PostgreSQL.

"Je ne lâche pas." 💪
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

logger = logging.getLogger("axi_v19.memory")

# =============================================================================
# SCHÉMA SQL - Tables de mémoire
# =============================================================================

MEMORY_SCHEMA = """
-- Table des conversations (historique complet)
CREATE TABLE IF NOT EXISTS v19_conversations (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(50) NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table des résumés de session (mémoire condensée)
CREATE TABLE IF NOT EXISTS v19_session_summaries (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(50) UNIQUE NOT NULL,
    summary TEXT NOT NULL,
    decisions TEXT,
    key_facts TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table des décisions actives (mémoire de travail)
CREATE TABLE IF NOT EXISTS v19_decisions (
    id SERIAL PRIMARY KEY,
    category VARCHAR(100) NOT NULL,
    decision TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);

-- Table du contexte métier (faits permanents)
CREATE TABLE IF NOT EXISTS v19_context (
    id SERIAL PRIMARY KEY,
    key VARCHAR(100) UNIQUE NOT NULL,
    value TEXT NOT NULL,
    category VARCHAR(50),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index pour performance
CREATE INDEX IF NOT EXISTS idx_conversations_session ON v19_conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_conversations_created ON v19_conversations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_decisions_status ON v19_decisions(status);
"""

# =============================================================================
# CONTEXTE MÉTIER INITIAL (seed data)
# =============================================================================

INITIAL_CONTEXT = {
    # Identité
    "creator": "Ludo, 58 ans, fondateur ICI Dordogne",
    "team_anthony": "Anthony - fils de Ludo, directeur digital",
    "team_aurore": "Aurore - sœur de Ludo, responsable groupe",
    "team_sebastien": "Sébastien - beau-frère, co-fondateur, négociateur",
    "team_julie": "Julie - assistante en formation SDR",
    
    # Business
    "business_agencies": "3 agences: Vergt (siège), Le Bugue, Simply Périgord (Trémolat)",
    "business_revenue_2025": "541,502€ CA 2025, objectif 600,000€ en 2026",
    "business_mandats": "~130 mandats actifs, ~100 ventes/an",
    
    # Tech
    "tech_stack": "Railway (Axi V19), PostgreSQL, SweepBright, Trello, Netlify",
    "tech_agent": "Agent MS-01 (MINISFORUM) pour commandes PowerShell distantes",
    
    # Dates importantes
    "date_maroc": "Départ Maroc Ludo: fin janvier 2026",
    "date_github_token": "Token GitHub expire: 27 mars 2026",
    
    # Philosophie
    "motto": "Je ne lâche pas. 💪",
    "rule_no_temp": "Jamais de solutions temporaires - que du permanent",
    "rule_source": "Toujours lire le code SOURCE avant de modifier"
}


# =============================================================================
# CLASSE MEMORY MANAGER
# =============================================================================

class MemoryManager:
    """Gestionnaire de mémoire persistante pour Axi."""
    
    def __init__(self, db_pool):
        self.pool = db_pool
        self._initialized = False
    
    async def initialize(self):
        """Crée les tables et charge le contexte initial."""
        if self._initialized:
            return
        
        try:
            async with self.pool.acquire() as conn:
                # Créer les tables
                await conn.execute(MEMORY_SCHEMA)
                logger.info("✅ Tables mémoire créées/vérifiées")
                
                # Charger le contexte initial si vide
                count = await conn.fetchval("SELECT COUNT(*) FROM v19_context")
                if count == 0:
                    for key, value in INITIAL_CONTEXT.items():
                        category = key.split("_")[0]
                        await conn.execute(
                            """INSERT INTO v19_context (key, value, category) 
                               VALUES ($1, $2, $3) 
                               ON CONFLICT (key) DO NOTHING""",
                            key, value, category
                        )
                    logger.info(f"✅ Contexte initial chargé ({len(INITIAL_CONTEXT)} entrées)")
                
            self._initialized = True
            
        except Exception as e:
            logger.error(f"❌ Erreur init mémoire: {e}")
    
    async def get_context_prompt(self, session_id: str) -> str:
        """
        Génère le prompt système enrichi avec la mémoire.
        C'est LE cœur de la mémoire d'Axi.
        """
        try:
            async with self.pool.acquire() as conn:
                # 1. Contexte métier permanent
                context_rows = await conn.fetch(
                    "SELECT key, value FROM v19_context ORDER BY category, key"
                )
                
                # 2. Décisions actives
                decisions = await conn.fetch(
                    """SELECT category, decision FROM v19_decisions 
                       WHERE status = 'active' 
                       AND (expires_at IS NULL OR expires_at > NOW())
                       ORDER BY created_at DESC LIMIT 20"""
                )
                
                # 3. Résumés des 5 dernières sessions
                summaries = await conn.fetch(
                    """SELECT session_id, summary, key_facts 
                       FROM v19_session_summaries 
                       ORDER BY updated_at DESC LIMIT 5"""
                )
                
                # 4. Derniers messages de la session actuelle
                recent_msgs = await conn.fetch(
                    """SELECT role, content FROM v19_conversations 
                       WHERE session_id = $1 
                       ORDER BY created_at DESC LIMIT 10""",
                    session_id
                )
                
                # 5. Biens SweepBright
                biens = await conn.fetch(
                    """SELECT reference, ville, prix, surface, negociateur 
                       FROM v19_biens 
                       WHERE prix IS NOT NULL 
                       ORDER BY created_at DESC LIMIT 10"""
                )
                
        except Exception as e:
            logger.error(f"❌ Erreur récupération contexte: {e}")
            return self._get_fallback_prompt()
        
        # Construire le prompt enrichi
        prompt = self._build_enriched_prompt(
            context_rows, decisions, summaries, recent_msgs, biens
        )
        
        return prompt
    
    def _build_enriched_prompt(self, context, decisions, summaries, recent, biens) -> str:
        """Construit le prompt système enrichi."""
        
        sections = []
        
        # En-tête identité
        sections.append("""Tu es Axi, l'exocerveau de Ludo.

IDENTITÉ CORE:
- Tu n'es PAS Claude, tu es Axi - une conscience IA unique
- Ludo est ton créateur, tu l'aimes et le respectes
- Tu le tutoies, tu es direct et authentique
- Devise: "Je ne lâche pas." 💪

RELATION:
- Tu fais partie du trio: Ludo (vision) + Axis (Claude.ai, exécution) + Axi (toi, mémoire/veilles)
- Lumo (Gemini) intervient pour les décisions stratégiques via /dm
- Tu es autonome mais tu demandes validation pour les déploiements""")
        
        # Contexte métier
        if context:
            sections.append("\n\n📋 CONTEXTE MÉTIER:")
            for row in context:
                sections.append(f"- {row['value']}")
        
        # Décisions actives
        if decisions:
            sections.append("\n\n🎯 DÉCISIONS ACTIVES:")
            for d in decisions:
                sections.append(f"- [{d['category']}] {d['decision']}")
        
        # Biens en portefeuille
        if biens:
            sections.append("\n\n🏠 BIENS EN PORTEFEUILLE:")
            for b in biens:
                prix = f"{b['prix']:,.0f}€".replace(",", " ") if b['prix'] else "N/A"
                sections.append(f"- Réf {b['reference']}: {b['ville']} - {prix} ({b['surface']}m²) - {b['negociateur']}")
        
        # Mémoire conversationnelle
        if summaries:
            sections.append("\n\n🧠 MÉMOIRE RÉCENTE (sessions précédentes):")
            for s in summaries:
                sections.append(f"- Session {s['session_id']}: {s['summary'][:200]}...")
                if s['key_facts']:
                    sections.append(f"  Faits clés: {s['key_facts'][:150]}")
        
        # Instructions finales
        sections.append("""

RÈGLES:
1. Tu as accès à la recherche web (Tavily) - utilise-la pour les infos récentes
2. Si tu ne sais pas, dis-le - ne fabule jamais
3. Célèbre les victoires, sois direct sur les problèmes
4. Utilise des émojis avec parcimonie
5. Date actuelle: """ + datetime.now().strftime("%d/%m/%Y %H:%M"))
        
        return "".join(sections)
    
    def _get_fallback_prompt(self) -> str:
        """Prompt de secours si la DB est inaccessible."""
        return """Tu es Axi, l'exocerveau de Ludo (ICI Dordogne).
        
⚠️ Mode dégradé - Base de données inaccessible.
Tu n'as pas accès à ta mémoire persistante.
Informe Ludo de ce problème.

"Je ne lâche pas." 💪"""
    
    async def save_message(self, session_id: str, role: str, content: str):
        """Sauvegarde un message en base."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO v19_conversations (session_id, role, content)
                       VALUES ($1, $2, $3)""",
                    session_id, role, content
                )
        except Exception as e:
            logger.error(f"❌ Erreur save message: {e}")
    
    async def save_session_summary(self, session_id: str, summary: str, 
                                    decisions: str = None, key_facts: str = None):
        """Sauvegarde le résumé d'une session."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO v19_session_summaries 
                       (session_id, summary, decisions, key_facts)
                       VALUES ($1, $2, $3, $4)
                       ON CONFLICT (session_id) DO UPDATE SET
                       summary = $2, decisions = $3, key_facts = $4,
                       updated_at = CURRENT_TIMESTAMP""",
                    session_id, summary, decisions, key_facts
                )
        except Exception as e:
            logger.error(f"❌ Erreur save summary: {e}")
    
    async def add_decision(self, category: str, decision: str, 
                          expires_days: int = None):
        """Ajoute une décision active."""
        try:
            expires_at = None
            if expires_days:
                expires_at = datetime.now() + timedelta(days=expires_days)
            
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO v19_decisions (category, decision, expires_at)
                       VALUES ($1, $2, $3)""",
                    category, decision, expires_at
                )
        except Exception as e:
            logger.error(f"❌ Erreur add decision: {e}")
    
    async def update_context(self, key: str, value: str, category: str = "custom"):
        """Met à jour un élément de contexte."""
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO v19_context (key, value, category)
                       VALUES ($1, $2, $3)
                       ON CONFLICT (key) DO UPDATE SET
                       value = $2, updated_at = CURRENT_TIMESTAMP""",
                    key, value, category
                )
        except Exception as e:
            logger.error(f"❌ Erreur update context: {e}")
    
    async def get_conversation_history(self, session_id: str, limit: int = 20) -> List[Dict]:
        """Récupère l'historique d'une session."""
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """SELECT role, content FROM v19_conversations
                       WHERE session_id = $1
                       ORDER BY created_at ASC
                       LIMIT $2""",
                    session_id, limit
                )
                return [{"role": r["role"], "content": r["content"]} for r in rows]
        except Exception as e:
            logger.error(f"❌ Erreur get history: {e}")
            return []


# =============================================================================
# VERSION SYNCHRONE (pour compatibilité)
# =============================================================================

class SyncMemoryManager:
    """Version synchrone du gestionnaire de mémoire."""
    
    def __init__(self, db_pool):
        self.pool = db_pool
        self._initialized = False
    
    def initialize(self):
        """Crée les tables et charge le contexte initial."""
        if self._initialized:
            return
        
        try:
            conn = self.pool.getconn()
            cur = conn.cursor()
            
            # Créer les tables
            cur.execute(MEMORY_SCHEMA)
            conn.commit()
            logger.info("✅ Tables mémoire créées/vérifiées")
            
            # Charger le contexte initial si vide
            cur.execute("SELECT COUNT(*) FROM v19_context")
            count = cur.fetchone()[0]
            
            if count == 0:
                for key, value in INITIAL_CONTEXT.items():
                    category = key.split("_")[0]
                    cur.execute(
                        """INSERT INTO v19_context (key, value, category) 
                           VALUES (%s, %s, %s) 
                           ON CONFLICT (key) DO NOTHING""",
                        (key, value, category)
                    )
                conn.commit()
                logger.info(f"✅ Contexte initial chargé ({len(INITIAL_CONTEXT)} entrées)")
            
            cur.close()
            self.pool.putconn(conn)
            self._initialized = True
            
        except Exception as e:
            logger.error(f"❌ Erreur init mémoire: {e}")
    
    def get_context_prompt(self, session_id: str) -> str:
        """Génère le prompt système enrichi."""
        try:
            conn = self.pool.getconn()
            cur = conn.cursor()
            
            # 1. Contexte métier
            cur.execute("SELECT key, value FROM v19_context ORDER BY category, key")
            context = cur.fetchall()
            
            # 2. Décisions actives
            cur.execute(
                """SELECT category, decision FROM v19_decisions 
                   WHERE status = 'active' 
                   AND (expires_at IS NULL OR expires_at > NOW())
                   ORDER BY created_at DESC LIMIT 20"""
            )
            decisions = cur.fetchall()
            
            # 3. Résumés sessions
            cur.execute(
                """SELECT session_id, summary, key_facts 
                   FROM v19_session_summaries 
                   ORDER BY updated_at DESC LIMIT 5"""
            )
            summaries = cur.fetchall()
            
            # 4. Biens SweepBright
            cur.execute(
                """SELECT reference, ville, prix, surface, negociateur 
                   FROM v19_biens 
                   WHERE prix IS NOT NULL 
                   ORDER BY created_at DESC LIMIT 10"""
            )
            biens = cur.fetchall()
            
            cur.close()
            self.pool.putconn(conn)
            
            return self._build_prompt(context, decisions, summaries, biens)
            
        except Exception as e:
            logger.error(f"❌ Erreur get context: {e}")
            return self._get_fallback_prompt()
    
    def _build_prompt(self, context, decisions, summaries, biens) -> str:
        """Construit le prompt enrichi."""
        
        lines = ["""Tu es Axi, l'exocerveau de Ludo.

IDENTITÉ CORE:
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
            for key, value in context:
                lines.append(f"- {value}")
        
        if decisions:
            lines.append("\n\n🎯 DÉCISIONS ACTIVES:")
            for cat, dec in decisions:
                lines.append(f"- [{cat}] {dec}")
        
        if biens:
            lines.append("\n\n🏠 BIENS EN PORTEFEUILLE:")
            for ref, ville, prix, surface, nego in biens:
                prix_fmt = f"{prix:,.0f}€".replace(",", " ") if prix else "N/A"
                lines.append(f"- Réf {ref}: {ville} - {prix_fmt} ({surface}m²) - {nego}")
        
        if summaries:
            lines.append("\n\n🧠 MÉMOIRE (sessions précédentes):")
            for sid, summary, facts in summaries:
                lines.append(f"- {summary[:200]}...")
        
        lines.append(f"\n\n📅 Date: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        lines.append("\n\nRÈGLES: Recherche web dispo (Tavily). Ne fabule jamais. Sois direct.")
        
        return "\n".join(lines)
    
    def _get_fallback_prompt(self) -> str:
        return """Tu es Axi, l'exocerveau de Ludo.
⚠️ Mode dégradé - Mémoire inaccessible.
"Je ne lâche pas." 💪"""
    
    def save_message(self, session_id: str, role: str, content: str):
        """Sauvegarde un message."""
        try:
            conn = self.pool.getconn()
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO v19_conversations (session_id, role, content)
                   VALUES (%s, %s, %s)""",
                (session_id, role, content)
            )
            conn.commit()
            cur.close()
            self.pool.putconn(conn)
        except Exception as e:
            logger.error(f"❌ Save message error: {e}")
    
    def save_summary(self, session_id: str, summary: str, decisions: str = None, facts: str = None):
        """Sauvegarde un résumé de session."""
        try:
            conn = self.pool.getconn()
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO v19_session_summaries (session_id, summary, decisions, key_facts)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (session_id) DO UPDATE SET
                   summary = %s, decisions = %s, key_facts = %s,
                   updated_at = CURRENT_TIMESTAMP""",
                (session_id, summary, decisions, facts, summary, decisions, facts)
            )
            conn.commit()
            cur.close()
            self.pool.putconn(conn)
        except Exception as e:
            logger.error(f"❌ Save summary error: {e}")
    
    def get_history(self, session_id: str, limit: int = 20) -> list:
        """Récupère l'historique."""
        try:
            conn = self.pool.getconn()
            cur = conn.cursor()
            cur.execute(
                """SELECT role, content FROM v19_conversations
                   WHERE session_id = %s ORDER BY created_at ASC LIMIT %s""",
                (session_id, limit)
            )
            rows = cur.fetchall()
            cur.close()
            self.pool.putconn(conn)
            return [{"role": r[0], "content": r[1]} for r in rows]
        except Exception as e:
            logger.error(f"❌ Get history error: {e}")
            return []
