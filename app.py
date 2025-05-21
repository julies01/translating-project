import streamlit as st
import tempfile
import os
from backend import process_video

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

            output_path = tmp_input_path.replace(".mp4", "_translated.mp4")
            process_video(
                tmp_input_path,
                output_path,
                tgt_lang=tgt_lang,
                translate_audio=translate_audio,
                add_subtitles=add_subtitles,
                progress_callback=progress_callback,
                status_callback=status_callback
            )
            status_placeholder.success("✅ Traduction terminée !")
            with open(output_path, "rb") as f:
                st.download_button(
                    label="Télécharger la vidéo traduite",
                    data=f,
                    file_name="video_traduite.mp4",
                    mime="video/mp4"
                )
            st.video(output_path)
            os.remove(output_path)
    os.remove(tmp_input_path)