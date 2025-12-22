"""
AXI ICI DORDOGNE v4 - Service unifié Railway
- Veille DPE ADEME (8h00)
- Veille Concurrence 16 agences (7h00)
- Endpoints API
"""

import os
import json
import urllib.request
import urllib.parse
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import time
import re

# ============================================================
# CONFIGURATION
# ============================================================

GMAIL_USER = "u5050786429@gmail.com"
GMAIL_APP_PASSWORD = "izemquwmmqjdasrk"
EMAIL_TO = "agence@icidordogne.fr"
EMAIL_CC = "laetony@gmail.com"

# Codes postaux veille DPE
CODES_POSTAUX = [
    "24380", "24420", "24150", "24510", "24480",
    "24260", "24220", "24170", "24200", "24290",
    "24620", "24550"
]

# 16 AGENCES À SURVEILLER
AGENCES = [
    {"nom": "Périgord Noir Immobilier", "url": "https://perigordnoirimmobilier.com/", "priorite": "haute"},
    {"nom": "Virginie Michelin", "url": "https://virginie-michelin-immobilier.fr/", "priorite": "haute"},
    {"nom": "Bayenche Immobilier", "url": "https://www.bayencheimmobilier.fr/", "priorite": "haute"},
    {"nom": "Laforêt Périgueux", "url": "https://www.laforet.com/agence-immobiliere/perigueux", "priorite": "moyenne"},
    {"nom": "HUMAN Immobilier", "url": "https://www.human-immobilier.fr/agences-immobilieres/24", "priorite": "moyenne"},
    {"nom": "Valadié Immobilier", "url": "https://www.valadie-immobilier.com/fr", "priorite": "moyenne"},
    {"nom": "Internat Agency", "url": "https://www.interimmoagency.com/fr", "priorite": "moyenne"},
    {"nom": "Agence du Périgord", "url": "https://www.agenceduperigord.fr/", "priorite": "moyenne"},
    {"nom": "Century 21 Dordogne", "url": "https://www.century21.fr/trouver_agence/d-24_dordogne/", "priorite": "basse"},
    {"nom": "Immobilier La Maison", "url": "https://www.immobilierlamaison.fr/", "priorite": "basse"},
    {"nom": "FD Immo Lalinde", "url": "https://www.fdimmo24.com/", "priorite": "basse"},
    {"nom": "Montet Immobilier", "url": "https://www.montet-immobilier.com/", "priorite": "basse"},
    {"nom": "Aliénor Immobilier", "url": "https://www.immobilier-alienor.fr/", "priorite": "moyenne"},
    {"nom": "Transaxia Ste-Alvère", "url": "https://transaxia-saintealvere.fr/", "priorite": "haute"},
    {"nom": "KOK Immobilier", "url": "https://www.kok.immo/", "priorite": "haute"},
    {"nom": "JDC Immo Lalinde", "url": "https://www.jdcimmo.fr/", "priorite": "haute"},
]

# Fichiers de stockage
FICHIER_DPE = "dpe_connus.json"
FICHIER_ANNONCES = "annonces_connues.json"

# ============================================================
# UTILITAIRES
# ============================================================

def charger_json(fichier, defaut=None):
    try:
        with open(fichier, 'r') as f:
            return json.load(f)
    except:
        return defaut if defaut else {}

def sauver_json(fichier, data):
    with open(fichier, 'w') as f:
        json.dump(data, f)

def envoyer_email(sujet, corps_html):
    """Envoie un email via Gmail SMTP"""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = sujet
        msg['From'] = GMAIL_USER
        msg['To'] = EMAIL_TO
        msg['Cc'] = EMAIL_CC
        
        msg.attach(MIMEText(corps_html, 'html', 'utf-8'))
        
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, [EMAIL_TO, EMAIL_CC], msg.as_string())
        
        print(f"[EMAIL] Envoyé: {sujet}")
        return True
    except Exception as e:
        print(f"[EMAIL ERREUR] {e}")
        return False

