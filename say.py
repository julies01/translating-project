import os
import glob
import subprocess
import creds
import deepl
from pathlib import Path
import torch
from transformers import pipeline
from faster_whisper import WhisperModel
from pyannote.audio import Pipeline  # Ajouté pour la diarisation
import numpy as np

translator = deepl.Translator(creds.auth_key)

os.environ["TOKENIZERS_PARALLELISM"] = "false"  # Avoid warnings
os.environ["USE_TORCH"] = "1"  # Force use of PyTorch
os.environ["USE_TF"] = "0"  # Disable TensorFlow

# Configuration optimisée pour Mac M2
if torch.backends.mps.is_available():
    print("Using MPS (Metal Performance Shaders) for acceleration on Mac M2")
    device = "mps"  # Utiliser l'accélération Metal sur Mac M2
else:
    device = "cpu"

def install_requirements():
    """Installe les dépendances nécessaires pour le script."""
    try:
        # Liste des packages requis
        required_packages = [
            "torch",
            "pyannote.audio",
            "faster_whisper",
            "transformers",
            "deepl",
            "numpy"
        ]
        
        # Installation des packages
        for package in required_packages:
            print(f"Installation de {package}...")
            subprocess.run(["pip", "install", package], check=True)
            
        # Installation spécifique pour PyAnnote
        print("Installation des dépendances PyAnnote...")
        subprocess.run(["pip", "install", "pyannote.audio"], check=True)
        
        print("Toutes les dépendances ont été installées avec succès!")
    except Exception as e:
        print(f"Erreur lors de l'installation des dépendances: {e}")
        print("Veuillez installer manuellement les packages requis.")


# Fonction principale améliorée
def main():
    # Vérifier si les dépendances sont installées
    try:
        import torch
        import pyannote.audio
    except ImportError:
        print("Certaines dépendances sont manquantes. Installation en cours...")
        install_requirements()
    
    # Sélection de la vidéo et de la langue cible
    video_files = glob.glob(os.path.join(video_dir, "*.mp4")) + glob.glob(os.path.join(video_dir, "*.avi")) + glob.glob(os.path.join(video_dir, "*.mov"))
    
    if not video_files:
        print("Aucun fichier vidéo trouvé dans le répertoire courant.")
        return
    
    print("Fichiers vidéo disponibles:")
    for i, video in enumerate(video_files):
        print(f"{i+1}. {os.path.basename(video)}")
    
    selection = input("Sélectionnez le numéro de la vidéo à traiter (ou 'q' pour quitter): ")
    if selection.lower() == 'q':
        return
    
    try:
        video_index = int(selection) - 1
        if video_index < 0 or video_index >= len(video_files):
            print("Sélection invalide.")
            return
    except ValueError:
        print("Veuillez entrer un numéro valide.")
        return
    
    selected_video = video_files[video_index]
    
    # Liste des langues disponibles
    languages = {
        "1": "FR",  # Français
        "2": "EN",  # Anglais
        "3": "DE",  # Allemand
        "4": "ES",  # Espagnol
        "5": "IT",  # Italien
        "6": "JA",  # Japonais
        "7": "ZH",  # Chinois
    }
    
    print("\nLangues cibles disponibles:")
    for key, lang in languages.items():
        print(f"{key}. {lang}")
    
    lang_selection = input("Sélectionnez le numéro de la langue cible (ou 'q' pour quitter): ")
    if lang_selection.lower() == 'q':
        return
    
    if lang_selection not in languages:
        print("Sélection de langue invalide.")
        return
    
    selected_lang = languages[lang_selection]
    
    # Traitement de la vidéo
    essai(selected_video, selected_lang)
    print(f"Traitement terminé! La vidéo avec sous-titres est disponible: {output_video}")


if __name__ == "__main__":
    main()


def transcribe_video_with_diarization(video_path):
    print(f"Transcribing {video_path} with speaker diarization...")

    # Using faster-whisper for better performance
    model_size = "medium"  # Vous pouvez utiliser "small" si "medium" est trop lent
    # Utilisation du device défini au début du script (mps ou cpu)
    compute_type = "float16" if device == "mps" else "int8"

    # Load the Whisper model
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    # First, detect language by running with language=None
    _, info = model.transcribe(
        video_path, language=None, task="transcribe", vad_filter=True
    )
    print(f"Detected language: {info.language}")

    # Now, transcribe with the detected language code
    segments, _ = model.transcribe(
        video_path, language=info.language, task="transcribe", vad_filter=True
    )

    # Extract audio from video for diarization
    audio_path = extract_audio(video_path)
    
    try:
        # Perform speaker diarization
        print("Starting speaker diarization (this may take some time)...")
        speaker_segments = diarize_audio(audio_path)
        
        # Merge transcription with speaker information
        enriched_segments = merge_transcription_with_diarization(segments, speaker_segments)
        
        # Format as SRT with speaker indicators
        srt_content = []
        for i, segment in enumerate(enriched_segments, 1):
            start = format_timestamp(segment["start"])
            end = format_timestamp(segment["end"])
            
            # Format text with speakers
            if len(segment["speakers"]) > 1:
                # Multiple speakers - add dashes and newlines
                speaker_lines = []
                for speaker in segment["speakers"]:
                    speaker_lines.append(f"- {segment['text']}")
                text = "\n".join(speaker_lines)
            else:
                # Single speaker - no need for dash or special formatting
                text = segment["text"].strip()
            
            srt_content.append(f"{i}\n{start} --> {end}\n{text}\n")
    except Exception as e:
        print(f"Error during diarization: {e}")
        print("Falling back to standard transcription without speaker detection...")
        srt_content = []
        for i, segment in enumerate(segments, 1):
            start = format_timestamp(segment.start)
            end = format_timestamp(segment.end)
            text = segment.text.strip()
            srt_content.append(f"{i}\n{start} --> {end}\n{text}\n")

    # Clean up temp audio file
    if os.path.exists(audio_path):
        os.remove(audio_path)
        
    return srt_content


