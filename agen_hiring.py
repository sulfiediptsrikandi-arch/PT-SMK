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
from phi.model.google import Gemini
from phi.utils.log import logger

# Import Supabase
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    logger.warning("Supabase library not found. Install: pip install supabase")

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


# --- SUPABASE CONFIGURATION ---
def get_supabase_client() -> Optional[Client]:
    """Initialize Supabase client"""
    if not SUPABASE_AVAILABLE:
        return None
    
    supabase_url = st.session_state.get('supabase_url', '')
    supabase_key = st.session_state.get('supabase_key', '')
    
    if not supabase_url or not supabase_key:
        return None
    
    try:
        return create_client(supabase_url, supabase_key)
    except Exception as e:
        logger.error(f"Failed to create Supabase client: {e}")
        return None


# --- 1. DICTIONARY UNTUK TEKS DWIBASA (BAHASA INDONESIA & INGGRIS) ---
TEXTS = {
    # Sidebar & Konfigurasi - TEMA NATURE
    'app_title': {'id': "PT Srikandi Mitra Karya - Sistem Rekrutmen AI", 'en': "PT Srikandi Mitra Karya - AI Recruitment System"},
    'config_header': {'id': "🌿 Konfigurasi", 'en': "🌿 Configuration"},
    'gemini_settings': {'id': "Pengaturan Google Gemini", 'en': "Google Gemini Settings"},
    'api_key_label': {'id': "Kunci API Google Gemini", 'en': "Google Gemini API Key"},
    'api_key_help': {'id': "Dapatkan kunci API Anda dari aistudio.google.com/apikey", 'en': "Get your API key from aistudio.google.com/apikey"},
    'warning_missing_config': {'id': "⚠️ Harap konfigurasikan hal berikut di sidebar: ", 'en': "⚠️ Please configure the following in the sidebar: "},
    'language_select': {'id': "Pilih Bahasa", 'en': "Select Language"},
    'reset_button': {'id': "🔄 Reset Aplikasi", 'en': "🔄 Reset Application"},
    'ocr_settings': {'id': "Pengaturan OCR", 'en': "OCR Settings"},
    'enable_ocr': {'id': "Aktifkan OCR untuk PDF Gambar", 'en': "Enable OCR for Image PDFs"},
    'ocr_help': {'id': "OCR akan memindai PDF berbasis gambar untuk ekstraksi teks yang lebih baik", 'en': "OCR will scan image-based PDFs for better text extraction"},
    
    # Supabase Settings
    'supabase_settings': {'id': "Pengaturan Supabase", 'en': "Supabase Settings"},
    'supabase_url_label': {'id': "Supabase URL", 'en': "Supabase URL"},
    'supabase_url_help': {'id': "URL project Supabase Anda", 'en': "Your Supabase project URL"},
    'supabase_key_label': {'id': "Supabase Anon Key", 'en': "Supabase Anon Key"},
    'supabase_key_help': {'id': "Anon/Public key dari project Supabase Anda", 'en': "Anon/Public key from your Supabase project"},
    'supabase_status': {'id': "Status Koneksi", 'en': "Connection Status"},
    'supabase_connected': {'id': "✅ Terhubung ke Supabase", 'en': "✅ Connected to Supabase"},
    'supabase_not_configured': {'id': "⚠️ Supabase belum dikonfigurasi", 'en': "⚠️ Supabase not configured"},
    
    # Role Management - TEMA NATURE
    'tab_manage_roles': {'id': "🌱 Kelola Posisi", 'en': "🌱 Manage Roles"},
    'add_role_header': {'id': "🌿 Tambah Posisi Baru", 'en': "🌿 Add New Role"},
    'edit_role_header': {'id': "🍃 Edit Posisi", 'en': "🍃 Edit Role"},
    'role_id_label': {'id': "ID Posisi (tanpa spasi)", 'en': "Role ID (no spaces)"},
    'role_id_help': {'id': "Gunakan huruf kecil dan underscore, contoh: senior_developer", 'en': "Use lowercase and underscores, e.g.: senior_developer"},
    'role_name_label': {'id': "Nama Posisi", 'en': "Role Name"},
    'required_skills_label': {'id': "Persyaratan & Keterampilan", 'en': "Requirements & Skills"},
    'required_skills_help': {'id': "Daftar persyaratan untuk posisi ini", 'en': "List of requirements for this role"},
    'add_role_button': {'id': "🌿 Tambah Posisi", 'en': "🌿 Add Role"},
    'update_role_button': {'id': "💚 Update Posisi", 'en': "💚 Update Role"},
    'delete_role_button': {'id': "🍂 Hapus Posisi", 'en': "🍂 Delete Role"},
    'role_added_success': {'id': "✅ Posisi berhasil ditambahkan!", 'en': "✅ Role added successfully!"},
    'role_updated_success': {'id': "✅ Posisi berhasil diupdate!", 'en': "✅ Role updated successfully!"},
    'role_deleted_success': {'id': "✅ Posisi berhasil dihapus!", 'en': "✅ Role deleted successfully!"},
    'role_exists_error': {'id': "❌ ID Posisi sudah ada!", 'en': "❌ Role ID already exists!"},
    'role_id_invalid': {'id': "❌ ID Posisi tidak valid! Gunakan huruf kecil, angka, dan underscore saja.", 'en': "❌ Invalid Role ID! Use lowercase letters, numbers, and underscores only."},
    'select_role_to_edit': {'id': "Pilih posisi untuk diedit:", 'en': "Select role to edit:"},
    'no_roles_available': {'id': "Tidak ada posisi tersedia. Tambahkan posisi baru terlebih dahulu.", 'en': "No roles available. Add a new role first."},
    'current_roles_header': {'id': "📋 Daftar Posisi Saat Ini", 'en': "📋 Current Roles List"},
    'export_roles_button': {'id': "🌳 Export Posisi (JSON)", 'en': "🌳 Export Roles (JSON)"},
    'import_roles_button': {'id': "🌲 Import Posisi (JSON)", 'en': "🌲 Import Roles (JSON)"},
    'import_roles_success': {'id': "✅ Posisi berhasil diimport!", 'en': "✅ Roles imported successfully!"},
    'import_roles_error': {'id': "❌ Gagal import posisi. Pastikan format JSON benar.", 'en': "❌ Failed to import roles. Ensure JSON format is correct."},
    'storage_info': {'id': "💚 Data disimpan otomatis ke Supabase", 'en': "💚 Data saved automatically to Supabase"},
    'data_loaded': {'id': "✅ Data berhasil dimuat dari Supabase", 'en': "✅ Data loaded from Supabase successfully"},
    'clear_all_data': {'id': "🍂 Hapus History & Hasil Analisa", 'en': "🍂 Clear History & Analysis Results"},
    'confirm_clear_data': {'id': "Apakah Anda yakin ingin menghapus history chat dan hasil analisa? (Data posisi akan tetap tersimpan)", 'en': "Are you sure you want to delete chat history and analysis results? (Position data will remain saved)"},
    'all_data_cleared': {'id': "✅ History chat dan hasil analisa berhasil dihapus", 'en': "✅ Chat history and analysis results cleared successfully"},
    'data_management': {'id': "Manajemen Data", 'en': "Data Management"},
    'tab_data_management': {'id': "💚 Manajemen Data", 'en': "💚 Data Management"},
    'export_all_data': {'id': "🌳 Export Semua Data", 'en': "🌳 Export All Data"},
    'import_all_data': {'id': "🌲 Import Semua Data", 'en': "🌲 Import All Data"},
    'backup_success': {'id': "✅ Backup berhasil dibuat", 'en': "✅ Backup created successfully"},
    'restore_success': {'id': "✅ Data berhasil dipulihkan", 'en': "✅ Data restored successfully"},
    
    # Mode Pemrosesan - TEMA NATURE
    'select_role': {'id': "Pilih Posisi yang Dibutuhkan:", 'en': "Select the Required Role:"},
    'view_skills_expander': {'id': "📋 Lihat Keterampilan yang Dibutuhkan", 'en': "📋 View Required Skills"},
    
    # Mode Batch Processing - TEMA NATURE
    'upload_resume_label': {'id': "Unggah resume (PDF)", 'en': "Upload resume (PDF)"},
    'batch_info': {'id': "🌿 Unggah beberapa resume (PDF) untuk memprosesnya secara otomatis.", 'en': "🌿 Upload multiple resumes (PDF) to process them automatically."},
    'clear_resumes_button': {'id': "🍂 Bersihkan Resume", 'en': "🍂 Clear Resumes"},
    'clear_resumes_help': {'id': "Hapus semua berkas PDF yang diunggah", 'en': "Remove all uploaded PDF files"},
    'resumes_uploaded': {'id': "resume(s) terunggah", 'en': "resume(s) uploaded"},
    'process_all_button': {'id': "🌳 Proses Semua Resume", 'en': "🌳 Process All Applications"},
    'processing_spinner': {'id': "Memproses aplikasi...", 'en': "Processing application..."},
    'ocr_processing': {'id': "🔍 Memindai dengan OCR...", 'en': "🔍 Scanning with OCR..."},
    
    # Mode Excel Processing - TEMA NATURE
    'excel_mode_header': {'id': "📊 Mode: Proses CV dari Excel", 'en': "📊 Mode: Process CVs from Excel"},
    'upload_excel_label': {'id': "🌿 Unggah File Excel (.xlsx, .xls)", 'en': "🌿 Upload Excel File (.xlsx, .xls)"},
    'excel_uploaded': {'id': "File Excel terunggah", 'en': "Excel file uploaded"},
    'download_all_cv': {'id': "🌳 Unduh & Proses Semua CV", 'en': "🌳 Download & Process All CVs"},
    'google_drive_guide': {'id': "📘 Panduan Google Drive", 'en': "📘 Google Drive Guide"},
    'no_valid_links': {'id': "❌ Tidak ada link CV valid yang ditemukan di Excel", 'en': "❌ No valid CV links found in Excel"},
    'invalid_excel_format': {'id': "❌ Format Excel tidak valid atau tidak ada kolom 'Link CV'", 'en': "❌ Invalid Excel format or no 'Link CV' column"},
    
    # Resume Analysis Results - TEMA NATURE
    'tab_results': {'id': "🌿 Hasil & Ringkasan", 'en': "🌿 Results & Summary"},
    'no_results_yet': {'id': "Belum ada hasil analisis. Unggah dan proses CV terlebih dahulu.", 'en': "No analysis results yet. Upload and process CVs first."},
    'download_selected_excel': {'id': "📥 Unduh Hasil (Excel)", 'en': "📥 Download Results (Excel)"},
    'download_rejected_excel': {'id': "📥 Unduh Rejected (Excel)", 'en': "📥 Download Rejected (Excel)"},
    'download_all_excel': {'id': "📥 Unduh Semua Hasil (Excel)", 'en': "📥 Download All Results (Excel)"},
    'filter_results': {'id': "🔍 Filter Hasil", 'en': "🔍 Filter Results"},
    'show_all': {'id': "Tampilkan Semua", 'en': "Show All"},
    'show_selected': {'id': "Hanya Terpilih", 'en': "Only Selected"},
    'show_rejected': {'id': "Hanya Rejected", 'en': "Only Rejected"},
    'processing_complete': {'id': "🎉 Pemrosesan Selesai!", 'en': "🎉 Processing Complete!"},
    'results_summary': {'id': "📊 Ringkasan Hasil", 'en': "📊 Results Summary"},
    'total_processed': {'id': "Total Diproses", 'en': "Total Processed"},
    'selected_candidates': {'id': "Kandidat Terpilih", 'en': "Selected Candidates"},
    'rejected_candidates': {'id': "Kandidat Rejected", 'en': "Rejected Candidates"},
    'error_processing': {'id': "Error Pemrosesan", 'en': "Processing Errors"},
    'search_candidates': {'id': "🔍 Cari Kandidat", 'en': "🔍 Search Candidates"},
    'search_placeholder': {'id': "Cari berdasarkan nama, alasan, atau keterampilan...", 'en': "Search by name, reason, or skills..."},
    'candidate_details': {'id': "Detail Kandidat", 'en': "Candidate Details"},
    'match_percentage': {'id': "Persentase Kecocokan", 'en': "Match Percentage"},
    'selection_reason': {'id': "Alasan Keputusan", 'en': "Decision Reason"},
    'extracted_skills': {'id': "Keterampilan Teridentifikasi", 'en': "Identified Skills"},
    'view_resume_text': {'id': "📄 Lihat Teks Resume", 'en': "📄 View Resume Text"},
    'view_analysis': {'id': "🔍 Lihat Analisis Lengkap", 'en': "🔍 View Full Analysis"},
    
    # Chatbot Interface - TEMA NATURE
    'tab_chatbot': {'id': "💬 Chat dengan Asisten", 'en': "💬 Chat with Assistant"},
    'chat_welcome': {'id': "Halo! Saya asisten rekrutmen AI. Tanyakan apapun tentang kandidat yang sudah diproses.", 'en': "Hello! I'm an AI recruitment assistant. Ask me anything about the processed candidates."},
    'chat_input_placeholder': {'id': "Ketik pertanyaan Anda di sini...", 'en': "Type your question here..."},
    'send_button': {'id': "Kirim", 'en': "Send"},
    'clear_chat_button': {'id': "🍂 Bersihkan Chat", 'en': "🍂 Clear Chat"},
    'chat_cleared': {'id': "Chat dibersihkan!", 'en': "Chat cleared!"},
    'no_candidates_chat': {'id': "Belum ada data kandidat. Proses CV terlebih dahulu untuk memulai chat.", 'en': "No candidate data yet. Process CVs first to start chatting."},
    
    # Tab Titles - TEMA NATURE
    'tab_upload': {'id': "🌿 Unggah Resume", 'en': "🌿 Upload Resumes"},
    'tab_excel': {'id': "📊 Proses dari Excel", 'en': "📊 Process from Excel"},
    
    # Status messages
    'status_selected': {'id': "Terpilih", 'en': "Selected"},
    'status_rejected': {'id': "Rejected", 'en': "Rejected"},
    'status_error': {'id': "Error", 'en': "Error"},
    
    # Missing configuration warnings
    'missing_api_key': {'id': "Kunci API Google Gemini", 'en': "Google Gemini API Key"},
    'missing_roles': {'id': "Definisi Posisi", 'en': "Role Definitions"},
}

