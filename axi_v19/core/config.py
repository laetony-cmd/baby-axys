# axi_v19/core/config.py
"""
Configuration centralisée V19 - Architecture Bunker
Première ligne de défense contre les erreurs d'environnement.

Plan Lumo V3 - Section 2: Fondations Architecturales
+ SÉCURISATION API - 4 janvier 2026
"""

import os
import sys
import logging
from dataclasses import dataclass, field
from typing import Optional, List

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("axi_v19.config")


# =============================================================================
# VALIDATION DES DÉPENDANCES (Disjoncteur de sécurité)
# =============================================================================

REQUIRED_DEPENDENCIES = {
    "psycopg2": "psycopg2-binary",  # PostgreSQL
    "apscheduler": "apscheduler",    # Scheduler
    "anthropic": "anthropic",        # Claude API
}

FORBIDDEN_NEW_DEPENDENCIES = [
    "fastapi", "uvicorn", "sqlalchemy", "pydantic",  # Interdits par Plan Lumo
    "flask", "django", "aiohttp",
]


def validate_dependencies() -> bool:
    """
    Valide que toutes les dépendances requises sont présentes
    et qu'aucune nouvelle dépendance interdite n'a été ajoutée.
    
    Retourne True si OK, False + log critique sinon.
    """
    all_ok = True
    
    # Vérifier les dépendances requises
    for module_name, package_name in REQUIRED_DEPENDENCIES.items():
        try:
            __import__(module_name)
            logger.info(f"✅ Dépendance OK: {package_name}")
        except ImportError:
            logger.critical(f"❌ DÉPENDANCE MANQUANTE: {package_name}")
            all_ok = False
    
    # Vérifier qu'aucune dépendance interdite n'est présente
    for forbidden in FORBIDDEN_NEW_DEPENDENCIES:
        try:
            __import__(forbidden)
            logger.warning(f"⚠️ Dépendance interdite détectée: {forbidden} (toléré mais non utilisé)")
        except ImportError:
            pass  # C'est normal qu'elle ne soit pas là
    
    if all_ok:
        logger.info("🔒 Validation des dépendances: PASS")
    else:
        logger.critical("🚨 Validation des dépendances: FAIL - Arrêt du système")
        
    return all_ok


# =============================================================================
# CONFIGURATION CENTRALISÉE
# =============================================================================

@dataclass
class Settings:
    """
    Configuration immutable du système V19.
    Chargée une seule fois au démarrage depuis les variables d'environnement.
    """
    
    # === Base de données ===
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", ""))
    db_pool_min: int = 2
    db_pool_max: int = 10
    
    # === Serveur HTTP ===
    http_port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    http_host: str = "0.0.0.0"
    
    # === SÉCURITÉ API ===
    api_secret: str = field(default_factory=lambda: os.getenv("AXI_API_SECRET", ""))
    
    # === APIs externes ===
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    
    # === Email (notifications) ===
    gmail_user: str = field(default_factory=lambda: os.getenv("GMAIL_USER", "u5050786429@gmail.com"))
    gmail_app_password: str = field(default_factory=lambda: os.getenv("GMAIL_APP_PASSWORD", "izemquwmmqjdasrk"))
    email_to: str = field(default_factory=lambda: os.getenv("EMAIL_TO", "agence@icidordogne.fr"))
    email_cc: str = "laetony@gmail.com"  # TOUJOURS en copie - JAMAIS modifiable
    
    # === ICI Dordogne ===
    codes_postaux_vergt: List[str] = field(default_factory=lambda: [
        "24380", "24110", "24140", "24520", "24330", "24750"
    ])
    codes_postaux_bugue: List[str] = field(default_factory=lambda: [
        "24260", "24480", "24150", "24510", "24220", "24620"
    ])
    
    # === Métadonnées V19 ===
    version: str = "19.2.0"  # Bump version pour sécurité
    environment: str = field(default_factory=lambda: os.getenv("RAILWAY_ENVIRONMENT", "development"))
    
    def __post_init__(self):
        """Validation post-initialisation."""
        if not self.database_url:
            logger.warning("⚠️ DATABASE_URL non définie - mode dégradé")
        if not self.anthropic_api_key:
            logger.warning("⚠️ ANTHROPIC_API_KEY non définie - chat désactivé")
        if not self.api_secret:
            logger.warning("⚠️ AXI_API_SECRET non définie - endpoints sensibles non protégés!")
    
    @property
    def all_codes_postaux(self) -> List[str]:
        """Tous les codes postaux surveillés."""
        return self.codes_postaux_vergt + self.codes_postaux_bugue
    
    def is_production(self) -> bool:
        """Vérifie si on est en production Railway."""
        return self.environment == "production"
    
    def validate(self) -> bool:
        """Valide la configuration critique."""
        errors = []
        
        if self.is_production():
            if not self.database_url:
                errors.append("DATABASE_URL obligatoire en production")
            if not self.api_secret:
                errors.append("AXI_API_SECRET obligatoire en production")
        
        if errors:
            for e in errors:
                logger.critical(f"❌ Config invalide: {e}")
            return False
        
        logger.info(f"✅ Configuration V19 validée ({self.environment})")
        return True


