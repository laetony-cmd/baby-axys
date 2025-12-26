import os
import logging
from flask import Flask, request, jsonify, render_template_string
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
import tavily
import google.generativeai as genai

# --- CONFIGURATION ---
VERSION = "v12.5 - TRIO SYMBINE (Final)"
# Configuration Gemini (Lumo)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Configuration Tavily
tavily_client = None
try:
    if os.environ.get("TAVILY_API_KEY"):
        tavily_client = tavily.TavilyClient(api_key=os.environ.get("TAVILY_API_KEY"))
        print("✅ [TAVILY] Client activé")
except Exception as e:
    print(f"⚠️ [TAVILY] Erreur: {e}")

# --- IMPORT DB (Le fichier que tu as corrigé) ---
try:
    import db
    print("✅ [DB] Module db.py chargé avec succès")
    # Tente d'initialiser la table
    db.init_db()
except ImportError as e:
    print(f"❌ [DB] CRITIQUE: Impossible d'importer db.py: {e}")
    db = None

app = Flask(__name__)

# --- BANNIERE DE DEMARRAGE ---
print(f"""
╔══════════════════════════════════════════════════════════════╗
║         {VERSION}          ║
║      AXIS + LUMO + LUDO = SYMBINE INTELLIGENCE               ║
╚══════════════════════════════════════════════════════════════╝
""")

# --- FONCTIONS IA ---

def ask_gemini(prompt):
    """Interroge Lumo (Gemini)"""
    if not GEMINI_API_KEY:
        return "⚠️ Gemini non configuré (Clé manquante)"
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Erreur Gemini: {e}"

# --- ROUTES FLASK ---

@app.route('/')
def home():
    """Interface simple de test"""
    return f"""
    <html>
    <body style="font-family:sans-serif; background:#111; color:#0f0; padding:20px;">
        <h1>{VERSION}</h1>
        <p>✅ Serveur Actif</p>
        <p>🤖 Tavily: {'OK' if tavily_client else 'OFF'}</p>
        <p>🧠 Gemini: {'OK' if GEMINI_API_KEY else 'OFF'}</p>
        <p>🗄️ Database: {'OK' if db else 'ERREUR'}</p>
        <hr>
        <h3>Test Trio Symbine</h3>
        <form action="/chat" method="post">
            <input type="text" name="message" placeholder="Parler au Trio..." style="width:300px; padding:10px;">
            <button type="submit" style="padding:10px;">Envoyer</button>
        </form>
    </body>
    </html>
    """

@app.route('/status')
def status():
    return jsonify({
        "version": VERSION,
        "db_status": "connected" if db else "disconnected",
        "tavily": "active" if tavily_client else "inactive",
        "gemini": "active" if GEMINI_API_KEY else "inactive"
    })

@app.route('/chat', methods=['POST'])
def chat():
    user_input = request.form.get('message') or request.json.get('message')
    
    # 1. Sauvegarde en DB (Mémoire)
    if db:
        conn = db.get_db_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO memory (session_id, user_input, axis_response, metadata) VALUES (%s, %s, %s, %s)",
                        ("session_web", user_input, "processing", '{"source": "web"}')
                    )
                    conn.commit()
            except Exception as e:
                print(f"Erreur save DB: {e}")
            finally:
                conn.close()

    # 2. Appel Gemini (Lumo) pour test
    lumo_response = ask_gemini(f"Tu es Lumo. Ludo dit : {user_input}. Réponds court.")

    return jsonify({
        "user": user_input,
        "lumo_response": lumo_response,
        "system": "Trio v12.5 Operational"
    })

# --- DEMARRAGE ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