def get_text(key: str) -> str:
    """Ambil teks berdasarkan bahasa yang dipilih"""
    return TEXTS.get(key, {}).get(st.session_state.language, key)


# --- 2. STATE MANAGEMENT MENGGUNAKAN SESSION STATE ---
def initialize_session_state():
    """Initialize semua state yang diperlukan"""
    defaults = {
        'language': 'id',
        'gemini_api_key': '',
        'supabase_url': '',
        'supabase_key': '',
        'uploaded_files': [],
        'batch_results': [],
        'chat_history': [],
        'roles': {},
        'enable_ocr': False,
        'selected_filter': 'Tampilkan Semua',
        'search_query': '',
        'data_loaded_from_supabase': False,
    }
    
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value
    
    # IMPORTANT: Load dari Supabase hanya sekali saat pertama kali
    if not st.session_state.data_loaded_from_supabase:
        load_all_from_supabase()
        st.session_state.data_loaded_from_supabase = True


# --- 3. SUPABASE DATA PERSISTENCE ---
def save_to_supabase(table_name: str, data: dict):
    """Save data to Supabase"""
    client = get_supabase_client()
    if not client:
        return False
    
    try:
        # Use upsert to handle both insert and update
        result = client.table(table_name).upsert(data).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to save to Supabase {table_name}: {e}")
        return False


