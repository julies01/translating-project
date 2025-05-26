import streamlit as st

"""
@brief Retourne le texte traduit dans la langue d'interface sélectionnée

@param key Clé du texte à traduire (ex: "title", "upload", "translate_btn")
@return Texte traduit dans la langue courante ou la clé si traduction non trouvée
"""

def get_text(key):
    """Retourne le texte dans la langue sélectionnée"""
    texts = {
        "fr": {
            "title": "🎬 Traducteur de Vidéo Automatique",
            "history": "🕑  Historique des traductions",
            "upload": "Télécharge ta vidéo à traduire (MP4, MOV, AVI, WMV, etc.)",
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
            "upload": "Upload your video to translate (MP4, MOV, AVI, WMV, etc.)",
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
            "upload": "上传您要翻译的视频（MP4, MOV, AVI, WMV等）",
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

"""
@brief Retourne la liste des langues de traduction disponibles dans la langue d'interface

@return Dictionnaire {nom_langue_affiché: code_langue} selon la langue d'interface
"""

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