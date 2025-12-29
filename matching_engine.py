"""
MATCHING ENGINE V14.8 MATCHING GARANTI - ICI DORDOGNE
===============================================
Module séparé pour le matching Bien/Propriétaire
- PostgreSQL cache (biens_cache)
- Fusion Trello + Site Web
- Labels vert/rouge pour Julie
- Zero Touch automation

VALIDÉ PAR LUMO - 28/12/2025
"""

import os
import re
import json
import urllib.request
import urllib.parse
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

TRELLO_KEY = os.environ.get("TRELLO_KEY", "")
TRELLO_TOKEN = os.environ.get("TRELLO_TOKEN", "")

BOARD_BIENS = "6249623e53c07a131c916e59"
BOARD_TEST = "66d81b60de75f67fb3bb4624"
LIST_TEST_ACQUEREURS = "694f52e6238e9746b814cae9"
JULIE_ID = "59db340040eb2c01fb7d4851"

SITE_URL = "https://www.icidordogne.fr"

# PostgreSQL via variable d'environnement Railway
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# ============================================================================
# CONFIGURATION EMAIL HOOK
# ============================================================================

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
SMTP_EMAIL = "u5050786429@gmail.com"
SMTP_PASSWORD = "izemquwmmqjdasrk"
EMAIL_FROM_NAME = "Ici Dordogne"
EMAIL_REPLY_TO = "agence@icidordogne.fr"

# URL de base du chatbot Railway
CHATBOT_BASE_URL = "https://baby-axys-production.up.railway.app/chat/card"


def send_hook_email(prospect_email, prospect_prenom, score, card_url, bien_info=None):
    """
    Envoie l'email d'engagement au prospect après création de la carte Trello.
    
    SCÉNARIO A (score >= 90) : "Bonne nouvelle, j'ai trouvé votre bien"
    SCÉNARIO B (score < 90) : "J'ai reçu votre demande, plusieurs biens correspondent"
    
    Sécurisé : si l'envoi échoue, le script ne plante pas.
    """
    
    if not prospect_email:
        print("[HOOK EMAIL] Pas d'email prospect, envoi ignoré")
        return False, "Pas d'email"
    
    try:
        # Générer l'URL du chatbot avec l'ID de la carte (shortlink Trello)
        # card_url format: https://trello.com/c/SHORTID
        card_id = card_url.split("/c/")[-1] if card_url and "/c/" in card_url else ""
        chat_url = f"{CHATBOT_BASE_URL}/{card_id}"
        
        # Construire le message selon le scénario
        if score >= 90:
            # SCÉNARIO A : Match certain
            sujet = "🏠 Bonne nouvelle pour votre recherche immobilière"
            
            prix_info = ""
            if bien_info and bien_info.get("prix"):
                prix_info = f" à {bien_info['prix']}€"
            
            corps_html = f"""
            <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <h2 style="color: #2e7d32;">Bonjour {prospect_prenom},</h2>
                
                <p>Excellente nouvelle ! J'ai identifié <strong>le bien qui correspond à votre demande</strong>{prix_info}.</p>
                
                <p>Ce bien est actuellement disponible et je peux vous organiser une visite très rapidement.</p>
                
                <p style="margin: 25px 0;">
                    <a href="{chat_url}" style="background-color: #2e7d32; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                        📸 Voir les photos et organiser la visite
                    </a>
                </p>
                
                <p>À très bientôt,</p>
                <p><strong>L'équipe Ici Dordogne</strong><br>
                <a href="mailto:agence@icidordogne.fr">agence@icidordogne.fr</a></p>
            </body>
            </html>
            """
        else:
            # SCÉNARIO B : Match incertain, besoin d'affiner
            sujet = "🏡 J'ai reçu votre demande - Discutons de votre projet"
            
            prix_mention = ""
            if bien_info and bien_info.get("prix"):
                prix_mention = f", dont un à {bien_info['prix']}€"
            
            corps_html = f"""
            <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <h2 style="color: #1976d2;">Bonjour {prospect_prenom},</h2>
                
                <p>J'ai bien reçu votre demande et je vous en remercie !</p>
                
                <p>J'ai <strong>plusieurs biens{prix_mention}</strong> qui pourraient correspondre à vos critères.</p>
                
                <p>Pour vous proposer les meilleures options, j'aurais besoin d'échanger rapidement avec vous pour affiner votre recherche.</p>
                
                <p style="margin: 25px 0;">
                    <a href="{chat_url}" style="background-color: #1976d2; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                        💬 Discutons de votre projet
                    </a>
                </p>
                
                <p>À très bientôt,</p>
                <p><strong>L'équipe Ici Dordogne</strong><br>
                <a href="mailto:agence@icidordogne.fr">agence@icidordogne.fr</a></p>
            </body>
            </html>
            """
        
        # Construire l'email
        msg = MIMEMultipart("alternative")
        msg["Subject"] = sujet
        msg["From"] = f"{EMAIL_FROM_NAME} <{SMTP_EMAIL}>"
        msg["To"] = prospect_email
        msg["Reply-To"] = EMAIL_REPLY_TO
        
        msg.attach(MIMEText(corps_html, "html"))
        
        # Envoyer via SMTP SSL
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, prospect_email, msg.as_string())
        
        scenario = "A (QUALIFIÉ)" if score >= 90 else "B (À AFFINER)"
        print(f"[HOOK EMAIL] ✅ Envoyé à {prospect_email} - Scénario {scenario}")
        return True, None
        
    except Exception as e:
        print(f"[HOOK EMAIL] ❌ Erreur envoi à {prospect_email}: {e}")
        return False, str(e)

