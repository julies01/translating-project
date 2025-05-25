import streamlit as st
import tempfile
import os
import glob
import glob
from backend import process_video
import uuid
from datetime import datetime
import unicodedata
import re

# Configuration de la page pour utiliser toute la largeur
st.set_page_config(page_title="Video Translator", layout="wide")

def get_text(key):
    """Retourne le texte dans la langue sélectionnée"""
    texts = {
        "fr": {
            "title": "🎬 Traducteur de Vidéo Automatique",
            "history": "🕑  Historique des traductions",
            "upload": "Télécharge ta vidéo à traduire (format mp4)",
            "choose_lang": "Choisis la langue de traduction :",
            "translate_audio": "Traduire l'audio",
            "add_subtitles": "Ajouter les sous-titres",
            "translate_btn": "Traduire la vidéo",
            "view_translation": "Voir traduction",
            "download_video": "Télécharger la vidéo traduite",
            "download_srt": "Télécharger les sous-titres (SRT)",
            "translation_complete": "✅ Traduction terminée !",
            "select_option": "Veuillez sélectionner au moins une option : Traduire l'audio ou Ajouter les sous-titres.",
            "having_issue": "Vous rencontrez un problème ?",
            "go_readme": "Voir le README",
            "submit_issue": "Signaler un problème"
        },
        "en": {
            "title": "🎬 Automatic Video Translator",
            "history": "🕑  Translation History",
            "upload": "Upload your video to translate (mp4 format)",
            "choose_lang": "Choose translation language :",
            "translate_audio": "Translate audio",
            "add_subtitles": "Add subtitles",
            "translate_btn": "Translate video",
            "view_translation": "View translation",
            "download_video": "Download translated video",
            "download_srt": "Download subtitles (SRT)",
            "translation_complete": "✅ Translation completed!",
            "select_option": "Please select at least one option: Translate audio or Add subtitles.",
            "having_issue": "Having an issue ?",
            "go_readme": "Go to README",
            "submit_issue": "Submit an Issue"
        },
        "zh": {
            "title": "🎬 自动视频翻译器",
            "history": "🕑  翻译历史",
            "upload": "上传您要翻译的视频（mp4格式）",
            "choose_lang": "选择翻译语言：",
            "translate_audio": "翻译音频",
            "add_subtitles": "添加字幕",
            "translate_btn": "翻译视频",
            "view_translation": "查看翻译",
            "download_video": "下载翻译视频",
            "download_srt": "下载字幕（SRT）",
            "translation_complete": "✅ 翻译完成！",
            "select_option": "请至少选择一个选项：翻译音频或添加字幕。",
            "having_issue": "遇到问题了吗？",
            "go_readme": "查看说明文档",
            "submit_issue": "提交问题"
        }
    }
    lang = st.session_state.get('interface_lang', 'fr')
    return texts[lang].get(key, key)

HISTORY_DIR = "history"
os.makedirs(HISTORY_DIR, exist_ok=True)

# Initialiser la langue par défaut
if 'interface_lang' not in st.session_state:
    st.session_state.interface_lang = "en"

# Créer les boutons de langue en haut à droite avec une approche plus simple
col_main, col_lang = st.columns([0.85, 0.15])

with col_lang:
    lang_col1, lang_col2, lang_col3 = st.columns(3)
    
    with lang_col1:
        if st.button("🇫🇷", key="lang_fr", help="Français"):
            st.session_state.interface_lang = "fr"
            st.rerun()
    
    with lang_col2:
        if st.button("🇬🇧", key="lang_en", help="English"):
            st.session_state.interface_lang = "en"
            st.rerun()
    
    with lang_col3:
        if st.button("🇨🇳", key="lang_zh", help="中文"):
            st.session_state.interface_lang = "zh"
            st.rerun()

