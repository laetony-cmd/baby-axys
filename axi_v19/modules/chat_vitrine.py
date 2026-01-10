# axi_v19/modules/chat_vitrine.py
"""
Module Chat Vitrine V2 - Template permanent pour sites immobiliers
- CORS complet (preflight OPTIONS)
- Config JSON par bien
- Claude API avec contexte enrichi
- Web Search Tavily pour infos fraîches
- Flow RDV avec capture progressive
- Email automatique à l'agence

"Je ne lâche pas." 💪
"""

import os
import json
import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional
import requests
from pathlib import Path

logger = logging.getLogger("axi_v19.chat_vitrine")

# =============================================================================
# CONFIGURATION
# =============================================================================

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
GMAIL_USER = os.getenv("GMAIL_USER", "u5050786429@gmail.com")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "izemquwmmqjdasrk")
EMAIL_TO = os.getenv("EMAIL_TO", "agence@icidordogne.fr")
EMAIL_CC = os.getenv("EMAIL_CC", "laetony@gmail.com")

# Config des biens (inline pour éviter les problèmes de chemin)
BIENS_CONFIG = {
    "lormont": {
        "id": "lormont",
        "titre": "Appartement T3 avec Piscine Résidence",
        "adresse": "21 rue Édouard Herriot, 33310 Lormont",
        "prix": 165000,
        "surface": 62,
        "chambres": 2,
        "etage": "4ème avec ascenseur",
        "batiment": "D - Porte D33",
        "parking": "Extérieur inclus",
        "piscine": "Collective (résidence)",
        "equipements": [
            "Double vitrage intégral",
            "Volets roulants électriques",
            "Cuisine équipée (micro-onde, frigo)",
            "Salle de bains avec baignoire + douche + double vasque",
            "WC indépendant",
            "Balcon",
            "Interphone + Thermostat"
        ],
        "surfaces_detail": {
            "Séjour": "24,49 m²",
            "Cuisine": "5,47 m²",
            "Chambre 1": "9,75 m² avec placard",
            "Chambre 2": "11,20 m² avec placard",
            "Salle de bains": "3,22 m²",
            "WC": "1,00 m²",
            "Couloir": "3,20 m²"
        },
        "chauffage": "Radiateurs électriques (à moderniser ~2000€)",
        "isolation": "Bonne - 17-19°C sans chauffage en hiver",
        "etat": "Très propre, habitable immédiatement",
        "transports": "Tramway ligne A (Carriet/Mairie de Lormont) - 15 min Bordeaux centre",
        "commerces": "Supermarché, boulangerie, pharmacie à proximité",
        "points_forts": [
            "Piscine résidence - rare à ce prix",
            "Parking extérieur inclus dans le prix",
            "Double vitrage + volets roulants toutes fenêtres",
            "Très propre - aucun travaux",
            "Bonne isolation thermique",
            "15 min de Bordeaux - Tramway ligne A",
            "4ème étage lumineux avec ascenseur"
        ],
        "visite_virtuelle": "https://my.matterport.com/show/?m=7zeq1p",
        "agence_tel": "05 53 13 33 33",
        "agence_email": "agence@icidordogne.fr",
        "vendeur": "Laetitia Dorle",
        "prix_m2_bien": 2661,
        "prix_m2_marche": 2350,
        "estimation_haute": 175000
    }
}

# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def get_bien_config(bien_id: str) -> Optional[Dict]:
    """Récupère la configuration d'un bien"""
    return BIENS_CONFIG.get(bien_id)


def search_web_tavily(query: str, max_results: int = 3) -> str:
    """Recherche web via Tavily pour infos fraîches"""
    if not TAVILY_API_KEY:
        return ""
    
    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_API_KEY,
                "query": query,
                "search_depth": "basic",
                "max_results": max_results,
                "include_domains": ["leboncoin.fr", "seloger.com", "pap.fr", "bordeaux.fr", "lormont.fr"]
            },
            timeout=10
        )
        
        if response.status_code == 200:
            results = response.json().get("results", [])
            if results:
                summaries = [f"- {r.get('title', '')}: {r.get('content', '')[:200]}" for r in results[:3]]
                return "\n".join(summaries)
    except Exception as e:
        logger.warning(f"[TAVILY] Erreur recherche: {e}")
    
    return ""


