"""
MODULE EMAIL WATCHER - AXI V19.6
================================
Surveillance IMAP agence@icidordogne.fr
Création automatique cartes Trello pour prospects ENRICHIES

Auteur: Axis (Claude)
Date: 13 janvier 2026
Version: 2.0.0

NOUVEAUTÉS V2:
- Vérification doublon avant création
- Lien carte Trello du bien
- Lien site ICI Dordogne du bien
- Affectation Julie + membres du bien
- Message prospect en commentaire (pas description)
- Étiquettes "Pas dans Sweepbright" + "Pas traité"
- Création sur board "1 ACQUÉREURS" liste "SUIVI CLIENTS ACTIFS"

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
import time
from email.header import decode_header
from datetime import datetime
from typing import Optional, List, Dict, Tuple

# =============================================================================
# CONFIGURATION
# =============================================================================

logger = logging.getLogger("email_watcher")

EMAIL_WATCHER_VERSION = "V2.0.0-13JAN2026"

# Gmail ICI Dordogne
IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993
IMAP_EMAIL = os.getenv("IMAP_EMAIL", "agence@icidordogne.fr")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD", "logrqinzbgzibyrt")

# Trello
TRELLO_KEY = os.getenv("TRELLO_KEY")
TRELLO_TOKEN = os.getenv("TRELLO_TOKEN")

# Board et Liste de production : 1 ACQUÉREURS -> SUIVI CLIENTS ACTIFS
BOARD_ACQUEREURS = "66d81b60de75f67fb3bb4624"  # Pros LUDO
LIST_SUIVI_CLIENTS = "694f52e6238e9746b814cae9"  # TEST ACQUÉREURS

# Board des biens
BOARD_BIENS = "6249623e53c07a131c916e59"

# Labels à appliquer automatiquement
LABEL_PAS_SWEEPBRIGHT = "695227935ddf69abc5c10bae"  # sky  # purple
LABEL_PAS_TRAITE = "695227935ddf69abc5c10bad"  # red  # red

# Membres équipe
JULIE_ID = "59db340040eb2c01fb7d4851"
ANTHONY_ID = "57879b4a2abe0d93992c43db"
INGRID_ID = "60d5dadd9a6e79370d2a748c"
NATHALIE_ID = "578a587b36715870c806a084"
SEBASTIEN_ID = "5788b5ba8e0046d61b2c54ae"
LUDO_ID = "57888fe6dd9bbc4851b2562b"

# Label pour marquer les emails traités
LABEL_ACQUEREURS = "**ACQUÉREURS"
LABEL_ACQUEREURS_IMAP = "**ACQU&AMk-REURS"


# =============================================================================
# UTILITAIRES TRELLO
# =============================================================================

def trello_request(method: str, endpoint: str, data: dict = None) -> Optional[dict]:
    """Requête générique vers l'API Trello."""
    if not TRELLO_KEY or not TRELLO_TOKEN:
        logger.error("Credentials Trello manquants")
        return None
    
    url = f"https://api.trello.com/1{endpoint}?key={TRELLO_KEY}&token={TRELLO_TOKEN}"
    
    try:
        if data:
            encoded_data = urllib.parse.urlencode(data).encode()
        else:
            encoded_data = None
        
        req = urllib.request.Request(url, data=encoded_data, method=method)
        
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    
    except Exception as e:
        logger.error(f"Trello {method} {endpoint} failed: {e}")
        return None


def trello_get(endpoint: str) -> Optional[dict]:
    """GET request vers l'API Trello."""
    return trello_request("GET", endpoint)


def trello_post(endpoint: str, data: dict) -> Optional[dict]:
    """POST request vers l'API Trello."""
    return trello_request("POST", endpoint, data)


def trello_put(endpoint: str, data: dict) -> Optional[dict]:
    """PUT request vers l'API Trello."""
    return trello_request("PUT", endpoint, data)


# =============================================================================
# VÉRIFICATION DOUBLON
# =============================================================================

