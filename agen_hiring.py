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


# --- TEMA NATURE - KONFIGURASI WARNA ---
def apply_nature_theme():
    """
    Menerapkan tema nature dengan palet warna hijau alami dan kontras yang baik
    Terinspirasi dari alam: hutan, daun, tanah, dan langit
    """
    st.markdown("""
    <style>
    /* ===== THEME NATURE - COLOR PALETTE ===== */
    :root {
        --nature-primary: #2d5016;        /* Forest Green - Hijau Hutan Gelap */
        --nature-secondary: #4a7c2c;      /* Moss Green - Hijau Lumut */
        --nature-accent: #6b9d3a;         /* Leaf Green - Hijau Daun */
        --nature-light: #a8d08d;          /* Light Green - Hijau Muda */
        --nature-bg: #f5f9f0;             /* Cream White - Putih Krem */
        --nature-card: #ffffff;           /* Pure White */
        --nature-earth: #8b7355;          /* Earth Brown - Coklat Tanah */
        --nature-sky: #87ceeb;            /* Sky Blue - Biru Langit */
        --nature-warning: #ff8c42;        /* Sunset Orange */
        --nature-error: #c44536;          /* Red Clay */
        --nature-success: #4a7c2c;        /* Success Green */
    }
    
    /* ===== BACKGROUND UTAMA ===== */
    .stApp {
        background: linear-gradient(135deg, #f5f9f0 0%, #e8f5e0 100%);
    }
    
    /* ===== SIDEBAR ===== */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #2d5016 0%, #1a3010 100%);
        border-right: 3px solid var(--nature-accent);
    }
    
    /* Default text di sidebar - PUTIH karena bg gelap */
    [data-testid="stSidebar"] {
        color: #ffffff !important;
    }
    
    /* Sidebar headings - PUTIH TERANG untuk visibility pada bg gelap */
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] h4,
    [data-testid="stSidebar"] .stMarkdown h1,
    [data-testid="stSidebar"] .stMarkdown h2,
    [data-testid="stSidebar"] .stMarkdown h3,
    [data-testid="stSidebar"] .stMarkdown h4 {
        color: #ffffff !important;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        font-weight: 700 !important;
    }
    
    /* Paragraf di sidebar - putih */
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span:not(input span):not(select span),
    [data-testid="stSidebar"] div:not([data-baseweb]) {
        color: #ffffff !important;
    }
    
    /* Label di sidebar - PUTIH dan BOLD */
    [data-testid="stSidebar"] label {
        color: #ffffff !important;
        font-weight: 600 !important;
    }
    
    /* EXCEPTION: Elemen dengan background terang di sidebar */
    /* Input fields - text GELAP karena bg putih */
    [data-testid="stSidebar"] input[type="text"],
    [data-testid="stSidebar"] input[type="password"],
    [data-testid="stSidebar"] input[type="number"],
    [data-testid="stSidebar"] textarea {
        color: #1a3010 !important;
        background-color: #ffffff !important;
    }
    
    /* Select dropdown di sidebar - text gelap */
    [data-testid="stSidebar"] [data-baseweb="select"] {
        background-color: #ffffff !important;
    }
    
    [data-testid="stSidebar"] [data-baseweb="select"] span,
    [data-testid="stSidebar"] [data-baseweb="select"] div {
        color: #1a3010 !important;
    }
    
    /* Alert boxes di sidebar - sesuaikan warna text */
    [data-testid="stSidebar"] .stAlert p,
    [data-testid="stSidebar"] .stAlert span,
    [data-testid="stSidebar"] .stAlert div {
        color: inherit !important;
    }
    
    /* Expander di sidebar */
    [data-testid="stSidebar"] [data-testid="stExpander"] summary {
        color: #ffffff !important;
    }
    
    [data-testid="stSidebar"] [data-testid="stExpander"] p,
    [data-testid="stSidebar"] [data-testid="stExpander"] span {
        color: #ffffff !important;
    }
    
    /* Button di sidebar - keep white text */
    [data-testid="stSidebar"] button {
        color: #ffffff !important;
    }
    
    /* ===== HEADER & JUDUL ===== */
    /* Semua heading HARUS gelap untuk kontras tinggi pada bg terang */
    h1, h2, h3, h4, h5, h6 {
        color: var(--nature-primary) !important;
        font-weight: 700;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
    }
    
    h1 {
        border-bottom: 3px solid var(--nature-accent);
        padding-bottom: 10px;
    }
    
    /* Pastikan heading di main content area juga gelap */
    .main h1, .main h2, .main h3 {
        color: var(--nature-primary) !important;
    }
    
    /* Subheadings dan captions juga gelap */
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3,
    .stMarkdown h4, .stMarkdown h5, .stMarkdown h6 {
        color: var(--nature-primary) !important;
    }
    
    /* Caption dan helper text */
    .stCaption, [data-testid="stCaptionContainer"] {
        color: var(--nature-secondary) !important;
    }
    
    /* ===== TABS ===== */
    .stTabs [data-baseweb="tab-list"] {
        background-color: var(--nature-card);
        border-radius: 10px 10px 0 0;
        padding: 10px;
        box-shadow: 0 2px 8px rgba(45,80,22,0.1);
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        color: var(--nature-primary);
        font-weight: 600;
        border-radius: 8px 8px 0 0;
        padding: 12px 24px;
        transition: all 0.3s ease;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        background-color: var(--nature-light);
        color: var(--nature-primary);
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, var(--nature-primary) 0%, var(--nature-secondary) 100%);
        color: white !important;
        box-shadow: 0 4px 12px rgba(45,80,22,0.3);
    }
    
    /* ===== CARDS & CONTAINERS ===== */
    .stMarkdown, [data-testid="stVerticalBlock"], [data-testid="column"] {
        background-color: var(--nature-card);
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 12px rgba(45,80,22,0.08);
        margin-bottom: 15px;
    }
    
    /* ===== BUTTONS ===== */
    .stButton > button {
        background: linear-gradient(135deg, var(--nature-secondary) 0%, var(--nature-accent) 100%);
        color: white !important;
        border: none;
        border-radius: 8px;
        padding: 12px 24px;
        font-weight: 600;
        box-shadow: 0 4px 12px rgba(74,124,44,0.3);
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        background: linear-gradient(135deg, var(--nature-accent) 0%, var(--nature-light) 100%);
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(74,124,44,0.4);
    }
    
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, var(--nature-primary) 0%, var(--nature-secondary) 100%);
    }
    
    .stButton > button[kind="secondary"] {
        background: transparent;
        border: 2px solid var(--nature-accent);
        color: var(--nature-primary) !important;
    }
    
    /* ===== INPUT FIELDS ===== */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div {
        background-color: white;
        border: 2px solid var(--nature-light);
        border-radius: 8px;
        color: var(--nature-primary);
        padding: 10px;
        transition: all 0.3s ease;
    }
    
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: var(--nature-accent);
        box-shadow: 0 0 0 3px rgba(107,157,58,0.1);
    }
    
    /* ===== LABELS ===== */
    .stTextInput > label,
    .stTextArea > label,
    .stSelectbox > label,
    .stFileUploader > label {
        color: var(--nature-primary) !important;
        font-weight: 600;
        font-size: 16px;
    }
    
    /* ===== INFO BOXES ===== */
    .stAlert {
        border-radius: 10px;
        border-left: 5px solid;
        background-color: white;
    }
    
    [data-baseweb="notification"][kind="info"] {
        background-color: #e3f2fd;
        border-left-color: var(--nature-sky);
        color: #0d47a1;
    }
    
    [data-baseweb="notification"][kind="success"] {
        background-color: #e8f5e9;
        border-left-color: var(--nature-success);
        color: var(--nature-primary);
    }
    
    [data-baseweb="notification"][kind="warning"] {
        background-color: #fff3e0;
        border-left-color: var(--nature-warning);
        color: #e65100;
    }
    
    [data-baseweb="notification"][kind="error"] {
        background-color: #ffebee;
        border-left-color: var(--nature-error);
        color: #b71c1c;
    }
    
    /* ===== FILE UPLOADER ===== */
    [data-testid="stFileUploader"] {
        background-color: var(--nature-bg);
        border: 2px dashed var(--nature-accent);
        border-radius: 10px;
        padding: 20px;
    }
    
    /* ===== DATAFRAME / TABLE ===== */
    .stDataFrame {
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 4px 12px rgba(45,80,22,0.1);
    }
    
    .stDataFrame th {
        background: linear-gradient(135deg, var(--nature-primary) 0%, var(--nature-secondary) 100%) !important;
        color: white !important;
        font-weight: 700;
        padding: 15px !important;
    }
    
    .stDataFrame td {
        background-color: white !important;
        color: var(--nature-primary) !important;
        padding: 12px !important;
    }
    
    .stDataFrame tr:hover td {
        background-color: var(--nature-bg) !important;
    }
    
    /* ===== EXPANDER ===== */
    [data-testid="stExpander"] {
        background-color: white;
        border: 2px solid var(--nature-light);
        border-radius: 10px;
        overflow: hidden;
    }
    
    [data-testid="stExpander"] summary {
        background: linear-gradient(135deg, var(--nature-light) 0%, #c8e6c0 100%);
        color: var(--nature-primary);
        font-weight: 600;
        padding: 15px;
    }
    
    [data-testid="stExpander"] summary:hover {
        background: linear-gradient(135deg, var(--nature-accent) 0%, var(--nature-light) 100%);
    }
    
    /* ===== PROGRESS BAR ===== */
    .stProgress > div > div > div {
        background: linear-gradient(90deg, var(--nature-accent) 0%, var(--nature-light) 100%);
    }
    
    /* ===== SPINNER ===== */
    .stSpinner > div {
        border-top-color: var(--nature-accent) !important;
    }
    
    /* ===== METRIC CARDS ===== */
    [data-testid="stMetricValue"] {
        color: var(--nature-primary);
        font-size: 32px;
        font-weight: 700;
    }
    
    [data-testid="stMetricLabel"] {
        color: var(--nature-secondary);
        font-weight: 600;
    }
    
    /* ===== CUSTOM BADGES ===== */
    .nature-badge {
        display: inline-block;
        padding: 6px 12px;
        border-radius: 20px;
        font-size: 14px;
        font-weight: 600;
        margin: 4px;
    }
    
    .badge-success {
        background-color: #e8f5e9;
        color: var(--nature-success);
        border: 2px solid var(--nature-success);
    }
    
    .badge-warning {
        background-color: #fff3e0;
        color: #e65100;
        border: 2px solid var(--nature-warning);
    }
    
    .badge-error {
        background-color: #ffebee;
        color: var(--nature-error);
        border: 2px solid var(--nature-error);
    }
    
    .badge-info {
        background-color: #e3f2fd;
        color: #0d47a1;
        border: 2px solid var(--nature-sky);
    }
    
    /* ===== SCROLLBAR ===== */
    ::-webkit-scrollbar {
        width: 12px;
        height: 12px;
    }
    
    ::-webkit-scrollbar-track {
        background: var(--nature-bg);
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(135deg, var(--nature-secondary) 0%, var(--nature-accent) 100%);
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: linear-gradient(135deg, var(--nature-primary) 0%, var(--nature-secondary) 100%);
    }
    
    /* ===== DECORATIVE ELEMENTS ===== */
    .nature-divider {
        height: 3px;
        background: linear-gradient(90deg, transparent 0%, var(--nature-accent) 50%, transparent 100%);
        margin: 20px 0;
        border-radius: 2px;
    }
    
    /* ===== TOOLTIPS ===== */
    [data-testid="stTooltipHoverTarget"] {
        color: var(--nature-accent);
    }
    
    /* ===== SELECTBOX DROPDOWN ===== */
    [data-baseweb="popover"] {
        background-color: white;
        border: 2px solid var(--nature-light);
        border-radius: 10px;
        box-shadow: 0 8px 24px rgba(45,80,22,0.15);
    }
    
    [data-baseweb="select"] li:hover {
        background-color: var(--nature-bg);
    }
    
    /* ===== RADIO BUTTONS ===== */
    [data-testid="stRadio"] label {
        color: var(--nature-primary);
        font-weight: 500;
    }
    
    /* ===== CHECKBOX ===== */
    [data-testid="stCheckbox"] label {
        color: var(--nature-primary);
        font-weight: 500;
    }
    
    /* ===== KONTRAS TEKS - READABILITY ===== */
    /* KRITIS: Semua teks pada background terang HARUS menggunakan warna GELAP */
    
    /* Default text - dark untuk kontras maksimal */
    p, span, div, li, td, th {
        color: #1a3010 !important;
    }
    
    /* Heading dengan kontras tinggi - SELALU GELAP */
    h1, h2, h3, h4, h5, h6,
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3,
    .stMarkdown h4, .stMarkdown h5, .stMarkdown h6 {
        color: var(--nature-primary) !important;
    }
    
    /* Main content area text - GELAP */
    .main p, .main span, .main div:not([data-testid="stSidebar"] div) {
        color: #1a3010 !important;
    }
    
    /* Markdown content - GELAP */
    .stMarkdown p, .stMarkdown span, .stMarkdown li {
        color: #1a3010 !important;
    }
    
    /* Link dengan warna yang terlihat jelas tapi tetap kontras tinggi */
    a {
        color: var(--nature-secondary) !important;
        font-weight: 600;
    }
    
    a:hover {
        color: var(--nature-accent) !important;
        text-decoration: underline;
    }
    
    /* Expander content - text GELAP */
    [data-testid="stExpander"] p,
    [data-testid="stExpander"] span,
    [data-testid="stExpander"] div {
        color: #1a3010 !important;
    }
    
    /* Info boxes - text GELAP pada bg terang */
    .stAlert p, .stAlert span, .stAlert div {
        color: inherit !important;
    }
    
    /* Caption dan helper text - medium dark untuk hierarchy */
    .stCaption, [data-testid="stCaptionContainer"],
    [data-testid="stCaptionContainer"] p {
        color: var(--nature-secondary) !important;
    }
    
    /* Label untuk form - GELAP dan BOLD */
    label, .stTextInput > label, .stTextArea > label,
    .stSelectbox > label, .stFileUploader > label,
    .stCheckbox > label, .stRadio > label {
        color: var(--nature-primary) !important;
        font-weight: 600 !important;
    }
    
    /* Select dropdown text - GELAP */
    [data-baseweb="select"] span,
    [data-baseweb="select"] div {
        color: #1a3010 !important;
    }
    
    /* ===== CUSTOM NATURE HEADER ===== */
    .nature-header {
        background: linear-gradient(135deg, var(--nature-primary) 0%, var(--nature-secondary) 50%, var(--nature-accent) 100%);
        color: white;
        padding: 30px;
        border-radius: 15px;
        text-align: center;
        margin-bottom: 30px;
        box-shadow: 0 8px 24px rgba(45,80,22,0.2);
    }
    
    .nature-header h1 {
        color: white !important;
        margin: 0;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }
    
    .nature-header p {
        color: var(--nature-light);
        font-size: 18px;
        margin-top: 10px;
    }
    
    /* ===== RESPONSIVENESS ===== */
    @media (max-width: 768px) {
        .stButton > button {
            width: 100%;
            margin-bottom: 10px;
        }
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
    'app_title': {'id': "🌿 PT Srikandi Mitra Karya - Sistem Rekrutmen AI", 'en': "🌿 PT Srikandi Mitra Karya - AI Recruitment System"},
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
    'tab_manage_roles': {'id': "🌱 Kelola Posisi", 'en': "🌱 Manage Roles"},
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
    'processing_spinner': {'id': "🌿 Memproses aplikasi...", 'en': "🌿 Processing application..."},
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
    'candidate_name': {'id': "Nama Kandidat", 'en': "Candidate Name"},
    'match_percentage': {'id': "Persentase Kecocokan", 'en': "Match Percentage"},
    'status': {'id': "Status", 'en': "Status"},
    'strengths': {'id': "Kekuatan", 'en': "Strengths"},
    'areas_improvement': {'id': "Area Perbaikan", 'en': "Areas for Improvement"},
    'key_skills': {'id': "Keterampilan Kunci", 'en': "Key Skills"},
    'experience_years': {'id': "Tahun Pengalaman", 'en': "Years of Experience"},
    'education': {'id': "Pendidikan", 'en': "Education"},
    'action': {'id': "Aksi", 'en': "Action"},
    'download_button': {'id': "📄 Download", 'en': "📄 Download"},
    'view_details': {'id': "👁️ Lihat Detail", 'en': "👁️ View Details"},
    
    # Download Excel
    'upload_excel_label': {'id': "📊 Unggah File Excel", 'en': "📊 Upload Excel File"},
    'excel_format_info': {'id': "📝 Format Excel harus memiliki kolom: **Nama** atau **Name**, dan **Link CV** atau **CV Link** atau **URL**", 'en': "📝 Excel format must have columns: **Name** or **Nama**, and **CV Link** or **Link CV** or **URL**"},
    'download_all_cv': {'id': "🌿 Download & Proses Semua CV", 'en': "🌿 Download & Process All CVs"},
    'downloading_cv': {'id': "⬇️ Mendownload CV...", 'en': "⬇️ Downloading CVs..."},
    'excel_uploaded': {'id': "File Excel terunggah", 'en': "Excel file uploaded"},
    'invalid_excel_format': {'id': "❌ Format Excel tidak valid. Pastikan ada kolom Nama dan Link CV.", 'en': "❌ Invalid Excel format. Ensure Name and CV Link columns exist."},
    'no_valid_links': {'id': "❌ Tidak ada link CV yang valid di file Excel.", 'en': "❌ No valid CV links found in Excel file."},
    'cv_download_success': {'id': "✅ CV berhasil didownload", 'en': "✅ CV downloaded successfully"},
    'cv_download_error': {'id': "❌ Gagal mendownload CV", 'en': "❌ Failed to download CV"},
    
    # Results
    'no_results_yet': {'id': "Belum ada hasil. Unggah dan proses resume terlebih dahulu.", 'en': "No results yet. Upload and process resumes first."},
    'export_results_csv': {'id': "📥 Export Hasil (CSV)", 'en': "📥 Export Results (CSV)"},
    'export_results_json': {'id': "📥 Export Hasil (JSON)", 'en': "📥 Export Results (JSON)"},
    'export_results_excel': {'id': "📥 Export Hasil (Excel)", 'en': "📥 Export Results (Excel)"},
    'filter_by_status': {'id': "🔍 Filter berdasarkan Status:", 'en': "🔍 Filter by Status:"},
    'filter_all': {'id': "Semua", 'en': "All"},
    'filter_selected': {'id': "Direkomendasikan", 'en': "Recommended"},
    'filter_rejected': {'id': "Tidak direkomendasikan", 'en': "Not Recommended"},
    'filter_error': {'id': "Error", 'en': "Error"},
    'sort_by': {'id': "🔢 Urutkan berdasarkan:", 'en': "🔢 Sort by:"},
    'sort_match_desc': {'id': "Persentase Kecocokan (Tertinggi)", 'en': "Match Percentage (Highest)"},
    'sort_match_asc': {'id': "Persentase Kecocokan (Terendah)", 'en': "Match Percentage (Lowest)"},
    'sort_name': {'id': "Nama (A-Z)", 'en': "Name (A-Z)"},
}


def get_text(key: str) -> str:
    """Ambil teks dalam bahasa yang dipilih"""
    lang = st.session_state.get('language', 'id')
    return TEXTS.get(key, {}).get(lang, key)


# --- 2. INISIALISASI SESSION STATE ---
def initialize_session_state():
    """Inisialisasi semua variabel session state"""
    defaults = {
        'language': 'id',
        'api_key': '',
        'enable_ocr': False,
        'batch_results': [],
        'uploaded_files': [],
        'chat_history': [],
        'analysis_memory': {},
        'roles': {},
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    
    # Load data dari disk
    load_data_from_disk()


# --- 3. PERSISTENT STORAGE FUNCTIONS ---
def save_roles_to_disk():
    """Simpan roles ke file JSON"""
    try:
        with open(ROLES_FILE, 'w', encoding='utf-8') as f:
            json.dump(st.session_state.roles, f, ensure_ascii=False, indent=2)
        logger.info("Roles saved to disk")
    except Exception as e:
        logger.error(f"Error saving roles: {e}")


def load_roles_from_disk():
    """Load roles dari file JSON"""
    try:
        if ROLES_FILE.exists():
            with open(ROLES_FILE, 'r', encoding='utf-8') as f:
                st.session_state.roles = json.load(f)
            logger.info(f"Loaded {len(st.session_state.roles)} roles from disk")
            return True
    except Exception as e:
        logger.error(f"Error loading roles: {e}")
    return False


def save_results_to_disk():
    """Simpan batch results ke file JSON"""
    try:
        # Convert results to JSON-serializable format
        serializable_results = []
        for result in st.session_state.batch_results:
            result_copy = result.copy()
            # Remove or convert non-serializable objects
            if 'pdf_bytes' in result_copy:
                result_copy['pdf_bytes'] = base64.b64encode(result_copy['pdf_bytes']).decode('utf-8')
            serializable_results.append(result_copy)
        
        with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(serializable_results, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(serializable_results)} results to disk")
    except Exception as e:
        logger.error(f"Error saving results: {e}")


def load_results_from_disk():
    """Load batch results dari file JSON"""
    try:
        if RESULTS_FILE.exists():
            with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
                results = json.load(f)
            
            # Convert back PDF bytes from base64
            for result in results:
                if 'pdf_bytes' in result and isinstance(result['pdf_bytes'], str):
                    result['pdf_bytes'] = base64.b64decode(result['pdf_bytes'])
            
            st.session_state.batch_results = results
            logger.info(f"Loaded {len(results)} results from disk")
            return True
    except Exception as e:
        logger.error(f"Error loading results: {e}")
    return False


def save_chat_history_to_disk():
    """Simpan chat history ke file JSON"""
    try:
        with open(CHAT_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(st.session_state.chat_history, f, ensure_ascii=False, indent=2)
        logger.info("Chat history saved to disk")
    except Exception as e:
        logger.error(f"Error saving chat history: {e}")


def load_chat_history_from_disk():
    """Load chat history dari file JSON"""
    try:
        if CHAT_HISTORY_FILE.exists():
            with open(CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                st.session_state.chat_history = json.load(f)
            logger.info(f"Loaded {len(st.session_state.chat_history)} chat messages from disk")
            return True
    except Exception as e:
        logger.error(f"Error loading chat history: {e}")
    return False


def save_memory_to_disk():
    """Simpan analysis memory ke file JSON"""
    try:
        with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(st.session_state.analysis_memory, f, ensure_ascii=False, indent=2)
        logger.info("Analysis memory saved to disk")
    except Exception as e:
        logger.error(f"Error saving memory: {e}")


def load_memory_from_disk():
    """Load analysis memory dari file JSON"""
    try:
        if MEMORY_FILE.exists():
            with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
                st.session_state.analysis_memory = json.load(f)
            logger.info("Analysis memory loaded from disk")
            return True
    except Exception as e:
        logger.error(f"Error loading memory: {e}")
    return False


def load_data_from_disk():
    """Load semua data dari disk"""
    load_roles_from_disk()
    load_results_from_disk()
    load_chat_history_from_disk()
    load_memory_from_disk()


def clear_all_data():
    """Hapus semua data dari memory dan disk"""
    # Clear session state
    st.session_state.batch_results = []
    st.session_state.chat_history = []
    st.session_state.analysis_memory = {}
    st.session_state.roles = {}
    st.session_state.uploaded_files = []
    
    # Delete files
    for file in [ROLES_FILE, RESULTS_FILE, CHAT_HISTORY_FILE, MEMORY_FILE]:
        try:
            if file.exists():
                file.unlink()
                logger.info(f"Deleted {file}")
        except Exception as e:
            logger.error(f"Error deleting {file}: {e}")


# --- 4. ROLE MANAGEMENT FUNCTIONS ---
def load_roles() -> Dict[str, str]:
    """Load roles dari session state"""
    return st.session_state.roles


def save_role(role_id: str, role_description: str):
    """Simpan role baru atau update existing role"""
    st.session_state.roles[role_id] = role_description
    save_roles_to_disk()


def delete_role(role_id: str):
    """Hapus role"""
    if role_id in st.session_state.roles:
        del st.session_state.roles[role_id]
        save_roles_to_disk()


def validate_role_id(role_id: str) -> bool:
    """Validasi role ID (lowercase, underscore, numbers only)"""
    return bool(re.match(r'^[a-z0-9_]+$', role_id))


# --- 5. PDF EXTRACTION dengan OCR FALLBACK ---
def extract_text_from_pdf(pdf_bytes: bytes, use_ocr: bool = False) -> str:
    """
    Ekstrak teks dari PDF dengan fallback ke OCR jika diperlukan
    """
    text = ""
    
    # Try standard extraction first
    try:
        pdf_reader = PyPDF2.PdfReader(BytesIO(pdf_bytes))
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    except Exception as e:
        logger.warning(f"Standard PDF extraction failed: {e}")
    
    # If minimal text extracted and OCR is available, try OCR
    if len(text.strip()) < 100 and use_ocr and OCR_AVAILABLE:
        try:
            logger.info("Attempting OCR extraction...")
            images = convert_from_bytes(pdf_bytes)
            ocr_text = ""
            for image in images:
                ocr_text += pytesseract.image_to_string(image) + "\n"
            
            if len(ocr_text.strip()) > len(text.strip()):
                text = ocr_text
                logger.info("OCR extraction successful")
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
    
    return text.strip()


# --- 6. CV DOWNLOAD dari URL (Google Drive, Dropbox, Direct Links) ---
def convert_google_drive_link(url: str) -> str:
    """
    Convert Google Drive sharing link to direct download link
    """
    if 'drive.google.com' in url:
        if '/file/d/' in url:
            file_id = url.split('/file/d/')[1].split('/')[0]
            return f"https://drive.google.com/uc?export=download&id={file_id}"
        elif 'id=' in url:
            file_id = url.split('id=')[1].split('&')[0]
            return f"https://drive.google.com/uc?export=download&id={file_id}"
    return url


def download_cv_from_url(url: str) -> Optional[bytes]:
    """
    Download CV PDF from URL (support Google Drive, Dropbox, direct links)
    """
    if not PANDAS_AVAILABLE or not requests:
        logger.error("requests library not available")
        return None
    
    try:
        # Convert Google Drive links
        url = convert_google_drive_link(url)
        
        # Handle Dropbox links
        if 'dropbox.com' in url and 'dl=0' in url:
            url = url.replace('dl=0', 'dl=1')
        
        # Download with timeout
        response = requests.get(url, timeout=30, allow_redirects=True)
        response.raise_for_status()
        
        # Check if response is PDF
        content_type = response.headers.get('Content-Type', '')
        if 'application/pdf' in content_type or url.lower().endswith('.pdf'):
            return response.content
        else:
            logger.warning(f"URL did not return PDF: {content_type}")
            return None
            
    except requests.exceptions.Timeout:
        logger.error(f"Timeout downloading from {url}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading from {url}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error downloading from {url}: {e}")
    
    return None


def read_excel_with_cv_links(excel_file) -> Optional[pd.DataFrame]:
    """
    Membaca file Excel dan mengekstrak kolom nama kandidat dan link CV
    """
    if not PANDAS_AVAILABLE or pd is None:
        st.error("Pandas library not available. Please install: pip install pandas openpyxl")
        return None
    
    try:
        df = pd.read_excel(excel_file)
        
        # Cari kolom nama (case-insensitive)
        name_cols = [col for col in df.columns if col.lower() in ['name', 'nama', 'candidate name', 'nama kandidat']]
        if not name_cols:
            st.error("Kolom 'Nama' atau 'Name' tidak ditemukan / Column 'Name' or 'Nama' not found")
            return None
        name_col = name_cols[0]
        
        # Cari kolom link CV (case-insensitive)
        link_cols = [col for col in df.columns if any(x in col.lower() for x in ['link', 'url', 'cv link', 'link cv'])]
        if not link_cols:
            st.error("Kolom 'Link CV' atau 'CV Link' atau 'URL' tidak ditemukan / Column 'CV Link', 'Link CV', or 'URL' not found")
            return None
        link_col = link_cols[0]
        
        # Filter rows dengan link yang valid
        df_filtered = df[[name_col, link_col]].dropna()
        df_filtered.columns = ['name', 'cv_link']
        
        # Validasi URL
        df_filtered = df_filtered[df_filtered['cv_link'].str.contains('http', case=False, na=False)]
        
        return df_filtered
        
    except Exception as e:
        logger.error(f"Error reading Excel: {e}")
        st.error(f"Error membaca Excel / Error reading Excel: {str(e)}")
        return None


def process_excel_cv_links(excel_file, role: str) -> List[Dict]:
    """
    Download dan proses semua CV dari Excel file
    """
    df = read_excel_with_cv_links(excel_file)
    if df is None or df.empty:
        return []
    
    results = []
    roles = load_roles()
    role_description = roles.get(role, "")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, row in df.iterrows():
        candidate_name = row['name']
        cv_url = row['cv_link']
        
        progress = (idx + 1) / len(df)
        progress_bar.progress(progress)
        status_text.text(f"{get_text('processing_status')}: {candidate_name} ({idx + 1}/{len(df)})")
        
        # Download CV
        pdf_bytes = download_cv_from_url(cv_url)
        
        if pdf_bytes:
            # Extract text
            cv_text = extract_text_from_pdf(pdf_bytes, use_ocr=st.session_state.enable_ocr)
            
            if cv_text and len(cv_text) > 50:
                # Analyze
                try:
                    analysis = analyze_resume(cv_text, role_description, st.session_state.api_key)
                    
                    result = {
                        'candidate_name': candidate_name,
                        'role': role,
                        'status': analysis.get('status', 'error'),
                        'match_percentage': analysis.get('match_percentage', 0),
                        'strengths': analysis.get('strengths', []),
                        'areas_for_improvement': analysis.get('areas_for_improvement', []),
                        'key_skills': analysis.get('key_skills', []),
                        'experience_years': analysis.get('experience_years', 'N/A'),
                        'education': analysis.get('education', 'N/A'),
                        'recommendation': analysis.get('recommendation', ''),
                        'pdf_bytes': pdf_bytes,
                        'cv_url': cv_url,
                        'ocr_used': st.session_state.enable_ocr,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    results.append(result)
                    st.toast(f"✅ {candidate_name}: {result['match_percentage']}%", icon="✅")
                    
                except Exception as e:
                    logger.error(f"Analysis error for {candidate_name}: {e}")
                    results.append({
                        'candidate_name': candidate_name,
                        'role': role,
                        'status': 'error',
                        'match_percentage': 0,
                        'error': str(e),
                        'cv_url': cv_url,
                        'timestamp': datetime.now().isoformat()
                    })
            else:
                results.append({
                    'candidate_name': candidate_name,
                    'role': role,
                    'status': 'error',
                    'match_percentage': 0,
                    'error': get_text('error_pdf_text'),
                    'cv_url': cv_url,
                    'timestamp': datetime.now().isoformat()
                })
        else:
            results.append({
                'candidate_name': candidate_name,
                'role': role,
                'status': 'error',
                'match_percentage': 0,
                'error': get_text('cv_download_error'),
                'cv_url': cv_url,
                'timestamp': datetime.now().isoformat()
            })
    
    progress_bar.empty()
    status_text.empty()
    
    return results


# --- 7. AGENT AI UNTUK ANALISIS RESUME ---
def analyze_resume(cv_text: str, role_description: str, api_key: str) -> Dict:
    """
    Analisis resume menggunakan OpenAI melalui phidata Agent
    """
    try:
        agent = Agent(
            model=OpenAIChat(id="gpt-4o", api_key=api_key),
            markdown=True,
        )
        
        prompt = f"""
Sebagai expert HR recruiter, analisis CV berikut untuk posisi:

ROLE REQUIREMENTS:
{role_description}

CANDIDATE CV:
{cv_text[:8000]}

Berikan analisis dalam format JSON berikut:
{{
    "status": "selected" atau "rejected",
    "match_percentage": <angka 0-100>,
    "strengths": [<list kekuatan kandidat, max 5 poin>],
    "areas_for_improvement": [<list area yang perlu ditingkatkan, max 5 poin>],
    "key_skills": [<list skill utama yang relevan>],
    "experience_years": "<total tahun pengalaman>",
    "education": "<pendidikan terakhir>",
    "recommendation": "<rekomendasi singkat>"
}}

CRITICAL: Respons HARUS valid JSON. Jangan tambahkan teks apapun di luar JSON.
"""
        
        response = agent.run(prompt)
        
        # Extract JSON from response
        json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
        if json_match:
            analysis = json.loads(json_match.group())
            return analysis
        else:
            raise ValueError("No valid JSON found in response")
            
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return {
            'status': 'error',
            'match_percentage': 0,
            'error': str(e)
        }


# --- 8. DISPLAY FUNCTIONS ---
def display_role_management():
    """Tampilan untuk mengelola roles"""
    st.header(get_text('tab_manage_roles'))
    
    # Add new role section
    st.subheader(get_text('add_role_header'))
    
    col1, col2 = st.columns(2)
    with col1:
        new_role_id = st.text_input(
            get_text('role_id_label'),
            help=get_text('role_id_help'),
            key='new_role_id'
        )
    with col2:
        new_role_name = st.text_input(
            get_text('role_name_label'),
            key='new_role_name'
        )
    
    new_role_description = st.text_area(
        get_text('required_skills_label'),
        height=200,
        help=get_text('required_skills_help'),
        key='new_role_description'
    )
    
    if st.button(get_text('add_role_button'), type='primary'):
        if new_role_id and new_role_description:
            if not validate_role_id(new_role_id):
                st.error(get_text('role_id_invalid'))
            elif new_role_id in st.session_state.roles:
                st.error(get_text('role_exists_error'))
            else:
                save_role(new_role_id, new_role_description)
                st.success(get_text('role_added_success'))
                st.rerun()
    
    st.markdown("---")
    
    # Edit existing roles
    roles = load_roles()
    if roles:
        st.subheader(get_text('edit_role_header'))
        
        selected_role = st.selectbox(
            get_text('select_role_to_edit'),
            list(roles.keys()),
            format_func=lambda x: x.replace('_', ' ').title()
        )
        
        if selected_role:
            edit_description = st.text_area(
                get_text('required_skills_label'),
                value=roles[selected_role],
                height=200,
                key='edit_role_description'
            )
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button(get_text('update_role_button'), type='primary'):
                    save_role(selected_role, edit_description)
                    st.success(get_text('role_updated_success'))
                    st.rerun()
            
            with col2:
                if st.button(get_text('delete_role_button'), type='secondary'):
                    delete_role(selected_role)
                    st.success(get_text('role_deleted_success'))
                    st.rerun()
        
        st.markdown("---")
        
        # Current roles list
        st.subheader(get_text('current_roles_header'))
        for role_id, description in roles.items():
            with st.expander(f"🌱 {role_id.replace('_', ' ').title()}"):
                st.markdown(description)
    else:
        st.info(get_text('no_roles_available'))


def display_results_table(results: List[Dict], language: str):
    """Tampilkan hasil dalam bentuk tabel dengan filter dan sort"""
    st.header(get_text('tab_results'))
    
    if not results:
        st.info(get_text('no_results_yet'))
        return
    
    # Summary metrics
    st.subheader(get_text('summary_header'))
    col1, col2, col3, col4 = st.columns(4)
    
    selected_count = sum(1 for r in results if r['status'] == 'selected')
    rejected_count = sum(1 for r in results if r['status'] == 'rejected')
    error_count = sum(1 for r in results if r['status'] == 'error')
    
    col1.metric(get_text('total_processed'), len(results))
    col2.metric(get_text('selected_label'), selected_count)
    col3.metric(get_text('rejected_label'), rejected_count)
    col4.metric(get_text('errors_label'), error_count)
    
    st.markdown("---")
    
    # Filters
    col1, col2 = st.columns(2)
    with col1:
        status_filter = st.selectbox(
            get_text('filter_by_status'),
            [get_text('filter_all'), get_text('filter_selected'), get_text('filter_rejected'), get_text('filter_error')]
        )
    
    with col2:
        sort_option = st.selectbox(
            get_text('sort_by'),
            [get_text('sort_match_desc'), get_text('sort_match_asc'), get_text('sort_name')]
        )
    
    # Apply filters
    filtered_results = results.copy()
    if status_filter == get_text('filter_selected'):
        filtered_results = [r for r in filtered_results if r['status'] == 'selected']
    elif status_filter == get_text('filter_rejected'):
        filtered_results = [r for r in filtered_results if r['status'] == 'rejected']
    elif status_filter == get_text('filter_error'):
        filtered_results = [r for r in filtered_results if r['status'] == 'error']
    
    # Apply sorting
    if sort_option == get_text('sort_match_desc'):
        filtered_results.sort(key=lambda x: x.get('match_percentage', 0), reverse=True)
    elif sort_option == get_text('sort_match_asc'):
        filtered_results.sort(key=lambda x: x.get('match_percentage', 0))
    elif sort_option == get_text('sort_name'):
        filtered_results.sort(key=lambda x: x.get('candidate_name', ''))
    
    # Display results
    if PANDAS_AVAILABLE and pd is not None:
        df_display = pd.DataFrame([
            {
                get_text('candidate_name'): r.get('candidate_name', 'N/A'),
                get_text('match_percentage'): f"{r.get('match_percentage', 0)}%",
                get_text('status'): '✅' if r['status'] == 'selected' else ('❌' if r['status'] == 'rejected' else '⚠️'),
                get_text('key_skills'): ', '.join(r.get('key_skills', [])[:3]) if r.get('key_skills') else 'N/A',
                get_text('experience_years'): r.get('experience_years', 'N/A'),
            }
            for r in filtered_results
        ])
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    else:
        for result in filtered_results:
            with st.expander(f"🌿 {result.get('candidate_name', 'N/A')} - {result.get('match_percentage', 0)}%"):
                status_icon = '✅' if result['status'] == 'selected' else ('❌' if result['status'] == 'rejected' else '⚠️')
                st.markdown(f"**Status:** {status_icon} {result['status']}")
                st.markdown(f"**Match:** {result.get('match_percentage', 0)}%")
                
                if result.get('strengths'):
                    st.markdown("**Strengths:**")
                    for strength in result['strengths']:
                        st.markdown(f"- {strength}")
                
                if result.get('key_skills'):
                    st.markdown(f"**Skills:** {', '.join(result['key_skills'])}")
                
                if result.get('pdf_bytes'):
                    st.download_button(
                        get_text('download_button'),
                        data=result['pdf_bytes'],
                        file_name=f"{result.get('candidate_name', 'resume')}.pdf",
                        mime="application/pdf"
                    )
    
    # Export options
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button(get_text('export_results_json')):
            json_data = json.dumps(filtered_results, ensure_ascii=False, indent=2, default=str)
            st.download_button(
                get_text('export_results_json'),
                data=json_data,
                file_name=f"recruitment_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )


def display_chatbot_interface():
    """Interface chatbot untuk tanya jawab tentang hasil rekrutmen"""
    st.header(get_text('chatbot_header'))
    st.caption(get_text('chatbot_help'))
    
    # Check if there are results to discuss
    if not st.session_state.batch_results:
        st.info(get_text('no_results_for_chat'))
        return
    
    # Display chat history
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input(get_text('chatbot_placeholder')):
        # Add user message
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("🌿 Berpikir..."):
                try:
                    # Prepare context from results
                    results_summary = "\n\n".join([
                        f"Kandidat: {r.get('candidate_name')}, Match: {r.get('match_percentage')}%, Status: {r.get('status')}, "
                        f"Strengths: {', '.join(r.get('strengths', []))}, Skills: {', '.join(r.get('key_skills', []))}"
                        for r in st.session_state.batch_results[:10]  # Limit context
                    ])
                    
                    agent = Agent(
                        model=OpenAIChat(id="gpt-4o", api_key=st.session_state.api_key),
                        markdown=True,
                    )
                    
                    chat_prompt = f"""
Kamu adalah AI Recruiter yang membantu HR membuat keputusan rekrutmen.

DATA KANDIDAT:
{results_summary}

PERTANYAAN USER:
{prompt}

Berikan jawaban yang helpful, detailed, dan actionable. Gunakan data kandidat di atas untuk menjawab pertanyaan.
"""
                    
                    response = agent.run(chat_prompt)
                    assistant_message = response.content
                    
                    st.markdown(assistant_message)
                    st.session_state.chat_history.append({"role": "assistant", "content": assistant_message})
                    save_chat_history_to_disk()
                    
                except Exception as e:
                    error_msg = f"❌ Error: {str(e)}"
                    st.error(error_msg)
                    st.session_state.chat_history.append({"role": "assistant", "content": error_msg})
    
    # Clear chat button
    if st.button(get_text('clear_chat')):
        st.session_state.chat_history = []
        save_chat_history_to_disk()
        st.success(get_text('chat_cleared'))
        st.rerun()


# --- 9. MAIN APPLICATION ---
def main():
    # Apply nature theme FIRST
    apply_nature_theme()
    
    # Initialize
    initialize_session_state()
    
    # Page config (setelah theme applied)
    st.set_page_config(
        page_title="PT Srikandi - Recruitment System",
        page_icon="🌿",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom header dengan tema nature
    st.markdown("""
    <div class="nature-header">
        <h1>🌿 PT Srikandi Mitra Karya</h1>
        <p>AI-Powered Recruitment System with Nature Theme</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Sidebar configuration
    with st.sidebar:
        st.markdown(f"### {get_text('config_header')}")
        
        # Language selection
        language = st.selectbox(
            get_text('language_select'),
            ['id', 'en'],
            format_func=lambda x: '🇮🇩 Bahasa Indonesia' if x == 'id' else '🇬🇧 English',
            key='language'
        )
        
        st.markdown("---")
        
        # OpenAI settings
        st.markdown(f"### {get_text('openai_settings')}")
        api_key = st.text_input(
            get_text('api_key_label'),
            type="password",
            help=get_text('api_key_help'),
            value=st.session_state.api_key
        )
        if api_key:
            st.session_state.api_key = api_key
        
        st.markdown("---")
        
        # OCR settings
        if OCR_AVAILABLE:
            st.markdown(f"### {get_text('ocr_settings')}")
            enable_ocr = st.checkbox(
                get_text('enable_ocr'),
                value=st.session_state.enable_ocr,
                help=get_text('ocr_help')
            )
            st.session_state.enable_ocr = enable_ocr
            
            st.markdown("---")
        
        # Data management
        st.markdown(f"### {get_text('data_management')}")
        
        if st.button(get_text('clear_all_data'), type='secondary'):
            if st.checkbox(get_text('confirm_clear_data')):
                clear_all_data()
                st.success(get_text('all_data_cleared'))
                st.rerun()
        
        st.markdown("---")
        st.caption(get_text('storage_info'))
    
    # Main tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        get_text('tab_upload'),
        get_text('tab_download_excel'),
        get_text('tab_results'),
        get_text('tab_chatbot'),
        get_text('tab_manage_roles')
    ])
    
    # TAB 1: Upload & Process
    with tab1:
        st.info(get_text('batch_info'))
        
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
            
            uploaded_files = st.file_uploader(
                get_text('upload_resume_label'),
                type=['pdf'],
                accept_multiple_files=True,
                key='resume_uploader'
            )
            
            if uploaded_files:
                st.success(f"📁 {len(uploaded_files)} {get_text('resumes_uploaded')}")
                
                if st.button(get_text('process_all_button'), type='primary'):
                    results = []
                    role_description = roles[role]
                    
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    for idx, uploaded_file in enumerate(uploaded_files):
                        progress = (idx + 1) / len(uploaded_files)
                        progress_bar.progress(progress)
                        status_text.text(f"{get_text('processing_spinner')} {uploaded_file.name} ({idx + 1}/{len(uploaded_files)})")
                        
                        pdf_bytes = uploaded_file.read()
                        cv_text = extract_text_from_pdf(pdf_bytes, use_ocr=st.session_state.enable_ocr)
                        
                        if cv_text and len(cv_text) > 50:
                            try:
                                analysis = analyze_resume(cv_text, role_description, st.session_state.api_key)
                                
                                result = {
                                    'candidate_name': uploaded_file.name.replace('.pdf', ''),
                                    'role': role,
                                    'status': analysis.get('status', 'error'),
                                    'match_percentage': analysis.get('match_percentage', 0),
                                    'strengths': analysis.get('strengths', []),
                                    'areas_for_improvement': analysis.get('areas_for_improvement', []),
                                    'key_skills': analysis.get('key_skills', []),
                                    'experience_years': analysis.get('experience_years', 'N/A'),
                                    'education': analysis.get('education', 'N/A'),
                                    'recommendation': analysis.get('recommendation', ''),
                                    'pdf_bytes': pdf_bytes,
                                    'ocr_used': st.session_state.enable_ocr,
                                    'timestamp': datetime.now().isoformat()
                                }
                                
                                results.append(result)
                                st.toast(f"✅ {uploaded_file.name}: {result['match_percentage']}%", icon="✅")
                                
                            except Exception as e:
                                logger.error(f"Error processing {uploaded_file.name}: {e}")
                                results.append({
                                    'candidate_name': uploaded_file.name,
                                    'role': role,
                                    'status': 'error',
                                    'match_percentage': 0,
                                    'error': str(e),
                                    'timestamp': datetime.now().isoformat()
                                })
                        else:
                            results.append({
                                'candidate_name': uploaded_file.name,
                                'role': role,
                                'status': 'error',
                                'match_percentage': 0,
                                'error': get_text('error_pdf_text'),
                                'timestamp': datetime.now().isoformat()
                            })
                    
                    progress_bar.empty()
                    status_text.empty()
                    
                    if results:
                        results.sort(key=lambda x: x.get('match_percentage', 0), reverse=True)
                        st.session_state.batch_results = results
                        save_results_to_disk()
                        
                        st.success(get_text('processing_complete'))
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
            if PANDAS_AVAILABLE:
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
