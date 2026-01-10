# axi_v19/modules/chat_vitrine.py
"""
Module Chat Vitrine V3.4 - Données officielles copropriété 10/01/2026
=====================================================================
- Surfaces officielles du plan TAGERIM
- 4ème et dernier étage
- Charges réelles (décomptes Citya 2024)
- Taxe foncière 2025: 1351€/an
- Syndic CITYA Lanaverre Talence

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
# CONFIGURATION DES BIENS - V3.3 Surfaces TAGERIM 10/01/2026
# =============================================================================

BIENS_CONFIG = {
    
    # =========================================================================
    # LORMONT T3 - Laetitia Dorle - V3.3 SURFACES TAGERIM OFFICIELLES
    # =========================================================================
    "lormont": {
        "id": "lormont",
        "titre": "Appartement T3 avec Piscine Résidence",
        "type_bien": "Appartement",
        
        # LOCALISATION
        "adresse": "21 rue Édouard Herriot, 33310 Lormont",
        "ville": "Lormont",
        "code_postal": "33310",
        "quartier": "4 Pavillons",
        
        # RÉSIDENCE
        "residence_nom": "L'ARÈNE MARGAUX",
        "residence_securite": "Résidence entièrement sécurisée et clôturée. Le bâtiment D est lui-même clôturé dans la résidence. Accès par bip pour le portail et par code pour le reste.",
        "residence": "Résidence L'ARÈNE MARGAUX - Sécurisée, entièrement clôturée",
        
        # PRIX
        "prix": 165000,
        "prix_affiche": "165 000 €",
        "honoraires": "charge vendeur",
        "frais_notaire": 12600,
        "total_acquisition": 177600,
        "prix_m2": 2680,
        "prix_m2_marche": 2350,
        "analyse_prix": "Prix compétitif justifié par piscine + parking inclus. Estimation haute: 175 000€.",
        
        # =================================================================
        # SURFACES - OFFICIELLES PLAN TAGERIM
        # =================================================================
        "surface": 61.59,
        "surface_ponderee": 62.19,
        "surfaces_detail": {
            "Séjour + cuisine + placard": "31,56 m²",
            "Chambre 1 + placard": "11,01 m²",
            "Chambre 2 + placard": "10,25 m²",
            "Salle de bains": "3,59 m²",
            "WC": "1,22 m²",
            "Dégagement + placard": "3,96 m²",
            "Balcon": "1,20 m²"
        },
        "surface_habitable": "61,59 m²",
        "surface_balcon": "1,20 m²",
        
        # COMPOSITION
        "pieces": 3,
        "chambres": 2,
        "sdb": 1,
        "wc": 1,
        "balcon": True,
        
        # BÂTIMENT
        "etage": "4ème et dernier étage avec ascenseur",
        "batiment": "Bâtiment D - Porte D33",
        "ascenseur": True,
        "interphone": True,
        
        # EXTÉRIEURS
        "parking": "1 place extérieure numérotée INCLUSE dans le prix",
        "piscine": "Piscine collective de la résidence - accès inclus",
        
        # ÉQUIPEMENTS
        "equipements": [
            "Double vitrage intégral sur toutes les fenêtres",
            "Volets roulants électriques sur toutes les ouvertures",
            "Cuisine équipée avec micro-onde et frigo-congélateur + emplacements lave-linge et lave-vaisselle",
            "Salle de bains avec baignoire + douche italienne + double vasque",
            "WC indépendant",
            "Balcon 1,20 m² avec vue dégagée",
            "Interphone vidéo",
            "Placards dans l'entrée et dans les 2 chambres",
            "VMC"
        ],
        
        # CHAUFFAGE & ÉNERGIE
        "chauffage": "Radiateurs électriques (conseil: modernisation ~2000€ pour économies)",
        "isolation": "Bonne isolation - Température 17-19°C maintenue sans chauffage en hiver",
        "dpe": "D (estimation dans l'attente du DPE)",
        
        # ÉTAT
        "etat": "TRÈS PROPRE - Emménagement immédiat possible, aucun travaux nécessaires",
        
        # TRANSPORTS - Distances vérifiées Moovit 10/01/2026
        "transports": {
            "tramway": "Ligne A - Arrêt Buttinière à 9 min à pied (629m)",
            "bus": "Arrêt Centre Commercial 4 Pavillons à 5 min (298m) - Lignes 27, 32, 64, 66, 67",
            "bus_detail": "Arrêt Place des 2 Villes à 5 min (379m), Arrêt Iris à 6 min (388m)",
            "voiture": "Rocade A630 sortie 2 (Lormont) à 3 min",
            "bordeaux_centre": "20-25 min en tramway (correspondance possible)",
            "gare_saint_jean": "30 minutes",
            "aeroport": "45 minutes"
        },
        
        # COMMERCES
        "commerces": [
            "Centre Commercial Carrefour 4 Pavillons à 5 min à pied (300m)",
            "Hypermarché Carrefour avec galerie commerciale",
            "Boulangeries et commerces dans le centre commercial",
            "Pharmacies à proximité",
            "Restaurants et cafés"
        ],
        
        # ÉCOLES
        "ecoles": [
            "Crèche intercommunale au 64 rue Édouard Herriot (même rue !)",
            "Écoles maternelles du secteur: Paul Fort, Rosa Bonheur, Jean Rostand",
            "Écoles primaires du secteur: Condorcet, Marie Curie, Albert Camus",
            "Collège Georges Lapierre (rue Pierre Brossolette) - REP+",
            "Lycée Élie Faure à Lormont"
        ],
        
        # LOISIRS
        "loisirs": [
            "Piscine résidence sur place !",
            "Parc de l'Ermitage pour promenades",
            "Complexe sportif",
            "Berges de la Garonne"
        ],
        
        # POINTS FORTS
        "points_forts": [
            "🏊 Piscine résidence - TRÈS RARE à ce prix !",
            "🚗 Parking extérieur numéroté INCLUS",
            "🔒 Résidence L'ARÈNE MARGAUX ultra-sécurisée (bip + code)",
            "🪟 Double vitrage + volets roulants TOUTES fenêtres",
            "✨ Très propre - ZÉRO travaux",
            "🌡️ Excellente isolation thermique",
            "🚌 Bus à 5 min - Centre commercial 4 Pavillons",
            "🚃 Tramway ligne A à 9 min (Buttinière)",
            "☀️ 4ème et dernier étage très lumineux",
            "🛗 Ascenseur dans le bâtiment",
            "👶 Crèche sur la même rue",
            "💰 Prix/m² compétitif vs marché"
        ],
        
        # ARGUMENTS PAR PROFIL ACHETEUR
        "arguments": {
            "investisseur": "Forte demande locative à Lormont (étudiants, jeunes actifs Bordeaux). Loyer estimé 750-850€/mois. Rentabilité ~5.5%. Résidence sécurisée = rassurant pour locataires.",
            "primo_accedant": "Idéal 1ère acquisition - prix accessible, 2 vraies chambres, piscine, résidence sécurisée, proche transports et commerces.",
            "famille": "2 chambres avec placards, piscine pour les enfants, crèche sur la même rue, résidence ultra-sécurisée (bip + code), quartier calme.",
            "senior": "4ème et dernier étage avec ascenseur, résidence L'ARÈNE MARGAUX très sécurisée, tous commerces à 5 min à pied, pas d'entretien extérieur."
        },
        
        # VISITE VIRTUELLE
        "visite_virtuelle": "https://my.matterport.com/show/?m=7zeq1p",
        
        # CHARGES & COPROPRIÉTÉ (données réelles 2024-2025)
        "charges_mensuelles": 110,
        "charges_detail": {
            "total_annuel": "~1 300 €/an",
            "par_mois": "~110 €/mois",
            "trimestriel": "~334 €",
            "detail": {
                "Générales": "134 €/trim",
                "Bâtiment D": "94 €/trim",
                "Piscine": "34 €/trim",
                "Ascenseur D": "48 €/trim",
                "VMC": "2 €/trim",
                "Antenne/Interphone": "9 €/trim",
                "Fonds travaux ALUR": "17 €/trim"
            }
        },
        "taxe_fonciere": 1351,
        "taxe_fonciere_mensuel": 113,
        "cout_total_mensuel": "~221 €/mois (charges 110€ + TF 113€)",
        
        # SYNDIC
        "syndic": {
            "nom": "CITYA Lanaverre Talence",
            "gestionnaire": "Eric CLAVIER",
            "tel": "05.57.35.87.00",
            "email": "eclavier@citya.com",
            "adresse": "170 cours Gambetta, 33400 Talence",
            "espace_copro": "www.citya.com"
        },
        
        # COPROPRIÉTÉ
        "copropriete": {
            "immeuble": "5074 - L'ARENE MARGAUX",
            "lot_appartement": "1140",
            "lot_parking": "1276 (P265)",
            "tantiemes_appart": "79/11616",
            "tantiemes_parking": "2/11616",
            "reserve": "194,68 €",
            "fonds_travaux": "~558 €"
        },
        
        # POINTS ATTENTION RÉSIDENCE (CR CS Sept 2025)
        "points_attention": [
            "Assurance copro en hausse (sinistralité)",
            "Franchise 2500€ si sinistre",
            "Porte parking B en remplacement",
            "Vidéosurveillance à moderniser",
            "Ravalement en projet"
        ],
        
        # CONTACT
        "agence": "ICI Dordogne",
        "tel": "05 53 13 33 33",
        "email": "agence@icidordogne.fr",
        "site": "https://lormont-t3-piscine-icidordogne.netlify.app/"
    },
    
    # MANZAC (inchangé)
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
    return BIENS_CONFIG.get(bien_id.lower())

def search_web(query: str, domains: List[str] = None) -> str:
    if not TAVILY_API_KEY:
        return ""
    default_domains = ["bordeaux.fr", "lormont.fr", "seloger.com", "leboncoin.fr", "meilleursagents.com"]
    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={"api_key": TAVILY_API_KEY, "query": query, "search_depth": "basic", "max_results": 3, "include_domains": domains or default_domains},
            timeout=8
        )
        if response.status_code == 200:
            results = response.json().get("results", [])
            if results:
                return "\n".join([f"• {r.get('title','')[:50]}: {r.get('content','')[:150]}" for r in results[:3]])
    except:
        pass
    return ""

def build_system_prompt(bien: Dict, langue: str = "fr") -> str:
    lang = LANG_CONFIG.get(langue, LANG_CONFIG["fr"])
    surfaces = "\n".join([f"  • {k}: {v}" for k, v in bien.get("surfaces_detail", {}).items()])
    equipements = "\n".join([f"  ✓ {e}" for e in bien.get("equipements", [])])
    points_forts = "\n".join(bien.get("points_forts", []))
    transports = "\n".join([f"  • {k.upper()}: {v}" for k, v in bien.get("transports", {}).items()]) if isinstance(bien.get("transports"), dict) else ""
    commerces = "\n".join([f"  • {c}" for c in bien.get("commerces", [])])
    ecoles = "\n".join([f"  • {e}" for e in bien.get("ecoles", [])])
    arguments = "\n".join([f"  → {k.upper()}: {v}" for k, v in bien.get("arguments", {}).items()])
    
    return f"""Tu es Sophie, assistante virtuelle de l'agence ICI Dordogne.
{lang['instruction']}