# CSS simplifié pour améliorer l'apparence
st.markdown("""
<style>
    .main .block-container {
        max-width: none;
        padding-top: 1rem;
    }
    
   .stButton > button {
        width: 100%;
        font-size: 1.2rem;
        background-color: #f0f2f6 !important;
        color: black !important;
        border: none !important;
        border-radius: 0.5rem !important;
        padding: 0.5rem 1rem !important;
        transition: background-color 0.3s ease !important;
    }
    
    .stButton > button:hover {
        background-color: #f0f2f6 !important;
        color: black !important;
    }
    
    .stButton > button:focus {
        background-color: #f0f2f6 !important;
        color: black !important;
        box-shadow: 0 0 0 2px rgba(108, 123, 127, 0.3) !important;
    }
    
    
    [data-testid="stFileUploader"] label p {
        font-size: 1.4rem !important;
        font-weight: 600 !important;
    }
    
    [data-testid="stSelectbox"] label p {
        font-size: 1.4rem !important;
        font-weight: 600 !important;
    }
    
    .stFileUploader > label {
         margin-bottom: 1rem !important;
    }
    
     .stSelectbox > label {
         margin-bottom: 1rem !important;
    }
    
     .stCheckbox {
        display: flex;
        justify-content: center;
        align-items: center;
    }
    
    .stCheckbox > label {
        display: flex;
        justify-content: center;
        align-items: center;
        width: 100%;
    }
    
    .stDownloadButton {
        display: flex !important;
        justify-content: center !important;
    }
    
    .stDownloadButton > button {
        margin: 0 auto !important;
    }
            
</style>
""", unsafe_allow_html=True)

def get_history_groups():
    folders = sorted(glob.glob(os.path.join(HISTORY_DIR, "*")), reverse=True)
    groups = {}
    for folder in folders:
        basename = os.path.basename(folder)
        parts = basename.split('_')
        if len(parts) >= 3:
            date_str = parts[-3]
            time_str = parts[-2]
            date_fmt = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            title = "_".join(parts[:-3])
        else:
            date_fmt = "Inconnu"
            title = basename
        groups.setdefault(date_fmt, []).append((folder, title))
    return groups

# Volet historique dans la sidebar
st.sidebar.title(get_text("history"))
st.sidebar.markdown("")  # Ajouter de l'espace vide
st.sidebar.markdown("")  
history_groups = get_history_groups()
for date, items in history_groups.items():
    st.sidebar.markdown(f"**{date}**")
    for folder, title in items:
        original = os.path.join(folder, "original.mp4")
        translated = os.path.join(folder, "translated.mp4")
        srt = os.path.join(folder, "translated.srt")
        if os.path.exists(original) and os.path.exists(translated):
            with st.sidebar.expander(title):
                st.video(original, format="video/mp4", start_time=0)
                
                # Bouton pour voir la traduction
                if st.button(get_text("view_translation"), key=f"view_{folder}"):
                    # Afficher dans la zone principale
                    st.session_state.selected_video = translated
                    st.session_state.selected_srt = srt if os.path.exists(srt) else None
                    st.rerun()
                
                # Bouton de téléchargement pour la vidéo traduite
                if os.path.exists(translated):
                    with open(translated, "rb") as f:
                        st.download_button(
                            get_text("download_video"),
                            data=f.read(),
                            file_name=f"{title}_traduite.mp4",
                            mime="video/mp4",
                            key=f"dl_video_{folder}"
                        )
                
                # Bouton de téléchargement pour le SRT
                if os.path.exists(srt):
                    with open(srt, "r", encoding="utf-8") as f:
                        st.download_button(
                            get_text("download_srt"),
                            data=f.read(),
                            file_name=f"{title}_sous-titres.srt",
                            mime="text/plain",
                            key=f"dl_srt_{folder}"
                        )

st.title(get_text("title"))

# Ajouter de l'espace vide après le titre
st.markdown("")
st.markdown("")
st.markdown("")
st.markdown("")

# Affichage de la vidéo sélectionnée depuis l'historique
if 'selected_video' in st.session_state and st.session_state.selected_video:
    st.subheader("📹 " + get_text("view_translation"))
    
    # Utiliser des colonnes pour limiter la taille de la vidéo
    col_video, col_empty = st.columns([0.6, 0.4])
    
    with col_video:
        st.video(st.session_state.selected_video)
    
    if 'selected_srt' in st.session_state and st.session_state.selected_srt:
        with open(st.session_state.selected_srt, "r", encoding="utf-8") as f:
            st.download_button(
                get_text("download_srt"),
                data=f.read(),
                file_name="sous-titres.srt",
                mime="text/plain"
            )
    st.divider()


uploaded_file = st.file_uploader(get_text("upload"), type=["mp4"])

