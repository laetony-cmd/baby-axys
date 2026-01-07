#!/usr/bin/env python3
#!/usr/bin/env python3
# axi_v19/main.py
"""
AXI V19 - Point d'entrée principal
Architecture Bunker - "Je ne lâche pas." 💪

Plan Lumo V3 - Section 6: Orchestration et Démarrage
Correction imports: 4 janvier 2026
"""

# =============================================================================
# PREMIER CRI - Logs AVANT tout import (recommandation Lumo)
# =============================================================================
import sys
import os
from datetime import datetime

print("=" * 60, flush=True)
print(f"🚀 [V19] KERNEL INITIALIZING - {datetime.now().isoformat()}", flush=True)
print(f"🐍 [V19] Python: {sys.version.split()[0]}", flush=True)
print(f"📁 [V19] CWD: {os.getcwd()}", flush=True)
print(f"📦 [V19] __name__: {__name__}", flush=True)
print(f"📦 [V19] __package__: {__package__}", flush=True)
print("=" * 60, flush=True)

# =============================================================================
# VÉRIFICATION DES DÉPENDANCES CRITIQUES (Guard-fou Lumo)
# =============================================================================
print("[V19] Checking critical dependencies...", flush=True)

REQUIRED_VERSIONS = {
    "psycopg2": "2.9",
    "apscheduler": "3.",
    "anthropic": "0.",
}

def check_dependency(module_name, expected_prefix):
    """Vérifie qu'une dépendance est présente et compatible."""
    try:
        mod = __import__(module_name)
        version = getattr(mod, '__version__', 'unknown')
        if version.startswith(expected_prefix):
            print(f"  ✅ {module_name}: {version}", flush=True)
            return True
        else:
            print(f"  ⚠️ {module_name}: {version} (expected {expected_prefix}*)", flush=True)
            return True  # Continue anyway, just warn
    except ImportError as e:
        print(f"  ❌ {module_name}: MISSING - {e}", flush=True)
        return False

deps_ok = True
for mod, prefix in REQUIRED_VERSIONS.items():
    if not check_dependency(mod, prefix):
        deps_ok = False

if not deps_ok:
    print("❌ [V19] Critical dependencies missing - ABORT", flush=True)
    sys.exit(1)

print("[V19] Dependencies OK ✅", flush=True)

# =============================================================================
# IMPORTS V19 - Syntaxe relative (fix du bug)
# =============================================================================
print("[V19] Loading core modules...", flush=True)

try:
    from .core.config import settings, validate_dependencies
    print("  ✅ core.config loaded", flush=True)
except ImportError as e:
    print(f"  ❌ core.config FAILED: {e}", flush=True)
    sys.exit(1)

try:
    from .core.database import db
    print("  ✅ core.database loaded", flush=True)
except ImportError as e:
    print(f"  ❌ core.database FAILED: {e}", flush=True)
    sys.exit(1)

try:
    from .core.server import server
    print("  ✅ core.server loaded", flush=True)
except ImportError as e:
    print(f"  ❌ core.server FAILED: {e}", flush=True)
    sys.exit(1)

print("[V19] Core modules loaded ✅", flush=True)

# Import module legacy (endpoints V18 compatibles)
try:
    from .modules.legacy import register_legacy_routes
    print("  ✅ modules.legacy loaded", flush=True)
    LEGACY_OK = True
except ImportError as e:
    print(f"  ⚠️ modules.legacy not available: {e}", flush=True)
    LEGACY_OK = False

# Import module veille (DPE + Concurrence)
try:
    from .modules.veille import register_veille_routes
    print("  ✅ modules.veille loaded", flush=True)
    VEILLE_OK = True
except ImportError as e:
    print(f"  ⚠️ modules.veille not available: {e}", flush=True)
    VEILLE_OK = False

# Import module interface (Chat avec Tavily corrigé)
try:
    from .modules.interface import register_interface_routes
    print("  ✅ modules.interface loaded (Chat + Tavily)", flush=True)
    INTERFACE_OK = True
