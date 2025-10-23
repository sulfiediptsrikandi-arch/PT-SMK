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
    'app_title': {'id': "PT Srikandi Mitra Karya - Sistem Rekrutmen AI", 'en': "PT Srikandi Mitra Karya - AI Recruitment System"},
    'config_header': {'id': "⚙️ Konfigurasi", 'en': "⚙️ Configuration"},
    'openai_settings': {'id': "Pengaturan OpenAI", 'en': "OpenAI Settings"},
    'api_key_label': {'id': "Kunci API OpenAI", 'en': "OpenAI API Key"},
    'api_key_help': {'id': "Dapatkan kunci API Anda dari platform.openai.com", 'en': "Get your API key from platform.openai.com"},
    'warning_missing_config': {'id': "⚠️ Harap konfigurasikan hal berikut di sidebar: ", 'en': "⚠️ Please configure the following in the sidebar: "},
    'language_select': {'id': "Pilih Bahasa", 'en': "Select Language"},
    'reset_button': {'id': "🔄 Reset Aplikasi", 'en': "🔄 Reset Application"},
    'ocr_settings': {'id': "Pengaturan OCR", 'en': "OCR Settings"},
    'enable_ocr': {'id': "Aktifkan OCR untuk PDF Gambar", 'en': "Enable OCR for Image PDFs"},
    'ocr_help': {'id': "OCR akan memindai PDF berbasis gambar untuk ekstraksi teks yang lebih baik", 'en': "OCR will scan image-based PDFs for better text extraction"},
    
    # Role Management
    'tab_manage_roles': {'id': "Kelola Posisi", 'en': "Manage Roles"},
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
    'select_role': {'id': "Pilih Posisi yang Dibutuhkan:", 'en': "Select the Required Role:"},
    'view_skills_expander': {'id': "📋 Lihat Keterampilan yang Dibutuhkan", 'en': "📋 View Required Skills"},
    
    # Mode Batch Processing
    'upload_resume_label': {'id': "Unggah resume (PDF)", 'en': "Upload resume (PDF)"},
    'batch_info': {'id': "💡 Unggah beberapa resume (PDF) untuk memprosesnya secara otomatis.", 'en': "💡 Upload multiple resumes (PDF) to process them automatically."},
    'clear_resumes_button': {'id': "🗑️ Bersihkan Resume", 'en': "🗑️ Clear Resumes"},
    'clear_resumes_help': {'id': "Hapus semua berkas PDF yang diunggah", 'en': "Remove all uploaded PDF files"},
    'resumes_uploaded': {'id': "resume(s) terunggah", 'en': "resume(s) uploaded"},
    'process_all_button': {'id': "🚀 Proses Semua Resume", 'en': "🚀 Process All Applications"},
    'processing_spinner': {'id': "Memproses aplikasi...", 'en': "Processing application..."},
    'ocr_processing': {'id': "🔍 Memindai dengan OCR...", 'en': "🔍 Scanning with OCR..."},
    
    # Hasil & Feedback
    'tab_upload': {'id': "Unggah & Proses", 'en': "Upload & Process"},
    'tab_download_excel': {'id': "📥 Download dari Excel", 'en': "📥 Download from Excel"},
    'tab_results': {'id': "Hasil & Ringkasan", 'en': "Results & Summary"},
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
    'table_col_no': {'id': "No.", 'en': "No."},
    'table_col_filename': {'id': "Nama Berkas", 'en': "File Name"},
    'table_col_candidate_name': {'id': "Nama Kandidat", 'en': "Candidate Name"}, 
    'table_col_candidate_phone': {'id': "No HP Kandidat", 'en': "Candidate Phone"}, 
    'table_col_status': {'id': "Status", 'en': "Status"},
    'table_col_role': {'id': "Posisi", 'en': "Role"},
    'table_col_match': {'id': "Match %", 'en': "Match %"},
    'table_col_feedback_short': {'id': "Umpan Balik Singkat", 'en': "Short Feedback"},
    'table_col_error': {'id': "Detail Error", 'en': "Error Detail"},
    'no_candidates_found': {'id': "Tidak ada kandidat dengan status ini.", 'en': "No candidates found with this status."},
    'role_label': {'id': "Posisi:", 'en': "Role:"},
    'status_label': {'id': "Status:", 'en': "Status:"},
    'feedback_label': {'id': "Umpan Balik:", 'en': "Feedback:"},
    'error_label': {'id': "Kesalahan:", 'en': "Error:"},
    'download_excel_button': {'id': "⬇️ Unduh Hasil (Excel)", 'en': "⬇️ Download Results (Excel)"},
    'no_results_yet': {'id': "Silakan unggah dan proses resume di tab **Unggah & Proses** untuk melihat hasilnya di sini.", 'en': "Please upload and process resumes in the **Upload & Process** tab to see the results here."},
    'detail_results_header': {'id': "### Detail Hasil Pemrosesan", 'en': "### Processing Results Details"},
    'detail_feedback_header': {'id': "### Umpan Balik Detail", 'en': "### Detailed Feedback"},
    'sorted_by_match': {'id': "📊 Kandidat diurutkan berdasarkan persentase kesesuaian (tertinggi ke terendah)", 'en': "📊 Candidates sorted by match percentage (highest to lowest)"},
    
    # Fitur Download dari Excel
    'upload_excel_label': {'id': "Upload File Excel dengan Link CV", 'en': "Upload Excel File with CV Links"},
    'excel_format_info': {'id': "💡 Format Excel harus memiliki kolom 'Link CV' atau 'CV Link' atau 'URL' yang berisi link download CV (PDF)", 'en': "💡 Excel format must have 'Link CV' or 'CV Link' or 'URL' column containing CV download links (PDF)"},
    'excel_uploaded': {'id': "File Excel terupload", 'en': "Excel file uploaded"},
    'download_all_cv': {'id': "📥 Download Semua CV", 'en': "📥 Download All CVs"},
    'downloading_cv': {'id': "Mengunduh CV...", 'en': "Downloading CVs..."},
    'download_complete': {'id': "✅ Download selesai!", 'en': "✅ Download complete!"},
    'download_error': {'id': "❌ Gagal mengunduh", 'en': "❌ Failed to download"},
    'invalid_excel_format': {'id': "❌ Format Excel tidak valid. Pastikan ada kolom 'Link CV', 'CV Link', atau 'URL'", 'en': "❌ Invalid Excel format. Ensure there is a 'Link CV', 'CV Link', or 'URL' column"},
    'no_valid_links': {'id': "⚠️ Tidak ada link CV yang valid ditemukan", 'en': "⚠️ No valid CV links found"},
    'cv_downloaded': {'id': "CV berhasil diunduh", 'en': "CV downloaded successfully"},
    'processing_downloaded_cvs': {'id': "Memproses CV yang telah diunduh...", 'en': "Processing downloaded CVs..."},
}

def get_text(key: str) -> str:
    """Mengambil teks berdasarkan kunci dan bahasa yang dipilih."""
    lang = st.session_state.get('language', 'id')
    return TEXTS.get(key, {}).get(lang, f"MISSING TEXT: {key}")

# --- Default Role requirements ---
DEFAULT_ROLE_REQUIREMENTS: Dict[str, str] = {
    "spv_civil_structural": """Required Skills:
- Pendidikan minimal S1 Teknik Sipil.
- Pengalaman minimal 5 tahun di bidang konstruksi sipil dan struktural.
- Mahir menggunakan software desain seperti AutoCAD, SAP2000, ETABS.
- Memiliki sertifikasi POP, HWP, WAH, LOTOTO, FW, CSE.""",
    
    "electrician": """Required Skills:
- Pendidikan minimal D3/SMK Teknik Elektro.
- Pengalaman minimal 1 tahun di bidang kelistrikan.
- Menguasai instalasi dan perawatan sistem kelistrikan.
- Memiliki sertifikasi kelistrikan dan P3K.""",
    
    "safety_officer": """Required Skills:
- Pendidikan minimal S1 semua jurusan.
- Pengalaman minimal 2 tahun di bidang safety.
- Memiliki sertifikasi AK3U.
- Memiliki sertifikasi HWP, WAH, LOTOTO, FW, CSE.""",
}


