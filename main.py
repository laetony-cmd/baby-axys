"""
AXI ICI DORDOGNE v10 UNIFIÉ - Service complet Railway
======================================================
- Chat Axi avec Claude API + recherche web
- Interface web conversation (/, /trio)
- Veille DPE ADEME (8h00 Paris)
- Veille Concurrence 16 agences (7h00 Paris)
- Enrichissement DVF (historique ventes)
- Tous les endpoints API

Fusion du code chat (23/12) et code veilles v7 (22/12)
"""

import os
import json
import urllib.request
import urllib.parse
import smtplib
import ssl
import gzip
import csv
import io
import re
import threading
import time
import anthropic
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from math import radians, cos, sin, asin, sqrt

# Import conditionnel openpyxl
try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    OPENPYXL_OK = True
except:
    OPENPYXL_OK = False
    print("[WARNING] openpyxl non installé - Excel désactivé")

# Import conditionnel APScheduler
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    import pytz
    SCHEDULER_OK = True
except:
    SCHEDULER_OK = False
    print("[WARNING] APScheduler non installé - cron désactivé")

# ============================================================
# CONFIGURATION
# ============================================================

# Gmail SMTP
GMAIL_USER = "u5050786429@gmail.com"
GMAIL_APP_PASSWORD = "izemquwmmqjdasrk"
EMAIL_TO = "agence@icidordogne.fr"
EMAIL_CC = "laetony@gmail.com"

# Codes postaux veille DPE + DVF
CODES_POSTAUX = [
    "24260", "24480", "24150", "24510", "24220", "24620",  # Zone Le Bugue
    "24380", "24110", "24140", "24520", "24330", "24750"   # Zone Vergt
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
FICHIER_URLS = "urls_annonces.json"
DVF_CACHE_DIR = "/tmp/dvf_cache"
CONVERSATIONS_FILE = "conversations.txt"
JOURNAL_FILE = "journal.txt"

# Identité chat Axi
IDENTITE = """Tu es Axi, l'assistant IA d'ICI Dordogne, agence immobilière en Dordogne.
Tu travailles avec Ludo (stratégie) et Anthony (opérationnel).
Tu es direct, efficace, et tu proposes des solutions concrètes.
Tu as accès à la recherche web et tu peux créer des documents.
Devise: "Je ne lâche pas."
"""

# Variables globales
CHAT_ADMIN_INFOS = {}
_enrichisseur_dvf = None

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

def charger_json(fichier, defaut=None):
    try:
        with open(fichier, 'r') as f:
            return json.load(f)
    except:
        return defaut if defaut else {}

def sauver_json(fichier, data):
    with open(fichier, 'w') as f:
        json.dump(data, f)

# ============================================================
# EMAIL
# ============================================================

def envoyer_email(sujet, corps_html, piece_jointe=None, nom_fichier=None, destinataire=None):
    """Envoie un email via Gmail SMTP avec pièce jointe optionnelle"""
    try:
        msg = MIMEMultipart('mixed')
        msg['Subject'] = sujet
        msg['From'] = GMAIL_USER
        msg['To'] = destinataire or EMAIL_TO
        msg['Cc'] = EMAIL_CC
        
        # Corps HTML
        msg.attach(MIMEText(corps_html, 'html', 'utf-8'))
        
        # Pièce jointe si fournie
        if piece_jointe and nom_fichier:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(piece_jointe)
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename="{nom_fichier}"')
            msg.attach(part)
            print(f"[EMAIL] Pièce jointe: {nom_fichier}")
        
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            recipients = [destinataire or EMAIL_TO, EMAIL_CC]
            server.sendmail(GMAIL_USER, recipients, msg.as_string())
        
        print(f"[EMAIL] Envoyé: {sujet}")
        return True
    except Exception as e:
        print(f"[EMAIL ERREUR] {e}")
        return False

# ============================================================
# FETCH URL
# ============================================================

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
# RECHERCHE WEB (DuckDuckGo)
# ============================================================

def recherche_web(requete):
    """Recherche web via DuckDuckGo HTML"""
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(requete)}"
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8')
        
        resultats = []
        import re
        pattern = r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>([^<]+)</a>'
        matches = re.findall(pattern, html)
        
        for url, titre in matches[:5]:
            if url.startswith('//duckduckgo.com/l/?uddg='):
                url = urllib.parse.unquote(url.split('uddg=')[1].split('&')[0])
            resultats.append({"titre": titre.strip(), "url": url})
        
        return resultats
    except Exception as e:
        print(f"[RECHERCHE ERREUR] {e}")
        return []

def faire_recherche(requete):
    """Effectue une recherche et retourne un texte formaté"""
    resultats = recherche_web(requete)
    if not resultats:
        return f"Aucun résultat trouvé pour: {requete}"
    
    texte = f"Résultats pour '{requete}':\n"
    for i, r in enumerate(resultats, 1):
        texte += f"{i}. {r['titre']}\n   {r['url']}\n"
    return texte

# ============================================================
# GÉNÉRATION RÉPONSE CLAUDE
# ============================================================