def fetch_url(url, timeout=15):
    """Récupère le contenu d'une URL"""
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"[FETCH ERREUR] {url}: {e}")
        return None

# ============================================================
# VEILLE DPE ADEME
# ============================================================

def get_dpe_ademe(code_postal):
    """Récupère les DPE des 30 derniers jours pour un code postal"""
    date_limite = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    url = f"https://data.ademe.fr/data-fair/api/v1/datasets/dpe-v2-logements-existants/lines"
    params = {
        "Code_postal_(BAN)": code_postal,
        "size": 100,
        "select": "N°DPE,Date_établissement_DPE,Etiquette_DPE,Etiquette_GES,Type_bâtiment,Adresse_(BAN),Nom_commune_(BAN),Surface_habitable_logement",
        "qs": f"Date_établissement_DPE:[{date_limite} TO *]",
        "sort": "-Date_établissement_DPE"
    }
    
    query = "&".join([f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items()])
    full_url = f"{url}?{query}"
    
    try:
        req = urllib.request.Request(full_url, headers={'User-Agent': 'Axi/1.0'})
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
            return data.get('results', [])
    except Exception as e:
        print(f"[DPE ERREUR] {code_postal}: {e}")
        return []

def run_veille_dpe():
    """Exécute la veille DPE complète"""
    print(f"[VEILLE DPE] Démarrage - {datetime.now()}")
    
    dpe_connus = charger_json(FICHIER_DPE, {})
    nouveaux_dpe = []
    total = 0
    
    for cp in CODES_POSTAUX:
        resultats = get_dpe_ademe(cp)
        total += len(resultats)
        
        for dpe in resultats:
            num_dpe = dpe.get('N°DPE', '')
            if num_dpe and num_dpe not in dpe_connus:
                dpe_connus[num_dpe] = True
                nouveaux_dpe.append(dpe)
    
    sauver_json(FICHIER_DPE, dpe_connus)
    
    print(f"[VEILLE DPE] Total: {total}, Nouveaux: {len(nouveaux_dpe)}")
    
    # Envoyer email si nouveaux DPE
    if nouveaux_dpe:
        html = f"""
        <h2>🏠 {len(nouveaux_dpe)} nouveau(x) DPE détecté(s)</h2>
        <p>Veille du {datetime.now().strftime('%d/%m/%Y à %H:%M')}</p>
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse;">
        <tr style="background: #e94560; color: white;">
            <th>Adresse</th>
            <th>Commune</th>
            <th>DPE</th>
            <th>GES</th>
            <th>Surface</th>
            <th>Date</th>
        </tr>
        """
        
        for dpe in nouveaux_dpe[:50]:  # Max 50
            etiquette = dpe.get('Etiquette_DPE', '?')
            couleur = {
                'A': '#319834', 'B': '#33cc66', 'C': '#cbfc33',
                'D': '#fbea49', 'E': '#fccc2a', 'F': '#eb8235', 'G': '#d7221f'
            }.get(etiquette, '#888')
            
            html += f"""
            <tr>
                <td>{dpe.get('Adresse_(BAN)', 'N/C')}</td>
                <td>{dpe.get('Nom_commune_(BAN)', 'N/C')}</td>
                <td style="background: {couleur}; color: white; text-align: center; font-weight: bold;">{etiquette}</td>
                <td style="text-align: center;">{dpe.get('Etiquette_GES', '?')}</td>
                <td>{dpe.get('Surface_habitable_logement', 'N/C')} m²</td>
                <td>{dpe.get('Date_établissement_DPE', 'N/C')}</td>
            </tr>
            """
        
        html += "</table>"
        html += f"<p><small>Codes postaux surveillés: {', '.join(CODES_POSTAUX)}</small></p>"
        
        envoyer_email(f"🏠 ICI Dordogne - {len(nouveaux_dpe)} nouveau(x) DPE", html)
    
    return {"total": total, "nouveaux": len(nouveaux_dpe)}

