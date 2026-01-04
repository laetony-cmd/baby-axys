#!/usr/bin/env python3
# axi_v19/main.py
"""
AXI V19 - Point d'entrée principal
Architecture Bunker - "Je ne lâche pas." 💪

Plan Lumo V3 - Section 6: Orchestration et Démarrage
"""

import sys
import signal
import logging
import threading
import time
from datetime import datetime

# Import conditionnel APScheduler
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    import pytz
    SCHEDULER_OK = True
except ImportError:
    SCHEDULER_OK = False

# Imports V19
from core.config import settings, validate_dependencies
from core.database import db
from core.server import server

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("axi_v19.main")

# Timezone Paris
TZ_PARIS = pytz.timezone('Europe/Paris') if SCHEDULER_OK else None


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
        
        # Placeholder pour futures veilles V19
        # self._scheduler.add_job(...)
        
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
        
        # Enregistrement des routes
        server.register_route('GET', '/v19/prospects', get_prospects)
        server.register_route('GET', '/v19/brain', get_brain)
        server.register_route('POST', '/v19/brain', post_brain)
        server.register_route('GET', '/v19/veille', get_veille_results)
        
        logger.info("📍 Routes API V19 enregistrées")
    
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
        logger.info("🎉 AXI V19 est opérationnel et en attente")
        logger.info(f"   Endpoints: /health, /ready, /status, /v19/*")
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
    app = AxiV19()
    app.start()


if __name__ == "__main__":
    main()