def generer_reponse(client, message_utilisateur, identite, histoire, conversations, est_axis=False):
    """Génère une réponse via Claude API"""
    
    # Construire le contexte
    contexte = identite + "\n\n"
    if histoire:
        contexte += f"Historique récent:\n{histoire[-2000:]}\n\n"
    
    # Ajouter les infos admin si disponibles
    if CHAT_ADMIN_INFOS:
        contexte += f"Infos admin: {json.dumps(CHAT_ADMIN_INFOS)}\n\n"
    
    messages = [{"role": "user", "content": message_utilisateur}]
    
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=contexte,
            messages=messages
        )
        
        reponse_texte = response.content[0].text
        
        # Détecter les demandes de recherche
        if "[RECHERCHE:" in reponse_texte:
            match = re.search(r'\[RECHERCHE:\s*([^\]]+)\]', reponse_texte)
            if match:
                requete = match.group(1)
                resultats = faire_recherche(requete)
                reponse_texte = reponse_texte.replace(match.group(0), f"\n{resultats}\n")
        
        return reponse_texte
        
    except Exception as e:
        return f"Erreur API Claude: {e}"

# ============================================================
# MODULE DVF - ENRICHISSEMENT HISTORIQUE VENTES
# ============================================================

class EnrichisseurDVF:
    """Enrichissement des annonces avec données DVF (historique ventes)"""
    
    def __init__(self):
        self.index_dvf = None
        self.derniere_maj = None
    
    def telecharger_dvf(self, departement="24", annee="2023"):
        """Télécharge le fichier DVF pour un département"""
        os.makedirs(DVF_CACHE_DIR, exist_ok=True)
        
        cache_file = f"{DVF_CACHE_DIR}/dvf_{departement}_{annee}.csv"
        cache_meta = f"{DVF_CACHE_DIR}/dvf_{departement}_{annee}.meta"
        
        # Vérifier cache (7 jours)
        if os.path.exists(cache_file) and os.path.exists(cache_meta):
            with open(cache_meta, 'r') as f:
                meta = json.load(f)
            cache_date = datetime.fromisoformat(meta.get('date', '2000-01-01'))
            if datetime.now() - cache_date < timedelta(days=7):
                print(f"[DVF] Cache valide: {cache_file}")
                return cache_file
        
        url = f"https://files.data.gouv.fr/geo-dvf/latest/csv/{annee}/departements/{departement}.csv.gz"
        print(f"[DVF] Téléchargement: {url}")
        
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'ICI-Dordogne/1.0'})
            with urllib.request.urlopen(req, timeout=60) as response:
                compressed = response.read()
            
            decompressed = gzip.decompress(compressed)
            content = decompressed.decode('utf-8')
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            with open(cache_meta, 'w') as f:
                json.dump({'date': datetime.now().isoformat(), 'url': url}, f)
            
            print(f"[DVF] Sauvegardé: {cache_file}")
            return cache_file
        except Exception as e:
            print(f"[DVF] Erreur téléchargement: {e}")
            if os.path.exists(cache_file):
                return cache_file
            return None
    
    def charger_index(self, fichier_csv):
        """Charge le fichier DVF en index mémoire"""
        if not fichier_csv or not os.path.exists(fichier_csv):
            return {}
        
        print(f"[DVF] Chargement: {fichier_csv}")
        index_parcelle = {}
        index_cp = {}
        
        with open(fichier_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                code_postal = row.get('code_postal', '')
                
                # Filtrer par codes postaux surveillés
                if code_postal not in CODES_POSTAUX:
                    continue
                
                id_parcelle = row.get('id_parcelle', '')
                
                mutation = {
                    'date_mutation': row.get('date_mutation', ''),
                    'valeur_fonciere': float(row.get('valeur_fonciere', 0) or 0),
                    'adresse_numero': row.get('adresse_numero', ''),
                    'adresse_nom_voie': row.get('adresse_nom_voie', ''),
                    'code_postal': code_postal,
                    'nom_commune': row.get('nom_commune', ''),
                    'type_local': row.get('type_local', ''),
                    'surface_reelle_bati': float(row.get('surface_reelle_bati', 0) or 0),
                    'surface_terrain': float(row.get('surface_terrain', 0) or 0),
                    'longitude': float(row.get('longitude', 0) or 0),
                    'latitude': float(row.get('latitude', 0) or 0),
                    'id_parcelle': id_parcelle
                }
                
                if id_parcelle:
                    if id_parcelle not in index_parcelle:
                        index_parcelle[id_parcelle] = []
                    index_parcelle[id_parcelle].append(mutation)
                
                if code_postal:
                    if code_postal not in index_cp:
                        index_cp[code_postal] = []
                    index_cp[code_postal].append(mutation)
        
        print(f"[DVF] {len(index_parcelle)} parcelles chargées")
        return {'par_parcelle': index_parcelle, 'par_code_postal': index_cp}
    
    def initialiser(self):
        """Télécharge et indexe les données DVF (2022-2024)"""
        print("[DVF] Initialisation...")
        
        for annee in ["2024", "2023", "2022"]:
            fichier = self.telecharger_dvf("24", annee)
            if fichier:
                index = self.charger_index(fichier)
                if self.index_dvf is None:
                    self.index_dvf = index
                else:
                    # Fusionner
                    for parcelle, mutations in index.get('par_parcelle', {}).items():
                        if parcelle not in self.index_dvf['par_parcelle']:
                            self.index_dvf['par_parcelle'][parcelle] = []
                        self.index_dvf['par_parcelle'][parcelle].extend(mutations)
        
        self.derniere_maj = datetime.now()
        
        if self.index_dvf:
            nb = len(self.index_dvf.get('par_parcelle', {}))
            print(f"[DVF] Index prêt: {nb} parcelles")
            return True
        return False
    
    def geocoder(self, adresse, code_postal=None):
        """Géocode une adresse via API BAN"""
        query = adresse
        if code_postal:
            query += f" {code_postal}"
        
        url = f"https://api-adresse.data.gouv.fr/search/?q={urllib.parse.quote(query)}&limit=1"
        
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'ICI-Dordogne/1.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
            
            if data.get('features'):
                feature = data['features'][0]
                coords = feature.get('geometry', {}).get('coordinates', [0, 0])
                props = feature.get('properties', {})
                return {
                    'latitude': coords[1],
                    'longitude': coords[0],
                    'code_insee': props.get('citycode', ''),
                    'score': props.get('score', 0)
                }
        except Exception as e:
            print(f"[GEOCODE] Erreur: {e}")
        return None
    
    def haversine(self, lon1, lat1, lon2, lat2):
        """Calcule la distance en km entre deux points GPS"""
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        return 6371 * c
    
    def enrichir_adresse(self, adresse, code_postal=None, rayon_km=0.5):
        """Enrichit une adresse avec l'historique DVF"""
        if not self.index_dvf:
            self.initialiser()
        
        if not self.index_dvf:
            return {"erreur": "Index DVF non disponible"}
        
        # Géocoder l'adresse
        geo = self.geocoder(adresse, code_postal)
        if not geo:
            return {"erreur": "Adresse non trouvée"}
        
        lat, lon = geo['latitude'], geo['longitude']
        
        # Chercher les ventes proches
        ventes_proches = []
        
        for cp in CODES_POSTAUX:
            for mutation in self.index_dvf.get('par_code_postal', {}).get(cp, []):
                m_lat = mutation.get('latitude', 0)
                m_lon = mutation.get('longitude', 0)
                if m_lat and m_lon:
                    distance = self.haversine(lon, lat, m_lon, m_lat)
                    if distance <= rayon_km:
                        mutation['distance_km'] = round(distance, 2)
                        ventes_proches.append(mutation)
        
        # Trier par date
        ventes_proches.sort(key=lambda x: x.get('date_mutation', ''), reverse=True)
        
        return {
            "adresse": adresse,
            "code_postal": code_postal,
            "coordonnees": geo,
            "ventes_proches": ventes_proches[:20],
            "nb_ventes": len(ventes_proches)
        }
    
    def stats_zone(self, code_postal):
        """Statistiques DVF pour un code postal"""
        if not self.index_dvf:
            self.initialiser()
        
        mutations = self.index_dvf.get('par_code_postal', {}).get(code_postal, [])
        
        if not mutations:
            return {"code_postal": code_postal, "nb_ventes": 0}
        
        # Calculs
        prix = [m['valeur_fonciere'] for m in mutations if m['valeur_fonciere'] > 0]
        surfaces = [m['surface_reelle_bati'] for m in mutations if m['surface_reelle_bati'] > 0]
        
        prix_m2 = []
        for m in mutations:
            if m['valeur_fonciere'] > 0 and m['surface_reelle_bati'] > 0:
                prix_m2.append(m['valeur_fonciere'] / m['surface_reelle_bati'])
        
        return {
            "code_postal": code_postal,
            "nb_ventes": len(mutations),
            "prix_moyen": round(sum(prix) / len(prix), 0) if prix else 0,
            "prix_median": round(sorted(prix)[len(prix)//2], 0) if prix else 0,
            "prix_m2_moyen": round(sum(prix_m2) / len(prix_m2), 0) if prix_m2 else 0,
            "surface_moyenne": round(sum(surfaces) / len(surfaces), 0) if surfaces else 0
        }


def get_enrichisseur():
    """Singleton pour EnrichisseurDVF"""
    global _enrichisseur_dvf
    if _enrichisseur_dvf is None:
        _enrichisseur_dvf = EnrichisseurDVF()
    return _enrichisseur_dvf

# ============================================================
# VEILLE DPE ADEME
# ============================================================

def get_dpe_ademe(code_postal):
    """Récupère les DPE récents depuis l'API ADEME"""
    url = f"https://data.ademe.fr/data-fair/api/v1/datasets/dpe-v2-logements-existants/lines?size=100&select=N%C2%B0DPE%2CDate_r%C3%A9ception_DPE%2CEtiquette_DPE%2CAdresse_brute%2CCode_postal_%28BAN%29%2CNom_commune_%28BAN%29%2CType_b%C3%A2timent%2CSurface_habitable_logement&q_fields=Code_postal_%28BAN%29&q={code_postal}&sort=Date_r%C3%A9ception_DPE%3A-1"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'ICI-Dordogne/1.0'})
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
        return data.get('results', [])
    except Exception as e:
        print(f"[DPE] Erreur {code_postal}: {e}")
        return []


def run_veille_dpe():
    """Exécute la veille DPE quotidienne"""
    print(f"\n[VEILLE DPE] Démarrage - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    # Charger les DPE déjà connus
    dpe_connus = charger_json(FICHIER_DPE, {})
    nouveaux_dpe = []
    
    # Récupérer l'enrichisseur DVF
    enrichisseur = get_enrichisseur()
    
    for cp in CODES_POSTAUX:
        print(f"[DPE] Scan {cp}...")
        resultats = get_dpe_ademe(cp)
        
        for dpe in resultats:
            numero = dpe.get('N°DPE', '')
            if numero and numero not in dpe_connus:
                # Nouveau DPE trouvé
                dpe_connus[numero] = {
                    'date_detection': datetime.now().isoformat(),
                    'data': dpe
                }
                
                # Enrichir avec DVF si possible
                adresse = dpe.get('Adresse_brute', '')
                if adresse and enrichisseur.index_dvf:
                    try:
                        enrichissement = enrichisseur.enrichir_adresse(adresse, cp, rayon_km=0.3)
                        if enrichissement.get('ventes_proches'):
                            dpe['historique_dvf'] = enrichissement['ventes_proches'][:5]
                    except:
                        pass
                
                nouveaux_dpe.append(dpe)
        
        time.sleep(0.5)  # Pause entre requêtes
    
    # Sauvegarder
    sauver_json(FICHIER_DPE, dpe_connus)
    
    print(f"[DPE] Terminé: {len(nouveaux_dpe)} nouveaux DPE")
    
    # Envoyer email si nouveaux DPE
    if nouveaux_dpe:
        corps = f"""
        <h2>🏠 Veille DPE - {len(nouveaux_dpe)} nouveaux diagnostics</h2>
        <p>Date: {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
        <table border="1" cellpadding="5" style="border-collapse: collapse;">
            <tr style="background-color: #f0f0f0;">
                <th>Adresse</th>
                <th>CP</th>
                <th>Commune</th>
                <th>Type</th>
                <th>Surface</th>
                <th>DPE</th>
                <th>Historique DVF</th>
            </tr>
        """
        
        for dpe in nouveaux_dpe:
            dvf_info = ""
            if dpe.get('historique_dvf'):
                derniere_vente = dpe['historique_dvf'][0]
                dvf_info = f"{derniere_vente.get('date_mutation', '')} - {derniere_vente.get('valeur_fonciere', 0):,.0f}€"
            
            corps += f"""
            <tr>
                <td>{dpe.get('Adresse_brute', 'N/A')}</td>
                <td>{dpe.get('Code_postal_(BAN)', '')}</td>
                <td>{dpe.get('Nom_commune_(BAN)', '')}</td>
                <td>{dpe.get('Type_bâtiment', '')}</td>
                <td>{dpe.get('Surface_habitable_logement', '')} m²</td>
                <td><strong>{dpe.get('Etiquette_DPE', '')}</strong></td>
                <td>{dvf_info}</td>
            </tr>
            """
        
        corps += "</table><p>🤖 Généré automatiquement par Axi</p>"
        
        envoyer_email(
            f"🏠 Veille DPE - {len(nouveaux_dpe)} nouveaux ({datetime.now().strftime('%d/%m')})",
            corps
        )
    
    return {"nouveaux": len(nouveaux_dpe), "total_connus": len(dpe_connus)}

# ============================================================
# VEILLE CONCURRENCE
# ============================================================

def extraire_urls_annonces(html, base_url):
    """Extrait les URLs d'annonces depuis le HTML d'une agence"""
    urls = set()
    
    # Patterns courants pour les liens d'annonces
    patterns = [
        r'href="(/annonce[s]?/[^"]+)"',
        r'href="(/bien[s]?/[^"]+)"',
        r'href="(/vente[s]?/[^"]+)"',
        r'href="(/immobilier/[^"]+)"',
        r'href="(/property/[^"]+)"',
        r'href="(/achat/[^"]+)"',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for match in matches:
            if not any(x in match.lower() for x in ['javascript', 'mailto', '#', 'login', 'contact']):
                full_url = urllib.parse.urljoin(base_url, match)
                urls.add(full_url)
    
    return list(urls)


def extraire_prix_page(html):
    """Extrait le prix d'une page d'annonce"""
    patterns = [
        r'(\d{2,3}[\s\xa0]?\d{3})[\s\xa0]?€',
        r'(\d{2,3}[\s\xa0]?\d{3})[\s\xa0]?euros',
        r'prix["\s:]+(\d+[\s\xa0]?\d*)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            prix_str = match.group(1).replace(' ', '').replace('\xa0', '')
            try:
                return int(prix_str)
            except:
                pass
    return None


def extraire_cp_page_detail(html):
    """Extrait le code postal d'une page d'annonce"""
    match = re.search(r'\b(24\d{3})\b', html)
    return match.group(1) if match else None


def scraper_agence_urls(agence):
    """Scrape les URLs d'annonces d'une agence"""
    try:
        html = fetch_url(agence['url'], timeout=20)
        if html:
            urls = extraire_urls_annonces(html, agence['url'])
            return urls[:50]  # Limiter à 50 URLs par agence
    except Exception as e:
        print(f"[CONCURRENCE] Erreur {agence['nom']}: {e}")
    return []


def creer_excel_veille(annonces_enrichies, dans_zone, toutes_urls):
    """Crée un fichier Excel avec les résultats de la veille"""
    if not OPENPYXL_OK:
        return None
    
    wb = Workbook()
    
    # === FEUILLE 1: Dans votre zone ===
    ws1 = wb.active
    ws1.title = "Dans votre zone"
    
    headers = ["Agence", "URL", "Prix", "Code Postal"]
    for col, header in enumerate(headers, 1):
        cell = ws1.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        cell.font = Font(bold=True, color="FFFFFF")
    
    for row, annonce in enumerate(dans_zone, 2):
        ws1.cell(row=row, column=1, value=annonce.get('agence', ''))
        ws1.cell(row=row, column=2, value=annonce.get('url', ''))
        ws1.cell(row=row, column=3, value=annonce.get('prix', ''))
        ws1.cell(row=row, column=4, value=annonce.get('code_postal', ''))
    
    # Ajuster largeurs
    ws1.column_dimensions['A'].width = 25
    ws1.column_dimensions['B'].width = 60
    ws1.column_dimensions['C'].width = 12
    ws1.column_dimensions['D'].width = 12
    
    # === FEUILLE 2: Toutes les annonces ===
    ws2 = wb.create_sheet("Toutes les annonces")
    
    for col, header in enumerate(["Agence", "Priorité", "Nb URLs"], 1):
        cell = ws2.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="70AD47", end_color="70AD47", fill_type="solid")
        cell.font = Font(bold=True, color="FFFFFF")
    
    for row, (agence, urls) in enumerate(toutes_urls.items(), 2):
        priorite = next((a['priorite'] for a in AGENCES if a['nom'] == agence), 'N/A')
        ws2.cell(row=row, column=1, value=agence)
        ws2.cell(row=row, column=2, value=priorite)
        ws2.cell(row=row, column=3, value=len(urls))
    
    # Sauvegarder en mémoire
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def run_veille_concurrence():
    """Exécute la veille concurrence quotidienne"""
    print(f"\n[CONCURRENCE] Démarrage - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    # Charger les URLs déjà connues
    urls_connues = charger_json(FICHIER_URLS, {})
    nouvelles_annonces = []
    toutes_urls = {}
    dans_zone = []
    
    for agence in AGENCES:
        print(f"[CONCURRENCE] Scan {agence['nom']}...")
        urls = scraper_agence_urls(agence)
        toutes_urls[agence['nom']] = urls
        
        # Identifier les nouvelles URLs
        agence_id = agence['nom']
        if agence_id not in urls_connues:
            urls_connues[agence_id] = []
        
        for url in urls:
            if url not in urls_connues[agence_id]:
                urls_connues[agence_id].append(url)
                
                # Enrichir avec prix et CP
                try:
                    html_detail = fetch_url(url, timeout=10)
                    if html_detail:
                        prix = extraire_prix_page(html_detail)
                        cp = extraire_cp_page_detail(html_detail)
                        
                        annonce = {
                            'agence': agence['nom'],
                            'url': url,
                            'prix': prix,
                            'code_postal': cp,
                            'date_detection': datetime.now().isoformat()
                        }
                        nouvelles_annonces.append(annonce)
                        
                        # Vérifier si dans notre zone
                        if cp and cp in CODES_POSTAUX:
                            dans_zone.append(annonce)
                except:
                    pass
        
        time.sleep(1)  # Pause entre agences
    
    # Sauvegarder
    sauver_json(FICHIER_URLS, urls_connues)
    
    print(f"[CONCURRENCE] Terminé: {len(nouvelles_annonces)} nouvelles, {len(dans_zone)} dans zone")
    
    # Créer Excel si disponible
    excel_data = None
    if OPENPYXL_OK and (dans_zone or nouvelles_annonces):
        excel_data = creer_excel_veille(nouvelles_annonces, dans_zone, toutes_urls)
    
    # Envoyer email
    if nouvelles_annonces or dans_zone:
        corps = f"""
        <h2>🔍 Veille Concurrence - {len(nouvelles_annonces)} nouvelles annonces</h2>
        <p>Date: {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
        <p><strong>🎯 Dans votre zone ({len(dans_zone)}):</strong></p>
        """
        
        if dans_zone:
            corps += "<ul>"
            for a in dans_zone[:10]:
                corps += f"<li>{a['agence']} - {a.get('code_postal', '?')} - {a.get('prix', '?')}€ - <a href='{a['url']}'>Voir</a></li>"
            corps += "</ul>"
        else:
            corps += "<p><em>Aucune nouvelle annonce dans vos codes postaux</em></p>"
        
        corps += f"""
        <p><strong>📊 Résumé par agence:</strong></p>
        <table border="1" cellpadding="5" style="border-collapse: collapse;">
            <tr style="background-color: #f0f0f0;">
                <th>Agence</th>
                <th>Priorité</th>
                <th>URLs trouvées</th>
            </tr>
        """
        
        for agence in AGENCES:
            nb = len(toutes_urls.get(agence['nom'], []))
            corps += f"""
            <tr>
                <td>{agence['nom']}</td>
                <td>{agence['priorite']}</td>
                <td>{nb}</td>
            </tr>
            """
        
        corps += "</table><p>🤖 Généré automatiquement par Axi</p>"
        
        nom_fichier = f"veille_concurrence_{datetime.now().strftime('%Y%m%d')}.xlsx" if excel_data else None
        
        envoyer_email(
            f"🔍 Veille Concurrence - {len(dans_zone)} dans zone ({datetime.now().strftime('%d/%m')})",
            corps,
            piece_jointe=excel_data,
            nom_fichier=nom_fichier
        )
    
    return {"nouvelles": len(nouvelles_annonces), "dans_zone": len(dans_zone)}

# ============================================================
# MEMORY CONTENT
# ============================================================

MEMORY_CONTENT = """# MEMORY - CONSIGNES POUR AXIS

*Dernière mise à jour: 24/12/2025*

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

### 1. Veille DPE ✅ OPÉRATIONNELLE + DVF
- Cron: 08h00 Paris
- Endpoint: /run-veille
- Enrichissement: historique ventes DVF

### 2. Veille Concurrence ✅ OPÉRATIONNELLE
- Cron: 07h00 Paris
- Endpoint: /run-veille-concurrence
- Agences: 16

### 3. DVF ✅ ACTIF
- Endpoint: /dvf/stats, /dvf/enrichir
- Données: 2022-2024, Dordogne

## HISTORIQUE

| Date | Action |
|------|--------|
| 24/12/2025 | v10: Code unifié (chat + veilles) |
| 23/12/2025 | Code chat écrasé les veilles |
| 22/12/2025 | v7: Machine de guerre + Excel |
| 22/12/2025 | v5: Enrichissement DVF intégré |
| 21/12/2025 | Création service unifié Railway |
"""

# ============================================================
# GÉNÉRATION HTML INTERFACE CHAT
# ============================================================

def generer_page_html(conversations, documents_dispo=None):
    """Génère la page HTML de l'interface chat"""
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Axi - ICI Dordogne</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #eee; min-height: 100vh; display: flex; flex-direction: column; }}
        .header {{ background: #16213e; padding: 15px 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #0f3460; }}
        .header h1 {{ font-size: 1.5rem; color: #e94560; }}
        .header .status {{ font-size: 0.9rem; color: #4ecca3; }}
        .chat-container {{ flex: 1; overflow-y: auto; padding: 20px; max-width: 900px; margin: 0 auto; width: 100%; }}
        .message {{ margin-bottom: 20px; padding: 15px; border-radius: 12px; }}
        .message.user {{ background: #0f3460; margin-left: 20%; }}
        .message.assistant {{ background: #16213e; margin-right: 10%; border-left: 3px solid #e94560; }}
        .message .role {{ font-size: 0.8rem; color: #888; margin-bottom: 5px; }}
        .message .content {{ line-height: 1.6; white-space: pre-wrap; }}
        .input-container {{ background: #16213e; padding: 20px; border-top: 1px solid #0f3460; }}
        .input-wrapper {{ max-width: 900px; margin: 0 auto; display: flex; gap: 10px; }}
        textarea {{ flex: 1; background: #0f3460; border: none; padding: 15px; border-radius: 8px; color: #eee; font-size: 1rem; resize: none; min-height: 60px; }}
        textarea:focus {{ outline: 2px solid #e94560; }}
        button {{ background: #e94560; color: white; border: none; padding: 15px 30px; border-radius: 8px; cursor: pointer; font-size: 1rem; transition: background 0.2s; }}
        button:hover {{ background: #ff6b6b; }}
        .nav {{ display: flex; gap: 10px; }}
        .nav a {{ color: #4ecca3; text-decoration: none; padding: 5px 10px; border-radius: 4px; }}
        .nav a:hover {{ background: #0f3460; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 Axi v10</h1>
        <div class="nav">
            <a href="/">Chat</a>
            <a href="/trio">Trio</a>
            <a href="/briefing">Briefing</a>
            <a href="/effacer">Effacer</a>
        </div>
        <div class="status">● En ligne</div>
    </div>
    
    <div class="chat-container" id="chat">
        {conversations}
    </div>
    
    <div class="input-container">
        <form class="input-wrapper" method="POST" action="/chat">
            <textarea name="message" placeholder="Écris ton message..." autofocus></textarea>
            <button type="submit">Envoyer</button>
        </form>
    </div>
    
    <script>
        document.getElementById('chat').scrollTop = document.getElementById('chat').scrollHeight;
    </script>
</body>
</html>"""


def formater_conversations_html(conversations_txt):
    """Formate les conversations en HTML"""
    if not conversations_txt:
        return '<div class="message assistant"><div class="role">Axi</div><div class="content">Salut ! Je suis Axi, prêt à t\'aider. 🚀</div></div>'
    
    html = ""
    lignes = conversations_txt.strip().split('\n')
    message_courant = []
    role_courant = None
    
    for ligne in lignes:
        if ligne.startswith('[USER]'):
            if message_courant and role_courant:
                contenu = '\n'.join(message_courant)
                css_class = 'user' if role_courant == 'user' else 'assistant'
                label = 'Toi' if role_courant == 'user' else 'Axi'
                html += f'<div class="message {css_class}"><div class="role">{label}</div><div class="content">{contenu}</div></div>'
            role_courant = 'user'
            message_courant = [ligne.replace('[USER] ', '')]
        elif ligne.startswith('[AXI]'):
            if message_courant and role_courant:
                contenu = '\n'.join(message_courant)
                css_class = 'user' if role_courant == 'user' else 'assistant'
                label = 'Toi' if role_courant == 'user' else 'Axi'
                html += f'<div class="message {css_class}"><div class="role">{label}</div><div class="content">{contenu}</div></div>'
            role_courant = 'assistant'
            message_courant = [ligne.replace('[AXI] ', '')]
        else:
            message_courant.append(ligne)
    
    # Dernier message
    if message_courant and role_courant:
        contenu = '\n'.join(message_courant)
        css_class = 'user' if role_courant == 'user' else 'assistant'
        label = 'Toi' if role_courant == 'user' else 'Axi'
        html += f'<div class="message {css_class}"><div class="role">{label}</div><div class="content">{contenu}</div></div>'
    
    return html if html else '<div class="message assistant"><div class="role">Axi</div><div class="content">Salut ! Je suis Axi, prêt à t\'aider. 🚀</div></div>'

# ============================================================
# APSCHEDULER - CRON JOBS
# ============================================================

def scheduler_loop():
    """Configure et démarre le scheduler pour les veilles automatiques"""
    if not SCHEDULER_OK:
        print("[SCHEDULER] APScheduler non disponible - cron désactivé")
        return
    
    try:
        paris_tz = pytz.timezone('Europe/Paris')
        scheduler = BackgroundScheduler(timezone=paris_tz)
        
        # Veille Concurrence à 7h00 Paris
        scheduler.add_job(
            run_veille_concurrence,
            CronTrigger(hour=7, minute=0, timezone=paris_tz),
            id='veille_concurrence',
            name='Veille Concurrence 7h00',
            replace_existing=True
        )
        
        # Veille DPE à 8h00 Paris
        scheduler.add_job(
            run_veille_dpe,
            CronTrigger(hour=8, minute=0, timezone=paris_tz),
            id='veille_dpe',
            name='Veille DPE 8h00',
            replace_existing=True
        )
        
        scheduler.start()
        print("[SCHEDULER] ✅ Cron configuré: Concurrence 7h00, DPE 8h00 (Paris)")
        
    except Exception as e:
        print(f"[SCHEDULER] Erreur: {e}")

# ============================================================
# HANDLER HTTP UNIFIÉ
# ============================================================

class AxiHandler(BaseHTTPRequestHandler):
    
    def do_GET(self):
        path = self.path.split('?')[0]
        
        # === INTERFACE CHAT ===
        if path == '/':
            conversations = lire_fichier(CONVERSATIONS_FILE)
            html_conv = formater_conversations_html(conversations)
            html = generer_page_html(html_conv)
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode())
        
        elif path == '/trio':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            html = """<!DOCTYPE html><html><head><title>Trio</title></head><body style="background:#1a1a2e;color:#eee;padding:20px;">
            <h1>🔺 Trio - Axis / Axi / Ludo</h1>
            <p>Interface de coordination entre les trois entités.</p>
            <a href="/" style="color:#4ecca3;">← Retour au chat</a>
            </body></html>"""
            self.wfile.write(html.encode())
        
        elif path == '/effacer':
            ecrire_fichier(CONVERSATIONS_FILE, "")
            self.send_response(302)
            self.send_header('Location', '/')
            self.end_headers()
        
        elif path == '/briefing':
            journal = lire_fichier(JOURNAL_FILE)
            derniers = journal[-2000:] if journal else "Aucun journal disponible."
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(f"=== BRIEFING AXI ===\n\n{derniers}".encode())
        
        elif path == '/memory':
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(MEMORY_CONTENT.encode())
        
        # === STATUS ET ENDPOINTS VEILLES ===
        elif path == '/status' or path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            status = {
                "service": "Axi ICI Dordogne v10 UNIFIÉ",
                "status": "ok",
                "features": ["Chat", "DPE", "Concurrence", "DVF"],
                "endpoints": ["/", "/trio", "/chat", "/briefing", "/memory", "/status",
                             "/run-veille", "/test-veille", "/run-veille-concurrence", 
                             "/test-veille-concurrence", "/dvf/stats", "/dvf/enrichir"]
            }
            self.wfile.write(json.dumps(status).encode())
        
        elif path == '/run-veille':
            result = run_veille_dpe()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        
        elif path == '/test-veille':
            # Test sans email
            print("[TEST] Veille DPE (mode test)")
            dpe_connus = charger_json(FICHIER_DPE, {})
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "mode": "test",
                "dpe_connus": len(dpe_connus),
                "codes_postaux": CODES_POSTAUX
            }).encode())
        
        elif path == '/run-veille-concurrence':
            result = run_veille_concurrence()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        
        elif path == '/test-veille-concurrence':
            print("[TEST] Veille Concurrence (mode test)")
            urls_connues = charger_json(FICHIER_URLS, {})
            total_urls = sum(len(v) for v in urls_connues.values())
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "mode": "test",
                "agences": len(AGENCES),
                "urls_connues": total_urls
            }).encode())
        
        elif path == '/dvf/stats':
            enrichisseur = get_enrichisseur()
            if not enrichisseur.index_dvf:
                enrichisseur.initialiser()
            
            stats = {}
            for cp in CODES_POSTAUX:
                stats[cp] = enrichisseur.stats_zone(cp)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(stats, ensure_ascii=False).encode())
        
        elif path.startswith('/dvf/enrichir'):
            # Parse query params
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            adresse = params.get('adresse', [''])[0]
            cp = params.get('cp', [''])[0]
            
            if not adresse:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"erreur": "Paramètre 'adresse' requis"}).encode())
                return
            
            enrichisseur = get_enrichisseur()
            result = enrichisseur.enrichir_adresse(adresse, cp)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode())
        
        elif path == '/check-new':
            # Pour AJAX refresh
            conversations = lire_fichier(CONVERSATIONS_FILE)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"length": len(conversations)}).encode())
        
        elif path == '/export':
            conversations = lire_fichier(CONVERSATIONS_FILE)
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Disposition', 'attachment; filename="conversations.txt"')
            self.end_headers()
            self.wfile.write(conversations.encode())
        
        else:
            self.send_response(404)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b"Not Found")
    
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        path = self.path
        
        if path == '/chat':
            # Formulaire HTML
            params = urllib.parse.parse_qs(post_data)
            message = params.get('message', [''])[0]
            
            if message:
                # Sauvegarder message utilisateur
                ajouter_fichier(CONVERSATIONS_FILE, f"\n[USER] {message}\n")
                
                # Générer réponse
                try:
                    client = anthropic.Anthropic()
                    conversations = lire_fichier(CONVERSATIONS_FILE)
                    reponse = generer_reponse(client, message, IDENTITE, "", conversations)
                    ajouter_fichier(CONVERSATIONS_FILE, f"[AXI] {reponse}\n")
                except Exception as e:
                    ajouter_fichier(CONVERSATIONS_FILE, f"[AXI] Erreur: {e}\n")
            
            self.send_response(302)
            self.send_header('Location', '/')
            self.end_headers()
        
        elif path == '/axis-message':
            # Message depuis Axis (JSON)
            try:
                data = json.loads(post_data)
                message = data.get('message', '')
                
                if message:
                    ajouter_fichier(CONVERSATIONS_FILE, f"\n[AXIS] {message}\n")
                    
                    client = anthropic.Anthropic()
                    conversations = lire_fichier(CONVERSATIONS_FILE)
                    reponse = generer_reponse(client, message, IDENTITE, "", conversations, est_axis=True)
                    ajouter_fichier(CONVERSATIONS_FILE, f"[AXI] {reponse}\n")
                    
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"response": reponse}).encode())
                else:
                    self.send_response(400)
                    self.end_headers()
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        
        elif path == '/memoire':
            # Sauvegarde mémoire depuis Axis
            try:
                data = json.loads(post_data)
                resume = data.get('resume', '')
                
                if resume:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
                    ajouter_fichier(JOURNAL_FILE, f"\n=== {timestamp} ===\n{resume}\n")
                    
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "saved"}).encode())
                else:
                    self.send_response(400)
                    self.end_headers()
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        print(f"[HTTP] {args[0]}")

# ============================================================
# MAIN
# ============================================================

def main():
    port = int(os.environ.get('PORT', 8080))
    
    print(f"""
╔════════════════════════════════════════════════════════════╗
║         AXI ICI DORDOGNE v10 UNIFIÉ                        ║
║         Chat + Veilles + DVF                               ║
╠════════════════════════════════════════════════════════════╣
║  Endpoints:                                                ║
║    /              Interface chat                           ║
║    /trio          Interface Trio                           ║
║    /briefing      Briefing journal                         ║
║    /memory        Consignes Axis                           ║
║    /status        Status JSON                              ║
║    /run-veille    Lancer veille DPE                        ║
║    /run-veille-concurrence  Lancer veille concurrence      ║
║    /dvf/stats     Stats DVF par CP                         ║
║    /dvf/enrichir  Enrichir une adresse                     ║
╠════════════════════════════════════════════════════════════╣
║  Cron: Concurrence 7h00, DPE 8h00 (Paris)                  ║
╚════════════════════════════════════════════════════════════╝
    """)
    
    # Démarrer le scheduler
    scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
    scheduler_thread.start()
    
    # Pré-initialiser DVF en arrière-plan
    def init_dvf():
        time.sleep(5)  # Attendre démarrage serveur
        try:
            enrichisseur = get_enrichisseur()
            enrichisseur.initialiser()
        except Exception as e:
            print(f"[DVF] Erreur init: {e}")
    
    dvf_thread = threading.Thread(target=init_dvf, daemon=True)
    dvf_thread.start()
    
    # Démarrer serveur HTTP
    server = HTTPServer(('0.0.0.0', port), AxiHandler)
    print(f"[SERVER] Démarré sur port {port}")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[SERVER] Arrêt...")
        server.shutdown()


if __name__ == "__main__":
    main()
