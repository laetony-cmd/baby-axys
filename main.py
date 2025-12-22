"""
AXI - SERVICE UNIFIÉ RAILWAY v3
================================
Endpoints:
- GET  /                    → Interface
- GET  /memory              → Lire MEMORY.md
- POST /memory              → Écrire MEMORY.md
- GET  /briefing            → Contexte complet pour Axis
- GET  /status              → Health check
- GET  /run-veille          → Veille DPE + email
- GET  /test-veille         → Test veille DPE (sans email)
- GET  /run-veille-concurrence  → Veille concurrentielle + email
- GET  /test-veille-concurrence → Test veille concurrence (sans email)

Crons:
- 07h00 Paris: Veille concurrentielle
- 08h00 Paris: Veille DPE

Auteur: Axis pour Ludo
Version: 3.0 - 22/12/2025
"""

import os
import json
import re
import hashlib
import urllib.request
import urllib.parse
import smtplib
import tempfile
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.base import MIMEBase
from email import encoders

# Scheduler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

# ============================================================
# CONFIGURATION
# ============================================================

CODES_POSTAUX = ["24510", "24150", "24480", "24260", "24620", "24220", 
                 "24330", "24110", "24520", "24140", "24380", "24750"]

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "u5050786429@gmail.com"
SMTP_PASSWORD = "izemquwmmqjdasrk"
EMAIL_TO = "agence@icidordogne.fr"
EMAIL_CC = "laetony@gmail.com"

API_DPE = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe03existant/lines"

PRIX_M2 = {
    "24260": 1800, "24150": 1500, "24480": 1400, "24510": 1600,
    "24620": 1700, "24220": 1500, "24330": 1400, "24110": 1300,
    "24520": 1200, "24140": 1400, "24380": 1300, "24750": 1600,
}

COULEURS_DPE = {
    'A': '#319834', 'B': '#33a357', 'C': '#cbce00',
    'D': '#f2e600', 'E': '#ebb700', 'F': '#d66f00', 'G': '#c81e01'
}

HEADERS_WEB = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}

# Cache pour veille concurrence
CACHE_CONCURRENCE = {}


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
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Axi/3.0'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8'))
    except:
        return None

def get_nouveaux_dpe(heures=26):
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
    
    dpe_uniques = {d.get("numero_dpe"): d for d in tous_dpe if d.get("numero_dpe")}
    return list(dpe_uniques.values())


def get_mairie_info(commune, cp):
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
    dpe_list = get_nouveaux_dpe(heures=26)
    
    if not dpe_list:
        if envoyer:
            envoyer_email_vide()
        return {"status": "ok", "count": 0, "message": "Aucun DPE"}
    
    fiches_html = [generer_fiche_html(dpe) for dpe in dpe_list]
    
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
# VEILLE CONCURRENTIELLE - FONCTIONS
# ============================================================

def fetch_text(url, session=None):
    """Récupère le texte d'une page web"""
    try:
        req = urllib.request.Request(url, headers=HEADERS_WEB)
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
            html = r.read().decode('utf-8', errors='ignore')
            # Nettoyage basique HTML -> texte
            text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL|re.I)
            text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL|re.I)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text)
            return text.replace('\xa0', ' ')
    except Exception as e:
        print(f"[CONCURRENCE] Erreur fetch {url[:50]}: {e}")
        return None


def extract_prices(text):
    """Extrait les prix depuis le texte"""
    if not text:
        return []
    matches = re.findall(r'(\d{1,3}[\s\.]?\d{3})\s*[€E]', text)
    prices = []
    for m in matches:
        clean = m.replace(' ', '').replace('.', '')
        try:
            p = int(clean)
            if 30000 <= p <= 10000000:
                prices.append(p)
        except:
            pass
    return list(set(prices))