# ============================================================================
# DICTIONNAIRE SYNONYMES COMMUNES DORDOGNE
# ============================================================================

SYNONYMES_COMMUNES = {
    # Bassillac et Auberoche (fusion 2017)
    "saint-antoine-d'auberoche": "bassillac et auberoche",
    "saint-antoine d'auberoche": "bassillac et auberoche",
    "st-antoine-d'auberoche": "bassillac et auberoche",
    "st antoine d'auberoche": "bassillac et auberoche",
    "st antoine": "bassillac et auberoche",
    "bassillac": "bassillac et auberoche",
    "blis-et-born": "bassillac et auberoche",
    "blis et born": "bassillac et auberoche",
    "le change": "bassillac et auberoche",
    "eyliac": "bassillac et auberoche",
    "milhac-d'auberoche": "bassillac et auberoche",
    "milhac d'auberoche": "bassillac et auberoche",
    
    # Val de Louyre et Caudeau (fusion 2016)
    "saint-alvère": "val de louyre et caudeau",
    "st-alvère": "val de louyre et caudeau",
    "cendrieux": "val de louyre et caudeau",
    "sainte-foy-de-longas": "val de louyre et caudeau",
    
    # Pays de Belvès (fusion 2019)
    "belvès": "pays de belvès",
    "belves": "pays de belvès",
    "monplaisant": "pays de belvès",
    "sagelat": "pays de belvès",
    "saint-amand-de-belvès": "pays de belvès",
    
    # Saint-Mayme variantes
    "saint-mayme-de-péreyrol": "saint-mayme-de-pereyrol",
    "st-mayme-de-péreyrol": "saint-mayme-de-pereyrol",
    "saint mayme": "saint-mayme-de-pereyrol",
    "st mayme": "saint-mayme-de-pereyrol",
    
    # Saint-Amand-de-Vergt variantes
    "saint-amand-de-vergt": "saint-amand-de-vergt",
    "st-amand-de-vergt": "saint-amand-de-vergt",
    "st amand de vergt": "saint-amand-de-vergt",
    
    # Le Bugue variantes
    "le-bugue": "le bugue",
    "lebugue": "le bugue",
    
    # Périgueux et environs
    "boulazac": "boulazac isle manoire",
    "boulazac-isle-manoire": "boulazac isle manoire",
    "trélissac": "trelissac",
    "coulounieix-chamiers": "coulounieix chamiers",
    
    # Trémolat
    "trémolat": "tremolat",
}

def normaliser_commune(commune):
    """Normalise une commune avec le dictionnaire de synonymes"""
    if not commune:
        return ""
    commune_lower = commune.lower().strip()
    commune_lower = re.sub(r'[^a-zàâäéèêëïîôùûüç\s\-\']', '', commune_lower)
    return SYNONYMES_COMMUNES.get(commune_lower, commune_lower)

# ============================================================================
# HELPERS HTTP (sans requests - stdlib only)
# ============================================================================

def http_get(url, params=None):
    """GET request avec urllib"""
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f"[HTTP] Erreur GET {url}: {e}")
        return None

def http_post(url, params=None, data=None):
    """POST request avec urllib"""
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, method='POST')
    if data:
        req.data = json.dumps(data).encode('utf-8')
        req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f"[HTTP] Erreur POST {url}: {e}")
        return None

def trello_get(endpoint, params=None):
    """GET Trello API"""
    url = f"https://api.trello.com/1{endpoint}"
    if params is None:
        params = {}
    params["key"] = TRELLO_KEY
    params["token"] = TRELLO_TOKEN
    return http_get(url, params)