except ImportError as e:
    print(f"  ⚠️ modules.interface not available: {e}", flush=True)
    INTERFACE_OK = False

# Import module agent (Pilotage distant MS-01)
try:
    from .modules.agent import register_agent_routes
    print("  ✅ modules.agent loaded (Remote Control)", flush=True)
    AGENT_OK = True
except ImportError as e:
    print(f"  ⚠️ modules.agent not available: {e}", flush=True)
    AGENT_OK = False

# Import module SweepBright (Webhooks + API)
try:
    from .modules.sweepbright import register_sweepbright_routes
    print("  ✅ modules.sweepbright loaded (Webhooks + API)", flush=True)
    SWEEPBRIGHT_OK = True
except ImportError as e:
    print(f"  ⚠️ modules.sweepbright not available: {e}", flush=True)
    SWEEPBRIGHT_OK = False

# Import module Trello (Sync + Matching) - V19.4
try:
    from .modules.trello import register_routes as register_trello_routes
    print("  ✅ modules.trello loaded (Sync + Matching)", flush=True)
    TRELLO_OK = True
except ImportError as e:
    print(f"  ⚠️ modules.trello not available: {e}", flush=True)
    TRELLO_OK = False

# =============================================================================
# IMPORTS STANDARDS
# =============================================================================
import signal
import logging
import threading
import time

# Import conditionnel APScheduler
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    import pytz
    SCHEDULER_OK = True
    TZ_PARIS = pytz.timezone('Europe/Paris')
    print("  ✅ APScheduler loaded", flush=True)
except ImportError:
    SCHEDULER_OK = False
    TZ_PARIS = None
    print("  ⚠️ APScheduler not available", flush=True)

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("axi_v19.main")

print("[V19] All imports complete ✅", flush=True)
print("=" * 60, flush=True)


# =============================================================================
# CLASSE PRINCIPALE
# =============================================================================