def scrape_agences():
    """Scrape toutes les agences concurrentes"""
    annonces = []
    
    agences = [
        ("HUMAN Vergt", "https://www.human-immobilier.fr/achat-immobilier-vergt", "Vergt"),
        ("HUMAN Le Bugue", "https://www.human-immobilier.fr/achat-immobilier-le-bugue", "Le Bugue"),
        ("HUMAN St-Amand", "https://www.human-immobilier.fr/achat-immobilier-saint-amand-de-vergt", "St-Amand"),
        ("Valadie", "https://valadie-immobilier.com/fr/biens/a_vendre", "Le Bugue"),
        ("Laforet", "https://www.laforet.com/agence-immobiliere/perigueux/acheter", "Périgueux"),
        ("Century 21", "https://www.century21.fr/annonces/f/achat/v-perigueux/", "Périgueux"),
        ("FD Immo", "https://www.fdimmo24.com/immobilier/catalog/?_f_i=1", "Lalinde"),
        ("Montet", "https://www.montet-immobilier.com", "Périgueux"),
        ("La Maison", "https://www.immobilierlamaison.fr/a-vendre/1", "Périgueux"),
        ("Internat Agency", "https://www.interimmoagency.com/fr/listing-vente.html", "Monpazier"),
    ]
    
    for nom, url, zone in agences:
        print(f"[CONCURRENCE] -> {nom}")
        text = fetch_text(url)
        if text:
            prices = extract_prices(text)
            for prix in prices:
                annonces.append({
                    'source': nom,
                    'prix': prix,
                    'zone': zone,
                    'url': url,
                    'date': datetime.now().isoformat()[:10]
                })
            print(f"[CONCURRENCE]    {len(prices)} annonces")
    
    # Virginie Michelin (multi-pages)
    print("[CONCURRENCE] -> Virginie Michelin")
    vm_count = 0
    for page in [1, 2, 3]:
        url = f"https://www.virginie-michelin-immobilier.fr/listeAnnonce.php?prix={page}"
        text = fetch_text(url)
        if text:
            prices = extract_prices(text)
            for prix in prices:
                annonces.append({'source': 'Virginie Michelin', 'prix': prix, 'zone': 'Villamblard', 'url': url, 'date': datetime.now().isoformat()[:10]})
            vm_count += len(prices)
    print(f"[CONCURRENCE]    {vm_count} annonces")
    
    # Bayenche (multi-pages)
    print("[CONCURRENCE] -> Bayenche")
    bay_count = 0
    for page in range(1, 6):
        url = f"https://www.bayencheimmobilier.fr/category/acheter/page/{page}" if page > 1 else "https://www.bayencheimmobilier.fr/category/acheter"
        text = fetch_text(url)
        if text:
            prices = extract_prices(text)
            for prix in prices:
                annonces.append({'source': 'Bayenche', 'prix': prix, 'zone': 'Périgueux', 'url': url, 'date': datetime.now().isoformat()[:10]})
            bay_count += len(prices)
            if len(prices) < 5:
                break
    print(f"[CONCURRENCE]    {bay_count} annonces")
    
    # Perigord Noir (multi-pages)
    print("[CONCURRENCE] -> Perigord Noir")
    pn_count = 0
    for page in range(1, 15):
        url = "https://perigordnoirimmobilier.com/nos-biens-immobiliers" if page == 1 else f"https://perigordnoirimmobilier.com/nos-biens-immobiliers/?page_number={page}"
        text = fetch_text(url)
        if text:
            prices = extract_prices(text)
            for prix in prices:
                annonces.append({'source': 'Perigord Noir', 'prix': prix, 'zone': 'Périgord Noir', 'url': url, 'date': datetime.now().isoformat()[:10]})
            pn_count += len(prices)
            if len(prices) < 5:
                break
    print(f"[CONCURRENCE]    {pn_count} annonces")
    
    return annonces


def detect_nouvelles_concurrence(annonces):
    """Détecte les nouvelles annonces vs cache"""
    global CACHE_CONCURRENCE
    nouvelles = []
    
    for a in annonces:
        aid = hashlib.md5(f"{a['source']}|{a['prix']}|{a['zone']}".encode()).hexdigest()[:12]
        if aid not in CACHE_CONCURRENCE:
            nouvelles.append(a)
            CACHE_CONCURRENCE[aid] = {'prix': a['prix'], 'date': datetime.now().isoformat()}
    
    return nouvelles


def envoyer_email_concurrence(annonces, nouvelles):
    """Envoie l'email de veille concurrentielle"""
    stats = {}
    for a in annonces:
        s = a['source']
        if s not in stats:
            stats[s] = []
        stats[s].append(a['prix'])
    
    body = f"""Bonjour,

Veille concurrentielle ICI Dordogne - {datetime.now().strftime('%d/%m/%Y %H:%M')}

📊 RÉSUMÉ
- Total annonces : {len(annonces)}
- Nouvelles aujourd'hui : {len(nouvelles)}
- Agences surveillées : {len(stats)}

📈 PAR AGENCE
"""
    
    for source, prices in sorted(stats.items(), key=lambda x: -len(x[1])):
        body += f"• {source}: {len(prices)} annonces ({min(prices):,}€ - {max(prices):,}€)\n".replace(',', ' ')
    
    if nouvelles:
        body += f"\n🆕 NOUVELLES ANNONCES ({len(nouvelles)})\n\n"
        for a in sorted(nouvelles, key=lambda x: x['prix'])[:25]:
            body += f"• {a['prix']:,}€ - {a['source']} ({a['zone']})\n".replace(',', ' ')
            body += f"  {a['url']}\n\n"
    
    body += """
--
Axi - ICI Dordogne
Je ne lâche pas."""
    
    msg = MIMEMultipart()
    msg['From'] = SMTP_USER
    msg['To'] = EMAIL_TO
    msg['Cc'] = EMAIL_CC
    msg['Subject'] = f"🏠 Veille Concurrence: {len(nouvelles)} nouvelles / {len(annonces)} total"
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASSWORD)
        s.sendmail(SMTP_USER, [EMAIL_TO, EMAIL_CC], msg.as_string())