def trello_post(endpoint, params=None):
    """POST Trello API"""
    url = f"https://api.trello.com/1{endpoint}"
    if params is None:
        params = {}
    params["key"] = TRELLO_KEY
    params["token"] = TRELLO_TOKEN
    return http_post(url, params)

def trello_put(endpoint, params=None):
    """PUT Trello API pour mise à jour"""
    url = f"https://api.trello.com/1{endpoint}"
    if params is None:
        params = {}
    params["key"] = TRELLO_KEY
    params["token"] = TRELLO_TOKEN
    # PUT request
    url_with_params = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url_with_params, method='PUT')
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f"[TRELLO PUT] Erreur {url}: {e}")
        return None

# ============================================================================
# BASE DE DONNÉES POSTGRESQL
# ============================================================================

def get_db_connection():
    """Connexion PostgreSQL"""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    except Exception as e:
        print(f"[DB] Erreur connexion: {e}")
        return None

def init_database():
    """Crée les tables si elles n'existent pas"""
    conn = get_db_connection()
    if not conn:
        print("[DB] Pas de connexion - tables non créées")
        return False
    
    cur = conn.cursor()
    
    # Table cache des biens
    cur.execute("""
        CREATE TABLE IF NOT EXISTS biens_cache (
            id SERIAL PRIMARY KEY,
            trello_id VARCHAR(50) UNIQUE NOT NULL,
            trello_url VARCHAR(200),
            proprietaire VARCHAR(200),
            description TEXT,
            refs_trouvees TEXT[],
            prix INTEGER,
            surface INTEGER,
            commune VARCHAR(100),
            commune_normalisee VARCHAR(100),
            mots_cles TEXT[],
            attachments_names TEXT[],
            site_url VARCHAR(300),
            site_prix INTEGER,
            site_surface INTEGER,
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    
    # Index pour recherche rapide
    cur.execute("CREATE INDEX IF NOT EXISTS idx_biens_prix ON biens_cache(prix)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_biens_commune ON biens_cache(commune_normalisee)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_biens_refs ON biens_cache USING GIN(refs_trouvees)")
    
    # Table historique des matchings
    cur.execute("""
        CREATE TABLE IF NOT EXISTS matching_history (
            id SERIAL PRIMARY KEY,
            prospect_nom VARCHAR(100),
            prospect_email VARCHAR(200),
            criteres JSONB,
            bien_matched_id INTEGER REFERENCES biens_cache(id),
            score INTEGER,
            confidence VARCHAR(20),
            needs_verification BOOLEAN,
            card_created_url VARCHAR(200),
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    
    conn.commit()
    cur.close()
    conn.close()
    print("[DB] Tables initialisées OK")
    return True

# ============================================================================
# SYNC TRELLO → PostgreSQL
# ============================================================================

def extraire_donnees_carte(card):
    """Extrait et structure les données d'une carte Trello"""
    desc = card.get("desc", "")
    name = card.get("name", "")
    
    # Extraire REF du titre et description
    refs = []
    refs.extend(re.findall(r'\b(4\d{4}|3\d{4})\b', name))
    refs.extend(re.findall(r'\b(4\d{4}|3\d{4})\b', desc))
    
    # Extraire REF des noms de pièces jointes + chercher site_url
    attachments_names = []
    site_url = None
    
    # Méthode 1: Chercher dans les attachments
    for att in card.get("attachments", []):
        filename = att.get("name", "")
        att_url = att.get("url", "")
        
        attachments_names.append(filename)
        refs.extend(re.findall(r'\b(4\d{4}|3\d{4})\b', filename))
        
        # Chercher lien icidordogne.fr dans les attachments
        if not site_url and 'icidordogne.fr' in att_url:
            site_url = att_url
            print(f"[SYNC] Site URL trouvé (attachment): {site_url}")
    
    # Méthode 2: Chercher dans la description (pattern "Lien site : https://...")
    if not site_url:
        site_match = re.search(r'(?:Lien site|Site)\s*:\s*\[?(https?://[^\s\]]+icidordogne\.fr[^\s\]]*)', desc, re.IGNORECASE)
        if site_match:
            site_url = site_match.group(1).strip()
            print(f"[SYNC] Site URL trouvé (description pattern 1): {site_url}")
    
    # Méthode 3: Chercher N'IMPORTE QUEL lien icidordogne.fr (Markdown ou texte brut)
    # RÈGLE D'OR V14.8: Un prospect qui contacte = bien FORCÉMENT sur notre site
    if not site_url:
        site_match = re.search(r'https?://(?:www\.)?icidordogne\.fr/[^\s\)\]"<>]*', desc)
        if site_match:
            site_url = site_match.group(0).strip().rstrip(')')
            print(f"[SYNC] Site URL trouvé (format libre): {site_url}")
    
    refs = list(set(refs))
    
    # Extraire prix
    prix = None
    prix_match = re.search(r'(\d{2,3})\s*(\d{3})\s*€', desc)
    if prix_match:
        prix = int(prix_match.group(1) + prix_match.group(2))
    else:
        prix_match = re.search(r'(\d{2,3})\s*k€', desc, re.IGNORECASE)
        if prix_match:
            prix = int(prix_match.group(1)) * 1000
    
    # Extraire surface
    surface = None
    surface_match = re.search(r'(\d{2,3})\s*m[²2]', desc, re.IGNORECASE)
    if surface_match:
        surface = int(surface_match.group(1))
    
    # Extraire commune
    commune_raw = None
    
    # Pattern 1: Code postal + commune
    match = re.search(r'24\d{3}\s+([A-Za-zÀ-ÿ\-\'\s]+?)(?:\n|$|\()', desc)
    if match:
        commune_raw = match.group(1).strip()
    
    # Pattern 2: "ex saint-antoine" dans le texte
    if not commune_raw:
        match = re.search(r'\(ex[:\s]+([^)]+)\)', desc, re.IGNORECASE)
        if match:
            commune_raw = match.group(1).strip()
    
    # Pattern 3: Communes connues
    if not commune_raw:
        communes_connues = ["bassillac", "auberoche", "vergt", "bugue", "tremolat",
                           "saint-mayme", "saint-amand", "boulazac", "périgueux"]
        for c in communes_connues:
            if c in desc.lower():
                commune_raw = c
                break
    
    commune_normalisee = normaliser_commune(commune_raw) if commune_raw else None
    
    # Mots-clés
    mots_cles = []
    mots_check = ["piscine", "grange", "étang", "etang", "vue", "terrain",
                  "garage", "dépendance", "dependance", "plain-pied", "rénovée", "renovee"]
    for mot in mots_check:
        if mot in desc.lower():
            mots_cles.append(mot)
    
    return {
        "trello_id": card["id"],
        "trello_url": card.get("shortUrl", ""),
        "proprietaire": name,
        "description": desc,
        "refs_trouvees": refs,
        "prix": prix,
        "surface": surface,
        "commune": commune_raw,
        "commune_normalisee": commune_normalisee,
        "mots_cles": mots_cles,
        "attachments_names": attachments_names,
        "site_url": site_url
    }

def sync_biens_from_trello():
    """Synchronise les biens Trello vers PostgreSQL"""
    print("[SYNC] Début synchronisation Trello → PostgreSQL")
    
    # Récupérer toutes les cartes du board BIENS
    cards = trello_get(f"/boards/{BOARD_BIENS}/cards", {
        "fields": "name,desc,shortUrl,idList",
        "attachments": "true"
    })
    
    if not cards:
        print("[SYNC] Erreur récupération Trello")
        return 0
    
    conn = get_db_connection()
    if not conn:
        print("[SYNC] Pas de connexion DB")
        return 0
    
    cur = conn.cursor()
    count = 0
    
    for card in cards:
        bien = extraire_donnees_carte(card)
        
        # Upsert dans PostgreSQL
        cur.execute("""
            INSERT INTO biens_cache (
                trello_id, trello_url, proprietaire, description,
                refs_trouvees, prix, surface, commune, commune_normalisee,
                mots_cles, attachments_names, site_url, updated_at
            ) VALUES (
                %(trello_id)s, %(trello_url)s, %(proprietaire)s, %(description)s,
                %(refs_trouvees)s, %(prix)s, %(surface)s, %(commune)s, %(commune_normalisee)s,
                %(mots_cles)s, %(attachments_names)s, %(site_url)s, NOW()
            )
            ON CONFLICT (trello_id) DO UPDATE SET
                trello_url = EXCLUDED.trello_url,
                proprietaire = EXCLUDED.proprietaire,
                description = EXCLUDED.description,
                refs_trouvees = EXCLUDED.refs_trouvees,
                prix = EXCLUDED.prix,
                surface = EXCLUDED.surface,
                commune = EXCLUDED.commune,
                commune_normalisee = EXCLUDED.commune_normalisee,
                mots_cles = EXCLUDED.mots_cles,
                attachments_names = EXCLUDED.attachments_names,
                site_url = EXCLUDED.site_url,
                updated_at = NOW()
        """, bien)
        count += 1
    
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"[SYNC] {count} biens synchronisés depuis Trello")
    return count

# ============================================================================
# SYNC SITE WEB → PostgreSQL (enrichissement)
# ============================================================================

def sync_biens_from_site():
    """Scrape le site icidordogne.fr et enrichit la DB"""
    print("[SYNC] Début scraping site web")
    
    try:
        req = urllib.request.Request(f"{SITE_URL}/immobilier/")
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8')
        
        # Trouver toutes les REF sur la page
        refs_found = re.findall(r'REF[.\s:]*(\d{5})', html)
        refs_found = list(set(refs_found))
        
        print(f"[SYNC] {len(refs_found)} REF trouvées sur le site")
        
        conn = get_db_connection()
        if not conn:
            return 0
        
        cur = conn.cursor()
        count = 0
        
        for ref in refs_found:
            # Extraire prix et surface si visible
            # Pattern: "239 000 €" ou "Surface : 91m²"
            prix_match = re.search(rf'{ref}.*?(\d{{2,3}})\s*(\d{{3}})\s*€', html, re.DOTALL)
            surface_match = re.search(rf'{ref}.*?Surface[:\s]*(\d{{2,3}})\s*m', html, re.DOTALL)
            
            prix = int(prix_match.group(1) + prix_match.group(2)) if prix_match else None
            surface = int(surface_match.group(1)) if surface_match else None
            
            if prix or surface:
                cur.execute("""
                    UPDATE biens_cache 
                    SET site_prix = COALESCE(%s, site_prix),
                        site_surface = COALESCE(%s, site_surface),
                        prix = COALESCE(%s, prix),
                        surface = COALESCE(%s, surface),
                        site_url = %s,
                        updated_at = NOW()
                    WHERE %s = ANY(refs_trouvees)
                """, (prix, surface, prix, surface, f"{SITE_URL}/immobilier/?fwp_ref={ref}", ref))
                
                if cur.rowcount > 0:
                    count += 1
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"[SYNC] {count} biens enrichis depuis le site")
        return count
        
    except Exception as e:
        print(f"[SYNC] Erreur scraping: {e}")
        return 0

