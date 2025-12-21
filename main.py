"""
AXI - SERVICE UNIFIÉ RAILWAY
==============================
Endpoints:
- GET  /              → Interface chat
- GET  /memory        → Lire MEMORY.md
- POST /memory        → Écrire MEMORY.md
- GET  /briefing      → Contexte complet pour Axis
- GET  /status        → Health check
- GET  /run-veille    → Exécute la veille DPE et envoie l'email
- GET  /test-veille   → Test sans envoi d'email
- POST /chat          → Envoyer un message à Axi

Auteur: Axis pour Ludo
Version: 2.0 - 21/12/2025
"""

import os
import json
import re
import urllib.request
import urllib.parse
import smtplib
import tempfile
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

# ============================================================
# CONFIGURATION
# ============================================================

# Codes postaux ICI Dordogne
CODES_POSTAUX = ["24510", "24150", "24480", "24260", "24620", "24220", 
                 "24330", "24110", "24520", "24140", "24380", "24750"]

# Email
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "u5050786429@gmail.com"
SMTP_PASSWORD = "izemquwmmqjdasrk"
EMAIL_TO = "agence@icidordogne.fr"
EMAIL_CC = "laetony@gmail.com"

# API
API_DPE = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe03existant/lines"

# Prix moyens par zone
PRIX_M2 = {
    "24260": 1800, "24150": 1500, "24480": 1400, "24510": 1600,
    "24620": 1700, "24220": 1500, "24330": 1400, "24110": 1300,
    "24520": 1200, "24140": 1400, "24380": 1300, "24750": 1600,
}

COULEURS_DPE = {
    'A': '#319834', 'B': '#33a357', 'C': '#cbce00',
    'D': '#f2e600', 'E': '#ebb700', 'F': '#d66f00', 'G': '#c81e01'
}


# ============================================================
# UTILITAIRES FICHIERS
# ============================================================

def lire_fichier(chemin):
    try:
        with open(chemin, 'r', encoding='utf-8') as f:
            return f.read()
    except:
        return ""

def ecrire_fichier(chemin, contenu):
    with open(chemin, 'w', encoding='utf-8') as f:
        f.write(contenu)

def ajouter_fichier(chemin, contenu):
    with open(chemin, 'a', encoding='utf-8') as f:
        f.write(contenu)


# ============================================================
# VEILLE DPE - FONCTIONS
# ============================================================

def http_get(url, timeout=30):
    """GET request simple"""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Axi/2.0'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8'))
    except:
        return None

def get_nouveaux_dpe(heures=26):
    """Récupère les DPE des dernières X heures"""
    date_limite = datetime.now() - timedelta(hours=heures)
    tous_dpe = []
    
    for cp in CODES_POSTAUX:
        try:
            params = urllib.parse.urlencode({
                "size": 50,
                "qs": f"code_postal_ban:{cp}",
                "select": "numero_dpe,date_reception_dpe,adresse_ban,nom_commune_ban,code_postal_ban,type_batiment,surface_habitable_logement,annee_construction,etiquette_dpe,etiquette_ges,cout_total_5_usages,type_energie_principale_chauffage",
                "sort": "-date_reception_dpe"
            })
            url = f"{API_DPE}?{params}"
            data = http_get(url)
            
            if data and "results" in data:
                for dpe in data["results"]:
                    date_str = dpe.get("date_reception_dpe", "")
                    if date_str:
                        try:
                            date_dpe = datetime.fromisoformat(date_str.split('T')[0])
                            if date_dpe >= date_limite:
                                tous_dpe.append(dpe)
                        except:
                            pass
        except:
            pass
    
    # Dédupliquer
    dpe_uniques = {d.get("numero_dpe"): d for d in tous_dpe if d.get("numero_dpe")}
    return list(dpe_uniques.values())


def get_mairie_info(commune, cp):
    """Récupère les infos mairie"""
    try:
        url = f"https://geo.api.gouv.fr/communes?nom={urllib.parse.quote(commune)}&codePostal={cp}&fields=code&limit=1"
        data = http_get(url, timeout=10)
        if data and len(data) > 0:
            code_insee = data[0]['code']
            url2 = f"https://etablissements-publics.api.gouv.fr/v3/communes/{code_insee}/mairie"
            data2 = http_get(url2, timeout=10)
            if data2 and data2.get('features'):
                props = data2['features'][0]['properties']
                return {'tel': props.get('telephone', ''), 'email': props.get('email', '')}
    except:
        pass
    return {'tel': '', 'email': ''}


