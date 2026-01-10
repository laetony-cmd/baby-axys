# axi_v19/modules/chat_vitrine.py
"""
Module Chat Vitrine V3 - Template PERMANENT pour sites immobiliers ICI Dordogne
==============================================================================

FONCTIONNALITÉS:
- Config JSON complète par bien (toutes les infos)
- Claude API avec contexte ultra-enrichi
- Web Search Tavily pour infos fraîches (quartier, transports, prix marché)
- Flow RDV avec capture progressive (nom → tel → dispo)
- Email automatique à l'agence avec les leads
- Support multilingue (FR/EN/ES)
- CORS complet

USAGE:
POST /chat-vitrine
{
    "bien_id": "lormont",
    "messages": [{"role": "user", "content": "..."}],
    "langue": "fr",
    "lead_data": {"nom": "", "telephone": "", "disponibilites": "", "email": ""}
}

"Je ne lâche pas." 💪
"""

import os
import json
import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional, List
import requests
from datetime import datetime

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

# =============================================================================
# CONFIGURATION DES BIENS - SOURCE UNIQUE DE VÉRITÉ
# =============================================================================

BIENS_CONFIG = {
    
    # =========================================================================
    # LORMONT T3 - Laetitia Dorle
    # =========================================================================
    "lormont": {
        "id": "lormont",
        "titre": "Appartement T3 avec Piscine Résidence",
        "type_bien": "Appartement",
        
        # LOCALISATION
        "adresse": "21 rue Édouard Herriot, 33310 Lormont",
        "ville": "Lormont",
        "code_postal": "33310",
        
        # PRIX
        "prix": 165000,
        "prix_affiche": "165 000 €",
        "honoraires": "charge vendeur",
        "frais_notaire": 12600,
        "total_acquisition": 177600,
        "prix_m2": 2661,
        "prix_m2_marche": 2350,
        "analyse_prix": "Prix compétitif justifié par piscine + parking inclus. Estimation haute: 175 000€.",
        
        # SURFACES
        "surface": 62,
        "surfaces_detail": {
            "Séjour/Salon": "24,49 m²",
            "Cuisine équipée": "5,47 m²",
            "Chambre 1": "9,75 m² avec placard intégré",
            "Chambre 2": "11,20 m² avec placard intégré",
            "Salle de bains": "3,22 m²",
            "WC indépendant": "1,00 m²",
            "Couloir": "3,20 m²"
        },
        
        # COMPOSITION
        "pieces": 3,
        "chambres": 2,
        "sdb": 1,
        "wc": 1,
        "balcon": True,
        
        # BÂTIMENT
        "etage": "4ème avec ascenseur",
        "batiment": "D - Porte D33",
        "ascenseur": True,
        "interphone": True,
        "residence": "Résidence calme et sécurisée",
        
        # EXTÉRIEURS
        "parking": "1 place extérieure INCLUSE dans le prix",
        "piscine": "Piscine collective de la résidence - accès inclus",
        
        # ÉQUIPEMENTS
        "equipements": [
            "Double vitrage intégral sur toutes les fenêtres",
            "Volets roulants électriques sur toutes les ouvertures",
            "Cuisine équipée avec micro-onde et frigo-congélateur",
            "Salle de bains avec baignoire + douche italienne + double vasque",
            "WC indépendant",
            "Balcon avec vue dégagée",
            "Interphone vidéo",
            "Thermostat programmable",
            "Placards intégrés dans les 2 chambres",
            "VMC"
        ],
        
        # CHAUFFAGE & ÉNERGIE
        "chauffage": "Radiateurs électriques (conseil: modernisation ~2000€ pour économies)",
        "isolation": "Bonne isolation - Température 17-19°C maintenue sans chauffage en hiver",
        "dpe": "D (estimation)",
        
        # ÉTAT
        "etat": "TRÈS PROPRE - Emménagement immédiat possible, aucun travaux nécessaires",
        
        # TRANSPORTS
        "transports": {
            "tramway": "Ligne A - Arrêts Carriet et Mairie de Lormont à 5-7 min à pied",
            "bus": "Lignes 7, 32, 36 à proximité",
            "voiture": "Rocade A630 sortie 2 (Lormont) à 3 min",
            "bordeaux_centre": "15 minutes en tramway direct",
            "gare_saint_jean": "25 minutes",
            "aeroport": "40 minutes"
        },
        
        # COMMERCES & SERVICES
        "commerces": [
            "Supermarché Carrefour Market à 500m",
            "Boulangerie à 200m",
            "Pharmacie à 300m",
            "Centre commercial Auchan Lormont à 2km",
            "Nombreux restaurants et cafés"
        ],
        "ecoles": [
            "École maternelle Jean Jaurès à 800m",
            "École primaire Génicart à 600m",
            "Collège Georges Lapierre à 1km",
            "Lycée Les Iris à 2km"
        ],
        "loisirs": [
            "Piscine résidence sur place !",
            "Parc de l'Ermitage pour promenades",
            "Complexe sportif à 1km",
            "Berges de la Garonne à 2km"
        ],
        
        # POINTS FORTS
        "points_forts": [
            "🏊 Piscine résidence - TRÈS RARE à ce prix !",
            "🚗 Parking extérieur INCLUS",
            "🪟 Double vitrage + volets roulants TOUTES fenêtres",
            "✨ Très propre - ZÉRO travaux",
            "🌡️ Excellente isolation thermique",
            "🚃 15 min Bordeaux centre - Tramway direct",
            "☀️ 4ème étage très lumineux",
            "🛗 Ascenseur dans le bâtiment",
            "💰 Prix/m² compétitif vs marché"
        ],
        
        # ARGUMENTS PAR PROFIL
        "arguments": {
            "investisseur": "Forte demande locative à Lormont (étudiants, jeunes actifs Bordeaux). Loyer estimé 750-850€/mois. Rentabilité ~5.5%.",
            "primo_accedant": "Idéal 1ère acquisition - prix accessible, 2 vraies chambres, piscine, proche transports pour le travail.",
            "famille": "2 chambres avec placards, piscine pour les enfants, écoles à proximité, quartier calme et sécurisé.",
            "senior": "4ème avec ascenseur, résidence sécurisée, tous commerces à pied, pas d'entretien extérieur."
        },
        
        # VISITE VIRTUELLE
        "visite_virtuelle": "https://my.matterport.com/show/?m=7zeq1p",
        
        # CONTACT
        "agence": "ICI Dordogne",
        "tel": "05 53 13 33 33",
        "email": "agence@icidordogne.fr",
        "site": "https://lormont-t3-piscine-icidordogne.netlify.app/",
        
        # VENDEUR (interne - ne pas communiquer au public)
        "_vendeur": "Laetitia Dorle",
        "_docs_manquants": ["3 derniers PV AG", "Prix acquisition 2020"]
    },
    
    # =========================================================================
    # MANZAC - À compléter
    # =========================================================================
    "manzac": {
        "id": "manzac",
        "titre": "Maison Plain-pied 99m² - Terrain 1889m²",
        "type_bien": "Maison",
        "adresse": "Manzac-sur-Vern, 24110",
        "ville": "Manzac-sur-Vern",
        "code_postal": "24110",
        "prix": 198000,
        "prix_affiche": "198 000 €",
        "honoraires": "charge vendeur",
        "surface": 99,
        "terrain": 1889,
        "chambres": 3,
        "dpe": "C",
        "ges": "A",
        "chauffage": "Pompe à chaleur + Poêle à granulés",
        "garage": "38 m² avec atelier",
        "points_forts": [
            "DPE C - Excellent à ce prix",
            "Plain-pied pratique",
            "Terrain 1889m² clos et piscinable",
            "Vue campagne dégagée",
            "6 min autoroute A89"
        ],
        "tel": "05 53 13 33 33",
        "visite_virtuelle": "https://nouveaute-maisonavendre-manzacsurvern.netlify.app/"
    }
}