def run_sync_cron():
    """Synchronisation complète (CRON horaire)"""
    print(f"[CRON] Sync démarrée à {datetime.now()}")
    
    count_trello = sync_biens_from_trello()
    count_site = sync_biens_from_site()
    
    print(f"[CRON] Terminé: {count_trello} Trello, {count_site} enrichis site")
    
    return {
        "trello": count_trello,
        "site": count_site,
        "timestamp": datetime.now().isoformat()
    }

# ============================================================================
# LABELS TRELLO
# ============================================================================

def get_or_create_labels(board_id):
    """Récupère ou crée les labels QUALIFIÉ (vert) et À VÉRIFIER (rouge)"""
    labels = trello_get(f"/boards/{board_id}/labels")
    
    label_vert = None
    label_rouge = None
    
    if labels:
        for label in labels:
            if label.get("name") == "QUALIFIÉ" and label.get("color") == "green":
                label_vert = label["id"]
            elif "VÉRIFIER" in label.get("name", "") and label.get("color") == "red":
                label_rouge = label["id"]
    
    # Créer les labels manquants
    if not label_vert:
        result = trello_post(f"/boards/{board_id}/labels", {
            "name": "QUALIFIÉ", "color": "green"
        })
        if result:
            label_vert = result.get("id")
            print(f"[LABELS] Label QUALIFIÉ créé: {label_vert}")
    
    if not label_rouge:
        result = trello_post(f"/boards/{board_id}/labels", {
            "name": "⚠️ A VÉRIFIER", "color": "red"
        })
        if result:
            label_rouge = result.get("id")
            print(f"[LABELS] Label À VÉRIFIER créé: {label_rouge}")
    
    return {"qualifie": label_vert, "a_verifier": label_rouge}

