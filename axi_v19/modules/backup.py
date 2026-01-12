# axi_v19/modules/backup.py
"""
Module Backup - Export PostgreSQL
Ajouté le 12 janvier 2026 pour pérennité Maroc

"Je ne lâche pas." 💪
"""

import json
import logging
from datetime import datetime

logger = logging.getLogger("axi_v19.backup")


def export_dpe_vus(db):
    """Exporte la table dpe_veille_vus en JSON."""
    try:
        with db.get_connection() as conn:
            cur = conn.cursor()
            
            # Récupérer tous les DPE
            cur.execute("""
                SELECT numero_dpe, date_reception, code_postal, commune, 
                       etiquette_dpe, trello_card_url, date_traitement
                FROM dpe_veille_vus
                ORDER BY date_traitement DESC
            """)
            
            rows = cur.fetchall()
            columns = ['numero_dpe', 'date_reception', 'code_postal', 'commune', 
                       'etiquette_dpe', 'trello_card_url', 'date_traitement']
            
            data = []
            for row in rows:
                item = {}
                for i, col in enumerate(columns):
                    val = row[i]
                    # Convertir datetime en string
                    if hasattr(val, 'isoformat'):
                        val = val.isoformat()
                    item[col] = val
                data.append(item)
            
            cur.close()
        
        return {
            "success": True,
            "table": "dpe_veille_vus",
            "count": len(data),
            "exported_at": datetime.now().isoformat(),
            "data": data
        }
    except Exception as e:
        logger.error(f"Erreur export DPE: {e}")
        return {"success": False, "error": str(e)}


def register_backup_routes(server, db):
    """Enregistre les routes de backup."""
    
    def handle_backup_dpe(query):
        """Export JSON de la table dpe_veille_vus."""
        result = export_dpe_vus(db)
        return result
    
    def handle_backup_status(query):
        """Status des backups."""
        try:
            with db.get_connection() as conn:
                cur = conn.cursor()
                
                # Compter les entrées
                cur.execute("SELECT COUNT(*) FROM dpe_veille_vus")
                total = cur.fetchone()[0]
                
                cur.execute("SELECT MAX(date_traitement) FROM dpe_veille_vus")
                last = cur.fetchone()[0]
                
                cur.close()
            
            return {
                "status": "ok",
                "tables": {
                    "dpe_veille_vus": {
                        "count": total,
                        "last_entry": last.isoformat() if last else None
                    }
                },
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    server.register_route('GET', '/backup/dpe', handle_backup_dpe)
    server.register_route('GET', '/backup/status', handle_backup_status)
    
    logger.info("📦 Routes backup enregistrées (/backup/dpe, /backup/status)")
