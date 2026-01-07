# axi_v19/core/server.py
"""
Serveur HTTP threadé V19 - Architecture Bunker
Remplace FastAPI par http.server natif (zéro dépendance nouvelle)

Plan Lumo V3 - Section 5: Serveur HTTP
+ SÉCURISATION API - 4 janvier 2026
+ AGENT SUPPORT - 7 janvier 2026 (headers, routes dynamiques)
"""

import json
import logging
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Any, Callable, Optional, Tuple
from urllib.parse import urlparse, parse_qs

from .config import settings, check_auth
from .database import db

logger = logging.getLogger("axi_v19.server")


class AxiRequestHandler(BaseHTTPRequestHandler):
    """
    Handler HTTP minimaliste et robuste V19.
    Gère les réponses JSON basiques pour les endpoints de santé et API.
    + Authentification pour endpoints sensibles.
    + Support headers et routes dynamiques pour Agent.
    """
    
    # Routes enregistrées dynamiquement
    routes_get: Dict[str, Callable] = {}
    routes_post: Dict[str, Callable] = {}
    # Routes avec patterns (regex)
    routes_get_patterns: list = []  # [(pattern, handler)]
    routes_post_patterns: list = []
    
    def do_GET(self):
        """Gère les requêtes GET."""
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        
        # === AUTHENTIFICATION ===
        headers_dict = {k: v for k, v in self.headers.items()}
        authorized, error_msg = check_auth(path, 'GET', query, headers_dict)
        
        if not authorized:
            self._send_json(401, {"error": error_msg, "code": 401})
            return
        
        # Routing exact
        if path in self.routes_get:
            try:
                handler = self.routes_get[path]
                result = self._call_handler(handler, query, None, headers_dict)
                self._handle_result(result)
            except Exception as e:
                logger.error(f"Erreur GET {path}: {e}")
                self._send_json(500, {"error": str(e)})
            return
        
        # Routing patterns (ex: /agent/result/{id})
        for pattern, handler in self.routes_get_patterns:
            match = pattern.match(path)
            if match:
                try:
                    path_params = match.groupdict()
                    result = self._call_handler(handler, query, None, headers_dict, path_params)
                    self._handle_result(result)
                except Exception as e:
                    logger.error(f"Erreur GET {path}: {e}")
                    self._send_json(500, {"error": str(e)})
                return
        
        # Routes système
        if path == '/health':
            self._handle_health()
        elif path == '/ready':
            self._handle_ready()
        elif path == '/status':
            self._handle_status()
        else:
            self.send_error(404, f"Endpoint non trouvé: {path}")
    
    def do_POST(self):
        """Gère les requêtes POST."""
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        
        # === AUTHENTIFICATION ===
        headers_dict = {k: v for k, v in self.headers.items()}
        authorized, error_msg = check_auth(path, 'POST', query, headers_dict)
        
        if not authorized:
            self._send_json(401, {"error": error_msg, "code": 401})
            return
        
        # Lire le body
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length else ''
        
        # Parser le body selon le Content-Type
        content_type = self.headers.get('Content-Type', '')
        
        try:
            if 'application/json' in content_type:
                data = json.loads(body) if body else {}
            elif 'application/x-www-form-urlencoded' in content_type:
                # Form data (URL encoded)
                from urllib.parse import parse_qs as parse_form
                parsed_data = parse_form(body)
                data = {k: v[0] if len(v) == 1 else v for k, v in parsed_data.items()}
            else:
                # Essayer JSON par défaut
                data = json.loads(body) if body else {}
        except (json.JSONDecodeError, Exception) as e:
            # Si ça échoue, essayer comme form data
            try:
                from urllib.parse import parse_qs as parse_form
                parsed_data = parse_form(body)
                data = {k: v[0] if len(v) == 1 else v for k, v in parsed_data.items()}
            except:
                self._send_json(400, {"error": "Données invalides"})
                return
        
        # Routing exact
        if path in self.routes_post:
            try:
                handler = self.routes_post[path]
                result = self._call_handler(handler, query, data, headers_dict)
                self._handle_result(result)
            except Exception as e:
                logger.error(f"Erreur POST {path}: {e}")
                self._send_json(500, {"error": str(e)})
            return
        
        # Routing patterns (ex: /agent/result/{id})
        for pattern, handler in self.routes_post_patterns:
            match = pattern.match(path)
            if match:
                try:
                    path_params = match.groupdict()
                    result = self._call_handler(handler, query, data, headers_dict, path_params)
                    self._handle_result(result)
                except Exception as e:
                    logger.error(f"Erreur POST {path}: {e}")
                    self._send_json(500, {"error": str(e)})
                return
        
        self.send_error(404, f"Endpoint POST non trouvé: {path}")
    
    def _call_handler(self, handler, query, body, headers, path_params=None):
        """Appelle un handler avec les bons arguments."""
        import inspect
        sig = inspect.signature(handler)
        params = sig.parameters
        
        kwargs = {}
        if 'query' in params:
            kwargs['query'] = query
        if 'body' in params:
            kwargs['body'] = body
        if 'headers' in params:
            kwargs['headers'] = headers
        if 'path_params' in params:
            kwargs['path_params'] = path_params
        
        # Si le handler n'a pas de params nommés, passer les args positionnels
        if not kwargs:
            if body is not None:
                return handler(query, body)
            return handler(query)
        
        return handler(**kwargs)
    
    def _handle_result(self, result):
        """Gère le résultat d'un handler (peut être tuple ou dict)."""
        if isinstance(result, tuple) and len(result) == 2:
            code, data = result
            self._send_json(code, data)
        else:
            self._send_json(200, result)
    
    def _handle_health(self):
        """Endpoint vital pour Railway."""
        self._send_json(200, {
            "status": "ok",
            "version": f"v{settings.version}",
            "secured": bool(settings.api_secret)
        })
    
    def _handle_ready(self):
        """Indique que le système est prêt (DB connectée, etc.)."""
        db_health = db.health_check()
        ready = db_health.get("status") == "connected"
        
        self._send_json(200 if ready else 503, {
            "ready": ready,
            "database": db_health.get("status"),
            "version": f"v{settings.version}",
            "secured": bool(settings.api_secret)
        })
    
    def _handle_status(self):
        """Status complet du système V19."""
        self._send_json(200, {
            "service": f"Axi ICI Dordogne V{settings.version}",
            "status": "ok",
            "environment": settings.environment,
            "secured": bool(settings.api_secret),
            "database": db.health_check(),
            "features": ["V19 Bunker", "Chat Interface", "Tavily Search", "Prospects", "Conversations", "Brain", "Auth", "Agent"],
            "public_endpoints": ["/", "/health", "/ready", "/status", "/memory", "/briefing", "/chat", "/trio", "/nouvelle-session", "/agent/status"],
            "protected_endpoints": ["/run-veille", "/run-veille-concurrence", "/v19/brain (POST)", "/agent/execute", "/agent/pending"],
            "endpoints": list(self.routes_get.keys()) + list(self.routes_post.keys()) + [
                "/health", "/ready", "/status"
            ]
        })
    
    def _send_json(self, code: int, data: Any):
        """Helper pour envoyer des réponses JSON ou HTML."""
        self.send_response(code)
        
        # Détecter si c'est du HTML (string commençant par <!DOCTYPE ou <html)
        if isinstance(data, str) and (data.strip().startswith('<!DOCTYPE') or data.strip().startswith('<html')):
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(data.encode('utf-8'))
        else:
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = json.dumps(data, ensure_ascii=False, default=str)
            self.wfile.write(response.encode('utf-8'))
    
    def log_message(self, format, *args):
        """Redirige les logs HTTP vers notre logger structuré."""
        # Filtrer les health checks pour réduire le bruit
        message = format % args
        if '/health' not in message:
            logger.debug(f"HTTP {self.client_address[0]} - {message}")