# =============================================================================
# PROMPTS MULTILINGUES
# =============================================================================

LANG_CONFIG = {
    "fr": {
        "instruction": "Tu réponds TOUJOURS en français.",
        "ask_name": "Pour organiser votre visite, quel est votre nom ?",
        "ask_phone": "Merci {nom} ! Quel est votre numéro de téléphone ?",
        "ask_dispo": "Parfait ! Quelles sont vos disponibilités cette semaine ?",
        "confirm": "Excellent ! L'agence ICI Dordogne va vous recontacter très rapidement. À bientôt !",
        "error": "Désolée, je rencontre un problème technique. Appelez-nous au {tel} !"
    },
    "en": {
        "instruction": "You ALWAYS respond in English.",
        "ask_name": "To schedule your visit, what is your name?",
        "ask_phone": "Thank you {nom}! What is your phone number?",
        "ask_dispo": "Great! What are your availabilities this week?",
        "confirm": "Excellent! ICI Dordogne agency will contact you very soon. See you soon!",
        "error": "Sorry, I'm experiencing a technical issue. Call us at {tel}!"
    },
    "es": {
        "instruction": "SIEMPRE respondes en español.",
        "ask_name": "Para organizar su visita, ¿cuál es su nombre?",
        "ask_phone": "¡Gracias {nom}! ¿Cuál es su número de teléfono?",
        "ask_dispo": "¡Perfecto! ¿Cuáles son sus disponibilidades esta semana?",
        "confirm": "¡Excelente! La agencia ICI Dordogne le contactará muy pronto. ¡Hasta pronto!",
        "error": "Lo siento, tengo un problema técnico. ¡Llámenos al {tel}!"
    }
}

# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def get_bien_config(bien_id: str) -> Optional[Dict]:
    """Récupère la configuration d'un bien."""
    return BIENS_CONFIG.get(bien_id.lower())


def search_web(query: str, domains: List[str] = None) -> str:
    """Recherche web via Tavily pour infos fraîches."""
    if not TAVILY_API_KEY:
        logger.warning("[TAVILY] API key non configurée")
        return ""
    
    default_domains = [
        "bordeaux.fr", "lormont.fr", "seloger.com", 
        "leboncoin.fr", "meilleursagents.com", "dvf.etalab.gouv.fr"
    ]
    
    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_API_KEY,
                "query": query,
                "search_depth": "basic",
                "max_results": 3,
                "include_domains": domains or default_domains
            },
            timeout=8
        )
        
        if response.status_code == 200:
            results = response.json().get("results", [])
            if results:
                infos = []
                for r in results[:3]:
                    title = r.get("title", "")[:50]
                    content = r.get("content", "")[:150]
                    infos.append(f"• {title}: {content}")
                return "\n".join(infos)
    except Exception as e:
        logger.warning(f"[TAVILY] Erreur: {e}")
    
    return ""


def build_system_prompt(bien: Dict, langue: str = "fr") -> str:
    """Construit le prompt système COMPLET avec toutes les infos du bien."""
    
    lang = LANG_CONFIG.get(langue, LANG_CONFIG["fr"])
    
    # Formatage des surfaces détaillées
    surfaces = ""
    if "surfaces_detail" in bien:
        surfaces = "\n".join([f"  • {k}: {v}" for k, v in bien["surfaces_detail"].items()])
    
    # Formatage des équipements
    equipements = ""
    if "equipements" in bien:
        equipements = "\n".join([f"  ✓ {e}" for e in bien["equipements"]])
    
    # Formatage des points forts
    points_forts = ""
    if "points_forts" in bien:
        points_forts = "\n".join(bien["points_forts"])
    
    # Formatage transports
    transports = ""
    if isinstance(bien.get("transports"), dict):
        transports = "\n".join([f"  • {k.title()}: {v}" for k, v in bien["transports"].items()])
    elif isinstance(bien.get("transports"), list):
        transports = "\n".join([f"  • {t}" for t in bien["transports"]])
    
    # Formatage commerces
    commerces = "\n".join([f"  • {c}" for c in bien.get("commerces", [])])
    
    # Formatage écoles
    ecoles = "\n".join([f"  • {e}" for e in bien.get("ecoles", [])])
    
    # Arguments de vente par profil
    arguments = ""
    if "arguments" in bien:
        arguments = "\n".join([f"  → {k.upper()}: {v}" for k, v in bien["arguments"].items()])
    
    return f"""Tu es Sophie, assistante virtuelle de l'agence ICI Dordogne.
{lang['instruction']}

══════════════════════════════════════════════════════════════════════════════
🏠 {bien.get('titre', 'Bien immobilier')}
══════════════════════════════════════════════════════════════════════════════

📍 LOCALISATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Adresse: {bien.get('adresse', 'Non communiquée')}
Ville: {bien.get('ville', '')} ({bien.get('code_postal', '')})

💰 PRIX
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Prix: {bien.get('prix_affiche', bien.get('prix', 'NC'))} (honoraires {bien.get('honoraires', 'charge vendeur')})
Frais de notaire estimés: ~{bien.get('frais_notaire', 'NC')} €
Total acquisition: ~{bien.get('total_acquisition', 'NC')} €
Prix au m²: {bien.get('prix_m2', 'NC')} €/m² (marché local: ~{bien.get('prix_m2_marche', 'NC')} €/m²)
Analyse: {bien.get('analyse_prix', '')}

📐 SURFACES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Surface totale: ~{bien.get('surface', 'NC')} m²
Détail:
{surfaces}

🏗️ COMPOSITION & BÂTIMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Type: {bien.get('type_bien', 'NC')}
Pièces: {bien.get('pieces', 'NC')} | Chambres: {bien.get('chambres', 'NC')} | SDB: {bien.get('sdb', 'NC')} | WC: {bien.get('wc', 'NC')}
Étage: {bien.get('etage', 'NC')}
Bâtiment: {bien.get('batiment', 'NC')}
Ascenseur: {'Oui' if bien.get('ascenseur') else 'Non'}
Balcon: {'Oui' if bien.get('balcon') else 'Non'}
Résidence: {bien.get('residence', 'NC')}

🔧 ÉQUIPEMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{equipements}

🚗 EXTÉRIEURS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Parking: {bien.get('parking', 'Non inclus')}
Piscine: {bien.get('piscine', 'Non')}

🌡️ ÉNERGIE & ÉTAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Chauffage: {bien.get('chauffage', 'NC')}
Isolation: {bien.get('isolation', 'NC')}
DPE: {bien.get('dpe', 'NC')}
État général: {bien.get('etat', 'NC')}

🚃 TRANSPORTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{transports}

🛒 COMMERCES & SERVICES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{commerces}

🏫 ÉCOLES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{ecoles}

⭐ POINTS FORTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{points_forts}

🎯 ARGUMENTS PAR PROFIL ACHETEUR
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{arguments}

🔗 VISITE VIRTUELLE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{bien.get('visite_virtuelle', 'Non disponible')}

══════════════════════════════════════════════════════════════════════════════
📋 TON RÔLE
══════════════════════════════════════════════════════════════════════════════

1️⃣ INFORMER avec précision et enthousiasme
   • Utilise TOUTES les données ci-dessus pour répondre
   • Mets en avant les points forts naturellement
   • Si tu ne connais pas une info, dis-le honnêtement
   • Adapte tes arguments au profil de l'acheteur si tu le détectes

2️⃣ CONVERTIR vers une visite
   • Détecte l'intérêt: questions détaillées, budget, timeline...
   • Propose la visite: "Ce bien vous intéresse ? Je peux organiser une visite !"
   • Si OUI, capture dans l'ordre:
     a) "{lang['ask_name']}"
     b) "{lang['ask_phone']}"
     c) "{lang['ask_dispo']}"
   • Confirmation: "{lang['confirm']}"

3️⃣ STYLE
   • Chaleureux, enthousiaste mais pas pushy
   • Concis: 2-3 phrases max par réponse
   • Ne donne JAMAIS de RDV précis - l'agence rappellera
   • Utilise des émojis avec parcimonie (1-2 max par réponse)

📞 CONTACT AGENCE: {bien.get('agence', 'ICI Dordogne')} - {bien.get('tel', '05 53 13 33 33')}
"""


