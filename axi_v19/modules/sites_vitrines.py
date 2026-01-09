# axi_v19/modules/sites_vitrines.py
"""
Module Sites Vitrines V19 - Chat et Contact pour sites immobiliers
(Lormont, Manzac, etc.)

"Je ne lâche pas." 💪
"""

import os
import json
import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any
import requests

logger = logging.getLogger("axi_v19.sites_vitrines")

# =============================================================================
# CONFIGURATION
# =============================================================================

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GMAIL_USER = os.getenv("GMAIL_USER", "u5050786429@gmail.com")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "izemquwmmqjdasrk")
EMAIL_TO = os.getenv("EMAIL_TO", "agence@icidordogne.fr")
EMAIL_CC = os.getenv("EMAIL_CC", "laetony@gmail.com")


# =============================================================================
# HANDLER: /chat-proxy
# =============================================================================

def chat_proxy_handler(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Proxy chat pour les sites vitrines (Manzac, Lormont, etc.)
    Reçoit: { system: "...", messages: [...], site_id: "..." }
    Renvoie: La réponse Claude au format { content: [...] }
    """
    try:
        system_prompt = body.get('system', '')
        messages = body.get('messages', [])
        site_id = body.get('site_id', 'unknown')
        
        if not ANTHROPIC_API_KEY:
            logger.error("[CHAT-PROXY] API key not configured")
            return {"error": "API key not configured"}
        
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
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"[CHAT-PROXY] Site: {site_id} | Messages: {len(messages)}")
            return {
                "content": [{"type": "text", "text": result["content"][0]["text"]}]
            }
        else:
            logger.error(f"[CHAT-PROXY] Claude error: {response.status_code} - {response.text}")
            return {"error": f"Claude API error: {response.status_code}"}
            
    except Exception as e:
        logger.error(f"[CHAT-PROXY ERROR] {e}")
        return {"error": str(e)}


# =============================================================================
# HANDLER: /contact
# =============================================================================

def contact_handler(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Reçoit les demandes de contact des sites vitrines
    Envoie un email à l'agence
    """
    try:
        name = body.get('name', 'Inconnu')
        email = body.get('email', '')
        phone = body.get('phone', 'Non renseigné')
        message = body.get('message', '')
        bien = body.get('bien', 'Non spécifié')
        site = body.get('site', 'unknown')
        
        # Email HTML
        subject = f"🏠 Contact Site Vitrine - {bien}"
        html_body = f'''
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: #1a5d4a; color: white; padding: 20px; text-align: center;">
                <h2>📬 Nouvelle demande de contact</h2>
            </div>
            <div style="padding: 20px; background: #f5f5f5;">
                <h3 style="color: #1a5d4a;">Informations du prospect</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Nom</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;">{name}</td></tr>
                    <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Email</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;"><a href="mailto:{email}">{email}</a></td></tr>
                    <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Téléphone</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;"><a href="tel:{phone}">{phone}</a></td></tr>
                    <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Bien concerné</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;">{bien}</td></tr>
                    <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Site source</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;">{site}</td></tr>
                </table>
                <h3 style="color: #1a5d4a; margin-top: 20px;">Message</h3>
                <div style="background: white; padding: 15px; border-radius: 8px; border-left: 4px solid #1a5d4a;">
                    {message or '<em>Aucun message</em>'}
                </div>
            </div>
            <div style="background: #1a5d4a; color: white; padding: 10px; text-align: center; font-size: 12px;">
                Envoyé depuis le site vitrine {site} • ICI Dordogne
            </div>
        </body>
        </html>
        '''
        
        # Envoi email
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = GMAIL_USER
        msg['To'] = EMAIL_TO
        msg['Cc'] = EMAIL_CC
        msg['Reply-To'] = email
        msg.attach(MIMEText(html_body, 'html'))
        
        context = ssl.create_default_context()
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls(context=context)
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"[CONTACT] Email envoyé - {name} - {bien} - Site: {site}")
        return {"success": True, "message": "Contact envoyé"}
        
    except Exception as e:
        logger.error(f"[CONTACT ERROR] {e}")
        return {"error": str(e)}


# =============================================================================
# ENREGISTREMENT DES ROUTES
# =============================================================================

def register_sites_vitrines_routes(server):
    """Enregistre les routes pour les sites vitrines."""
    
    # Routes POST
    server.register_route('POST', '/chat-proxy', chat_proxy_handler)
    server.register_route('POST', '/contact', contact_handler)
    
    logger.info("✅ Routes sites vitrines enregistrées: /chat-proxy, /contact")