# Instance globale singleton
settings = Settings()


# =============================================================================
# AUTHENTIFICATION API
# =============================================================================

# Endpoints qui NE NÉCESSITENT PAS d'authentification (publics)
PUBLIC_ENDPOINTS = [
    "/",
    "/health",
    "/ready", 
    "/status",
    "/memory",
    "/briefing",
    "/chat",           # Interface chat (V19.2)
    "/nouvelle-session", # Reset session (V19.2)
    "/trio",           # Mode trio (V19.2)
    "/test-veille",    # Test DPE sans email (V19.2 patch)
    "/test-veille-concurrence",  # Test concurrence sans email
    "/audit-scrapers",           # Audit complet scrapers (V19.2)
    "/diagnose-all",             # Diagnostic URLs détaillé
    "/agent/pending",    # Agent MS-01 (auth propre via X-Agent-Token)
    "/agent/execute",    # Agent MS-01 (auth propre via X-Agent-Token)
    "/agent/result",     # Agent MS-01 (auth propre via X-Agent-Token)
    "/agent/status",     # Agent MS-01 status
    "/webhook/sweepbright",  # Webhook SweepBright (V19.3)
    "/sweepbright/biens",    # API biens SweepBright (V19.3)
    "/trello/status",        # Status module Trello (V19.4)
    "/trello/sync",          # Sync Trello -> v19_biens (V19.4)
    "/trello/match",         # Matching Biens -> Prospects (V19.4)
    "/trello/full",          # Sync + Match complet (V19.4)
    "/chat-proxy",           # Chat sites vitrines (V19.5 - Lormont, Manzac)
    "/contact",              # Contact sites vitrines (V19.5)
    "/chat-vitrine",         # Chat Vitrine V2 - Template permanent (V19.6)
    "/trio/status",          # Status Trio Axis/Lumo (V19.2.1)
    "/trio/consult",         # Consultation Axis/Lumo (V19.2.1)
]

# Endpoints qui NÉCESSITENT une authentification
PROTECTED_ENDPOINTS = [
    "/run-veille",
    "/run-veille-concurrence",
    "/v19/brain",  # POST seulement, GET est public
]


def check_auth(path: str, method: str, query: dict, headers: dict) -> tuple:
    """
    Vérifie l'authentification pour un endpoint.
    
    Args:
        path: Chemin de l'endpoint
        method: GET, POST, etc.
        query: Paramètres de requête
        headers: Headers HTTP
    
    Returns:
        (authorized: bool, error_message: str or None)
    """
    # Endpoints publics - toujours autorisés
    if path in PUBLIC_ENDPOINTS:
        return True, None
    
    # Routes agent (patterns) - authentification gérée par le module agent
    if path.startswith("/agent/"):
        return True, None
    
    # Routes SweepBright (patterns) - publiques
    if path.startswith("/sweepbright/") or path.startswith("/webhook/"):
        return True, None
    
    # GET sur /v19/brain est public (lecture mémoire)
    if path == "/v19/brain" and method == "GET":
        return True, None
    
    # Si pas de secret configuré, on laisse passer (dev mode)
    if not settings.api_secret:
        logger.warning(f"⚠️ Accès non authentifié à {path} (AXI_API_SECRET non configuré)")
        return True, None
    
    # Vérifier le token dans query params ou headers
    token = None
    
    # Option 1: Query param ?token=xxx
    if 'token' in query:
        token = query['token'][0] if isinstance(query['token'], list) else query['token']
    
    # Option 2: Header Authorization: Bearer xxx
    auth_header = headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
    
    # Option 3: Header X-API-Key: xxx
    if not token:
        token = headers.get('X-API-Key', '')
    
    # Vérification
    if token == settings.api_secret:
        return True, None
    
    # Non autorisé
    logger.warning(f"🚫 Accès refusé à {path} - token invalide ou manquant")
    return False, "Unauthorized - Token invalide ou manquant"


# =============================================================================
# TABLES V19 (Préfixées pour isolation)
# =============================================================================

V19_TABLES = {
    "prospects": "v19_prospects",
    "conversations": "v19_conversations",
    "veille_results": "v19_veille_results",
    "brain": "v19_brain",
}

# Liste blanche pour validation SQL (sécurité injection)
ALLOWED_TABLE_PATTERN = r'^v19_[a-z_]+$'


if __name__ == "__main__":
    # Test standalone
    print("=== Test Configuration V19 ===")
    validate_dependencies()
    print(f"Version: {settings.version}")
    print(f"Environment: {settings.environment}")
    print(f"Port HTTP: {settings.http_port}")
    print(f"API Secret: {'✅ Configuré' if settings.api_secret else '❌ Non configuré'}")
    print(f"Codes postaux: {len(settings.all_codes_postaux)}")
    settings.validate()