def load_from_supabase(table_name: str, key_column: str = 'id'):
    """Load data from Supabase"""
    client = get_supabase_client()
    if not client:
        return None
    
    try:
        result = client.table(table_name).select("*").execute()
        if result.data:
            return {item[key_column]: item for item in result.data}
        return {}
    except Exception as e:
        logger.error(f"Failed to load from Supabase {table_name}: {e}")
        return None


def save_all_to_supabase():
    """Save all application data to Supabase"""
    client = get_supabase_client()
    if not client:
        return
    
    try:
        # Save roles
        if st.session_state.roles:
            for role_id, role_data in st.session_state.roles.items():
                save_to_supabase('roles', {
                    'id': role_id,
                    'data': role_data,
                    'updated_at': datetime.now().isoformat()
                })
        
        # Save batch results
        if st.session_state.batch_results:
            save_to_supabase('batch_results', {
                'id': 'current',
                'data': st.session_state.batch_results,
                'updated_at': datetime.now().isoformat()
            })
        
        # Save chat history
        if st.session_state.chat_history:
            save_to_supabase('chat_history', {
                'id': 'current',
                'data': st.session_state.chat_history,
                'updated_at': datetime.now().isoformat()
            })
        
        logger.info("All data saved to Supabase")
    except Exception as e:
        logger.error(f"Error saving to Supabase: {e}")


def load_all_from_supabase():
    """Load all application data from Supabase"""
    client = get_supabase_client()
    if not client:
        return
    
    try:
        # Load roles
        roles_data = load_from_supabase('roles')
        if roles_data:
            st.session_state.roles = {k: v['data'] for k, v in roles_data.items()}
        
        # Load batch results
        try:
            result = client.table('batch_results').select("*").eq('id', 'current').execute()
            if result.data and len(result.data) > 0:
                st.session_state.batch_results = result.data[0].get('data', [])
        except Exception as e:
            logger.error(f"Error loading batch results: {e}")
        
        # Load chat history
        try:
            result = client.table('chat_history').select("*").eq('id', 'current').execute()
            if result.data and len(result.data) > 0:
                st.session_state.chat_history = result.data[0].get('data', [])
        except Exception as e:
            logger.error(f"Error loading chat history: {e}")
        
        logger.info("All data loaded from Supabase")
    except Exception as e:
        logger.error(f"Error loading from Supabase: {e}")


# --- 4. ROLE MANAGEMENT FUNCTIONS ---
def save_roles_to_disk():
    """Save roles ke file JSON lokal sebagai backup"""
    try:
        with open('roles.json', 'w', encoding='utf-8') as f:
            json.dump(st.session_state.roles, f, ensure_ascii=False, indent=2)
        
        # Auto-save to Supabase
        save_all_to_supabase()
    except Exception as e:
        logger.error(f"Error saving roles: {e}")


def load_roles() -> Dict[str, str]:
    """Load roles dari session state atau file lokal"""
    if st.session_state.roles:
        return st.session_state.roles
    
    try:
        if os.path.exists('roles.json'):
            with open('roles.json', 'r', encoding='utf-8') as f:
                st.session_state.roles = json.load(f)
                return st.session_state.roles
    except Exception as e:
        logger.error(f"Error loading roles: {e}")
    
    return {}


def add_role(role_id: str, role_name: str, requirements: str) -> bool:
    """Add a new role"""
    if not re.match(r'^[a-z0-9_]+$', role_id):
        return False
    
    if role_id in st.session_state.roles:
        return False
    
    st.session_state.roles[role_id] = f"**{role_name}**\n\n{requirements}"
    save_roles_to_disk()
    return True


def update_role(role_id: str, role_name: str, requirements: str) -> bool:
    """Update an existing role"""
    if role_id not in st.session_state.roles:
        return False
    
    st.session_state.roles[role_id] = f"**{role_name}**\n\n{requirements}"
    save_roles_to_disk()
    return True


def delete_role(role_id: str) -> bool:
    """Delete a role"""
    if role_id not in st.session_state.roles:
        return False
    
    del st.session_state.roles[role_id]
    save_roles_to_disk()
    return True


# --- 5. RESULT PERSISTENCE ---
def save_results_to_disk():
    """Save hasil analisis ke file JSON lokal sebagai backup"""
    try:
        results_file = 'batch_results.json'
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(st.session_state.batch_results, f, ensure_ascii=False, indent=2)
        
        # Auto-save to Supabase
        save_all_to_supabase()
    except Exception as e:
        logger.error(f"Error saving results: {e}")


def load_results_from_disk():
    """Load hasil analisis dari file JSON lokal"""
    try:
        results_file = 'batch_results.json'
        if os.path.exists(results_file):
            with open(results_file, 'r', encoding='utf-8') as f:
                st.session_state.batch_results = json.load(f)
    except Exception as e:
        logger.error(f"Error loading results: {e}")


