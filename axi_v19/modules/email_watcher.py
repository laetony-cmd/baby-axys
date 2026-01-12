"""
MODULE EMAIL WATCHER - AXI V19.5
================================
Surveillance IMAP agence@icidordogne.fr
Création automatique cartes Trello pour prospects

Auteur: Axis (Claude)
Date: 10 janvier 2026
Version: 1.0.0

RÈGLE D'OR: Ce module ne doit RIEN exécuter lors de l'import.
"""

import os
import re
import json
import imaplib
import email
import logging
import urllib.request
import urllib.parse
from email.header import decode_header
from datetime import datetime
from typing import Optional, List, Dict, Tuple

# =============================================================================
# CONFIGURATION
# =============================================================================

logger = logging.getLogger("email_watcher")

# Gmail ICI Dordogne
IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993
IMAP_EMAIL = os.getenv("IMAP_EMAIL", "agence@icidordogne.fr")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD", "logrqinzbgzibyrt")

# Trello
TRELLO_KEY = os.getenv("TRELLO_KEY")
TRELLO_TOKEN = os.getenv("TRELLO_TOKEN")
TRELLO_LIST_PROSPECTS = "694f52e6238e9746b814cae9"  # TEST ACQUÉREURS dans Pros LUDO
JULIE_ID = "59db340040eb2c01fb7d4851"

# Label pour marquer les emails traités
PROCESSED_LABEL = "AXI_PROCESSED"

# =============================================================================
# PARSERS EMAIL
# =============================================================================

def parse_leboncoin(body: str, subject: str) -> Optional[Dict]:
    """Parse un email Leboncoin et extrait les infos prospect."""
    try:
        data = {
            "source": "Leboncoin",
            "nom": None,
            "email": None,
            "tel": None,
            "message": None,
            "bien_titre": None,
            "bien_prix": None,
            "bien_ref": None,
            "ville": None
        }
        
        # Nom
        nom_match = re.search(r'Nom\s*:\s*([^\n<]+)', body, re.IGNORECASE)
        if nom_match:
            data["nom"] = nom_match.group(1).strip()
        
        # Email
        email_match = re.search(r'E-mail\s*:\s*([^\s<>]+@[^\s<>]+)', body, re.IGNORECASE)
        if email_match:
            data["email"] = email_match.group(1).strip()
        
        # Téléphone
        tel_match = re.search(r'T[ée]l[ée]phone\s*:\s*([+\d\s\-\.]+)', body, re.IGNORECASE)
        if tel_match:
            data["tel"] = re.sub(r'[^\d+]', '', tel_match.group(1))
        
        # Message
        msg_match = re.search(r'[«"]([^»"]+)[»"]', body)
        if msg_match:
            data["message"] = msg_match.group(1).strip()
        
        # Prix dans le sujet ou le body
        prix_match = re.search(r'(\d[\d\s]*)\s*€', subject + " " + body)
        if prix_match:
            data["bien_prix"] = re.sub(r'\s', '', prix_match.group(1))
        
        # Ville
        ville_match = re.search(r'Ville\s*:\s*([^\n<]+)', body, re.IGNORECASE)
        if ville_match:
            data["ville"] = ville_match.group(1).strip()
        
        # Référence Leboncoin
        ref_match = re.search(r'[Rr][ée]f[ée]rence\s*:\s*([A-Z0-9\-]+)', body)
        if ref_match:
            data["bien_ref"] = ref_match.group(1)
        
        # Titre du bien depuis le sujet
        if "intéressé" in subject.lower() or "favori" in subject.lower():
            titre_match = re.search(r'pour\s+(.+?)(?:\s+-\s+|\s*$)', subject, re.IGNORECASE)
            if titre_match:
                data["bien_titre"] = titre_match.group(1).strip()
        
        # Validation minimum
        if data["email"] or data["tel"]:
            return data
        return None
        
    except Exception as e:
        logger.error(f"Erreur parse Leboncoin: {e}")
        return None