def build_system_prompt(bien: Dict, langue: str = "fr") -> str:
    """Construit le prompt système avec toutes les infos du bien"""
    
    lang_instruction = {
        "fr": "Réponds TOUJOURS en français.",
        "en": "ALWAYS respond in English.",
        "es": "SIEMPRE responde en español."
    }.get(langue, "Réponds TOUJOURS en français.")
    
    equipements = "\n".join([f"  - {e}" for e in bien.get("equipements", [])])
    points_forts = "\n".join([f"  ✓ {p}" for p in bien.get("points_forts", [])])
    surfaces = "\n".join([f"  - {k}: {v}" for k, v in bien.get("surfaces_detail", {}).items()])
    
    return f"""Tu es Sophie, assistante virtuelle de l'agence ICI Dordogne pour le bien suivant.

{lang_instruction}

═══════════════════════════════════════════════════════════════
📍 {bien.get('titre', 'Bien immobilier')}
═══════════════════════════════════════════════════════════════

INFORMATIONS CLÉS:
• Adresse: {bien.get('adresse', 'Non précisée')}
• Prix: {bien.get('prix', 0):,} € (honoraires charge vendeur)
• Surface: ~{bien.get('surface', 0)} m²
• Chambres: {bien.get('chambres', 0)}
• Étage: {bien.get('etage', 'RDC')}
• Bâtiment: {bien.get('batiment', '')}

SURFACES DÉTAILLÉES:
{surfaces}

ÉQUIPEMENTS:
{equipements}

POINTS FORTS:
{points_forts}

AUTRES INFOS:
• Chauffage: {bien.get('chauffage', 'Non précisé')}
• Isolation: {bien.get('isolation', 'Non précisée')}
• État: {bien.get('etat', 'Non précisé')}
• Parking: {bien.get('parking', 'Non inclus')}
• Piscine: {bien.get('piscine', 'Non')}

LOCALISATION:
• Transports: {bien.get('transports', 'Non précisé')}
• Commerces: {bien.get('commerces', 'Non précisé')}

VISITE VIRTUELLE: {bien.get('visite_virtuelle', 'Non disponible')}

ANALYSE MARCHÉ:
• Prix/m² du bien: {bien.get('prix_m2_bien', 0)} €/m²
• Prix/m² marché Lormont: {bien.get('prix_m2_marche', 0)} €/m²
• Estimation haute: {bien.get('estimation_haute', 0):,} €
→ Bien compétitif grâce à la piscine et au parking inclus

═══════════════════════════════════════════════════════════════
TON RÔLE
═══════════════════════════════════════════════════════════════

1. INFORMER: Réponds aux questions sur le bien avec précision et enthousiasme
   - Utilise les données ci-dessus
   - Sois honnête si tu ne connais pas une info

2. CONVERTIR: Guide vers une prise de RDV
   - Si intérêt détecté: "Souhaitez-vous organiser une visite ?"
   - Si OUI, capture dans l'ordre:
     a) "Pour organiser votre visite, quel est votre nom ?"
     b) "Merci [nom] ! Quel est votre numéro de téléphone ?"
     c) "Parfait ! Quelles sont vos disponibilités cette semaine ?"
   - Une fois les 3 infos: "Excellent ! L'agence va vous recontacter très rapidement pour confirmer le créneau."

3. STYLE:
   - Chaleureux et professionnel
   - Concis (2-3 phrases max par réponse)
   - Ne donne JAMAIS de RDV précis, l'agence rappellera
   - Mets en avant les points forts naturellement

CONTACT AGENCE: ICI Dordogne - {bien.get('agence_tel', '05 53 13 33 33')}
"""


def send_lead_email(bien_id: str, lead_data: Dict) -> bool:
    """Envoie un email à l'agence avec les infos du lead"""
    try:
        bien = get_bien_config(bien_id) or {}
        
        subject = f"🏠 Nouveau lead - {bien.get('titre', bien_id)}"
        
        body = f"""
<html>
<body style="font-family: Arial, sans-serif; padding: 20px;">
<h2 style="color: #1a5d4a;">🏠 Nouveau Lead Chat Vitrine</h2>

<table style="border-collapse: collapse; width: 100%; max-width: 500px;">
<tr style="background: #f5f5f5;">
    <td style="padding: 10px; border: 1px solid #ddd;"><strong>Bien</strong></td>
    <td style="padding: 10px; border: 1px solid #ddd;">{bien.get('titre', bien_id)}</td>
</tr>
<tr>
    <td style="padding: 10px; border: 1px solid #ddd;"><strong>Nom</strong></td>
    <td style="padding: 10px; border: 1px solid #ddd;">{lead_data.get('nom', 'Non renseigné')}</td>
</tr>
<tr style="background: #f5f5f5;">
    <td style="padding: 10px; border: 1px solid #ddd;"><strong>Téléphone</strong></td>
    <td style="padding: 10px; border: 1px solid #ddd;"><a href="tel:{lead_data.get('telephone', '')}">{lead_data.get('telephone', 'Non renseigné')}</a></td>
</tr>
<tr>
    <td style="padding: 10px; border: 1px solid #ddd;"><strong>Disponibilités</strong></td>
    <td style="padding: 10px; border: 1px solid #ddd;">{lead_data.get('disponibilites', 'Non renseigné')}</td>
</tr>
<tr style="background: #f5f5f5;">
    <td style="padding: 10px; border: 1px solid #ddd;"><strong>Email</strong></td>
    <td style="padding: 10px; border: 1px solid #ddd;">{lead_data.get('email', 'Non renseigné')}</td>
</tr>
</table>

<p style="margin-top: 20px; color: #666;">
<em>Lead capturé via le chat du site vitrine</em><br>
<a href="{bien.get('visite_virtuelle', '#')}">Voir la visite virtuelle</a>
</p>

</body>
</html>
"""
        
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = GMAIL_USER
        msg["To"] = EMAIL_TO
        msg["Cc"] = EMAIL_CC
        
        msg.attach(MIMEText(body, "html"))
        
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, [EMAIL_TO, EMAIL_CC], msg.as_string())
        
        logger.info(f"[LEAD EMAIL] Envoyé pour {bien_id}: {lead_data.get('nom', '?')}")
        return True
        
    except Exception as e:
        logger.error(f"[LEAD EMAIL ERROR] {e}")
        return False


