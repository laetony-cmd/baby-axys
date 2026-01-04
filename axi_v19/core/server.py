# axi_v19/core/server.py
"""
Serveur HTTP threadé V19 - Architecture Bunker
Remplace FastAPI par http.server natif (zéro dépendance nouvelle)

Plan Lumo V3 - Section 5: Serveur HTTP
"""

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Any, Callable, Optional
from urllib.parse import urlparse, parse_qs

from .config import settings
from .database import db

logger = logging.getLogger("axi_v19.server")


class AxiRequestHandler(BaseHTTPRequestHandler):
    """
    Handler HTTP minimaliste et robuste V19.
    Gère les réponses JSON basiques pour les endpoints de santé et API.
    """
    
    # Routes enregistrées dynamiquement
    routes_get: Dict[str, Callable] = {}
    routes_post: Dict[str, Callable] = {}
    
    def do_GET(self):
        """Gère les requêtes GET."""
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        
        # Routing
        if path in self.routes_get:
            try:
                result = self.routes_get[path](query)
                self._send_json(200, result)
            except Exception as e:
                logger.error(f"Erreur GET {path}: {e}")
                self._send_json(500, {"error": str(e)})
        elif path == '/health':
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
        
        # Lire le body
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length else '{}'
        
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_json(400, {"error": "JSON invalide"})
            return
        
        # Routing
        if path in self.routes_post:
            try:
                result = self.routes_post[path](data)
                self._send_json(200, result)
            except Exception as e:
                logger.error(f"Erreur POST {path}: {e}")
                self._send_json(500, {"error": str(e)})
        else:
            self.send_error(404, f"Endpoint POST non trouvé: {path}")
    
    def _handle_health(self):
        """Endpoint vital pour Railway."""
        self._send_json(200, {
            "status": "ok",
            "version": f"v{settings.version}"
        })
    
    def _handle_ready(self):
        """Indique que le système est prêt (DB connectée, etc.)."""
        db_health = db.health_check()
        ready = db_health.get("status") == "connected"
        
        self._send_json(200 if ready else 503, {
            "ready": ready,
            "database": db_health.get("status"),
            "version": f"v{settings.version}"
        })
    
    def _handle_status(self):
        """Status complet du système V19."""
        self._send_json(200, {
            "service": f"Axi ICI Dordogne V{settings.version}",
            "status": "ok",
            "environment": settings.environment,
            "database": db.health_check(),
            "features": ["V19 Bunker", "Prospects", "Conversations", "Brain"],
            "endpoints": list(self.routes_get.keys()) + list(self.routes_post.keys()) + [
                "/health", "/ready", "/status"
            ]
        })
    
    def _send_json(self, code: int, data: Any):
        """Helper pour envoyer des réponses JSON standardisées."""
        self.send_response(code)
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
        
        Args:
            method: 'GET' ou 'POST'
            path: Chemin de l'endpoint (ex: '/api/prospects')
            handler: Fonction qui traite la requête
        """
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
            logger.info(f"🚀 Serveur HTTP V19 démarré sur {settings.http_host}:{settings.http_port}")
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
    print("Ctrl+C pour arrêter")
    
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