class AxiV19:
    """
    Orchestrateur principal V19.
    Gère le cycle de vie complet: démarrage, scheduler, shutdown.
    """
    
    def __init__(self):
        self._scheduler = None
        self._shutdown_event = threading.Event()
        self._startup_time = None
    
    def _setup_signal_handlers(self):
        """
        Configure les handlers pour SIGTERM et SIGINT.
        Crucial pour le graceful shutdown sur Railway.
        """
        def signal_handler(signum, frame):
            sig_name = signal.Signals(signum).name
            logger.info(f"📡 Signal {sig_name} reçu - Arrêt gracieux...")
            self._shutdown_event.set()
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        logger.info("🔒 Handlers de signaux configurés (SIGTERM, SIGINT)")
    
    def _init_scheduler(self):
        """Initialise APScheduler pour les tâches planifiées."""
        if not SCHEDULER_OK:
            logger.warning("⚠️ APScheduler non disponible - Cron désactivé")
            return
        
        self._scheduler = BackgroundScheduler(timezone=TZ_PARIS)
        
        # Job de heartbeat (toutes les 5 minutes)
        self._scheduler.add_job(
            self._heartbeat,
            'interval',
            minutes=5,
            id='heartbeat_v19',
            name='V19 Heartbeat'
        )
        
        # =================================================================
        # VEILLES QUOTIDIENNES - Ajouté le 5 janvier 2026
        # =================================================================
        if VEILLE_OK:
            from .modules.veille import run_veille_dpe, run_veille_concurrence
            
            # Veille Concurrence à 7h00 Paris
            self._scheduler.add_job(
                lambda: run_veille_concurrence(db),
                'cron',
                hour=7,
                minute=0,
                id='veille_concurrence_7h',
                name='Veille Concurrence 7h Paris'
            )
            logger.info("📡 Job Veille Concurrence programmé: 7h00 Paris")
            
            # Veille DPE à 8h00 Paris
            self._scheduler.add_job(
                lambda: run_veille_dpe(db),
                'cron',
                hour=8,
                minute=0,
                id='veille_dpe_8h',
                name='Veille DPE 8h Paris'
            )
            logger.info("🏠 Job Veille DPE programmé: 8h00 Paris")
        else:
            logger.warning("⚠️ Module veille non disponible - Crons veille désactivés")
        
        self._scheduler.start()
        logger.info("⏰ Scheduler V19 démarré")
    
    def _heartbeat(self):
        """Job de heartbeat pour monitoring."""
        uptime = (datetime.now() - self._startup_time).total_seconds() if self._startup_time else 0
        logger.info(f"💓 V19 Heartbeat - Uptime: {uptime:.0f}s - DB: {db.is_connected}")
    
    def _register_routes(self):
        """Enregistre les routes API V19."""
        
        # API Prospects
        def get_prospects(query):
            if not db.is_connected:
                return {"error": "DB non connectée", "prospects": []}
            
            status_filter = query.get('status', ['new'])[0] if query else 'new'
            try:
                prospects = db.execute_safe(
                    "SELECT * FROM v19_prospects WHERE status = %s ORDER BY created_at DESC LIMIT 50",
                    (status_filter,),
                    table_name="v19_prospects"
                )
                return {"count": len(prospects), "prospects": prospects}
            except Exception as e:
                return {"error": str(e), "prospects": []}
        
        # API Brain (mémoire)
        def get_brain(query):
            if not db.is_connected:
                return {"error": "DB non connectée", "brain": []}
            
            category = query.get('category', [None])[0] if query else None
            try:
                if category:
                    brain = db.execute_safe(
                        "SELECT * FROM v19_brain WHERE category = %s ORDER BY updated_at DESC",
                        (category,),
                        table_name="v19_brain"
                    )
                else:
                    brain = db.execute_safe(
                        "SELECT * FROM v19_brain ORDER BY category, key",
                        table_name="v19_brain"
                    )
                return {"count": len(brain), "brain": brain}
            except Exception as e:
                return {"error": str(e), "brain": []}
        
        def post_brain(data):
            if not db.is_connected:
                return {"error": "DB non connectée", "success": False}
            
            category = data.get('category')
            key = data.get('key')
            value = data.get('value')
            
            if not all([category, key]):
                return {"error": "category et key requis", "success": False}
            
            try:
                db.execute_safe(
                    """
                    INSERT INTO v19_brain (category, key, value, metadata)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (category, key) DO UPDATE SET
                        value = EXCLUDED.value,
                        updated_at = NOW()
                    """,
                    (category, key, value, data.get('metadata', '{}')),
                    table_name="v19_brain"
                )
                return {"success": True, "category": category, "key": key}
            except Exception as e:
                return {"error": str(e), "success": False}
        
        # API Veille Results
        def get_veille_results(query):
            if not db.is_connected:
                return {"error": "DB non connectée", "results": []}
            
            try:
                results = db.execute_safe(
                    """
                    SELECT * FROM v19_veille_results 
                    ORDER BY run_date DESC LIMIT 20
                    """,
                    table_name="v19_veille_results"
                )
                return {"count": len(results), "results": results}
            except Exception as e:
                return {"error": str(e), "results": []}
        
        # Enregistrement des routes API
        server.register_route('GET', '/v19/prospects', get_prospects)
        server.register_route('GET', '/v19/brain', get_brain)
        server.register_route('POST', '/v19/brain', post_brain)
        server.register_route('GET', '/v19/veille', get_veille_results)
        
        logger.info("📍 Routes API V19 enregistrées")
        
        # Routes Interface (Chat avec Tavily corrigé) - PRIORITÉ
        if INTERFACE_OK:
            register_interface_routes(server)
            logger.info("✅ Interface Chat + Tavily activée")
        else:
            # Fallback: route racine basique si interface non disponible
            def get_root(query):
                return {
                    "service": f"Axi ICI Dordogne V{settings.version}",
                    "status": "ok",
                    "message": "Je ne lâche pas. 💪"
                }
            server.register_route('GET', '/', get_root)
            logger.warning("⚠️ Interface non disponible - Mode API only")
        
        # Routes legacy (compatibilité V18)
        if LEGACY_OK:
            register_legacy_routes(server)
        else:
            logger.warning("⚠️ Routes legacy non disponibles")
        
        # Routes veille (DPE + Concurrence)
        if VEILLE_OK:
            register_veille_routes(server)
        else:
            logger.warning("⚠️ Routes veille non disponibles")
        
        # Routes agent (Pilotage distant MS-01)
        if AGENT_OK:
            register_agent_routes(server)
            logger.info("✅ Routes Agent activées (pilotage MS-01)")
        else:
            logger.warning("⚠️ Routes agent non disponibles")
        
        # Routes SweepBright (Webhooks + API)
        if SWEEPBRIGHT_OK:
            register_sweepbright_routes(server, db)
            logger.info("✅ Routes SweepBright activées (webhooks + biens)")
        else:
            logger.warning("⚠️ Routes SweepBright non disponibles")
        
        # Routes Trello (Sync + Matching) - V19.4
        if TRELLO_OK:
            register_trello_routes(server.app, db)
            logger.info("✅ Routes Trello activées (Sync + Matching)")
        else:
            logger.warning("⚠️ Routes Trello non disponibles")
    
    def start(self):
        """Démarre l'application V19 complète."""
        self._startup_time = datetime.now()
        
        logger.info("=" * 60)
        logger.info(f"🚀 DÉMARRAGE AXI V19 - {settings.version}")
        logger.info(f"   Environment: {settings.environment}")
        logger.info(f"   Port: {settings.http_port}")
        logger.info("=" * 60)
        
        # 1. Validation des dépendances (disjoncteur)
        if not validate_dependencies():
            logger.critical("❌ Dépendances invalides - Arrêt")
            sys.exit(1)
        
        # 2. Validation configuration
        if not settings.validate():
            if settings.is_production():
                logger.critical("❌ Configuration invalide en production - Arrêt")
                sys.exit(1)
            else:
                logger.warning("⚠️ Configuration incomplète - Mode développement")
        
        # 3. Setup signal handlers
        self._setup_signal_handlers()
        
        # 4. Initialisation base de données
        if db.is_connected:
            logger.info("✅ Connexion PostgreSQL établie")
            if db.init_v19_tables():
                logger.info("✅ Tables V19 prêtes")
        else:
            logger.warning("⚠️ Base de données non connectée - Mode dégradé")
        
        # 5. Enregistrement des routes
        self._register_routes()
        
        # 6. Démarrage serveur HTTP
        server.start()
        
        # 7. Démarrage scheduler
        self._init_scheduler()
        
        # 8. Message de bienvenue
        logger.info("=" * 60)
        logger.info("🎉 AXI V19.4 est opérationnel et en attente")
        logger.info(f"   Endpoints: /health, /status, /v19/*, /agent/*, /sweepbright/*, /trello/*")
        logger.info("   \"Je ne lâche pas.\" 💪")
        logger.info("=" * 60)
        
        # 9. Boucle principale (attend le signal d'arrêt)
        self._main_loop()
    
    def _main_loop(self):
        """Boucle principale - attend le signal d'arrêt."""
        try:
            while not self._shutdown_event.is_set():
                self._shutdown_event.wait(timeout=1.0)
        except KeyboardInterrupt:
            logger.info("⌨️ Interruption clavier détectée")
        finally:
            self.shutdown()
    
    def shutdown(self):
        """Arrêt gracieux de tous les composants."""
        logger.info("🛑 Arrêt gracieux de V19...")
        
        # 1. Arrêter le scheduler
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=True)
            logger.info("✅ Scheduler arrêté")
        
        # 2. Arrêter le serveur HTTP
        server.stop()
        
        # 3. Fermer les connexions DB
        db.close()
        
        uptime = (datetime.now() - self._startup_time).total_seconds() if self._startup_time else 0
        logger.info(f"👋 AXI V19 arrêté proprement (uptime: {uptime:.0f}s)")


def main():
    """Point d'entrée principal."""
    print("[V19] Starting main application...", flush=True)
    app = AxiV19()
    app.start()


if __name__ == "__main__":
    main()
