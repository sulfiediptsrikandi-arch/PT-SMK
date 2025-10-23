from typing import Literal, Tuple, Dict, Optional, List
import os
import time
import json
import PyPDF2
import re 
import uuid 
import base64
from datetime import datetime
import hashlib
from pathlib import Path

# KRITIS: Streamlit harus diimpor di global scope
import streamlit as st 
from phi.agent import Agent
from phi.model.openai import OpenAIChat
from phi.utils.log import logger

# Impor library tambahan untuk OCR
try:
    from pdf2image import convert_from_bytes
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logger.warning("OCR libraries not found. Install: pip install pdf2image pytesseract pillow")

# Impor Pandas untuk menampilkan data dalam bentuk tabel
try:
    import pandas as pd
    from io import BytesIO 
    import openpyxl
    import requests
    from urllib.parse import urlparse
    PANDAS_AVAILABLE = True
except ImportError:
    pd = None
    BytesIO = None
    requests = None
    PANDAS_AVAILABLE = False
    logger.warning("Pandas library not found. Table display and Excel download will be degraded.")


# --- OCEAN THEME STYLING ---
def apply_ocean_theme():
    """Apply custom ocean-themed CSS styling inspired by World Ocean Day"""
    st.markdown("""
    <style>
        /* Import Google Fonts */
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap');
        
        /* Main Background - Ocean Gradient */
        .stApp {
            background: linear-gradient(180deg, 
                #4DD0E1 0%,      /* Light cyan - surface water */
                #26C6DA 20%,     /* Bright cyan */
                #00BCD4 40%,     /* Cyan */
                #0097A7 60%,     /* Deep cyan */
                #00838F 80%,     /* Darker teal */
                #006064 100%     /* Deep ocean blue */
            );
            font-family: 'Poppins', sans-serif;
        }
        
        /* Sidebar - Coral Reef Colors */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, 
                #26C6DA 0%,
                #00ACC1 50%,
                #0097A7 100%
            );
        }
        
        [data-testid="stSidebar"] * {
            color: #FFFFFF !important;
        }
        
        /* Headers - Wave-like styling */
        h1, h2, h3 {
            color: #FFFFFF !important;
            font-weight: 700;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
            padding: 10px;
            border-radius: 10px;
            background: linear-gradient(90deg, rgba(38, 198, 218, 0.3), rgba(0, 188, 212, 0.3));
        }
        
        /* Content Containers - Bubble effect */
        .stMarkdown, .stDataFrame, div[data-testid="stExpander"] {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 15px;
            padding: 15px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1), 
                        0 1px 3px rgba(77, 208, 225, 0.3);
            margin: 10px 0;
        }
        
        /* Buttons - Coral & Fish Colors */
        .stButton>button {
            background: linear-gradient(135deg, #FF6B9D 0%, #FFA07A 100%) !important;
            color: white !important;
            border: none;
            border-radius: 25px;
            padding: 10px 25px;
            font-weight: 600;
            box-shadow: 0 4px 15px rgba(255, 107, 157, 0.4);
            transition: all 0.3s ease;
        }
        
        .stButton>button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(255, 107, 157, 0.6);
        }
        
        /* Primary Button - Ocean Blue */
        .stButton>button[kind="primary"] {
            background: linear-gradient(135deg, #0097A7 0%, #00BCD4 100%) !important;
            box-shadow: 0 4px 15px rgba(0, 188, 212, 0.4);
        }
        
        /* Tabs - Wave design */
        .stTabs [data-baseweb="tab-list"] {
            background: linear-gradient(90deg, 
                rgba(77, 208, 225, 0.2),
                rgba(38, 198, 218, 0.2)
            );
            border-radius: 15px;
            padding: 10px;
        }
        
        .stTabs [data-baseweb="tab"] {
            color: #FFFFFF !important;
            font-weight: 600;
            background: rgba(0, 150, 167, 0.3);
            border-radius: 10px;
            margin: 0 5px;
        }
        
        .stTabs [data-baseweb="tab"][aria-selected="true"] {
            background: linear-gradient(135deg, #FF6B9D, #FFA07A) !important;
            box-shadow: 0 4px 10px rgba(255, 107, 157, 0.3);
        }
        
        /* Input Fields - Underwater bubble style */
        .stTextInput>div>div>input,
        .stTextArea textarea,
        .stSelectbox>div>div>select {
            background: rgba(255, 255, 255, 0.95) !important;
            border: 2px solid #4DD0E1 !important;
            border-radius: 10px;
            color: #006064 !important;
            font-weight: 500;
        }
        
        /* File Uploader */
        [data-testid="stFileUploader"] {
            background: rgba(255, 255, 255, 0.9);
            border: 2px dashed #26C6DA;
            border-radius: 15px;
            padding: 20px;
        }
        
        /* Success Messages - Sea Green */
        .stSuccess {
            background: linear-gradient(135deg, #00E676 0%, #00C853 100%);
            color: white !important;
            border-radius: 10px;
            padding: 15px;
            box-shadow: 0 4px 10px rgba(0, 230, 118, 0.3);
        }
        
        /* Info Messages - Ocean Blue */
        .stInfo {
            background: linear-gradient(135deg, #00BCD4 0%, #0097A7 100%);
            color: white !important;
            border-radius: 10px;
            padding: 15px;
            box-shadow: 0 4px 10px rgba(0, 188, 212, 0.3);
        }
        
        /* Warning Messages - Coral Orange */
        .stWarning {
            background: linear-gradient(135deg, #FFB74D 0%, #FFA726 100%);
            color: white !important;
            border-radius: 10px;
            padding: 15px;
            box-shadow: 0 4px 10px rgba(255, 183, 77, 0.3);
        }
        
        /* Error Messages - Red Coral */
        .stError {
            background: linear-gradient(135deg, #EF5350 0%, #E53935 100%);
            color: white !important;
            border-radius: 10px;
            padding: 15px;
            box-shadow: 0 4px 10px rgba(239, 83, 80, 0.3);
        }
        
        /* Expander - Shell-like design */
        div[data-testid="stExpander"] {
            background: rgba(255, 255, 255, 0.95);
            border: 2px solid #4DD0E1;
            border-radius: 15px;
            box-shadow: 0 4px 10px rgba(77, 208, 225, 0.2);
        }
        
        /* DataFrame - Ocean table style */
        .dataframe {
            background: rgba(255, 255, 255, 0.98) !important;
            border-radius: 10px;
            overflow: hidden;
        }
        
        .dataframe thead tr th {
            background: linear-gradient(135deg, #00BCD4, #0097A7) !important;
            color: white !important;
            font-weight: 600;
        }
        
        .dataframe tbody tr:nth-child(even) {
            background: rgba(77, 208, 225, 0.1);
        }
        
        /* Metric Cards - Treasure Chest style */
        [data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 15px;
            padding: 15px;
            box-shadow: 0 4px 10px rgba(77, 208, 225, 0.3);
            border: 2px solid #4DD0E1;
        }
        
        [data-testid="stMetricValue"] {
            color: #00838F !important;
            font-weight: 700;
        }
        
        /* Chat Messages - Bubble style */
        .stChatMessage {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            padding: 15px;
            margin: 10px 0;
            box-shadow: 0 4px 8px rgba(77, 208, 225, 0.2);
        }
        
        /* Scrollbar - Ocean wave */
        ::-webkit-scrollbar {
            width: 10px;
        }
        
        ::-webkit-scrollbar-track {
            background: rgba(77, 208, 225, 0.2);
            border-radius: 10px;
        }
        
        ::-webkit-scrollbar-thumb {
            background: linear-gradient(180deg, #26C6DA, #00BCD4);
            border-radius: 10px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: linear-gradient(180deg, #00BCD4, #0097A7);
        }
        
        /* Floating bubbles animation */
        @keyframes float {
            0%, 100% { transform: translateY(0px); }
            50% { transform: translateY(-20px); }
        }
        
        /* Add wave effect to headers */
        @keyframes wave {
            0%, 100% { transform: translateX(0px); }
            50% { transform: translateX(10px); }
        }
        
        /* Tooltips */
        .stTooltipIcon {
            color: #4DD0E1 !important;
        }
    </style>
    """, unsafe_allow_html=True)