def check_prospect_exists(nom: str, prenom: str = "", email_addr: str = "") -> Optional[Dict]:
    """
    Vérifie si un prospect existe déjà dans Trello (tous les boards).
    Retourne les infos de la carte si trouvée, None sinon.
    """
    search_terms = []
    
    if nom:
        search_terms.append(nom.upper())
    if prenom:
        search_terms.append(prenom)
    if email_addr and "@" in email_addr:
        search_terms.append(email_addr.split("@")[0])
    
    if not search_terms:
        return None
    
    query = " ".join(search_terms[:2])
    
    logger.info(f"🔍 Recherche doublon: '{query}'")
    
    result = trello_get(f"/search?query={urllib.parse.quote(query)}&modelTypes=cards&card_fields=name,shortUrl,idBoard,closed")
    
    if not result or not result.get("cards"):
        return None
    
    nom_upper = nom.upper() if nom else ""
    
    for card in result.get("cards", []):
        card_name = card.get("name", "").upper()
        
        if nom_upper and nom_upper in card_name:
            if card.get("closed"):
                logger.info(f"  → Trouvé archivé: {card.get('name')} (ignoré)")
                continue
            
            logger.info(f"  → DOUBLON TROUVÉ: {card.get('name')} - {card.get('shortUrl')}")
            return {
                "found": True,
                "card_id": card.get("id"),
                "card_name": card.get("name"),
                "card_url": card.get("shortUrl"),
                "board_id": card.get("idBoard")
            }
    
    logger.info(f"  → Aucun doublon trouvé")
    return None


# =============================================================================
# RECHERCHE BIEN
# =============================================================================

def extract_ville_from_email(subject: str, body: str) -> Optional[str]:
    """Extrait la ville/adresse du bien depuis l'email."""
    cp_match = re.search(r'\b(24\d{3})\b', subject + " " + body)
    if cp_match:
        return cp_match.group(1)
    
    villes = [
        "Saint-Geyrac", "Manzac", "Vergt", "Le Bugue", "Trémolat",
        "Bergerac", "Périgueux", "Sarlat", "Lalinde", "Limeuil"
    ]
    
    text = subject + " " + body
    for ville in villes:
        if ville.lower() in text.lower():
            return ville
    
    return None


def find_property_on_trello(ville: str = None, reference: str = None) -> Optional[Dict]:
    """
    Recherche la carte Trello du bien sur le board BIENS.
    Retourne: card_id, card_url, membres assignés.
    """
    search_query = reference if reference else ville
    
    if not search_query:
        return None
    
    logger.info(f"🏠 Recherche bien Trello: '{search_query}'")
    
    result = trello_get(
        f"/search?query={urllib.parse.quote(search_query)}"
        f"&modelTypes=cards"
        f"&board_ids={BOARD_BIENS}"
        f"&card_fields=name,shortUrl,idMembers,closed"
    )
    
    if not result or not result.get("cards"):
        logger.info(f"  → Bien non trouvé sur Trello")
        return None
    
    for card in result.get("cards", []):
        logger.info(f"  → Trouvé: {card.get('name')} - {card.get('shortUrl')}")
        return {
            "card_id": card.get("id"),
            "card_name": card.get("name"),
            "card_url": card.get("shortUrl"),
            "members": card.get("idMembers", []),
            "closed": card.get("closed", False)
        }
    
    return None


def find_property_on_website(ville: str) -> Optional[str]:
    """
    Recherche l'URL du bien sur icidordogne.fr.
    Retourne l'URL de la page du bien.
    """
    base_url = "https://www.icidordogne.fr"
    
    if ville:
        search_url = f"{base_url}/?s={urllib.parse.quote(ville)}"
        return search_url
    
    return base_url


# =============================================================================
# CRÉATION CARTE PROSPECT ENRICHIE
# =============================================================================