# --- 6. PDF TEXT EXTRACTION ---
def extract_text_from_pdf(pdf_file) -> Tuple[str, bool]:
    """
    Ekstrak teks dari PDF. Return tuple (text, ocr_used)
    Jika PDF berbasis gambar dan OCR diaktifkan, gunakan OCR.
    """
    text = ""
    ocr_used = False
    
    try:
        # Coba ekstraksi teks normal dulu
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        
        # Jika hasil ekstraksi terlalu pendek (<100 karakter), gunakan OCR jika diaktifkan
        if len(text.strip()) < 100 and st.session_state.get('enable_ocr', False) and OCR_AVAILABLE:
            logger.info("Text extraction insufficient, trying OCR...")
            pdf_file.seek(0)
            pdf_bytes = pdf_file.read()
            
            try:
                images = convert_from_bytes(pdf_bytes)
                ocr_text = ""
                
                for image in images:
                    ocr_text += pytesseract.image_to_string(image) + "\n"
                
                if len(ocr_text.strip()) > len(text.strip()):
                    text = ocr_text
                    ocr_used = True
                    logger.info("OCR extraction successful")
            except Exception as ocr_error:
                logger.error(f"OCR failed: {ocr_error}")
        
        pdf_file.seek(0)
        
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        return "", False
    
    return text.strip(), ocr_used


# --- 7. AI AGENT & ANALYSIS ---
def create_recruitment_agent(role_requirements: str) -> Agent:
    """Create an AI agent untuk analisis resume"""
    
    if not st.session_state.gemini_api_key:
        raise ValueError("Google Gemini API key is not configured")
    
    instructions = f"""
    Anda adalah asisten rekrutmen AI yang berpengalaman. Tugas Anda adalah menganalisis resume kandidat 
    dan menentukan apakah mereka cocok untuk posisi yang dibutuhkan.
    
    **Persyaratan Posisi:**
    {role_requirements}
    
    **Instruksi Analisis:**
    1. Baca dan pahami resume dengan teliti
    2. Identifikasi keterampilan dan pengalaman kandidat
    3. Bandingkan dengan persyaratan posisi
    4. Berikan keputusan: SELECTED atau REJECTED
    5. Berikan alasan yang jelas dan spesifik
    6. Jika SELECTED, estimasi persentase kecocokan (0-100%)
    7. Daftar keterampilan yang teridentifikasi dari resume
    
    **Format Output (JSON):**
    {{
        "decision": "SELECTED" atau "REJECTED",
        "reason": "Alasan keputusan dengan detail spesifik",
        "match_percentage": 85,
        "identified_skills": ["skill1", "skill2", "skill3"]
    }}
    
    **Catatan Penting:**
    - Gunakan Bahasa Indonesia untuk alasan
    - Fokus pada keterampilan teknis dan pengalaman relevan
    - Pertimbangkan potensi kandidat, bukan hanya pengalaman langsung
    - Jika kandidat memiliki keterampilan transferable yang relevan, pertimbangkan ini positif
    - Berikan feedback konstruktif dalam alasan rejection
    """
    
    agent = Agent(
        model=Gemini(
            id="gemini-1.5-flash",
            api_key=st.session_state.gemini_api_key
        ),
        instructions=instructions,
        markdown=True,
        show_tool_calls=False,
        debug_mode=False
    )
    
    return agent


def analyze_resume(resume_text: str, role_requirements: str) -> Dict:
    """Analisis resume menggunakan AI agent"""
    try:
        agent = create_recruitment_agent(role_requirements)
        
        prompt = f"""
        Analisis resume berikut dan berikan keputusan rekrutmen:
        
        ---RESUME---
        {resume_text[:4000]}  # Batasi panjang untuk efisiensi
        ---END RESUME---
        
        Berikan output dalam format JSON yang telah ditentukan.
        """
        
        response = agent.run(prompt)
        
        # Parse response
        response_text = response.content if hasattr(response, 'content') else str(response)
        
        # Coba ekstrak JSON dari response
        try:
            # Cari JSON dalam response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                # Fallback parsing
                result = {
                    "decision": "SELECTED" if "SELECTED" in response_text.upper() else "REJECTED",
                    "reason": response_text[:500],
                    "match_percentage": 50,
                    "identified_skills": []
                }
        except json.JSONDecodeError:
            result = {
                "decision": "SELECTED" if "SELECTED" in response_text.upper() else "REJECTED",
                "reason": response_text[:500],
                "match_percentage": 50,
                "identified_skills": []
            }
        
        # Validasi dan normalisasi
        result.setdefault("decision", "REJECTED")
        result.setdefault("reason", "Analisis tidak lengkap")
        result.setdefault("match_percentage", 0)
        result.setdefault("identified_skills", [])
        
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing resume: {e}")
        return {
            "decision": "REJECTED",
            "reason": f"Error dalam analisis: {str(e)}",
            "match_percentage": 0,
            "identified_skills": []
        }


