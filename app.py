import streamlit as st
import tempfile
import os
import glob
from backend import process_video
import uuid
from datetime import datetime
import unicodedata
import re
import language_config as lc


# Configure page to use full width
st.set_page_config(page_title="Video Translator", layout="wide")

# @brief Load external CSS file and inject it into the Streamlit app
# @param file_name Name of the CSS file to load
# @return None
# @details Reads the CSS file and uses st.markdown with unsafe_allow_html to inject styles

def load_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# Load CSS styles
load_css('style.css')

# History directory setup
HISTORY_DIR = "history"
os.makedirs(HISTORY_DIR, exist_ok=True)

# Initialize default language
if 'interface_lang' not in st.session_state:
    st.session_state.interface_lang = "en"

# Create language selection buttons in top right corner
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

# @brief Group translation history folders by date
# @return Dictionary with dates as keys and list of (folder, title) tuples as values
# @details Scans the history directory for translation folders, extracts date and time 
#          information from folder names with format: title_YYYYMMDD_HHMMSS_uniqueid,
#          and groups them by date for organized display in the sidebar

def get_history_groups():
    folders = sorted(glob.glob(os.path.join(HISTORY_DIR, "*")), reverse=True)
    groups = {}
    for folder in folders:
        basename = os.path.basename(folder)
        parts = basename.split('_')
        if len(parts) >= 3:
            date_str = parts[-3]
            time_str = parts[-2]
            # Format date as YYYY-MM-DD
            date_fmt = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            title = "_".join(parts[:-3])
        else:
            date_fmt = "Unknown"
            title = basename
        groups.setdefault(date_fmt, []).append((folder, title))
    return groups

# History panel in sidebar
st.sidebar.title(lc.get_text("history"))
st.sidebar.markdown("")  # Add empty space
st.sidebar.markdown("")  
history_groups = get_history_groups()

# Display history grouped by date
for date, items in history_groups.items():
    st.sidebar.markdown(f"**{date}**")
    for folder, title in items:
        original = os.path.join(folder, "original.mp4")
        translated = os.path.join(folder, "translated.mp4")
        srt = os.path.join(folder, "translated.srt")
        
        # Only show items that have both original and translated videos
        if os.path.exists(original) and os.path.exists(translated):
            with st.sidebar.expander(title):
                # Display original video preview
                st.video(original, format="video/mp4", start_time=0)
                
                # Button to view translation in main area
                if st.button(lc.get_text("view_translation"), key=f"view_{folder}"):
                    st.session_state.sidebar_video = translated
                    st.session_state.sidebar_srt = srt if os.path.exists(srt) else None
                    st.rerun()
                
                if (st.session_state.get('sidebar_video') == translated):
                    st.video(translated, format="video/mp4", start_time=0)
                
                # Download button for translated video
                if os.path.exists(translated):
                    with open(translated, "rb") as f:
                        st.download_button(
                            lc.get_text("download_video"),
                            data=f.read(),
                            file_name=f"{title}_translated.mp4",
                            mime="video/mp4",
                            key=f"dl_video_{folder}"
                        )
                
                # Download button for SRT subtitles
                if os.path.exists(srt):
                    with open(srt, "r", encoding="utf-8") as f:
                        st.download_button(
                            lc.get_text("download_srt"),
                            data=f.read(),
                            file_name=f"{title}_subtitles.srt",
                            mime="text/plain",
                            key=f"dl_srt_{folder}"
                        )

# Main page title
st.title(lc.get_text("title"))

# Add vertical spacing after title
st.markdown("")
st.markdown("")
st.markdown("")
st.markdown("")

# Display selected video from history in main area
if 'selected_video' in st.session_state and st.session_state.selected_video:
    st.subheader("📹 " + lc.get_text("view_translation"))
    
    # Use columns to limit video size
    col_video, col_empty = st.columns([0.6, 0.4])
    
    with col_video:
        st.video(st.session_state.selected_video)
    
    # Provide SRT download if available
    if 'selected_srt' in st.session_state and st.session_state.selected_srt:
        with open(st.session_state.selected_srt, "r", encoding="utf-8") as f:
            st.download_button(
                lc.get_text("download_srt"),
                data=f.read(),
                file_name="subtitles.srt",
                mime="text/plain"
            )
    st.divider()