def generer_fiche_html(dpe):
    """Génère le HTML d'une fiche prospect"""
    adresse = dpe.get('adresse_ban', 'Adresse inconnue')
    commune = dpe.get('nom_commune_ban', '')
    cp = str(dpe.get('code_postal_ban', ''))
    surface = float(dpe.get('surface_habitable_logement', 0) or 0)
    etiquette = dpe.get('etiquette_dpe', '?')
    date_dpe = str(dpe.get('date_reception_dpe', ''))[:10]
    type_bien = dpe.get('type_batiment', 'Logement')
    cout = float(dpe.get('cout_total_5_usages', 0) or 0)
    chauffage = dpe.get('type_energie_principale_chauffage', 'N/C')
    annee = dpe.get('annee_construction', 'N/C')
    
    couleur = COULEURS_DPE.get(etiquette, '#888')
    is_passoire = etiquette in ['F', 'G']
    
    prix_m2 = PRIX_M2.get(cp, 1500)
    est_bas = int(surface * prix_m2 * 0.85)
    est_haut = int(surface * prix_m2 * 1.15)
    
    mairie = get_mairie_info(commune, cp)
    lien_maps = f"https://www.google.com/maps/search/{urllib.parse.quote(f'{adresse}, {cp} {commune}')}"
    
    badge = '<div style="background:#c81e01;color:white;padding:8px 15px;border-radius:5px;display:inline-block;margin-top:10px;font-weight:bold;">🔥 PASSOIRE ÉNERGÉTIQUE</div>' if is_passoire else ''
    
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 0; background: #f5f5f5; }}
        .container {{ max-width: 700px; margin: 20px auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, #2E7D32, #1B5E20); color: white; padding: 30px; }}
        .header h1 {{ margin: 0 0 5px 0; font-size: 16px; opacity: 0.9; }}
        .header h2 {{ margin: 0; font-size: 22px; }}
        .content {{ padding: 30px; }}
        .section {{ margin-bottom: 25px; }}
        .section-title {{ font-size: 12px; color: #888; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; border-bottom: 2px solid #eee; padding-bottom: 8px; }}
        .grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; }}
        .box {{ background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; }}
        .box .label {{ font-size: 11px; color: #888; }}
        .box .value {{ font-size: 18px; font-weight: bold; margin-top: 5px; }}
        .dpe {{ display: flex; align-items: center; gap: 20px; background: #f8f9fa; padding: 20px; border-radius: 8px; }}
        .dpe-badge {{ width: 60px; height: 60px; display: flex; align-items: center; justify-content: center; font-size: 28px; font-weight: bold; color: white; border-radius: 8px; }}
        .estimation {{ background: linear-gradient(135deg, #e8f5e9, #c8e6c9); padding: 20px; border-radius: 8px; }}
        .estimation .prix {{ font-size: 26px; font-weight: bold; color: #2E7D32; }}
        .mairie {{ background: #e3f2fd; padding: 15px; border-radius: 8px; }}
        .links a {{ display: inline-block; background: #2E7D32; color: white; padding: 10px 20px; border-radius: 6px; text-decoration: none; margin-right: 10px; }}
        .checklist {{ background: #fff3e0; padding: 20px; border-radius: 8px; }}
        .footer {{ background: #f5f5f5; padding: 20px; text-align: center; font-size: 11px; color: #888; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏠 NOUVEAU DPE DÉTECTÉ</h1>
            <h2>{adresse}</h2>
            <p style="margin:5px 0;opacity:0.9;">{cp} {commune}</p>
            <div style="margin-top:10px;display:inline-block;background:rgba(255,255,255,0.2);padding:5px 12px;border-radius:20px;font-size:12px;">📅 DPE du {date_dpe}</div>
            {badge}
        </div>
        
        <div class="content">
            <div class="section">
                <div class="section-title">Caractéristiques</div>
                <div class="grid">
                    <div class="box"><div class="label">Type</div><div class="value">{type_bien}</div></div>
                    <div class="box"><div class="label">Surface</div><div class="value">{surface:.0f} m²</div></div>
                    <div class="box"><div class="label">Année</div><div class="value">{annee}</div></div>
                </div>
            </div>
            
            <div class="section">
                <div class="section-title">Performance énergétique</div>
                <div class="dpe">
                    <div class="dpe-badge" style="background:{couleur}">{etiquette}</div>
                    <div>
                        <div style="font-size:18px;font-weight:bold;">Classe : {etiquette}</div>
                        <div style="color:#666;margin-top:5px;">Coût : {cout:.0f} €/an • {chauffage}</div>
                    </div>
                </div>
            </div>
            
            <div class="section">
                <div class="section-title">Estimation</div>
                <div class="estimation">
                    <div class="prix">{est_bas:,} € - {est_haut:,} €</div>
                    <div style="font-size:12px;color:#666;margin-top:5px;">~{prix_m2} €/m²</div>
                </div>
            </div>
            
            <div class="section">
                <div class="section-title">Mairie de {commune}</div>
                <div class="mairie">
                    📞 {mairie['tel'] or 'N/C'} • 📧 {mairie['email'] or 'N/C'}
                </div>
            </div>
            
            <div class="section">
                <div class="section-title">Liens</div>
                <div class="links">
                    <a href="{lien_maps}">📍 Maps</a>
                    <a href="https://www.cadastre.gouv.fr/scpc/rechercherPlan.do" style="background:#1976D2;">📋 Cadastre</a>
                </div>
            </div>
            
            <div class="section">
                <div class="section-title">Actions</div>
                <div class="checklist">
                    <ul style="list-style:none;padding:0;margin:0;">
                        <li style="margin:6px 0;">☐ Vérifier si en vente</li>
                        <li style="margin:6px 0;">☐ Noter référence cadastre</li>
                        <li style="margin:6px 0;">☐ Demander nom propriétaire (mairie)</li>
                        <li style="margin:6px 0;">☐ Envoyer courrier "cadeau"</li>
                    </ul>
                </div>
            </div>
        </div>
        
        <div class="footer">
            ICI Dordogne • {datetime.now().strftime('%d/%m/%Y %H:%M')} • 05 53 54 75 75
        </div>
    </div>
</body>
</html>"""


def envoyer_email_veille(dpe_list, fiches_html):
    """Envoie l'email récap + fiches"""
    nb = len(dpe_list)
    nb_p = len([d for d in dpe_list if d.get('etiquette_dpe') in ['F', 'G']])
    
    html = f"""<html><body style="font-family:Arial;padding:20px;max-width:700px;">
    <h2 style="color:#2E7D32;">🏠 Veille DPE - {datetime.now().strftime('%d/%m/%Y')}</h2>
    <p><strong>{nb} DPE</strong> détecté(s).</p>
    {"<p style='color:#c62828;font-weight:bold;'>🔥 Dont " + str(nb_p) + " passoire(s)</p>" if nb_p else ""}
    
    <table style="border-collapse:collapse;width:100%;font-size:14px;">
        <tr style="background:#2E7D32;color:white;">
            <th style="padding:10px;text-align:left;">Commune</th>
            <th style="padding:10px;text-align:left;">Adresse</th>
            <th style="padding:10px;text-align:center;">DPE</th>
            <th style="padding:10px;text-align:center;">m²</th>
        </tr>"""
    
    for i, d in enumerate(sorted(dpe_list, key=lambda x: x.get('etiquette_dpe', 'Z'))):
        bg = '#ffebee' if d.get('etiquette_dpe') in ['F','G'] else ('#f5f5f5' if i%2==0 else 'white')
        html += f"""<tr style="background:{bg};">
            <td style="padding:10px;border-bottom:1px solid #eee;">{d.get('nom_commune_ban','')}</td>
            <td style="padding:10px;border-bottom:1px solid #eee;">{d.get('adresse_ban','')[:40]}</td>
            <td style="padding:10px;text-align:center;border-bottom:1px solid #eee;font-weight:bold;">{d.get('etiquette_dpe','?')}</td>
            <td style="padding:10px;text-align:center;border-bottom:1px solid #eee;">{d.get('surface_habitable_logement',0):.0f}</td>
        </tr>"""
    
    html += """</table><p style="margin-top:20px;">📎 Fiches en pièces jointes (HTML, ouvrir dans navigateur)</p>
    <hr style="margin:30px 0;border:none;border-top:1px solid #eee;">
    <p style="color:#888;font-size:12px;">Veille automatique ICI Dordogne</p></body></html>"""
    
    msg = MIMEMultipart()
    subj = f"🔥 {nb_p} passoire(s) + {nb-nb_p} autres" if nb_p else f"🏠 {nb} DPE"
    msg['Subject'] = f"{subj} - {datetime.now().strftime('%d/%m/%Y')}"
    msg['From'] = SMTP_USER
    msg['To'] = EMAIL_TO
    msg['Cc'] = EMAIL_CC
    msg.attach(MIMEText(html, 'html', 'utf-8'))
    
    # Pièces jointes HTML
    for i, (dpe, fiche_html) in enumerate(zip(dpe_list, fiches_html)):
        commune = dpe.get('nom_commune_ban', 'x')[:15].replace(' ', '_')
        filename = f"fiche_{i+1}_{commune}.html"
        part = MIMEApplication(fiche_html.encode('utf-8'), Name=filename)
        part['Content-Disposition'] = f'attachment; filename="{filename}"'
        msg.attach(part)
    
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASSWORD)
        s.sendmail(SMTP_USER, [EMAIL_TO, EMAIL_CC], msg.as_string())


def envoyer_email_vide():
    html = f"""<html><body style="font-family:Arial;padding:20px;">
    <h2 style="color:#2E7D32;">🏠 Veille DPE - {datetime.now().strftime('%d/%m/%Y')}</h2>
    <p>Aucun nouveau DPE sur vos secteurs.</p></body></html>"""
    
    msg = MIMEMultipart()
    msg['Subject'] = f"🏠 Veille DPE - RAS - {datetime.now().strftime('%d/%m/%Y')}"
    msg['From'] = SMTP_USER
    msg['To'] = EMAIL_TO
    msg['Cc'] = EMAIL_CC
    msg.attach(MIMEText(html, 'html', 'utf-8'))
    
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASSWORD)
        s.sendmail(SMTP_USER, [EMAIL_TO, EMAIL_CC], msg.as_string())


def executer_veille(envoyer=True):
    """Exécute la veille complète"""
    dpe_list = get_nouveaux_dpe(heures=26)
    
    if not dpe_list:
        if envoyer:
            envoyer_email_vide()
        return {"status": "ok", "count": 0, "message": "Aucun DPE"}
    
    # Générer les fiches
    fiches_html = [generer_fiche_html(dpe) for dpe in dpe_list]
    
    # Envoyer
    if envoyer:
        envoyer_email_veille(dpe_list, fiches_html)
    
    nb_p = len([d for d in dpe_list if d.get('etiquette_dpe') in ['F', 'G']])
    
    return {
        "status": "ok",
        "count": len(dpe_list),
        "passoires": nb_p,
        "sent_to": EMAIL_TO if envoyer else "non envoyé"
    }


# ============================================================
# INTERFACE CHAT (optionnel, conservé pour compatibilité)
# ============================================================

def generer_page_html_chat(conversations_html):
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Axi - ICI Dordogne</title>
    <style>
        body {{ font-family: Georgia, serif; background: #1a1a2e; color: #eee; padding: 20px; }}
        h1 {{ color: #e94560; }}
        .status {{ background: #16213e; padding: 15px; border-radius: 8px; margin: 20px 0; }}
        .endpoint {{ background: #0f3460; padding: 10px 15px; border-radius: 5px; margin: 5px 0; font-family: monospace; }}
        a {{ color: #4ade80; }}
    </style>
</head>
<body>
    <h1>🏠 Axi - Service ICI Dordogne</h1>
    
    <div class="status">
        <strong>Status:</strong> En ligne<br>
        <strong>Heure:</strong> {datetime.now().strftime('%d/%m/%Y %H:%M')}
    </div>
    
    <h2>Endpoints disponibles</h2>
    
    <div class="endpoint">GET <a href="/memory">/memory</a> → Lire les consignes</div>
    <div class="endpoint">POST /memory → Écrire les consignes</div>
    <div class="endpoint">GET <a href="/briefing">/briefing</a> → Contexte complet pour Axis</div>
    <div class="endpoint">GET <a href="/status">/status</a> → Health check JSON</div>
    <div class="endpoint">GET <a href="/test-veille">/test-veille</a> → Test veille DPE (sans email)</div>
    <div class="endpoint">GET <a href="/run-veille">/run-veille</a> → Exécuter veille DPE + envoyer email</div>
    
    <h2>Configuration veille</h2>
    <ul>
        <li>Destinataire: {EMAIL_TO}</li>
        <li>Copie: {EMAIL_CC}</li>
        <li>Codes postaux: {len(CODES_POSTAUX)}</li>
    </ul>
    
    {conversations_html}
</body>
</html>"""


# ============================================================
# HANDLER HTTP
# ============================================================

class AxiHandler(BaseHTTPRequestHandler):
    
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def send_text(self, text, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(text.encode('utf-8'))
    
    def send_html(self, html, status=200):
        self.send_response(status)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))
    
    def do_GET(self):
        path = self.path.split('?')[0]
        
        # === /memory ===
        if path == "/memory":
            memory = lire_fichier("MEMORY.md")
            if not memory:
                memory = "# MEMORY\n\nAucune consigne."
            self.send_text(memory)
            return
        
        # === /briefing ===
        if path == "/briefing":
            memory = lire_fichier("MEMORY.md") or "Aucune consigne."
            briefing = f"""=== BRIEFING AXI ===
Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}

=== MEMORY (CONSIGNES PRIORITAIRES) ===
{memory}

=== STATUS SERVICE ===
- Veille DPE: Prête
- Email to: {EMAIL_TO}
- Codes postaux: {len(CODES_POSTAUX)}
"""
            self.send_text(briefing)
            return
        
        # === /status ===
        if path == "/status":
            self.send_json({
                "status": "ok",
                "time": datetime.now().isoformat(),
                "service": "Axi ICI Dordogne",
                "memory_exists": os.path.exists("MEMORY.md"),
                "email_to": EMAIL_TO,
                "codes_postaux": len(CODES_POSTAUX)
            })
            return
        
        # === /test-veille ===
        if path == "/test-veille":
            try:
                result = executer_veille(envoyer=False)
                self.send_json(result)
            except Exception as e:
                self.send_json({"status": "error", "message": str(e)}, 500)
            return
        
        # === /run-veille ===
        if path == "/run-veille":
            try:
                result = executer_veille(envoyer=True)
                self.send_json(result)
            except Exception as e:
                self.send_json({"status": "error", "message": str(e)}, 500)
            return
        
        # === / (accueil) ===
        html = generer_page_html_chat("")
        self.send_html(html)
    
    def do_POST(self):
        path = self.path.split('?')[0]
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else ""
        
        # === POST /memory ===
        if path == "/memory":
            # Supporter form-urlencoded et raw text
            if 'contenu=' in post_data:
                params = urllib.parse.parse_qs(post_data)
                contenu = params.get('contenu', [''])[0]
            else:
                contenu = post_data
            
            if contenu.strip():
                ecrire_fichier("MEMORY.md", contenu)
                self.send_json({"status": "ok", "message": "Memory updated"})
            else:
                self.send_json({"status": "error", "message": "Empty content"}, 400)
            return
        
        # === POST /contact ===
        if path == "/contact":
            try:
                data = json.loads(post_data)
                name = data.get('name', '')
                email = data.get('email', '')
                phone = data.get('phone', 'Non renseigné')
                message = data.get('message', '')
                bien = data.get('bien', 'Bien non spécifié')
                
                # Construire l'email
                html = f"""<html><body style="font-family:Arial;padding:20px;">
                <h2 style="color:#2E7D32;">📬 Nouvelle demande de renseignement</h2>
                <p><strong>Bien concerné:</strong> {bien}</p>
                <hr style="border:none;border-top:1px solid #eee;margin:20px 0;">
                <p><strong>Nom:</strong> {name}</p>
                <p><strong>Email:</strong> <a href="mailto:{email}">{email}</a></p>
                <p><strong>Téléphone:</strong> {phone}</p>
                <hr style="border:none;border-top:1px solid #eee;margin:20px 0;">
                <p><strong>Message:</strong></p>
                <p style="background:#f5f5f5;padding:15px;border-radius:8px;">{message}</p>
                <hr style="border:none;border-top:1px solid #eee;margin:20px 0;">
                <p style="color:#888;font-size:12px;">Envoyé depuis le site vitrine ICI Dordogne</p>
                </body></html>"""
                
                msg = MIMEMultipart()
                msg['Subject'] = f"📬 Demande de renseignement - {bien}"
                msg['From'] = SMTP_USER
                msg['To'] = EMAIL_TO
                msg['Cc'] = EMAIL_CC
                msg['Reply-To'] = email
                msg.attach(MIMEText(html, 'html', 'utf-8'))
                
                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as s:
                    s.starttls()
                    s.login(SMTP_USER, SMTP_PASSWORD)
                    s.sendmail(SMTP_USER, [EMAIL_TO, EMAIL_CC], msg.as_string())
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok", "message": "Email sent"}).encode('utf-8'))
                
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
            return
        
        # === POST /chat-proxy ===
        if path == "/chat-proxy":
            try:
                data = json.loads(post_data)
                system_prompt = data.get('system', '')
                messages = data.get('messages', [])
                site_id = data.get('site_id', 'default')
                
                # Charger le memo du site
                try:
                    memos = json.loads(lire_fichier("SITE_MEMOS.json") or "{}")
                except:
                    memos = {}
                site_memo = memos.get(site_id, "")
                
                # Détecter #memo dans le dernier message pour ajouter des infos
                last_msg = messages[-1].get('content', '') if messages else ''
                if last_msg.strip().startswith('#memo '):
                    memo_content = last_msg.strip()[6:].strip()
                    if site_memo:
                        site_memo += "\n" + memo_content
                    else:
                        site_memo = memo_content
                    memos[site_id] = site_memo
                    ecrire_fichier("SITE_MEMOS.json", json.dumps(memos, ensure_ascii=False))
                    # Répondre confirmation
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({"content": [{"text": f"✅ Mémo enregistré : {memo_content}"}]}).encode('utf-8'))
                    return
                
                # Ajouter le memo au system prompt
                if site_memo:
                    system_prompt += f"\n\nINFORMATIONS MÉMORISÉES:\n{site_memo}"
                
                # Appel API Anthropic avec web search
                api_key = os.environ.get("ANTHROPIC_API_KEY")
                req_data = json.dumps({
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 1024,
                    "system": system_prompt,
                    "messages": messages,
                    "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}]
                }).encode('utf-8')
                
                req = urllib.request.Request(
                    "https://api.anthropic.com/v1/messages",
                    data=req_data,
                    headers={
                        'Content-Type': 'application/json',
                        'x-api-key': api_key,
                        'anthropic-version': '2023-06-01',
                        'anthropic-beta': 'web-search-2025-03-05'
                    }
                )
                
                with urllib.request.urlopen(req, timeout=60) as response:
                    result = json.loads(response.read().decode('utf-8'))
                
                # Extraire le texte de la réponse (ignorer les blocs web_search)
                text_content = ""
                for block in result.get("content", []):
                    if block.get("type") == "text":
                        text_content += block.get("text", "")
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"content": [{"text": text_content}]}).encode('utf-8'))
                
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
            return
        
        self.send_json({"status": "error", "message": "Unknown endpoint"}, 404)
    
    def do_OPTIONS(self):
        """Handler pour les requêtes CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")


# ============================================================
# MAIN
# ============================================================

def init_files():
    """Initialise les fichiers si nécessaires"""
    if not os.path.exists("MEMORY.md"):
        ecrire_fichier("MEMORY.md", """# MEMORY - CONSIGNES AXIS

## RÈGLES
- Emails: toujours laetony@gmail.com en copie
- Validation: ne rien lancer sans accord Ludo
- Qualité: être critique avant de passer à la suite

## VEILLE DPE
- Heure: 8h00
- Destinataire: agence@icidordogne.fr
- Copie: laetony@gmail.com
""")


def main():
    print("=" * 50)
    print("AXI - SERVICE UNIFIÉ ICI DORDOGNE")
    print("=" * 50)
    
    init_files()
    
    port = int(os.environ.get("PORT", 8080))
    serveur = HTTPServer(('0.0.0.0', port), AxiHandler)
    
    print(f"Port: {port}")
    print(f"Endpoints: /memory, /briefing, /status, /run-veille, /test-veille")
    print(f"Email to: {EMAIL_TO}")
    print("En attente...")
    
    serveur.serve_forever()


if __name__ == "__main__":
    main()
