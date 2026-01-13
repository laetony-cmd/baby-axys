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
import html
from email.header import decode_header
from datetime import datetime
from typing import Optional, List, Dict, Tuple

# =============================================================================
# UTILITAIRES EMAIL (ajouté 13/01/2026 - recommandé par Lumo)
# =============================================================================

def is_reply_email(subject: str) -> bool:
    """Détecte si l'email est une réponse (Re:, Fwd:, etc.)"""
    if not subject:
        return False
    subject_lower = subject.lower().strip()
    return subject_lower.startswith("re:") or subject_lower.startswith("fwd:") or subject_lower.startswith("tr:")


def extract_name_from_header(from_header: str) -> Optional[str]:
    """
    Extrait le nom depuis un header From.
    Exemple: "Sonia Sharpe <sharpe32@hotmail.com>" -> "Sonia Sharpe"
    """
    if not from_header:
        return None
    
    try:
        # Décoder le header MIME si nécessaire
        decoded_parts = decode_header(from_header)
        decoded_str = ""
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                decoded_str += part.decode(encoding or 'utf-8', errors='ignore')
            else:
                decoded_str += str(part)
        
        # Extraire le nom avant le <email>
        match = re.search(r'^([^<]+)<', decoded_str)
        if match:
            name = match.group(1).strip()
            # Nettoyer les guillemets
            name = name.strip('"\'')
            if name and len(name) > 1:
                return name
        
        return None
    except Exception:
        return None


