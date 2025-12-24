"""
AXI DATABASE LAYER - Version V4 Corrigée
Compatible avec init_schema_v4_final.sql
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import json
import os
from datetime import datetime

# === CONFIGURATION ===
DB_CONFIG = {
    "dbname": os.environ.get("AXI_DB_NAME", "axis_db"),
    "user": os.environ.get("AXI_DB_USER", "axis_user"),
    "password": os.environ.get("AXI_DB_PASSWORD", "ton_password_ici"),
    "host": os.environ.get("AXI_DB_HOST", "localhost"),
    "port": os.environ.get("AXI_DB_PORT", "5432")
}

class AxiDB:
    def __init__(self):
        self.conn = None

    def connect(self):
        """Établit la connexion si elle n'existe pas ou est fermée"""
        try:
            if self.conn is None or self.conn.closed:
                self.conn = psycopg2.connect(**DB_CONFIG)
                print("✅ [DB] Connexion PostgreSQL établie")
        except Exception as e:
            print(f"❌ [DB] Erreur connexion: {e}")
            self.conn = None
        return self.conn is not None

    def close(self):
        """Ferme proprement la connexion"""
        if self.conn and not self.conn.closed:
            self.conn.close()

    def _query(self, sql, params=None, fetch=False, fetch_one=False):
        """Exécuteur générique de requêtes"""
        if not self.connect():
            return None
            
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                if fetch_one:
                    return cur.fetchone()
                if fetch:
                    return cur.fetchall()
                self.conn.commit()
                return True
        except Exception as e:
            self.conn.rollback()
            print(f"⚠️ [DB] Erreur: {e}")
            return None

    # =========================================================================
    # 🧠 SOUVENIRS (Mémoire / Conversations / Logs)
    # =========================================================================

    def ajouter_souvenir(self, type_evt, source, contenu, relation_id=None, bien_id=None, metadata=None):
        """
        Enregistre un souvenir (conversation, log, erreur, etc.)
        """
        sql = """
            INSERT INTO souvenirs (type, source, contenu, relation_id, bien_id, metadata, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            RETURNING id;
        """
        meta_json = json.dumps(metadata, ensure_ascii=False) if metadata else None
        result = self._query(sql, (type_evt, source, contenu, relation_id, bien_id, meta_json), fetch_one=True)
        return result['id'] if result else None

    def recuperer_contexte_chat(self, limit=50):
        """Récupère l'historique récent des conversations"""
        sql = """
            SELECT source, contenu, timestamp 
            FROM souvenirs 
            WHERE type = 'conversation' 
            ORDER BY timestamp DESC 
            LIMIT %s;
        """
        rows = self._query(sql, (limit,), fetch=True)
        return sorted(rows, key=lambda x: x['timestamp']) if rows else []

    def formater_historique_pour_llm(self, limit=50):
        """
        Formate l'historique en string pour le prompt Claude/Mistral
        Retourne le format attendu par main.py
        """
        conversations = self.recuperer_contexte_chat(limit)
        if not conversations:
            return ""
        
        lignes = []
        for conv in conversations:
            source = conv['source'].upper()
            if source == 'LUDO':
                tag = '[USER]'
            elif source == 'AXIS':
                tag = '[AXIS]'
            elif source == 'AXI':
                tag = '[AXI]'
            else:
                tag = f'[{source}]'
            lignes.append(f"{tag} {conv['contenu']}")
        
        return "\n".join(lignes)

    def log_systeme(self, message, metadata=None):
        """Raccourci pour logs système"""
        return self.ajouter_souvenir('systeme', 'axi', message, metadata=metadata)

    def log_erreur(self, message, metadata=None):
        """Raccourci pour logs d'erreur"""
        return self.ajouter_souvenir('erreur', 'axi', message, metadata=metadata)

    def log_veille(self, message, metadata=None):
        """Raccourci pour logs de veille"""
        return self.ajouter_souvenir('log_veille', 'cron', message, metadata=metadata)

    # =========================================================================
    # 🏠 BIENS (DPE, Mandats, DVF, Annonces)
    # =========================================================================

    def ajouter_bien(self, data):
        """
        Insère ou ignore un bien (anti-doublon via reference_interne)
        Retourne l'ID si créé, None si doublon
        """
        sql = """
            INSERT INTO biens (
                reference_interne, statut, 
                adresse_brute, code_postal, ville, id_parcelle,
                type_bien, prix_affiche, surface_habitable, surface_terrain, pieces,
                dpe_lettre, ges_lettre, dpe_valeur,
                source_initiale, url_source, proprietaire_id, details,
                created_at
            ) VALUES (
                %(ref)s, %(statut)s,
                %(adresse)s, %(cp)s, %(ville)s, %(parcelle)s,
                %(type)s, %(prix)s, %(surface_hab)s, %(surface_ter)s, %(pieces)s,
                %(dpe)s, %(ges)s, %(dpe_val)s,
                %(source)s, %(url)s, %(proprio)s, %(details)s,
                NOW()
            )
            ON CONFLICT (reference_interne) DO NOTHING
            RETURNING id;
        """
        
        params = {
            'ref': data.get('reference_interne'),
            'statut': data.get('statut', 'veille'),
            'adresse': data.get('adresse', ''),
            'cp': str(data.get('code_postal', '')).replace('.0', ''),
            'ville': data.get('ville', ''),
            'parcelle': data.get('id_parcelle'),
            'type': data.get('type_bien', 'maison'),
            'prix': data.get('prix') or None,
            'surface_hab': data.get('surface_habitable') or None,
            'surface_ter': data.get('surface_terrain') or None,
            'pieces': data.get('pieces') or None,
            'dpe': data.get('dpe_lettre'),
            'ges': data.get('ges_lettre'),
            'dpe_val': data.get('dpe_valeur') or None,
            'source': data.get('source_initiale', 'inconnue'),
            'url': data.get('url_source'),
            'proprio': data.get('proprietaire_id'),
            'details': json.dumps(data.get('details', {}), ensure_ascii=False)
        }
        
        result = self._query(sql, params, fetch_one=True)
        return result['id'] if result else None

    def trouver_bien(self, reference):
        """Retrouve un bien par sa référence unique"""
        sql = "SELECT * FROM biens WHERE reference_interne = %s;"
        return self._query(sql, (reference,), fetch_one=True)

    def bien_existe(self, reference):
        """Vérifie si un bien existe (plus rapide que trouver_bien)"""
        sql = "SELECT 1 FROM biens WHERE reference_interne = %s LIMIT 1;"
        return self._query(sql, (reference,), fetch_one=True) is not None

    def stats_biens_par_dpe(self):
        """Stats pour tableau de bord"""
        sql = """
            SELECT dpe_lettre, COUNT(*) as total 
            FROM biens 
            WHERE dpe_lettre IS NOT NULL
            GROUP BY dpe_lettre 
            ORDER BY dpe_lettre;
        """
        return self._query(sql, fetch=True) or []

    def passoires_thermiques(self, code_postal=None):
        """Récupère les DPE F et G (passoires)"""
        if code_postal:
            sql = "SELECT * FROM biens WHERE dpe_lettre IN ('F', 'G') AND code_postal = %s;"
            return self._query(sql, (code_postal,), fetch=True) or []
        else:
            sql = "SELECT * FROM biens WHERE dpe_lettre IN ('F', 'G');"
            return self._query(sql, fetch=True) or []

    # =========================================================================
    # 👥 RELATIONS (Personnes)
    # =========================================================================

    def ajouter_relation(self, nom, type_rel=None, email=None, telephone=None, profil=None):
        """Crée une nouvelle relation"""
        sql = """
            INSERT INTO relations (nom, type, email, telephone, profil_psychologique, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            RETURNING *;
        """
        return self._query(sql, (nom, type_rel, email, telephone, profil), fetch_one=True)

    def trouver_relation(self, nom=None, email=None):
        """Cherche une relation par nom ou email"""
        if email:
            sql = "SELECT * FROM relations WHERE email = %s LIMIT 1;"
            result = self._query(sql, (email,), fetch_one=True)
            if result:
                return result
        
        if nom:
            sql = "SELECT * FROM relations WHERE nom ILIKE %s LIMIT 1;"
            return self._query(sql, (f"%{nom}%",), fetch_one=True)
        
        return None

    def trouver_ou_creer_relation(self, nom, email=None, type_rel='prospect'):
        """Cherche une relation, la crée si inexistante"""
        existant = self.trouver_relation(nom, email)
        if existant:
            return existant
        return self.ajouter_relation(nom, type_rel, email)

    # =========================================================================
    # 📚 FAITS (Connaissances)
    # =========================================================================

    def ajouter_fait(self, sujet, predicat, objet, confiance=1.0, source_souvenir_id=None):
        """Enregistre un fait (triplet sujet-prédicat-objet)"""
        sql = """
            INSERT INTO faits (sujet, predicat, objet, confiance, source_souvenir_id, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            RETURNING id;
        """
        result = self._query(sql, (sujet, predicat, objet, confiance, source_souvenir_id), fetch_one=True)
        return result['id'] if result else None

    def chercher_faits(self, sujet=None, predicat=None):
        """Recherche des faits par sujet et/ou prédicat"""
        conditions = ["valide = TRUE"]
        params = []
        
        if sujet:
            conditions.append("sujet ILIKE %s")
            params.append(f"%{sujet}%")
        
        if predicat:
            conditions.append("predicat = %s")
            params.append(predicat)
        
        sql = f"SELECT * FROM faits WHERE {' AND '.join(conditions)};"
        return self._query(sql, params, fetch=True) or []

    def invalider_fait(self, fait_id):
        """Invalide un fait (soft delete)"""
        sql = "UPDATE faits SET valide = FALSE, updated_at = NOW() WHERE id = %s;"
        return self._query(sql, (fait_id,))

    # =========================================================================
    # 📄 DOCUMENTS (Phase 3 - OCR)
    # =========================================================================

    def ajouter_document(self, hash_fichier, nom_original, chemin, type_mime, taille, bien_id=None, relation_id=None):
        """Enregistre un document (préparé pour OCR)"""
        sql = """
            INSERT INTO documents (
                hash_fichier, nom_original, chemin_stockage, type_mime, taille_octets,
                bien_id, relation_id, statut_traitement, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'en_attente', NOW())
            ON CONFLICT (hash_fichier) DO NOTHING
            RETURNING id;
        """
        result = self._query(sql, (hash_fichier, nom_original, chemin, type_mime, taille, bien_id, relation_id), fetch_one=True)
        return result['id'] if result else None

    def documents_a_traiter(self):
        """Liste les documents en attente d'OCR"""
        sql = "SELECT * FROM documents WHERE statut_traitement = 'en_attente';"
        return self._query(sql, fetch=True) or []

    def marquer_document_traite(self, doc_id, extraction_json, contenu_texte):
        """Met à jour un document après OCR"""
        sql = """
            UPDATE documents 
            SET statut_traitement = 'traite', 
                extraction_json = %s, 
                contenu_texte = %s,
                processed_at = NOW()
            WHERE id = %s;
        """
        return self._query(sql, (json.dumps(extraction_json, ensure_ascii=False), contenu_texte, doc_id))


# =========================================================================
# INSTANCE GLOBALE (Singleton)
# =========================================================================

_db_instance = None

def get_db():
    """Retourne l'instance unique de la base de données"""
    global _db_instance
    if _db_instance is None:
        _db_instance = AxiDB()
    return _db_instance


# =========================================================================
# TEST DE CONNEXION
# =========================================================================

if __name__ == "__main__":
    print("🧪 Test connexion PostgreSQL...")
    db = get_db()
    if db.connect():
        print("✅ Connexion OK")
        
        # Test écriture
        test_id = db.ajouter_souvenir('test', 'script', 'Test de connexion db.py')
        if test_id:
            print(f"✅ Écriture OK (souvenir #{test_id})")
        
        # Test lecture
        stats = db.stats_biens_par_dpe()
        print(f"📊 Stats DPE: {stats}")
        
        db.close()
    else:
        print("❌ Connexion échouée")