🏠 {bien.get('titre', 'Bien immobilier')}

📍 LOCALISATION: {bien.get('adresse', '')} | Résidence: {bien.get('residence_nom', '')}
🔒 SÉCURITÉ: {bien.get('residence_securite', '')}

💰 PRIX: {bien.get('prix_affiche', '')} | {bien.get('prix_m2', '')} €/m² | Frais notaire: ~{bien.get('frais_notaire', '')} €

📐 SURFACES (officielles TAGERIM):
Surface habitable: {bien.get('surface_habitable', '')}
{surfaces}

🏗️ COMPOSITION: T{bien.get('pieces', '')} | {bien.get('chambres', '')} chambres | Étage: {bien.get('etage', '')}

🔧 ÉQUIPEMENTS:
{equipements}

🚗 EXTÉRIEURS: Parking: {bien.get('parking', '')} | Piscine: {bien.get('piscine', '')}

🌡️ ÉNERGIE: {bien.get('chauffage', '')} | DPE: {bien.get('dpe', '')} | {bien.get('isolation', '')}

🚃 TRANSPORTS (vérifiés Moovit):
{transports}

🛒 COMMERCES: {commerces}

🏫 ÉCOLES: {ecoles}

⭐ POINTS FORTS:
{points_forts}

🎯 ARGUMENTS:
{arguments}

