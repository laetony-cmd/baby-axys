"""
DRIVE WATCHER (OAuth + ZIP) - Surveillance Google Drive + Transcription Whisper
ICI Dordogne - Axi V19
Date: 09/01/2026

Gère les fichiers ZIP du DJI Mic : télécharge, décompresse, transcrit.
"""

import os
import sys
import json
import time
import logging
import argparse
import zipfile
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

import whisper

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('drive_watcher.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

CONFIG = {
    "oauth_credentials_path": r"C:\axi-v19\client_secret.json",
    "token_path": r"C:\axi-v19\token.json",
    "local_download_path": r"C:\axi-v19\audio_downloads",
    "local_transcripts_path": r"C:\axi-v19\transcriptions",
    "audio_extensions": [".wav", ".m4a", ".mp3", ".ogg", ".flac"],
    "archive_extensions": [".zip"],
    "whisper_model": "small",
    "check_interval": 60,
    "processed_file": r"C:\axi-v19\processed_files.json",
    "language": "fr"
}

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']


def get_drive_service(config: Dict):
    creds = None
    if os.path.exists(config["token_path"]):
        try:
            creds = Credentials.from_authorized_user_file(config["token_path"], SCOPES)
            logger.info("✅ Token existant chargé")
        except Exception as e:
            logger.warning(f"⚠️ Erreur chargement token: {e}")
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                logger.info("✅ Token rafraîchi")
            except:
                creds = None
        
        if not creds:
            if not os.path.exists(config["oauth_credentials_path"]):
                raise FileNotFoundError(f"❌ Fichier OAuth non trouvé: {config['oauth_credentials_path']}")
            
            logger.info("🔐 Authentification OAuth requise...")
            flow = InstalledAppFlow.from_client_secrets_file(config["oauth_credentials_path"], SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(config["token_path"], 'w') as token:
            token.write(creds.to_json())
            logger.info(f"💾 Token sauvegardé")
    
    service = build('drive', 'v3', credentials=creds)
    logger.info("✅ Service Google Drive connecté")
    return service


class DriveService:
    def __init__(self, service):
        self.service = service
    
    def list_files(self, folder_id: str, extensions: List[str]) -> List[Dict]:
        try:
            query = f"'{folder_id}' in parents and trashed=false"
            results = self.service.files().list(
                q=query, spaces='drive',
                fields='files(id, name, mimeType, createdTime, size)',
                orderBy='createdTime desc'
            ).execute()
            
            files = results.get('files', [])
            matched = [f for f in files if any(f.get('name', '').lower().endswith(ext) for ext in extensions)]
            logger.info(f"📁 {len(matched)} fichiers trouvés (extensions: {extensions})")
            return matched
        except Exception as e:
            logger.error(f"❌ Erreur listing: {e}")
            return []
    
    def download_file(self, file_id: str, file_name: str, download_path: str) -> Optional[str]:
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
                        logger.info(f"⬇️ {int(status.progress() * 100)}%")
            
            logger.info(f"✅ Téléchargé: {local_path}")
            return local_path
        except Exception as e:
            logger.error(f"❌ Erreur téléchargement {file_name}: {e}")
            return None


class WhisperTranscriber:
    def __init__(self, model_name: str = "small", language: str = "fr"):
        self.model_name = model_name
        self.language = language
        self.model = None
        self._load_model()
    
    def _load_model(self):
        logger.info(f"🔄 Chargement Whisper '{self.model_name}'...")
        self.model = whisper.load_model(self.model_name)
        logger.info(f"✅ Whisper chargé")
    
    def transcribe(self, audio_path: str) -> Optional[Dict]:
        try:
            logger.info(f"🎤 Transcription: {audio_path}")
            start = time.time()
            result = self.model.transcribe(audio_path, language=self.language, verbose=False)
            duration = time.time() - start
            logger.info(f"✅ Transcrit en {duration:.1f}s")
            return {"text": result["text"], "segments": result.get("segments", []), "duration_seconds": duration}
        except Exception as e:
            logger.error(f"❌ Erreur transcription: {e}")
            return None


class ProcessedFilesManager:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.processed = self._load()
    
    def _load(self) -> Dict:
        try:
            if os.path.exists(self.file_path):
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            pass
        return {}
    
    def _save(self):
        Path(self.file_path).parent.mkdir(parents=True, exist_ok=True)
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(self.processed, f, indent=2, ensure_ascii=False)
    
    def is_processed(self, file_id: str) -> bool:
        return file_id in self.processed
    
    def mark_processed(self, file_id: str, file_name: str, transcript_path: str):
        self.processed[file_id] = {"name": file_name, "transcript": transcript_path, "processed_at": datetime.now().isoformat()}
        self._save()


def extract_audio_from_zip(zip_path: str, extract_dir: str, audio_extensions: List[str]) -> List[str]:
    """Extrait les fichiers audio d'un ZIP"""
    audio_files = []
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for name in zf.namelist():
                if any(name.lower().endswith(ext) for ext in audio_extensions):
                    zf.extract(name, extract_dir)
                    extracted_path = os.path.join(extract_dir, name)
                    audio_files.append(extracted_path)
                    logger.info(f"📦 Extrait: {name}")
    except Exception as e:
        logger.error(f"❌ Erreur extraction ZIP: {e}")
    return audio_files


class DriveWatcher:
    def __init__(self, folder_id: str, config: Dict = None):
        self.config = config or CONFIG
        self.folder_id = folder_id
        
        service = get_drive_service(self.config)
        self.drive = DriveService(service)
        self.transcriber = WhisperTranscriber(self.config.get("whisper_model", "small"), self.config.get("language", "fr"))
        self.processed_manager = ProcessedFilesManager(self.config["processed_file"])
        
        Path(self.config["local_download_path"]).mkdir(parents=True, exist_ok=True)
        Path(self.config["local_transcripts_path"]).mkdir(parents=True, exist_ok=True)
        
        logger.info(f"✅ DriveWatcher initialisé pour: {folder_id}")
    
    def process_file(self, file_info: Dict) -> Optional[str]:
        file_id = file_info["id"]
        file_name = file_info["name"]
        
        logger.info(f"📄 Traitement: {file_name}")
        
        # Télécharger
        local_path = self.drive.download_file(file_id, file_name, self.config["local_download_path"])
        if not local_path:
            return None
        
        # Si ZIP, extraire les fichiers audio
        audio_files = []
        if file_name.lower().endswith('.zip'):
            extract_dir = os.path.join(self.config["local_download_path"], Path(file_name).stem)
            audio_files = extract_audio_from_zip(local_path, extract_dir, self.config["audio_extensions"])
            if not audio_files:
                logger.warning(f"⚠️ Aucun audio dans le ZIP: {file_name}")
                return None
        else:
            audio_files = [local_path]
        
        # Transcrire chaque fichier audio
        all_text = []
        for audio_path in audio_files:
            result = self.transcriber.transcribe(audio_path)
            if result:
                all_text.append(result["text"])
        
        if not all_text:
            return None
        
        # Sauvegarder
        transcript_name = Path(file_name).stem + "_transcript.json"
        transcript_path = os.path.join(self.config["local_transcripts_path"], transcript_name)
        
        full_text = "\n\n".join(all_text)
        transcript_data = {
            "source_file": file_name,
            "source_id": file_id,
            "transcribed_at": datetime.now().isoformat(),
            "text": full_text,
            "audio_files_count": len(audio_files)
        }
        
        with open(transcript_path, 'w', encoding='utf-8') as f:
            json.dump(transcript_data, f, indent=2, ensure_ascii=False)
        logger.info(f"💾 JSON: {transcript_path}")
        
        # TXT
        txt_path = os.path.join(self.config["local_transcripts_path"], Path(file_name).stem + ".txt")
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(f"# Transcription: {file_name}\n")
            f.write(f"# Date: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n")
            f.write(f"# Fichiers audio: {len(audio_files)}\n\n")
            f.write(full_text)
        logger.info(f"📝 TXT: {txt_path}")
        
        self.processed_manager.mark_processed(file_id, file_name, transcript_path)
        return transcript_path
    
    def check_and_process(self) -> int:
        logger.info("🔍 Vérification...")
        
        # Chercher ZIP et fichiers audio directs
        all_extensions = self.config["audio_extensions"] + self.config["archive_extensions"]
        files = self.drive.list_files(self.folder_id, all_extensions)
        
        count = 0
        for f in files:
            if self.processed_manager.is_processed(f["id"]):
                continue
            # Ignorer les raccourcis Google
            if f.get("mimeType") == "application/vnd.google-apps.shortcut":
                logger.info(f"⏭️ Raccourci ignoré: {f['name']}")
                continue
            if self.process_file(f):
                count += 1
        
        return count
    
    def run_once(self):
        logger.info("🚀 Mode ONE-SHOT")
        count = self.check_and_process()
        logger.info(f"✅ Terminé - {count} fichier(s)")
        return count
    
    def run_continuous(self):
        logger.info(f"🔄 Mode SURVEILLANCE ({self.config['check_interval']}s)")
        try:
            while True:
                self.check_and_process()
                time.sleep(self.config['check_interval'])
        except KeyboardInterrupt:
            logger.info("🛑 Arrêt")


def main():
    parser = argparse.ArgumentParser(description="Drive Watcher (OAuth + ZIP)")
    parser.add_argument("folder_id", help="ID du dossier Google Drive")
    parser.add_argument("--once", action="store_true", help="Exécuter une seule fois")
    parser.add_argument("--model", default="small", choices=["tiny", "base", "small", "medium", "large"])
    parser.add_argument("--interval", type=int, default=60)
    
    args = parser.parse_args()
    CONFIG["whisper_model"] = args.model
    CONFIG["check_interval"] = args.interval
    
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║  🎙️  DRIVE WATCHER (ZIP) - ICI Dordogne                     ║
    ║  Surveillance Google Drive + Transcription Whisper           ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    try:
        watcher = DriveWatcher(args.folder_id, CONFIG)
        if args.once:
            watcher.run_once()
        else:
            watcher.run_continuous()
    except Exception as e:
        logger.error(f"Erreur: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