def executer_veille_concurrence(envoyer=True):
    """Exécute la veille concurrentielle"""
    print("[CONCURRENCE] Démarrage veille concurrentielle...")
    
    annonces = scrape_agences()
    print(f"[CONCURRENCE] Total: {len(annonces)} annonces")
    
    nouvelles = detect_nouvelles_concurrence(annonces)
    print(f"[CONCURRENCE] Nouvelles: {len(nouvelles)}")
    
    if envoyer:
        envoyer_email_concurrence(annonces, nouvelles)
        print(f"[CONCURRENCE] Email envoyé à {EMAIL_TO}")
    
    return {
        "status": "ok",
        "total": len(annonces),
        "nouvelles": len(nouvelles),
        "sent_to": EMAIL_TO if envoyer else "non envoyé"
    }




# ============================================================
# INTERFACE HTML
# ============================================================

def get_index_html():
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Axi - ICI Dordogne</title>
    <style>
        body {{ font-family: Arial; padding: 40px; max-width: 800px; margin: 0 auto; background: #f5f5f5; }}
        h1 {{ color: #2E7D32; }}
        .status {{ background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .endpoint {{ background: #e8f5e9; padding: 12px; margin: 8px 0; border-radius: 6px; font-family: monospace; }}
        .endpoint a {{ color: #1B5E20; }}
        h2 {{ color: #1B5E20; margin-top: 30px; }}
        ul {{ line-height: 2; }}
    </style>
</head>
<body>
    <h1>🏠 Axi - ICI Dordogne</h1>
    
    <div class="status">
        <strong>Service:</strong> Actif<br>
        <strong>Heure:</strong> {datetime.now().strftime('%d/%m/%Y %H:%M')}<br>
        <strong>Crons:</strong> 07h00 (concurrence) + 08h00 (DPE)
    </div>
    
    <h2>Endpoints</h2>
    
    <div class="endpoint">GET <a href="/memory">/memory</a> → Consignes</div>
    <div class="endpoint">GET <a href="/briefing">/briefing</a> → Contexte Axis</div>
    <div class="endpoint">GET <a href="/status">/status</a> → Health check</div>
    
    <h2>Veille DPE</h2>
    <div class="endpoint">GET <a href="/test-veille">/test-veille</a> → Test (sans email)</div>
    <div class="endpoint">GET <a href="/run-veille">/run-veille</a> → Exécuter + email</div>
    
    <h2>Veille Concurrence</h2>
    <div class="endpoint">GET <a href="/test-veille-concurrence">/test-veille-concurrence</a> → Test (sans email)</div>
    <div class="endpoint">GET <a href="/run-veille-concurrence">/run-veille-concurrence</a> → Exécuter + email</div>
    
    <h2>Configuration</h2>
    <ul>
        <li>Email: {EMAIL_TO}</li>
        <li>Copie: {EMAIL_CC}</li>
        <li>Codes postaux DPE: {len(CODES_POSTAUX)}</li>
    </ul>
</body>
</html>"""


# ============================================================
# HANDLER HTTP
# ============================================================

class AxiHandler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        print(f"[HTTP] {args[0]}")
    
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
        
        if path == "/":
            self.send_html(get_index_html())
            return
        
        if path == "/memory":
            memory = lire_fichier("MEMORY.md") or "# MEMORY\n\nAucune consigne."
            self.send_text(memory)
            return
        
        if path == "/briefing":
            memory = lire_fichier("MEMORY.md") or "Aucune consigne."
            briefing = f"""=== BRIEFING AXI ===
Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}

=== MEMORY ===
{memory}

=== STATUS ===
- Veille DPE: 08h00
- Veille Concurrence: 07h00
- Email to: {EMAIL_TO}
"""
            self.send_text(briefing)
            return
        
        if path == "/status":
            self.send_json({
                "status": "ok",
                "time": datetime.now().isoformat(),
                "service": "Axi ICI Dordogne v3",
                "crons": ["07:00 concurrence", "08:00 DPE"],
                "email_to": EMAIL_TO,
                "codes_postaux": len(CODES_POSTAUX)
            })
            return
        
        # Veille DPE
        if path == "/test-veille":
            try:
                result = executer_veille(envoyer=False)
                self.send_json(result)
            except Exception as e:
                self.send_json({"status": "error", "message": str(e)}, 500)
            return
        
        if path == "/run-veille":
            try:
                result = executer_veille(envoyer=True)
                self.send_json(result)
            except Exception as e:
                self.send_json({"status": "error", "message": str(e)}, 500)
            return
        
        # Veille Concurrence
        if path == "/test-veille-concurrence":
            try:
                result = executer_veille_concurrence(envoyer=False)
                self.send_json(result)
            except Exception as e:
                self.send_json({"status": "error", "message": str(e)}, 500)
            return
        
        if path == "/run-veille-concurrence":
            try:
                result = executer_veille_concurrence(envoyer=True)
                self.send_json(result)
            except Exception as e:
                self.send_json({"status": "error", "message": str(e)}, 500)
            return
        
        # 404
        self.send_json({"error": "Not found"}, 404)
    
    def do_POST(self):
        path = self.path.split('?')[0]
        
        if path == "/memory":
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length).decode('utf-8')
            ecrire_fichier("MEMORY.md", body)
            self.send_json({"status": "ok", "written": len(body)})
            return
        
        self.send_json({"error": "Not found"}, 404)


# ============================================================
# FICHIERS INIT
# ============================================================

def init_files():
    if not os.path.exists("MEMORY.md"):
        ecrire_fichier("MEMORY.md", """# MEMORY - CONSIGNES POUR AXIS

*Dernière mise à jour: """ + datetime.now().strftime('%d/%m/%Y') + """*

## RÈGLES ABSOLUES

### Emails
- ❌ Jamais d'envoi sans accord explicite de Ludo
- ✅ Toujours laetony@gmail.com en copie

### Validation
- ❌ Ne RIEN lancer/exécuter/déployer sans validation Ludo

## VEILLES ACTIVES

### 1. Veille DPE ✅
- Cron: 08h00 Paris
- Endpoint: /run-veille

### 2. Veille Concurrence ✅
- Cron: 07h00 Paris
- Endpoint: /run-veille-concurrence
""")


# ============================================================
# SCHEDULER
# ============================================================

def tache_veille_dpe():
    print(f"[CRON] {datetime.now()} - Veille DPE")
    try:
        executer_veille(envoyer=True)
    except Exception as e:
        print(f"[CRON] Erreur DPE: {e}")

def tache_veille_concurrence():
    print(f"[CRON] {datetime.now()} - Veille Concurrence")
    try:
        executer_veille_concurrence(envoyer=True)
    except Exception as e:
        print(f"[CRON] Erreur Concurrence: {e}")

def demarrer_scheduler():
    scheduler = BackgroundScheduler(timezone=pytz.timezone('Europe/Paris'))
    
    # Veille Concurrence à 07h00
    scheduler.add_job(
        tache_veille_concurrence,
        CronTrigger(hour=7, minute=0, timezone=pytz.timezone('Europe/Paris')),
        id='veille_concurrence',
        name='Veille Concurrence 7h00',
        replace_existing=True
    )
    
    # Veille DPE à 08h00
    scheduler.add_job(
        tache_veille_dpe,
        CronTrigger(hour=8, minute=0, timezone=pytz.timezone('Europe/Paris')),
        id='veille_dpe',
        name='Veille DPE 8h00',
        replace_existing=True
    )
    
    scheduler.start()
    print("[SCHEDULER] Crons activés:")
    print("  - 07h00: Veille Concurrence")
    print("  - 08h00: Veille DPE")
    return scheduler


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 50)
    print("AXI - SERVICE UNIFIÉ ICI DORDOGNE v3")
    print("=" * 50)
    
    init_files()
    scheduler = demarrer_scheduler()
    
    port = int(os.environ.get("PORT", 8080))
    serveur = HTTPServer(('0.0.0.0', port), AxiHandler)
    
    print(f"Port: {port}")
    print(f"Email: {EMAIL_TO} (cc: {EMAIL_CC})")
    print("Endpoints: /run-veille, /run-veille-concurrence")
    print("En attente...")
    
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        scheduler.shutdown()
        print("Arrêt propre.")


if __name__ == "__main__":
    main()