# File upload widget - now accepts multiple video formats
uploaded_file = st.file_uploader(
    lc.get_text("upload"), 
    type=["mp4", "mov", "avi", "wmv", "flv", "mkv", "webm", "m4v", "3gp"]
)

# Translation languages adapted to interface language
LANGUAGES = lc.get_languages()

# Add spacing
st.markdown("")
st.markdown("")
st.markdown("") 

# Language selection dropdown
tgt_lang_label = st.selectbox(lc.get_text("choose_lang"), list(LANGUAGES.keys()), index=0)
tgt_lang = LANGUAGES[tgt_lang_label]
st.markdown("")
st.markdown("") 

# @brief Convert string to URL-friendly slug
# @param value Input string to slugify
# @return URL-friendly string with only lowercase letters, numbers, and hyphens
# @details Removes unicode characters, special characters, and converts spaces to hyphens

def slugify(value):
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    return re.sub(r'[-\s]+', '-', value)

# Main processing section - only shown when file is uploaded
if uploaded_file is not None:
    # Save uploaded file to temporary location
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_input:
        tmp_input.write(uploaded_file.read())
        tmp_input_path = tmp_input.name

    # Display uploaded video preview in centered column
    col_empty_1, col_video_upload, col_empty_2 = st.columns([0.25, 0.5, 0.25])

    with col_video_upload:
        st.video(tmp_input_path)
    st.markdown("") 

    # Processing options checkboxes
    col1, col2, col3, col4 = st.columns(4)
    with col2:
        translate_audio = st.checkbox(lc.get_text("translate_audio"), value=True)
    with col3:
        add_subtitles = st.checkbox(lc.get_text("add_subtitles"), value=True)

    st.markdown("")  
    st.markdown("")  

    # Translation process trigger
    if st.button(lc.get_text("translate_btn")):
        # Validate that at least one option is selected
        if not (translate_audio or add_subtitles):
            st.error(lc.get_text("select_option"))
        else:
            st.markdown("")  
            st.markdown("")  

            # Create progress tracking UI elements
            status_placeholder = st.empty()
            progress_bar = st.progress(0)

            # @brief Update progress bar with current value
            # @param val Progress value between 0 and 1
            # @return None

            def progress_callback(val):
                progress_bar.progress(val)

            # @brief Update status message display
            # @param msg Status message to display
            # @return None
            
            def status_callback(msg):
                status_placeholder.text(msg)

            # Generate unique save directory path
            filename = os.path.splitext(uploaded_file.name)[0]
            filename = slugify(filename)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            save_dir = os.path.join(
                HISTORY_DIR,
                f"{filename}-{tgt_lang.upper()}_{timestamp}_{unique_id}"
            )

            # Process the video
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
            
            # Show completion message
            status_placeholder.success(lc.get_text("translation_complete"))
            
            # Display translated video in centered column
            col_final_empty_1, col_final_video, col_final_empty_2 = st.columns([0.25, 0.5, 0.25])
            
            with col_final_video:
                st.video(result["translated_video"])
            
            st.markdown("")  
            st.markdown("")  
            
            # Download buttons in main column
            col_dl1, col_dl2, col_dl3, col_dl4 = st.columns(4)
            
            # Video download button
            with col_dl2:
                with open(result["translated_video"], "rb") as f:
                    st.download_button(
                        label=lc.get_text("download_video"),
                        data=f,
                        file_name="translated_video.mp4",
                        mime="video/mp4"
                    )

            # SRT download button (if subtitles were generated)
            with col_dl3:
                if add_subtitles and os.path.exists(result["srt"]):
                    with open(result["srt"], "r", encoding="utf-8") as f:
                        st.download_button(
                            label=lc.get_text("download_srt"),
                            data=f.read(),
                            file_name="subtitles.srt",
                            mime="text/plain"
                        )

    # Clean up temporary file
    os.remove(tmp_input_path)

# Help section at bottom of page
st.markdown("---")  # Separator line
st.markdown(f"### {lc.get_text('having_issue')}")
col_help1, col_help2, col_empty = st.columns([0.15, 0.15, 0.7])

# README link
with col_help1:
    st.link_button(
        lc.get_text("go_readme"),
        "https://github.com/julies01/translating-project/blob/branche-principale/README.md"
    )

# Issue reporting link
with col_help2:
    st.link_button(
        lc.get_text("submit_issue"), 
        "https://github.com/julies01/translating-project/issues/new"
    )

