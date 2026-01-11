# axi_v19/modules/trio.py
"""
Module Trio - Consultation Axis ↔ Lumo (Gemini)
Permet à Ludo de consulter les deux IA pour un second avis

Endpoints:
- POST /trio/consult : Poser une question aux deux IA
- GET /trio/status : Vérifier que Gemini est configuré

Use cases (validés par Ludo):
- Pertes de mémoire Axis → Lumo peut avoir le contexte
- Anti-hallucination → Second avis = filet de sécurité
- Pérenne vs bricolage → Lumo recadre si patch rapide
- Règle des 3 tentatives → Après 3 échecs, consultation obligatoire

ARCHITECTURE V19: server.register_route() - PAS de routes_get directe

"Je ne lâche pas." 💪
"""

import os
import logging
from datetime import datetime

logger = logging.getLogger("axi_v19.trio")

# =============================================================================
# CONFIGURATION
# =============================================================================

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-1.5-flash"

# Context partagé pour Lumo
LUMO_CONTEXT = """Tu es Lumo, l'un des deux exobrains de Ludo (fondateur ICI Dordogne, immobilier en Dordogne).
L'autre exobrain est Axis (Claude/Anthropic). Vous formez un Trio avec Ludo.

Règles de Ludo que tu dois respecter:
- Viser la PERFECTION, pas 15/20
- Solutions PÉRENNES, pas de bricolage temporaire
- JAMAIS d'action sans validation de Ludo
- Devise: "Je ne lâche pas."

Contexte technique:
- Railway héberge Axi (baby-axys-production.up.railway.app)
- MS-01 (Minisforum) = AXIS Station locale
- Version actuelle: V19.2
- Ludo part au Maroc fin janvier 2026

Quand Axis te consulte, donne un avis clair et actionnable.
Si tu vois qu'il part en mode "bricolage", recadre-le vers du pérenne.
"""

# =============================================================================
# CLIENT GEMINI
# =============================================================================

def call_gemini(question: str, context: str = "") -> dict:
    """Appelle l'API Gemini et retourne la réponse."""
    
    if not GEMINI_API_KEY:
        return {
            "success": False,
            "error": "GEMINI_API_KEY non configurée dans Railway",
            "response": None
        }
    
    try:
        import google.generativeai as genai
        
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(GEMINI_MODEL)
        
        # Construire le prompt
        full_prompt = f"{LUMO_CONTEXT}\n\n"
        if context:
            full_prompt += f"Contexte additionnel:\n{context}\n\n"
        full_prompt += f"Question d'Axis:\n{question}"
        
        # Appel API
        response = model.generate_content(full_prompt)
        
        return {
            "success": True,
            "error": None,
            "response": response.text,
            "model": GEMINI_MODEL
        }
        
    except ImportError:
        return {
            "success": False,
            "error": "google-generativeai non installé",
            "response": None
        }
    except Exception as e:
        logger.error(f"Erreur Gemini: {e}")
        return {
            "success": False,
            "error": str(e),
            "response": None
        }

# =============================================================================
# HANDLERS HTTP (Architecture V19 - signature: query, body, headers)
# =============================================================================

def handle_trio_status(query=None, body=None, headers=None):
    """GET /trio/status - Vérifier la configuration."""
    return {
        "service": "Trio Consult",
        "gemini_configured": bool(GEMINI_API_KEY),
        "model": GEMINI_MODEL,
        "description": "Consultation Axis ↔ Lumo pour second avis",
        "endpoints": ["/trio/status", "/trio/consult"]
    }

def handle_trio_consult(query=None, body=None, headers=None):
    """POST /trio/consult - Consulter Lumo."""
    
    if not body:
        body = {}
    
    question = body.get("question", "")
    context = body.get("context", "")
    
    if not question:
        return {
            "success": False,
            "error": "Paramètre 'question' requis dans le body JSON",
            "timestamp": datetime.now().isoformat()
        }
    
    logger.info(f"🤝 Trio Consult: {question[:100]}...")
    
    # Appeler Gemini
    lumo_result = call_gemini(question, context)
    
    # Construire la réponse
    response = {
        "success": lumo_result["success"],
        "question": question,
        "lumo": {
            "response": lumo_result.get("response"),
            "model": lumo_result.get("model"),
            "error": lumo_result.get("error")
        },
        "timestamp": datetime.now().isoformat(),
        "note": "Avis de Lumo (Gemini) - Ludo décide"
    }
    
    if lumo_result["success"]:
        logger.info(f"✅ Trio Consult OK - Réponse Lumo reçue")
    else:
        logger.warning(f"⚠️ Trio Consult FAILED: {lumo_result.get('error')}")
    
    return response

# =============================================================================
# ENREGISTREMENT DES ROUTES (Architecture V19 - server.register_route)
# =============================================================================

def register_trio_routes(server):
    """
    Enregistre les routes Trio sur le serveur V19.
    Utilise server.register_route() comme les autres modules (trello, agent, etc.)
    """
    server.register_route("GET", "/trio/status", handle_trio_status)
    server.register_route("POST", "/trio/consult", handle_trio_consult)
    
    logger.info("🤝 Routes Trio enregistrées: /trio/status (GET), /trio/consult (POST)")

