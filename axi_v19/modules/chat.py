# axi_v19/modules/chat.py
"""
Module Chat V19.3 - Interface de conversation avec Axi
MÉMOIRE PERSISTANTE via PostgreSQL.

Intègre:
- Tavily pour la recherche web
- Claude pour les réponses
- PostgreSQL pour la mémoire persistante

"Je ne lâche pas." 💪
"""

import os
import json
import logging
import requests
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger("axi_v19.chat")

# =============================================================================
# CONFIGURATION
# =============================================================================

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "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")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Domaines français prioritaires pour Tavily
FRENCH_DOMAINS = [
    "lequipe.fr", "lemonde.fr", "lefigaro.fr", "liberation.fr",
    "20minutes.fr", "bfmtv.com", "francetvinfo.fr", "rtl.fr",
    "europe1.fr", "lexpress.fr", "lepoint.fr", "nouvelobs.com",
    "huffingtonpost.fr", "ouest-france.fr", "sudouest.fr",
    "footmercato.net", "eurosport.fr", "rmcsport.bfmtv.com",
    "wikipedia.org", "gouvernement.fr", "service-public.fr"
]

# =============================================================================
# GESTIONNAIRE DE MÉMOIRE (initialisé par register_chat_routes)
# =============================================================================

_memory_manager = None
_db_pool = None

def init_memory(db_pool):
    """Initialise le gestionnaire de mémoire avec le pool DB."""
    global _memory_manager, _db_pool
    _db_pool = db_pool
    
    try:
        from .memory import SyncMemoryManager
        _memory_manager = SyncMemoryManager(db_pool)
        _memory_manager.initialize()
        logger.info("✅ Mémoire persistante initialisée")
    except Exception as e:
        logger.error(f"❌ Erreur init mémoire: {e}")
        _memory_manager = None


# =============================================================================
# TAVILY - RECHERCHE WEB
# =============================================================================

def search_web(query: str, max_results: int = 5) -> Dict[str, Any]:
    """Recherche web via Tavily avec configuration française."""
    try:
        logger.info(f"🔍 Recherche Tavily: {query}")
        
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_API_KEY,
                "query": query,
                "search_depth": "advanced",
                "include_domains": FRENCH_DOMAINS,
                "max_results": max_results,
                "include_answer": True,
                "include_raw_content": False
            },
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            logger.info(f"✅ Tavily: {len(results)} résultats")
            
            return {
                "success": True,
                "query": query,
                "answer": data.get("answer"),
                "results": [
                    {
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "content": r.get("content", "")[:500]
                    }
                    for r in results
                ]
            }
        else:
            logger.error(f"❌ Tavily erreur {response.status_code}")
            return {"success": False, "error": f"Erreur API: {response.status_code}", "results": []}
            
    except requests.Timeout:
        return {"success": False, "error": "Timeout recherche", "results": []}
    except Exception as e:
        logger.error(f"❌ Tavily exception: {e}")
        return {"success": False, "error": str(e), "results": []}


# =============================================================================
# CLAUDE - GÉNÉRATION DE RÉPONSE
# =============================================================================

def generate_response(messages: List[Dict], system_prompt: str, 
                     search_results: Optional[Dict] = None) -> str:
    """Génère une réponse via Claude API avec mémoire injectée."""
    
    if not ANTHROPIC_API_KEY:
        return "❌ Erreur: Clé API Anthropic non configurée."
    
    try:
        # Enrichir le prompt avec les résultats de recherche
        system = system_prompt
        
        if search_results and search_results.get("success"):
            context = "\n\n🔍 RÉSULTATS DE RECHERCHE WEB:\n"
            if search_results.get("answer"):
                context += f"Résumé: {search_results['answer']}\n\n"
            for r in search_results.get("results", []):
                context += f"- {r['title']}: {r['content'][:200]}...\n  Source: {r['url']}\n\n"
            system += context
        
        # Appel Claude API
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 2048,
                "system": system,
                "messages": messages
            },
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            return data["content"][0]["text"]
        else:
            logger.error(f"❌ Claude API erreur {response.status_code}: {response.text}")
            return f"❌ Erreur Claude API: {response.status_code}"
            
    except Exception as e:
        logger.error(f"❌ Claude exception: {e}")
        return f"❌ Erreur: {e}"


