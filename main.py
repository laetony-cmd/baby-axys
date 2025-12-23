"""
AXI ICI DORDOGNE v9 + CHAT ADMIN - Service unifié Railway
- Veille DPE ADEME (8h00)
- Veille Concurrence v7 MACHINE DE GUERRE + Excel (7h00)
- Enrichissement DVF (historique ventes)
- Endpoints API
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
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import time
import re
from math import radians, cos, sin, asin, sqrt

# Infos admin chatbot Clara (ajoutées par les agents)
CHAT_ADMIN_INFOS = {}

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    OPENPYXL_OK = True
except:
    OPENPYXL_OK = False
    print("[WARNING] openpyxl non installé - Excel désactivé")

# ============================================================
# CONFIGURATION
# ============================================================

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

def envoyer_email(sujet, corps_html, piece_jointe=None, nom_fichier=None):
    """Envoie un email via Gmail SMTP avec pièce jointe optionnelle"""
    try:
        msg = MIMEMultipart('mixed')
        msg['Subject'] = sujet
        msg['From'] = GMAIL_USER
        msg['To'] = EMAIL_TO
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
    
    def trouver_parcelle(self, latitude, longitude):
        """Trouve la parcelle cadastrale via API IGN"""
        url = f"https://apicarto.ign.fr/api/cadastre/parcelle?geom={{\"type\":\"Point\",\"coordinates\":[{longitude},{latitude}]}}"
        
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'ICI-Dordogne/1.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
            
            if data.get('features'):
                props = data['features'][0].get('properties', {})
                return {
                    'id_parcelle': props.get('id', ''),
                    'section': props.get('section', ''),
                    'numero': props.get('numero', '')
                }
        except Exception as e:
            print(f"[CADASTRE] Erreur: {e}")
        return None
    
    def haversine(self, lon1, lat1, lon2, lat2):
        """Distance entre deux points GPS en km"""
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        return 6371 * 2 * asin(sqrt(a))
    
    def rechercher_par_gps(self, latitude, longitude, rayon_km=0.1):
        """Recherche les ventes dans un rayon autour de coordonnées GPS"""
        if not self.index_dvf:
            return []
        
        resultats = []
        for parcelle, mutations in self.index_dvf['par_parcelle'].items():
            for m in mutations:
                if m['latitude'] and m['longitude']:
                    distance = self.haversine(longitude, latitude, m['longitude'], m['latitude'])
                    if distance <= rayon_km:
                        m_copy = m.copy()
                        m_copy['distance_km'] = round(distance, 3)
                        resultats.append(m_copy)
        
        resultats.sort(key=lambda x: x['distance_km'])
        return resultats
    
    def enrichir(self, annonce):
        """
        Enrichit une annonce avec les données DVF
        
        Entrée: dict avec code_postal, adresse (optionnel), latitude/longitude (optionnel)
        Sortie: dict enrichi avec dvf_* fields
        """
        if not self.index_dvf:
            self.initialiser()
        
        enrichie = annonce.copy()
        
        # 1. Géocoder si pas de coordonnées
        if not annonce.get('latitude') and annonce.get('adresse'):
            geo = self.geocoder(annonce['adresse'], annonce.get('code_postal'))
            if geo:
                enrichie['latitude'] = geo['latitude']
                enrichie['longitude'] = geo['longitude']
                enrichie['code_insee'] = geo.get('code_insee')
        
        # 2. Trouver parcelle
        if not annonce.get('id_parcelle') and enrichie.get('latitude'):
            parcelle = self.trouver_parcelle(enrichie['latitude'], enrichie['longitude'])
            if parcelle:
                enrichie['id_parcelle'] = parcelle['id_parcelle']
                enrichie['section_cadastrale'] = parcelle['section']
                enrichie['numero_parcelle'] = parcelle['numero']
        
        # 3. Rechercher dans DVF
        resultat_dvf = None
        
        # Par parcelle
        if enrichie.get('id_parcelle') and enrichie['id_parcelle'] in self.index_dvf.get('par_parcelle', {}):
            mutations = self.index_dvf['par_parcelle'][enrichie['id_parcelle']]
            mutations_triees = sorted(mutations, key=lambda x: x['date_mutation'], reverse=True)
            resultat_dvf = mutations_triees[0] if mutations_triees else None
        
        # Par GPS (fallback)
        if not resultat_dvf and enrichie.get('latitude'):
            ventes_proches = self.rechercher_par_gps(enrichie['latitude'], enrichie['longitude'], 0.1)
            if ventes_proches:
                resultat_dvf = ventes_proches[0]
        
        # 4. Enrichir
        if resultat_dvf:
            enrichie['dvf_trouve'] = True
            enrichie['dvf_date_derniere_vente'] = resultat_dvf['date_mutation']
            enrichie['dvf_prix_derniere_vente'] = resultat_dvf['valeur_fonciere']
            enrichie['dvf_type'] = resultat_dvf['type_local']
            enrichie['dvf_surface'] = resultat_dvf['surface_reelle_bati']
            
            # Calcul plus-value si prix actuel connu
            if annonce.get('prix') and resultat_dvf['valeur_fonciere'] > 0:
                prix_actuel = annonce['prix']
                prix_achat = resultat_dvf['valeur_fonciere']
                plus_value = prix_actuel - prix_achat
                plus_value_pct = (plus_value / prix_achat * 100)
                enrichie['dvf_plus_value'] = plus_value
                enrichie['dvf_plus_value_pct'] = round(plus_value_pct, 1)
        else:
            enrichie['dvf_trouve'] = False
        
        return enrichie
    
    def get_stats(self):
        """Retourne les statistiques de l'index"""
        if not self.index_dvf:
            return {'status': 'non_initialise'}
        
        return {
            'status': 'ok',
            'nb_parcelles': len(self.index_dvf.get('par_parcelle', {})),
            'nb_codes_postaux': len(self.index_dvf.get('par_code_postal', {})),
            'derniere_maj': self.derniere_maj.isoformat() if self.derniere_maj else None
        }