# --- FUNGSI UNTUK MENGATUR TEMA ---
def set_futuristic_robotic_theme():
    """Enhanced Futuristic Robotic Theme with animations and glow effects"""
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@300;500;700&display=swap');
        
        /* === GLOBAL BACKGROUND & ANIMATIONS === */
        .stApp {
            background: linear-gradient(135deg, #0a0e27 0%, #1a1f3a 50%, #0f1729 100%);
            font-family: 'Rajdhani', sans-serif;
            position: relative;
            overflow-x: hidden;
        }
        
        /* Animated Background Gradient */
        @keyframes gradientShift {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        
        .stApp::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: 
                radial-gradient(circle at 20% 80%, rgba(0, 255, 255, 0.05) 0%, transparent 50%),
                radial-gradient(circle at 80% 20%, rgba(138, 43, 226, 0.05) 0%, transparent 50%);
            pointer-events: none;
            animation: gradientShift 15s ease infinite;
            z-index: 0;
        }
        
        /* === SIDEBAR STYLING === */
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0f1729 0%, #1a1f3a 100%);
            border-right: 2px solid rgba(0, 255, 255, 0.3);
            box-shadow: 
                0 0 30px rgba(0, 255, 255, 0.2),
                inset 0 0 50px rgba(0, 0, 0, 0.5);
        }
        
        section[data-testid="stSidebar"] * {
            color: #00ffff !important;
        }
        
        /* === TYPOGRAPHY === */
        * {
            font-family: 'Rajdhani', sans-serif;
        }
        
        h1, h2, h3 {
            font-family: 'Orbitron', sans-serif !important;
            font-weight: 700;
            color: #00ffff;
            text-shadow: 
                0 0 10px rgba(0, 255, 255, 0.8),
                0 0 20px rgba(0, 255, 255, 0.5),
                0 0 30px rgba(0, 255, 255, 0.3);
            letter-spacing: 2px;
            animation: glowPulse 2s ease-in-out infinite;
        }
        
        @keyframes glowPulse {
            0%, 100% { 
                text-shadow: 
                    0 0 10px rgba(0, 255, 255, 0.8),
                    0 0 20px rgba(0, 255, 255, 0.5);
            }
            50% { 
                text-shadow: 
                    0 0 15px rgba(0, 255, 255, 1),
                    0 0 30px rgba(0, 255, 255, 0.7),
                    0 0 45px rgba(0, 255, 255, 0.5);
            }
        }
        
        /* === PRIMARY BUTTONS - CYBER STYLE === */
        .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #00ffff 0%, #0080ff 50%, #8a2be2 100%);
            background-size: 200% 200%;
            color: #000 !important;
            border: 2px solid rgba(0, 255, 255, 0.5);
            border-radius: 10px;
            font-family: 'Orbitron', sans-serif;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 2px;
            box-shadow: 
                0 0 20px rgba(0, 255, 255, 0.5),
                0 0 40px rgba(0, 128, 255, 0.3),
                inset 0 0 10px rgba(255, 255, 255, 0.2);
            transition: all 0.4s ease;
            animation: gradientShift 3s ease infinite;
            position: relative;
            overflow: hidden;
        }
        
        .stButton > button[kind="primary"]::before {
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            width: 0;
            height: 0;
            background: rgba(255, 255, 255, 0.3);
            border-radius: 50%;
            transform: translate(-50%, -50%);
            transition: width 0.6s, height 0.6s;
        }
        
        .stButton > button[kind="primary"]:hover {
            background: linear-gradient(135deg, #00ffff 0%, #00bfff 50%, #8a2be2 100%);
            box-shadow: 
                0 0 30px rgba(0, 255, 255, 0.8),
                0 0 60px rgba(0, 128, 255, 0.5),
                0 0 90px rgba(138, 43, 226, 0.3);
            transform: translateY(-3px) scale(1.05);
            border-color: rgba(0, 255, 255, 1);
        }
        
        .stButton > button[kind="primary"]:hover::before {
            width: 300px;
            height: 300px;
        }
        
        .stButton > button[kind="primary"]:active {
            transform: translateY(0) scale(0.98);
            box-shadow: 
                0 0 15px rgba(0, 255, 255, 0.6),
                inset 0 0 20px rgba(0, 0, 0, 0.3);
        }
        
        /* === SECONDARY BUTTONS === */
        .stButton > button[kind="secondary"] {
            background: linear-gradient(135deg, rgba(26, 31, 58, 0.8) 0%, rgba(15, 23, 41, 0.9) 100%);
            color: #00ffff !important;
            border: 2px solid rgba(0, 255, 255, 0.3);
            border-radius: 10px;
            font-family: 'Rajdhani', sans-serif;
            font-weight: 500;
            box-shadow: 
                0 0 10px rgba(0, 255, 255, 0.2),
                inset 0 0 10px rgba(0, 0, 0, 0.5);
            transition: all 0.3s ease;
        }
        
        .stButton > button[kind="secondary"]:hover {
            background: linear-gradient(135deg, rgba(26, 31, 58, 1) 0%, rgba(15, 23, 41, 1) 100%);
            border-color: rgba(0, 255, 255, 0.8);
            box-shadow: 
                0 0 20px rgba(0, 255, 255, 0.4),
                inset 0 0 15px rgba(0, 255, 255, 0.1);
            transform: translateY(-2px);
        }
        
        /* === DOWNLOAD BUTTON === */
        .stDownloadButton > button {
            background: linear-gradient(135deg, #00ff88 0%, #00cc66 100%);
            background-size: 200% 200%;
            color: #000 !important;
            border: 2px solid rgba(0, 255, 136, 0.5);
            border-radius: 10px;
            font-family: 'Orbitron', sans-serif;
            font-weight: 700;
            box-shadow: 
                0 0 20px rgba(0, 255, 136, 0.5),
                inset 0 0 10px rgba(255, 255, 255, 0.2);
            transition: all 0.3s ease;
            animation: gradientShift 3s ease infinite;
        }
        
        .stDownloadButton > button:hover {
            box-shadow: 
                0 0 30px rgba(0, 255, 136, 0.8),
                0 0 60px rgba(0, 204, 102, 0.5);
            transform: translateY(-3px) scale(1.05);
        }
        
        /* === METRICS - HOLOGRAPHIC CARDS === */
        div[data-testid="stMetric"] {
            background: linear-gradient(135deg, rgba(26, 31, 58, 0.6) 0%, rgba(15, 23, 41, 0.8) 100%);
            backdrop-filter: blur(10px);
            padding: 20px;
            border-radius: 15px;
            border: 2px solid rgba(0, 255, 255, 0.3);
            box-shadow: 
                0 0 30px rgba(0, 255, 255, 0.2),
                inset 0 0 20px rgba(0, 0, 0, 0.5);
            transition: all 0.4s ease;
            position: relative;
            overflow: hidden;
        }
        
        div[data-testid="stMetric"]::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: linear-gradient(
                45deg,
                transparent 30%,
                rgba(0, 255, 255, 0.1) 50%,
                transparent 70%
            );
            animation: hologramScan 3s linear infinite;
        }
        
        @keyframes hologramScan {
            0% { transform: translateX(-100%) translateY(-100%) rotate(45deg); }
            100% { transform: translateX(100%) translateY(100%) rotate(45deg); }
        }
        
        div[data-testid="stMetric"]:hover {
            border-color: rgba(0, 255, 255, 0.8);
            box-shadow: 
                0 0 40px rgba(0, 255, 255, 0.4),
                inset 0 0 30px rgba(0, 255, 255, 0.1);
            transform: translateY(-5px) scale(1.02);
        }
        
        [data-testid="stMetricValue"] {
            font-size: 2.5rem !important;
            font-weight: 900 !important;
            font-family: 'Orbitron', sans-serif !important;
            color: #00ffff !important;
            text-shadow: 
                0 0 10px rgba(0, 255, 255, 1),
                0 0 20px rgba(0, 255, 255, 0.7),
                0 0 30px rgba(0, 255, 255, 0.5);
        }
        
        /* === TABS - FUTURISTIC STYLE === */
        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
            background: transparent;
        }
        
        .stTabs [data-baseweb="tab"] {
            background: linear-gradient(135deg, rgba(26, 31, 58, 0.6) 0%, rgba(15, 23, 41, 0.8) 100%);
            border: 2px solid rgba(0, 255, 255, 0.2);
            border-radius: 10px 10px 0 0;
            color: #00ffff !important;
            font-family: 'Rajdhani', sans-serif;
            font-weight: 500;
            padding: 12px 24px;
            transition: all 0.3s ease;
            box-shadow: 0 0 10px rgba(0, 255, 255, 0.1);
        }
        
        .stTabs [data-baseweb="tab"]:hover {
            background: linear-gradient(135deg, rgba(26, 31, 58, 0.8) 0%, rgba(15, 23, 41, 1) 100%);
            border-color: rgba(0, 255, 255, 0.5);
            box-shadow: 0 0 20px rgba(0, 255, 255, 0.3);
            transform: translateY(-2px);
        }
        
        .stTabs [data-baseweb="tab"][aria-selected="true"] {
            background: linear-gradient(135deg, #00ffff 0%, #0080ff 100%);
            color: #000 !important;
            border-color: #00ffff;
            box-shadow: 
                0 0 30px rgba(0, 255, 255, 0.6),
                0 5px 15px rgba(0, 0, 0, 0.3);
        }
        
        /* === FILE UPLOADER === */
        [data-testid="stFileUploader"] {
            background: linear-gradient(135deg, rgba(26, 31, 58, 0.4) 0%, rgba(15, 23, 41, 0.6) 100%);
            backdrop-filter: blur(10px);
            border: 2px dashed rgba(0, 255, 255, 0.3);
            border-radius: 15px;
            padding: 30px;
            box-shadow: 
                0 0 20px rgba(0, 255, 255, 0.1),
                inset 0 0 20px rgba(0, 0, 0, 0.3);
            transition: all 0.3s ease;
        }
        
        [data-testid="stFileUploader"]:hover {
            border-color: rgba(0, 255, 255, 0.6);
            box-shadow: 
                0 0 30px rgba(0, 255, 255, 0.3),
                inset 0 0 30px rgba(0, 255, 255, 0.05);
        }
        
        /* === EXPANDERS === */
        .streamlit-expanderHeader {
            background: linear-gradient(135deg, rgba(26, 31, 58, 0.6) 0%, rgba(15, 23, 41, 0.8) 100%);
            border: 2px solid rgba(0, 255, 255, 0.3);
            border-radius: 10px;
            color: #00ffff !important;
            font-family: 'Rajdhani', sans-serif;
            font-weight: 500;
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.2);
            transition: all 0.3s ease;
        }
        
        .streamlit-expanderHeader:hover {
            background: linear-gradient(135deg, rgba(26, 31, 58, 0.8) 0%, rgba(15, 23, 41, 1) 100%);
            border-color: rgba(0, 255, 255, 0.6);
            box-shadow: 0 0 25px rgba(0, 255, 255, 0.4);
            transform: translateX(5px);
        }
        
        /* === TEXT INPUTS === */
        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea {
            background: rgba(15, 23, 41, 0.8) !important;
            border: 2px solid rgba(0, 255, 255, 0.3) !important;
            border-radius: 8px !important;
            color: #00ffff !important;
            font-family: 'Rajdhani', sans-serif;
            box-shadow: inset 0 0 10px rgba(0, 0, 0, 0.5);
            transition: all 0.3s ease;
        }
        
        .stTextInput > div > div > input:focus,
        .stTextArea > div > div > textarea:focus {
            border-color: rgba(0, 255, 255, 0.8) !important;
            box-shadow: 
                inset 0 0 10px rgba(0, 0, 0, 0.5),
                0 0 20px rgba(0, 255, 255, 0.3) !important;
        }
        
        /* === LOADING SPINNER === */
        .stSpinner > div {
            border-color: #00ffff transparent #00ffff transparent !important;
            animation: spin 1s linear infinite, glow 2s ease-in-out infinite;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        @keyframes glow {
            0%, 100% { filter: drop-shadow(0 0 5px rgba(0, 255, 255, 0.5)); }
            50% { filter: drop-shadow(0 0 20px rgba(0, 255, 255, 1)); }
        }
        
        /* === SCROLLBAR === */
        ::-webkit-scrollbar {
            width: 12px;
            height: 12px;
        }
        
        ::-webkit-scrollbar-track {
            background: rgba(15, 23, 41, 0.5);
            border-radius: 10px;
        }
        
        ::-webkit-scrollbar-thumb {
            background: linear-gradient(135deg, #00ffff 0%, #0080ff 100%);
            border-radius: 10px;
            box-shadow: 0 0 10px rgba(0, 255, 255, 0.5);
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: linear-gradient(135deg, #00ffff 0%, #00bfff 100%);
            box-shadow: 0 0 20px rgba(0, 255, 255, 0.8);
        }
        
        /* === GENERAL TEXT COLOR === */
        p, label, span, div {
            color: #00ffff !important;
        }
        
        /* === ANIMATION FOR LOGO === */
        @keyframes logoGlow {
            0%, 100% {
                filter: drop-shadow(0 0 10px rgba(0, 255, 255, 0.5));
            }
            50% {
                filter: drop-shadow(0 0 30px rgba(0, 255, 255, 1))
                        drop-shadow(0 0 50px rgba(138, 43, 226, 0.5));
            }
        }
        
        img {
            animation: logoGlow 3s ease-in-out infinite;
        }
        
        </style>
    """, unsafe_allow_html=True)


# --- FUNGSI OCR ---
def extract_text_with_ocr(pdf_file) -> Tuple[str, bool]:
    """
    Extract text from PDF with OCR support for image-based PDFs.
    Returns: (extracted_text, ocr_used)
    """
    if not OCR_AVAILABLE:
        logger.warning("OCR not available. Falling back to standard extraction.")
        return extract_text_from_pdf(pdf_file), False
    
    try:
        # Try standard extraction first
        pdf_file.seek(0)
        standard_text = extract_text_from_pdf(pdf_file)
        
        # If we got enough text, return it
        if standard_text and len(standard_text.strip()) > 100:
            return standard_text, False
        
        # Otherwise, use OCR
        logger.info("Standard extraction insufficient. Using OCR...")
        pdf_file.seek(0)
        pdf_bytes = pdf_file.read()
        
        # Convert PDF to images
        images = convert_from_bytes(pdf_bytes, dpi=300)
        
        ocr_text = ""
        for i, image in enumerate(images):
            logger.info(f"OCR processing page {i+1}/{len(images)}")
            # Extract text from image using Tesseract
            page_text = pytesseract.image_to_string(image, lang='eng+ind')
            ocr_text += page_text + "\n\n"
        
        # Combine standard and OCR text
        combined_text = standard_text + "\n\n" + ocr_text
        return combined_text.strip(), True
        
    except Exception as e:
        logger.error(f"OCR extraction failed: {e}")
        # Fallback to standard extraction
        pdf_file.seek(0)
        return extract_text_from_pdf(pdf_file), False


# --- FUNGSI MEMORY MANAGEMENT ---
def save_to_memory(result: dict):
    """Save analysis result to memory with timestamp and auto-save to disk."""
    if 'analysis_memory' not in st.session_state:
        st.session_state.analysis_memory = []
    
    # Add timestamp and unique ID
    memory_entry = {
        'id': str(uuid.uuid4()),
        'timestamp': datetime.now().isoformat(),
        'data': result
    }
    
    st.session_state.analysis_memory.append(memory_entry)
    
    # Keep only last 100 entries to prevent memory overflow
    if len(st.session_state.analysis_memory) > 100:
        st.session_state.analysis_memory = st.session_state.analysis_memory[-100:]
    
    # Auto-save to disk
    save_memory_to_disk()

def get_memory_context() -> str:
    """Get formatted memory context for chatbot."""
    if 'analysis_memory' not in st.session_state or not st.session_state.analysis_memory:
        return "No previous analysis in memory."
    
    context = "Previous Analysis Summary:\n\n"
    for entry in st.session_state.analysis_memory[-10:]:  # Last 10 entries
        data = entry['data']
        context += f"- {data.get('candidate_name', 'Unknown')}: {data.get('status', 'unknown').upper()} "
        context += f"(Match: {data.get('match_percentage', 0)}%)\n"
    
    return context

def get_current_results_context() -> str:
    """Get formatted context of current batch results."""
    if 'batch_results' not in st.session_state or not st.session_state.batch_results:
        return "No current results available."
    
    results = st.session_state.batch_results
    context = f"Current Batch Analysis ({len(results)} candidates):\n\n"
    
    for i, result in enumerate(results, 1):
        context += f"{i}. {result.get('candidate_name', 'N/A')} - {result.get('filename', 'N/A')}\n"
        context += f"   Status: {result.get('status', 'unknown').upper()}\n"
        context += f"   Match: {result.get('match_percentage', 0)}%\n"
        context += f"   Role: {result.get('role', 'N/A')}\n"
        if result.get('matching_skills'):
            context += f"   Matching Skills: {', '.join(result['matching_skills'][:3])}\n"
        context += "\n"
    
    return context


# --- FUNGSI PERSISTENT STORAGE ---
def save_to_file(filepath: Path, data: any) -> bool:
    """Save data to JSON file."""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Error saving to {filepath}: {e}")
        return False

def load_from_file(filepath: Path, default: any = None) -> any:
    """Load data from JSON file."""
    try:
        if filepath.exists():
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading from {filepath}: {e}")
    return default if default is not None else {}

def save_roles_to_disk():
    """Save roles to disk."""
    roles = st.session_state.get('role_requirements', DEFAULT_ROLE_REQUIREMENTS)
    save_to_file(ROLES_FILE, roles)
    logger.info("Roles saved to disk")

def load_roles_from_disk() -> Dict[str, str]:
    """Load roles from disk."""
    roles = load_from_file(ROLES_FILE, DEFAULT_ROLE_REQUIREMENTS.copy())
    logger.info(f"Loaded {len(roles)} roles from disk")
    return roles

def save_memory_to_disk():
    """Save analysis memory to disk."""
    memory = st.session_state.get('analysis_memory', [])
    save_to_file(MEMORY_FILE, memory)

def load_memory_from_disk() -> List[Dict]:
    """Load analysis memory from disk."""
    memory = load_from_file(MEMORY_FILE, [])
    logger.info(f"Loaded {len(memory)} memory entries from disk")
    return memory

def save_chat_history_to_disk():
    """Save chat history to disk."""
    history = st.session_state.get('chat_history', [])
    save_to_file(CHAT_HISTORY_FILE, history)

def load_chat_history_from_disk() -> List[Dict]:
    """Load chat history from disk."""
    history = load_from_file(CHAT_HISTORY_FILE, [])
    logger.info(f"Loaded {len(history)} chat messages from disk")
    return history

def save_results_to_disk():
    """Save batch results to disk."""
    results = st.session_state.get('batch_results', [])
    save_to_file(RESULTS_FILE, results)

def load_results_from_disk() -> List[Dict]:
    """Load batch results from disk."""
    results = load_from_file(RESULTS_FILE, [])
    logger.info(f"Loaded {len(results)} results from disk")
    return results

def clear_all_data():
    """Clear all persistent data."""
    try:
        for filepath in [ROLES_FILE, MEMORY_FILE, CHAT_HISTORY_FILE, RESULTS_FILE]:
            if filepath.exists():
                filepath.unlink()
        logger.info("All persistent data cleared")
        return True
    except Exception as e:
        logger.error(f"Error clearing data: {e}")
        return False

def export_all_data() -> str:
    """Export all data as JSON string."""
    data = {
        'roles': st.session_state.get('role_requirements', {}),
        'memory': st.session_state.get('analysis_memory', []),
        'chat_history': st.session_state.get('chat_history', []),
        'results': st.session_state.get('batch_results', []),
        'export_date': datetime.now().isoformat()
    }
    return json.dumps(data, indent=2, ensure_ascii=False)

def import_all_data(json_str: str) -> bool:
    """Import all data from JSON string."""
    try:
        data = json.loads(json_str)
        
        if 'roles' in data:
            st.session_state.role_requirements = data['roles']
            save_roles_to_disk()
        
        if 'memory' in data:
            st.session_state.analysis_memory = data['memory']
            save_memory_to_disk()
        
        if 'chat_history' in data:
            st.session_state.chat_history = data['chat_history']
            save_chat_history_to_disk()
        
        if 'results' in data:
            st.session_state.batch_results = data['results']
            save_results_to_disk()
        
        return True
    except Exception as e:
        logger.error(f"Error importing data: {e}")
        return False


# --- FUNGSI ROLE MANAGEMENT ---
def load_roles() -> Dict[str, str]:
    """Load roles from session state or disk."""
    if 'role_requirements' not in st.session_state:
        st.session_state.role_requirements = load_roles_from_disk()
    return st.session_state.role_requirements

def save_role(role_id: str, requirements: str) -> bool:
    """Save or update a role."""
    roles = load_roles()
    roles[role_id] = requirements
    st.session_state.role_requirements = roles
    save_roles_to_disk()
    return True

def delete_role(role_id: str) -> bool:
    """Delete a role."""
    roles = load_roles()
    if role_id in roles:
        del roles[role_id]
        st.session_state.role_requirements = roles
        save_roles_to_disk()
        return True
    return False

def export_roles_json() -> str:
    """Export roles to JSON string."""
    roles = load_roles()
    return json.dumps(roles, indent=2, ensure_ascii=False)

def import_roles_json(json_str: str) -> bool:
    """Import roles from JSON string."""
    try:
        roles = json.loads(json_str)
        if isinstance(roles, dict):
            st.session_state.role_requirements = roles
            return True
    except:
        pass
    return False

def is_valid_role_id(role_id: str) -> bool:
    """Validate role ID format."""
    return bool(re.match(r'^[a-z0-9_]+$', role_id))


# --- FUNGSI DOWNLOAD CV DARI EXCEL ---
def is_valid_url(url: str) -> bool:
    """Check if URL is valid."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def convert_google_drive_link(url: str) -> str:
    """
    Convert Google Drive view link to direct download link.
    
    Formats handled:
    - https://drive.google.com/file/d/FILE_ID/view
    - https://drive.google.com/open?id=FILE_ID
    - https://drive.google.com/file/d/FILE_ID/view?usp=sharing
    
    Returns direct download link:
    - https://drive.google.com/uc?export=download&id=FILE_ID
    """
    # Check if it's a Google Drive link
    if 'drive.google.com' not in url:
        return url
    
    # Extract file ID from different formats
    file_id = None
    
    # Format 1: /file/d/FILE_ID/view
    match = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
    if match:
        file_id = match.group(1)
    
    # Format 2: open?id=FILE_ID or ?id=FILE_ID
    if not file_id:
        match = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', url)
        if match:
            file_id = match.group(1)
    
    # If we found a file ID, convert to direct download
    if file_id:
        direct_link = f"https://drive.google.com/uc?export=download&id={file_id}"
        logger.info(f"Converted Google Drive link: {url} -> {direct_link}")
        return direct_link
    
    # Return original if we couldn't extract file ID
    logger.warning(f"Could not extract file ID from Google Drive link: {url}")
    return url

def is_google_auth_error(content: bytes) -> bool:
    """
    Check if the downloaded content is a Google authentication/login page.
    Returns True if it's an auth error (private file).
    """
    if not content:
        return False
    
    # Check first 500 bytes for common Google auth patterns
    content_start = content[:500].decode('utf-8', errors='ignore').lower()
    
    auth_patterns = [
        'sign in',
        'google accounts',
        'accounts.google.com',
        'accounts/servicelogin',
        'you need permission',
        'request access',
        'access denied'
    ]
    
    return any(pattern in content_start for pattern in auth_patterns)

def download_cv_from_url(url: str, candidate_name: str = "unknown") -> Optional[BytesIO]:
    """Download CV from URL and return as BytesIO object. Supports Google Drive links."""
    try:
        safe_name = re.sub(r'[^\w\s-]', '', candidate_name).strip().replace(' ', '_')
        
        # Convert Google Drive links to direct download format
        original_url = url
        url = convert_google_drive_link(url)
        if url != original_url:
            logger.info(f"Using converted Google Drive link for {candidate_name}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        logger.info(f"Downloading CV from: {url}")
        response = requests.get(url, headers=headers, timeout=30, stream=True, allow_redirects=True)
        response.raise_for_status()
        
        content_type = response.headers.get('Content-Type', '')
        content_length = len(response.content)
        logger.info(f"Downloaded {content_length} bytes, Content-Type: {content_type}")
        
        # Check if we got a Google authentication page instead of the file
        if is_google_auth_error(response.content):
            logger.error(f"Google Drive authentication required for {candidate_name}")
            logger.error(f"The file at {original_url} is PRIVATE and requires Google login")
            return None  # Return None to trigger specific error message
        
        # Warning saja jika content type bukan PDF, tapi tetap lanjutkan
        if 'pdf' not in content_type.lower() and not url.lower().endswith('.pdf'):
            logger.warning(f"URL may not be a PDF: {url} (Content-Type: {content_type})")
            # Hanya cek header sebagai warning, jangan langsung reject
            if not response.content.startswith(b'%PDF'):
                logger.warning(f"Downloaded content may not be a PDF. First bytes: {response.content[:20]}")
                # Check if it's HTML (likely an error page)
                if response.content.startswith(b'<!DOCTYPE') or response.content.startswith(b'<html'):
                    logger.error(f"Downloaded HTML instead of PDF - likely authentication or access issue")
                    return None
        
        cv_file = BytesIO(response.content)
        cv_file.name = f"{safe_name}.pdf"
        cv_file.seek(0)
        
        logger.info(f"Successfully created BytesIO for {safe_name}.pdf")
        return cv_file
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading CV from {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error downloading CV: {e}")
        return None

def read_excel_with_cv_links(excel_file) -> Optional[pd.DataFrame]:
    """Read Excel file and extract CV links."""
    try:
        df = pd.read_excel(excel_file)
        
        cv_link_columns = ['link cv', 'cv link', 'url', 'link', 'cv url', 'resume link']
        cv_col = None
        
        for col in df.columns:
            if col.lower().strip() in cv_link_columns:
                cv_col = col
                break
        
        if cv_col is None:
            return None
        
        name_columns = ['nama', 'name', 'nama kandidat', 'candidate name', 'full name']
        name_col = None
        
        for col in df.columns:
            if col.lower().strip() in name_columns:
                name_col = col
                break
        
        result_df = pd.DataFrame()
        result_df['cv_link'] = df[cv_col]
        
        if name_col:
            result_df['candidate_name'] = df[name_col]
        else:
            result_df['candidate_name'] = [f"Candidate_{i+1}" for i in range(len(df))]
        
        result_df = result_df[result_df['cv_link'].notna()]
        result_df = result_df[result_df['cv_link'].astype(str).str.strip() != '']
        
        return result_df
        
    except Exception as e:
        logger.error(f"Error reading Excel file: {e}")
        return None

def process_excel_cv_links(excel_file, role: str) -> List[Dict]:
    """Process CVs from Excel file with links."""
    results = []
    
    df = read_excel_with_cv_links(excel_file)
    
    if df is None or df.empty:
        return []
    
    total_cvs = len(df)
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, row in df.iterrows():
        cv_link = row['cv_link']
        candidate_name = row['candidate_name']
        
        progress = idx / total_cvs
        progress_bar.progress(progress)
        status_text.text(f"⏳ {get_text('downloading_cv')} {idx+1}/{total_cvs}: {candidate_name}")
        
        result = {
            'filename': f"{candidate_name}.pdf",
            'role': role,
            'status': 'pending',
            'selected': False,
            'feedback': '',
            'error': None,
            'candidate_name': candidate_name,
            'candidate_phone': 'N/A',
            'match_percentage': 0,
            'ocr_used': False,
            'cv_link': cv_link
        }
        
        if not is_valid_url(cv_link):
            result['error'] = f"Invalid URL: {cv_link}"
            result['status'] = 'error'
            results.append(result)
            st.warning(f"⚠️ {candidate_name}: Invalid URL")
            continue
        
        cv_file = download_cv_from_url(cv_link, candidate_name)
        
        if cv_file is None:
            # Check if it's a Google Drive link that might be private
            if 'drive.google.com' in cv_link:
                error_msg = "🔒 File Google Drive PRIVATE - Butuh akses"
                result['error'] = f"Google Drive file is PRIVATE. Please set to public: {cv_link}"
                st.error(f"❌ {candidate_name}: {error_msg}")
                st.info("""
                💡 **Cara Set File Google Drive ke Public:**
                1. Buka Google Drive
                2. Klik kanan file/folder → Share/Bagikan
                3. Ubah ke: "Anyone with the link" / "Siapa saja yang memiliki link"
                4. Permission: "Viewer" / "Dapat melihat"
                5. Klik Done/Selesai
                """)
            else:
                result['error'] = f"{get_text('download_error')}: {cv_link}"
                st.warning(f"❌ {candidate_name}: {get_text('download_error')}")
            
            result['status'] = 'error'
            results.append(result)
            continue
        
        st.info(f"✅ {candidate_name}: {get_text('cv_downloaded')}")
        
        status_text.text(f"⏳ {get_text('processing_status')} {idx+1}/{total_cvs}: {candidate_name}")
        
        try:
            # Validasi bahwa file adalah PDF yang valid (soft check)
            cv_file.seek(0)
            header = cv_file.read(5)  # Baca 5 bytes untuk cek %PDF
            cv_file.seek(0)
            
            # Cek apakah dimulai dengan %PDF (bukan exact match)
            if not header.startswith(b'%PDF'):
                logger.warning(f"File may not be a valid PDF. Header: {header}")
                st.warning(f"⚠️ {candidate_name}: File mungkin bukan PDF valid, tetap mencoba ekstraksi...")
                # Tetap lanjutkan, biarkan ekstraksi PDF yang handle
            
            # Ekstrak teks dari PDF
            try:
                if st.session_state.get('enable_ocr', False):
                    text, ocr_used = extract_text_with_ocr(cv_file)
                    result['ocr_used'] = ocr_used
                else:
                    cv_file.seek(0)  # Pastikan posisi file di awal
                    text = extract_text_from_pdf(cv_file)
                    result['ocr_used'] = False
                
                logger.info(f"Extracted {len(text)} characters from {candidate_name}'s CV")
            except Exception as extract_error:
                logger.error(f"Error extracting text from {candidate_name}: {extract_error}")
                result['error'] = f"Gagal ekstraksi PDF: {str(extract_error)}"
                result['status'] = 'error'
                results.append(result)
                st.warning(f"⚠️ {candidate_name}: Gagal mengekstrak PDF - {str(extract_error)}")
                continue
            
            if not text or len(text.strip()) < 50:
                result['error'] = f"{get_text('error_pdf_text')} - Teks terlalu pendek: {len(text.strip())} karakter"
                result['status'] = 'error'
                results.append(result)
                st.warning(f"⚠️ {candidate_name}: Tidak dapat mengekstrak teks dari PDF (teks: {len(text.strip())} karakter)")
                continue
            
            analyzer = create_resume_analyzer()
            if not analyzer:
                result['error'] = get_text('error_api_key')
                result['status'] = 'error'
                results.append(result)
                continue
            
            selected, feedback, details = analyze_resume(text, role, analyzer)
            
            result.update({
                'selected': selected,
                'feedback': feedback,
                'status': 'selected' if selected else 'rejected',
                'candidate_name': details.get('candidate_name', candidate_name),
                'candidate_phone': details.get('candidate_phone', 'N/A'),
                'match_percentage': details.get('match_percentage', 0),
            })
            
            if 'matching_skills' in details:
                result['matching_skills'] = details['matching_skills']
            if 'missing_skills' in details:
                result['missing_skills'] = details['missing_skills']
            if 'experience_level' in details:
                result['experience_level'] = details['experience_level']
            
            if result['status'] != 'error':
                save_to_memory(result)
            
            status_map = {
                'selected': 'DIREKOMENDASIKAN',
                'rejected': 'TIDAK DIREKOMENDASIKAN',
                'error': 'ERROR'
            } if st.session_state.language == 'id' else {
                'selected': 'RECOMMENDED',
                'rejected': 'NOT RECOMMENDED',
                'error': 'ERROR'
            }
            status_display = status_map.get(result['status'], 'UNKNOWN')
            icon = "✅" if result['status'] == 'selected' else ("❌" if result['status'] == 'rejected' else "⚠️")
            
            match_info = f" ({int(result.get('match_percentage', 0))}%)" if result.get('match_percentage') else ""
            st.write(f"{icon} {candidate_name}: {status_display}{match_info}")
            
        except Exception as e:
            logger.error(f"Error processing {candidate_name}: {e}")
            result['error'] = f"Processing Error: {str(e)}"
            result['status'] = 'error'
        
        results.append(result)
    
    progress_bar.progress(1.0)
    status_text.text(get_text('processing_complete'))
    
    return results


# --- FUNGSI PEMBANTU LAINNYA ---
def init_session_state() -> None:
    """Initialize session state variables with data from disk."""
    defaults = {
        'openai_api_key': "",
        'batch_results': load_results_from_disk(),
        'language': 'id',
        'uploader_key': str(uuid.uuid4()),
        'role_requirements': load_roles_from_disk(),
        'enable_ocr': OCR_AVAILABLE,
        'chat_history': load_chat_history_from_disk(),
        'analysis_memory': load_memory_from_disk(),
        'data_loaded': False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    
    if not st.session_state.get('data_loaded', False):
        total_items = (
            len(st.session_state.role_requirements) +
            len(st.session_state.analysis_memory) +
            len(st.session_state.batch_results) +
            len(st.session_state.chat_history)
        )
        if total_items > 0:
            st.session_state.data_loaded = True
            logger.info(f"Loaded {total_items} items from persistent storage")

def create_resume_analyzer() -> Optional[Agent]:
    """Creates and returns a resume analysis agent with strict consistency settings."""
    if not st.session_state.openai_api_key:
        return None
    
    return Agent(
        model=OpenAIChat(
            id="gpt-4o",
            api_key=st.session_state.openai_api_key,
            temperature=0,
            response_format={"type": "json_object"}
        ),
        description="Expert technical recruiter who analyzes resumes with strict consistency.",
        instructions=[
            "You are a highly consistent resume analyzer.",
            "Always analyze resumes objectively using the EXACT same criteria.",
            "Return ONLY valid JSON - no explanations, no markdown, no extra text.",
            "Be strict and objective in your evaluation.",
            "Apply the same standards to all candidates equally.",
            "Use deterministic scoring methodology for consistency."
        ],
        markdown=False
    )

def create_chatbot_agent() -> Optional[Agent]:
    """Creates and returns a chatbot agent for recruitment assistance."""
    if not st.session_state.openai_api_key:
        return None
    
    lang_code = st.session_state.get('language', 'id')
    language = "Indonesian" if lang_code == 'id' else "English"
    
    return Agent(
        model=OpenAIChat(
            id="gpt-4o",
            api_key=st.session_state.openai_api_key,
            temperature=0.7,
        ),
        description="Helpful AI recruitment assistant with access to analysis results.",
        instructions=[
            f"You are a helpful recruitment assistant speaking in {language}.",
            "You have access to candidate analysis results and can provide insights.",
            "Be professional, friendly, and helpful.",
            "Provide actionable recommendations based on the data.",
            "If asked about specific candidates, reference their names and details.",
            "Help recruiters make informed decisions.",
            f"Always respond in {language} language.",
            "Be concise but informative."
        ],
        markdown=True
    )

def extract_text_from_pdf(pdf_file) -> str:
    """Extracts text from PDF file."""
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text
    except Exception as e:
        logger.error(f"Error extracting PDF: {e}")
        return ""

def extract_json_from_response(response_text: str) -> dict:
    """Extract JSON from response with multiple fallback methods."""
    if not response_text:
        raise ValueError("Empty response")
    
    try:
        return json.loads(response_text.strip())
    except json.JSONDecodeError:
        pass
    
    cleaned = re.sub(r'```(?:json)?\s*|\s*```', '', response_text, flags=re.IGNORECASE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    
    json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    matches = re.findall(json_pattern, response_text, re.DOTALL)
    
    for match in matches:
        try:
            parsed = json.loads(match)
            if all(k in parsed for k in ["selected", "feedback", "candidate_name", "candidate_phone"]):
                return parsed
        except json.JSONDecodeError:
            continue
    
    try:
        fixed = re.sub(r',(\s*[}\]])', r'\1', response_text)
        fixed = re.sub(r'//.*?\n|/\*.*?\*/', '', fixed, flags=re.DOTALL)
        return json.loads(fixed)
    except:
        pass
    
    raise ValueError(f"Could not extract valid JSON from response: {response_text[:200]}")

def validate_analysis_result(result: dict) -> bool:
    """Validate analysis result structure."""
    required_keys = ["selected", "feedback", "candidate_name", "candidate_phone"]
    
    if not all(k in result for k in required_keys):
        return False
    
    if not isinstance(result["selected"], bool):
        return False
    
    if not isinstance(result["feedback"], str) or len(result["feedback"]) < 10:
        return False
    
    if not isinstance(result["candidate_name"], str):
        return False
    
    if not isinstance(result["candidate_phone"], str):
        return False
    
    return True

def calculate_consistent_score(resume_text: str, requirements: str) -> dict:
    """Calculate a deterministic matching score based on keyword analysis."""
    req_lower = requirements.lower()
    
    education_keywords = ['s1', 's2', 's3', 'd3', 'd4', 'sarjana', 'magister', 'diploma', 'bachelor', 'master']
    experience_keywords = ['tahun', 'year', 'pengalaman', 'experience']
    certification_keywords = ['sertifikasi', 'certification', 'certified', 'license', 'ak3']
    
    resume_lower = resume_text.lower()
    
    education_match = any(kw in resume_lower for kw in education_keywords)
    
    experience_years = re.findall(r'(\d+)\s*(?:tahun|year)', resume_lower)
    has_experience = len(experience_years) > 0
    
    has_certifications = any(kw in resume_lower for kw in certification_keywords)
    
    score = 0
    if education_match:
        score += 30
    if has_experience:
        score += 30
    if has_certifications:
        score += 25
    
    req_words = set(re.findall(r'\b\w{4,}\b', req_lower))
    resume_words = set(re.findall(r'\b\w{4,}\b', resume_lower))
    common_words = req_words.intersection(resume_words)
    
    if len(req_words) > 0:
        keyword_score = (len(common_words) / len(req_words)) * 15
        score += keyword_score
    
    return {
        'score': min(int(score), 100),
        'education_match': education_match,
        'has_experience': has_experience,
        'has_certifications': has_certifications,
        'matching_keywords': len(common_words)
    }

def analyze_resume(resume_text: str, role: str, analyzer: Agent, max_retries: int = 3) -> Tuple[bool, str, dict]:
    """Analyze resume with retry mechanism and strict validation."""
    lang_code = st.session_state.get('language', 'id')
    feedback_lang = "Indonesian" if lang_code == 'id' else "English"
    
    roles = load_roles()
    requirements = roles.get(role, "")
    
    baseline_analysis = calculate_consistent_score(resume_text, requirements)
    baseline_score = baseline_analysis['score']
    
    resume_hash = hashlib.md5(resume_text.encode()).hexdigest()[:8]
    
    prompt = f"""You are an objective resume analyzer. Analyze this resume strictly and consistently.

RESUME HASH: {resume_hash} (for consistency tracking)

ROLE REQUIREMENTS:
{requirements}

RESUME TEXT:
{resume_text}

BASELINE ANALYSIS (Use this as reference):
- Calculated Score: {baseline_score}%
- Education Match: {baseline_analysis['education_match']}
- Experience Found: {baseline_analysis['has_experience']}
- Certifications: {baseline_analysis['has_certifications']}
- Matching Keywords: {baseline_analysis['matching_keywords']}

EVALUATION CRITERIA (Apply these EXACTLY the same way for every candidate):
1. Education match (30%): Does education meet minimum requirements?
2. Experience match (30%): Does experience meet minimum years required?
3. Skills match (25%): Count matching skills vs required skills
4. Certifications (15%): Does candidate have required certifications?

SCORING RULES (Be strict and deterministic):
- Score must be between 0-100
- If score >= 70: selected = true
- If score < 70: selected = false
- Use the baseline score as a reference point
- Adjust only based on specific factors found in the resume

OUTPUT REQUIREMENTS:
- Return ONLY a valid JSON object
- No markdown formatting, no code blocks, no extra text
- Feedback must be in {feedback_lang}
- Be professional, specific, and consistent

Required JSON structure:
{{
    "candidate_name": "Full Name from Resume or 'N/A'",
    "candidate_phone": "Phone Number or 'N/A'",
    "selected": true or false,
    "feedback": "Professional evaluation in {feedback_lang} (minimum 100 words, explain specific match/mismatch with examples)",
    "matching_skills": ["list", "of", "specific", "matching", "skills"],
    "missing_skills": ["list", "of", "critical", "missing", "skills"],
    "experience_level": "junior or mid or senior",
    "match_percentage": {baseline_score}
}}

IMPORTANT: The match_percentage should be close to {baseline_score}% unless there are strong specific reasons to adjust it.

Analyze now and return ONLY the JSON:"""

    last_error = None
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Analysis attempt {attempt + 1}/{max_retries} for resume hash {resume_hash}")
            
            response = analyzer.run(prompt)
            
            msg = None
            for m in response.messages:
                if m.role == 'assistant' and m.content:
                    msg = m.content
                    break
            
            if not msg:
                raise ValueError("No response content from AI")
            
            result = extract_json_from_response(msg)
            
            if not validate_analysis_result(result):
                raise ValueError("Invalid result structure")
            
            if "match_percentage" not in result:
                result["match_percentage"] = baseline_score
            else:
                result["match_percentage"] = max(0, min(100, int(result["match_percentage"])))
            
            if result["match_percentage"] >= 70:
                result["selected"] = True
            else:
                result["selected"] = False
            
            logger.info(f"Analysis successful: {result['candidate_name']} - {'Selected' if result['selected'] else 'Rejected'} ({result['match_percentage']}%)")
            
            return result["selected"], result["feedback"], result
            
        except Exception as e:
            last_error = e
            logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
            
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2
                logger.info(f"Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
    
    error_msg = f"{get_text('error_processing')}: {str(last_error)}"
    logger.error(f"All analysis attempts failed: {last_error}")
    return False, error_msg, {}

def process_single_candidate(resume_file, role: str) -> dict:
    """Process a single resume with enhanced error handling and OCR support."""
    result = {
        'filename': resume_file.name,
        'role': role,
        'status': 'pending',
        'selected': False,
        'feedback': '',
        'error': None,
        'candidate_name': 'N/A',
        'candidate_phone': 'N/A',
        'match_percentage': 0,
        'ocr_used': False,
    }
    
    try:
        if st.session_state.get('enable_ocr', False):
            text, ocr_used = extract_text_with_ocr(resume_file)
            result['ocr_used'] = ocr_used
        else:
            text = extract_text_from_pdf(resume_file)
            result['ocr_used'] = False
        
        if not text or len(text.strip()) < 50:
            result['error'] = get_text('error_pdf_text')
            result['status'] = 'error'
            return result
        
        analyzer = create_resume_analyzer()
        if not analyzer:
            result['error'] = get_text('error_api_key')
            result['status'] = 'error'
            return result
        
        selected, feedback, details = analyze_resume(text, role, analyzer)
        
        result.update({
            'selected': selected,
            'feedback': feedback,
            'status': 'selected' if selected else 'rejected',
            'candidate_name': details.get('candidate_name', 'N/A'),
            'candidate_phone': details.get('candidate_phone', 'N/A'),
            'match_percentage': details.get('match_percentage', 0),
        })
        
        if 'matching_skills' in details:
            result['matching_skills'] = details['matching_skills']
        if 'missing_skills' in details:
            result['missing_skills'] = details['missing_skills']
        if 'experience_level' in details:
            result['experience_level'] = details['experience_level']
        
        if result['feedback'].startswith(get_text('error_processing')):
            result['status'] = 'error'
            result['error'] = result['feedback']
        else:
            save_to_memory(result)
            
    except Exception as e:
        logger.error(f"Fatal error processing {resume_file.name}: {e}")
        result['error'] = f"Fatal Error: {str(e)}"
        result['status'] = 'error'
        
    return result

def clear_batch_resumes():
    """Clear uploaded resumes and save to disk."""
    st.session_state['batch_results'] = []
    st.session_state['uploader_key'] = str(uuid.uuid4())
    save_results_to_disk()

def set_language():
    """Set language from selector."""
    selected = st.session_state['lang_selector']
    st.session_state['language'] = 'id' if selected == 'Indonesia' else 'en'

def load_logo_icon(logo_path: str = None) -> str:
    """Load company logo or return emoji."""
    if logo_path and os.path.exists(logo_path):
        return logo_path
    return "🤖"

def display_logo_in_sidebar(logo_path: str = None):
    """Display logo in sidebar with 3D effect."""
    if logo_path and os.path.exists(logo_path):
        st.sidebar.markdown("""
            <style>
            section[data-testid="stSidebar"] img {
                border-radius: 15px;
                padding: 15px;
                background: linear-gradient(145deg, #c9e4ea, #a8d5dd);
                box-shadow: 
                    8px 8px 16px rgba(0, 0, 0, 0.3),
                    -8px -8px 16px rgba(255, 255, 255, 0.7),
                    inset 2px 2px 4px rgba(255, 255, 255, 0.3),
                    inset -2px -2px 4px rgba(0, 0, 0, 0.1);
                transition: all 0.3s ease;
                transform: perspective(1000px) rotateX(0deg) rotateY(0deg);
            }
            
            section[data-testid="stSidebar"] img:hover {
                box-shadow: 
                    12px 12px 24px rgba(0, 0, 0, 0.4),
                    -12px -12px 24px rgba(255, 255, 255, 0.8),
                    inset 3px 3px 6px rgba(255, 255, 255, 0.4),
                    inset -3px -3px 6px rgba(0, 0, 0, 0.15);
                transform: perspective(1000px) rotateX(5deg) rotateY(5deg) translateY(-5px);
            }
            </style>
        """, unsafe_allow_html=True)
        st.sidebar.image(logo_path, use_container_width=True)
    else:
        st.sidebar.markdown("""
            <style>
            section[data-testid="stSidebar"] h3 {
                background: linear-gradient(145deg, #c9e4ea, #a8d5dd);
                padding: 20px;
                border-radius: 15px;
                text-align: center;
                box-shadow: 
                    8px 8px 16px rgba(0, 0, 0, 0.3),
                    -8px -8px 16px rgba(255, 255, 255, 0.7),
                    inset 2px 2px 4px rgba(255, 255, 255, 0.3);
                text-shadow: 
                    2px 2px 4px rgba(0, 0, 0, 0.2),
                    -1px -1px 2px rgba(255, 255, 255, 0.5);
                transition: all 0.3s ease;
            }
            
            section[data-testid="stSidebar"] h3:hover {
                box-shadow: 
                    12px 12px 24px rgba(0, 0, 0, 0.4),
                    -12px -12px 24px rgba(255, 255, 255, 0.8);
                transform: translateY(-3px);
            }
            </style>
        """, unsafe_allow_html=True)
        st.sidebar.markdown("### 🤖 PT SMK")

def display_logo_in_header(logo_path: str = None, title: str = ""):
    """Display logo in header."""
    if logo_path and os.path.exists(logo_path):
        col1, col2 = st.columns([1, 5])
        with col1:
            st.image(logo_path, width=100)
        with col2:
            st.title(title)
    else:
        st.title(title)

def to_excel(df: pd.DataFrame) -> bytes:
    """Convert DataFrame to Excel."""
    if not PANDAS_AVAILABLE:
        raise ImportError("Pandas required")
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Hasil Rekrutmen', index=False)
    return output.getvalue()


# --- TAMPILAN HASIL ---
def display_results_table(results: List[Dict], lang: str):
    """Display results table with enhanced visualization and sorting."""
    if not PANDAS_AVAILABLE:
        st.error("Pandas required")
        return

    df = pd.DataFrame(results)
    if df.empty:
        st.info(get_text('no_candidates_found'))
        return

    if 'match_percentage' in df.columns:
        df = df.sort_values('match_percentage', ascending=False)
        st.info(get_text('sorted_by_match'))

    st.subheader(get_text('summary_header'))
    col1, col2, col3, col4 = st.columns(4)
    selected = sum(1 for r in results if r['status'] == 'selected')
    rejected = sum(1 for r in results if r['status'] == 'rejected')
    errors = sum(1 for r in results if r['status'] == 'error')
    
    col1.metric(get_text('total_processed'), len(results))
    col2.metric(get_text('selected_label'), selected)
    col3.metric(get_text('rejected_label'), rejected)
    col4.metric(get_text('errors_label'), errors)

    st.markdown("---")

    status_map = {
        'selected': 'DIREKOMENDASIKAN ✅',
        'rejected': 'TIDAK DIREKOMENDASIKAN ❌',
        'error': 'ERROR ⚠️'
    } if lang == 'id' else {
        'selected': 'RECOMMENDED ✅',
        'rejected': 'NOT RECOMMENDED ❌',
        'error': 'ERROR ⚠️'
    }
    
    df['Tampilan Status'] = df['status'].map(status_map)
    df['Ringkasan'] = df['feedback'].apply(lambda x: (x[:100] + '...') if isinstance(x, str) and len(x) > 100 else x)
    
    df_download = df.copy()
    df_download.insert(0, get_text('table_col_no'), range(1, len(df_download) + 1))
    df_download = df_download.rename(columns={
        'filename': get_text('table_col_filename'),
        'candidate_name': get_text('table_col_candidate_name'),
        'candidate_phone': get_text('table_col_candidate_phone'),
        'role': get_text('table_col_role'),
        'Tampilan Status': get_text('table_col_status'),
        'Ringkasan': get_text('table_col_feedback_short'),
        'feedback': 'Detail Feedback',
        'error': get_text('table_col_error'),
        'match_percentage': get_text('table_col_match')
    })
    
    df_display = df.copy().reset_index(drop=True)
    df_display.insert(0, 'No.', range(1, len(df_display) + 1))
    
    if 'match_percentage' in df_display.columns:
        df_display['Match %'] = df_display['match_percentage'].apply(
            lambda x: f"{int(x)}%" if pd.notna(x) else "N/A"
        )
    
    if 'ocr_used' in df_display.columns:
        df_display['OCR'] = df_display['ocr_used'].apply(lambda x: "🔍" if x else "")
    
    st.markdown(get_text('detail_results_header'))
    
    display_cols = ['No.', 'filename', 'candidate_name', 'candidate_phone', 'Tampilan Status', 'role']
    if 'Match %' in df_display.columns:
        display_cols.append('Match %')
    if 'OCR' in df_display.columns:
        display_cols.append('OCR')
    display_cols.append('Ringkasan')
    
    st.dataframe(
        df_display[display_cols].rename(columns={
            'No.': get_text('table_col_no'),
            'filename': get_text('table_col_filename'),
            'candidate_name': get_text('table_col_candidate_name'),
            'candidate_phone': get_text('table_col_candidate_phone'),
            'Tampilan Status': get_text('table_col_status'),
            'role': get_text('table_col_role'),
            'Ringkasan': get_text('table_col_feedback_short'),
        }),
        use_container_width=True,
        hide_index=True,
        height=400
    )
    
    st.markdown("---")
    col_space, col_download = st.columns([3, 1])
    with col_download:
        st.download_button(
            label=get_text('download_excel_button'),
            data=to_excel(df_download),
            file_name=f"rekrutmen_{time.strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True
        )

    st.markdown(get_text('detail_feedback_header'))
    for _, row in df.iterrows():
        icon = "✅" if row['status'] == 'selected' else ("❌" if row['status'] == 'rejected' else "⚠️")
        match_info = f" | Match: {int(row.get('match_percentage', 0))}%" if 'match_percentage' in row and pd.notna(row['match_percentage']) else ""
        ocr_indicator = " 🔍" if row.get('ocr_used', False) else ""
        
        with st.expander(f"{icon} {row['filename']} | {row['candidate_name']} | {row['Tampilan Status']}{match_info}{ocr_indicator}", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**{get_text('table_col_filename')}:** {row['filename']}")
                st.markdown(f"**{get_text('table_col_candidate_name')}:** {row['candidate_name']}")
                st.markdown(f"**{get_text('table_col_candidate_phone')}:** {row['candidate_phone']}")
            with col2:
                st.markdown(f"**{get_text('role_label')}** {row['role'].replace('_', ' ').title()}")
                st.markdown(f"**{get_text('status_label')}** {row['Tampilan Status']}")
                if 'match_percentage' in row and pd.notna(row['match_percentage']):
                    st.markdown(f"**Match Percentage:** {int(row['match_percentage'])}%")
                if row.get('ocr_used', False):
                    st.markdown("**🔍 OCR:** Used for text extraction")
            
            st.markdown("---")
            
            if 'matching_skills' in row and row['matching_skills']:
                st.markdown("**✅ Matching Skills:**")
                st.write(", ".join(row['matching_skills']))
            
            if 'missing_skills' in row and row['missing_skills']:
                st.markdown("**❌ Missing Skills:**")
                st.write(", ".join(row['missing_skills']))
            
            if 'experience_level' in row and row['experience_level']:
                st.markdown(f"**📊 Experience Level:** {row['experience_level'].title()}")
            
            st.markdown("---")
            
            if row['error']:
                st.error(f"**{get_text('error_label')}** {row['error']}")
            else:
                st.markdown(f"**{get_text('feedback_label')}**")
                st.markdown(row['feedback'])


# --- CHATBOT INTERFACE ---
def display_chatbot_interface():
    """Display chatbot interface for recruitment assistance."""
    st.header(get_text('chatbot_header'))
    
    if not st.session_state.batch_results:
        st.warning(get_text('no_results_for_chat'))
        st.info(get_text('no_results_yet'))
        return
    
    st.markdown(get_text('chatbot_help'))
    st.markdown("---")
    
    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button(get_text('clear_chat'), type="secondary", use_container_width=True):
            st.session_state.chat_history = []
            save_chat_history_to_disk()
            st.success(get_text('chat_cleared'))
            st.rerun()
    
    # Container untuk chat messages - memastikan scrollable
    chat_container = st.container()
    with chat_container:
        for message in st.session_state.chat_history:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    
    # Chat input akan selalu berada di bawah
    if prompt := st.chat_input(get_text('chatbot_placeholder')):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        save_chat_history_to_disk()
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    chatbot = create_chatbot_agent()
                    if not chatbot:
                        st.error(get_text('error_api_key'))
                        return
                    
                    current_results = get_current_results_context()
                    memory_context = get_memory_context()
                    
                    system_context = f"""You are a helpful recruitment assistant. You have access to candidate analysis data.

{current_results}

{memory_context}

User question: {prompt}

Please provide a helpful, actionable response based on the data available. If the user asks about specific candidates, reference their names and details. Be concise but informative."""
                    
                    response = chatbot.run(system_context)
                    
                    response_text = ""
                    for msg in response.messages:
                        if msg.role == 'assistant' and msg.content:
                            response_text = msg.content
                            break
                    
                    if not response_text:
                        response_text = "I apologize, but I couldn't generate a response. Please try again."
                    
                    st.markdown(response_text)
                    
                    st.session_state.chat_history.append({"role": "assistant", "content": response_text})
                    save_chat_history_to_disk()
                    
                except Exception as e:
                    error_msg = f"Error: {str(e)}"
                    st.error(error_msg)
                    st.session_state.chat_history.append({"role": "assistant", "content": error_msg})
                    save_chat_history_to_disk()


# --- TAB ROLE MANAGEMENT ---
def display_role_management():
    """Display role management interface."""
    st.header(get_text('tab_manage_roles'))
    
    roles = load_roles()
    
    st.markdown("---")
    
    tab1, tab2 = st.tabs([get_text('add_role_header'), get_text('edit_role_header')])
    
    with tab1:
        with st.form("add_role_form_unique"):
            role_id = st.text_input(
                get_text('role_id_label'),
                help=get_text('role_id_help'),
                placeholder="e.g., senior_developer"
            )
            requirements = st.text_area(
                get_text('required_skills_label'),
                height=200,
                help=get_text('required_skills_help'),
                placeholder="Required Skills:\n- Skill 1\n- Skill 2\n..."
            )
            
            submitted = st.form_submit_button(get_text('add_role_button'), type="primary", use_container_width=True)
            
            if submitted:
                if not role_id or not requirements:
                    st.error("All fields required")
                elif not is_valid_role_id(role_id):
                    st.error(get_text('role_id_invalid'))
                elif role_id in roles:
                    st.error(get_text('role_exists_error'))
                else:
                    save_role(role_id, requirements)
                    st.success(get_text('role_added_success'))
                    st.toast(get_text('role_added_success'), icon="✅")
                    time.sleep(1)
                    st.rerun()
    
    with tab2:
        if not roles:
            st.info(get_text('no_roles_available'))
        else:
            selected_role = st.selectbox(
                get_text('select_role_to_edit'),
                options=list(roles.keys()),
                format_func=lambda x: x.replace('_', ' ').title()
            )
            
            if selected_role:
                with st.form("edit_role_form_unique"):
                    st.info(f"Editing: **{selected_role}**")
                    
                    new_requirements = st.text_area(
                        get_text('required_skills_label'),
                        value=roles[selected_role],
                        height=200,
                        help=get_text('required_skills_help')
                    )
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        update_btn = st.form_submit_button(
                            get_text('update_role_button'),
                            type="primary",
                            use_container_width=True
                        )
                    with col2:
                        delete_btn = st.form_submit_button(
                            get_text('delete_role_button'),
                            type="secondary",
                            use_container_width=True
                        )
                    
                    if update_btn:
                        if new_requirements:
                            save_role(selected_role, new_requirements)
                            st.success(get_text('role_updated_success'))
                            st.toast(f"✅ {selected_role.replace('_', ' ').title()} " + get_text('role_updated_success'), icon="✏️")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Requirements cannot be empty")
                    
                    if delete_btn:
                        if len(roles) > 1:
                            delete_role(selected_role)
                            st.success(get_text('role_deleted_success'))
                            st.toast(f"🗑️ {selected_role.replace('_', ' ').title()} " + get_text('role_deleted_success'), icon="✅")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Cannot delete the last role")


# --- FUNGSI UTAMA ---
def main() -> None:
    COMPANY_LOGO = "logo.png"
    
    st.set_page_config(
        page_title="PT SMK - AI Recruitment System",
        page_icon=load_logo_icon(COMPANY_LOGO),
        layout="wide"
    )
    
    init_session_state()
    set_futuristic_robotic_theme()
    
    if st.session_state.get('data_loaded', False) and 'notification_shown' not in st.session_state:
        st.session_state.notification_shown = True
        total_items = (
            len(st.session_state.role_requirements) +
            len(st.session_state.analysis_memory) +
            len(st.session_state.batch_results) +
            len(st.session_state.chat_history)
        )
        if total_items > 0:
            st.toast(f"✅ {get_text('data_loaded')} ({total_items} items)", icon="💾")
    
    display_logo_in_header(COMPANY_LOGO, get_text('app_title'))
    
    # Sidebar
    with st.sidebar:
        # === EXPANDER 1: Pilih Bahasa ===
        with st.expander("🌐 " + get_text('language_select'), expanded=False):
            st.selectbox(
                get_text('language_select'),
                options=['Indonesia', 'English'],
                key='lang_selector',
                on_change=set_language,
                index=0 if st.session_state.language == 'id' else 1,
                label_visibility="collapsed"
            )
        
        st.markdown("")  # Spacing
        
        # === EXPANDER 2: Pengaturan OpenAI ===
        with st.expander("⚙️ " + get_text('openai_settings'), expanded=True):
            api_key = st.text_input(
                get_text('api_key_label'),
                type="password",
                value=st.session_state.openai_api_key,
                help=get_text('api_key_help')
            )
            if api_key:
                st.session_state.openai_api_key = api_key
        
        st.markdown("")  # Spacing
        
        # === EXPANDER 3: Manajemen Data ===
        with st.expander("💾 " + get_text('data_management'), expanded=False):
            total_roles = len(st.session_state.get('role_requirements', {}))
            total_memory = len(st.session_state.get('analysis_memory', []))
            total_results = len(st.session_state.get('batch_results', []))
            total_chats = len(st.session_state.get('chat_history', []))
            
            st.info(f"""💾 **{get_text('storage_info')}**
            
- 📋 Posisi: {total_roles}
- 🧠 Memory: {total_memory}
- 📊 Hasil: {total_results}
- 💬 Chat: {total_chats}
            """)
            
            if st.button(get_text('export_all_data'), use_container_width=True, key='sidebar_export_btn'):
                backup_data = export_all_data()
                st.download_button(
                    label="⬇️ Download Backup",
                    data=backup_data,
                    file_name=f"recruitment_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    use_container_width=True,
                    key='sidebar_download_btn'
                )
                st.success(get_text('backup_success'))
            
            uploaded_backup = st.file_uploader(
                get_text('import_all_data'),
                type=['json'],
                key='backup_uploader'
            )
            if uploaded_backup:
                try:
                    backup_str = uploaded_backup.read().decode('utf-8')
                    if import_all_data(backup_str):
                        st.success(get_text('restore_success'))
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Failed to restore data")
                except Exception as e:
                    st.error(f"Error: {e}")
            
            st.markdown("")  # Internal spacing
            
            # Initialize confirm state
            if 'confirm_clear' not in st.session_state:
                st.session_state.confirm_clear = False
            
            if not st.session_state.confirm_clear:
                if st.button(get_text('clear_all_data'), type="secondary", use_container_width=True, key='sidebar_clear_btn'):
                    st.session_state.confirm_clear = True
                    st.rerun()
            else:
                st.warning(get_text('confirm_clear_data'))
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("⚠️ Ya, Hapus", type="primary", use_container_width=True, key="sidebar_confirm_yes"):
                        if clear_all_data():
                            for key in ['role_requirements', 'analysis_memory', 'batch_results', 'chat_history']:
                                if key == 'role_requirements':
                                    st.session_state[key] = DEFAULT_ROLE_REQUIREMENTS.copy()
                                else:
                                    st.session_state[key] = []
                            st.session_state.confirm_clear = False
                            st.success(get_text('all_data_cleared'))
                            time.sleep(1)
                            st.rerun()
                with col_b:
                    if st.button("❌ Batal", type="secondary", use_container_width=True, key="sidebar_confirm_no"):
                        st.session_state.confirm_clear = False
                        st.rerun()
        
        st.markdown("")  # Spacing
        
        # === EXPANDER 4: Pengaturan OCR ===
        if OCR_AVAILABLE:
            with st.expander("🔍 " + get_text('ocr_settings'), expanded=False):
                enable_ocr = st.checkbox(
                    get_text('enable_ocr'),
                    value=st.session_state.get('enable_ocr', True),
                    help=get_text('ocr_help')
                )
                st.session_state.enable_ocr = enable_ocr
        else:
            with st.expander("🔍 " + get_text('ocr_settings'), expanded=False):
                st.warning("OCR tidak tersedia. Install: pdf2image, pytesseract, pillow")
        
        st.markdown("")  # Spacing
        
    if not st.session_state.openai_api_key:
        st.error(f"{get_text('warning_missing_config')}{get_text('api_key_label')}")
        st.info("👉 " + get_text('api_key_help'))
        st.stop()
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        get_text('tab_upload'),
        get_text('tab_download_excel'),
        get_text('tab_results'),
        get_text('tab_chatbot'),
        get_text('tab_manage_roles')
    ])
    
    # TAB 1: Upload & Process
    with tab1:
        st.header(get_text('select_role'))
        
        roles = load_roles()
        if not roles:
            st.warning(get_text('no_roles_available'))
            st.info(f"👉 {get_text('tab_manage_roles')}")
        else:
            role_options = list(roles.keys())
            role = st.selectbox(
                " ",
                role_options,
                format_func=lambda x: x.replace('_', ' ').title(),
                label_visibility="collapsed",
                key='app_selected_role'
            )
            
            with st.expander(get_text('view_skills_expander'), expanded=False):
                st.markdown(roles[role])
            
            st.markdown("---")
            
            if st.session_state.get('enable_ocr', False):
                st.info("🔍 OCR Enabled - Image-based PDFs will be scanned automatically")
            
            st.info(get_text('batch_info'))
            
            col_upload, col_clear = st.columns([4, 1])
            
            with col_upload:
                resume_files = st.file_uploader(
                    get_text('upload_resume_label'),
                    type=["pdf"],
                    accept_multiple_files=True,
                    key=st.session_state.uploader_key
                )
            
            with col_clear:
                st.write("")
                st.write("")
                if st.button(
                    get_text('clear_resumes_button'),
                    help=get_text('clear_resumes_help'),
                    type="secondary",
                    use_container_width=True
                ):
                    clear_batch_resumes()
                    st.rerun()

            if resume_files and len(resume_files) > 0:
                num_files = len(resume_files)
                st.success(f"📁 **{num_files}** {get_text('resumes_uploaded')}")
                
                st.markdown("---")
                
                if st.button(get_text('process_all_button'), type='primary', use_container_width=True):
                    results = []
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    for i, resume_file in enumerate(resume_files):
                        filename = resume_file.name
                        progress = i / len(resume_files)
                        progress_bar.progress(progress)
                        
                        if st.session_state.get('enable_ocr', False):
                            status_text.text(f"⏳ {get_text('processing_status')} {i+1}/{len(resume_files)}: {filename} {get_text('ocr_processing')}")
                        else:
                            status_text.text(f"⏳ {get_text('processing_status')} {i+1}/{len(resume_files)}: {filename}")
                        
                        result = process_single_candidate(resume_file, role)
                        results.append(result)
                        
                        status_map = {
                            'selected': 'DIREKOMENDASIKAN',
                            'rejected': 'TIDAK DIREKOMENDASIKAN',
                            'error': 'ERROR'
                        } if st.session_state.language == 'id' else {
                            'selected': 'RECOMMENDED',
                            'rejected': 'NOT RECOMMENDED',
                            'error': 'ERROR'
                        }
                        status_display = status_map.get(result['status'], 'UNKNOWN')
                        icon = "✅" if result['status'] == 'selected' else ("❌" if result['status'] == 'rejected' else "⚠️")
                        
                        match_info = f" ({int(result.get('match_percentage', 0))}%)" if result.get('match_percentage') else ""
                        ocr_indicator = " 🔍" if result.get('ocr_used', False) else ""
                        st.write(f"{icon} {filename}: {result['candidate_name']} ({status_display}){match_info}{ocr_indicator}")
                    
                    progress_bar.progress(1.0)
                    status_text.text(get_text('processing_complete'))
                    
                    results.sort(key=lambda x: x.get('match_percentage', 0), reverse=True)
                    
                    st.session_state.batch_results = results
                    save_results_to_disk()
                    
                    st.success(get_text('processing_complete'))
                    
                    selected_count = sum(1 for r in results if r['status'] == 'selected')
                    rejected_count = sum(1 for r in results if r['status'] == 'rejected')
                    ocr_count = sum(1 for r in results if r.get('ocr_used', False))
                    
                    summary = f"🎉 {get_text('processing_complete')}\n📊 Total: {len(results)} | ✅ {selected_count} | ❌ {rejected_count}"
                    if ocr_count > 0:
                        summary += f" | 🔍 OCR: {ocr_count}"
                    st.toast(summary, icon="✅")
                    
                    st.info(f"👉 {get_text('tab_results')} atau {get_text('tab_chatbot')}")
    
    # TAB 2: Download from Excel
    with tab2:
        st.header(get_text('tab_download_excel'))
        
        st.info(get_text('excel_format_info'))
        
        # Warning khusus untuk Google Drive
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
        
        st.markdown("")  # Spacing
        
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
