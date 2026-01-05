# axi_v19/modules/interface.py
"""
Module Interface V19 - Pages HTML pour le chat Axi
Interface style ChatGPT avec sidebar et conversations.

"Je ne lâche pas." 💪
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, Any
from urllib.parse import parse_qs

from .chat import process_message, clear_session, conversations

logger = logging.getLogger("axi_v19.interface")

# Session active (pour simplifier, une seule session globale)
# TODO: Migrer vers PostgreSQL pour multi-sessions
current_session = str(uuid.uuid4())[:8]
chat_history = []  # Messages affichés


# =============================================================================
# TEMPLATE HTML
# =============================================================================

def get_chat_html() -> str:
    """Génère la page HTML du chat."""
    
    # Construire les messages
    messages_html = ""
    for msg in chat_history:
        if msg["role"] == "user":
            messages_html += f'''
            <div class="message user">
                <div class="message-avatar">👤</div>
                <div class="message-content">
                    <div class="message-author">Ludo</div>
                    <div class="message-text">{escape_html(msg["content"])}</div>
                </div>
            </div>'''
        else:
            messages_html += f'''
            <div class="message assistant">
                <div class="message-avatar">🤖</div>
                <div class="message-content">
                    <div class="message-author">Axi</div>
                    <div class="message-text">{format_message(msg["content"])}</div>
                </div>
            </div>'''
    
    return f'''<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Axi - ICI Dordogne</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        :root {{
            --bg-primary: #212121;
            --bg-secondary: #171717;
            --bg-sidebar: #171717;
            --bg-input: #2f2f2f;
            --bg-hover: #2f2f2f;
            --text-primary: #ececec;
            --text-secondary: #a1a1a1;
            --accent: #10a37f;
            --accent-hover: #1a7f64;
            --border: #424242;
        }}
        
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            height: 100vh;
            display: flex;
            overflow: hidden;
        }}
        
        /* SIDEBAR */
        .sidebar {{
            width: 260px;
            background: var(--bg-sidebar);
            border-right: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            flex-shrink: 0;
        }}
        
        .sidebar-header {{
            padding: 12px;
            border-bottom: 1px solid var(--border);
        }}
        
        .new-chat-btn {{
            width: 100%;
            padding: 12px 16px;
            background: transparent;
            border: 1px solid var(--border);
            border-radius: 8px;
            color: var(--text-primary);
            font-size: 14px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 10px;
            transition: background 0.2s;
        }}
        
        .new-chat-btn:hover {{ background: var(--bg-hover); }}
        
        .sidebar-nav {{
            flex: 1;
            overflow-y: auto;
            padding: 8px;
        }}
        
        .nav-section {{ margin-bottom: 16px; }}
        
        .nav-section-title {{
            font-size: 11px;
            font-weight: 600;
            color: var(--text-secondary);
            padding: 8px 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .nav-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px 12px;
            border-radius: 8px;
            color: var(--text-primary);
            text-decoration: none;
            font-size: 14px;
            transition: background 0.2s;
        }}
        
        .nav-item:hover, .nav-item.active {{ background: var(--bg-hover); }}
        
        .sidebar-footer {{
            padding: 12px;
            border-top: 1px solid var(--border);
        }}
        
        .status-badge {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            background: var(--bg-hover);
            border-radius: 8px;
            font-size: 12px;
        }}
        
        .status-dot {{
            width: 8px;
            height: 8px;
            background: var(--accent);
            border-radius: 50%;
        }}
        
        /* MAIN */
        .main {{
            flex: 1;
            display: flex;
            flex-direction: column;
            min-width: 0;
        }}
        
        .chat-header {{
            padding: 16px 24px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .chat-title {{ font-size: 16px; font-weight: 600; }}
        
        .chat-container {{
            flex: 1;
            overflow-y: auto;
            scroll-behavior: smooth;
        }}
        
        .chat-messages {{
            max-width: 800px;
            margin: 0 auto;
            padding: 24px;
        }}
        
        .message {{
            margin-bottom: 24px;
            display: flex;
            gap: 16px;
        }}
        
        .message-avatar {{
            width: 36px;
            height: 36px;
            border-radius: 6px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            flex-shrink: 0;
        }}
        
        .message.user .message-avatar {{ background: #5436DA; }}
        .message.assistant .message-avatar {{ background: var(--accent); }}
        
        .message-content {{ flex: 1; min-width: 0; }}
        
        .message-author {{
            font-weight: 600;
            margin-bottom: 4px;
            font-size: 14px;
        }}
        
        .message-text {{
            line-height: 1.6;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
        
        .message-text strong {{ color: #fff; font-weight: 600; }}
        
        /* INPUT */
        .input-container {{
            padding: 16px 24px 24px;
            background: var(--bg-primary);
        }}
        
        .input-wrapper {{
            max-width: 800px;
            margin: 0 auto;
            position: relative;
        }}
        
        .input-box {{
            display: flex;
            align-items: flex-end;
            background: var(--bg-input);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 12px 16px;
            gap: 12px;
        }}
        
        .input-box:focus-within {{
            border-color: var(--accent);
        }}
        
        textarea {{
            flex: 1;
            background: transparent;
            border: none;
            color: var(--text-primary);
            font-family: inherit;
            font-size: 14px;
            resize: none;
            min-height: 24px;
            max-height: 200px;
            outline: none;
        }}
        
        textarea::placeholder {{ color: var(--text-secondary); }}
        
        .send-btn {{
            background: var(--accent);
            border: none;
            border-radius: 6px;
            padding: 8px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: background 0.2s;
        }}
        
        .send-btn:hover {{ background: var(--accent-hover); }}
        .send-btn:disabled {{ opacity: 0.5; cursor: not-allowed; }}
        
        .send-btn svg {{
            width: 20px;
            height: 20px;
            color: white;
        }}
        
        .input-hint {{
            text-align: center;
            font-size: 12px;
            color: var(--text-secondary);
            margin-top: 8px;
        }}
        
        /* Welcome */
        .welcome {{
            text-align: center;
            padding: 60px 20px;
        }}
        
        .welcome h1 {{
            font-size: 28px;
            margin-bottom: 12px;
        }}
        
        .welcome p {{
            color: var(--text-secondary);
            font-size: 16px;
        }}
        
        @keyframes spin {{
            from {{ transform: rotate(0deg); }}
            to {{ transform: rotate(360deg); }}
        }}
    </style>
</head>
<body>
    <div class="sidebar">
        <div class="sidebar-header">
            <a href="/nouvelle-session" class="new-chat-btn">
                <span>➕</span> Nouvelle session
            </a>
        </div>
        
        <nav class="sidebar-nav">
            <div class="nav-section">
                <div class="nav-section-title">Outils</div>
                <a href="/" class="nav-item active">💬 Chat</a>
                <a href="/trio" class="nav-item">👥 Mode Trio</a>
                <a href="/briefing" class="nav-item">📋 Briefing</a>
            </div>
            
            <div class="nav-section">
                <div class="nav-section-title">Veilles</div>
                <a href="/run-veille" class="nav-item">🏠 DPE ADEME</a>
                <a href="/run-veille-concurrence" class="nav-item">🔍 Concurrence</a>
            </div>
            
            <div class="nav-section">
                <div class="nav-section-title">Système</div>
                <a href="/status" class="nav-item">📊 Status</a>
                <a href="/memory" class="nav-item">🧠 Memory</a>
            </div>
        </nav>
        
        <div class="sidebar-footer">
            <div class="status-badge">
                <span class="status-dot"></span>
                <span>Axi V19.2 • PostgreSQL</span>
            </div>
        </div>
    </div>
    
    <main class="main">
        <div class="chat-header">
            <div class="chat-title">🤖 Axi - ICI Dordogne</div>
            <div style="color: var(--text-secondary); font-size: 12px;">
                Je ne lâche pas ! 💪
            </div>
        </div>
        
        <div class="chat-container" id="chat">
            <div class="chat-messages">
                {messages_html if messages_html else '''
                <div class="welcome">
                    <h1>👋 Salut Ludo !</h1>
                    <p>Je suis Axi, ton compagnon IA. Comment puis-je t'aider aujourd'hui ?</p>
                    <p style="margin-top: 20px; font-size: 14px;">
                        ✅ Recherche web corrigée (Tavily avec filtrage français)<br>
                        ✅ Claude Sonnet 4 pour les réponses<br>
                        ✅ V19.2 Bunker sécurisé
                    </p>
                </div>
                '''}
            </div>
        </div>
        
        <div class="input-container">
            <div class="input-wrapper">
                <div class="input-box">
                    <textarea 
                        id="messageInput" 
                        placeholder="Écris ton message à Axi..."
                        rows="1"
                    ></textarea>
                    <button class="send-btn" id="sendBtn" onclick="sendMessage()">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/>
                        </svg>
                    </button>
                </div>
                <div class="input-hint">Entrée pour envoyer • Shift+Entrée pour nouvelle ligne</div>
            </div>
        </div>
    </main>
    
    <script>
        const textarea = document.getElementById('messageInput');
        const chatBox = document.getElementById('chat');
        
        // Auto-resize textarea
        textarea.addEventListener('input', function() {{
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 200) + 'px';
        }});
        
        // Scroll to bottom
        chatBox.scrollTop = chatBox.scrollHeight;
        
        // Send message
        async function sendMessage() {{
            const input = document.getElementById('messageInput');
            const btn = document.getElementById('sendBtn');
            const message = input.value.trim();
            
            if (!message) return;
            
            input.disabled = true;
            btn.disabled = true;
            btn.innerHTML = '<span style="animation: spin 1s linear infinite; display: inline-block;">⏳</span>';
            
            try {{
                const formData = new URLSearchParams();
                formData.append('message', message);
                
                const response = await fetch('/chat', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/x-www-form-urlencoded' }},
                    body: formData
                }});
                
                if (response.ok || response.redirected) {{
                    window.location.reload();
                }} else {{
                    alert("Erreur serveur : " + response.status);
                    resetUI();
                }}
            }} catch (error) {{
                console.error('Erreur:', error);
                alert("Erreur de connexion.");
                resetUI();
            }}
        }}
        
        function resetUI() {{
            const input = document.getElementById('messageInput');
            const btn = document.getElementById('sendBtn');
            input.disabled = false;
            btn.disabled = false;
            btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>';
            input.focus();
        }}
        
        // Enter to send
        textarea.addEventListener('keydown', function(e) {{
            if (e.key === 'Enter' && !e.shiftKey) {{
                e.preventDefault();
                sendMessage();
            }}
        }});
        
        // Focus on load
        textarea.focus();
    </script>
</body>
</html>'''


def escape_html(text: str) -> str:
    """Échappe les caractères HTML dangereux."""
    return (text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;"))


def format_message(text: str) -> str:
    """Formate un message pour l'affichage HTML (markdown basique)."""
    text = escape_html(text)
    
    # Bold: **text** -> <strong>text</strong>
    import re
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    
    # Emoji preservation
    return text