def parse_seloger(body: str, subject: str) -> Optional[Dict]:
    """Parse un email SeLoger."""
    try:
        data = {
            "source": "SeLoger",
            "nom": None,
            "email": None,
            "tel": None,
            "message": None,
            "bien_titre": None,
            "bien_prix": None,
            "bien_ref": None
        }
        
        # Patterns SeLoger
        nom_match = re.search(r'(?:Nom|Name)\s*:\s*([^\n<]+)', body, re.IGNORECASE)
        if nom_match:
            data["nom"] = nom_match.group(1).strip()
        
        email_match = re.search(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', body)
        if email_match:
            data["email"] = email_match.group(1)
        
        tel_match = re.search(r'(\+?\d[\d\s\-\.]{8,})', body)
        if tel_match:
            data["tel"] = re.sub(r'[^\d+]', '', tel_match.group(1))
        
        if data["email"] or data["tel"]:
            return data
        return None
        
    except Exception as e:
        logger.error(f"Erreur parse SeLoger: {e}")
        return None


def parse_generic(body: str, subject: str, from_addr: str) -> Optional[Dict]:
    """Parse générique pour autres sources."""
    try:
        data = {
            "source": "Site/Autre",
            "nom": None,
            "email": None,
            "tel": None,
            "message": body[:500] if body else None,
            "bien_titre": subject
        }
        
        # Extraire email du from
        email_match = re.search(r'<([^>]+)>', from_addr)
        if email_match:
            data["email"] = email_match.group(1)
        elif "@" in from_addr:
            data["email"] = from_addr.split()[0] if " " in from_addr else from_addr
        
        # Chercher téléphone dans le body
        tel_match = re.search(r'(\+?\d[\d\s\-\.]{8,})', body)
        if tel_match:
            data["tel"] = re.sub(r'[^\d+]', '', tel_match.group(1))
        
        # Chercher nom
        nom_patterns = [
            r'(?:Nom|Name|Prénom|Prenom)\s*:\s*([^\n<]+)',
            r'^([A-Z][a-zéèêë]+\s+[A-Z][a-zéèêë]+)',
        ]
        for pattern in nom_patterns:
            match = re.search(pattern, body, re.IGNORECASE | re.MULTILINE)
            if match:
                data["nom"] = match.group(1).strip()
                break
        
        if data["email"]:
            return data
        return None
        
    except Exception as e:
        logger.error(f"Erreur parse generic: {e}")
        return None


# =============================================================================
# TRELLO
# =============================================================================

def create_prospect_card(prospect: Dict) -> Optional[str]:
    """Crée une carte Trello pour le prospect."""
    if not TRELLO_KEY or not TRELLO_TOKEN:
        logger.error("Credentials Trello manquants")
        return None
    
    try:
        # Nom de la carte: NOM Prénom ou Email
        nom = prospect.get("nom", "").upper() if prospect.get("nom") else prospect.get("email", "PROSPECT").split("@")[0].upper()
        card_name = f"{nom} - {prospect.get('source', 'Email')}"
        
        # Description
        desc = f"""**Tél** : {prospect.get('tel', '-')}
**Email** : {prospect.get('email', '-')}
**Source** : {prospect.get('source', '-')}

**Bien demandé** : {prospect.get('bien_titre', '-')}
**Prix** : {prospect.get('bien_prix', '-')} €
**Réf** : {prospect.get('bien_ref', '-')}
**Ville** : {prospect.get('ville', '-')}

**Message** :
{prospect.get('message', '-')}

---
*Créé automatiquement par Axi le {datetime.now().strftime('%d/%m/%Y %H:%M')}*
"""
        
        # Créer la carte
        url = f"https://api.trello.com/1/cards"
        params = {
            "key": TRELLO_KEY,
            "token": TRELLO_TOKEN,
            "idList": TRELLO_LIST_PROSPECTS,
            "name": card_name,
            "desc": desc,
            "pos": "top",
            "idMembers": JULIE_ID
        }
        
        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            card_url = result.get("url")
            card_id = result.get("id")
            logger.info(f"✅ Carte créée: {card_name} -> {card_url}")
            
            # Ajouter checklists
            add_checklists(card_id)
            
            return card_url
    
    except Exception as e:
        logger.error(f"Erreur création carte Trello: {e}")
        return None


def add_checklists(card_id: str):
    """Ajoute les checklists standard à la carte."""
    try:
        checklists = [
            ("Avant la visite", ["RDV validé avec l'acquéreur", "Bon de visite signé reçu", "RDV dans Sweep", "Bon de visite envoyé", "RDV validé avec le propriétaire"]),
            ("Après la visite", ["CR Proprio", "CR Trello", "Autres biens à proposer"])
        ]
        
        for cl_name, items in checklists:
            # Créer checklist
            url = f"https://api.trello.com/1/checklists"
            params = {"key": TRELLO_KEY, "token": TRELLO_TOKEN, "idCard": card_id, "name": cl_name}
            data = urllib.parse.urlencode(params).encode()
            req = urllib.request.Request(url, data=data, method="POST")
            
            with urllib.request.urlopen(req, timeout=10) as resp:
                cl = json.loads(resp.read().decode())
                cl_id = cl.get("id")
                
                # Ajouter items
                for item in items:
                    item_url = f"https://api.trello.com/1/checklists/{cl_id}/checkItems"
                    item_params = {"key": TRELLO_KEY, "token": TRELLO_TOKEN, "name": item}
                    item_data = urllib.parse.urlencode(item_params).encode()
                    item_req = urllib.request.Request(item_url, data=item_data, method="POST")
                    urllib.request.urlopen(item_req, timeout=10)
    
    except Exception as e:
        logger.warning(f"Erreur ajout checklists: {e}")


# =============================================================================
# IMAP WATCHER
# =============================================================================

def get_email_body(msg) -> str:
    """Extrait le corps texte d'un email."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    body = payload.decode('utf-8', errors='ignore')
                    break
            elif content_type == "text/html" and not body:
                payload = part.get_payload(decode=True)
                if payload:
                    # Nettoyer HTML basique
                    html = payload.decode('utf-8', errors='ignore')
                    body = re.sub(r'<[^>]+>', ' ', html)
                    body = re.sub(r'\s+', ' ', body)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode('utf-8', errors='ignore')
    return body


def check_emails() -> List[Dict]:
    """Vérifie les nouveaux emails et retourne les prospects détectés."""
    prospects = []
    
    try:
        logger.info(f"📧 Connexion IMAP {IMAP_EMAIL}...")
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(IMAP_EMAIL, IMAP_PASSWORD)
        mail.select("inbox")
        
        # Chercher emails non lus
        status, messages = mail.search(None, "(UNSEEN)")
        unread_ids = messages[0].split()
        
        logger.info(f"📬 {len(unread_ids)} emails non lus")
        
        for mail_id in unread_ids:
            try:
                status, msg_data = mail.fetch(mail_id, "(RFC822)")
                
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        
                        # Décoder sujet
                        subject_raw = msg.get("Subject", "")
                        subject, encoding = decode_header(subject_raw)[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding or "utf-8", errors='ignore')
                        
                        from_addr = msg.get("From", "")
                        body = get_email_body(msg)
                        
                        # Détecter type de mail et parser
                        prospect = None
                        
                        if "leboncoin" in from_addr.lower() or "leboncoin" in subject.lower():
                            prospect = parse_leboncoin(body, subject)
                        elif "seloger" in from_addr.lower() or "seloger" in subject.lower():
                            prospect = parse_seloger(body, subject)
                        elif any(kw in subject.lower() for kw in ["contact", "demande", "visite", "information", "intéressé"]):
                            prospect = parse_generic(body, subject, from_addr)
                        
                        if prospect:
                            prospect["raw_subject"] = subject
                            prospect["raw_from"] = from_addr
                            prospect["date"] = msg.get("Date", "")
                            prospects.append(prospect)
                            logger.info(f"🔥 Prospect détecté: {prospect.get('nom', prospect.get('email'))}")
                        
            except Exception as e:
                logger.error(f"Erreur traitement email {mail_id}: {e}")
                continue
        
        mail.logout()
        
    except Exception as e:
        logger.error(f"❌ Erreur IMAP: {e}")
    
    return prospects


def process_new_emails() -> Dict:
    """Fonction principale: vérifie emails et crée cartes Trello."""
    result = {
        "timestamp": datetime.now().isoformat(),
        "emails_checked": 0,
        "prospects_found": 0,
        "cards_created": 0,
        "errors": []
    }
    
    try:
        prospects = check_emails()
        result["prospects_found"] = len(prospects)
        
        for prospect in prospects:
            card_url = create_prospect_card(prospect)
            if card_url:
                result["cards_created"] += 1
            else:
                result["errors"].append(f"Échec création carte pour {prospect.get('email')}")
        
        logger.info(f"📊 Résultat: {result['prospects_found']} prospects, {result['cards_created']} cartes créées")
        
    except Exception as e:
        result["errors"].append(str(e))
        logger.error(f"Erreur process_new_emails: {e}")
    
    return result


# =============================================================================
# ENDPOINTS HTTP (pour intégration main.py)
# =============================================================================

def handle_check_emails(params: Dict) -> Tuple[int, Dict]:
    """Handler pour endpoint /emails/check"""
    result = process_new_emails()
    return 200, result


def handle_email_status(params: Dict) -> Tuple[int, Dict]:
    """Handler pour endpoint /emails/status"""
    return 200, {
        "service": "Email Watcher",
        "imap_email": IMAP_EMAIL,
        "trello_list": TRELLO_LIST_PROSPECTS,
        "status": "ready"
    }




# =============================================================================
# MOVE EMAIL TO LABEL (ajouté 12/01/2026)
# =============================================================================

LABEL_ACQUEREURS = "**ACQUÉREURS"
# Version encodée UTF-7 pour IMAP
LABEL_ACQUEREURS_IMAP = "&ACoAKg-ACQ-U&AOk-REURS"  # **ACQUÉREURS en UTF-7 modifié


def move_email_to_label(email_from: str = '', subject_contains: str = '', label: str = None) -> Dict:
    """
    Déplace un email de INBOX vers un label Gmail (par défaut **ACQUÉREURS).
    """
    target_label = label or LABEL_ACQUEREURS
    
    try:
        logger.info(f"📧 Déplacement email vers {target_label}...")
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(IMAP_EMAIL, IMAP_PASSWORD)
        mail.select("inbox")
        
        search_parts = []
        if email_from:
            search_parts.append(f'FROM "{email_from}"')
        if subject_contains:
            search_parts.append(f'SUBJECT "{subject_contains}"')
        
        if not search_parts:
            mail.logout()
            return {"success": False, "error": "Paramètre 'from' ou 'subject' requis"}
        
        search_query = ' '.join(search_parts)
        status, messages = mail.search(None, search_query)
        
        if status != 'OK' or not messages[0]:
            mail.logout()
            return {"success": False, "moved": 0, "message": f"Aucun email trouvé"}
        
        email_ids = messages[0].split()
        moved_count = 0
        
        for email_id in email_ids[-5:]:
            try:
                # Encoder le label pour IMAP (UTF-7 modifié pour Gmail)
                imap_label = target_label
                # **ACQUÉREURS -> encodage IMAP UTF-7
                if 'ACQUÉREURS' in target_label:
                    imap_label = '**ACQU&AMk-REURS'
                copy_result = mail.copy(email_id, imap_label)
                if copy_result[0] == 'OK':
                    mail.store(email_id, '+FLAGS', '\\Deleted')
                    moved_count += 1
            except Exception as e:
                logger.warning(f"Erreur email {email_id}: {e}")
                continue
        
        mail.expunge()
        mail.logout()
        
        return {
            "success": moved_count > 0,
            "moved": moved_count,
            "label": target_label,
            "message": f"{moved_count} email(s) déplacé(s) vers {target_label}"
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        return {"success": False, "error": str(e)}


def handle_move_email(query=None, body=None, headers=None) -> Tuple[int, Dict]:
    """Handler pour endpoint POST /email/move-acquereur"""
    if not body:
        body = {}
    email_from = body.get('from', '')
    subject_contains = body.get('subject', '')
    label = body.get('label', LABEL_ACQUEREURS)
    
    result = move_email_to_label(email_from, subject_contains, label)
    status_code = 200 if result.get('success') else 400
    return status_code, result




def debug_imap_search(query=None, body=None, headers=None) -> Tuple[int, Dict]:
    """Debug: voir ce que contient INBOX via IMAP"""
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(IMAP_EMAIL, IMAP_PASSWORD)
        
        # Lister les dossiers
        status, folders = mail.list()
        folder_names = []
        for f in folders[:20]:
            folder_names.append(f.decode('utf-8', errors='ignore'))
        
        # Sélectionner INBOX
        status, count = mail.select('INBOX')
        inbox_count = count[0].decode() if count else '0'
        
        # Chercher TOUS les emails
        status, messages = mail.search(None, 'ALL')
        all_ids = messages[0].split() if messages[0] else []
        
        # Récupérer les 5 derniers sujets/from
        last_emails = []
        for eid in all_ids[-5:]:
            try:
                status, data = mail.fetch(eid, '(BODY[HEADER.FIELDS (SUBJECT FROM)])')
                if data and data[0]:
                    header = data[0][1].decode('utf-8', errors='ignore')
                    last_emails.append(header.strip()[:150])
            except:
                pass
        
        # Tester recherche "fafa"
        status_fafa, msg_fafa = mail.search(None, 'FROM "fafa"')
        fafa_count = len(msg_fafa[0].split()) if msg_fafa[0] else 0
        
        # Tester recherche "leboncoin"
        status_lbc, msg_lbc = mail.search(None, 'FROM "leboncoin"')
        lbc_count = len(msg_lbc[0].split()) if msg_lbc[0] else 0
        
        mail.logout()
        
        return 200, {
            "inbox_total": inbox_count,
            "all_emails_count": len(all_ids),
            "last_5_emails": last_emails,
            "search_fafa": fafa_count,
            "search_leboncoin": lbc_count,
            "folders_sample": folder_names[:10]
        }
        
    except Exception as e:
        return 500, {"error": str(e)}


# Point d'entrée pour test manuel
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = process_new_emails()
    print(json.dumps(result, indent=2, ensure_ascii=False))