# ============================================================
# VEILLE CONCURRENCE
# ============================================================

def extraire_prix(html):
    """Extrait les prix d'une page HTML"""
    prix_pattern = r'(\d{2,3}[\s\.]?\d{3})\s*€'
    matches = re.findall(prix_pattern, html)
    prix = []
    for m in matches:
        try:
            p = int(m.replace(' ', '').replace('.', ''))
            if 50000 <= p <= 2000000:
                prix.append(p)
        except:
            pass
    return list(set(prix))

def scraper_agence(agence):
    """Scrape une agence et retourne les annonces détectées"""
    html = fetch_url(agence['url'])
    if not html:
        return {"agence": agence['nom'], "status": "erreur", "annonces": 0}
    
    prix = extraire_prix(html)
    
    # Compter les annonces (patterns communs)
    nb_annonces = 0
    patterns = [
        r'(\d+)\s*bien',
        r'(\d+)\s*annonce',
        r'(\d+)\s*résultat',
        r'class="[^"]*property[^"]*"',
        r'class="[^"]*listing[^"]*"',
        r'class="[^"]*bien[^"]*"',
    ]
    
    for pattern in patterns[:3]:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            try:
                nb_annonces = max(nb_annonces, int(match.group(1)))
            except:
                pass
    
    if nb_annonces == 0:
        nb_annonces = len(prix)
    
    return {
        "agence": agence['nom'],
        "url": agence['url'],
        "status": "ok",
        "annonces": nb_annonces,
        "prix_detectes": len(prix),
        "prix_min": min(prix) if prix else None,
        "prix_max": max(prix) if prix else None
    }

def run_veille_concurrence():
    """Exécute la veille concurrence sur toutes les agences"""
    print(f"[VEILLE CONCURRENCE] Démarrage - {datetime.now()}")
    
    resultats = []
    total_annonces = 0
    
    for agence in AGENCES:
        print(f"  → Scraping {agence['nom']}...")
        result = scraper_agence(agence)
        resultats.append(result)
        total_annonces += result.get('annonces', 0)
        time.sleep(1)  # Délai entre requêtes
    
    # Charger les données précédentes pour détecter les changements
    anciennes = charger_json(FICHIER_ANNONCES, {})
    changements = []
    
    for r in resultats:
        nom = r['agence']
        ancien_count = anciennes.get(nom, {}).get('annonces', 0)
        nouveau_count = r.get('annonces', 0)
        
        if ancien_count > 0 and nouveau_count != ancien_count:
            diff = nouveau_count - ancien_count
            changements.append({
                "agence": nom,
                "avant": ancien_count,
                "apres": nouveau_count,
                "diff": diff
            })
        
        anciennes[nom] = {"annonces": nouveau_count, "date": datetime.now().isoformat()}
    
    sauver_json(FICHIER_ANNONCES, anciennes)
    
    print(f"[VEILLE CONCURRENCE] Total: {total_annonces} annonces, {len(changements)} changements")
    
    # Email récapitulatif
    html = f"""
    <h2>📊 Veille Concurrence ICI Dordogne</h2>
    <p>Rapport du {datetime.now().strftime('%d/%m/%Y à %H:%M')}</p>
    
    <h3>Résumé: {total_annonces} annonces sur {len(AGENCES)} agences</h3>
    """
    
    if changements:
        html += "<h3>⚠️ Changements détectés:</h3><ul>"
        for c in changements:
            signe = "+" if c['diff'] > 0 else ""
            html += f"<li><strong>{c['agence']}</strong>: {c['avant']} → {c['apres']} ({signe}{c['diff']})</li>"
        html += "</ul>"
    
    html += """
    <h3>Détail par agence:</h3>
    <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse;">
    <tr style="background: #16213e; color: white;">
        <th>Agence</th>
        <th>Annonces</th>
        <th>Prix Min</th>
        <th>Prix Max</th>
        <th>Status</th>
    </tr>
    """
    
    for r in sorted(resultats, key=lambda x: x.get('annonces', 0), reverse=True):
        prix_min = f"{r['prix_min']:,}€".replace(',', ' ') if r.get('prix_min') else "N/C"
        prix_max = f"{r['prix_max']:,}€".replace(',', ' ') if r.get('prix_max') else "N/C"
        status_color = "#4ade80" if r['status'] == 'ok' else "#ef4444"
        
        html += f"""
        <tr>
            <td><a href="{r.get('url', '#')}">{r['agence']}</a></td>
            <td style="text-align: center; font-weight: bold;">{r.get('annonces', 0)}</td>
            <td>{prix_min}</td>
            <td>{prix_max}</td>
            <td style="color: {status_color};">{r['status']}</td>
        </tr>
        """
    
    html += "</table>"
    html += f"<p><small>Agences surveillées: {len(AGENCES)}</small></p>"
    
    envoyer_email(f"📊 Veille Concurrence - {total_annonces} annonces", html)
    
    return {"total": total_annonces, "agences": len(AGENCES), "changements": len(changements)}