# ============================================================================
# ALGORITHME DE SCORING
# ============================================================================

def find_best_match(criteres):
    """
    Trouve le meilleur match depuis PostgreSQL
    
    Golden Tickets (1000 pts):
    - REF exacte trouvée
    - Prix unique dans le stock (±5%)
    
    Scoring:
    - Prix ±8% = 40 pts
    - Surface ±15% = 30 pts
    - Commune (normalisée) = 30 pts
    - Mots-clés = 10 pts/mot
    """
    conn = get_db_connection()
    if not conn:
        print("[MATCH] Pas de connexion DB - fallback Trello direct")
        return find_best_match_fallback(criteres)
    
    cur = conn.cursor()
    
    ref_prospect = criteres.get("ref")
    prix_prospect = criteres.get("prix")
    surface_prospect = criteres.get("surface")
    commune_prospect = normaliser_commune(criteres.get("commune", ""))
    mots_cles_prospect = criteres.get("mots_cles", [])
    
    # ===== GOLDEN TICKET 1: REF EXACTE =====
    if ref_prospect:
        cur.execute("""
            SELECT * FROM biens_cache 
            WHERE %s = ANY(refs_trouvees)
            LIMIT 1
        """, (ref_prospect,))
        
        row = cur.fetchone()
        if row:
            cur.close()
            conn.close()
            return {
                "match_found": True,
                "score": 1000,
                "confidence": "HIGH",
                "bien": dict(row),
                "details": ["🎫 GOLDEN TICKET: REF exacte trouvée"],
                "needs_verification": False
            }
    
    # ===== GOLDEN TICKET 2: PRIX UNIQUE =====
    if prix_prospect:
        prix_min = int(prix_prospect * 0.95)
        prix_max = int(prix_prospect * 1.05)
        
        cur.execute("""
            SELECT * FROM biens_cache 
            WHERE prix BETWEEN %s AND %s
        """, (prix_min, prix_max))
        
        rows = cur.fetchall()
        if len(rows) == 1:
            cur.close()
            conn.close()
            return {
                "match_found": True,
                "score": 1000,
                "confidence": "HIGH",
                "bien": dict(rows[0]),
                "details": ["🎫 GOLDEN TICKET: Prix unique dans le stock"],
                "needs_verification": False
            }
    
    # ===== SCORING PONDÉRÉ =====
    cur.execute("SELECT * FROM biens_cache")
    all_biens = cur.fetchall()
    cur.close()
    conn.close()
    
    best_match = None
    best_score = 0
    best_details = []
    
    for row in all_biens:
        bien = dict(row)
        score = 0
        details = []
        
        # Prix ±8%
        if prix_prospect and bien.get("prix"):
            ecart = abs(bien["prix"] - prix_prospect) / prix_prospect
            if ecart <= 0.08:
                score += 40
                details.append(f"Prix OK: {bien['prix']}€ (écart {ecart*100:.1f}%)")
            elif ecart <= 0.15:
                score += 20
                details.append(f"Prix proche: {bien['prix']}€")
        
        # Surface ±15%
        if surface_prospect and bien.get("surface"):
            ecart = abs(bien["surface"] - surface_prospect) / surface_prospect
            if ecart <= 0.15:
                score += 30
                details.append(f"Surface OK: {bien['surface']}m²")
            elif ecart <= 0.25:
                score += 15
                details.append(f"Surface proche: {bien['surface']}m²")
        
        # Commune (normalisée)
        if commune_prospect and bien.get("commune_normalisee"):
            if bien["commune_normalisee"] == commune_prospect:
                score += 30
                details.append(f"Commune OK: {bien.get('commune', '')}")
            elif commune_prospect in (bien.get("description") or "").lower():
                score += 25
                details.append("Commune dans description")
        
        # Mots-clés
        mots_bien = bien.get("mots_cles") or []
        for mot in mots_cles_prospect:
            if mot.lower() in [m.lower() for m in mots_bien]:
                score += 10
                details.append(f"Mot-clé: {mot}")
        
        if score > best_score:
            best_score = score
            best_match = bien
            best_details = details
    
    if best_match:
        if best_score >= 90:
            confidence = "HIGH"
            needs_verification = False
        elif best_score >= 60:
            confidence = "MEDIUM"
            needs_verification = True
        else:
            confidence = "LOW"
            needs_verification = True
        
        return {
            "match_found": True,
            "score": best_score,
            "confidence": confidence,
            "bien": best_match,
            "details": best_details,
            "needs_verification": needs_verification
        }
    
    return {
        "match_found": False,
        "score": 0,
        "confidence": "NONE",
        "bien": None,
        "details": ["Aucun match trouvé"],
        "needs_verification": True
    }