# =============================================================================
# HANDLERS
# =============================================================================

def handle_chat_page(query: Dict) -> str:
    """GET / - Page principale du chat."""
    return get_chat_html()


def handle_chat_post(data: Dict) -> str:
    """POST /chat - Traite un message et redirige."""
    global chat_history
    
    message = data.get("message", "")
    if not message:
        return '''<!DOCTYPE html>
<html><head><meta http-equiv="refresh" content="0;url=/"></head>
<body>Redirection...</body></html>'''
    
    # Traiter le message
    result = process_message(current_session, message)
    
    # Ajouter à l'historique d'affichage
    chat_history.append({"role": "user", "content": message})
    chat_history.append({"role": "assistant", "content": result["response"]})
    
    # Limiter l'historique
    if len(chat_history) > 40:
        chat_history = chat_history[-40:]
    
    # Rediriger vers la page principale
    return '''<!DOCTYPE html>
<html><head><meta http-equiv="refresh" content="0;url=/"></head>
<body>Redirection...</body></html>'''


def handle_new_session(query: Dict) -> str:
    """GET /nouvelle-session - Nouvelle conversation."""
    global current_session, chat_history
    current_session = str(uuid.uuid4())[:8]
    chat_history = []
    clear_session(current_session)
    
    return '''<!DOCTYPE html>
<html><head><meta http-equiv="refresh" content="0;url=/"></head>
<body>Redirection...</body></html>'''