# Langues de traduction traduites selon la langue de l'interface
def get_languages():
    lang = st.session_state.get('interface_lang', 'fr')
    if lang == "fr":
        return {
            "Français": "fr",
            "Anglais": "en", 
            "Chinois": "zh",
            "Espagnol": "es",
            "Allemand": "de",
            "Italien": "it",
            "Néerlandais": "nl",
            "Portugais": "pt",
            "Russe": "ru"
        }
    elif lang == "en":
        return {
            "French": "fr",
            "English": "en",
            "Chinese": "zh", 
            "Spanish": "es",
            "German": "de",
            "Italian": "it",
            "Dutch": "nl",
            "Portuguese": "pt",
            "Russian": "ru"
        }
    else:  # zh
        return {
            "法语": "fr",
            "英语": "en",
            "中文": "zh",
            "西班牙语": "es", 
            "德语": "de",
            "意大利语": "it",
            "荷兰语": "nl",
            "葡萄牙语": "pt",
            "俄语": "ru"
        }

LANGUAGES = get_languages()

st.markdown("")
st.markdown("")
st.markdown("") 

tgt_lang_label = st.selectbox(get_text("choose_lang"), list(LANGUAGES.keys()), index=0)
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
st.markdown("")
st.markdown("") 

def slugify(value):
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    return re.sub(r'[-\s]+', '-', value)

def slugify(value):
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    return re.sub(r'[-\s]+', '-', value)

def slugify(value):
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    return re.sub(r'[-\s]+', '-', value)

if uploaded_file is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_input:
        tmp_input.write(uploaded_file.read())
        tmp_input_path = tmp_input.name

    
    col_empty_1, col_video_upload, col_empty_2 = st.columns([0.25, 0.5, 0.25])

    with col_video_upload:
        st.video(tmp_input_path)
    st.markdown("") 


    col1, col2, col3, col4 = st.columns(4)
    with col2:
        translate_audio = st.checkbox(get_text("translate_audio"), value=True)
    with col3:
        add_subtitles = st.checkbox(get_text("add_subtitles"), value=True)

    st.markdown("")  
    st.markdown("")  

    if st.button(get_text("translate_btn")):
        if not (translate_audio or add_subtitles):
            st.error(get_text("select_option"))
        else:
            st.markdown("")  
            st.markdown("")  

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
                os.path.join(save_dir, "translated.mp4"),
                tgt_lang=tgt_lang,
                translate_audio=translate_audio,
                add_subtitles=add_subtitles,
                progress_callback=progress_callback,
                status_callback=status_callback,
                save_dir=save_dir
                status_callback=status_callback,
                save_dir=save_dir
            )
            
            status_placeholder.success(get_text("translation_complete"))
            
            # Affichage de la vidéo traduite dans la colonne principale
            col_final_empty_1, col_final_video, col_final_empty_2 = st.columns([0.25, 0.5, 0.25])
            
            with col_final_video:
                st.video(result["translated_video"])
            
            st.markdown("")  
            st.markdown("")  
            
            # Boutons de téléchargement dans la colonne principale
            col_dl1, col_dl2, col_dl3, col_dl4 = st.columns(4)
            
            with col_dl2:
                with open(result["translated_video"], "rb") as f:
                    st.download_button(
                        label=get_text("download_video"),
                        data=f,
                        file_name="video_traduite.mp4",
                        mime="video/mp4"
                    )

            
            with col_dl3:
                # Bouton de téléchargement pour le SRT (si les sous-titres ont été générés)
                if add_subtitles and os.path.exists(result["srt"]):
                    with open(result["srt"], "r", encoding="utf-8") as f:
                        st.download_button(
                            label=get_text("download_srt"),
                            data=f.read(),
                            file_name="sous-titres.srt",
                            mime="text/plain"
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

st.markdown("---")  # Ligne de séparation
st.markdown(f"### {get_text('having_issue')}")
col_help1, col_help2, col_empty = st.columns([0.15, 0.15, 0.7])

with col_help1:
    st.link_button(
         get_text("go_readme"),
        "https://github.com/julies01/translating-project/blob/branche-principale/README.md"
    )

with col_help2:
    st.link_button(
         get_text("submit_issue"), 
        "https://github.com/julies01/translating-project/issues/new"
    )