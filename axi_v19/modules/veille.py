# axi_v19/modules/veille.py
"""
Module Veille V19 - DPE et Concurrence
Port des fonctions V18 vers architecture Bunker

"Je ne lâche pas." 💪
"""

import os
import json
import urllib.request
import urllib.parse
import smtplib
import ssl
import gzip
import re
import time
import logging
import requests  # Plus robuste que urllib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from io import BytesIO

logger = logging.getLogger("axi_v19.veille")

# =============================================================================
# CONFIGURATION
# =============================================================================

GMAIL_USER = os.environ.get("GMAIL_USER", "u5050786429@gmail.com")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "izemquwmmqjdasrk")
EMAIL_TO = os.environ.get("EMAIL_TO", "agence@icidordogne.fr")
EMAIL_CC = os.environ.get("EMAIL_CC", "laetony@gmail.com")

# Codes postaux surveillés
CODES_POSTAUX = [
    "24260", "24480", "24150", "24510", "24220", "24620",  # Zone Le Bugue
    "24380", "24110", "24140", "24520", "24330", "24750"   # Zone Vergt
]

# Headers pour scraping
HEADERS_SCRAPER = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive'
}

# Configuration 16 agences
SCRAPERS_CONFIG = {
    "Périgord Noir Immobilier": {
        "type": "html",
        "base_url": "https://perigordnoirimmobilier.com",
        "search_url": "https://perigordnoirimmobilier.com/nos-biens-immobiliers/?page_number={page}",
        "max_pages": 5,
        "pattern": r'href="([^"]+/detail/[^"]+\.html)"'
    },
    "Virginie Michelin": {
        "type": "html",
        "base_url": "https://virginie-michelin-immobilier.fr",
        "search_url": "https://virginie-michelin-immobilier.fr/immobilier/vente",
        "max_pages": 1,
        "pattern": r'href="([^"]+/annonce/[^"]+)"'
    },
    "Bayenche Immobilier": {
        "type": "api_json",
        "api_url": "https://www.bayencheimmobilier.fr/api/properties",
        "params": {"transaction": "sale", "limit": 100}
    },
    "Laforêt Périgueux": {
        "type": "api_rest",
        "api_url": "https://www.laforet.com/api/immo/properties/search",
        "params": {"agencyIds[]": "laforet-perigueux", "transactionType": "sale"}
    },
    "HUMAN Immobilier": {
        "type": "html",
        "base_url": "https://www.human-immobilier.fr",
        "search_url": "https://www.human-immobilier.fr/immobilier-dordogne-24?page={page}",
        "max_pages": 3,
        "pattern": r'href="(/annonce-immobiliere-[^"]+)"'
    },
    "Valadié Immobilier": {
        "type": "html",
        "base_url": "https://www.valadie-immobilier.com",
        "search_url": "https://www.valadie-immobilier.com/fr/vente/maison?page={page}",
        "max_pages": 2,
        "pattern": r'href="([^"]+/vente/[^"]+\.html)"'
    },
    "Internat Agency": {
        "type": "api_json",
        "api_url": "https://www.interimmoagency.com/api/properties",
        "params": {"for_sale": "true"}
    },
    "Agence du Périgord": {
        "type": "html",
        "base_url": "https://www.agenceduperigord.fr",
        "search_url": "https://www.agenceduperigord.fr/acheter",
        "max_pages": 1,
        "pattern": r'href="([^"]+/bien/[^"]+)"'
    },
    "Century 21 Dordogne": {
        "type": "api_rest",
        "api_url": "https://www.century21.fr/api/properties",
        "params": {"department": "24"}
    },
    "Immobilier La Maison": {
        "type": "html",
        "base_url": "https://www.immobilierlamaison.fr",
        "search_url": "https://www.immobilierlamaison.fr/vente",
        "max_pages": 1,
        "pattern": r'href="([^"]+/annonce/[^"]+)"'
    },
    "Cabinet Labrousse": {
        "type": "html",
        "base_url": "https://www.cabinet-labrousse.fr",
        "search_url": "https://www.cabinet-labrousse.fr/recherche/?type%5B%5D=buy",
        "max_pages": 2,
        "pattern": r'href="([^"]+/annonces/[^"]+)"'
    },
    "Lagrange Immobilier": {
        "type": "html",
        "base_url": "https://www.lagrangeimmobilier.com",
        "search_url": "https://www.lagrangeimmobilier.com/fr/ventes",
        "max_pages": 2,
        "pattern": r'href="(/fr/vente/[^"]+)"'
    },
    "Lascaux Immobilier": {
        "type": "html",
        "base_url": "https://www.lascaux-immobilier.com",
        "search_url": "https://www.lascaux-immobilier.com/fr/annonces/achat",
        "max_pages": 1,
        "pattern": r'href="([^"]+/annonces/[^"]+)"'
    },
    "Dordogne Habitat": {
        "type": "html",
        "base_url": "https://www.dordogne-habitat.com",
        "search_url": "https://www.dordogne-habitat.com/nos-offres",
        "max_pages": 2,
        "pattern": r'href="(/offres/[^"]+)"'
    },
    "Immo Sud Ouest": {
        "type": "api_json",
        "api_url": "https://www.immosudouest.fr/api/listings",
        "params": {"department": "24", "type": "sale"}
    },
    "Sarlat Immobilier": {
        "type": "html",
        "base_url": "https://www.sarlat-immobilier.fr",
        "search_url": "https://www.sarlat-immobilier.fr/vente",
        "max_pages": 2,
        "pattern": r'href="([^"]+/bien-[^"]+)"'
    }
}


# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def envoyer_email(sujet, corps_html, destinataire=None):
    """Envoie un email via Gmail SMTP."""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = sujet
        msg['From'] = GMAIL_USER
        msg['To'] = destinataire or EMAIL_TO
        msg['Cc'] = EMAIL_CC
        
        msg.attach(MIMEText(corps_html, 'html', 'utf-8'))
        
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            recipients = [msg['To']]
            if msg['Cc']:
                recipients.append(msg['Cc'])
            server.sendmail(msg['From'], recipients, msg.as_string())
        
        logger.info(f"📧 Email envoyé: {sujet}")
        return True
    except Exception as e:
        logger.error(f"❌ Erreur email: {e}")
        return False


def get_dpe_ademe(code_postal):
    """
    Récupère les DPE récents depuis l'API ADEME.
    
    MISE À JOUR 05/01/2026: 
    - Nouveau dataset dpe03existant (ancien dpe-v2-logements-existants → 404)
    - Migration urllib → requests pour robustesse
    - Meilleure gestion d'erreurs
    """
    # NOUVEAU dataset ADEME 2025
    url = "https://data.ademe.fr/data-fair/api/v1/datasets/dpe03existant/lines"
    
    # Paramètres de recherche (q_mode=simple OBLIGATOIRE pour recherche par champ)
    params = {
        "size": 100,
        "q": str(code_postal),
        "q_fields": "code_postal_ban",
        "q_mode": "simple",
        "select": "numero_dpe,date_reception_dpe,etiquette_dpe,etiquette_ges,adresse_brut,code_postal_ban,nom_commune_ban,type_batiment,surface_habitable_logement,_geopoint,conso_5_usages_par_m2_ep,emission_ges_5_usages_par_m2,cout_total_5_usages,annee_construction,type_energie_principale_chauffage",
        "sort": "-date_reception_dpe"
    }
    
    headers = {
        'User-Agent': 'ICI-Dordogne-V19/1.0',
        'Accept': 'application/json'
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()  # Lève exception si erreur HTTP
        
        data = response.json()
        total = data.get('total', 0)
        
        # Normaliser les noms de champs pour compatibilité avec le reste du code
        results = []
        for dpe in data.get('results', []):
            normalized = {
                'N°DPE': dpe.get('numero_dpe', ''),
                'Date_réception_DPE': dpe.get('date_reception_dpe', ''),
                'Etiquette_DPE': dpe.get('etiquette_dpe', ''),
                'Etiquette_GES': dpe.get('etiquette_ges', ''),
                'Adresse_brute': dpe.get('adresse_brut', ''),
                'Code_postal_(BAN)': dpe.get('code_postal_ban', ''),
                'Nom_commune_(BAN)': dpe.get('nom_commune_ban', ''),
                'Type_bâtiment': dpe.get('type_batiment', ''),
                'Surface_habitable_logement': dpe.get('surface_habitable_logement', ''),
                '_geopoint': dpe.get('_geopoint', ''),
                'Conso_kWh_m2_an': dpe.get('conso_5_usages_par_m2_ep', ''),
                'Emission_GES_m2_an': dpe.get('emission_ges_5_usages_par_m2', ''),
                'Cout_annuel': dpe.get('cout_total_5_usages', ''),
                'Annee_construction': dpe.get('annee_construction', ''),
                'Type_chauffage': dpe.get('type_energie_principale_chauffage', '')
            }
            results.append(normalized)
        
        logger.info(f"[DPE] {code_postal}: {len(results)} DPE trouvés (total API: {total})")
        return results
        
    except requests.exceptions.Timeout:
        logger.error(f"[DPE] Timeout {code_postal} - API ADEME ne répond pas")
        return []
    except requests.exceptions.HTTPError as e:
        logger.error(f"[DPE] Erreur HTTP {code_postal}: {e}")
        return []
    except requests.exceptions.RequestException as e:
        logger.error(f"[DPE] Erreur réseau {code_postal}: {e}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"[DPE] Erreur JSON {code_postal}: {e}")
        return []
    except Exception as e:
        logger.error(f"[DPE] Erreur inattendue {code_postal}: {type(e).__name__}: {e}")
        return []


# =============================================================================
# SCRAPER ENGINE V19
# =============================================================================

class ScraperEngineV19:
    """Moteur de scraping unifié pour 16 agences - V19"""
    
    def __init__(self):
        self.headers = HEADERS_SCRAPER.copy()
        self.stats = {'total_urls': 0, 'erreurs': 0, 'par_agence': {}}
    
    def fetch_html(self, url, timeout=20, retry=2):
        """Récupère une URL avec retry et gestion gzip."""
        for attempt in range(retry + 1):
            try:
                req = urllib.request.Request(url, headers=self.headers)
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    if response.info().get('Content-Encoding') == 'gzip':
                        buf = BytesIO(response.read())
                        with gzip.GzipFile(fileobj=buf) as f:
                            return f.read().decode('utf-8', errors='ignore')
                    return response.read().decode('utf-8', errors='ignore')
            except Exception as e:
                if attempt < retry:
                    time.sleep(1 * (attempt + 1))
                    continue
                logger.debug(f"Fetch failed {url}: {e}")
                return None
        return None
    
    def fetch_json(self, url, params=None, timeout=20):
        """Récupère JSON depuis API."""
        try:
            if params:
                url = f"{url}?{urllib.parse.urlencode(params)}"
            headers = self.headers.copy()
            headers['Accept'] = 'application/json'
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode('utf-8'))
        except:
            return None
    
    def _is_valid_url(self, url):
        if not url:
            return False
        invalid = ['javascript:', 'mailto:', 'tel:', '#', 'login', 'contact', '.css', '.js', '.png', '.jpg']
        return not any(p in url.lower() for p in invalid)
    
    def scrape_html(self, config):
        """Scrape pages HTML avec pattern regex."""
        urls = set()
        base_url = config.get('base_url', '')
        
        for page in range(1, config.get('max_pages', 1) + 1):
            search_url = config['search_url'].format(page=page)
            logger.info(f"[SCRAPER] Fetching: {search_url}")
            html = self.fetch_html(search_url)
            if not html:
                logger.warning(f"[SCRAPER] No HTML returned for {search_url}")
                continue
            
            logger.info(f"[SCRAPER] HTML size: {len(html)} chars")
            matches = re.findall(config['pattern'], html)
            logger.info(f"[SCRAPER] Pattern matches: {len(matches)}")
            
            for match in matches:
                url = match if match.startswith('http') else f"{base_url}{match}"
                if self._is_valid_url(url):
                    urls.add(url)
            
            time.sleep(0.5)
        
        return list(urls)
    
    def scrape_api_json(self, config):
        """Scrape via API JSON."""
        urls = set()
        data = self.fetch_json(config['api_url'], config.get('params'))
        
        if data:
            # Extraction générique des URLs
            def extract_urls(obj, urls_set):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if k in ['url', 'link', 'href', 'permalink'] and isinstance(v, str):
                            if self._is_valid_url(v):
                                urls_set.add(v)
                        else:
                            extract_urls(v, urls_set)
                elif isinstance(obj, list):
                    for item in obj:
                        extract_urls(item, urls_set)
            
            extract_urls(data, urls)
        
        return list(urls)
    
    def scrape_api_rest(self, config):
        """Scrape via API REST."""
        return self.scrape_api_json(config)  # Même logique
    
    def scrape_agence(self, agence_name):
        """Scrape une agence selon sa config."""
        if agence_name not in SCRAPERS_CONFIG:
            return []
        
        config = SCRAPERS_CONFIG[agence_name]
        scrape_type = config.get('type', 'html')
        
        try:
            if scrape_type == 'html':
                return self.scrape_html(config)
            elif scrape_type == 'api_json':
                return self.scrape_api_json(config)
            elif scrape_type == 'api_rest':
                return self.scrape_api_rest(config)
            else:
                return []
        except Exception as e:
            logger.error(f"Erreur scraping {agence_name}: {e}")
            return []
    
    def scrape_all(self):
        """Scrape toutes les agences."""
        resultats = {}
        
        for agence_name in SCRAPERS_CONFIG.keys():
            logger.info(f"[SCRAPER] {agence_name}...")
            urls = self.scrape_agence(agence_name)
            resultats[agence_name] = urls
            self.stats['total_urls'] += len(urls)
            self.stats['par_agence'][agence_name] = len(urls)
            time.sleep(1)  # Pause entre agences
        
        return resultats


# =============================================================================
# VEILLE DPE
# =============================================================================

# Stockage en mémoire (sera migré vers v19_brain PostgreSQL)
_dpe_connus = {}

def run_veille_dpe(db=None):
    """Exécute la veille DPE quotidienne."""
    global _dpe_connus
    
    logger.info(f"[VEILLE DPE] Démarrage - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    nouveaux_dpe = []
    
    for cp in CODES_POSTAUX:
        logger.info(f"[DPE] Scan {cp}...")
        resultats = get_dpe_ademe(cp)
        
        for dpe in resultats:
            numero = dpe.get('N°DPE', '')
            if numero and numero not in _dpe_connus:
                _dpe_connus[numero] = {
                    'date_detection': datetime.now().isoformat(),
                    'data': dpe
                }
                nouveaux_dpe.append(dpe)
        
        time.sleep(0.5)
    
    logger.info(f"[DPE] Terminé: {len(nouveaux_dpe)} nouveaux DPE")
    
    # Envoyer email si nouveaux DPE
    if nouveaux_dpe:
        corps = f"""
        <h2>🏠 Veille DPE V19 - {len(nouveaux_dpe)} nouveaux diagnostics</h2>
        <p>Date: {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
        <p><em>Généré par Axi V19 - Architecture Bunker</em></p>
        <table border="1" cellpadding="5" style="border-collapse: collapse;">
            <tr style="background-color: #4CAF50; color: white;">
                <th>Adresse</th>
                <th>CP</th>
                <th>Commune</th>
                <th>Type</th>
                <th>Surface</th>
                <th>DPE</th>
            </tr>
        """
        
        for dpe in nouveaux_dpe[:50]:  # Limiter à 50
            corps += f"""
            <tr>
                <td>{dpe.get('Adresse_brute', 'N/A')}</td>
                <td>{dpe.get('Code_postal_(BAN)', '')}</td>
                <td>{dpe.get('Nom_commune_(BAN)', '')}</td>
                <td>{dpe.get('Type_bâtiment', '')}</td>
                <td>{dpe.get('Surface_habitable_logement', '')} m²</td>
                <td><strong>{dpe.get('Etiquette_DPE', '')}</strong></td>
            </tr>
            """
        
        corps += "</table><p>🤖 Généré automatiquement par Axi V19</p>"
        
        envoyer_email(
            f"🏠 Veille DPE V19 - {len(nouveaux_dpe)} nouveaux ({datetime.now().strftime('%d/%m')})",
            corps
        )
    
    return {
        "status": "success",
        "nouveaux": len(nouveaux_dpe),
        "total_connus": len(_dpe_connus),
        "version": "V19"
    }


# =============================================================================
# VEILLE CONCURRENCE
# =============================================================================

# Stockage en mémoire
_urls_connues = set()

def run_veille_concurrence(db=None):
    """Exécute la veille concurrence quotidienne."""
    global _urls_connues
    
    logger.info(f"[VEILLE CONCURRENCE] Démarrage - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    scraper = ScraperEngineV19()
    resultats = scraper.scrape_all()
    
    nouvelles_urls = []
    for agence, urls in resultats.items():
        for url in urls:
            if url not in _urls_connues:
                _urls_connues.add(url)
                nouvelles_urls.append({'agence': agence, 'url': url})
    
    logger.info(f"[CONCURRENCE] Terminé: {len(nouvelles_urls)} nouvelles annonces")
    
    # Envoyer email si nouvelles annonces
    if nouvelles_urls:
        corps = f"""
        <h2>🔍 Veille Concurrence V19 - {len(nouvelles_urls)} nouvelles annonces</h2>
        <p>Date: {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
        <p><em>Généré par Axi V19 - {len(SCRAPERS_CONFIG)} agences surveillées</em></p>
        
        <h3>📊 Résumé par agence</h3>
        <table border="1" cellpadding="5" style="border-collapse: collapse;">
            <tr style="background-color: #2196F3; color: white;">
                <th>Agence</th>
                <th>Nouvelles</th>
            </tr>
        """
        
        # Compter par agence
        par_agence = {}
        for item in nouvelles_urls:
            agence = item['agence']
            par_agence[agence] = par_agence.get(agence, 0) + 1
        
        for agence, count in sorted(par_agence.items(), key=lambda x: -x[1]):
            corps += f"<tr><td>{agence}</td><td><strong>{count}</strong></td></tr>"
        
        corps += "</table>"
        
        # Détail (max 30)
        corps += "<h3>📋 Détail (30 premières)</h3><ul>"
        for item in nouvelles_urls[:30]:
            corps += f"<li><strong>{item['agence']}</strong>: <a href='{item['url']}'>{item['url'][:60]}...</a></li>"
        corps += "</ul>"
        
        corps += "<p>🤖 Généré automatiquement par Axi V19</p>"
        
        envoyer_email(
            f"🔍 Veille Concurrence V19 - {len(nouvelles_urls)} nouvelles ({datetime.now().strftime('%d/%m')})",
            corps
        )
    
    return {
        "status": "success",
        "nouvelles": len(nouvelles_urls),
        "total_urls": scraper.stats['total_urls'],
        "par_agence": scraper.stats['par_agence'],
        "version": "V19"
    }


# =============================================================================
# REGISTRATION
# =============================================================================

def register_veille_routes(server):
    """Enregistre les routes de veille sur le serveur."""
    
    def handle_run_veille(query):
        return run_veille_dpe()
    
    def handle_test_veille(query):
        # Test sans email
        global _dpe_connus
        count = 0
        for cp in CODES_POSTAUX[:2]:  # Juste 2 CP
            resultats = get_dpe_ademe(cp)
            count += len(resultats)
        return {"status": "test", "dpe_trouvés": count, "codes_testés": 2, "version": "V19"}
    
    def handle_run_veille_concurrence(query):
        return run_veille_concurrence()
    
    def handle_test_veille_concurrence(query):
        # Test sur 2 agences
        scraper = ScraperEngineV19()
        agences_test = list(SCRAPERS_CONFIG.keys())[:2]
        total = 0
        for agence in agences_test:
            urls = scraper.scrape_agence(agence)
            total += len(urls)
        return {"status": "test", "agences_testées": agences_test, "urls_trouvées": total, "version": "V19"}
    
    server.register_route('GET', '/run-veille', handle_run_veille)
    server.register_route('GET', '/test-veille', handle_test_veille)
    server.register_route('GET', '/run-veille-concurrence', handle_run_veille_concurrence)
    server.register_route('GET', '/test-veille-concurrence', handle_test_veille_concurrence)
    
    logger.info("📍 Routes veille V19 enregistrées (DPE + Concurrence)")