def process_single_resume(pdf_file, role: str, filename: str = None) -> Dict:
    """Process single resume file"""
    try:
        # Extract text
        resume_text, ocr_used = extract_text_from_pdf(pdf_file)
        
        if not resume_text:
            return {
                'filename': filename or "unknown.pdf",
                'status': 'error',
                'reason': 'Gagal mengekstrak teks dari PDF',
                'match_percentage': 0,
                'resume_text': '',
                'ocr_used': ocr_used
            }
        
        # Analyze with AI
        roles = load_roles()
        role_requirements = roles.get(role, "")
        
        analysis = analyze_resume(resume_text, role_requirements)
        
        return {
            'filename': filename or "unknown.pdf",
            'status': 'selected' if analysis['decision'] == 'SELECTED' else 'rejected',
            'reason': analysis['reason'],
            'match_percentage': analysis.get('match_percentage', 0),
            'identified_skills': analysis.get('identified_skills', []),
            'resume_text': resume_text[:2000],  # Store limited text
            'ocr_used': ocr_used,
            'analysis_time': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error processing resume: {e}")
        return {
            'filename': filename or "unknown.pdf",
            'status': 'error',
            'reason': f'Error: {str(e)}',
            'match_percentage': 0,
            'resume_text': '',
            'ocr_used': False
        }


# --- 8. EXCEL & URL PROCESSING ---
def is_google_drive_link(url: str) -> bool:
    """Check if URL is a Google Drive link"""
    return 'drive.google.com' in url


def convert_google_drive_link(url: str) -> str:
    """Convert Google Drive link to direct download format"""
    try:
        if '/file/d/' in url:
            file_id = url.split('/file/d/')[1].split('/')[0]
            return f'https://drive.google.com/uc?export=download&id={file_id}'
        elif 'id=' in url:
            file_id = url.split('id=')[1].split('&')[0]
            return f'https://drive.google.com/uc?export=download&id={file_id}'
    except Exception as e:
        logger.error(f"Error converting Google Drive link: {e}")
    return url


def download_pdf_from_url(url: str, timeout: int = 30) -> Optional[BytesIO]:
    """Download PDF from URL with timeout"""
    if not PANDAS_AVAILABLE or not requests:
        logger.error("Requests library not available")
        return None
    
    try:
        # Convert Google Drive links
        if is_google_drive_link(url):
            url = convert_google_drive_link(url)
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        
        # Check if content is PDF
        content_type = response.headers.get('Content-Type', '')
        if 'pdf' not in content_type.lower() and not url.lower().endswith('.pdf'):
            logger.warning(f"URL may not be a PDF: {content_type}")
        
        return BytesIO(response.content)
        
    except requests.exceptions.Timeout:
        logger.error(f"Timeout downloading from {url}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading from {url}: {e}")
        return None


def read_excel_with_cv_links(excel_file) -> Optional[pd.DataFrame]:
    """Read Excel file and extract CV links"""
    if not PANDAS_AVAILABLE or pd is None:
        logger.error("Pandas not available")
        return None
    
    try:
        df = pd.read_excel(excel_file)
        
        # Find CV link column (case insensitive)
        cv_link_col = None
        name_col = None
        
        for col in df.columns:
            col_lower = col.lower()
            if 'link' in col_lower or 'url' in col_lower or 'cv' in col_lower:
                cv_link_col = col
            if 'nama' in col_lower or 'name' in col_lower:
                name_col = col
        
        if cv_link_col is None:
            logger.error("No CV link column found in Excel")
            return None
        
        # Filter rows with valid URLs
        df_filtered = df[df[cv_link_col].notna()].copy()
        df_filtered = df_filtered[df_filtered[cv_link_col].astype(str).str.startswith('http')]
        
        return df_filtered
        
    except Exception as e:
        logger.error(f"Error reading Excel: {e}")
        return None


def process_excel_cv_links(excel_file, role: str, max_cvs: int = 50) -> List[Dict]:
    """Process CVs from Excel file with links"""
    if not PANDAS_AVAILABLE:
        st.error("Pandas library required for Excel processing")
        return []
    
    results = []
    
    try:
        df = read_excel_with_cv_links(excel_file)
        
        if df is None or df.empty:
            return results
        
        # Limit to max_cvs
        df = df.head(max_cvs)
        
        # Find columns
        cv_link_col = None
        name_col = None
        
        for col in df.columns:
            col_lower = col.lower()
            if 'link' in col_lower or 'url' in col_lower:
                cv_link_col = col
            if 'nama' in col_lower or 'name' in col_lower:
                name_col = col
        
        # Create progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        total = len(df)
        
        for idx, row in df.iterrows():
            try:
                cv_url = str(row[cv_link_col])
                candidate_name = str(row[name_col]) if name_col else f"Candidate_{idx+1}"
                
                # Update progress
                progress = (idx + 1) / total
                progress_bar.progress(progress)
                status_text.text(f"Processing: {candidate_name} ({idx+1}/{total})")
                
                # Download PDF
                pdf_bytes = download_pdf_from_url(cv_url)
                
                if pdf_bytes is None:
                    results.append({
                        'filename': candidate_name,
                        'status': 'error',
                        'reason': 'Gagal mengunduh CV dari URL',
                        'match_percentage': 0,
                        'cv_url': cv_url
                    })
                    continue
                
                # Process resume
                result = process_single_resume(pdf_bytes, role, candidate_name)
                result['cv_url'] = cv_url
                
                # Add other info from Excel
                for col in df.columns:
                    if col not in [cv_link_col, name_col]:
                        result[col] = str(row[col])
                
                results.append(result)
                
                # Small delay to avoid rate limiting
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error processing row {idx}: {e}")
                results.append({
                    'filename': f"Row_{idx+1}",
                    'status': 'error',
                    'reason': f'Error: {str(e)}',
                    'match_percentage': 0
                })
        
        # Clear progress indicators
        progress_bar.empty()
        status_text.empty()
        
    except Exception as e:
        logger.error(f"Error in process_excel_cv_links: {e}")
        st.error(f"Error: {str(e)}")
    
    return results


# --- 9. RESULTS DISPLAY & EXPORT ---
def create_results_dataframe(results: List[Dict]) -> pd.DataFrame:
    """Create a DataFrame from results for display"""
    if not PANDAS_AVAILABLE or pd is None:
        return None
    
    display_data = []
    for r in results:
        display_data.append({
            'Nama / Name': r.get('filename', 'Unknown'),
            'Status': r.get('status', 'unknown').title(),
            'Match %': r.get('match_percentage', 0),
            'Alasan / Reason': r.get('reason', '')[:100] + '...' if len(r.get('reason', '')) > 100 else r.get('reason', ''),
            'Skills': ', '.join(r.get('identified_skills', []))[:50],
            'OCR': '🔍' if r.get('ocr_used', False) else ''
        })
    
    return pd.DataFrame(display_data)


def export_to_excel(results: List[Dict], filename: str = "recruitment_results.xlsx") -> BytesIO:
    """Export results to Excel file"""
    if not PANDAS_AVAILABLE or pd is None:
        return None
    
    try:
        df = pd.DataFrame([
            {
                'Nama Kandidat': r.get('filename', 'Unknown'),
                'Status': r.get('status', 'unknown').upper(),
                'Match Percentage': r.get('match_percentage', 0),
                'Alasan': r.get('reason', ''),
                'Identified Skills': ', '.join(r.get('identified_skills', [])),
                'OCR Used': 'Ya' if r.get('ocr_used', False) else 'Tidak',
                'CV URL': r.get('cv_url', ''),
                'Analysis Time': r.get('analysis_time', '')
            }
            for r in results
        ])
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Results')
        
        output.seek(0)
        return output
        
    except Exception as e:
        logger.error(f"Error exporting to Excel: {e}")
        return None


def display_results_table(results: List[Dict], language: str):
    """Display results in a nice table format with filters"""
    if not results:
        st.info(get_text('no_results_yet'))
        return
    
    # Summary metrics
    st.markdown(f"### {get_text('results_summary')}")
    col1, col2, col3, col4 = st.columns(4)
    
    total = len(results)
    selected = sum(1 for r in results if r['status'] == 'selected')
    rejected = sum(1 for r in results if r['status'] == 'rejected')
    errors = sum(1 for r in results if r['status'] == 'error')
    
    with col1:
        st.metric(get_text('total_processed'), total)
    with col2:
        st.metric(get_text('selected_candidates'), selected, f"{selected/total*100:.0f}%" if total > 0 else "0%")
    with col3:
        st.metric(get_text('rejected_candidates'), rejected, f"{rejected/total*100:.0f}%" if total > 0 else "0%")
    with col4:
        st.metric(get_text('error_processing'), errors)
    
    st.markdown("---")
    
    # Filter options
    col_filter, col_search = st.columns([1, 2])
    
    with col_filter:
        filter_option = st.selectbox(
            get_text('filter_results'),
            [get_text('show_all'), get_text('show_selected'), get_text('show_rejected')],
            key='results_filter'
        )
    
    with col_search:
        search_query = st.text_input(
            get_text('search_candidates'),
            placeholder=get_text('search_placeholder'),
            key='results_search'
        )
    
    # Apply filters
    filtered_results = results.copy()
    
    if filter_option == get_text('show_selected'):
        filtered_results = [r for r in filtered_results if r['status'] == 'selected']
    elif filter_option == get_text('show_rejected'):
        filtered_results = [r for r in filtered_results if r['status'] == 'rejected']
    
    if search_query:
        query_lower = search_query.lower()
        filtered_results = [
            r for r in filtered_results 
            if query_lower in r.get('filename', '').lower() 
            or query_lower in r.get('reason', '').lower()
            or any(query_lower in skill.lower() for skill in r.get('identified_skills', []))
        ]
    
    st.markdown(f"**{len(filtered_results)}** kandidat ditampilkan")
    
    # Export buttons
    col_export1, col_export2, col_export3 = st.columns(3)
    
    with col_export1:
        excel_all = export_to_excel(filtered_results)
        if excel_all:
            st.download_button(
                label=get_text('download_all_excel'),
                data=excel_all,
                file_name=f"all_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
    
    with col_export2:
        selected_results = [r for r in results if r['status'] == 'selected']
        if selected_results:
            excel_selected = export_to_excel(selected_results)
            if excel_selected:
                st.download_button(
                    label=get_text('download_selected_excel'),
                    data=excel_selected,
                    file_name=f"selected_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
    
    with col_export3:
        rejected_results = [r for r in results if r['status'] == 'rejected']
        if rejected_results:
            excel_rejected = export_to_excel(rejected_results)
            if excel_rejected:
                st.download_button(
                    label=get_text('download_rejected_excel'),
                    data=excel_rejected,
                    file_name=f"rejected_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
    
    st.markdown("---")
    
    # Display table
    if PANDAS_AVAILABLE:
        df = create_results_dataframe(filtered_results)
        if df is not None:
            st.dataframe(df, use_container_width=True, height=400)
    
    # Detailed view
    st.markdown(f"### {get_text('candidate_details')}")
    
    for idx, result in enumerate(filtered_results):
        status_icon = "✅" if result['status'] == 'selected' else "❌" if result['status'] == 'rejected' else "⚠️"
        
        with st.expander(f"{status_icon} {result.get('filename', 'Unknown')} - {result.get('match_percentage', 0)}%"):
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.markdown(f"**Status:** {result['status'].upper()}")
                st.markdown(f"**{get_text('match_percentage')}:** {result.get('match_percentage', 0)}%")
                if result.get('ocr_used'):
                    st.markdown("**OCR:** 🔍 Used")
            
            with col2:
                st.markdown(f"**{get_text('selection_reason')}:**")
                st.write(result.get('reason', 'N/A'))
            
            if result.get('identified_skills'):
                st.markdown(f"**{get_text('extracted_skills')}:**")
                st.write(", ".join(result['identified_skills']))
            
            if result.get('cv_url'):
                st.markdown(f"**CV URL:** [{result['cv_url']}]({result['cv_url']})")
            
            if result.get('resume_text'):
                with st.expander(get_text('view_resume_text')):
                    st.text(result['resume_text'][:1000] + "..." if len(result['resume_text']) > 1000 else result['resume_text'])


# --- 10. CHATBOT INTERFACE ---
def create_chatbot_agent() -> Agent:
    """Create chatbot agent untuk Q&A tentang kandidat"""
    
    if not st.session_state.gemini_api_key:
        raise ValueError("Google Gemini API key is not configured")
    
    # Prepare context from results
    context = "**Data Kandidat yang Sudah Diproses:**\n\n"
    
    for result in st.session_state.batch_results:
        context += f"- **{result.get('filename')}**: "
        context += f"Status={result['status'].upper()}, "
        context += f"Match={result.get('match_percentage', 0)}%, "
        context += f"Skills={', '.join(result.get('identified_skills', []))}, "
        context += f"Reason={result.get('reason', 'N/A')}\n"
    
    instructions = f"""
    Anda adalah asisten rekrutmen AI yang membantu HR dalam menganalisis kandidat.
    Anda memiliki akses ke data kandidat yang telah diproses.
    
    {context}
    
    **Instruksi:**
    - Jawab pertanyaan tentang kandidat dengan detail dan akurat
    - Gunakan Bahasa Indonesia atau Inggris sesuai dengan pertanyaan user
    - Berikan rekomendasi berdasarkan data yang tersedia
    - Jika ditanya tentang kandidat tertentu, rujuk ke data di atas
    - Jika informasi tidak tersedia, katakan dengan jelas
    - Berikan insight yang berguna untuk keputusan rekrutmen
    """
    
    agent = Agent(
        model=Gemini(
            id="gemini-1.5-flash",
            api_key=st.session_state.gemini_api_key
        ),
        instructions=instructions,
        markdown=True,
        show_tool_calls=False
    )
    
    return agent


def display_chatbot_interface():
    """Display chatbot interface"""
    st.markdown(f"## {get_text('tab_chatbot')}")
    
    if not st.session_state.batch_results:
        st.warning(get_text('no_candidates_chat'))
        return
    
    # Chat history display
    chat_container = st.container()
    
    with chat_container:
        for message in st.session_state.chat_history:
            role = message['role']
            content = message['content']
            
            if role == 'user':
                st.markdown(f"**🧑 You:** {content}")
            else:
                st.markdown(f"**🤖 Assistant:** {content}")
            
            st.markdown("---")
    
    # Chat input
    col1, col2 = st.columns([4, 1])
    
    with col1:
        user_input = st.text_input(
            get_text('chat_input_placeholder'),
            key='chat_input',
            label_visibility='collapsed'
        )
    
    with col2:
        send_button = st.button(get_text('send_button'), use_container_width=True)
    
    # Clear chat button
    if st.button(get_text('clear_chat_button')):
        st.session_state.chat_history = []
        save_all_to_supabase()
        st.success(get_text('chat_cleared'))
        st.rerun()
    
    # Process chat
    if send_button and user_input:
        # Add user message
        st.session_state.chat_history.append({
            'role': 'user',
            'content': user_input,
            'timestamp': datetime.now().isoformat()
        })
        
        # Get AI response
        try:
            agent = create_chatbot_agent()
            response = agent.run(user_input)
            
            assistant_message = response.content if hasattr(response, 'content') else str(response)
            
            # Add assistant message
            st.session_state.chat_history.append({
                'role': 'assistant',
                'content': assistant_message,
                'timestamp': datetime.now().isoformat()
            })
            
            # Save to Supabase
            save_all_to_supabase()
            
        except Exception as e:
            error_message = f"Error: {str(e)}"
            st.session_state.chat_history.append({
                'role': 'assistant',
                'content': error_message,
                'timestamp': datetime.now().isoformat()
            })
        
        st.rerun()


# --- 11. ROLE MANAGEMENT UI ---
def display_role_management():
    """Display role management interface"""
    st.markdown(f"## {get_text('tab_manage_roles')}")
    
    tab_add, tab_edit, tab_list = st.tabs([
        get_text('add_role_header'),
        get_text('edit_role_header'),
        get_text('current_roles_header')
    ])
    
    # TAB: Add Role
    with tab_add:
        st.markdown(f"### {get_text('add_role_header')}")
        
        new_role_id = st.text_input(
            get_text('role_id_label'),
            key='new_role_id',
            help=get_text('role_id_help')
        )
        
        new_role_name = st.text_input(
            get_text('role_name_label'),
            key='new_role_name'
        )
        
        new_requirements = st.text_area(
            get_text('required_skills_label'),
            height=200,
            key='new_requirements',
            help=get_text('required_skills_help')
        )
        
        if st.button(get_text('add_role_button'), type='primary', key='add_role_btn'):
            if new_role_id and new_role_name and new_requirements:
                if add_role(new_role_id, new_role_name, new_requirements):
                    st.success(get_text('role_added_success'))
                    st.rerun()
                else:
                    if not re.match(r'^[a-z0-9_]+$', new_role_id):
                        st.error(get_text('role_id_invalid'))
                    else:
                        st.error(get_text('role_exists_error'))
            else:
                st.warning("Please fill all fields")
    
    # TAB: Edit Role
    with tab_edit:
        st.markdown(f"### {get_text('edit_role_header')}")
        
        roles = load_roles()
        
        if not roles:
            st.info(get_text('no_roles_available'))
        else:
            role_to_edit = st.selectbox(
                get_text('select_role_to_edit'),
                list(roles.keys()),
                format_func=lambda x: x.replace('_', ' ').title(),
                key='role_to_edit'
            )
            
            if role_to_edit:
                current_content = roles[role_to_edit]
                # Extract name and requirements
                parts = current_content.split('\n\n', 1)
                current_name = parts[0].strip('**') if len(parts) > 0 else ""
                current_reqs = parts[1] if len(parts) > 1 else ""
                
                edit_role_name = st.text_input(
                    get_text('role_name_label'),
                    value=current_name,
                    key='edit_role_name'
                )
                
                edit_requirements = st.text_area(
                    get_text('required_skills_label'),
                    value=current_reqs,
                    height=200,
                    key='edit_requirements'
                )
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button(get_text('update_role_button'), type='primary', key='update_role_btn'):
                        if update_role(role_to_edit, edit_role_name, edit_requirements):
                            st.success(get_text('role_updated_success'))
                            st.rerun()
                
                with col2:
                    if st.button(get_text('delete_role_button'), type='secondary', key='delete_role_btn'):
                        if delete_role(role_to_edit):
                            st.success(get_text('role_deleted_success'))
                            st.rerun()
    
    # TAB: List Roles
    with tab_list:
        st.markdown(f"### {get_text('current_roles_header')}")
        
        roles = load_roles()
        
        if not roles:
            st.info(get_text('no_roles_available'))
        else:
            for role_id, role_content in roles.items():
                with st.expander(f"📋 {role_id.replace('_', ' ').title()}"):
                    st.markdown(role_content)
        
        st.markdown("---")
        
        # Export/Import
        col1, col2 = st.columns(2)
        
        with col1:
            if roles:
                roles_json = json.dumps(roles, ensure_ascii=False, indent=2)
                st.download_button(
                    label=get_text('export_roles_button'),
                    data=roles_json,
                    file_name=f"roles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    use_container_width=True
                )
        
        with col2:
            uploaded_roles = st.file_uploader(
                get_text('import_roles_button'),
                type=['json'],
                key='import_roles_uploader'
            )
            
            if uploaded_roles:
                try:
                    imported_roles = json.load(uploaded_roles)
                    st.session_state.roles.update(imported_roles)
                    save_roles_to_disk()
                    st.success(get_text('import_roles_success'))
                    st.rerun()
                except Exception as e:
                    st.error(f"{get_text('import_roles_error')}: {str(e)}")


# --- 12. DATA MANAGEMENT UI ---
def display_data_management():
    """Display data management interface"""
    st.markdown(f"## {get_text('tab_data_management')}")
    
    # Supabase Status
    client = get_supabase_client()
    if client:
        st.success(get_text('supabase_connected'))
        st.info(get_text('storage_info'))
    else:
        st.warning(get_text('supabase_not_configured'))
    
    st.markdown("---")
    
    # Clear Data
    st.markdown(f"### {get_text('clear_all_data')}")
    st.warning(get_text('confirm_clear_data'))
    
    if st.button(get_text('clear_all_data'), type='secondary', key='clear_data_btn'):
        st.session_state.batch_results = []
        st.session_state.chat_history = []
        save_all_to_supabase()
        st.success(get_text('all_data_cleared'))
        st.rerun()
    
    st.markdown("---")
    
    # Backup & Restore
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"### {get_text('export_all_data')}")
        
        if st.button(get_text('export_all_data'), type='primary', use_container_width=True):
            backup_data = {
                'roles': st.session_state.roles,
                'batch_results': st.session_state.batch_results,
                'chat_history': st.session_state.chat_history,
                'export_date': datetime.now().isoformat()
            }
            
            backup_json = json.dumps(backup_data, ensure_ascii=False, indent=2)
            
            st.download_button(
                label="⬇️ Download Backup",
                data=backup_json,
                file_name=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True
            )
            
            st.success(get_text('backup_success'))
    
    with col2:
        st.markdown(f"### {get_text('import_all_data')}")
        
        uploaded_backup = st.file_uploader(
            "Upload Backup File",
            type=['json'],
            key='import_backup_uploader'
        )
        
        if uploaded_backup:
            try:
                backup_data = json.load(uploaded_backup)
                
                if 'roles' in backup_data:
                    st.session_state.roles = backup_data['roles']
                if 'batch_results' in backup_data:
                    st.session_state.batch_results = backup_data['batch_results']
                if 'chat_history' in backup_data:
                    st.session_state.chat_history = backup_data['chat_history']
                
                save_all_to_supabase()
                st.success(get_text('restore_success'))
                st.rerun()
                
            except Exception as e:
                st.error(f"Error restoring backup: {str(e)}")


# --- 13. SIDEBAR CONFIGURATION ---
def display_sidebar():
    """Display sidebar with configuration"""
    with st.sidebar:
        st.markdown(f"# {get_text('config_header')}")
        
        # Language Selection
        language = st.selectbox(
            get_text('language_select'),
            options=['id', 'en'],
            format_func=lambda x: "🇮🇩 Bahasa Indonesia" if x == 'id' else "🇬🇧 English",
            key='language_selector'
        )
        st.session_state.language = language
        
        st.markdown("---")
        
        # Google Gemini Settings
        with st.expander(get_text('gemini_settings'), expanded=True):
            api_key = st.text_input(
                get_text('api_key_label'),
                type='password',
                value=st.session_state.gemini_api_key,
                help=get_text('api_key_help'),
                key='gemini_api_key_input'
            )
            st.session_state.gemini_api_key = api_key
        
        # Supabase Settings
        with st.expander(get_text('supabase_settings'), expanded=False):
            supabase_url = st.text_input(
                get_text('supabase_url_label'),
                value=st.session_state.supabase_url,
                help=get_text('supabase_url_help'),
                key='supabase_url_input'
            )
            st.session_state.supabase_url = supabase_url
            
            supabase_key = st.text_input(
                get_text('supabase_key_label'),
                type='password',
                value=st.session_state.supabase_key,
                help=get_text('supabase_key_help'),
                key='supabase_key_input'
            )
            st.session_state.supabase_key = supabase_key
            
            # Connection status
            client = get_supabase_client()
            if client:
                st.success(get_text('supabase_connected'))
            else:
                st.warning(get_text('supabase_not_configured'))
        
        # OCR Settings
        with st.expander(get_text('ocr_settings'), expanded=False):
            enable_ocr = st.checkbox(
                get_text('enable_ocr'),
                value=st.session_state.enable_ocr,
                help=get_text('ocr_help'),
                key='enable_ocr_checkbox'
            )
            st.session_state.enable_ocr = enable_ocr
            
            if not OCR_AVAILABLE:
                st.warning("OCR libraries not installed. Install: pip install pdf2image pytesseract pillow")
        
        st.markdown("---")
        
        # Reset Button
        if st.button(get_text('reset_button'), type='secondary', use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
        
        # Check for missing configuration
        missing_config = []
        if not st.session_state.gemini_api_key:
            missing_config.append(get_text('missing_api_key'))
        if not load_roles():
            missing_config.append(get_text('missing_roles'))
        
        if missing_config:
            st.markdown("---")
            st.warning(get_text('warning_missing_config'))
            for item in missing_config:
                st.markdown(f"- {item}")


# --- 14. MAIN APPLICATION ---
def main():
    """Main application function"""
    st.set_page_config(
        page_title="PT Srikandi Mitra Karya - AI Recruitment",
        page_icon="🌿",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS - Nature Theme
    st.markdown("""
    <style>
        .main { background-color: #f0f8f0; }
        .stButton>button { 
            background-color: #2d7a3d;
            color: white;
            border-radius: 10px;
        }
        .stButton>button:hover {
            background-color: #1f5a2d;
        }
        .stExpander {
            border: 1px solid #2d7a3d;
            border-radius: 10px;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Initialize
    initialize_session_state()
    
    # Display sidebar
    display_sidebar()
    
    # Main title
    st.title(get_text('app_title'))
    st.markdown("---")
    
    # Check configuration
    if not st.session_state.gemini_api_key:
        st.error("⚠️ Please configure Google Gemini API Key in the sidebar!")
        st.stop()
    
    # Tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        get_text('tab_upload'),
        get_text('tab_excel'),
        get_text('tab_results'),
        get_text('tab_chatbot'),
        get_text('tab_manage_roles'),
        get_text('tab_data_management')
    ])
    
    # TAB 1: Upload Resumes
    with tab1:
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
                key='batch_selected_role'
            )
            
            with st.expander(get_text('view_skills_expander'), expanded=False):
                st.markdown(roles[role])
            
            st.markdown("---")
            st.info(get_text('batch_info'))
            
            uploaded_files = st.file_uploader(
                get_text('upload_resume_label'),
                type=['pdf'],
                accept_multiple_files=True,
                key='batch_uploader'
            )
            
            if uploaded_files:
                st.success(f"📁 {len(uploaded_files)} {get_text('resumes_uploaded')}")
                
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    if st.button(get_text('process_all_button'), type='primary', use_container_width=True):
                        results = []
                        
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        for idx, pdf_file in enumerate(uploaded_files):
                            status_text.text(f"{get_text('processing_spinner')} {pdf_file.name}")
                            
                            result = process_single_resume(pdf_file, role, pdf_file.name)
                            results.append(result)
                            
                            progress_bar.progress((idx + 1) / len(uploaded_files))
                        
                        progress_bar.empty()
                        status_text.empty()
                        
                        results.sort(key=lambda x: x.get('match_percentage', 0), reverse=True)
                        
                        st.session_state.batch_results = results
                        save_results_to_disk()
                        
                        st.success(get_text('processing_complete'))
                        
                        selected_count = sum(1 for r in results if r['status'] == 'selected')
                        rejected_count = sum(1 for r in results if r['status'] == 'rejected')
                        error_count = sum(1 for r in results if r['status'] == 'error')
                        
                        st.info(f"✅ {selected_count} | ❌ {rejected_count} | ⚠️ {error_count}")
                        st.info(f"👉 {get_text('tab_results')}")
                
                with col2:
                    if st.button(get_text('clear_resumes_button'), help=get_text('clear_resumes_help'), use_container_width=True):
                        st.rerun()
    
    # TAB 2: Excel Processing
    with tab2:
        st.markdown(f"## {get_text('excel_mode_header')}")
        
        # Google Drive Guide
        guide_content = """
        ### 🔗 How to get a public Google Drive link:
        
        #### 📋 Method 1: Direct Link (Recommended)
        1. **Upload your CV to Google Drive**
        2. **Right-click the file → Get link**
        3. **Change access to:** *"Anyone with the link"*
        4. **Permission:** *"Viewer"*
        5. **Click Done**
        
        ---
        
        ℹ️ **Google Drive links will be automatically converted to direct download format.**
        """
        
        with st.expander(get_text('google_drive_guide'), expanded=False):
            st.markdown(guide_content)
        
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
                        
                        cv_count = len(df_preview)
                        if cv_count > 50:
                            st.warning(f"⚠️ File memiliki {cv_count} CV. Akan diproses maksimal 50 CV. / File has {cv_count} CVs. Will process maximum 50 CVs.")
                            st.info("💡 Tip: Pisahkan file Excel menjadi beberapa file dengan maksimal 50 baris per file. / Split Excel file into multiple files with maximum 50 rows each.")
                        else:
                            st.success(f"✅ Ditemukan {cv_count} kandidat dengan link CV valid / Found {cv_count} candidates with valid CV links")
                        
                        st.markdown("---")
                        
                        if st.button(get_text('download_all_cv'), type='primary', use_container_width=True):
                            # PERBAIKAN: Tanpa st.spinner karena sudah ada progress bar di dalam fungsi
                            # Process up to 50 CVs
                            results = process_excel_cv_links(excel_file, role, max_cvs=50)
                            
                            if results:
                                results.sort(key=lambda x: x.get('match_percentage', 0), reverse=True)
                                
                                st.session_state.batch_results = results
                                save_results_to_disk()
                                
                                st.success(get_text('processing_complete'))
                                
                                selected_count = sum(1 for r in results if r['status'] == 'selected')
                                rejected_count = sum(1 for r in results if r['status'] == 'rejected')
                                error_count = sum(1 for r in results if r['status'] == 'error')
                                ocr_count = sum(1 for r in results if r.get('ocr_used', False))
                                
                                summary = f"🌿 {get_text('processing_complete')}\n"
                                summary += f"📊 Total: {len(results)} | ✅ {selected_count} | ❌ {rejected_count} | ⚠️ {error_count}"
                                if ocr_count > 0:
                                    summary += f" | 🔍 OCR: {ocr_count}"
                                
                                st.toast(summary, icon="✅")
                                st.info(f"👉 {get_text('tab_results')} atau {get_text('tab_chatbot')}")
                                
                                # PERBAIKAN: HAPUS st.rerun() untuk menghindari timeout dan crash
                                # User dapat manual pindah ke tab "Hasil & Ringkasan" untuk melihat hasil
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
            st.markdown(f"### 🌿 {get_text('tab_upload')}")
            st.markdown(get_text('batch_info'))
    
    # TAB 4: Chatbot
    with tab4:
        display_chatbot_interface()

    # TAB 5: Role Management
    with tab5:
        display_role_management()
    
    # TAB 6: Data Management
    with tab6:
        display_data_management()



if __name__ == "__main__":
    main()
