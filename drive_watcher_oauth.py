"""
DRIVE WATCHER (OAuth) - Surveillance Google Drive + Transcription Whisper
ICI Dordogne - Axi V19
Date: 08/01/2026

Utilise OAuth2 (application de bureau) au lieu d'un compte de service.
Premier lancement : ouvrira un navigateur pour autorisation.

Usage:
    python drive_watcher_oauth.py <FOLDER_ID> [--once]
"""

import os
import sys
import json
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

# Google Drive API avec OAuth
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

# Whisper
import whisper

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('drive_watcher.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG = {
    # Fichier OAuth credentials (téléchargé depuis Google Cloud Console)
    "oauth_credentials_path": r"C:\axi-v19\client_secret.json",
    
    # Token généré après première authentification
    "token_path": r"C:\axi-v19\token.json",
    
    # Dossier local pour les téléchargements et transcriptions
    "local_download_path": r"C:\axi-v19\audio_downloads",
    "local_transcripts_path": r"C:\axi-v19\transcriptions",
    
    # Extensions audio supportées
    "audio_extensions": [".wav", ".m4a", ".mp3", ".ogg", ".flac"],
    
    # Modèle Whisper (tiny, base, small, medium, large)
    "whisper_model": "small",
    
    # Intervalle de vérification (secondes)
    "check_interval": 60,
    
    # Fichier pour tracker les fichiers déjà traités
    "processed_file": r"C:\axi-v19\processed_files.json",
    
    # Langue pour Whisper
    "language": "fr"
}

# Scopes nécessaires pour accéder à Drive en lecture
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']


# ============================================================================
# AUTHENTIFICATION OAUTH
# ============================================================================

def get_drive_service(config: Dict):
    """Authentification OAuth et création du service Drive"""
    creds = None
    
    # Vérifier si un token existe déjà
    if os.path.exists(config["token_path"]):
        try:
            creds = Credentials.from_authorized_user_file(config["token_path"], SCOPES)
            logger.info("✅ Token existant chargé")
        except Exception as e:
            logger.warning(f"⚠️ Erreur chargement token: {e}")
    
    # Si pas de credentials valides, authentifier
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                logger.info("✅ Token rafraîchi")
            except Exception as e:
                logger.warning(f"⚠️ Erreur refresh token: {e}")
                creds = None
        
        if not creds:
            if not os.path.exists(config["oauth_credentials_path"]):
                raise FileNotFoundError(
                    f"❌ Fichier OAuth non trouvé: {config['oauth_credentials_path']}\n"
                    "   Télécharge-le depuis Google Cloud Console > API > Identifiants"
                )
            
            logger.info("🔐 Authentification OAuth requise - ouverture du navigateur...")
            flow = InstalledAppFlow.from_client_secrets_file(
                config["oauth_credentials_path"], SCOPES
            )
            creds = flow.run_local_server(port=0)
            logger.info("✅ Authentification réussie")
        
        # Sauvegarder le token pour les prochaines fois
        with open(config["token_path"], 'w') as token:
            token.write(creds.to_json())
            logger.info(f"💾 Token sauvegardé: {config['token_path']}")
    
    # Créer le service Drive
    service = build('drive', 'v3', credentials=creds)
    logger.info("✅ Service Google Drive connecté")
    return service


# ============================================================================
# SERVICE GOOGLE DRIVE
# ============================================================================