def create_enriched_prospect_card(prospect: Dict) -> Optional[Dict]:
    """
    Crée une carte Trello prospect enrichie avec:
    - Liens vers le bien
    - Membres assignés
    - Labels
    - Message en commentaire
    """
    if not TRELLO_KEY or not TRELLO_TOKEN:
        logger.error("Credentials Trello manquants")
        return None
    
    # 1. Vérifier doublon
    nom = prospect.get("nom", "")
    email_addr = prospect.get("email", "")
    
    if nom or email_addr:
        existing = check_prospect_exists(nom, "", email_addr)
        if existing and existing.get("found"):
            logger.info(f"⚠️ Prospect existe déjà, création annulée")
            return {
                "created": False,
                "reason": "doublon",
                "existing_card": existing
            }
    
    # 2. Rechercher le bien
    ville = prospect.get("ville") or extract_ville_from_email(
        prospect.get("raw_subject", ""),
        prospect.get("message", "")
    )
    
    bien_trello = find_property_on_trello(ville=ville, reference=prospect.get("bien_ref"))
    site_url = find_property_on_website(ville)
    
    # 3. Construire le nom de la carte
    if nom:
        parts = nom.split()
        if len(parts) >= 2:
            card_name = f"{parts[0].upper()} {' '.join(parts[1:])}"
        else:
            card_name = nom.upper()
    else:
        card_name = email_addr.split("@")[0].upper() if email_addr else "PROSPECT"
    
    # 4. Construire la description (SANS le message)
    desc_parts = ["**Contact**"]
    desc_parts.append(f"- Tél : {prospect.get('tel', '-')}")
    desc_parts.append(f"- Email : {prospect.get('email', '-')}")
    desc_parts.append(f"- Source : {prospect.get('source', '-')}")
    desc_parts.append("")
    
    desc_parts.append("**Bien demandé**")
    if prospect.get("bien_ref"):
        desc_parts.append(f"- Référence : {prospect.get('bien_ref')}")
    if prospect.get("bien_titre"):
        desc_parts.append(f"- Titre : {prospect.get('bien_titre')}")
    if prospect.get("bien_prix"):
        desc_parts.append(f"- Prix : {prospect.get('bien_prix')} €")
    if ville:
        desc_parts.append(f"- Ville : {ville}")
    
    if bien_trello:
        desc_parts.append(f"- 🔗 Carte Trello bien : {bien_trello.get('card_url')}")
    if site_url:
        desc_parts.append(f"- 🌐 Site ICI Dordogne : {site_url}")
    
    desc_parts.append("")
    desc_parts.append("---")
    desc_parts.append(f"*Créé automatiquement par Axi le {datetime.now().strftime('%d/%m/%Y %H:%M')}*")
    
    description = "\n".join(desc_parts)
    
    # 5. Déterminer les membres à assigner
    members_to_assign = [JULIE_ID]
    
    if bien_trello and bien_trello.get("members"):
        for member_id in bien_trello.get("members"):
            if member_id not in members_to_assign:
                members_to_assign.append(member_id)
    
    # 6. Créer la carte (SANS description - sera écrasée par template de liste)
    card_data = {
        "idList": LIST_SUIVI_CLIENTS,
        "name": card_name,
        "pos": "top",
        "idMembers": ",".join(members_to_assign),
        "idLabels": f"{LABEL_PAS_SWEEPBRIGHT},{LABEL_PAS_TRAITE}"
    }
    
    logger.info(f"📝 Création carte: {card_name}")
    logger.info(f"   Liste: TEST ACQUÉREURS (Pros LUDO)")
    logger.info(f"   Membres: {len(members_to_assign)}")
    logger.info(f"   Labels: Pas dans Sweepbright, Pas traité")
    
    card_result = trello_post("/cards", card_data)
    
    if not card_result:
        logger.error("Échec création carte")
        return None
    
    card_id = card_result.get("id")
    card_url = card_result.get("url")
    
    logger.info(f"✅ Carte créée: {card_url}")
    
    # 6b. ATTENDRE puis PUT pour écraser le template de liste avec la vraie description
    time.sleep(1)
    put_result = trello_put(f"/cards/{card_id}", {"desc": description})
    if put_result:
        logger.info(f"   📝 Description mise à jour via PUT")
    else:
        logger.warning(f"   ⚠️ Échec PUT description")
    
    # 7. Ajouter le message en COMMENTAIRE
    message = prospect.get("message")
    if message and message.strip():
        comment_text = f"📩 **Message du prospect:**\n\n{message}"
        comment_result = trello_post(f"/cards/{card_id}/actions/comments", {"text": comment_text})
        if comment_result:
            logger.info(f"   💬 Commentaire ajouté")
        else:
            logger.warning(f"   ⚠️ Échec ajout commentaire")
    
    # 8. Ajouter les checklists
    add_checklists(card_id)
    
    return {
        "created": True,
        "card_id": card_id,
        "card_url": card_url,
        "card_name": card_name,
        "members_count": len(members_to_assign),
        "bien_found": bien_trello is not None
    }


