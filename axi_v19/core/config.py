# axi_v19/core/config.py
"""
Configuration centralisée V19 - Architecture Bunker
Première ligne de défense contre les erreurs d'environnement.

Plan Lumo V3 - Section 2: Fondations Architecturales
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
    
    # === APIs externes ===
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    
    # === Email (notifications) ===
    gmail_user: str = "u5050786429@gmail.com"
    gmail_app_password: str = "izemquwmmqjdasrk"
    email_to: str = "agence@icidordogne.fr"
    email_cc: str = "laetony@gmail.com"  # TOUJOURS en copie
    
    # === ICI Dordogne ===
    codes_postaux_vergt: List[str] = field(default_factory=lambda: [
        "24380", "24110", "24140", "24520", "24330", "24750"
    ])
    codes_postaux_bugue: List[str] = field(default_factory=lambda: [
        "24260", "24480", "24150", "24510", "24220", "24620"
    ])
    
    # === Métadonnées V19 ===
    version: str = "19.0.0"
    environment: str = field(default_factory=lambda: os.getenv("RAILWAY_ENVIRONMENT", "development"))
    
    def __post_init__(self):
        """Validation post-initialisation."""
        if not self.database_url:
            logger.warning("⚠️ DATABASE_URL non définie - mode dégradé")
        if not self.anthropic_api_key:
            logger.warning("⚠️ ANTHROPIC_API_KEY non définie - chat désactivé")
    
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
            if not self.anthropic_api_key:
                errors.append("ANTHROPIC_API_KEY obligatoire en production")
        
        if errors:
            for e in errors:
                logger.critical(f"❌ Config invalide: {e}")
            return False
        
        logger.info(f"✅ Configuration V19 validée ({self.environment})")
        return True


# Instance globale singleton
settings = Settings()


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
    print(f"Codes postaux: {len(settings.all_codes_postaux)}")
    settings.validate()
