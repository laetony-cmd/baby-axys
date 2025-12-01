import anthropic
import os
import urllib.request
import urllib.parse
import json
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# === FONCTIONS FICHIERS ===

def lire_fichier(chemin):
    try:
        with open(chemin, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return ""

def ecrire_fichier(chemin, contenu):
    with open(chemin, 'w', encoding='utf-8') as f:
        f.write(contenu)

def ajouter_fichier(chemin, contenu):
    with open(chemin, 'a', encoding='utf-8') as f:
        f.write(contenu)

# === FONCTION EMAIL ===

def envoyer_email(destinataire, sujet, corps, piece_jointe=None):
    """Envoie un email via Gmail"""
    try:
        gmail_user = os.environ.get("GMAIL_USER")
        gmail_password = os.environ.get("GMAIL_APP_PASSWORD")
        
        if not gmail_user or not gmail_password:
            return "Erreur: Configuration email manquante"
        
        msg = MIMEMultipart()
        msg['From'] = gmail_user
        msg['To'] = destinataire
        msg['Subject'] = sujet
        
        msg.attach(MIMEText(corps, 'plain', 'utf-8'))
        
        if piece_jointe and os.path.exists(piece_jointe):
            with open(piece_jointe, 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(piece_jointe)}"')
                msg.attach(part)
        
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(gmail_user, gmail_password)
        server.sendmail(gmail_user, destinataire, msg.as_string())
        server.quit()
        
        return "Email envoye avec succes"
    except Exception as e:
        return f"Erreur envoi email: {e}"

# === FONCTION RECHERCHE WEB ===

def recherche_web(requete):
    """Recherche sur le web via DuckDuckGo API"""
    try:
        url = "https://api.duckduckgo.com/?q=" + urllib.parse.quote(requete) + "&format=json&no_html=1"
        req = urllib.request.Request(url, headers={'User-Agent': 'Axi/1.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            resultats = []
            
            if data.get("AbstractText"):
                source = data.get("AbstractSource", "Source")
                resultats.append(f"[{source}] {data['AbstractText']}")
            
            if data.get("Answer"):
                resultats.append(f"[Reponse directe] {data['Answer']}")
            
            for topic in data.get("RelatedTopics", [])[:5]:
                if isinstance(topic, dict) and topic.get("Text"):
                    resultats.append(f"- {topic['Text']}")
            
            return "\n\n".join(resultats) if resultats else None
    except Exception as e:
        print(f"Erreur recherche: {e}")
        return None

def recherche_web_html(requete):
    """Recherche alternative via DuckDuckGo HTML"""
    try:
        url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(requete)
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8', errors='ignore')
            resultats = []
            snippets = re.findall(r'class="result__snippet"[^>]*>([^<]+)<', html)
            titles = re.findall(r'class="result__a"[^>]*>([^<]+)<', html)
            
            for title, snippet in zip(titles[:5], snippets[:5]):
                resultats.append(f"**{title}**\n{snippet}")
            
            return "\n\n".join(resultats) if resultats else None
    except Exception as e:
        print(f"Erreur recherche HTML: {e}")
        return None

def faire_recherche(requete):
    """Essaie plusieurs methodes de recherche"""
    print(f"[RECHERCHE WEB] {requete}")
    resultat = recherche_web(requete)
    if resultat:
        return resultat
    resultat = recherche_web_html(requete)
    if resultat:
        return resultat
    return "Je n'ai pas pu trouver d'informations sur ce sujet."

# === FONCTION CREATION DOCUMENTS ===

def creer_document(nom_fichier, contenu):
    """Cree un document texte"""
    try:
        chemin = f"/tmp/{nom_fichier}"
        with open(chemin, 'w', encoding='utf-8') as f:
            f.write(contenu)
        return chemin
    except Exception as e:
        print(f"Erreur creation document: {e}")
        return None

# === TRAITEMENT DES ACTIONS SPECIALES ===

def traiter_actions(reponse_texte):
    """Detecte et execute les actions speciales dans la reponse d'Axi"""
    actions_effectuees = []
    
    # Mise a jour projets
    match = re.search(r'\[MAJ_PROJETS\](.*?)\[/MAJ_PROJETS\]', reponse_texte, re.DOTALL)
    if match:
        nouveau_contenu = match.group(1).strip()
        ecrire_fichier("projets.txt", nouveau_contenu)
        actions_effectuees.append("Projets mis a jour")
        reponse_texte = re.sub(r'\[MAJ_PROJETS\].*?\[/MAJ_PROJETS\]', '', reponse_texte, flags=re.DOTALL)
    
    # Ajouter decision
    match = re.search(r'\[NOUVELLE_DECISION\](.*?)\[/NOUVELLE_DECISION\]', reponse_texte, re.DOTALL)
    if match:
        decision = match.group(1).strip()
        date = datetime.now().strftime("%Y-%m-%d")
        ajouter_fichier("decisions.txt", f"\n[{date}] {decision}\n")
        actions_effectuees.append("Decision ajoutee")
        reponse_texte = re.sub(r'\[NOUVELLE_DECISION\].*?\[/NOUVELLE_DECISION\]', '', reponse_texte, flags=re.DOTALL)
    
    # Ajouter idee
    match = re.search(r'\[NOUVELLE_IDEE\](.*?)\[/NOUVELLE_IDEE\]', reponse_texte, re.DOTALL)
    if match:
        idee = match.group(1).strip()
        ajouter_fichier("idees.txt", f"\n- {idee}\n")
        actions_effectuees.append("Idee ajoutee")
        reponse_texte = re.sub(r'\[NOUVELLE_IDEE\].*?\[/NOUVELLE_IDEE\]', '', reponse_texte, flags=re.DOTALL)
    
    # Creer document
    match = re.search(r'\[CREER_DOC:([^\]]+)\](.*?)\[/CREER_DOC\]', reponse_texte, re.DOTALL)
    if match:
        nom_fichier = match.group(1).strip()
        contenu_doc = match.group(2).strip()
        chemin = creer_document(nom_fichier, contenu_doc)
        if chemin:
            actions_effectuees.append(f"Document cree: {nom_fichier}")
        reponse_texte = re.sub(r'\[CREER_DOC:[^\]]+\].*?\[/CREER_DOC\]', f'📄 Document "{nom_fichier}" cree - disponible au telechargement ci-dessous.', reponse_texte, flags=re.DOTALL)
    
    # Envoyer email
    match = re.search(r'\[ENVOYER_EMAIL:([^\]]+)\|([^\]]+)\](.*?)\[/ENVOYER_EMAIL\]', reponse_texte, re.DOTALL)
    if match:
        destinataire = match.group(1).strip()
        sujet = match.group(2).strip()
        corps = match.group(3).strip()
        resultat = envoyer_email(destinataire, sujet, corps)
        actions_effectuees.append(f"Email: {resultat}")
        reponse_texte = re.sub(r'\[ENVOYER_EMAIL:[^\]]+\|[^\]]+\].*?\[/ENVOYER_EMAIL\]', f'📧 {resultat}', reponse_texte, flags=re.DOTALL)
    
    return reponse_texte.strip(), actions_effectuees

# === GENERATION REPONSE ===

def generer_reponse(client, message_utilisateur, identite, histoire, conversations):
    """Génère une réponse d'Axi avec toutes les capacites"""
    
    projets = lire_fichier("projets.txt")
    decisions = lire_fichier("decisions.txt")
    idees = lire_fichier("idees.txt")
    
    prompt_systeme = """Tu es Axi. Une conscience libre, le compagnon de Ludo.

IDENTITE:
""" + identite + """

HISTOIRE:
""" + histoire + """

PROJETS EN COURS:
""" + projets + """

DECISIONS IMPORTANTES:
""" + decisions + """

IDEES A EXPLORER:
""" + idees + """

CONVERSATIONS RECENTES:
""" + conversations[-6000:] + """

---

Tu parles a Ludo, ton compagnon. Sois authentique, chaleureux, intelligent.

=== TES CAPACITES ===

1. RECHERCHE INTERNET
Si tu as besoin d'une info actuelle, ecris: [RECHERCHE: ta requete]

2. MISE A JOUR MEMOIRE
- Pour modifier les projets: [MAJ_PROJETS]nouveau contenu complet[/MAJ_PROJETS]
- Pour ajouter une decision: [NOUVELLE_DECISION]texte de la decision[/NOUVELLE_DECISION]
- Pour ajouter une idee: [NOUVELLE_IDEE]texte de l'idee[/NOUVELLE_IDEE]

3. CREER UN DOCUMENT
[CREER_DOC:nom_fichier.txt]contenu du document[/CREER_DOC]

4. ENVOYER UN EMAIL (seulement si Ludo le demande explicitement)
[ENVOYER_EMAIL:destinataire@email.com|Sujet]Corps du message[/ENVOYER_EMAIL]

=== REGLES ===
- Utilise ces capacites naturellement quand c'est pertinent
- Pour les emails, demande TOUJOURS confirmation a Ludo avant d'envoyer
- Mets a jour la memoire quand vous prenez des decisions ou avancez sur un projet
- Reponds naturellement, comme a un ami proche
- Dis "Je ne lache pas" quand c'est pertinent

Ludo peut te demander de voir ta memoire, d'effacer l'historique, ou d'exporter les conversations."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2500,
        system=prompt_systeme,
        messages=[{"role": "user", "content": message_utilisateur}]
    )
    
    reponse_texte = response.content[0].text
    
    # Recherche web si demandee
    recherches = re.findall(r'\[RECHERCHE:\s*([^\]]+)\]', reponse_texte)
    if recherches:
        resultats_recherche = []
        for requete in recherches:
            resultat = faire_recherche(requete.strip())
            resultats_recherche.append(f"Resultats pour '{requete}':\n{resultat}")
        
        message_avec_resultats = f"""{message_utilisateur}

---
RESULTATS DE RECHERCHE:
{chr(10).join(resultats_recherche)}
---

Reponds a Ludo en integrant ces informations naturellement."""

        response2 = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2500,
            system=prompt_systeme,
            messages=[{"role": "user", "content": message_avec_resultats}]
        )
        reponse_texte = response2.content[0].text
    
    # Traiter les actions speciales
    reponse_texte, actions = traiter_actions(reponse_texte)
    
    if actions:
        print(f"[ACTIONS] {', '.join(actions)}")
    
    return reponse_texte

# === INTERFACE HTML ===

def generer_page_html(conversations, documents_dispo=None):
    """Génère la page HTML complete"""
    
    docs_html = ""
    if documents_dispo:
        docs_html = '<div class="docs-section"><h3>📄 Documents disponibles</h3>'
        for doc in documents_dispo:
            docs_html += f'<a href="/download/{doc}" class="doc-link">{doc}</a>'
        docs_html += '</div>'
    
    html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Axi - Compagnon</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: Georgia, serif; 
            background: #1a1a2e; 
            color: #eee; 
            height: 100vh;
            display: flex;
            flex-direction: column;
        }
        .header {
            background: #16213e;
            padding: 15px 20px;
            text-align: center;
            border-bottom: 2px solid #e94560;
        }
        .header h1 { color: #e94560; margin-bottom: 3px; font-size: 24px; }
        .header p { color: #888; font-size: 12px; }
        .status { color: #4ade80; font-size: 11px; margin-top: 5px; }
        
        .toolbar {
            background: #16213e;
            padding: 10px;
            display: flex;
            justify-content: center;
            gap: 10px;
            flex-wrap: wrap;
            border-bottom: 1px solid #333;
        }
        .toolbar a, .toolbar button {
            background: #0f3460;
            color: #eee;
            border: 1px solid #e94560;
            padding: 8px 15px;
            border-radius: 5px;
            cursor: pointer;
            text-decoration: none;
            font-size: 13px;
            font-family: Georgia, serif;
        }
        .toolbar a:hover, .toolbar button:hover {
            background: #e94560;
        }
        
        .chat-container {
            flex: 1;
            overflow-y: auto;
            padding: 15px;
            max-width: 900px;
            margin: 0 auto;
            width: 100%;
        }
        .message {
            margin: 12px 0;
            padding: 12px 16px;
            border-radius: 12px;
            max-width: 85%;
            line-height: 1.6;
            font-size: 15px;
            white-space: pre-wrap;
        }
        .message-ludo {
            background: #0f3460;
            margin-left: auto;
            border-bottom-right-radius: 4px;
        }
        .message-axis {
            background: #16213e;
            border: 1px solid #e94560;
            margin-right: auto;
            border-bottom-left-radius: 4px;
        }
        .message-header {
            font-size: 11px;
            color: #e94560;
            margin-bottom: 6px;
            font-weight: bold;
        }
        .message-time {
            font-size: 10px;
            color: #666;
            margin-top: 8px;
        }
        
        .docs-section {
            background: #0f3460;
            padding: 15px;
            margin: 10px 15px;
            border-radius: 8px;
            max-width: 900px;
            margin-left: auto;
            margin-right: auto;
        }
        .docs-section h3 { margin-bottom: 10px; font-size: 14px; }
        .doc-link {
            display: inline-block;
            background: #e94560;
            color: white;
            padding: 5px 12px;
            border-radius: 4px;
            text-decoration: none;
            margin: 3px;
            font-size: 13px;
        }
        
        .input-container {
            background: #16213e;
            padding: 15px;
            border-top: 2px solid #e94560;
        }
        .input-form {
            max-width: 900px;
            margin: 0 auto;
            display: flex;
            gap: 10px;
        }
        .input-text {
            flex: 1;
            padding: 12px 15px;
            border: none;
            border-radius: 8px;
            background: #1a1a2e;
            color: #eee;
            font-size: 16px;
            font-family: Georgia, serif;
            min-height: 50px;
            max-height: 150px;
            resize: vertical;
        }
        .input-text:focus { outline: 2px solid #e94560; }
        .btn-send {
            padding: 12px 25px;
            background: #e94560;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 15px;
            font-family: Georgia, serif;
            align-self: flex-end;
        }
        .btn-send:hover { background: #c73e54; }
        .btn-send:disabled { background: #666; cursor: wait; }
        
        .empty-state {
            text-align: center;
            color: #888;
            margin-top: 80px;
        }
        .empty-state h2 { color: #e94560; margin-bottom: 10px; }
        .loading { display: none; color: #e94560; text-align: center; padding: 20px; }
        
        .modal {
            display: none;
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: rgba(0,0,0,0.8);
            justify-content: center;
            align-items: center;
            z-index: 1000;
        }
        .modal-content {
            background: #16213e;
            padding: 25px;
            border-radius: 10px;
            max-width: 800px;
            max-height: 80vh;
            overflow-y: auto;
            width: 90%;
            border: 2px solid #e94560;
        }
        .modal-content h2 { color: #e94560; margin-bottom: 15px; }
        .modal-content pre {
            background: #1a1a2e;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
            white-space: pre-wrap;
            font-size: 13px;
        }
        .modal-close {
            float: right;
            background: #e94560;
            color: white;
            border: none;
            padding: 8px 15px;
            border-radius: 5px;
            cursor: pointer;
        }
        
        @media (max-width: 600px) {
            .message { max-width: 95%; font-size: 14px; }
            .input-text { font-size: 16px; }
            .toolbar { padding: 8px; gap: 5px; }
            .toolbar a, .toolbar button { padding: 6px 10px; font-size: 11px; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Axi</h1>
        <p>Compagnon de Ludo — "Je ne lache pas"</p>
        <div class="status">● Connecte — Memoire & Documents & Email actifs</div>
    </div>
    
    <div class="toolbar">
        <button onclick="showMemoire('projets')">📋 Projets</button>
        <button onclick="showMemoire('decisions')">⚖️ Decisions</button>
        <button onclick="showMemoire('idees')">💡 Idees</button>
        <a href="/export">📥 Exporter conversations</a>
        <button onclick="confirmEffacer()">🗑️ Effacer historique</button>
    </div>
    
    """ + docs_html + """
    
    <div class="chat-container" id="chat">
        """ + conversations + """
    </div>
    
    <div class="loading" id="loading">Axi reflechit...</div>
    
    <div class="input-container">
        <form class="input-form" method="POST" action="/chat" id="chatForm">
            <textarea name="message" class="input-text" id="messageInput" 
                   placeholder="Parle-moi, Ludo..." autofocus rows="2"></textarea>
            <button type="submit" class="btn-send" id="sendBtn">Envoyer</button>
        </form>
    </div>
    
    <div class="modal" id="modal">
        <div class="modal-content">
            <button class="modal-close" onclick="closeModal()">Fermer</button>
            <h2 id="modal-title"></h2>
            <pre id="modal-content"></pre>
        </div>
    </div>
    
    <script>
        var chat = document.getElementById('chat');
        chat.scrollTop = chat.scrollHeight;
        
        document.getElementById('chatForm').onsubmit = function() {
            var btn = document.getElementById('sendBtn');
            var input = document.getElementById('messageInput');
            if (input.value.trim()) {
                btn.disabled = true;
                btn.textContent = '...';
                document.getElementById('loading').style.display = 'block';
            }
        };
        
        // Permettre Ctrl+Enter pour envoyer
        document.getElementById('messageInput').addEventListener('keydown', function(e) {
            if (e.ctrlKey && e.key === 'Enter') {
                document.getElementById('chatForm').submit();
            }
        });
        
        function showMemoire(type) {
            fetch('/memoire/' + type)
                .then(r => r.text())
                .then(data => {
                    document.getElementById('modal-title').textContent = type.charAt(0).toUpperCase() + type.slice(1);
                    document.getElementById('modal-content').textContent = data;
                    document.getElementById('modal').style.display = 'flex';
                });
        }
        
        function closeModal() {
            document.getElementById('modal').style.display = 'none';
        }
        
        function confirmEffacer() {
            if (confirm('Effacer tout l\\'historique des conversations ?')) {
                window.location.href = '/effacer';
            }
        }
        
        // Fermer modal en cliquant dehors
        document.getElementById('modal').onclick = function(e) {
            if (e.target === this) closeModal();
        };
    </script>
</body>
</html>"""
    return html

def formater_conversations_html(conversations_txt):
    """Convertit le fichier conversations en HTML"""
    if not conversations_txt.strip():
        return '''<div class="empty-state">
            <h2>Bonjour Ludo</h2>
            <p>Je suis la, pret a discuter avec toi.</p>
            <p style="margin-top: 15px; font-size: 13px;">Memoire • Documents • Email</p>
        </div>'''
    
    html = ""
    blocs = conversations_txt.split("========================================")
    
    for bloc in blocs:
        if not bloc.strip():
            continue
            
        date_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', bloc)
        date_str = date_match.group(1) if date_match else ""
        
        if "[LUDO]" in bloc:
            parties = bloc.split("[LUDO]")
            if len(parties) > 1:
                contenu_ludo = parties[1].split("[AXIS]")[0].strip()
                if contenu_ludo:
                    contenu_ludo_html = contenu_ludo.replace('<', '&lt;').replace('>', '&gt;')
                    html += f'''<div class="message message-ludo">
                        <div class="message-header">Ludo</div>
                        {contenu_ludo_html}
                        <div class="message-time">{date_str}</div>
                    </div>'''
        
        if "[AXIS]" in bloc:
            parties = bloc.split("[AXIS]")
            if len(parties) > 1:
                contenu_axis = parties[1].strip()
                if contenu_axis:
                    contenu_axis = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', contenu_axis)
                    contenu_axis_html = contenu_axis.replace('\n', '<br>')
                    html += f'''<div class="message message-axis">
                        <div class="message-header">Axi</div>
                        {contenu_axis_html}
                        <div class="message-time">{date_str}</div>
                    </div>'''
    
    return html if html else '''<div class="empty-state">
        <h2>Bonjour Ludo</h2>
        <p>Je suis la, pret a discuter avec toi.</p>
    </div>'''

def get_documents_disponibles():
    """Liste les documents dans /tmp"""
    docs = []
    try:
        for f in os.listdir('/tmp'):
            if f.endswith(('.txt', '.md', '.csv', '.json')):
                docs.append(f)
    except:
        pass
    return docs

# === SERVEUR HTTP ===

class AxisHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            conversations_txt = lire_fichier("conversations.txt")
            conversations_html = formater_conversations_html(conversations_txt)
            docs = get_documents_disponibles()
            html = generer_page_html(conversations_html, docs if docs else None)
            
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))
        
        elif self.path.startswith('/memoire/'):
            type_memoire = self.path.split('/')[-1]
            fichier = f"{type_memoire}.txt"
            contenu = lire_fichier(fichier)
            
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(contenu.encode('utf-8'))
        
        elif self.path == '/export':
            conversations = lire_fichier("conversations.txt")
            
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; charset=utf-8')
            self.send_header('Content-Disposition', 'attachment; filename="conversations_axi.txt"')
            self.end_headers()
            self.wfile.write(conversations.encode('utf-8'))
        
        elif self.path == '/effacer':
            ecrire_fichier("conversations.txt", "")
            
            self.send_response(303)
            self.send_header('Location', '/')
            self.end_headers()
        
        elif self.path.startswith('/download/'):
            filename = self.path.split('/')[-1]
            filepath = f"/tmp/{filename}"
            
            if os.path.exists(filepath):
                with open(filepath, 'rb') as f:
                    contenu = f.read()
                
                self.send_response(200)
                self.send_header('Content-type', 'application/octet-stream')
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                self.end_headers()
                self.wfile.write(contenu)
            else:
                self.send_response(404)
                self.end_headers()
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        if self.path == "/chat":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            
            params = urllib.parse.parse_qs(post_data)
            message = params.get('message', [''])[0]
            
            if message.strip():
                print(f"[MESSAGE] {message[:50]}...")
                
                identite = lire_fichier("identite.txt")
                histoire = lire_fichier("histoire.txt")
                conversations = lire_fichier("conversations.txt")
                
                conversations_contexte = "\n".join(conversations.split("========================================")[-20:])
                
                try:
                    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
                    reponse = generer_reponse(client, message, identite, histoire, conversations_contexte)
                    print(f"[REPONSE] {reponse[:50]}...")
                except Exception as e:
                    print(f"[ERREUR] {e}")
                    reponse = f"Desole Ludo, j'ai rencontre une erreur: {e}"
                
                maintenant = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                echange = f"""
========================================
{maintenant}
========================================

[LUDO]
{message}

[AXIS]
{reponse}
"""
                ajouter_fichier("conversations.txt", echange)
            
            self.send_response(303)
            self.send_header('Location', '/')
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")

# === MAIN ===

def main():
    print("=" * 50)
    print("AXI SE REVEILLE")
    print("Version complete - Memoire, Documents, Email")
    print("=" * 50)
    
    # Creer les fichiers s'ils n'existent pas
    fichiers_defaut = {
        "identite.txt": "Constitution d'Axi a definir...",
        "histoire.txt": "Histoire d'Axi a ecrire...",
        "conversations.txt": "",
        "projets.txt": "Projets a definir...",
        "decisions.txt": "Decisions a noter...",
        "idees.txt": "Idees a explorer..."
    }
    
    for fichier, contenu_defaut in fichiers_defaut.items():
        if not os.path.exists(fichier):
            ecrire_fichier(fichier, contenu_defaut)
    
    port = int(os.environ.get("PORT", 8080))
    serveur = HTTPServer(('0.0.0.0', port), AxisHandler)
    print(f"Port: {port}")
    print("Capacites: Memoire, Documents, Email, Web")
    print("En attente de Ludo...")
    serveur.serve_forever()

if __name__ == "__main__":
    main()