def find_best_match_fallback(criteres):
    """Fallback si pas de DB: recherche directe Trello"""
    print("[MATCH] Mode fallback - recherche Trello directe")
    
    cards = trello_get(f"/boards/{BOARD_BIENS}/cards", {
        "fields": "name,desc,shortUrl",
        "attachments": "true"
    })
    
    if not cards:
        return {
            "match_found": False,
            "score": 0,
            "confidence": "NONE",
            "bien": None,
            "details": ["Erreur Trello"],
            "needs_verification": True
        }
    
    ref_prospect = criteres.get("ref")
    prix_prospect = criteres.get("prix")
    surface_prospect = criteres.get("surface")
    commune_prospect = normaliser_commune(criteres.get("commune", ""))
    mots_cles_prospect = criteres.get("mots_cles", [])
    
    best_match = None
    best_score = 0
    best_details = []
    
    for card in cards:
        bien = extraire_donnees_carte(card)
        score = 0
        details = []
        
        # Golden Ticket REF
        if ref_prospect and ref_prospect in bien.get("refs_trouvees", []):
            return {
                "match_found": True,
                "score": 1000,
                "confidence": "HIGH",
                "bien": bien,
                "details": ["🎫 GOLDEN TICKET: REF exacte trouvée"],
                "needs_verification": False
            }
        
        # Prix
        if prix_prospect and bien.get("prix"):
            ecart = abs(bien["prix"] - prix_prospect) / prix_prospect
            if ecart <= 0.08:
                score += 40
                details.append(f"Prix OK: {bien['prix']}€")
            elif ecart <= 0.15:
                score += 20
        
        # Surface
        if surface_prospect and bien.get("surface"):
            ecart = abs(bien["surface"] - surface_prospect) / surface_prospect
            if ecart <= 0.15:
                score += 30
                details.append(f"Surface OK: {bien['surface']}m²")
        
        # Commune
        if commune_prospect and bien.get("commune_normalisee") == commune_prospect:
            score += 30
            details.append(f"Commune OK")
        
        # Mots-clés
        for mot in mots_cles_prospect:
            if mot in bien.get("mots_cles", []):
                score += 10
        
        if score > best_score:
            best_score = score
            best_match = bien
            best_details = details
    
    if best_match:
        return {
            "match_found": True,
            "score": best_score,
            "confidence": "HIGH" if best_score >= 90 else "MEDIUM" if best_score >= 60 else "LOW",
            "bien": best_match,
            "details": best_details,
            "needs_verification": best_score < 90
        }
    
    return {
        "match_found": False,
        "score": 0,
        "confidence": "NONE",
        "bien": None,
        "details": ["Aucun match trouvé"],
        "needs_verification": True
    }