class ServerManager:
    """
    Gestionnaire du serveur HTTP threadé.
    Permet un démarrage/arrêt propre (graceful shutdown).
    """
    
    def __init__(self):
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
    
    def register_route(self, method: str, path: str, handler: Callable):
        """
        Enregistre une route dynamiquement.
        Supporte les patterns avec {param} (ex: /agent/result/{id})
        
        Args:
            method: 'GET' ou 'POST'
            path: Chemin de l'endpoint (ex: '/api/prospects' ou '/agent/result/{id}')
            handler: Fonction qui traite la requête
        """
        # Détecter si c'est un pattern
        if '{' in path:
            # Convertir /agent/result/{id} en regex /agent/result/(?P<id>[^/]+)
            pattern_str = re.sub(r'\{(\w+)\}', r'(?P<\1>[^/]+)', path)
            pattern = re.compile(f'^{pattern_str}$')
            
            if method.upper() == 'GET':
                AxiRequestHandler.routes_get_patterns.append((pattern, handler))
                logger.info(f"📍 Route GET pattern {path} enregistrée")
            elif method.upper() == 'POST':
                AxiRequestHandler.routes_post_patterns.append((pattern, handler))
                logger.info(f"📍 Route POST pattern {path} enregistrée")
        else:
            if method.upper() == 'GET':
                AxiRequestHandler.routes_get[path] = handler
                logger.info(f"📍 Route GET {path} enregistrée")
            elif method.upper() == 'POST':
                AxiRequestHandler.routes_post[path] = handler
                logger.info(f"📍 Route POST {path} enregistrée")
            else:
                raise ValueError(f"Méthode HTTP non supportée: {method}")
    
    def start(self):
        """Démarre le serveur HTTP dans un thread séparé."""
        if self._running:
            logger.warning("Serveur déjà en cours d'exécution")
            return
        
        try:
            self._server = ThreadingHTTPServer(
                (settings.http_host, settings.http_port),
                AxiRequestHandler
            )
            self._thread = threading.Thread(target=self._serve, daemon=True)
            self._thread.start()
            self._running = True
            
            # Log sécurité
            if settings.api_secret:
                logger.info(f"🔒 Serveur HTTP V19 démarré sur {settings.http_host}:{settings.http_port} (SÉCURISÉ)")
            else:
                logger.warning(f"⚠️ Serveur HTTP V19 démarré sur {settings.http_host}:{settings.http_port} (NON SÉCURISÉ - définir AXI_API_SECRET)")
                
        except Exception as e:
            logger.critical(f"❌ Échec démarrage serveur: {e}")
            raise
    
    def _serve(self):
        """Boucle de service (exécutée dans un thread)."""
        if self._server:
            self._server.serve_forever()
    
    def stop(self):
        """Arrête proprement le serveur HTTP."""
        if not self._running:
            return
        
        logger.info("🛑 Arrêt du serveur HTTP...")
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        
        self._running = False
        logger.info("✅ Serveur HTTP arrêté")
    
    @property
    def is_running(self) -> bool:
        return self._running


# Instance globale
server = ServerManager()


if __name__ == "__main__":
    # Test standalone
    print("=== Test Serveur V19 ===")
    
    # Route de test
    def test_handler(query):
        return {"test": "ok", "query": query}
    
    server.register_route('GET', '/test', test_handler)
    server.start()
    
    print(f"Serveur démarré sur port {settings.http_port}")
    print(f"Sécurisé: {bool(settings.api_secret)}")
    print("Ctrl+C pour arrêter")
    
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