class DriveService:
    """Gère les opérations Google Drive"""
    
    def __init__(self, service):
        self.service = service
    
    def list_audio_files(self, folder_id: str, extensions: List[str]) -> List[Dict]:
        """Liste les fichiers audio dans un dossier"""
        try:
            query = f"'{folder_id}' in parents and trashed=false"
            
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name, mimeType, createdTime, size)',
                orderBy='createdTime desc'
            ).execute()
            
            files = results.get('files', [])
            
            # Filtrer par extension
            audio_files = []
            for f in files:
                name = f.get('name', '')
                if any(name.lower().endswith(ext) for ext in extensions):
                    audio_files.append(f)
            
            logger.info(f"📁 {len(audio_files)} fichiers audio trouvés")
            return audio_files
            
        except Exception as e:
            logger.error(f"❌ Erreur listing fichiers: {e}")
            return []
    
    def download_file(self, file_id: str, file_name: str, download_path: str) -> Optional[str]:
        """Télécharge un fichier depuis Drive"""
        try:
            Path(download_path).mkdir(parents=True, exist_ok=True)
            local_path = os.path.join(download_path, file_name)
            
            request = self.service.files().get_media(fileId=file_id)
            
            with io.FileIO(local_path, 'wb') as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    if status:
                        logger.info(f"⬇️ Téléchargement {int(status.progress() * 100)}%")
            
            logger.info(f"✅ Fichier téléchargé: {local_path}")
            return local_path
            
        except Exception as e:
            logger.error(f"❌ Erreur téléchargement {file_name}: {e}")
            return None


# ============================================================================
# TRANSCRIPTION WHISPER
# ============================================================================