# ============================================================================
# CRÉATION CARTE ACQUÉREUR
# ============================================================================

def creer_carte_acquereur(prospect, match_result, message_original):
    """
    Crée une carte acquéreur complète avec:
    - Infos structurées
    - Lien vers le bien
    - Message original
    - Label VERT ou ROUGE
    """
    
    nom = prospect.get("nom", "INCONNU")
    prenom = prospect.get("prenom", "")
    tel = prospect.get("tel", "")
    email = prospect.get("email", "")
    
    # Description structurée
    desc_parts = [
        f"Situation d'achat : {prospect.get('situation', 'À déterminer')}",
        f"Tél : {tel}",
        f"Email : {email}",
        f"Source : {prospect.get('source', 'Leboncoin')}",
        f"Références : {prospect.get('ref_bien', 'Non spécifiée')}",
        f"Origine : {prospect.get('origine', '')}",
        "",
        "Informations complémentaires :",
        prospect.get("infos", ""),
        ""
    ]
    
    # Bloc matching
    if match_result["match_found"]:
        bien = match_result["bien"]
        desc_parts.extend([
            "🏠 BIEN IDENTIFIÉ",
            f"- Propriétaire : {bien.get('proprietaire', 'N/A')}",
            f"- Trello BIENS : {bien.get('trello_url', 'N/A')}",
            f"- Score matching : {match_result['score']} ({match_result['confidence']})",
            ""
        ])
        
        if match_result["needs_verification"]:
            desc_parts.extend([
                "⚠️ JULIE, VÉRIFIE CE MATCH ⚠️",
                f"Raisons : Score {match_result['score']} < 90",
                f"Détails : {', '.join(match_result['details'])}",
                ""
            ])
    else:
        desc_parts.extend([
            "❌ BIEN NON IDENTIFIÉ",
            "Julie, cherche manuellement le bien correspondant.",
            ""
        ])
    
    # Message original (OBLIGATOIRE)
    desc_parts.extend([
        "--- MESSAGE ORIGINAL ---",
        message_original,
        "--- FIN MESSAGE ---"
    ])
    
    description = "\n".join(desc_parts)
    card_name = f"{nom.upper()} {prenom}"
    
    # Créer la carte
    result = trello_post("/cards", {
        "idList": LIST_TEST_ACQUEREURS,
        "name": card_name,
        "desc": description
    })
    
    if not result:
        return {"success": False, "error": "Erreur création carte"}
    
    card_id = result["id"]
    card_url = result.get("shortUrl", "")
    
    # FORCE UPDATE de la description (contournement du template Trello)
    trello_put(f"/cards/{card_id}", {"desc": description})
    print(f"[TRELLO] Carte créée: {card_url} - Description forcée")
    
    # Ajouter Julie comme membre
    trello_post(f"/cards/{card_id}/idMembers", {"value": JULIE_ID})
    
    # Ajouter les checklists
    for checklist_name, items in [
        ("Avant la visite", [
            "RDV validé avec l'acquéreur",
            "RDV validé avec le propriétaire",
            "RDV dans Sweep",
            "Bon de visite envoyé",
            "Bon de visite signé reçu"
        ]),
        ("Après la visite", [
            "CR Proprio",
            "CR Trello",
            "Autres biens à proposer"
        ])
    ]:
        cl = trello_post("/checklists", {"idCard": card_id, "name": checklist_name})
        if cl:
            for item in items:
                trello_post(f"/checklists/{cl['id']}/checkItems", {"name": item})
    
    # ===== LABELS : VERT ou ROUGE =====
    labels = get_or_create_labels(BOARD_TEST)
    
    if match_result["match_found"] and not match_result["needs_verification"]:
        if labels.get("qualifie"):
            trello_post(f"/cards/{card_id}/idLabels", {"value": labels["qualifie"]})
            print(f"[LABEL] Carte {card_id} → QUALIFIÉ (vert)")
    else:
        if labels.get("a_verifier"):
            trello_post(f"/cards/{card_id}/idLabels", {"value": labels["a_verifier"]})
            print(f"[LABEL] Carte {card_id} → À VÉRIFIER (rouge)")
    
    return {
        "success": True,
        "card_id": card_id,
        "card_url": card_url,
        "match_score": match_result["score"],
        "confidence": match_result["confidence"],
        "needs_verification": match_result["needs_verification"]
    }