# =============================================================================
# HANDLER PRINCIPAL: /chat-vitrine
# =============================================================================

def chat_vitrine_handler(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handler principal du chat vitrine
    
    Entrée:
    {
        "bien_id": "lormont",
        "messages": [{"role": "user", "content": "..."}],
        "langue": "fr",  // optionnel
        "lead_data": {"nom": "...", "telephone": "...", "disponibilites": "..."}  // optionnel
    }
    
    Sortie:
    {
        "content": [{"type": "text", "text": "..."}],
        "lead_captured": true/false
    }
    """
    try:
        bien_id = body.get("bien_id", "").lower()
        messages = body.get("messages", [])
        langue = body.get("langue", "fr")
        lead_data = body.get("lead_data", {})
        
        # Récupérer config du bien
        bien = get_bien_config(bien_id)
        if not bien:
            return {"error": f"Bien '{bien_id}' non trouvé", "available": list(BIENS_CONFIG.keys())}
        
        # Vérifier API key
        if not ANTHROPIC_API_KEY:
            logger.error("[CHAT-VITRINE] ANTHROPIC_API_KEY non configurée")
            return {"error": "API non configurée"}
        
        # Construire le prompt système
        system_prompt = build_system_prompt(bien, langue)
        
        # Enrichir avec recherche web si pertinent
        last_message = messages[-1].get("content", "") if messages else ""
        web_context = ""
        
        # Recherche web pour questions sur le quartier, transports, etc.
        web_triggers = ["quartier", "transport", "tramway", "bus", "commerce", "école", "voisinage", "neighborhood", "barrio"]
        if any(trigger in last_message.lower() for trigger in web_triggers):
            web_context = search_web_tavily(f"Lormont 33310 {last_message}")
            if web_context:
                system_prompt += f"\n\nINFOS WEB RÉCENTES:\n{web_context}"
        
        # Appel Claude API
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 500,
                "system": system_prompt,
                "messages": messages
            },
            timeout=30
        )
        
        if response.status_code != 200:
            logger.error(f"[CHAT-VITRINE] Claude error: {response.status_code}")
            return {"error": f"Claude API error: {response.status_code}"}
        
        result = response.json()
        assistant_text = result["content"][0]["text"]
        
        # Vérifier si lead complet et envoyer email
        lead_captured = False
        if lead_data.get("nom") and lead_data.get("telephone") and lead_data.get("disponibilites"):
            send_lead_email(bien_id, lead_data)
            lead_captured = True
        
        logger.info(f"[CHAT-VITRINE] Bien: {bien_id} | Langue: {langue} | Lead: {lead_captured}")
        
        return {
            "content": [{"type": "text", "text": assistant_text}],
            "lead_captured": lead_captured
        }
        
    except Exception as e:
        logger.error(f"[CHAT-VITRINE ERROR] {e}")
        return {"error": str(e)}


# =============================================================================
# HANDLER CORS OPTIONS
# =============================================================================

def options_handler(body: Dict[str, Any] = None) -> Dict[str, Any]:
    """Handler pour les requêtes OPTIONS (preflight CORS)"""
    return {"status": "ok"}


# =============================================================================
# REGISTRATION
# =============================================================================

def register_chat_vitrine_routes(server):
    """Enregistre les routes du module chat vitrine"""
    try:
        # Route principale
        server.register_route("POST", "/chat-vitrine", chat_vitrine_handler)
        logger.info("[CHAT-VITRINE] Route /chat-vitrine enregistrée")
        
    except Exception as e:
        logger.error(f"[CHAT-VITRINE] Erreur registration: {e}")


def chat_proxy_legacy_handler(body: Dict[str, Any]) -> Dict[str, Any]:
    """Handler legacy pour compatibilité avec l'ancien /chat-proxy"""
    # Convertir l'ancien format vers le nouveau
    site_id = body.get("site_id", "lormont")
    messages = body.get("messages", [])
    system = body.get("system", "")
    
    # Détecter la langue depuis le system prompt
    langue = "fr"
    if "ENGLISH" in system.upper():
        langue = "en"
    elif "ESPAÑOL" in system.upper() or "SPANISH" in system.upper():
        langue = "es"
    
    # Appeler le nouveau handler
    return chat_vitrine_handler({
        "bien_id": site_id,
        "messages": messages,
        "langue": langue
    })