def extract_audio(video_path):
    """Extract audio from video file for diarization processing."""
    audio_path = os.path.splitext(video_path)[0] + "_temp_audio.wav"
    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-ac", "1",  # Convert to mono
        "-ar", "16000",  # 16kHz sample rate (standard pour les modèles de reconnaissance vocale)
        "-vn",  # No video
        "-acodec", "pcm_s16le",  # Format audio non compressé pour meilleur traitement
        audio_path
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return audio_path
    except subprocess.CalledProcessError as e:
        print(f"Erreur lors de l'extraction audio: {e}")
        return None


def diarize_audio(audio_path):
    """
    Effectue la diarisation d'un fichier audio pour identifier les différents locuteurs.
    
    Args:
        audio_path: Chemin vers le fichier audio
        
    Returns:
        Une liste de segments avec les identifiants de locuteurs
    """
    try:
        # Chargement du modèle de diarisation de PyAnnote
        # Vous aurez besoin d'un token d'accès HuggingFace pour utiliser ce modèle
        pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1",
                                        use_auth_token="VOTRE_TOKEN_HUGGINGFACE")
        
        # Configuration pour utiliser le CPU ou MPS si disponible
        if device == "mps":
            # PyAnnote ne supporte pas directement MPS, donc fallback à CPU
            pipeline.to("cpu")
        else:
            pipeline.to(device)
        
        # Exécution de la diarisation
        diarization = pipeline(audio_path)
        
        # Extraction des segments de locuteurs
        speaker_segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            speaker_segments.append({
                "start": turn.start,
                "end": turn.end,
                "speaker": speaker
            })
        
        return speaker_segments
    except Exception as e:
        print(f"Error in diarization: {e}")
        # En cas d'erreur, retourner une liste vide
        return []


def merge_transcription_with_diarization(segments, speaker_segments, time_tolerance=0.5):
    """
    Fusionne les données de transcription avec les informations de diarisation
    
    Args:
        segments: Segments de transcription de Whisper
        speaker_segments: Liste des segments de locuteurs issus de la diarisation
        time_tolerance: Tolérance de chevauchement en secondes
        
    Returns:
        Transcription enrichie avec les identifiants de locuteurs
    """
    enriched_segments = []
    
    for segment in segments:
        # Convertir le segment Whisper en dictionnaire
        segment_dict = {
            "start": segment.start,
            "end": segment.end,
            "text": segment.text
        }
        
        # Trouver les locuteurs qui parlent pendant ce segment
        speakers = set()
        for speaker_segment in speaker_segments:
            # Vérifier si les segments se chevauchent
            if (speaker_segment["start"] <= segment.end + time_tolerance and 
                speaker_segment["end"] >= segment.start - time_tolerance):
                speakers.add(speaker_segment["speaker"])
        
        # Ajouter l'information des locuteurs au segment
        segment_dict["speakers"] = list(speakers)
        enriched_segments.append(segment_dict)
    
    return enriched_segments


def format_timestamp(seconds):
    """Convert seconds to SRT timestamp format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    seconds = seconds % 60
    milliseconds = int((seconds - int(seconds)) * 1000)

    return f"{hours:02d}:{minutes:02d}:{int(seconds):02d},{milliseconds:03d}"


def translate_text(text, target_lang):
    if not text.strip():
        return ""

    translated = translator.translate_text(text, target_lang=target_lang)
    return translated.text


def put_subtitle_on_video(video_path, srt_path):
    cmd = [
    "ffmpeg",
    "-i", video_path,
    "-vf", f"subtitles={srt_path}:force_style='FontName=Arial,FontSize=24,PrimaryColour=&HFFFFFF&'",
    "-c:a", "copy",  # Keep original audio
    output_video
    ]
    subprocess.run(cmd, check=True)
    print("Subtitles burned successfully!")


def essai(video_path, selected_lang):
    video_filename = Path(video_path).stem
    srt_path = f"{video_filename}.srt"
    native_srt_path = f"{video_filename}_native.srt"

    # Utiliser la nouvelle fonction de transcription avec diarisation
    srt_content = transcribe_video_with_diarization(video_path)
    print(f"Translating subtitles for {video_path}...")

    with open(native_srt_path, "w", encoding="utf-8") as f:
        f.writelines(srt_content)

    # Translate only the subtitle text lines, keep timestamps and numbering
    translated_srt = []
    for line in srt_content:
        parts = line.split('\n')
        if len(parts) >= 3:
            # Si le texte contient des tirets (plusieurs locuteurs), traduire chaque ligne séparément
            if "-" in parts[2]:
                speaker_lines = parts[2].split('\n')
                translated_lines = []
                for speaker_line in speaker_lines:
                    translated_line = translate_text(speaker_line, selected_lang)
                    translated_lines.append(translated_line)
                parts[2] = '\n'.join(translated_lines)
            else:
                # Traduire normalement pour un seul locuteur
                parts[2] = translate_text(parts[2], selected_lang)
            translated_srt.append('\n'.join(parts) + '\n')
        else:
            translated_srt.append(line)
    
    with open(srt_path, "w", encoding="utf-8") as f:
        f.writelines(translated_srt)

    put_subtitle_on_video(video_path, srt_path)