# axi_v19/modules/legacy.py
"""
Endpoints legacy V18 portés vers V19
Assure la compatibilité avec les crons et l'interface Axis

"Je ne lâche pas." 💪
"""

import logging
from datetime import datetime

logger = logging.getLogger("axi_v19.legacy")

# =============================================================================
# MÉMOIRE STATIQUE (équivalent /memory V18)
# =============================================================================

MEMORY_CONTENT = """# MEMORY - CONSIGNES POUR AXIS

*Mise à jour: V19.1 - 5 janvier 2026*

## WORKFLOW OBLIGATOIRE

À chaque début de conversation, Axis doit:
1. Appeler GET /memory sur ce service
2. Lire et appliquer ces consignes
3. Ne jamais ignorer ces règles

## RÈGLES ABSOLUES

### Emails
- ❌ Jamais d'envoi sans accord explicite de Ludo
- ✅ Toujours laetony@gmail.com en copie

### Validation
- ❌ Ne RIEN lancer/exécuter/déployer sans validation Ludo
- ❌ Ne jamais changer de sujet sans confirmation que le précédent est terminé

### Qualité
- ✅ Toujours être critique sur le travail fait
- ✅ Identifier les failles/manques AVANT de proposer la suite

## VERSION ACTUELLE

**V19 BUNKER** - Architecture modulaire déployée le 4 janvier 2026

### Features V19
- Tables préfixées v19_* (isolation stricte)
- Pool PostgreSQL thread-safe
- Graceful shutdown (SIGTERM/SIGINT)
- Premier Cri (logs pré-initialisation)

### Endpoints V19
- /health, /ready, /status
- /v19/brain, /v19/prospects, /v19/veille
- /memory, /briefing (legacy compatible)

## CREDENTIALS ACTIFS

### Gmail SMTP
- Email: u5050786429@gmail.com
- App password: izemquwmmqjdasrk

### Destinataires
- Principal: agence@icidordogne.fr
- Copie: laetony@gmail.com

## VEILLES ✅ OPÉRATIONNELLES

### 1. Veille DPE
- Cron: 08h00 Paris (UTC 07h00)
- Endpoint: /run-veille (protégé)
- Status: ✅ Opérationnelle
- Enrichissement DVF actif (23,680 parcelles)

### 2. Veille Concurrence
- Cron: 07h00 Paris (UTC 06h00)
- Endpoint: /run-veille-concurrence (protégé)
- Agences surveillées: 16
- Status: ✅ Opérationnelle

## HISTORIQUE

| Date | Action |
|------|--------|
| 05/01/2026 | V19.1: Veilles opérationnelles, sécurité API |
| 04/01/2026 | V19: Architecture Bunker déployée |
| 24/12/2025 | v10: Code unifié (chat + veilles) |
| 22/12/2025 | v7: Machine de guerre + Excel |
"""


def get_memory(query):
    """GET /memory - Retourne les consignes pour Axis."""
    return MEMORY_CONTENT


def get_briefing(query):
    """GET /briefing - Retourne le contexte complet."""
    briefing = f"""=== BRIEFING AXI V19 ===

Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} Paris

## STATUS SYSTÈME
- Version: V19.1.0 (Bunker Sécurisé)
- Database: PostgreSQL connecté
- Architecture: Modulaire isolée

## DÉCISIONS ACTIVES

### 🟢 VALIDÉ (4 janvier 2026)
- ✅ V19 Bunker déployée
- ✅ Imports relatifs corrigés (rapport Lumo)
- ✅ Premier Cri implémenté
- ✅ Tables v19_* créées
- ✅ Veilles DPE + Concurrence portées

### 📅 DATES
- 7 janvier: Tirage Bio Vergt
- Fin janvier: Départ Maroc Ludo

## COMMANDES
- /m → GET /memory
- /d → Réflexion profonde
- /dm → Double Manœuvre (blocage + options)
- salut → Briefing
- bye → Clôture session

"Je ne lâche pas." 💪
"""
    return briefing


def register_legacy_routes(server):
    """Enregistre les endpoints legacy sur le serveur."""
    
    # Memory et briefing uniquement
    server.register_route('GET', '/memory', get_memory)
    server.register_route('GET', '/briefing', get_briefing)
    
    # Note: Les veilles sont gérées par modules/veille.py
    
    logger.info("📍 Routes legacy V18 enregistrées (/memory, /briefing)")