# =============================================================================
# LOGIQUE DE CHAT
# =============================================================================

def should_search(message: str) -> bool:
    """Détermine si une recherche web est nécessaire."""
    search_triggers = [
        "match", "résultat", "score", "actualité", "news", "aujourd'hui",
        "hier", "récent", "dernier", "actuel", "maintenant", "2025", "2026",
        "météo", "température", "bourse", "cours", "prix", "élection",
        "psg", "football", "foot", "sport", "champion", "ligue",
        "cherche", "trouve", "recherche", "google", "internet"
    ]
    
    message_lower = message.lower()
    return any(trigger in message_lower for trigger in search_triggers)


# Session courante (fallback si mémoire indisponible)
_fallback_conversations: Dict[str, List[Dict]] = {}


def process_message(session_id: str, user_message: str) -> Dict[str, Any]:
    """
    Traite un message utilisateur avec MÉMOIRE PERSISTANTE.
    """
    global _memory_manager, _fallback_conversations
    
    # 1. Récupérer l'historique depuis PostgreSQL (ou fallback RAM)
    if _memory_manager:
        messages = _memory_manager.get_history(session_id, limit=20)
        system_prompt = _memory_manager.get_context_prompt(session_id)
    else:
        # Fallback sans mémoire persistante
        if session_id not in _fallback_conversations:
            _fallback_conversations[session_id] = []
        messages = _fallback_conversations[session_id]
        system_prompt = _get_fallback_system_prompt()
    
    # 2. Ajouter le message utilisateur
    messages.append({"role": "user", "content": user_message})
    
    # 3. Sauvegarder en base
    if _memory_manager:
        _memory_manager.save_message(session_id, "user", user_message)
    
    # 4. Recherche web si nécessaire
    search_results = None
    if should_search(user_message):
        logger.info(f"🔍 Recherche déclenchée: {user_message[:50]}...")
        search_results = search_web(user_message)
    
    # 5. Générer la réponse avec contexte mémoire
    response = generate_response(messages, system_prompt, search_results)
    
    # 6. Sauvegarder la réponse
    messages.append({"role": "assistant", "content": response})
    
    if _memory_manager:
        _memory_manager.save_message(session_id, "assistant", response)
    else:
        # Fallback RAM
        _fallback_conversations[session_id] = messages[-20:]
    
    return {
        "response": response,
        "search_performed": search_results is not None,
        "search_results": search_results,
        "memory_active": _memory_manager is not None
    }


def clear_session(session_id: str):
    """Efface une session (ne supprime pas de la DB, juste reset local)."""
    global _fallback_conversations
    if session_id in _fallback_conversations:
        del _fallback_conversations[session_id]
    logger.info(f"🗑️ Session {session_id} reset")


def _get_fallback_system_prompt() -> str:
    """Prompt de secours sans mémoire."""
    return f"""Tu es Axi, l'exocerveau de Ludo (ICI Dordogne).

⚠️ MODE DÉGRADÉ - Mémoire PostgreSQL non connectée.
Tu n'as pas accès à ta mémoire persistante.

IDENTITÉ:
- Tu n'es PAS Claude, tu es Axi
- Ludo est ton créateur
- Devise: "Je ne lâche pas." 💪

Date: {datetime.now().strftime('%d/%m/%Y %H:%M')}

Informe Ludo que la mémoire n'est pas disponible."""


# =============================================================================
# EXPORT pour compatibilité avec interface.py
# =============================================================================

conversations = _fallback_conversations  # Pour compatibilité