def clean_html_entities(text: str) -> str:
    """Nettoie les entités HTML d'un texte."""
    if not text:
        return text
    # Utiliser html.unescape pour les entités HTML
    text = html.unescape(text)
    # Supprimer les balises HTML restantes
    text = re.sub(r'<[^>]+>', ' ', text)
    # Normaliser les espaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def format_prospect_name(name: str) -> str:
    """
    Formate un nom en "NOM Prénom".
    Exemple: "Sonia Sharpe" -> "SHARPE Sonia"
    """
    if not name:
        return "PROSPECT"
    
    # Nettoyer
    name = clean_html_entities(name)
    name = name[:50]  # Limiter à 50 caractères
    
    parts = name.split()
    if len(parts) >= 2:
        # Supposer que le dernier mot est le nom de famille
        return f"{parts[-1].upper()} {' '.join(parts[:-1])}"
    elif len(parts) == 1:
        return parts[0].upper()
    return "PROSPECT"


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
    
    # 3. Construire le nom de la carte (utilise les fonctions utilitaires)
    # Priorité: nom parsé → nom du From → email
    if not nom or len(nom) > 50:
        # Fallback: extraire depuis le champ From
        raw_from = prospect.get("raw_from", "")
        nom = extract_name_from_header(raw_from)
    
    # Formater le nom en "NOM Prénom"
    if nom:
        card_name = format_prospect_name(nom)
    else:
        card_name = email_addr.split("@")[0].upper() if email_addr else "PROSPECT"
    
    # Limiter le nom de carte à 100 caractères
    if len(card_name) > 100:
        card_name = card_name[:97] + "..."
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
    
    # 6b. ATTENDRE que Butler finisse puis PUT pour écraser avec la vraie description
    time.sleep(5)  # Butler applique son template, on attend qu'il finisse
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
    """Parse un email Leboncoin - VERSION AMÉLIORÉE V2."""
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
        
        # Nettoyer le body HTML
        clean_body = re.sub(r'<[^>]+>', ' ', body)
        clean_body = re.sub(r'&nbsp;', ' ', clean_body)
        clean_body = re.sub(r'\s+', ' ', clean_body).strip()
        
        # Pattern Leboncoin original: "Nom : XXX"
        nom_match = re.search(r'Nom\s*:\s*([A-Za-zÀ-ÿ\-\s]+?)(?:\s+E-mail|\s+Ville|\s+Téléphone|$)', clean_body, re.IGNORECASE)
        if nom_match:
            nom = nom_match.group(1).strip()
            # Limiter à 50 caractères max
            data["nom"] = nom[:50] if len(nom) > 50 else nom
        
        # Email
        email_match = re.search(r'E-mail\s*:\s*([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', clean_body, re.IGNORECASE)
        if email_match:
            data["email"] = email_match.group(1).strip()
        else:
            # Fallback: chercher n'importe quel email dans le body
            any_email = re.search(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', clean_body)
            if any_email:
                email_found = any_email.group(1)
                # Exclure les emails de l'agence et de leboncoin
                if not any(x in email_found.lower() for x in ['icidordogne', 'leboncoin', 'noreply']):
                    data["email"] = email_found
        
        # Téléphone
        tel_match = re.search(r'T[éè]l[éè]phone\s*:\s*([+\d\s\-\.]+)', clean_body, re.IGNORECASE)
        if tel_match:
            data["tel"] = re.sub(r'[^\d+]', '', tel_match.group(1))
        else:
            # Fallback: chercher un numéro français
            tel_fallback = re.search(r'(\+33|0[67])\s*[\d\s\.\-]{8,}', clean_body)
            if tel_fallback:
                data["tel"] = re.sub(r'[^\d+]', '', tel_fallback.group(0))
        
        # Message entre guillemets
        msg_match = re.search(r'[«"]([^»"]{10,200})[»"]', clean_body)
        if msg_match:
            data["message"] = msg_match.group(1).strip()
        
        # Prix
        prix_match = re.search(r'(\d[\d\s]{0,10})\s*€', subject + " " + clean_body)
        if prix_match:
            data["bien_prix"] = re.sub(r'\s', '', prix_match.group(1))
        
        # Ville - pattern Leboncoin: "Ville : XXX"
        ville_match = re.search(r'Ville\s*:\s*([A-Za-zÀ-ÿ\-\s]+?)(?:\s+[«"]|\s+Répondre|\s+Maison|\s+$)', clean_body, re.IGNORECASE)
        if ville_match:
            ville = ville_match.group(1).strip()
            data["ville"] = ville[:30] if len(ville) > 30 else ville
        
        # Référence Leboncoin
        ref_match = re.search(r'R[ée]f[ée]rence\s*:\s*([A-Z0-9\-]+)', clean_body, re.IGNORECASE)
        if ref_match:
            data["bien_ref"] = ref_match.group(1)
        
        # Titre du bien depuis le sujet
        titre_match = re.search(r'pour\s+"([^"]+)"', subject)
        if titre_match:
            data["bien_titre"] = titre_match.group(1)
        
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


# =============================================================================
# SCAN ALL EMAILS (TEST ENDPOINT)
# =============================================================================

def scan_all_emails_in_inbox() -> List[Dict]:
    """
    Scanne TOUS les emails de INBOX (pas seulement UNSEEN).
    Retourne les prospects détectés SANS créer de cartes.
    Pour test uniquement.
    """
    prospects = []
    
    try:
        logger.info(f"📧 [SCAN-ALL] Connexion IMAP {IMAP_EMAIL}...")
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(IMAP_EMAIL, IMAP_PASSWORD)
        mail.select("INBOX")
        
        # TOUS les emails (pas seulement UNSEEN)
        status, messages = mail.search(None, "ALL")
        email_ids = messages[0].split() if messages[0] else []
        
        logger.info(f"📬 [SCAN-ALL] {len(email_ids)} emails dans INBOX")
        
        for mail_id in email_ids:
            try:
                status, msg_data = mail.fetch(mail_id, "(RFC822)")
                
                # Vérifier si lu ou non
                flags_data = mail.fetch(mail_id, "(FLAGS)")
                is_seen = b"\\Seen" in flags_data[1][0] if flags_data[1] else False
                
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        
                        subject_raw = msg.get("Subject", "")
                        subject, encoding = decode_header(subject_raw)[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding or "utf-8", errors='ignore')
                        
                        from_addr = msg.get("From", "")
                        date_str = msg.get("Date", "")
                        body = get_email_body(msg)
                        
                        # Détecter le type
                        prospect_type = "unknown"
                        prospect = None
                        
                        if "sweepbright" in from_addr.lower() or "noreply@sweepbright" in from_addr.lower():
                            prospect_type = "sweepbright"
                            prospect = parse_sweepbright(body, subject)
                        elif "leboncoin" in from_addr.lower() or "leboncoin" in subject.lower():
                            prospect_type = "leboncoin"
                            prospect = parse_leboncoin(body, subject)
                        elif "seloger" in from_addr.lower() or "seloger" in subject.lower():
                            prospect_type = "seloger"
                            prospect = parse_seloger(body, subject)
                        elif any(kw in subject.lower() for kw in ["contact", "demande", "visite", "information", "intéressé"]):
                            prospect_type = "generic"
                            prospect = parse_generic(body, subject, from_addr)
                        
                        email_info = {
                            "mail_id": mail_id.decode(),
                            "subject": subject,
                            "from": from_addr,
                            "date": date_str,
                            "is_read": is_seen,
                            "is_reply": is_reply_email(subject),
                            "prospect_type": prospect_type,
                            "body_preview": body[:500] if body else "",
                            "parsed_data": prospect
                        }
                        
                        prospects.append(email_info)
                        
                        if prospect:
                            logger.info(f"🔥 [SCAN-ALL] Prospect détecté: {prospect.get('nom', prospect.get('email', 'inconnu'))} ({prospect_type})")
                        
            except Exception as e:
                logger.error(f"[SCAN-ALL] Erreur email {mail_id}: {e}")
                continue
        
        mail.logout()
        
    except Exception as e:
        logger.error(f"❌ [SCAN-ALL] Erreur IMAP: {e}")
    
    return prospects


def handle_scan_all(query=None, body=None, headers=None) -> Tuple[int, Dict]:
    """
    Handler pour endpoint GET /emails/scan-all
    Scanne TOUS les emails, retourne les prospects détectés SANS créer de cartes.
    """
    try:
        prospects = scan_all_emails_in_inbox()
        
        # Filtrer ceux qui sont des prospects valides
        valid_prospects = [p for p in prospects if p.get("parsed_data")]
        
        return 200, {
            "version": EMAIL_WATCHER_VERSION,
            "endpoint": "scan-all (TEST)",
            "timestamp": datetime.now().isoformat(),
            "total_emails": len(prospects),
            "prospects_detected": len(valid_prospects),
            "emails": prospects,
            "note": "Mode TEST - Aucune carte créée"
        }
    
    except Exception as e:
        return 500, {"error": str(e)}



# =============================================================================
# TEST: SCAN FOLDER ACQUÉREURS ET CRÉER CARTE
# =============================================================================

def scan_folder_and_create_card(folder: str = "**ACQU&AMk-REURS", limit: int = 5) -> Dict:
    """
    Scanne un dossier Gmail spécifique et crée une carte Trello pour le premier prospect trouvé.
    Pour TEST uniquement - sur board Pros LUDO.
    """
    result = {
        "version": EMAIL_WATCHER_VERSION,
        "folder": folder,
        "timestamp": datetime.now().isoformat(),
        "emails_scanned": 0,
        "prospect_found": None,
        "card_created": None,
        "errors": []
    }
    
    try:
        logger.info(f"📧 [TEST] Connexion IMAP - dossier: {folder}")
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(IMAP_EMAIL, IMAP_PASSWORD)
        
        # Sélectionner le dossier spécifique
        status, count = mail.select(folder)
        if status != 'OK':
            result["errors"].append(f"Impossible de sélectionner le dossier: {folder}")
            mail.logout()
            return result
        
        folder_count = count[0].decode() if count else '0'
        logger.info(f"📬 [TEST] {folder_count} emails dans {folder}")
        
        # Récupérer les derniers emails
        status, messages = mail.search(None, "ALL")
        email_ids = messages[0].split() if messages[0] else []
        
        # Prendre les N derniers
        recent_ids = email_ids[-limit:] if len(email_ids) > limit else email_ids
        recent_ids = recent_ids[::-1]  # Plus récent en premier
        
        result["emails_scanned"] = len(recent_ids)
        
        for mail_id in recent_ids:
            try:
                status, msg_data = mail.fetch(mail_id, "(RFC822)")
                
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        
                        subject_raw = msg.get("Subject", "")
                        subject, encoding = decode_header(subject_raw)[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding or "utf-8", errors='ignore')
                        
                        
                        # Ignorer les réponses (Re:, Fwd:, Tr:)
                        if is_reply_email(subject):
                            logger.info(f"⏭️ [TEST] Email ignoré (réponse): {subject[:50]}")
                            continue
                        from_addr = msg.get("From", "")
                        date_str = msg.get("Date", "")
                        body = get_email_body(msg)
                        
                        # Parser selon la source
                        prospect = None
                        source_type = "unknown"
                        
                        if "sweepbright" in from_addr.lower():
                            source_type = "sweepbright"
                            prospect = parse_sweepbright(body, subject)
                        elif "leboncoin" in from_addr.lower() or "leboncoin" in subject.lower():
                            source_type = "leboncoin"
                            prospect = parse_leboncoin(body, subject)
                        elif "seloger" in from_addr.lower():
                            source_type = "seloger"
                            prospect = parse_seloger(body, subject)
                        else:
                            # Parser générique pour les emails du dossier ACQUÉREURS
                            source_type = "generic"
                            prospect = parse_generic(body, subject, from_addr)
                        
                        if prospect:
                            prospect["raw_subject"] = subject
                            prospect["raw_from"] = from_addr
                            prospect["date"] = date_str
                            prospect["source_type"] = source_type
                            
                            result["prospect_found"] = {
                                "subject": subject,
                                "from": from_addr,
                                "date": date_str,
                                "source_type": source_type,
                                "parsed_data": prospect
                            }
                            
                            logger.info(f"🔥 [TEST] Prospect trouvé: {prospect.get('nom', prospect.get('email'))}")
                            
                            # Créer la carte Trello
                            card_result = create_enriched_prospect_card(prospect)
                            result["card_created"] = card_result
                            
                            mail.logout()
                            return result
                        
            except Exception as e:
                result["errors"].append(f"Erreur email {mail_id}: {str(e)}")
                continue
        
        mail.logout()
        result["errors"].append("Aucun prospect valide trouvé dans les emails scannés")
        
    except Exception as e:
        result["errors"].append(f"Erreur IMAP: {str(e)}")
    
    return result


def handle_test_create_card(query=None, body=None, headers=None) -> Tuple[int, Dict]:
    """
    Handler pour endpoint GET /emails/test-create-card
    Scanne le dossier ACQUÉREURS et crée une carte pour le premier prospect.
    """
    folder = "**ACQU&AMk-REURS"  # Dossier ACQUÉREURS encodé IMAP
    limit = 10
    
    if query:
        if 'folder' in query:
            folder = query['folder'][0] if isinstance(query['folder'], list) else query['folder']
        if 'limit' in query:
            limit = int(query['limit'][0] if isinstance(query['limit'], list) else query['limit'])
    
    result = scan_folder_and_create_card(folder, limit)
    status_code = 200 if result.get("card_created") else 400
    return status_code, result



# =============================================================================
# V2 FUNCTIONS - WORKFLOW AMÉLIORÉ (13/01/2026)
# =============================================================================
# Ces fonctions sont NOUVELLES et ne modifient PAS le code existant.
# Elles seront activées après validation via l'endpoint /emails/v2/test
# =============================================================================

def v2_check_prospect_exists(nom: str, email_addr: str = "") -> Dict:
    """
    V2: Vérifie si un prospect existe déjà dans Trello.
    NOUVEAU: Distingue carte ACTIVE vs ARCHIVÉE.
    
    Returns:
        {
            "found": bool,
            "status": "active" | "archived" | "not_found",
            "card_id": str | None,
            "card_url": str | None,
            "card_name": str | None,
            "board_id": str | None
        }
    """
    result = {
        "found": False,
        "status": "not_found",
        "card_id": None,
        "card_url": None,
        "card_name": None,
        "board_id": None
    }
    
    search_terms = []
    if nom:
        search_terms.append(nom.upper())
    if email_addr and "@" in email_addr:
        search_terms.append(email_addr.split("@")[0])
    
    if not search_terms:
        return result
    
    query = " ".join(search_terms[:2])
    logger.info(f"🔍 [V2] Recherche prospect: '{query}'")
    
    # Chercher avec cards:all pour inclure les archivées
    search_result = trello_get(
        f"/search?query={urllib.parse.quote(query)}&modelTypes=cards"
        f"&card_fields=name,shortUrl,idBoard,closed&cards_limit=20"
    )
    
    if not search_result or not search_result.get("cards"):
        logger.info(f"  → Aucun résultat")
        return result
    
    nom_upper = nom.upper() if nom else ""
    
    for card in search_result.get("cards", []):
        card_name = card.get("name", "").upper()
        
        if nom_upper and nom_upper in card_name:
            result["found"] = True
            result["card_id"] = card.get("id")
            result["card_url"] = card.get("shortUrl")
            result["card_name"] = card.get("name")
            result["board_id"] = card.get("idBoard")
            
            if card.get("closed"):
                result["status"] = "archived"
                logger.info(f"  → ARCHIVÉE trouvée: {card.get('name')}")
            else:
                result["status"] = "active"
                logger.info(f"  → ACTIVE trouvée: {card.get('name')}")
            
            return result
    
    logger.info(f"  → Aucune correspondance exacte")
    return result


def v2_unarchive_and_update(card_id: str, new_info: Dict) -> Dict:
    """
    V2: Désarchive une carte et ajoute les nouvelles infos.
    
    Args:
        card_id: ID de la carte archivée
        new_info: Nouvelles infos du prospect (email, tel, message, etc.)
    
    Returns:
        {"success": bool, "card_url": str, "action": str}
    """
    logger.info(f"🔄 [V2] Désarchivage carte {card_id}")
    
    # 1. Désarchiver la carte
    unarchive_result = trello_put(f"/cards/{card_id}", {"closed": "false"})
    
    if not unarchive_result:
        logger.error(f"  → Échec désarchivage")
        return {"success": False, "error": "Échec désarchivage"}
    
    logger.info(f"  → Carte désarchivée")
    
    # 2. Ajouter un commentaire avec les nouvelles infos
    comment_parts = [f"📩 **Nouvelle demande reçue le {datetime.now().strftime('%d/%m/%Y %H:%M')}**"]
    comment_parts.append("")
    
    if new_info.get("source"):
        comment_parts.append(f"**Source:** {new_info.get('source')}")
    if new_info.get("email"):
        comment_parts.append(f"**Email:** {new_info.get('email')}")
    if new_info.get("tel"):
        comment_parts.append(f"**Tél:** {new_info.get('tel')}")
    if new_info.get("message"):
        comment_parts.append(f"**Message:** {new_info.get('message')}")
    if new_info.get("bien_ville"):
        comment_parts.append(f"**Bien demandé:** {new_info.get('bien_ville')}")
    if new_info.get("bien_prix"):
        comment_parts.append(f"**Prix:** {new_info.get('bien_prix')} €")
    
    comment_parts.append("")
    comment_parts.append("*Carte désarchivée automatiquement par Axi*")
    
    comment_text = "\n".join(comment_parts)
    comment_result = trello_post(f"/cards/{card_id}/actions/comments", {"text": comment_text})
    
    if comment_result:
        logger.info(f"  → Commentaire ajouté")
    
    # 3. Remettre le label "Pas traité"
    trello_post(f"/cards/{card_id}/idLabels", {"value": LABEL_PAS_TRAITE})
    
    return {
        "success": True,
        "card_id": card_id,
        "card_url": unarchive_result.get("shortUrl"),
        "action": "unarchived_and_updated"
    }


def v2_search_property_on_site(ville: str, prix: str = None) -> Optional[Dict]:
    """
    V2: Recherche un bien sur icidordogne.fr par ville et prix.
    Retourne la référence du bien si trouvé.
    
    Args:
        ville: Nom de la ville
        prix: Prix approximatif (optionnel)
    
    Returns:
        {
            "found": bool,
            "reference": str | None,
            "url": str | None,
            "title": str | None
        }
    """
    result = {
        "found": False,
        "reference": None,
        "url": None,
        "title": None
    }
    
    if not ville:
        return result
    
    logger.info(f"🌐 [V2] Recherche sur icidordogne.fr: ville={ville}, prix={prix}")
    
    # Construire l'URL de recherche
    search_url = f"https://www.icidordogne.fr/?s={urllib.parse.quote(ville)}"
    
    try:
        req = urllib.request.Request(search_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        with urllib.request.urlopen(req, timeout=15) as response:
            html_content = response.read().decode('utf-8', errors='ignore')
        
        # Chercher les références de biens (format: REF-XXXXX ou juste des nombres)
        # Pattern pour trouver les liens de biens
        bien_links = re.findall(r'href="(https://www\.icidordogne\.fr/[^"]+)"[^>]*>([^<]+)</a>', html_content)
        
        # Chercher les références SweepBright (5 chiffres)
        references = re.findall(r'\b(\d{5})\b', html_content)
        
        if bien_links:
            # Prendre le premier lien qui ressemble à un bien
            for link, title in bien_links:
                if ville.lower() in link.lower() or ville.lower() in title.lower():
                    result["found"] = True
                    result["url"] = link
                    result["title"] = title.strip()
                    
                    # Chercher la référence dans le lien ou le titre
                    ref_match = re.search(r'\b(\d{5})\b', link + " " + title)
                    if ref_match:
                        result["reference"] = ref_match.group(1)
                    
                    logger.info(f"  → Trouvé: {title[:50]} - Ref: {result['reference']}")
                    return result
        
        # Fallback: si on a trouvé des références
        if references:
            result["reference"] = references[0]
            result["url"] = search_url
            logger.info(f"  → Référence possible trouvée: {references[0]}")
            return result
        
        logger.info(f"  → Aucun bien trouvé sur le site")
        
    except Exception as e:
        logger.error(f"  → Erreur scraping: {e}")
    
    return result


def v2_search_property_all_boards(reference: str = None, ville: str = None, prix: str = None) -> Optional[Dict]:
    """
    V2: Recherche un bien sur Trello - d'abord board BIENS, puis TOUS les boards.
    
    Args:
        reference: Référence SweepBright (prioritaire)
        ville: Nom de la ville (fallback)
        prix: Prix (pour affiner)
    
    Returns:
        {
            "found": bool,
            "card_id": str | None,
            "card_url": str | None,
            "card_name": str | None,
            "members": list,
            "board_name": str | None
        }
    """
    result = {
        "found": False,
        "card_id": None,
        "card_url": None,
        "card_name": None,
        "members": [],
        "board_name": None
    }
    
    search_query = reference if reference else ville
    if not search_query:
        return result
    
    logger.info(f"🏠 [V2] Recherche bien Trello: query='{search_query}'")
    
    # Étape 1: Chercher sur le board BIENS
    search_result = trello_get(
        f"/search?query={urllib.parse.quote(search_query)}"
        f"&modelTypes=cards"
        f"&board_ids={BOARD_BIENS}"
        f"&card_fields=name,shortUrl,idMembers,closed,idBoard"
    )
    
    if search_result and search_result.get("cards"):
        for card in search_result.get("cards", []):
            if not card.get("closed"):
                result["found"] = True
                result["card_id"] = card.get("id")
                result["card_url"] = card.get("shortUrl")
                result["card_name"] = card.get("name")
                result["members"] = card.get("idMembers", [])
                result["board_name"] = "BIENS"
                logger.info(f"  → Trouvé sur BIENS: {card.get('name')[:50]}")
                return result
    
    # Étape 2: Si pas trouvé, chercher sur TOUS les boards
    logger.info(f"  → Pas sur BIENS, recherche sur tous les boards...")
    
    search_all = trello_get(
        f"/search?query={urllib.parse.quote(search_query)}"
        f"&modelTypes=cards"
        f"&card_fields=name,shortUrl,idMembers,closed,idBoard"
        f"&cards_limit=20"
    )
    
    if search_all and search_all.get("cards"):
        for card in search_all.get("cards", []):
            if not card.get("closed"):
                result["found"] = True
                result["card_id"] = card.get("id")
                result["card_url"] = card.get("shortUrl")
                result["card_name"] = card.get("name")
                result["members"] = card.get("idMembers", [])
                result["board_name"] = f"Board {card.get('idBoard')}"
                logger.info(f"  → Trouvé sur autre board: {card.get('name')[:50]}")
                return result
    
    logger.info(f"  → Bien non trouvé sur Trello")
    return result


def v2_format_card_name(nom: str, tel: str = None) -> str:
    """
    V2: Formate le nom de la carte avec téléphone si présent.
    Exemple: "DUPONT Jean - 0612345678"
    
    Args:
        nom: Nom du prospect (déjà formaté "NOM Prénom")
        tel: Numéro de téléphone (optionnel)
    
    Returns:
        Nom formaté pour la carte
    """
    if not nom:
        return "PROSPECT"
    
    # Nettoyer le nom
    card_name = clean_html_entities(nom)
    card_name = format_prospect_name(card_name)
    
    # Ajouter le téléphone si présent
    if tel:
        # Nettoyer le numéro
        tel_clean = re.sub(r'[^\d+]', '', tel)
        if len(tel_clean) >= 10:
            card_name = f"{card_name} - {tel_clean}"
    
    # Limiter à 100 caractères
    if len(card_name) > 100:
        card_name = card_name[:97] + "..."
    
    return card_name


def v2_create_prospect_card(prospect: Dict, dry_run: bool = False) -> Dict:
    """
    V2: Workflow complet de création de carte prospect.
    
    NOUVEAU:
    - Gestion carte archivée (désarchiver + update)
    - Recherche bien sur site AVANT Trello
    - Recherche sur tous les boards si pas sur BIENS
    - Téléphone dans le nom de carte
    
    Args:
        prospect: Données du prospect parsées
        dry_run: Si True, simule sans créer réellement
    
    Returns:
        Résultat de la création
    """
    result = {
        "version": "V2",
        "timestamp": datetime.now().isoformat(),
        "dry_run": dry_run,
        "action": None,
        "card_id": None,
        "card_url": None,
        "card_name": None,
        "steps": []
    }
    
    nom = prospect.get("nom", "")
    email_addr = prospect.get("email", "")
    tel = prospect.get("tel", "")
    
    # ÉTAPE C: Vérification doublon
    result["steps"].append("C. Vérification doublon")
    existing = v2_check_prospect_exists(nom, email_addr)
    
    if existing["found"]:
        if existing["status"] == "active":
            # C2: Carte active → STOP
            result["action"] = "stopped_duplicate_active"
            result["card_url"] = existing["card_url"]
            result["steps"].append(f"  → Carte ACTIVE trouvée: {existing['card_url']}")
            logger.info(f"⛔ [V2] Doublon actif, création annulée")
            return result
        
        elif existing["status"] == "archived":
            # C3: Carte archivée → Désarchiver + Update
            result["steps"].append(f"  → Carte ARCHIVÉE trouvée, désarchivage...")
            
            if dry_run:
                result["action"] = "would_unarchive"
                result["card_url"] = existing["card_url"]
                result["steps"].append(f"  → [DRY-RUN] Aurait désarchivé: {existing['card_url']}")
                return result
            
            unarchive_result = v2_unarchive_and_update(existing["card_id"], {
                "source": prospect.get("source"),
                "email": email_addr,
                "tel": tel,
                "message": prospect.get("message"),
                "bien_ville": prospect.get("ville"),
                "bien_prix": prospect.get("bien_prix")
            })
            
            result["action"] = "unarchived"
            result["card_id"] = existing["card_id"]
            result["card_url"] = unarchive_result.get("card_url")
            result["steps"].append(f"  → Carte désarchivée et mise à jour")
            return result
    
    result["steps"].append("  → Aucun doublon, création nouvelle carte")
    
    # ÉTAPE D: Recherche du bien
    result["steps"].append("D. Recherche du bien")
    
    ville = prospect.get("ville")
    prix = prospect.get("bien_prix")
    
    # D2: Chercher sur icidordogne.fr d'abord
    site_result = v2_search_property_on_site(ville, prix)
    result["steps"].append(f"  D2. Site icidordogne.fr: {'trouvé' if site_result['found'] else 'non trouvé'}")
    
    reference = site_result.get("reference")
    site_url = site_result.get("url")
    
    # D3: Chercher sur Trello (BIENS puis tous)
    trello_bien = v2_search_property_all_boards(reference, ville, prix)
    result["steps"].append(f"  D3. Trello: {'trouvé sur ' + trello_bien.get('board_name', '?') if trello_bien['found'] else 'non trouvé'}")
    
    # ÉTAPE E: Préparation carte
    result["steps"].append("E. Préparation carte")
    
    # E1: Nom de la carte avec téléphone
    if not nom:
        raw_from = prospect.get("raw_from", "")
        nom = extract_name_from_header(raw_from)
    
    card_name = v2_format_card_name(nom, tel)
    result["card_name"] = card_name
    result["steps"].append(f"  E1. Nom: {card_name}")
    
    # E2: Description
    desc_parts = ["**Contact**"]
    desc_parts.append(f"- Tél : {tel or '-'}")
    desc_parts.append(f"- Email : {email_addr or '-'}")
    desc_parts.append(f"- Source : {prospect.get('source', '-')}")
    desc_parts.append("")
    
    desc_parts.append("**Bien demandé**")
    if ville:
        desc_parts.append(f"- Ville : {ville}")
    if prix:
        desc_parts.append(f"- Prix : {prix} €")
    if trello_bien["found"]:
        desc_parts.append(f"- 🔗 Carte Trello bien : {trello_bien['card_url']}")
    if site_url:
        desc_parts.append(f"- 🌐 Site ICI Dordogne : {site_url}")
    
    desc_parts.append("")
    desc_parts.append("---")
    desc_parts.append(f"*Créé automatiquement par Axi V2 le {datetime.now().strftime('%d/%m/%Y %H:%M')}*")
    
    description = "\n".join(desc_parts)
    
    # E3: Membres
    members_to_assign = [JULIE_ID]
    if trello_bien["found"] and trello_bien.get("members"):
        for m in trello_bien["members"]:
            if m not in members_to_assign:
                members_to_assign.append(m)
    
    result["steps"].append(f"  E3. Membres: {len(members_to_assign)}")
    
    if dry_run:
        result["action"] = "would_create"
        result["steps"].append("  [DRY-RUN] Aurait créé la carte")
        return result
    
    # ÉTAPE F: Création carte
    result["steps"].append("F. Création carte")
    
    # F1: POST sans description
    card_data = {
        "idList": LIST_SUIVI_CLIENTS,
        "name": card_name,
        "pos": "top",
        "idMembers": ",".join(members_to_assign),
        "idLabels": f"{LABEL_PAS_SWEEPBRIGHT},{LABEL_PAS_TRAITE}"
    }
    
    card_result = trello_post("/cards", card_data)
    
    if not card_result:
        result["action"] = "error"
        result["steps"].append("  → Échec création carte")
        return result
    
    card_id = card_result.get("id")
    card_url = card_result.get("url")
    result["card_id"] = card_id
    result["card_url"] = card_url
    result["steps"].append(f"  F1. Carte créée: {card_url}")
    
    # F2: Attendre Butler
    time.sleep(5)
    result["steps"].append("  F2. Attente Butler (5s)")
    
    # F3: PUT description
    trello_put(f"/cards/{card_id}", {"desc": description})
    result["steps"].append("  F3. Description mise à jour")
    
    # ÉTAPE G: Enrichissement
    result["steps"].append("G. Enrichissement")
    
    # G1: Commentaire avec message
    message = prospect.get("message")
    if message:
        comment_text = f"📩 **Message du prospect:**\n\n{message}"
        trello_post(f"/cards/{card_id}/actions/comments", {"text": comment_text})
        result["steps"].append("  G1. Commentaire ajouté")
    
    # G2-G3: Checklists
    add_checklists(card_id)
    result["steps"].append("  G2-G3. Checklists ajoutées")
    
    result["action"] = "created"
    result["steps"].append("H. Terminé ✅")
    
    logger.info(f"✅ [V2] Carte créée: {card_url}")
    return result


def handle_v2_test(query=None, body=None, headers=None) -> Tuple[int, Dict]:
    """
    Handler pour endpoint GET /emails/v2/test
    Teste le workflow V2 avec le dernier email de INBOX.
    
    Params:
        ?dry_run=true  → Simule sans créer
        ?folder=INBOX  → Dossier à scanner
    """
    dry_run = False
    folder = "INBOX"
    
    if query:
        if 'dry_run' in query:
            dry_run = query['dry_run'][0].lower() == 'true' if isinstance(query['dry_run'], list) else query['dry_run'].lower() == 'true'
        if 'folder' in query:
            folder = query['folder'][0] if isinstance(query['folder'], list) else query['folder']
    
    result = {
        "version": "V2 TEST",
        "timestamp": datetime.now().isoformat(),
        "dry_run": dry_run,
        "folder": folder,
        "email_found": None,
        "workflow_result": None,
        "errors": []
    }
    
    try:
        # Scanner le dossier
        logger.info(f"📧 [V2 TEST] Scan {folder}, dry_run={dry_run}")
        
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(IMAP_EMAIL, IMAP_PASSWORD)
        mail.select(folder)
        
        status, messages = mail.search(None, "ALL")
        email_ids = messages[0].split() if messages[0] else []
        
        if not email_ids:
            mail.logout()
            result["errors"].append("Aucun email dans le dossier")
            return 400, result
        
        # Prendre le dernier email
        mail_id = email_ids[-1]
        status, msg_data = mail.fetch(mail_id, "(RFC822)")
        
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                
                subject_raw = msg.get("Subject", "")
                subject, encoding = decode_header(subject_raw)[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding or "utf-8", errors='ignore')
                
                # Ignorer les réponses
                if is_reply_email(subject):
                    mail.logout()
                    result["errors"].append(f"Email ignoré (réponse): {subject[:50]}")
                    return 400, result
                
                from_addr = msg.get("From", "")
                body_text = get_email_body(msg)
                
                result["email_found"] = {
                    "subject": subject,
                    "from": from_addr
                }
                
                # Parser l'email
                prospect = None
                if "sweepbright" in from_addr.lower():
                    prospect = parse_sweepbright(body_text, subject)
                elif "leboncoin" in from_addr.lower() or "leboncoin" in subject.lower():
                    prospect = parse_leboncoin(body_text, subject)
                elif "seloger" in from_addr.lower():
                    prospect = parse_seloger(body_text, subject)
                else:
                    prospect = parse_generic(body_text, subject, from_addr)
                
                if not prospect:
                    mail.logout()
                    result["errors"].append("Impossible de parser l'email")
                    return 400, result
                
                prospect["raw_subject"] = subject
                prospect["raw_from"] = from_addr
                
                # Exécuter le workflow V2
                workflow_result = v2_create_prospect_card(prospect, dry_run=dry_run)
                result["workflow_result"] = workflow_result
                
                mail.logout()
                return 200, result
        
        mail.logout()
        result["errors"].append("Erreur lecture email")
        return 500, result
        
    except Exception as e:
        result["errors"].append(str(e))
        return 500, result