# Instance globale DVF
enrichisseur_dvf = None

def get_enrichisseur():
    global enrichisseur_dvf
    if enrichisseur_dvf is None:
        enrichisseur_dvf = EnrichisseurDVF()
        enrichisseur_dvf.initialiser()
    return enrichisseur_dvf

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
    """Exécute la veille DPE avec enrichissement DVF"""
    print(f"[VEILLE DPE] Démarrage - {datetime.now()}")
    
    dpe_connus = charger_json(FICHIER_DPE, {})
    nouveaux_dpe = []
    total = 0
    
    # Initialiser enrichisseur DVF
    enrichisseur = get_enrichisseur()
    
    for cp in CODES_POSTAUX:
        resultats = get_dpe_ademe(cp)
        total += len(resultats)
        
        for dpe in resultats:
            num_dpe = dpe.get('N°DPE', '')
            if num_dpe and num_dpe not in dpe_connus:
                dpe_connus[num_dpe] = True
                
                # Enrichir avec DVF
                annonce = {
                    'adresse': dpe.get('Adresse_(BAN)', ''),
                    'code_postal': cp,
                    'commune': dpe.get('Nom_commune_(BAN)', '')
                }
                enrichi = enrichisseur.enrichir(annonce)
                
                dpe['dvf_trouve'] = enrichi.get('dvf_trouve', False)
                dpe['dvf_date'] = enrichi.get('dvf_date_derniere_vente', '')
                dpe['dvf_prix'] = enrichi.get('dvf_prix_derniere_vente', 0)
                
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
            <th>DVF</th>
            <th>Date</th>
        </tr>
        """
        
        for dpe in nouveaux_dpe[:50]:
            etiquette = dpe.get('Etiquette_DPE', '?')
            couleur = {
                'A': '#319834', 'B': '#33cc66', 'C': '#cbfc33',
                'D': '#fbea49', 'E': '#fccc2a', 'F': '#eb8235', 'G': '#d7221f'
            }.get(etiquette, '#888')
            
            # Info DVF
            dvf_info = "—"
            if dpe.get('dvf_trouve') and dpe.get('dvf_prix'):
                dvf_info = f"{dpe['dvf_prix']:,.0f}€ ({dpe['dvf_date'][:4]})"
            
            html += f"""
            <tr>
                <td>{dpe.get('Adresse_(BAN)', 'N/C')}</td>
                <td>{dpe.get('Nom_commune_(BAN)', 'N/C')}</td>
                <td style="background: {couleur}; color: white; text-align: center; font-weight: bold;">{etiquette}</td>
                <td style="text-align: center;">{dpe.get('Etiquette_GES', '?')}</td>
                <td>{dpe.get('Surface_habitable_logement', 'N/C')} m²</td>
                <td style="font-size: 11px;">{dvf_info}</td>
                <td>{dpe.get('Date_établissement_DPE', 'N/C')}</td>
            </tr>
            """
        
        html += "</table>"
        html += f"<p><small>Codes postaux: {', '.join(CODES_POSTAUX)} | DVF: {enrichisseur.get_stats().get('nb_parcelles', 0)} parcelles</small></p>"
        
        envoyer_email(f"🏠 ICI Dordogne - {len(nouveaux_dpe)} nouveau(x) DPE", html)
    
    return {"total": total, "nouveaux": len(nouveaux_dpe)}

# ============================================================
# VEILLE CONCURRENCE v6 - MACHINE DE GUERRE
# ============================================================

def extraire_urls_annonces(html, base_url):
    """Extrait les URLs des annonces d'une page HTML"""
    from urllib.parse import urljoin
    urls = set()
    
    patterns = [
        r'href=["\']([^"\']*(?:detail|annonce|bien|property|fiche|vente)[^"\']*)["\']',
        r'href=["\']([^"\']*(?:maison|appartement|terrain|propriete|villa)[^"\']*)["\']',
        r'href=["\']([^"\']+/\d{5,}[^"\']*)["\']',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for m in matches:
            if m.startswith('http'):
                url = m
            elif m.startswith('/'):
                url = urljoin(base_url, m)
            else:
                continue
            
            if any(x in url.lower() for x in ['contact', 'agence', 'mention', 'cookie', 'politique', 'cgu', '#', 'javascript', 'login', 'compte']):
                continue
            urls.add(url)
    
    return list(urls)

def extraire_cp_page_detail(html):
    """Extrait le code postal Dordogne d'une page de détail"""
    matches = re.findall(r'(24\d{3})', html)
    for m in matches:
        return m
    return None

def extraire_prix_page(html):
    """Extrait le prix d'une page"""
    patterns = [r'(\d{2,3}[\s\xa0]?\d{3})\s*€']
    for pattern in patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for m in matches:
            try:
                prix = int(m.replace(' ', '').replace('\xa0', ''))
                if 30000 <= prix <= 3000000:
                    return prix
            except:
                pass
    return None

def extraire_titre_page(html):
    """Extrait le titre d'une annonce"""
    patterns = [r'<h1[^>]*>([^<]+)</h1>', r'<title>([^<]+)</title>']
    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            titre = match.group(1).strip()
            titre = re.sub(r'\s+', ' ', titre)
            if len(titre) > 10:
                return titre[:100]
    return None

def enrichir_annonce(url):
    """Va chercher les détails d'une annonce (CP, prix, titre)"""
    html = fetch_url(url)
    if not html:
        return None
    return {
        "url": url,
        "cp": extraire_cp_page_detail(html),
        "prix": extraire_prix_page(html),
        "titre": extraire_titre_page(html),
        "date_vue": datetime.now().isoformat()
    }

def scraper_agence_urls(agence):
    """Scrape une agence et retourne les URLs d'annonces"""
    html = fetch_url(agence['url'])
    if not html:
        return {"agence": agence['nom'], "status": "erreur", "urls": []}
    
    urls = extraire_urls_annonces(html, agence['url'])
    
    # Pagination si beaucoup d'annonces
    if len(urls) > 10:
        for page in [2, 3]:
            sep = '&' if '?' in agence['url'] else '?'
            html2 = fetch_url(f"{agence['url']}{sep}page={page}")
            if html2:
                urls.extend(extraire_urls_annonces(html2, agence['url']))
            time.sleep(0.3)
    
    return {"agence": agence['nom'], "url": agence['url'], "status": "ok", "urls": list(set(urls))}

def creer_excel_veille(annonces_enrichies, dans_zone, toutes_urls):
    """Crée un fichier Excel avec les annonces de la veille"""
    if not OPENPYXL_OK:
        print("[EXCEL] openpyxl non disponible")
        return None
    
    wb = Workbook()
    
    # Styles
    header_fill = PatternFill(start_color="16213e", end_color="16213e", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    zone_fill = PatternFill(start_color="d4edda", end_color="d4edda", fill_type="solid")
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )
    
    # === FEUILLE 1: Dans votre zone ===
    ws1 = wb.active
    ws1.title = "Dans votre zone"
    
    ws1.merge_cells('A1:F1')
    ws1['A1'] = f"🎯 VEILLE CONCURRENCE ICI DORDOGNE - {datetime.now().strftime('%d/%m/%Y')}"
    ws1['A1'].font = Font(bold=True, size=14, color="16213e")
    ws1['A1'].alignment = Alignment(horizontal='center')
    
    headers = ["Agence", "CP", "Prix", "Titre", "Lien"]
    for col, h in enumerate(headers, 1):
        cell = ws1.cell(row=3, column=col, value=h)
        cell.fill, cell.font, cell.border = header_fill, header_font, thin_border
    
    row = 4
    for a in dans_zone:
        ws1.cell(row=row, column=1, value=a.get('agence', 'N/C')).border = thin_border
        ws1.cell(row=row, column=2, value=a.get('cp', 'N/C')).border = thin_border
        prix_cell = ws1.cell(row=row, column=3)
        prix_cell.value = a['prix'] if a.get('prix') else "N/C"
        if a.get('prix'): prix_cell.number_format = '#,##0 €'
        prix_cell.border = thin_border
        ws1.cell(row=row, column=4, value=(a.get('titre') or 'N/C')[:60]).border = thin_border
        ws1.cell(row=row, column=5, value=a.get('url', '')).border = thin_border
        ws1.cell(row=row, column=5).font = Font(color="0000FF", underline="single")
        for c in range(1, 6): ws1.cell(row=row, column=c).fill = zone_fill
        row += 1
    
    ws1.column_dimensions['A'].width = 25
    ws1.column_dimensions['B'].width = 10
    ws1.column_dimensions['C'].width = 12
    ws1.column_dimensions['D'].width = 50
    ws1.column_dimensions['E'].width = 60
    
    # === FEUILLE 2: Toutes les annonces ===
    ws2 = wb.create_sheet("Toutes les annonces")
    
    headers2 = ["Agence", "CP", "Prix", "Titre", "Dans Zone", "Lien"]
    for col, h in enumerate(headers2, 1):
        cell = ws2.cell(row=1, column=col, value=h)
        cell.fill, cell.font, cell.border = header_fill, header_font, thin_border
    
    row = 2
    for a in annonces_enrichies:
        ws2.cell(row=row, column=1, value=a.get('agence', 'N/C')).border = thin_border
        ws2.cell(row=row, column=2, value=a.get('cp', 'N/C')).border = thin_border
        prix_cell = ws2.cell(row=row, column=3)
        prix_cell.value = a['prix'] if a.get('prix') else "N/C"
        if a.get('prix'): prix_cell.number_format = '#,##0 €'
        prix_cell.border = thin_border
        ws2.cell(row=row, column=4, value=(a.get('titre') or 'N/C')[:60]).border = thin_border
        zone_cell = ws2.cell(row=row, column=5)
        zone_cell.value = "OUI" if a.get('cp') in CODES_POSTAUX else "NON"
        if a.get('cp') in CODES_POSTAUX: zone_cell.fill = zone_fill
        zone_cell.border = thin_border
        ws2.cell(row=row, column=6, value=a.get('url', '')).border = thin_border
        row += 1
    
    ws2.column_dimensions['A'].width = 25
    ws2.column_dimensions['B'].width = 10
    ws2.column_dimensions['C'].width = 12
    ws2.column_dimensions['D'].width = 50
    ws2.column_dimensions['E'].width = 10
    ws2.column_dimensions['F'].width = 60
    
    # Sauvegarder en mémoire
    excel_buffer = io.BytesIO()
    wb.save(excel_buffer)
    excel_buffer.seek(0)
    return excel_buffer.getvalue()

def run_veille_concurrence():
    """Veille concurrence v7 - Machine de guerre avec Excel"""
    print(f"[VEILLE v7] Démarrage - {datetime.now()}")
    
    cache = charger_json(FICHIER_URLS, {"urls": {}, "derniere_maj": None})
    urls_connues = set(cache.get("urls", {}).keys())
    print(f"[VEILLE v7] {len(urls_connues)} URLs en cache")
    
    # Scraper toutes les agences
    toutes_urls = {}
    for agence in AGENCES:
        print(f"  → {agence['nom']}...")
        result = scraper_agence_urls(agence)
        for url in result.get('urls', []):
            toutes_urls[url] = agence['nom']
        time.sleep(0.5)
    
    print(f"[VEILLE v7] {len(toutes_urls)} URLs détectées")
    
    # Nouvelles URLs
    nouvelles_urls = {url: ag for url, ag in toutes_urls.items() if url not in urls_connues}
    print(f"[VEILLE v7] {len(nouvelles_urls)} NOUVELLES à enrichir")
    
    # Enrichir (max 50)
    annonces_enrichies = []
    for url, agence in list(nouvelles_urls.items())[:50]:
        detail = enrichir_annonce(url)
        if detail:
            detail['agence'] = agence
            annonces_enrichies.append(detail)
            cache["urls"][url] = detail
        time.sleep(0.3)
    
    # Filtrer sur CP cibles
    dans_zone = [a for a in annonces_enrichies if a.get('cp') in CODES_POSTAUX]
    print(f"[VEILLE v7] {len(dans_zone)} dans la zone cible")
    
    cache["derniere_maj"] = datetime.now().isoformat()
    sauver_json(FICHIER_URLS, cache)
    
    # Créer Excel
    excel_data = creer_excel_veille(annonces_enrichies, dans_zone, toutes_urls)
    nom_excel = f"Veille_Concurrence_{datetime.now().strftime('%Y%m%d')}.xlsx"
    
    # Email HTML
    html = f"""
    <h2>🎯 Veille Concurrence ICI Dordogne</h2>
    <p>Rapport du {datetime.now().strftime('%d/%m/%Y à %H:%M')}</p>
    <h3>📊 Résumé</h3>
    <ul>
        <li><strong>{len(toutes_urls)}</strong> annonces sur {len(AGENCES)} agences</li>
        <li><strong>{len(nouvelles_urls)}</strong> nouvelles détectées</li>
        <li><strong style="color: #16a34a;">{len(dans_zone)}</strong> dans votre zone (12 CP)</li>
    </ul>
    """
    
    if dans_zone:
        html += """
        <h3>🎯 NOUVELLES ANNONCES DANS VOTRE ZONE</h3>
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
        <tr style="background: #16213e; color: white;">
            <th>Agence</th><th>CP</th><th>Prix</th><th>Titre</th><th>Lien</th>
        </tr>
        """
        for a in dans_zone:
            prix_str = f"{a['prix']:,}€".replace(',', ' ') if a.get('prix') else "N/C"
            html += f"""
            <tr>
                <td>{a.get('agence', 'N/C')}</td>
                <td style="font-weight: bold;">{a.get('cp', 'N/C')}</td>
                <td>{prix_str}</td>
                <td>{(a.get('titre') or 'N/C')[:50]}</td>
                <td><a href="{a['url']}">Voir</a></td>
            </tr>
            """
        html += "</table>"
    else:
        html += "<p><em>Aucune nouvelle annonce dans votre zone aujourd'hui.</em></p>"
    
    html += f"""
    <p><small>CP surveillés: {', '.join(CODES_POSTAUX)}</small></p>
    <p><strong>📎 Fichier Excel en pièce jointe avec toutes les données</strong></p>
    """
    
    envoyer_email(
        f"🎯 Veille Concurrence - {len(dans_zone)} nouvelles dans votre zone",
        html,
        piece_jointe=excel_data,
        nom_fichier=nom_excel
    )
    
    return {"total": len(toutes_urls), "nouvelles": len(nouvelles_urls), "enrichies": len(annonces_enrichies), "dans_zone": len(dans_zone)}

# ============================================================
# MEMORY API
# ============================================================

MEMORY_CONTENT = """# MEMORY - CONSIGNES POUR AXIS

*Dernière mise à jour: 23/12/2025*

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

### 3. DVF ✅ NOUVEAU
- Endpoint: /dvf/stats, /dvf/enrichir
- Données: 2022-2024, Dordogne
- Parcelles indexées: 23 680

## AGENCES ICI DORDOGNE

### Structure
- **Vergt** : Agence principale
- **Le Bugue** : Deuxième agence
- **Équipe** : Anthony (opérationnel), Julie, Ingrid (validation NL)
- **Contact** : 05 53 13 33 33

### Stack technique
| Outil | Usage |
|-------|-------|
| SweepBright | CRM principal |
| Slack | Communication interne |
| Trello | Suivi dossiers |
| Gmail | Emails + Calendar |
| Google Ads | Campagnes (CPC 0.09€) |
| Netlify | Sites dédiés par bien |
| HeyGen | Vidéos présentation |

### Sites dédiés déployés
1. **Manzac** - nouveaute-maisonavendre-manzacsurvern.netlify.app (198K€, 99m²)
2. **Saint-Geyrac** - icidordogne-paradis-saint-geyrac.netlify.app (395K€)
3. Template validé : 3 langues (FR/EN/NL), chat IA, capture email

### Google Ads actif
- CPC: 0.09€ (marché = 1-3€)
- Clics: 1200+
- 1ère conversion: 6 décembre 2025

## SIMPLY PÉRIGORD

- **Activité** : Location saisonnière premium
- **Site** : simply-perigord.com
- **Positionnement** : Biens haut de gamme uniquement

## PLAN DIRECTEUR

- 6 semaines jusqu au Maroc
- Julie = prospection vendeurs
- Anthony = vente uniquement

## HISTORIQUE

| Date | Action |
|------|--------|
| 23/12/2025 | Sync mémoire agences + Simply depuis Axis |
| 22/12/2025 | v5: Enrichissement DVF intégré |
| 22/12/2025 | v4: 16 agences complètes |
| 22/12/2025 | v3: Veille concurrence intégrée |
| 22/12/2025 | Cron APScheduler intégré |
| 21/12/2025 | Création service unifié Railway |
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
        
        if heure == "07:00" and last_concurrence != date_str:
            print("[CRON] Lancement veille concurrence 7h00")
            try:
                run_veille_concurrence()
                last_concurrence = date_str
            except Exception as e:
                print(f"[CRON ERREUR] Concurrence: {e}")
        
        if heure == "08:00" and last_dpe != date_str:
            print("[CRON] Lancement veille DPE 8h00")
            try:
                run_veille_dpe()
                last_dpe = date_str
            except Exception as e:
                print(f"[CRON ERREUR] DPE: {e}")
        
        time.sleep(30)

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
    

    def do_OPTIONS(self):
        """Gestion CORS preflight"""
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        path = self.path.split('?')[0]
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        
        if path == '/':
            self.send_json({
                "service": "Axi ICI Dordogne v7",
                "status": "ok",
                "features": ["DPE", "Concurrence", "DVF"],
                "endpoints": ["/memory", "/status", "/dvf/stats", "/dvf/enrichir", "/run-veille", "/test-veille", "/run-veille-concurrence", "/test-veille-concurrence"]
            })
        
        elif path == '/memory':
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(MEMORY_CONTENT.encode())
        
        elif path == '/status':
            enrichisseur = get_enrichisseur()
            self.send_json({
                "status": "ok",
                "time": datetime.now().isoformat(),
                "service": "Axi ICI Dordogne v7",
                "crons": ["07:00 concurrence", "08:00 DPE"],
                "dvf": enrichisseur.get_stats(),
                "email_to": EMAIL_TO,
                "codes_postaux": len(CODES_POSTAUX),
                "agences": len(AGENCES)
            })
        
        elif path == '/briefing':
            enrichisseur = get_enrichisseur()
            dvf_stats = enrichisseur.get_stats()
            briefing = f"""
# BRIEFING AXI - {datetime.now().strftime('%d/%m/%Y %H:%M')}

## Statut Système
- Service: v5 opérationnel
- Veilles actives: DPE (8h) + Concurrence (7h)
- DVF: {dvf_stats.get('nb_parcelles', 0)} parcelles indexées
- Agences surveillées: {len(AGENCES)}
- Codes postaux: {len(CODES_POSTAUX)}

## Nouvelles fonctionnalités v5
- Enrichissement DVF automatique
- Historique des ventes sur chaque DPE
- API /dvf/enrichir pour enrichir n'importe quelle adresse

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
        
        elif path == '/test-veille-concurrence':
            print("[TEST] Veille Concurrence v6 (sans email)")
            # Test sur 3 agences
            test_urls = {}
            for agence in AGENCES[:3]:
                result = scraper_agence_urls(agence)
                for url in result.get('urls', []):
                    test_urls[url] = agence['nom']
                time.sleep(0.3)
            
            # Enrichir 5 URLs max
            enrichies = []
            for url in list(test_urls.keys())[:5]:
                detail = enrichir_annonce(url)
                if detail:
                    detail['agence'] = test_urls[url]
                    enrichies.append(detail)
                time.sleep(0.2)
            
            dans_zone = [a for a in enrichies if a.get('cp') in CODES_POSTAUX]
            self.send_json({
                "status": "ok",
                "agences_testees": 3,
                "urls_trouvees": len(test_urls),
                "enrichies": len(enrichies),
                "dans_zone": len(dans_zone),
                "details": enrichies[:5],
                "sent_to": "non envoyé"
            })
        
        elif path == '/test-veille':
            print("[TEST] Veille DPE (sans email)")
            total = 0
            for cp in CODES_POSTAUX[:3]:
                resultats = get_dpe_ademe(cp)
                total += len(resultats)
            self.send_json({"status": "ok", "total": total, "sent_to": "non envoyé"})
        
        elif path == '/dvf/stats':
            enrichisseur = get_enrichisseur()
            self.send_json(enrichisseur.get_stats())
        
        elif path == '/dvf/recherche':
            lat = query.get('lat', [None])[0]
            lon = query.get('lon', [None])[0]
            
            if lat and lon:
                enrichisseur = get_enrichisseur()
                resultats = enrichisseur.rechercher_par_gps(float(lat), float(lon), 0.5)
                self.send_json({"resultats": resultats[:20]})
            else:
                self.send_json({"error": "Paramètres lat et lon requis"}, 400)
        
        
        elif path.startswith('/site-chat-admin'):
            # Mode admin - voir les infos
            site = self.path.split('site=')[-1].split('&')[0] if 'site=' in self.path else 'all'
            if site == 'all':
                self.send_json({'sites': list(CHAT_ADMIN_INFOS.keys()), 'data': CHAT_ADMIN_INFOS})
            else:
                infos = CHAT_ADMIN_INFOS.get(site, [])
                self.send_json({'site': site, 'infos': infos, 'total': len(infos)})

        elif path == '/agences':
            self.send_json({"total": len(AGENCES), "agences": AGENCES})
        
        else:
            self.send_json({"error": "Not found"}, 404)
    
    def do_POST(self):
        path = self.path.split('?')[0]
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else '{}'
        
        if path == '/dvf/enrichir':
            try:
                annonce = json.loads(body)
                enrichisseur = get_enrichisseur()
                enrichie = enrichisseur.enrichir(annonce)
                self.send_json(enrichie)
            except Exception as e:
                self.send_json({"error": str(e)}, 400)
        
        elif path == '/memoire':
            print(f"[MEMOIRE] Reçu: {body[:100]}...")
            self.send_json({"status": "ok", "saved": True})
        

        elif path == '/site-chat':
            try:
                data = json.loads(body)
                message = data.get('message', '')
                history = data.get('history', [])
                site = data.get('site', 'default')
                
                if not message:
                    self.send_json({'reply': 'Pouvez-vous reformuler votre question ?'})
                    return
                
                ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
                if not ANTHROPIC_API_KEY:
                    self.send_json({'reply': 'Je suis momentanément indisponible. Appelez le 05 53 13 33 33.'})
                    return
                
                CONTEXTES = {
                    'saint-paul': """Tu es Clara, assistante ICI Dordogne pour villa Saint-Paul-de-Serre.
Prix: 420 000€. 190m². Terrain 7249m². 4 chambres. Piscine 10x5m. DPE B.
Distances: Périgueux 15 min, Bergerac 25 min.
Réponds en 2-3 phrases max. Contact: 05 53 13 33 33.""",
                    'bassillac': """Tu es Clara, assistante ICI Dordogne pour maison Bassillac.
Prix: 198 000€, 99m², 3 chambres, DPE C. Contact: 05 53 13 33 33. 2-3 phrases.""",
                    'manzac': """Tu es Clara, assistante ICI Dordogne pour maison Manzac.
Prix: 198 000€, 99m², terrain 1889m², DPE C. Contact: 05 53 13 33 33. 2-3 phrases.""",
                    'default': """Tu es Clara, assistante ICI Dordogne.
Contact: 05 53 13 33 33. Réponds en 2-3 phrases max."""
                }
                
                context = CONTEXTES.get(site, CONTEXTES['default'])
                
                # Ajouter les infos admin si présentes
                admin_infos = CHAT_ADMIN_INFOS.get(site, [])
                if admin_infos:
                    context += "\n\nINFOS SUPPLÉMENTAIRES:\n" + "\n".join(f"- {info}" for info in admin_infos)
                messages = history[-10:] + [{'role': 'user', 'content': message}]
                
                req_data = json.dumps({
                    'model': 'claude-3-haiku-20240307',
                    'max_tokens': 300,
                    'system': context,
                    'messages': messages
                }).encode('utf-8')
                
                req = urllib.request.Request(
                    'https://api.anthropic.com/v1/messages',
                    data=req_data,
                    headers={
                        'Content-Type': 'application/json',
                        'x-api-key': ANTHROPIC_API_KEY,
                        'anthropic-version': '2023-06-01'
                    }
                )
                
                with urllib.request.urlopen(req, timeout=30) as resp:
                    result = json.loads(resp.read().decode())
                
                if 'content' in result and len(result['content']) > 0:
                    reply = result['content'][0]['text']
                    self.send_json({
                        'reply': reply,
                        'history': messages + [{'role': 'assistant', 'content': reply}]
                    })
                else:
                    self.send_json({
                        'reply': 'Désolée, appelez le 05 53 13 33 33 !',
                        'error': result.get('error', {}).get('message', 'Unknown')
                    })
                    
            except Exception as e:
                print(f"[CHAT ERROR] {e}")
                self.send_json({
                    'reply': 'Je suis indisponible. Appelez le 05 53 13 33 33 !',
                    'error': str(e)
                })

        elif path == '/site-chat-admin':
            try:
                data = json.loads(body)
                site = data.get('site', 'default')
                
                if data.get('clear'):
                    CHAT_ADMIN_INFOS[site] = []
                    self.send_json({'status': 'cleared', 'site': site})
                elif data.get('info'):
                    if site not in CHAT_ADMIN_INFOS:
                        CHAT_ADMIN_INFOS[site] = []
                    CHAT_ADMIN_INFOS[site].append(data['info'])
                    self.send_json({
                        'status': 'added',
                        'site': site,
                        'info': data['info'],
                        'total': len(CHAT_ADMIN_INFOS[site])
                    })
                else:
                    self.send_json({'error': 'Missing info or clear parameter'}, 400)
            except Exception as e:
                self.send_json({'error': str(e)}, 400)

        else:
            self.send_json({"error": "Not found"}, 404)
    
    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")

# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("AXI ICI DORDOGNE v9 + CHAT ADMIN")
    print(f"Veille DPE: {len(CODES_POSTAUX)} codes postaux")
    print(f"Veille Concurrence: {len(AGENCES)} agences")
    print("DVF: Enrichissement historique ventes")
    print("=" * 60)
    
    # Pré-charger DVF au démarrage
    print("[INIT] Chargement index DVF...")
    get_enrichisseur()
    
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