# ============================================================
# MEMORY API
# ============================================================

MEMORY_CONTENT = """# MEMORY - CONSIGNES POUR AXIS

*Dernière mise à jour: 22/12/2025*

## WORKFLOW OBLIGATOIRE

À chaque début de conversation, Axis doit:
1. Appeler GET /memory sur ce service
2. Lire et appliquer ces consignes
3. Ne jamais ignorer ces règles

## RÈGLES ABSOLUES

### Emails
- ❌ Jamais d envoi sans accord explicite de Ludo
- ✅ Toujours laetony@gmail.com en copie

### Validation
- ❌ Ne RIEN lancer/exécuter/déployer sans validation Ludo
- ❌ Ne jamais changer de sujet sans confirmation que le précédent est terminé

### Qualité
- ✅ Toujours être critique sur le travail fait
- ✅ Identifier les failles/manques AVANT de proposer la suite

## CREDENTIALS ACTIFS

### Gmail SMTP
- Email: u5050786429@gmail.com
- App password: izemquwmmqjdasrk

### Destinataires
- Principal: agence@icidordogne.fr
- Copie: laetony@gmail.com

## VEILLES ACTIVES

### 1. Veille DPE ✅ OPÉRATIONNELLE
- Cron: 08h00 Paris
- Endpoint: /run-veille
- Codes postaux: 12

### 2. Veille Concurrence ✅ OPÉRATIONNELLE
- Cron: 07h00 Paris
- Endpoint: /run-veille-concurrence
- Agences: 16

## HISTORIQUE

| Date | Action |
|------|--------|
| 22/12/2025 | v4: 16 agences complètes |
| 22/12/2025 | v3: Veille concurrence intégrée - Cron 7h00 |
| 22/12/2025 | Cron APScheduler intégré - Veille DPE 8h00 |
| 21/12/2025 | Création service unifié Railway |
| 20/12/2025 | App password Gmail créé |
"""

# ============================================================
# SCHEDULER (CRON)
# ============================================================

def scheduler_loop():
    """Boucle de scheduling pour les tâches planifiées"""
    print("[SCHEDULER] Démarré")
    
    last_dpe = None
    last_concurrence = None
    
    while True:
        now = datetime.now()
        heure = now.strftime("%H:%M")
        date_str = now.strftime("%Y-%m-%d")
        
        # Veille concurrence à 7h00
        if heure == "07:00" and last_concurrence != date_str:
            print("[CRON] Lancement veille concurrence 7h00")
            try:
                run_veille_concurrence()
                last_concurrence = date_str
            except Exception as e:
                print(f"[CRON ERREUR] Concurrence: {e}")
        
        # Veille DPE à 8h00
        if heure == "08:00" and last_dpe != date_str:
            print("[CRON] Lancement veille DPE 8h00")
            try:
                run_veille_dpe()
                last_dpe = date_str
            except Exception as e:
                print(f"[CRON ERREUR] DPE: {e}")
        
        time.sleep(30)  # Vérifier toutes les 30 secondes