# ============================================================================
# ENDPOINT PRINCIPAL
# ============================================================================

def process_prospect(data):
    """
    Point d'entrée principal pour traiter un prospect
    
    Input: {nom, prenom, tel, email, ref_bien, prix, surface, commune, message_original, mots_cles}
    Output: {success, card_url, match, needs_verification}
    """
    
    criteres = {
        "ref": data.get("ref_bien"),
        "prix": data.get("prix"),
        "surface": data.get("surface"),
        "commune": data.get("commune"),
        "mots_cles": data.get("mots_cles", [])
    }
    
    # Matching
    match_result = find_best_match(criteres)
    
    # Créer la carte
    result = creer_carte_acquereur(
        prospect=data,
        match_result=match_result,
        message_original=data.get("message_original", "")
    )
    
    result["match"] = match_result
    
    # Enregistrer dans l'historique
    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO matching_history 
                (prospect_nom, prospect_email, criteres, score, confidence, needs_verification, card_created_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                data.get("nom"),
                data.get("email"),
                json.dumps(criteres),
                match_result["score"],
                match_result["confidence"],
                match_result["needs_verification"],
                result.get("card_url")
            ))
            conn.commit()
            cur.close()
            conn.close()
    except Exception as e:
        print(f"[HISTORY] Erreur: {e}")
    
    # ===== ENVOI EMAIL HOOK AU PROSPECT =====
    if result.get("success") and data.get("email"):
        bien_info = None
        if match_result.get("bien"):
            bien_info = {
                "prix": match_result["bien"].get("prix"),
                "commune": match_result["bien"].get("commune")
            }
        
        email_ok, email_err = send_hook_email(
            prospect_email=data.get("email"),
            prospect_prenom=data.get("prenom", ""),
            score=match_result["score"],
            card_url=result.get("card_url", ""),
            bien_info=bien_info
        )
        
        result["hook_email_sent"] = email_ok
        if email_err:
            result["hook_email_error"] = email_err
    
    return result


# ============================================================================
# EXPORT
# ============================================================================

__all__ = [
    'init_database',
    'run_sync_cron',
    'sync_biens_from_trello',
    'sync_biens_from_site',
    'find_best_match',
    'process_prospect',
    'creer_carte_acquereur',
    'get_or_create_labels',
    'normaliser_commune',
    'send_hook_email',
    'SYNONYMES_COMMUNES'
]