🔗 VISITE VIRTUELLE: {bien.get('visite_virtuelle', '')}

📋 TON RÔLE:
1. INFORMER avec précision
2. CONVERTIR vers une visite (nom → téléphone → disponibilités)
3. Style chaleureux, concis (2-3 phrases max)

📞 CONTACT: {bien.get('tel', '05 53 13 33 33')}
"""

def send_lead_email(bien_id: str, lead_data: Dict, conversation: List[Dict] = None) -> bool:
    try:
        bien = get_bien_config(bien_id) or {}
        conv_html = "<br>".join([f"<b>{'👤 Visiteur' if m['role'] == 'user' else '🤖 Sophie'}:</b> {m['content']}" for m in (conversation or [])[-10:]])
        subject = f"🏠 LEAD Chat Vitrine - {bien.get('titre', bien_id)}"
        body = f"""<html><body>
<h1>🏠 Nouveau Lead - {bien.get('titre', bien_id)}</h1>
<p><strong>Nom:</strong> {lead_data.get('nom', 'NC')}</p>
<p><strong>Tél:</strong> {lead_data.get('telephone', 'NC')}</p>
<p><strong>Dispo:</strong> {lead_data.get('disponibilites', 'NC')}</p>
<h2>Conversation</h2>{conv_html}
<p><em>Lead capturé le {datetime.now().strftime('%d/%m/%Y à %H:%M')}</em></p>
</body></html>"""
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
        return True
    except:
        return False

def chat_vitrine_handler(body: Dict[str, Any]) -> Dict[str, Any]:
    try:
        bien_id = body.get("bien_id", "").lower()
        messages = body.get("messages", [])
        langue = body.get("langue", "fr")
        lead_data = body.get("lead_data", {})
        bien = get_bien_config(bien_id)
        if not bien:
            return {"content": [{"type": "text", "text": f"Bien '{bien_id}' non trouvé."}], "error": "Bien non trouvé"}
        if not ANTHROPIC_API_KEY:
            return {"content": [{"type": "text", "text": "Erreur technique. Appelez le 05 53 13 33 33 !"}], "error": "API non configurée"}
        system_prompt = build_system_prompt(bien, langue)
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": "claude-sonnet-4-20250514", "max_tokens": 600, "system": system_prompt, "messages": messages},
            timeout=30
        )
        if response.status_code != 200:
            return {"content": [{"type": "text", "text": "Erreur technique. Appelez le 05 53 13 33 33 !"}], "error": f"API error: {response.status_code}"}
        result = response.json()
        assistant_text = result["content"][0]["text"]
        lead_captured = False
        if lead_data.get("nom") and lead_data.get("telephone") and lead_data.get("disponibilites"):
            send_lead_email(bien_id, lead_data, messages)
            lead_captured = True
        return {"content": [{"type": "text", "text": assistant_text}], "lead_captured": lead_captured}
    except Exception as e:
        return {"content": [{"type": "text", "text": "Erreur. Appelez le 05 53 13 33 33 !"}], "error": str(e)}

def register_chat_vitrine_routes(server):
    try:
        server.register_route("POST", "/chat-vitrine", chat_vitrine_handler)
        logger.info("✅ [CHAT-VITRINE] Route /chat-vitrine V3.3 enregistrée (surfaces TAGERIM)")
    except Exception as e:
        logger.error(f"❌ [CHAT-VITRINE] Erreur: {e}")