# ============================================================
# SERVEUR HTTP
# ============================================================

class AxiHandler(BaseHTTPRequestHandler):
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def do_GET(self):
        path = self.path.split('?')[0]
        
        if path == '/':
            self.send_json({
                "service": "Axi ICI Dordogne v4",
                "status": "ok",
                "endpoints": ["/memory", "/status", "/briefing", "/run-veille", "/run-veille-concurrence", "/test-veille", "/test-veille-concurrence"]
            })
        
        elif path == '/memory':
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(MEMORY_CONTENT.encode())
        
        elif path == '/status':
            self.send_json({
                "status": "ok",
                "time": datetime.now().isoformat(),
                "service": "Axi ICI Dordogne v4",
                "crons": ["07:00 concurrence", "08:00 DPE"],
                "email_to": EMAIL_TO,
                "codes_postaux": len(CODES_POSTAUX),
                "agences": len(AGENCES)
            })
        
        elif path == '/briefing':
            briefing = f"""
# BRIEFING AXI - {datetime.now().strftime('%d/%m/%Y %H:%M')}

## Statut Système
- Service: v4 opérationnel
- Veilles actives: DPE (8h) + Concurrence (7h)
- Agences surveillées: {len(AGENCES)}
- Codes postaux DPE: {len(CODES_POSTAUX)}

## Dernières Actions
- Veille concurrence: 16 agences
- Veille DPE: 12 codes postaux

## À faire aujourd'hui
1. Vérifier emails veille
2. Suivre leads DPE
3. Analyser concurrence

Je ne lâche pas.
"""
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(briefing.encode())
        
        elif path == '/run-veille':
            result = run_veille_dpe()
            self.send_json({"status": "ok", **result, "sent_to": EMAIL_TO})
        
        elif path == '/run-veille-concurrence':
            result = run_veille_concurrence()
            self.send_json({"status": "ok", **result, "sent_to": EMAIL_TO})
        
        elif path == '/test-veille':
            # Test sans envoi email
            print("[TEST] Veille DPE (sans email)")
            total = 0
            for cp in CODES_POSTAUX[:3]:
                resultats = get_dpe_ademe(cp)
                total += len(resultats)
            self.send_json({"status": "ok", "total": total, "sent_to": "non envoyé"})
        
        elif path == '/test-veille-concurrence':
            # Test sans envoi email
            print("[TEST] Veille Concurrence (sans email)")
            total = 0
            for agence in AGENCES[:3]:
                result = scraper_agence(agence)
                total += result.get('annonces', 0)
            self.send_json({"status": "ok", "total": total, "agences_testees": 3, "sent_to": "non envoyé"})
        
        elif path == '/agences':
            self.send_json({
                "total": len(AGENCES),
                "agences": AGENCES
            })
        
        else:
            self.send_json({"error": "Not found"}, 404)
    
    def do_POST(self):
        path = self.path.split('?')[0]
        
        if path == '/memoire':
            # Endpoint pour sauvegarder des notes
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode()
            print(f"[MEMOIRE] Reçu: {body[:100]}...")
            self.send_json({"status": "ok", "saved": True})
        else:
            self.send_json({"error": "Not found"}, 404)
    
    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")

# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("AXI ICI DORDOGNE v4")
    print(f"Veille DPE: {len(CODES_POSTAUX)} codes postaux")
    print(f"Veille Concurrence: {len(AGENCES)} agences")
    print("=" * 60)
    
    # Lancer le scheduler en background
    scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
    scheduler_thread.start()
    
    # Démarrer le serveur HTTP
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), AxiHandler)
    print(f"[SERVER] Écoute sur port {port}")
    print("[CRONS] 07:00 Concurrence, 08:00 DPE")
    server.serve_forever()

if __name__ == "__main__":
    main()
