# axi_v19/modules/agent.py
"""
Module Agent - Pilotage distant du MS-01 (AXIS Station)
Permet à Claude/Axis d'exécuter des commandes PowerShell sur le PC de Ludo

Endpoints:
- POST /agent/execute : Envoyer une commande (appelé par Claude)
- GET /agent/pending : Récupérer les commandes en attente (appelé par l'agent Windows)
- POST /agent/result/{id} : Renvoyer le résultat (appelé par l'agent Windows)
"""

import os
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional
from threading import Lock

logger = logging.getLogger("axi_v19.agent")

# =============================================================================
# CONFIGURATION
# =============================================================================

AGENT_TOKEN = os.environ.get("AGENT_TOKEN", "ici-dordogne-2026")
COMMAND_TIMEOUT = 300  # 5 minutes max pour une commande

# =============================================================================
# STORAGE EN MÉMOIRE (simple pour commencer)
# =============================================================================

class AgentStorage:
    """Stockage thread-safe des commandes et résultats."""
    
    def __init__(self):
        self._lock = Lock()
        self._commands: Dict[str, dict] = {}  # id -> command
        self._results: Dict[str, dict] = {}   # id -> result
        self._counter = 0
    
    def add_command(self, command: str, description: str = "") -> str:
        """Ajoute une commande et retourne son ID."""
        with self._lock:
            self._counter += 1
            cmd_id = f"cmd_{int(time.time())}_{self._counter}"
            self._commands[cmd_id] = {
                "id": cmd_id,
                "command": command,
                "description": description,
                "created_at": datetime.now().isoformat(),
                "status": "pending"
            }
            logger.info(f"📤 Commande ajoutée: {cmd_id} - {command[:50]}...")
            return cmd_id
    
    def get_pending(self) -> List[dict]:
        """Récupère les commandes en attente et les marque comme 'sent'."""
        with self._lock:
            pending = []
            for cmd_id, cmd in self._commands.items():
                if cmd["status"] == "pending":
                    cmd["status"] = "sent"
                    cmd["sent_at"] = datetime.now().isoformat()
                    pending.append(cmd.copy())
            return pending
    
    def set_result(self, cmd_id: str, result: str, success: bool = True) -> bool:
        """Enregistre le résultat d'une commande."""
        with self._lock:
            if cmd_id not in self._commands:
                return False
            
            self._commands[cmd_id]["status"] = "completed" if success else "failed"
            self._commands[cmd_id]["completed_at"] = datetime.now().isoformat()
            self._results[cmd_id] = {
                "id": cmd_id,
                "result": result,
                "success": success,
                "completed_at": datetime.now().isoformat()
            }
            logger.info(f"📥 Résultat reçu: {cmd_id} - {'OK' if success else 'FAILED'}")
            return True
    
    def get_result(self, cmd_id: str, timeout: int = 60) -> Optional[dict]:
        """Attend et récupère le résultat d'une commande."""
        start = time.time()
        while time.time() - start < timeout:
            with self._lock:
                if cmd_id in self._results:
                    return self._results[cmd_id]
            time.sleep(0.5)
        return None
    
    def cleanup_old(self, max_age_seconds: int = 3600):
        """Nettoie les vieilles commandes."""
        with self._lock:
            now = time.time()
            to_delete = []
            for cmd_id, cmd in self._commands.items():
                created = datetime.fromisoformat(cmd["created_at"]).timestamp()
                if now - created > max_age_seconds:
                    to_delete.append(cmd_id)
            for cmd_id in to_delete:
                del self._commands[cmd_id]
                if cmd_id in self._results:
                    del self._results[cmd_id]

# Instance globale
storage = AgentStorage()

# =============================================================================
# HANDLERS
# =============================================================================

def verify_token(headers: dict) -> bool:
    """Vérifie le token d'authentification."""
    token = headers.get("X-Agent-Token", "")
    return token == AGENT_TOKEN

def handle_execute(query: dict, body: dict, headers: dict) -> tuple:
    """POST /agent/execute - Envoyer une commande (appelé par Claude)."""
    if not verify_token(headers):
        return 401, {"error": "Unauthorized - Token invalide ou manquant", "code": 401}
    
    command = body.get("command", "")
    description = body.get("description", "")
    wait = body.get("wait", True)  # Attendre le résultat par défaut
    timeout = body.get("timeout", 30)
    
    if not command:
        return 400, {"error": "Commande manquante", "code": 400}
    
    cmd_id = storage.add_command(command, description)
    
    if wait:
        result = storage.get_result(cmd_id, timeout=timeout)
        if result:
            return 200, {
                "id": cmd_id,
                "command": command,
                "result": result["result"],
                "success": result["success"]
            }
        else:
            return 408, {
                "id": cmd_id,
                "error": "Timeout - L'agent n'a pas répondu",
                "code": 408
            }
    else:
        return 202, {
            "id": cmd_id,
            "command": command,
            "status": "queued",
            "message": "Commande en file d'attente"
        }

def handle_pending(query: dict, headers: dict) -> tuple:
    """GET /agent/pending - Récupérer les commandes en attente."""
    if not verify_token(headers):
        return 401, {"error": "Unauthorized - Token invalide ou manquant", "code": 401}
    
    pending = storage.get_pending()
    return 200, {"commands": pending, "count": len(pending)}

def handle_result(query: dict, body: dict, headers: dict, cmd_id: str) -> tuple:
    """POST /agent/result/{id} - Renvoyer le résultat."""
    if not verify_token(headers):
        return 401, {"error": "Unauthorized - Token invalide ou manquant", "code": 401}
    
    result = body.get("result", "")
    success = body.get("success", True)
    
    if storage.set_result(cmd_id, result, success):
        return 200, {"status": "ok", "id": cmd_id}
    else:
        return 404, {"error": f"Commande {cmd_id} non trouvée", "code": 404}

def handle_status(query: dict, headers: dict) -> tuple:
    """GET /agent/status - Status de l'agent."""
    return 200, {
        "service": "AXIS Agent",
        "version": "1.0",
        "token_configured": bool(AGENT_TOKEN),
        "pending_commands": len([c for c in storage._commands.values() if c["status"] == "pending"]),
        "total_commands": len(storage._commands)
    }

# =============================================================================
# ENREGISTREMENT DES ROUTES
# =============================================================================

def register_agent_routes(server):
    """Enregistre les routes de l'agent sur le serveur."""
    logger.info("📡 Enregistrement des routes Agent...")
    
    # GET /agent/pending
    def pending_handler(query, headers=None):
        return handle_pending(query, headers or {})
    server.register_route("GET", "/agent/pending", pending_handler)
    
    # GET /agent/status
    def status_handler(query, headers=None):
        return handle_status(query, headers or {})
    server.register_route("GET", "/agent/status", status_handler)
    
    # POST /agent/execute
    def execute_handler(query, body=None, headers=None):
        return handle_execute(query, body or {}, headers or {})
    server.register_route("POST", "/agent/execute", execute_handler)
    
    # POST /agent/result/{id} - Route dynamique
    def result_handler(query, body=None, headers=None, path_params=None):
        cmd_id = path_params.get("id", "") if path_params else query.get("id", "")
        return handle_result(query, body or {}, headers or {}, cmd_id)
    server.register_route("POST", "/agent/result", result_handler)
    
    logger.info("✅ Routes Agent enregistrées: /agent/pending, /agent/execute, /agent/result, /agent/status")
