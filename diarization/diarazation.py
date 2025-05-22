import os
import glob
import subprocess
import deepl
from pathlib import Path
import torch
from transformers import pipeline
from faster_whisper import WhisperModel
from pyannote.audio import Pipeline  
import creds

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
   
    try:
        # Chargement du modèle de diarisation de PyAnnote
        # Vous aurez besoin d'un token d'accès HuggingFace pour utiliser ce modèle
        pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1",
                                        use_auth_token=creds.pyannote_token)
        
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
        print(f"Error in diarization in diarize audio: {e}")
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