def send_lead_email(bien_id: str, lead_data: Dict, conversation: List[Dict] = None) -> bool:
    """Envoie un email à l'agence avec les infos du lead."""
    try:
        bien = get_bien_config(bien_id) or {}
        
        # Formater la conversation
        conv_html = ""
        if conversation:
            conv_html = "<br>".join([
                f"<b>{'👤 Visiteur' if m['role'] == 'user' else '🤖 Sophie'}:</b> {m['content']}"
                for m in conversation[-10:]  # Derniers 10 messages
            ])
        
        subject = f"🏠 LEAD Chat Vitrine - {bien.get('titre', bien_id)}"
        
        body = f"""
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">

<div style="background: linear-gradient(135deg, #1a5d4a, #2d8a6e); color: white; padding: 25px; border-radius: 10px 10px 0 0; text-align: center;">
    <h1 style="margin: 0;">🏠 Nouveau Lead !</h1>
    <p style="margin: 10px 0 0 0; opacity: 0.9;">Via Chat Site Vitrine</p>
</div>

<div style="background: #f8f9fa; padding: 25px; border: 1px solid #e9ecef;">
    
    <h2 style="color: #1a5d4a; margin-top: 0;">📋 Informations du prospect</h2>
    
    <table style="width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden;">
        <tr style="background: #1a5d4a; color: white;">
            <td style="padding: 12px; width: 40%;"><strong>Champ</strong></td>
            <td style="padding: 12px;"><strong>Valeur</strong></td>
        </tr>
        <tr>
            <td style="padding: 12px; border-bottom: 1px solid #eee;"><strong>👤 Nom</strong></td>
            <td style="padding: 12px; border-bottom: 1px solid #eee; font-size: 16px;">{lead_data.get('nom', 'Non renseigné')}</td>
        </tr>
        <tr style="background: #f8f9fa;">
            <td style="padding: 12px; border-bottom: 1px solid #eee;"><strong>📞 Téléphone</strong></td>
            <td style="padding: 12px; border-bottom: 1px solid #eee; font-size: 16px;">
                <a href="tel:{lead_data.get('telephone', '')}" style="color: #1a5d4a; text-decoration: none; font-weight: bold;">
                    {lead_data.get('telephone', 'Non renseigné')}
                </a>
            </td>
        </tr>
        <tr>
            <td style="padding: 12px; border-bottom: 1px solid #eee;"><strong>📅 Disponibilités</strong></td>
            <td style="padding: 12px; border-bottom: 1px solid #eee;">{lead_data.get('disponibilites', 'Non renseigné')}</td>
        </tr>
        <tr style="background: #f8f9fa;">
            <td style="padding: 12px; border-bottom: 1px solid #eee;"><strong>📧 Email</strong></td>
            <td style="padding: 12px; border-bottom: 1px solid #eee;">{lead_data.get('email', 'Non renseigné')}</td>
        </tr>
        <tr>
            <td style="padding: 12px;"><strong>🏠 Bien concerné</strong></td>
            <td style="padding: 12px;">{bien.get('titre', bien_id)}<br><small style="color: #666;">{bien.get('adresse', '')}</small></td>
        </tr>
    </table>
    
    <h2 style="color: #1a5d4a; margin-top: 25px;">💬 Conversation</h2>
    <div style="background: white; padding: 15px; border-radius: 8px; border-left: 4px solid #1a5d4a; font-size: 14px; line-height: 1.6;">
        {conv_html or '<em>Conversation non disponible</em>'}
    </div>
    
    <div style="margin-top: 25px; text-align: center;">
        <a href="{bien.get('visite_virtuelle', '#')}" style="display: inline-block; background: #1a5d4a; color: white; padding: 12px 25px; border-radius: 25px; text-decoration: none; font-weight: bold;">
            🔗 Voir la visite virtuelle
        </a>
    </div>
    
</div>

<div style="background: #1a5d4a; color: white; padding: 15px; text-align: center; border-radius: 0 0 10px 10px; font-size: 12px;">
    Lead capturé le {datetime.now().strftime('%d/%m/%Y à %H:%M')} • Chat Vitrine ICI Dordogne
</div>

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
        
        logger.info(f"[LEAD] ✅ Email envoyé - {bien_id}: {lead_data.get('nom', '?')} - {lead_data.get('telephone', '?')}")
        return True
        
    except Exception as e:
        logger.error(f"[LEAD] ❌ Erreur email: {e}")
        return False


# =============================================================================
# HANDLER PRINCIPAL: /chat-vitrine
# =============================================================================

def chat_vitrine_handler(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handler principal du chat vitrine V3.
    
    Entrée:
    {
        "bien_id": "lormont",
        "messages": [{"role": "user", "content": "..."}],
        "langue": "fr",
        "lead_data": {"nom": "", "telephone": "", "disponibilites": "", "email": ""}
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
            available = list(BIENS_CONFIG.keys())
            return {
                "content": [{"type": "text", "text": f"Bien '{bien_id}' non trouvé. Biens disponibles: {available}"}],
                "error": f"Bien '{bien_id}' non trouvé"
            }
        
        # Vérifier API key
        if not ANTHROPIC_API_KEY:
            lang = LANG_CONFIG.get(langue, LANG_CONFIG["fr"])
            return {
                "content": [{"type": "text", "text": lang["error"].format(tel=bien.get('tel', '05 53 13 33 33'))}],
                "error": "API non configurée"
            }
        
        # Construire le prompt système
        system_prompt = build_system_prompt(bien, langue)
        
        # Enrichir avec recherche web si question sur environnement
        last_message = messages[-1].get("content", "") if messages else ""
        web_triggers = [
            "quartier", "voisin", "transport", "tramway", "bus", "train",
            "commerce", "magasin", "école", "collège", "lycée", "crèche",
            "médecin", "hôpital", "pharmacie", "parc", "sport",
            "neighborhood", "school", "shop", "barrio", "tienda", "escuela"
        ]
        
        if any(trigger in last_message.lower() for trigger in web_triggers):
            ville = bien.get("ville", "")
            cp = bien.get("code_postal", "")
            web_results = search_web(f"{ville} {cp} {last_message}")
            if web_results:
                system_prompt += f"\n\n📡 INFOS WEB RÉCENTES:\n{web_results}"
        
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
                "max_tokens": 600,
                "system": system_prompt,
                "messages": messages
            },
            timeout=30
        )
        
        if response.status_code != 200:
            logger.error(f"[CHAT-VITRINE] Claude error: {response.status_code} - {response.text[:200]}")
            lang = LANG_CONFIG.get(langue, LANG_CONFIG["fr"])
            return {
                "content": [{"type": "text", "text": lang["error"].format(tel=bien.get('tel', '05 53 13 33 33'))}],
                "error": f"Claude API error: {response.status_code}"
            }
        
        result = response.json()
        assistant_text = result["content"][0]["text"]
        
        # Vérifier si lead complet → envoyer email
        lead_captured = False
        if (lead_data.get("nom") and 
            lead_data.get("telephone") and 
            lead_data.get("disponibilites")):
            
            send_lead_email(bien_id, lead_data, messages)
            lead_captured = True
        
        logger.info(f"[CHAT-VITRINE] ✅ Bien: {bien_id} | Langue: {langue} | Lead: {lead_captured}")
        
        return {
            "content": [{"type": "text", "text": assistant_text}],
            "lead_captured": lead_captured
        }
        
    except Exception as e:
        logger.error(f"[CHAT-VITRINE] ❌ Erreur: {e}")
        return {
            "content": [{"type": "text", "text": "Une erreur s'est produite. Appelez-nous au 05 53 13 33 33 !"}],
            "error": str(e)
        }


# =============================================================================
# REGISTRATION
# =============================================================================

def register_chat_vitrine_routes(server):
    """Enregistre les routes du module chat vitrine."""
    try:
        server.register_route("POST", "/chat-vitrine", chat_vitrine_handler)
        logger.info("✅ [CHAT-VITRINE] Route /chat-vitrine enregistrée")
    except Exception as e:
        logger.error(f"❌ [CHAT-VITRINE] Erreur registration: {e}")
