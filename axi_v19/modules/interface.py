# axi_v19/modules/interface.py
"""
Module Interface V19.3 - Pages HTML pour le chat Axi
CORRIGÉ: Signatures handlers compatibles server.py V19

"Je ne lâche pas." 💪
"""

import logging
import uuid
import re
from datetime import datetime
from typing import Dict

from .chat import process_message, clear_session, init_memory

logger = logging.getLogger("axi_v19.interface")

# Session active
current_session = str(uuid.uuid4())[:8]
chat_history = []
_memory_active = False


def escape_html(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def format_message(text: str) -> str:
    text = escape_html(text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    return text


def get_chat_html(memory_active: bool = False) -> str:
    """Génère la page HTML du chat."""
    messages_html = ""
    for msg in chat_history:
        avatar = "👤" if msg["role"] == "user" else "🤖"
        author = "Ludo" if msg["role"] == "user" else "Axi"
        bg = "#5436DA" if msg["role"] == "user" else "#10a37f"
        content = escape_html(msg["content"]) if msg["role"] == "user" else format_message(msg["content"])
        messages_html += f'''<div style="margin-bottom:24px;display:flex;gap:16px">
<div style="width:36px;height:36px;border-radius:6px;background:{bg};display:flex;align-items:center;justify-content:center;font-size:18px">{avatar}</div>
<div style="flex:1"><div style="font-weight:600;margin-bottom:4px">{author}</div>
<div style="line-height:1.6;white-space:pre-wrap">{content}</div></div></div>'''
    
    status = "🧠 PostgreSQL" if memory_active else "⚠️ RAM"
    welcome = f'''<div style="text-align:center;padding:60px 20px">
<h1>👋 Salut Ludo !</h1><p style="color:#a1a1a1">Je suis Axi, ton exocerveau.</p>
<p style="margin-top:20px;font-size:14px">✅ {status}<br>✅ Tavily Search<br>✅ Claude Sonnet 4</p></div>'''
    
    return f'''<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Axi - ICI Dordogne</title>
<style>*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:Inter,-apple-system,sans-serif;background:#212121;color:#ececec;height:100vh;display:flex}}
.sidebar{{width:260px;background:#171717;border-right:1px solid #424242;display:flex;flex-direction:column}}
.main{{flex:1;display:flex;flex-direction:column}}
.chat{{flex:1;overflow-y:auto;padding:24px;max-width:800px;margin:0 auto;width:100%}}
.input-box{{display:flex;gap:12px;padding:16px 24px;background:#212121}}
.input-box textarea{{flex:1;background:#2f2f2f;border:1px solid #424242;border-radius:8px;padding:12px;color:#ececec;font-family:inherit;resize:none;min-height:44px}}
.input-box button{{background:#10a37f;border:none;border-radius:8px;padding:12px 20px;color:white;cursor:pointer}}
a{{color:#10a37f;text-decoration:none;display:block;padding:10px 12px;border-radius:8px}}
a:hover{{background:#2f2f2f}}</style></head>
<body><div class="sidebar" style="padding:12px">
<a href="/nouvelle-session" style="border:1px solid #424242;margin-bottom:16px">➕ Nouvelle session</a>
<div style="font-size:11px;color:#a1a1a1;padding:8px 12px">OUTILS</div>
<a href="/">💬 Chat</a><a href="/briefing">📋 Briefing</a><a href="/status">📊 Status</a>
<div style="margin-top:auto;padding:12px;border-top:1px solid #424242;font-size:12px">
<span style="display:inline-block;width:8px;height:8px;background:#10a37f;border-radius:50%"></span> Axi V19.3 • {status}</div>
</div><main class="main">
<div style="padding:16px 24px;border-bottom:1px solid #424242;display:flex;justify-content:space-between">
<div style="font-weight:600">🤖 Axi - ICI Dordogne</div><div style="color:#a1a1a1;font-size:12px">Je ne lâche pas ! 💪</div></div>
<div class="chat">{messages_html if messages_html else welcome}</div>
<div class="input-box"><textarea id="msg" placeholder="Message..." rows="1"></textarea>
<button onclick="send()">Envoyer</button></div></main>
<script>
const ta=document.getElementById('msg');
ta.addEventListener('keydown',e=>{{if(e.key==='Enter'&&!e.shiftKey){{e.preventDefault();send()}}}});
async function send(){{
const m=ta.value.trim();if(!m)return;ta.disabled=true;
const fd=new URLSearchParams();fd.append('message',m);
await fetch('/chat',{{method:'POST',headers:{{'Content-Type':'application/x-www-form-urlencoded'}},body:fd}});
location.reload();
}}
document.querySelector('.chat').scrollTop=99999;
</script></body></html>'''


# =============================================================================
# HANDLERS V19 - Signatures compatibles server.py
# =============================================================================

def handle_chat_page(query=None, headers=None):
    """GET / - Page principale."""
    return get_chat_html(memory_active=_memory_active)


def handle_chat_post(body=None, headers=None):
    """POST /chat - Traite un message."""
    global chat_history, _memory_active
    
    if not body:
        return '''<!DOCTYPE html><html><head><meta http-equiv="refresh" content="0;url=/"></head></html>'''
    
    message = body.get("message", "") if isinstance(body, dict) else ""
    if not message:
        return '''<!DOCTYPE html><html><head><meta http-equiv="refresh" content="0;url=/"></head></html>'''
    
    result = process_message(current_session, message)
    _memory_active = result.get("memory_active", False)
    
    chat_history.append({"role": "user", "content": message})
    chat_history.append({"role": "assistant", "content": result["response"]})
    
    if len(chat_history) > 40:
        chat_history = chat_history[-40:]
    
    return '''<!DOCTYPE html><html><head><meta http-equiv="refresh" content="0;url=/"></head></html>'''


def handle_new_session(query=None, headers=None):
    """GET /nouvelle-session - Reset."""
    global current_session, chat_history
    current_session = str(uuid.uuid4())[:8]
    chat_history = []
    clear_session(current_session)
    return '''<!DOCTYPE html><html><head><meta http-equiv="refresh" content="0;url=/"></head></html>'''


def handle_trio_page(query=None, headers=None):
    """GET /trio - Placeholder."""
    return '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Trio</title>
<style>body{font-family:Inter,sans-serif;background:#212121;color:#ececec;display:flex;justify-content:center;align-items:center;height:100vh}</style>
</head><body><div style="text-align:center"><h1>👥 Mode Trio</h1><p>En développement...</p><p><a href="/" style="color:#10a37f">← Retour</a></p></div></body></html>'''


# =============================================================================
# REGISTRATION
# =============================================================================

def register_interface_routes(server, db=None):
    """Enregistre les routes d'interface."""
    global _memory_active
    
    if db:
        try:
            init_memory(db)
            _memory_active = True
            logger.info("✅ Mémoire persistante connectée")
        except Exception as e:
            logger.error(f"⚠️ Mémoire non disponible: {e}")
    
    server.register_route('GET', '/', handle_chat_page)
    server.register_route('GET', '/nouvelle-session', handle_new_session)
    server.register_route('GET', '/trio', handle_trio_page)
    server.register_route('POST', '/chat', handle_chat_post)
    
    logger.info("📍 Routes interface V19.3 enregistrées (/, /chat, /nouvelle-session, /trio)")