def add_checklists(card_id: str):
    """Ajoute les checklists standard à la carte."""
    try:
        checklists = [
            ("Avant la visite", [
                "RDV validé avec l'acquéreur",
                "Bon de visite signé reçu",
                "RDV dans Sweep",
                "Bon de visite envoyé",
                "RDV validé avec le propriétaire"
            ]),
            ("Après la visite", [
                "CR Proprio",
                "CR Trello",
                "Autres biens à proposer"
            ])
        ]
        
        for cl_name, items in checklists:
            cl_result = trello_post(f"/cards/{card_id}/checklists", {"name": cl_name})
            
            if cl_result:
                cl_id = cl_result.get("id")
                for item in items:
                    trello_post(f"/checklists/{cl_id}/checkItems", {"name": item})
    
    except Exception as e:
        logger.warning(f"Erreur ajout checklists: {e}")


# =============================================================================
# PARSERS EMAIL
# =============================================================================

def parse_sweepbright(body: str, subject: str) -> Optional[Dict]:
    """Parse un email SweepBright."""
    try:
        data = {
            "source": "SweepBright",
            "nom": None,
            "email": None,
            "tel": None,
            "message": None,
            "bien_titre": None,
            "bien_ref": None,
            "ville": None
        }
        
        nom_match = re.search(r'(?:Nom|Name)\s*:\s*([^\n<]+)', body, re.IGNORECASE)
        if nom_match:
            data["nom"] = nom_match.group(1).strip()
        
        email_match = re.search(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', body)
        if email_match:
            data["email"] = email_match.group(1)
        
        tel_match = re.search(r'(\+?\d[\d\s\-\.]{8,})', body)
        if tel_match:
            data["tel"] = re.sub(r'[^\d+]', '', tel_match.group(1))
        
        msg_match = re.search(r'(?:Message|Commentaire)\s*:\s*([^\n]+(?:\n(?![A-Z]).*)*)', body, re.IGNORECASE)
        if msg_match:
            data["message"] = msg_match.group(1).strip()
        
        ville_match = re.search(r'(\d+,?\s*)?(\d{5})\s+([A-Za-zÀ-ÿ\-\s]+)', subject)
        if ville_match:
            data["ville"] = ville_match.group(3).strip()
            data["bien_ref"] = ville_match.group(2)
        
        if data["email"] or data["tel"]:
            return data
        return None
        
    except Exception as e:
        logger.error(f"Erreur parse SweepBright: {e}")
        return None


def parse_leboncoin(body: str, subject: str) -> Optional[Dict]:
    """Parse un email Leboncoin."""
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
        
        nom_match = re.search(r'Nom\s*:\s*([^\n<]+)', body, re.IGNORECASE)
        if nom_match:
            data["nom"] = nom_match.group(1).strip()
        
        email_match = re.search(r'E-mail\s*:\s*([^\s<>]+@[^\s<>]+)', body, re.IGNORECASE)
        if email_match:
            data["email"] = email_match.group(1).strip()
        
        tel_match = re.search(r'T[éè]l[éè]phone\s*:\s*([+\d\s\-\.]+)', body, re.IGNORECASE)
        if tel_match:
            data["tel"] = re.sub(r'[^\d+]', '', tel_match.group(1))
        
        msg_match = re.search(r'[«"]([^»"]+)[»"]', body)
        if msg_match:
            data["message"] = msg_match.group(1).strip()
        
        prix_match = re.search(r'(\d[\d\s]*)\s*€', subject + " " + body)
        if prix_match:
            data["bien_prix"] = re.sub(r'\s', '', prix_match.group(1))
        
        ville_match = re.search(r'Ville\s*:\s*([^\n<]+)', body, re.IGNORECASE)
        if ville_match:
            data["ville"] = ville_match.group(1).strip()
        
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
        
        email_match = re.search(r'<([^>]+)>', from_addr)
        if email_match:
            data["email"] = email_match.group(1)
        elif "@" in from_addr:
            data["email"] = from_addr.split()[0] if " " in from_addr else from_addr
        
        tel_match = re.search(r'(\+?\d[\d\s\-\.]{8,})', body)
        if tel_match:
            data["tel"] = re.sub(r'[^\d+]', '', tel_match.group(1))
        
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
        mail.select("INBOX")
        
        status, messages = mail.search(None, "(UNSEEN)")
        unread_ids = messages[0].split()
        
        logger.info(f"📬 {len(unread_ids)} emails non lus")
        
        for mail_id in unread_ids:
            try:
                status, msg_data = mail.fetch(mail_id, "(RFC822)")
                
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        
                        subject_raw = msg.get("Subject", "")
                        subject, encoding = decode_header(subject_raw)[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding or "utf-8", errors='ignore')
                        
                        from_addr = msg.get("From", "")
                        body = get_email_body(msg)
                        
                        prospect = None
                        
                        if "sweepbright" in from_addr.lower() or "noreply@sweepbright" in from_addr.lower():
                            prospect = parse_sweepbright(body, subject)
                        elif "leboncoin" in from_addr.lower() or "leboncoin" in subject.lower():
                            prospect = parse_leboncoin(body, subject)
                        elif "seloger" in from_addr.lower() or "seloger" in subject.lower():
                            prospect = parse_seloger(body, subject)
                        elif any(kw in subject.lower() for kw in ["contact", "demande", "visite", "information", "intéressé"]):
                            prospect = parse_generic(body, subject, from_addr)
                        
                        if prospect:
                            prospect["raw_subject"] = subject
                            prospect["raw_from"] = from_addr
                            prospect["date"] = msg.get("Date", "")
                            prospect["mail_id"] = mail_id
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
    """Fonction principale: vérifie emails et crée cartes Trello enrichies."""
    result = {
        "version": EMAIL_WATCHER_VERSION,
        "timestamp": datetime.now().isoformat(),
        "emails_checked": 0,
        "prospects_found": 0,
        "cards_created": 0,
        "doublons_ignores": 0,
        "errors": [],
        "cards": []
    }
    
    try:
        prospects = check_emails()
        result["prospects_found"] = len(prospects)
        
        for prospect in prospects:
            card_result = create_enriched_prospect_card(prospect)
            
            if card_result:
                if card_result.get("created"):
                    result["cards_created"] += 1
                    result["cards"].append({
                        "name": card_result.get("card_name"),
                        "url": card_result.get("card_url")
                    })
                elif card_result.get("reason") == "doublon":
                    result["doublons_ignores"] += 1
            else:
                result["errors"].append(f"Échec création carte pour {prospect.get('email')}")
        
        logger.info(f"📊 Résultat: {result['prospects_found']} prospects, "
                   f"{result['cards_created']} cartes créées, "
                   f"{result['doublons_ignores']} doublons ignorés")
        
    except Exception as e:
        result["errors"].append(str(e))
        logger.error(f"Erreur process_new_emails: {e}")
    
    return result


# =============================================================================
# ENDPOINTS HTTP
# =============================================================================

def handle_check_emails(params: Dict) -> Tuple[int, Dict]:
    """Handler pour endpoint /emails/check"""
    result = process_new_emails()
    return 200, result


def handle_email_status(params: Dict) -> Tuple[int, Dict]:
    """Handler pour endpoint /emails/status"""
    return 200, {
        "service": "Email Watcher V2",
        "version": EMAIL_WATCHER_VERSION,
        "imap_email": IMAP_EMAIL,
        "trello_board": BOARD_ACQUEREURS,
        "trello_list": LIST_SUIVI_CLIENTS,
        "labels": [LABEL_PAS_SWEEPBRIGHT, LABEL_PAS_TRAITE],
        "status": "ready"
    }


# =============================================================================
# MOVE EMAIL TO LABEL
# =============================================================================

def move_email_to_label(email_from: str = '', subject_contains: str = '', label: str = None) -> Dict:
    """Déplace un email de INBOX vers un label Gmail."""
    target_label = label or LABEL_ACQUEREURS
    
    try:
        logger.info(f"📧 Déplacement email vers {target_label}...")
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(IMAP_EMAIL, IMAP_PASSWORD)
        mail.select("INBOX")
        
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
            return {"success": False, "moved": 0, "message": "Aucun email trouvé"}
        
        email_ids = messages[0].split()
        moved_count = 0
        errors = []
        
        for email_id in email_ids[-5:]:
            try:
                imap_label = LABEL_ACQUEREURS_IMAP if 'ACQUÉREURS' in target_label else target_label
                copy_result = mail.copy(email_id, imap_label)
                
                if copy_result[0] == 'OK':
                    mail.store(email_id, '+FLAGS', '\\Deleted')
                    moved_count += 1
                else:
                    errors.append(f"COPY {email_id} failed: {copy_result}")
            except Exception as e:
                errors.append(f"Email {email_id}: {str(e)}")
                continue
        
        mail.expunge()
        mail.logout()
        
        result = {
            "version": EMAIL_WATCHER_VERSION,
            "success": moved_count > 0,
            "moved": moved_count,
            "total_found": len(email_ids),
            "label": target_label,
            "message": f"{moved_count} email(s) déplacé(s) vers {target_label}"
        }
        if errors:
            result["errors"] = errors
        return result
        
    except Exception as e:
        logger.error(f"❌ Erreur: {e}")
        return {"success": False, "error": str(e)}


def debug_imap_search(query=None, body=None, headers=None) -> Tuple[int, Dict]:
    """Debug: voir ce que contient INBOX via IMAP"""
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(IMAP_EMAIL, IMAP_PASSWORD)
        
        status, folders = mail.list()
        folder_names = [f.decode('utf-8', errors='ignore') for f in folders[:15]]
        
        status, count = mail.select('INBOX')
        inbox_count = count[0].decode() if count else '0'
        
        status, messages = mail.search(None, 'ALL')
        all_ids = messages[0].split() if messages[0] else []
        
        last_emails = []
        for eid in all_ids[-5:]:
            try:
                status, data = mail.fetch(eid, '(BODY[HEADER.FIELDS (SUBJECT FROM)])')
                if data and data[0]:
                    header = data[0][1].decode('utf-8', errors='ignore')
                    last_emails.append(header.strip()[:150])
            except:
                pass
        
        mail.logout()
        
        return 200, {
            "version": EMAIL_WATCHER_VERSION,
            "inbox_total": inbox_count,
            "all_emails_count": len(all_ids),
            "last_5_emails": last_emails,
            "folders_sample": folder_names[:10]
        }
        
    except Exception as e:
        return 500, {"error": str(e)}


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


# =============================================================================
# POINT D'ENTRÉE TEST
# =============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = process_new_emails()
    print(json.dumps(result, indent=2, ensure_ascii=False))