class WhisperTranscriber:
    """Gère la transcription audio avec Whisper"""
    
    def __init__(self, model_name: str = "small", language: str = "fr"):
        self.model_name = model_name
        self.language = language
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Charge le modèle Whisper"""
        try:
            logger.info(f"🔄 Chargement du modèle Whisper '{self.model_name}'...")
            self.model = whisper.load_model(self.model_name)
            logger.info(f"✅ Modèle Whisper '{self.model_name}' chargé")
        except Exception as e:
            logger.error(f"❌ Erreur chargement Whisper: {e}")
            raise
    
    def transcribe(self, audio_path: str) -> Optional[Dict]:
        """Transcrit un fichier audio"""
        try:
            logger.info(f"🎤 Transcription en cours: {audio_path}")
            start_time = time.time()
            
            result = self.model.transcribe(
                audio_path,
                language=self.language,
                verbose=False
            )
            
            duration = time.time() - start_time
            logger.info(f"✅ Transcription terminée en {duration:.1f}s")
            
            return {
                "text": result["text"],
                "segments": result.get("segments", []),
                "language": result.get("language", self.language),
                "duration_seconds": duration
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur transcription {audio_path}: {e}")
            return None


# ============================================================================
# GESTIONNAIRE DE FICHIERS TRAITÉS
# ============================================================================

class ProcessedFilesManager:
    """Gère la persistance des fichiers déjà traités"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.processed = self._load()
    
    def _load(self) -> Dict:
        try:
            if os.path.exists(self.file_path):
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"⚠️ Erreur chargement fichiers traités: {e}")
        return {}
    
    def _save(self):
        try:
            Path(self.file_path).parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(self.processed, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde fichiers traités: {e}")
    
    def is_processed(self, file_id: str) -> bool:
        return file_id in self.processed
    
    def mark_processed(self, file_id: str, file_name: str, transcript_path: str):
        self.processed[file_id] = {
            "name": file_name,
            "transcript": transcript_path,
            "processed_at": datetime.now().isoformat()
        }
        self._save()


# ============================================================================
# DRIVE WATCHER PRINCIPAL
# ============================================================================

class DriveWatcher:
    """Classe principale de surveillance Drive + Transcription"""
    
    def __init__(self, folder_id: str, config: Dict = None):
        self.config = config or CONFIG
        self.folder_id = folder_id
        
        # Authentification OAuth et création du service
        service = get_drive_service(self.config)
        self.drive = DriveService(service)
        
        # Transcription
        self.transcriber = WhisperTranscriber(
            model_name=self.config.get("whisper_model", "small"),
            language=self.config.get("language", "fr")
        )
        
        # Tracking des fichiers traités
        self.processed_manager = ProcessedFilesManager(self.config["processed_file"])
        
        # Créer les dossiers
        Path(self.config["local_download_path"]).mkdir(parents=True, exist_ok=True)
        Path(self.config["local_transcripts_path"]).mkdir(parents=True, exist_ok=True)
        
        logger.info(f"✅ DriveWatcher initialisé pour dossier: {folder_id}")
    
    def process_file(self, file_info: Dict) -> Optional[str]:
        """Traite un fichier: télécharge, transcrit, sauvegarde"""
        file_id = file_info["id"]
        file_name = file_info["name"]
        
        logger.info(f"📄 Traitement de: {file_name}")
        
        # 1. Télécharger
        local_path = self.drive.download_file(
            file_id, file_name, self.config["local_download_path"]
        )
        if not local_path:
            return None
        
        # 2. Transcrire
        result = self.transcriber.transcribe(local_path)
        if not result:
            return None
        
        # 3. Sauvegarder JSON
        transcript_name = Path(file_name).stem + "_transcript.json"
        transcript_path = os.path.join(self.config["local_transcripts_path"], transcript_name)
        
        transcript_data = {
            "source_file": file_name,
            "source_id": file_id,
            "transcribed_at": datetime.now().isoformat(),
            "text": result["text"],
            "segments": result["segments"],
            "processing_time": result["duration_seconds"]
        }
        
        with open(transcript_path, 'w', encoding='utf-8') as f:
            json.dump(transcript_data, f, indent=2, ensure_ascii=False)
        logger.info(f"💾 Transcription JSON: {transcript_path}")
        
        # 4. Sauvegarder TXT
        txt_path = os.path.join(self.config["local_transcripts_path"], Path(file_name).stem + ".txt")
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(f"# Transcription: {file_name}\n")
            f.write(f"# Date: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n")
            f.write(result["text"])
        logger.info(f"📝 Transcription TXT: {txt_path}")
        
        # 5. Marquer comme traité
        self.processed_manager.mark_processed(file_id, file_name, transcript_path)
        
        return transcript_path
    
    def check_and_process(self) -> int:
        """Vérifie les nouveaux fichiers et les traite"""
        logger.info("🔍 Vérification des nouveaux fichiers...")
        
        audio_files = self.drive.list_audio_files(
            self.folder_id, self.config["audio_extensions"]
        )
        
        processed_count = 0
        for file_info in audio_files:
            file_id = file_info["id"]
            file_name = file_info["name"]
            
            if self.processed_manager.is_processed(file_id):
                logger.debug(f"⏭️ Déjà traité: {file_name}")
                continue
            
            result = self.process_file(file_info)
            if result:
                processed_count += 1
                logger.info(f"✅ Traité: {file_name}")
        
        return processed_count
    
    def run_once(self):
        """Exécute une seule vérification"""
        logger.info("🚀 Mode ONE-SHOT")
        count = self.check_and_process()
        logger.info(f"✅ Terminé - {count} fichier(s) traité(s)")
        return count
    
    def run_continuous(self):
        """Mode surveillance continue"""
        logger.info(f"🔄 Mode SURVEILLANCE - toutes les {self.config['check_interval']}s")
        logger.info("   Ctrl+C pour arrêter")
        
        try:
            while True:
                self.check_and_process()
                logger.info(f"💤 Attente {self.config['check_interval']}s...")
                time.sleep(self.config['check_interval'])
        except KeyboardInterrupt:
            logger.info("🛑 Arrêt demandé")


# ============================================================================
# POINT D'ENTRÉE
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Drive Watcher (OAuth) - Surveillance Drive + Transcription Whisper"
    )
    parser.add_argument("folder_id", help="ID du dossier Google Drive")
    parser.add_argument("--once", action="store_true", help="Exécuter une seule fois")
    parser.add_argument("--model", default="small", 
                       choices=["tiny", "base", "small", "medium", "large"],
                       help="Modèle Whisper (défaut: small)")
    parser.add_argument("--interval", type=int, default=60,
                       help="Intervalle en secondes (défaut: 60)")
    
    args = parser.parse_args()
    
    CONFIG["whisper_model"] = args.model
    CONFIG["check_interval"] = args.interval
    
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║  🎙️  DRIVE WATCHER (OAuth) - ICI Dordogne                   ║
    ║  Surveillance Google Drive + Transcription Whisper           ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    try:
        watcher = DriveWatcher(args.folder_id, CONFIG)
        
        if args.once:
            watcher.run_once()
        else:
            watcher.run_continuous()
            
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.error(f"Erreur fatale: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
