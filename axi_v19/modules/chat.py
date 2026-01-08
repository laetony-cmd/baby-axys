# axi_v19/modules/chat.py
"""
Module Chat V19.3 - Interface de conversation avec Axi
CORRIGÉ: Utilise API V19 pour mémoire persistante

"Je ne lâche pas." 💪
"""

import os
import logging
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger("axi_v19.chat")

# =============================================================================
# CONFIGURATION
# =============================================================================

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

FRENCH_DOMAINS = [
    "lequipe.fr", "lemonde.fr", "lefigaro.fr", "liberation.fr",
    "20minutes.fr", "bfmtv.com", "francetvinfo.fr", "rtl.fr",
    "wikipedia.org", "gouvernement.fr", "service-public.fr"
]

# =============================================================================
# GESTIONNAIRE DE MÉMOIRE
# =============================================================================

_memory_manager = None

def init_memory(db_manager):
    """Initialise le gestionnaire de mémoire avec le DatabaseManager V19."""
    global _memory_manager
    
    try:
        from .memory import SyncMemoryManager
        _memory_manager = SyncMemoryManager(db_manager)
        _memory_manager.initialize()
        logger.info("✅ Mémoire persistante initialisée")
    except Exception as e:
        logger.error(f"❌ Erreur init mémoire: {e}")
        _memory_manager = None


# =============================================================================
# TAVILY - RECHERCHE WEB
# =============================================================================

def search_web(query: str, max_results: int = 5) -> Dict[str, Any]:
    """Recherche web via Tavily."""
    if not TAVILY_API_KEY:
        return {"success": False, "error": "Tavily non configuré", "results": []}
    
    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_API_KEY,
                "query": query,
                "search_depth": "advanced",
                "include_domains": FRENCH_DOMAINS,
                "max_results": max_results,
                "include_answer": True,
            },
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "answer": data.get("answer"),
                "results": [
                    {"title": r.get("title", ""), "url": r.get("url", ""), "content": r.get("content", "")[:500]}
                    for r in data.get("results", [])
                ]
            }
        return {"success": False, "error": f"API: {response.status_code}", "results": []}
        
    except Exception as e:
        logger.error(f"❌ Tavily error: {e}")
        return {"success": False, "error": str(e), "results": []}


# =============================================================================
# CLAUDE - GÉNÉRATION RÉPONSE
# =============================================================================

def generate_response(messages: List[Dict], system_prompt: str, search_results: Optional[Dict] = None) -> str:
    """Génère une réponse via Claude API."""
    if not ANTHROPIC_API_KEY:
        return "❌ Clé API Anthropic non configurée."
    
    system = system_prompt
    if search_results and search_results.get("success"):
        context = "\n\n🔍 RÉSULTATS RECHERCHE:\n"
        if search_results.get("answer"):
            context += f"Résumé: {search_results['answer']}\n"
        for r in search_results.get("results", [])[:3]:
            context += f"- {r['title']}: {r['content'][:200]}...\n"
        system += context
    
    try:
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
            return response.json()["content"][0]["text"]
        return f"❌ Erreur Claude: {response.status_code}"
        
    except Exception as e:
        return f"❌ Erreur: {e}"


# =============================================================================
# LOGIQUE CHAT
# =============================================================================

def should_search(message: str) -> bool:
    """Détermine si une recherche est nécessaire."""
    triggers = ["match", "résultat", "score", "actualité", "news", "aujourd'hui",
                "hier", "récent", "2025", "2026", "météo", "foot", "psg", "cherche"]
    return any(t in message.lower() for t in triggers)


_fallback_conversations: Dict[str, List[Dict]] = {}


def process_message(session_id: str, user_message: str) -> Dict[str, Any]:
    """Traite un message avec mémoire persistante."""
    global _memory_manager, _fallback_conversations
    
    # Récupérer historique
    if _memory_manager:
        messages = _memory_manager.get_history(session_id, limit=20)
        system_prompt = _memory_manager.get_context_prompt(session_id)
    else:
        if session_id not in _fallback_conversations:
            _fallback_conversations[session_id] = []
        messages = _fallback_conversations[session_id]
        system_prompt = f"""Tu es Axi, l'exocerveau de Ludo.
⚠️ Mode RAM - Mémoire non persistante.
Date: {datetime.now().strftime('%d/%m/%Y %H:%M')}
"Je ne lâche pas." 💪"""
    
    # Ajouter message user
    messages.append({"role": "user", "content": user_message})
    
    # Sauvegarder en base
    if _memory_manager:
        _memory_manager.save_message(session_id, "user", user_message)
    
    # Recherche web si nécessaire
    search_results = None
    if should_search(user_message):
        search_results = search_web(user_message)
    
    # Générer réponse
    response = generate_response(messages, system_prompt, search_results)
    
    # Sauvegarder réponse
    messages.append({"role": "assistant", "content": response})
    if _memory_manager:
        _memory_manager.save_message(session_id, "assistant", response)
    else:
        _fallback_conversations[session_id] = messages[-20:]
    
    return {
        "response": response,
        "search_performed": search_results is not None,
        "memory_active": _memory_manager is not None
    }


def clear_session(session_id: str):
    """Reset session locale."""
    if session_id in _fallback_conversations:
        del _fallback_conversations[session_id]


# Export pour compatibilité
conversations = _fallback_conversations