def handle_trio_page(query: Dict) -> str:
    """GET /trio - Page Mode Trio (placeholder)."""
    return '''<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Mode Trio - Axi</title>
    <style>
        body { font-family: Inter, sans-serif; background: #212121; color: #ececec; 
               display: flex; justify-content: center; align-items: center; height: 100vh; }
        .container { text-align: center; }
        h1 { margin-bottom: 20px; }
        a { color: #10a37f; }
    </style>
</head>
<body>
    <div class="container">
        <h1>👥 Mode Trio</h1>
        <p>Ludo + Axis + Axi</p>
        <p style="color: #a1a1a1; margin-top: 20px;">En cours de développement...</p>
        <p><a href="/">← Retour au chat</a></p>
    </div>
</body>
</html>'''


def register_interface_routes(server):
    """Enregistre les routes d'interface sur le serveur."""
    
    # On doit modifier le serveur pour supporter les réponses HTML
    # Pour l'instant, on va utiliser une astuce: retourner le HTML comme string
    # et le handler JSON va le détecter
    
    server.register_route('GET', '/', handle_chat_page)
    server.register_route('GET', '/nouvelle-session', handle_new_session)
    server.register_route('GET', '/trio', handle_trio_page)
    server.register_route('POST', '/chat', handle_chat_post)
    
    logger.info("📍 Routes interface enregistrées (/, /chat, /nouvelle-session, /trio)")