# --- KONSTANTA UNTUK PERSISTENT STORAGE ---
DATA_DIR = Path("recruitment_data")
ROLES_FILE = DATA_DIR / "roles.json"
MEMORY_FILE = DATA_DIR / "analysis_memory.json"
CHAT_HISTORY_FILE = DATA_DIR / "chat_history.json"
RESULTS_FILE = DATA_DIR / "batch_results.json"

# Buat direktori jika belum ada
DATA_DIR.mkdir(exist_ok=True)


# --- 1. DICTIONARY UNTUK TEKS DWIBASA (BAHASA INDONESIA & INGGRIS) ---
TEXTS = {
    # Sidebar & Konfigurasi
    'app_title': {'id': "🐋 PT Srikandi Mitra Karya - Sistem Rekrutmen AI 🌊", 'en': "🐋 PT Srikandi Mitra Karya - AI Recruitment System 🌊"},
    'config_header': {'id': "⚙️ Konfigurasi", 'en': "⚙️ Configuration"},
    'openai_settings': {'id': "Pengaturan OpenAI", 'en': "OpenAI Settings"},
    'api_key_label': {'id': "Kunci API OpenAI", 'en': "OpenAI API Key"},
    'api_key_help': {'id': "Dapatkan kunci API Anda dari platform.openai.com", 'en': "Get your API key from platform.openai.com"},
    'warning_missing_config': {'id': "⚠️ Harap konfigurasikan hal berikut di sidebar: ", 'en': "⚠️ Please configure the following in the sidebar: "},
    'language_select': {'id': "🌐 Pilih Bahasa", 'en': "🌐 Select Language"},
    'reset_button': {'id': "🔄 Reset Aplikasi", 'en': "🔄 Reset Application"},
    'ocr_settings': {'id': "Pengaturan OCR", 'en': "OCR Settings"},
    'enable_ocr': {'id': "Aktifkan OCR untuk PDF Gambar", 'en': "Enable OCR for Image PDFs"},
    'ocr_help': {'id': "OCR akan memindai PDF berbasis gambar untuk ekstraksi teks yang lebih baik", 'en': "OCR will scan image-based PDFs for better text extraction"},
    
    # Role Management
    'tab_manage_roles': {'id': "🐠 Kelola Posisi", 'en': "🐠 Manage Roles"},
    'add_role_header': {'id': "➕ Tambah Posisi Baru", 'en': "➕ Add New Role"},
    'edit_role_header': {'id': "✏️ Edit Posisi", 'en': "✏️ Edit Role"},
    'role_id_label': {'id': "ID Posisi (tanpa spasi)", 'en': "Role ID (no spaces)"},
    'role_id_help': {'id': "Gunakan huruf kecil dan underscore, contoh: senior_developer", 'en': "Use lowercase and underscores, e.g.: senior_developer"},
    'role_name_label': {'id': "Nama Posisi", 'en': "Role Name"},
    'required_skills_label': {'id': "Persyaratan & Keterampilan", 'en': "Requirements & Skills"},
    'required_skills_help': {'id': "Daftar persyaratan untuk posisi ini", 'en': "List of requirements for this role"},
    'add_role_button': {'id': "➕ Tambah Posisi", 'en': "➕ Add Role"},
    'update_role_button': {'id': "💾 Update Posisi", 'en': "💾 Update Role"},
    'delete_role_button': {'id': "🗑️ Hapus Posisi", 'en': "🗑️ Delete Role"},
    'role_added_success': {'id': "✅ Posisi berhasil ditambahkan!", 'en': "✅ Role added successfully!"},
    'role_updated_success': {'id': "✅ Posisi berhasil diupdate!", 'en': "✅ Role updated successfully!"},
    'role_deleted_success': {'id': "✅ Posisi berhasil dihapus!", 'en': "✅ Role deleted successfully!"},
    'role_exists_error': {'id': "❌ ID Posisi sudah ada!", 'en': "❌ Role ID already exists!"},
    'role_id_invalid': {'id': "❌ ID Posisi tidak valid! Gunakan huruf kecil, angka, dan underscore saja.", 'en': "❌ Invalid Role ID! Use lowercase letters, numbers, and underscores only."},
    'select_role_to_edit': {'id': "Pilih posisi untuk diedit:", 'en': "Select role to edit:"},
    'no_roles_available': {'id': "Tidak ada posisi tersedia. Tambahkan posisi baru terlebih dahulu.", 'en': "No roles available. Add a new role first."},
    'current_roles_header': {'id': "📋 Daftar Posisi Saat Ini", 'en': "📋 Current Roles List"},
    'export_roles_button': {'id': "📥 Export Posisi (JSON)", 'en': "📥 Export Roles (JSON)"},
    'import_roles_button': {'id': "📤 Import Posisi (JSON)", 'en': "📤 Import Roles (JSON)"},
    'import_roles_success': {'id': "✅ Posisi berhasil diimport!", 'en': "✅ Roles imported successfully!"},
    'import_roles_error': {'id': "❌ Gagal import posisi. Pastikan format JSON benar.", 'en': "❌ Failed to import roles. Ensure JSON format is correct."},
    'storage_info': {'id': "💾 Data disimpan secara otomatis", 'en': "💾 Data saved automatically"},
    'data_loaded': {'id': "✅ Data berhasil dimuat dari penyimpanan", 'en': "✅ Data loaded from storage successfully"},
    'clear_all_data': {'id': "🗑️ Hapus Semua Data", 'en': "🗑️ Clear All Data"},
    'confirm_clear_data': {'id': "Apakah Anda yakin ingin menghapus SEMUA data termasuk posisi, hasil analisa, dan history chat?", 'en': "Are you sure you want to delete ALL data including roles, analysis results, and chat history?"},
    'all_data_cleared': {'id': "✅ Semua data berhasil dihapus", 'en': "✅ All data cleared successfully"},
    'data_management': {'id': "Manajemen Data", 'en': "Data Management"},
    'export_all_data': {'id': "📥 Export Semua Data", 'en': "📥 Export All Data"},
    'import_all_data': {'id': "📤 Import Semua Data", 'en': "📤 Import All Data"},
    'backup_success': {'id': "✅ Backup berhasil dibuat", 'en': "✅ Backup created successfully"},
    'restore_success': {'id': "✅ Data berhasil dipulihkan", 'en': "✅ Data restored successfully"},
    
    # Mode Pemrosesan
    'select_role': {'id': "🎯 Pilih Posisi yang Dibutuhkan:", 'en': "🎯 Select the Required Role:"},
    'view_skills_expander': {'id': "📋 Lihat Keterampilan yang Dibutuhkan", 'en': "📋 View Required Skills"},
    
    # Mode Batch Processing
    'upload_resume_label': {'id': "📄 Unggah resume (PDF)", 'en': "📄 Upload resume (PDF)"},
    'batch_info': {'id': "💡 Unggah beberapa resume (PDF) untuk memprosesnya secara otomatis.", 'en': "💡 Upload multiple resumes (PDF) to process them automatically."},
    'clear_resumes_button': {'id': "🗑️ Bersihkan Resume", 'en': "🗑️ Clear Resumes"},
    'clear_resumes_help': {'id': "Hapus semua berkas PDF yang diunggah", 'en': "Remove all uploaded PDF files"},
    'resumes_uploaded': {'id': "resume(s) terunggah", 'en': "resume(s) uploaded"},
    'process_all_button': {'id': "🚀 Proses Semua Resume", 'en': "🚀 Process All Applications"},
    'processing_spinner': {'id': "🌊 Memproses aplikasi...", 'en': "🌊 Processing application..."},
    'ocr_processing': {'id': "🔍 Memindai dengan OCR...", 'en': "🔍 Scanning with OCR..."},
    
    # Hasil & Feedback
    'tab_upload': {'id': "📤 Unggah & Proses", 'en': "📤 Upload & Process"},
    'tab_download_excel': {'id': "📥 Download dari Excel", 'en': "📥 Download from Excel"},
    'tab_results': {'id': "📊 Hasil & Ringkasan", 'en': "📊 Results & Summary"},
    'tab_chatbot': {'id': "💬 Chat dengan AI", 'en': "💬 Chat with AI"},
    'processing_status': {'id': "Memproses", 'en': "Processing"},
    'processing_complete': {'id': "✅ Pemrosesan selesai!", 'en': "✅ Processing complete!"},
    'error_processing': {'id': "⚠️ Kesalahan proses", 'en': "⚠️ Error processing"},
    'error_pdf_text': {'id': "Tidak dapat mengekstrak teks dari PDF", 'en': "Could not extract text from PDF"},
    'error_api_key': {'id': "Kunci API OpenAI hilang atau tidak valid.", 'en': "OpenAI API Key is missing or invalid."},
    'summary_header': {'id': "📊 Ringkasan Pemrosesan", 'en': "📊 Processing Summary"},
    'total_processed': {'id': "Total Diproses", 'en': "Total Processed"},
    'selected_label': {'id': "Direkomendasikan ✅", 'en': "Recommended ✅"},
    'rejected_label': {'id': "Tidak direkomendasikan ❌", 'en': "Not Recommended ❌"}, 
    'errors_label': {'id': "Kesalahan ⚠️", 'en': "Errors ⚠️"},
    
    # Chatbot
    'chatbot_header': {'id': "💬 Chat dengan AI Recruiter", 'en': "💬 Chat with AI Recruiter"},
    'chatbot_placeholder': {'id': "Tanyakan tentang kandidat, hasil analisa, atau minta saran rekrutmen...", 'en': "Ask about candidates, analysis results, or request recruitment advice..."},
    'chatbot_help': {'id': "AI dapat membantu Anda memahami hasil analisa dan memberikan rekomendasi", 'en': "AI can help you understand analysis results and provide recommendations"},
    'clear_chat': {'id': "🗑️ Hapus Riwayat Chat", 'en': "🗑️ Clear Chat History"},
    'chat_cleared': {'id': "✅ Riwayat chat berhasil dihapus", 'en': "✅ Chat history cleared"},
    'no_results_for_chat': {'id': "Belum ada hasil analisa. Silakan proses resume terlebih dahulu di tab Unggah & Proses.", 'en': "No analysis results yet. Please process resumes first in the Upload & Process tab."},
    
    # Header Tabel
    'table_name': {'id': "Nama", 'en': "Name"},
    'table_status': {'id': "Status", 'en': "Status"},
    'table_match': {'id': "Kesesuaian", 'en': "Match"},
    'table_analysis': {'id': "Analisa", 'en': "Analysis"},
    'table_details': {'id': "Detail", 'en': "Details"},
    'no_results_yet': {'id': "Belum ada hasil. Silakan proses resume terlebih dahulu.", 'en': "No results yet. Please process resumes first."},
    'download_results_excel': {'id': "📥 Download Hasil (Excel)", 'en': "📥 Download Results (Excel)"},
    'download_results_json': {'id': "📥 Download Hasil (JSON)", 'en': "📥 Download Results (JSON)"},
    'filter_by_status': {'id': "Filter berdasarkan Status:", 'en': "Filter by Status:"},
    'all_candidates': {'id': "Semua Kandidat", 'en': "All Candidates"},
    'recommended': {'id': "Direkomendasikan", 'en': "Recommended"},
    'not_recommended': {'id': "Tidak Direkomendasikan", 'en': "Not Recommended"},
    'errors': {'id': "Error", 'en': "Errors"},
    
    # Excel Mode
    'upload_excel_label': {'id': "Unggah file Excel dengan daftar kandidat & link CV", 'en': "Upload Excel file with candidate list & CV links"},
    'excel_uploaded': {'id': "File Excel terunggah", 'en': "Excel file uploaded"},
    'download_all_cv': {'id': "🚀 Download & Proses Semua CV", 'en': "🚀 Download & Process All CVs"},
    'downloading_cv': {'id': "Mendownload dan memproses CV...", 'en': "Downloading and processing CVs..."},
    'no_valid_links': {'id': "Tidak ada link CV yang valid ditemukan.", 'en': "No valid CV links found."},
    'invalid_excel_format': {'id': "Format Excel tidak valid atau tidak ada kolom link CV.", 'en': "Invalid Excel format or no CV link column found."},
    'excel_format_info': {'id': """
    📋 **Format Excel yang Diperlukan / Required Excel Format:**
    
    File Excel harus memiliki kolom-kolom berikut / Excel file must have the following columns:
    - **Nama / Name** (wajib / required): Nama kandidat / Candidate name
    - **Link CV / CV Link / URL** (wajib / required): Link ke file PDF CV / Link to PDF CV file
    - Kolom lain (opsional) / Other columns (optional): Email, Phone, dll / etc.
    
    ✅ **Link yang Didukung / Supported Links:**
    - Direct PDF links (https://example.com/cv.pdf)
    - Google Drive shared links
    - Dropbox shared links
    - OneDrive shared links
    
    ⚠️ **Catatan Penting / Important Notes:**
    - Link harus publicly accessible / Links must be publicly accessible
    - File harus dalam format PDF / Files must be in PDF format
    """, 'en': """
    📋 **Required Excel Format:**
    
    Excel file must have the following columns:
    - **Name** (required): Candidate name
    - **CV Link / URL** (required): Link to PDF CV file
    - Other columns (optional): Email, Phone, etc.
    
    ✅ **Supported Links:**
    - Direct PDF links (https://example.com/cv.pdf)
    - Google Drive shared links
    - Dropbox shared links
    - OneDrive shared links
    
    ⚠️ **Important Notes:**
    - Links must be publicly accessible
    - Files must be in PDF format
    """},
}

