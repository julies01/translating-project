import streamlit as st
import tempfile
import os
import glob
from backend import process_video
import uuid
from datetime import datetime
import unicodedata
import re

HISTORY_DIR = "history"
os.makedirs(HISTORY_DIR, exist_ok=True)

def get_history_groups():
    folders = sorted(glob.glob(os.path.join(HISTORY_DIR, "*")), reverse=True)
    groups = {}
    for folder in folders:
        basename = os.path.basename(folder)
        # Extrait la date au début du nom du dossier (format: nom-XX_YYYYMMDD_UUID)
        parts = basename.split('_')
        if len(parts) >= 2:
            date_str = parts[-2][:8]  # YYYYMMDD
            date_fmt = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
        else:
            date_fmt = "Inconnu"
        groups.setdefault(date_fmt, []).append(folder)
    return groups

# Volet historique dans la sidebar
st.sidebar.title("🕑 Historique des traductions")
history_groups = get_history_groups()
for date, folders in history_groups.items():
    st.sidebar.markdown(f"**{date}**")
    for folder in folders:
        original = os.path.join(folder, "original.mp4")
        translated = os.path.join(folder, "translated.mp4")
        srt = os.path.join(folder, "translated.srt")
        if os.path.exists(original) and os.path.exists(translated):
            label = os.path.basename(folder)
            with st.sidebar.expander(label):
                st.video(original, format="video/mp4", start_time=0)
                if st.button("Voir la traduction", key=folder):
                    st.video(translated)
                    if os.path.exists(srt):
                        with open(srt, "r", encoding="utf-8") as f:
                            st.download_button("Télécharger le SRT", f, file_name="sous-titres.srt")

st.title("🎬 Traducteur de Vidéo Automatique")

uploaded_file = st.file_uploader("Télécharge ta vidéo à traduire (format mp4)", type=["mp4"])

LANGUAGES = {
    "Français": "fr",
    "Anglais": "en",
    "Chinois (simplifié)": "zh",
    "Espagnol": "es",
    "Allemand": "de",
    "Italien": "it",
    "Néerlandais": "nl",
    "Portugais": "pt",
    "Russe": "ru"
}
tgt_lang_label = st.selectbox("Choisis la langue de traduction :", list(LANGUAGES.keys()), index=0)
tgt_lang = LANGUAGES[tgt_lang_label]

def slugify(value):
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    return re.sub(r'[-\s]+', '-', value)

if uploaded_file is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_input:
        tmp_input.write(uploaded_file.read())
        tmp_input_path = tmp_input.name

    st.video(tmp_input_path)

    col1, col2 = st.columns(2)
    with col1:
        translate_audio = st.checkbox("Traduire l'audio", value=True)
    with col2:
        add_subtitles = st.checkbox("Ajouter les sous-titres", value=True)

    if st.button("Traduire la vidéo"):
        if not (translate_audio or add_subtitles):
            st.error("Veuillez sélectionner au moins une option : Traduire l'audio ou Ajouter les sous-titres.")
        else:
            status_placeholder = st.empty()
            progress_bar = st.progress(0)

            def progress_callback(val):
                progress_bar.progress(val)

            def status_callback(msg):
                status_placeholder.text(msg)

            filename = os.path.splitext(uploaded_file.name)[0]
            filename = slugify(filename)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            save_dir = os.path.join(
                HISTORY_DIR,
                f"{filename}-{tgt_lang.upper()}_{timestamp}_{unique_id}"
            )

            result = process_video(
                tmp_input_path,
                os.path.join(save_dir, "translated.mp4"),
                tgt_lang=tgt_lang,
                translate_audio=translate_audio,
                add_subtitles=add_subtitles,
                progress_callback=progress_callback,
                status_callback=status_callback,
                save_dir=save_dir
            )
            status_placeholder.success("✅ Traduction terminée !")
            with open(result["translated_video"], "rb") as f:
                st.download_button(
                    label="Télécharger la vidéo traduite",
                    data=f,
                    file_name="video_traduite.mp4",
                    mime="video/mp4"
                )
            st.video(result["translated_video"])
    os.remove(tmp_input_path)