def get_text(key: str) -> str:
    """Get text in selected language"""
    lang = st.session_state.get('language', 'id')
    return TEXTS.get(key, {}).get(lang, key)


# --- 2. FUNGSI PERSISTENT STORAGE ---
def load_roles() -> Dict:
    """Load roles from disk"""
    try:
        if ROLES_FILE.exists():
            with open(ROLES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading roles: {e}")
    return {}

def save_roles(roles: Dict):
    """Save roles to disk"""
    try:
        with open(ROLES_FILE, 'w', encoding='utf-8') as f:
            json.dump(roles, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving roles: {e}")

def load_results_from_disk() -> List[Dict]:
    """Load batch results from disk"""
    try:
        if RESULTS_FILE.exists():
            with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading results: {e}")
    return []

def save_results_to_disk():
    """Save batch results to disk"""
    try:
        with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(st.session_state.batch_results, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving results: {e}")

def load_chat_history() -> List[Dict]:
    """Load chat history from disk"""
    try:
        if CHAT_HISTORY_FILE.exists():
            with open(CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading chat history: {e}")
    return []

def save_chat_history():
    """Save chat history to disk"""
    try:
        with open(CHAT_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(st.session_state.messages, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving chat history: {e}")

def clear_all_data():
    """Clear all persisted data"""
    try:
        for file in [ROLES_FILE, RESULTS_FILE, CHAT_HISTORY_FILE, MEMORY_FILE]:
            if file.exists():
                file.unlink()
        
        st.session_state.batch_results = []
        st.session_state.messages = []
        st.session_state.analysis_memory = {}
        
        return True
    except Exception as e:
        logger.error(f"Error clearing data: {e}")
        return False


# --- 3. FUNGSI UNTUK STREAMLIT SESSION STATE ---
def init_session_state():
    """Initialize all session state variables"""
    defaults = {
        'language': 'id',
        'uploaded_files': [],
        'batch_results': load_results_from_disk(),
        'messages': load_chat_history(),
        'analysis_memory': {},
        'enable_ocr': False,
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# --- 4. FUNGSI EKSTRAKSI PDF ---
def extract_text_from_pdf(pdf_file) -> str:
    """
    Extract text from PDF using PyPDF2.
    If OCR is enabled and text extraction fails, use OCR.
    """
    text = ""
    ocr_used = False
    
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        
        if not text.strip() and st.session_state.get('enable_ocr', False) and OCR_AVAILABLE:
            logger.info("No text found with PyPDF2, attempting OCR...")
            pdf_file.seek(0)
            
            images = convert_from_bytes(pdf_file.read())
            
            for i, image in enumerate(images):
                ocr_text = pytesseract.image_to_string(image, lang='ind+eng')
                if ocr_text.strip():
                    text += ocr_text + "\n"
                    ocr_used = True
            
            if text.strip():
                logger.info("✅ OCR successfully extracted text")
        
    except Exception as e:
        logger.error(f"Error extracting PDF: {e}")
        return ""
    
    return text.strip(), ocr_used


# --- 5. FUNGSI ANALISIS CV DENGAN AI ---
def analyze_cv_with_ai(cv_text: str, role_requirements: str, candidate_name: str) -> Dict:
    """Analyze CV using AI Agent and return structured results"""
    try:
        api_key = st.session_state.get('openai_api_key', '')
        if not api_key:
            return {
                'status': 'error',
                'error': get_text('error_api_key')
            }
        
        analysis_agent = Agent(
            name="CV Analyzer",
            model=OpenAIChat(id="gpt-4o-mini", api_key=api_key),
            instructions=[
                "You are an expert HR recruiter analyzing candidate CVs.",
                "Provide detailed, objective analysis focusing on skills match.",
                "Be constructive and highlight both strengths and gaps.",
                "Always respond in the same language as the role requirements."
            ],
            markdown=True,
        )
        
        prompt = f"""
Analyze this CV for the following role:

**Role Requirements:**
{role_requirements}

**Candidate: {candidate_name}**
**CV Content:**
{cv_text[:4000]}

Please provide a structured analysis with:
1. **Match Percentage** (0-100%): Overall fit for the role
2. **Status**: "RECOMMENDED" or "NOT RECOMMENDED"
3. **Key Strengths**: What matches well (bullet points)
4. **Gaps/Concerns**: What's missing or concerning (bullet points)
5. **Summary**: Brief 2-3 sentence recommendation

Format your response clearly with these sections.
"""
        
        response = analysis_agent.run(prompt)
        analysis_text = response.content if hasattr(response, 'content') else str(response)
        
        match_percentage = extract_percentage(analysis_text)
        status = 'selected' if 'RECOMMENDED' in analysis_text.upper() and 'NOT RECOMMENDED' not in analysis_text.upper() else 'rejected'
        
        return {
            'status': status,
            'match_percentage': match_percentage,
            'analysis': analysis_text,
            'candidate_name': candidate_name,
            'cv_text_preview': cv_text[:500]
        }
        
    except Exception as e:
        logger.error(f"AI Analysis Error: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'candidate_name': candidate_name
        }


def extract_percentage(text: str) -> int:
    """Extract percentage from analysis text"""
    import re
    patterns = [
        r'match\s*percentage[:\s]*(\d+)%',
        r'(\d+)%\s*match',
        r'fit[:\s]*(\d+)%',
        r'score[:\s]*(\d+)%'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    
    return 50


# --- 6. FUNGSI DOWNLOAD & PROCESS DARI EXCEL ---
def convert_google_drive_link(url: str) -> str:
    """Convert Google Drive share link to direct download link"""
    if 'drive.google.com' in url:
        file_id_match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
        if file_id_match:
            file_id = file_id_match.group(1)
            return f"https://drive.google.com/uc?export=download&id={file_id}"
    return url


def download_pdf_from_url(url: str) -> Optional[BytesIO]:
    """Download PDF from URL and return as BytesIO object"""
    try:
        if not PANDAS_AVAILABLE or not requests:
            logger.error("Requests library not available")
            return None
        
        url = convert_google_drive_link(url)
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '').lower()
            
            if 'pdf' in content_type or url.lower().endswith('.pdf'):
                return BytesIO(response.content)
            else:
                logger.warning(f"URL does not appear to be a PDF: {url}")
                return None
        else:
            logger.error(f"Failed to download. Status: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Error downloading from {url}: {e}")
        return None


def read_excel_with_cv_links(excel_file) -> pd.DataFrame:
    """Read Excel file and extract candidate names and CV links"""
    try:
        if not PANDAS_AVAILABLE or pd is None:
            st.error("Pandas library not available. Cannot process Excel files.")
            return None
        
        df = pd.read_excel(excel_file)
        
        name_col = None
        link_col = None
        
        for col in df.columns:
            col_lower = col.lower()
            if 'nama' in col_lower or 'name' in col_lower:
                name_col = col
            if 'link' in col_lower or 'url' in col_lower or 'cv' in col_lower:
                link_col = col
        
        if not name_col or not link_col:
            st.error(f"Cannot find required columns. Found: {list(df.columns)}")
            return None
        
        df_filtered = df[[name_col, link_col]].copy()
        df_filtered.columns = ['name', 'cv_link']
        df_filtered = df_filtered.dropna(subset=['cv_link'])
        
        def is_valid_url(url):
            try:
                result = urlparse(str(url))
                return all([result.scheme, result.netloc])
            except:
                return False
        
        df_filtered = df_filtered[df_filtered['cv_link'].apply(is_valid_url)]
        
        return df_filtered
        
    except Exception as e:
        logger.error(f"Error reading Excel: {e}")
        st.error(f"Error reading Excel: {str(e)}")
        return None


def process_excel_cv_links(excel_file, role: str) -> List[Dict]:
    """Process all CVs from Excel file with progress tracking"""
    results = []
    
    df = read_excel_with_cv_links(excel_file)
    
    if df is None or df.empty:
        return results
    
    roles = load_roles()
    role_requirements = roles.get(role, "No requirements specified")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total_candidates = len(df)
    
    for idx, row in df.iterrows():
        candidate_name = str(row['name'])
        cv_link = str(row['cv_link'])
        
        progress = (idx + 1) / total_candidates
        progress_bar.progress(progress)
        status_text.text(f"🌊 Processing {idx + 1}/{total_candidates}: {candidate_name}")
        
        try:
            pdf_file = download_pdf_from_url(cv_link)
            
            if pdf_file:
                cv_text, ocr_used = extract_text_from_pdf(pdf_file)
                
                if cv_text:
                    result = analyze_cv_with_ai(cv_text, role_requirements, candidate_name)
                    result['cv_link'] = cv_link
                    result['ocr_used'] = ocr_used
                else:
                    result = {
                        'status': 'error',
                        'error': get_text('error_pdf_text'),
                        'candidate_name': candidate_name,
                        'cv_link': cv_link
                    }
            else:
                result = {
                    'status': 'error',
                    'error': 'Failed to download PDF',
                    'candidate_name': candidate_name,
                    'cv_link': cv_link
                }
            
            results.append(result)
            time.sleep(0.5)
            
        except Exception as e:
            logger.error(f"Error processing {candidate_name}: {e}")
            results.append({
                'status': 'error',
                'error': str(e),
                'candidate_name': candidate_name,
                'cv_link': cv_link
            })
    
    progress_bar.empty()
    status_text.empty()
    
    return results


# --- 7. DISPLAY FUNCTIONS ---
def display_results_table(results: List[Dict], language: str):
    """Display results in a formatted table with filters and download options"""
    st.header(get_text('tab_results'))
    
    if not results:
        st.info(get_text('no_results_yet'))
        return
    
    col1, col2, col3, col4 = st.columns(4)
    
    selected_count = sum(1 for r in results if r['status'] == 'selected')
    rejected_count = sum(1 for r in results if r['status'] == 'rejected')
    error_count = sum(1 for r in results if r['status'] == 'error')
    ocr_count = sum(1 for r in results if r.get('ocr_used', False))
    
    with col1:
        st.metric(get_text('total_processed'), len(results))
    with col2:
        st.metric(get_text('selected_label'), selected_count)
    with col3:
        st.metric(get_text('rejected_label'), rejected_count)
    with col4:
        st.metric(get_text('errors_label'), error_count)
    
    if ocr_count > 0:
        st.info(f"🔍 OCR digunakan untuk {ocr_count} kandidat / OCR used for {ocr_count} candidates")
    
    st.markdown("---")
    
    filter_option = st.selectbox(
        get_text('filter_by_status'),
        [get_text('all_candidates'), get_text('recommended'), get_text('not_recommended'), get_text('errors')]
    )
    
    if filter_option == get_text('recommended'):
        filtered_results = [r for r in results if r['status'] == 'selected']
    elif filter_option == get_text('not_recommended'):
        filtered_results = [r for r in results if r['status'] == 'rejected']
    elif filter_option == get_text('errors'):
        filtered_results = [r for r in results if r['status'] == 'error']
    else:
        filtered_results = results
    
    for result in filtered_results:
        with st.expander(f"**{result.get('candidate_name', 'Unknown')}** - {result['status'].upper()}", expanded=False):
            col_a, col_b = st.columns([1, 3])
            
            with col_a:
                st.metric(get_text('table_match'), f"{result.get('match_percentage', 0)}%")
                
                status_emoji = "✅" if result['status'] == 'selected' else "❌" if result['status'] == 'rejected' else "⚠️"
                st.markdown(f"**Status:** {status_emoji} {result['status'].upper()}")
                
                if result.get('cv_link'):
                    st.markdown(f"**🔗 [Link CV]({result['cv_link']})**")
                
                if result.get('ocr_used'):
                    st.info("🔍 OCR digunakan")
            
            with col_b:
                if result['status'] == 'error':
                    st.error(f"**Error:** {result.get('error', 'Unknown error')}")
                else:
                    st.markdown(f"**{get_text('table_analysis')}:**")
                    st.markdown(result.get('analysis', 'No analysis available'))
    
    st.markdown("---")
    
    col_download1, col_download2 = st.columns(2)
    
    with col_download1:
        if PANDAS_AVAILABLE and pd is not None:
            df_results = pd.DataFrame([
                {
                    'Nama': r.get('candidate_name', 'Unknown'),
                    'Status': r['status'],
                    'Match %': r.get('match_percentage', 0),
                    'Link CV': r.get('cv_link', ''),
                    'OCR Used': r.get('ocr_used', False)
                }
                for r in results
            ])
            
            excel_buffer = BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                df_results.to_excel(writer, index=False, sheet_name='Results')
            
            st.download_button(
                label=get_text('download_results_excel'),
                data=excel_buffer.getvalue(),
                file_name=f"recruitment_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    
    with col_download2:
        json_str = json.dumps(results, ensure_ascii=False, indent=2)
        st.download_button(
            label=get_text('download_results_json'),
            data=json_str,
            file_name=f"recruitment_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )


def display_chatbot_interface():
    """Display chatbot interface for AI Q&A"""
    st.header(get_text('chatbot_header'))
    
    if not st.session_state.batch_results:
        st.warning(get_text('no_results_for_chat'))
        return
    
    st.info(get_text('chatbot_help'))
    
    if st.button(get_text('clear_chat')):
        st.session_state.messages = []
        save_chat_history()
        st.success(get_text('chat_cleared'))
        st.rerun()
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    if prompt := st.chat_input(get_text('chatbot_placeholder')):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("🤔 Berpikir..."):
                try:
                    api_key = st.session_state.get('openai_api_key', '')
                    
                    results_summary = f"""
Here are the recruitment results to reference:

Total Candidates: {len(st.session_state.batch_results)}
Recommended: {sum(1 for r in st.session_state.batch_results if r['status'] == 'selected')}
Not Recommended: {sum(1 for r in st.session_state.batch_results if r['status'] == 'rejected')}

Candidates:
"""
                    for r in st.session_state.batch_results[:10]:
                        results_summary += f"\n- {r.get('candidate_name', 'Unknown')}: {r['status']} ({r.get('match_percentage', 0)}%)"
                    
                    chat_agent = Agent(
                        name="HR Assistant",
                        model=OpenAIChat(id="gpt-4o-mini", api_key=api_key),
                        instructions=[
                            "You are a helpful HR assistant analyzing recruitment results.",
                            "Provide insights, comparisons, and recommendations based on the data.",
                            "Be conversational and helpful.",
                            f"Always respond in {'Indonesian' if st.session_state.language == 'id' else 'English'}."
                        ],
                        markdown=True,
                    )
                    
                    full_prompt = f"{results_summary}\n\nUser Question: {prompt}"
                    response = chat_agent.run(full_prompt)
                    assistant_response = response.content if hasattr(response, 'content') else str(response)
                    
                    st.markdown(assistant_response)
                    st.session_state.messages.append({"role": "assistant", "content": assistant_response})
                    save_chat_history()
                    
                except Exception as e:
                    error_msg = f"Error: {str(e)}"
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})


def display_role_management():
    """Display role management interface"""
    st.header(get_text('tab_manage_roles'))
    
    roles = load_roles()
    
    tab_add, tab_edit, tab_data = st.tabs([
        get_text('add_role_header'), 
        get_text('edit_role_header'),
        get_text('data_management')
    ])
    
    with tab_add:
        st.subheader(get_text('add_role_header'))
        
        role_id = st.text_input(
            get_text('role_id_label'),
            key='new_role_id',
            help=get_text('role_id_help')
        )
        
        role_name = st.text_input(
            get_text('role_name_label'),
            key='new_role_name'
        )
        
        role_requirements = st.text_area(
            get_text('required_skills_label'),
            height=200,
            key='new_role_requirements',
            help=get_text('required_skills_help')
        )
        
        if st.button(get_text('add_role_button'), type='primary'):
            if role_id and role_requirements:
                if not re.match(r'^[a-z0-9_]+$', role_id):
                    st.error(get_text('role_id_invalid'))
                elif role_id in roles:
                    st.error(get_text('role_exists_error'))
                else:
                    roles[role_id] = role_requirements
                    save_roles(roles)
                    st.success(get_text('role_added_success'))
                    st.rerun()
            else:
                st.warning("Please fill all fields")
    
    with tab_edit:
        if not roles:
            st.info(get_text('no_roles_available'))
        else:
            selected_role = st.selectbox(
                get_text('select_role_to_edit'),
                list(roles.keys()),
                format_func=lambda x: x.replace('_', ' ').title()
            )
            
            if selected_role:
                edited_requirements = st.text_area(
                    get_text('required_skills_label'),
                    value=roles[selected_role],
                    height=200,
                    key='edit_role_requirements'
                )
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button(get_text('update_role_button'), type='primary'):
                        roles[selected_role] = edited_requirements
                        save_roles(roles)
                        st.success(get_text('role_updated_success'))
                        st.rerun()
                
                with col2:
                    if st.button(get_text('delete_role_button'), type='secondary'):
                        del roles[selected_role]
                        save_roles(roles)
                        st.success(get_text('role_deleted_success'))
                        st.rerun()
    
    with tab_data:
        st.subheader(get_text('data_management'))
        
        col1, col2 = st.columns(2)
        
        with col1:
            if roles:
                roles_json = json.dumps(roles, ensure_ascii=False, indent=2)
                st.download_button(
                    label=get_text('export_roles_button'),
                    data=roles_json,
                    file_name=f"roles_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
        
        with col2:
            uploaded_roles = st.file_uploader(
                get_text('import_roles_button'),
                type=['json'],
                key='import_roles'
            )
            
            if uploaded_roles:
                try:
                    imported_roles = json.load(uploaded_roles)
                    save_roles(imported_roles)
                    st.success(get_text('import_roles_success'))
                    st.rerun()
                except Exception as e:
                    st.error(f"{get_text('import_roles_error')} {str(e)}")
        
        st.markdown("---")
        
        if st.button(get_text('clear_all_data'), type='secondary'):
            if st.checkbox(get_text('confirm_clear_data')):
                if clear_all_data():
                    st.success(get_text('all_data_cleared'))
                    st.rerun()
    
    if roles:
        st.markdown("---")
        st.subheader(get_text('current_roles_header'))
        
        for role_id, requirements in roles.items():
            with st.expander(f"📋 {role_id.replace('_', ' ').title()}", expanded=False):
                st.markdown(requirements)


# --- 8. MAIN APPLICATION ---
def main():
    """Main application"""
    st.set_page_config(
        page_title="🌊 Ocean AI Recruitment System",
        page_icon="🐋",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Apply ocean theme
    apply_ocean_theme()
    
    init_session_state()
    
    # Sidebar
    with st.sidebar:
        st.title(get_text('app_title'))
        
        st.markdown("---")
        
        # Language selector with ocean emoji
        language = st.selectbox(
            get_text('language_select'),
            options=['id', 'en'],
            format_func=lambda x: "🇮🇩 Bahasa Indonesia" if x == 'id' else "🇬🇧 English",
            key='language_selector'
        )
        
        if language != st.session_state.language:
            st.session_state.language = language
            st.rerun()
        
        st.markdown("---")
        st.subheader(get_text('config_header'))
        
        api_key = st.text_input(
            get_text('api_key_label'),
            type='password',
            help=get_text('api_key_help'),
            key='openai_api_key'
        )
        
        if OCR_AVAILABLE:
            st.markdown("---")
            st.subheader(get_text('ocr_settings'))
            st.session_state.enable_ocr = st.checkbox(
                get_text('enable_ocr'),
                value=st.session_state.get('enable_ocr', False),
                help=get_text('ocr_help')
            )
        
        st.markdown("---")
        st.info(get_text('storage_info'))
        
        if st.button(get_text('reset_button')):
            for key in list(st.session_state.keys()):
                if key != 'language':
                    del st.session_state[key]
            st.rerun()
    
    # Main content
    missing_config = []
    if not st.session_state.get('openai_api_key'):
        missing_config.append("OpenAI API Key")
    
    if missing_config:
        st.warning(f"{get_text('warning_missing_config')} {', '.join(missing_config)}")
        st.stop()
    
    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        get_text('tab_upload'),
        get_text('tab_download_excel'),
        get_text('tab_results'),
        get_text('tab_chatbot'),
        get_text('tab_manage_roles')
    ])
    
    # TAB 1: Upload & Process
    with tab1:
        st.header(get_text('tab_upload'))
        
        roles = load_roles()
        if not roles:
            st.warning(get_text('no_roles_available'))
            st.info(f"👉 {get_text('tab_manage_roles')}")
        else:
            role_options = list(roles.keys())
            role = st.selectbox(
                get_text('select_role'),
                role_options,
                format_func=lambda x: x.replace('_', ' ').title()
            )
            
            with st.expander(get_text('view_skills_expander'), expanded=False):
                st.markdown(roles[role])
            
            st.markdown("---")
            
            st.info(get_text('batch_info'))
            
            uploaded_files = st.file_uploader(
                get_text('upload_resume_label'),
                type=['pdf'],
                accept_multiple_files=True,
                key='resume_uploader'
            )
            
            if uploaded_files:
                st.success(f"📁 {len(uploaded_files)} {get_text('resumes_uploaded')}")
                
                if st.button(get_text('clear_resumes_button'), help=get_text('clear_resumes_help')):
                    st.rerun()
                
                if st.button(get_text('process_all_button'), type='primary', use_container_width=True):
                    results = []
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    for idx, uploaded_file in enumerate(uploaded_files):
                        progress = (idx + 1) / len(uploaded_files)
                        progress_bar.progress(progress)
                        
                        candidate_name = uploaded_file.name.replace('.pdf', '')
                        status_text.text(f"{get_text('processing_spinner')} {candidate_name}")
                        
                        cv_text, ocr_used = extract_text_from_pdf(uploaded_file)
                        
                        if cv_text:
                            if ocr_used:
                                status_text.text(f"{get_text('ocr_processing')} {candidate_name}")
                            
                            result = analyze_cv_with_ai(cv_text, roles[role], candidate_name)
                            result['ocr_used'] = ocr_used
                        else:
                            result = {
                                'status': 'error',
                                'error': get_text('error_pdf_text'),
                                'candidate_name': candidate_name
                            }
                        
                        results.append(result)
                    
                    progress_bar.empty()
                    status_text.empty()
                    
                    results.sort(key=lambda x: x.get('match_percentage', 0), reverse=True)
                    
                    st.session_state.batch_results = results
                    save_results_to_disk()
                    
                    st.success(get_text('processing_complete'))
                    
                    selected_count = sum(1 for r in results if r['status'] == 'selected')
                    rejected_count = sum(1 for r in results if r['status'] == 'rejected')
                    error_count = sum(1 for r in results if r['status'] == 'error')
                    ocr_count = sum(1 for r in results if r.get('ocr_used', False))
                    
                    summary = f"🎉 {get_text('processing_complete')}\n"
                    summary += f"📊 Total: {len(results)} | ✅ {selected_count} | ❌ {rejected_count} | ⚠️ {error_count}"
                    if ocr_count > 0:
                        summary += f" | 🔍 OCR: {ocr_count}"
                    
                    st.toast(summary, icon="✅")
                    st.info(f"👉 {get_text('tab_results')} atau {get_text('tab_chatbot')}")
    
    # TAB 2: Download from Excel
    with tab2:
        st.header(get_text('tab_download_excel'))
        
        st.info(get_text('excel_format_info'))
        
        st.warning("""
        🔒 **PENTING untuk Link Google Drive:**
        
        Jika menggunakan Google Form/Drive, pastikan file **PUBLIC**:
        1. Buka Google Drive
        2. Klik kanan folder/file → **Share / Bagikan**
        3. Ubah ke: **"Anyone with the link"** / **"Siapa saja yang memiliki link"**
        4. Permission: **"Viewer"** / **"Dapat melihat"**
        5. Klik **Done / Selesai**
        
        ℹ️ Link Google Drive akan otomatis dikonversi ke format direct download.
        """)
        
        with st.expander("📋 Contoh Format Excel / Excel Format Example", expanded=False):
            if PANDAS_AVAILABLE and pd is not None:
                sample_data = {
                    'Nama Kandidat / Candidate Name': ['John Doe', 'Jane Smith', 'Ahmad Rizki'],
                    'Link CV / CV Link': [
                        'https://example.com/cv1.pdf',
                        'https://drive.google.com/file/d/1aBcDeFgHiJk/view',
                        'https://www.dropbox.com/s/xxxxx/cv3.pdf?dl=1'
                    ],
                    'Email (Optional)': ['john@email.com', 'jane@email.com', 'ahmad@email.com']
                }
                st.dataframe(pd.DataFrame(sample_data), use_container_width=True)
            
            st.markdown("""
            **Catatan / Notes:**
            - Kolom wajib / Required columns: `Nama` atau `Name`, `Link CV` atau `CV Link` atau `URL`
            - Link harus valid dan mengarah ke file PDF / Links must be valid and point to PDF files
            - ✅ Support: Direct PDF, Google Drive, Dropbox, dll / Supports: Direct PDF, Google Drive, Dropbox, etc
            - 🔒 Google Drive harus PUBLIC / Google Drive must be PUBLIC
            - Kolom lain bersifat opsional / Other columns are optional
            """)
        
        st.markdown("")
        
        roles = load_roles()
        if not roles:
            st.warning(get_text('no_roles_available'))
            st.info(f"👉 {get_text('tab_manage_roles')}")
        else:
            role_options = list(roles.keys())
            role = st.selectbox(
                get_text('select_role'),
                role_options,
                format_func=lambda x: x.replace('_', ' ').title(),
                key='excel_selected_role'
            )
            
            with st.expander(get_text('view_skills_expander'), expanded=False):
                st.markdown(roles[role])
            
            st.markdown("---")
            
            excel_file = st.file_uploader(
                get_text('upload_excel_label'),
                type=['xlsx', 'xls'],
                key='excel_uploader'
            )
            
            if excel_file:
                st.success(f"📁 {get_text('excel_uploaded')}: {excel_file.name}")
                
                try:
                    df_preview = read_excel_with_cv_links(excel_file)
                    excel_file.seek(0)
                    
                    if df_preview is not None and not df_preview.empty:
                        st.markdown("### 👀 Preview Data")
                        st.dataframe(df_preview, use_container_width=True)
                        st.success(f"✅ Ditemukan {len(df_preview)} kandidat dengan link CV valid / Found {len(df_preview)} candidates with valid CV links")
                        
                        st.markdown("---")
                        
                        if st.button(get_text('download_all_cv'), type='primary', use_container_width=True):
                            with st.spinner(get_text('downloading_cv')):
                                results = process_excel_cv_links(excel_file, role)
                                
                                if results:
                                    results.sort(key=lambda x: x.get('match_percentage', 0), reverse=True)
                                    
                                    st.session_state.batch_results = results
                                    save_results_to_disk()
                                    
                                    st.success(get_text('processing_complete'))
                                    
                                    selected_count = sum(1 for r in results if r['status'] == 'selected')
                                    rejected_count = sum(1 for r in results if r['status'] == 'rejected')
                                    error_count = sum(1 for r in results if r['status'] == 'error')
                                    ocr_count = sum(1 for r in results if r.get('ocr_used', False))
                                    
                                    summary = f"🎉 {get_text('processing_complete')}\n"
                                    summary += f"📊 Total: {len(results)} | ✅ {selected_count} | ❌ {rejected_count} | ⚠️ {error_count}"
                                    if ocr_count > 0:
                                        summary += f" | 🔍 OCR: {ocr_count}"
                                    
                                    st.toast(summary, icon="✅")
                                    st.info(f"👉 {get_text('tab_results')} atau {get_text('tab_chatbot')}")
                                else:
                                    st.error(get_text('no_valid_links'))
                    else:
                        st.error(get_text('invalid_excel_format'))
                        st.markdown("""
                        **Troubleshooting:**
                        - Pastikan ada kolom dengan nama: `Link CV`, `CV Link`, atau `URL`
                        - Pastikan kolom berisi link yang valid
                        - Cek format Excel tidak rusak
                        """)
                except Exception as e:
                    st.error(f"Error reading Excel: {str(e)}")
                    logger.error(f"Excel reading error: {e}")
    
    # TAB 3: Results
    with tab3:
        if st.session_state.batch_results:
            display_results_table(st.session_state.batch_results, st.session_state.language)
        else:
            st.info(get_text('no_results_yet'))
            st.markdown("---")
            st.markdown(f"### 📤 {get_text('tab_upload')}")
            st.markdown(get_text('batch_info'))
    
    # TAB 4: Chatbot
    with tab4:
        display_chatbot_interface()

    # TAB 5: Role Management
    with tab5:
        display_role_management()
    


if __name__ == "__main__":
    main()
