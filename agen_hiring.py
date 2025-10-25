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
    # Sidebar & Konfigurasi - TEMA NATURE
    'app_title': {'id': "PT Srikandi Mitra Karya - Sistem Rekrutmen AI", 'en': "PT Srikandi Mitra Karya - AI Recruitment System"},
    'config_header': {'id': "🌿 Konfigurasi", 'en': "🌿 Configuration"},
    'openai_settings': {'id': "Pengaturan OpenAI", 'en': "OpenAI Settings"},
    'api_key_label': {'id': "Kunci API OpenAI", 'en': "OpenAI API Key"},
    'api_key_help': {'id': "Dapatkan kunci API Anda dari platform.openai.com", 'en': "Get your API key from platform.openai.com"},
    'warning_missing_config': {'id': "⚠️ Harap konfigurasikan hal berikut di sidebar: ", 'en': "⚠️ Please configure the following in the sidebar: "},
    'language_select': {'id': "Pilih Bahasa", 'en': "Select Language"},
    'reset_button': {'id': "🔄 Reset Aplikasi", 'en': "🔄 Reset Application"},
    'ocr_settings': {'id': "Pengaturan OCR", 'en': "OCR Settings"},
    'enable_ocr': {'id': "Aktifkan OCR untuk PDF Gambar", 'en': "Enable OCR for Image PDFs"},
    'ocr_help': {'id': "OCR akan memindai PDF berbasis gambar untuk ekstraksi teks yang lebih baik", 'en': "OCR will scan image-based PDFs for better text extraction"},
    
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
    'import_roles_button': {'id': "🌲 Import Posisi (JSON)", 'en': "🌲 Import Posisi (JSON)"},
    'import_roles_success': {'id': "✅ Posisi berhasil diimport!", 'en': "✅ Roles imported successfully!"},
    'import_roles_error': {'id': "❌ Gagal import posisi. Pastikan format JSON benar.", 'en': "❌ Failed to import roles. Ensure JSON format is correct."},
    'storage_info': {'id': "💚 Data disimpan secara otomatis", 'en': "💚 Data saved automatically"},
    'data_loaded': {'id': "✅ Data berhasil dimuat dari penyimpanan", 'en': "✅ Data loaded from storage successfully"},
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
    
    # Hasil & Feedback - TEMA NATURE
    'tab_upload': {'id': "🌿 Unggah & Proses", 'en': "🌿 Upload & Process"},
    'tab_download_excel': {'id': "🌲 Download dari Excel", 'en': "🌲 Download from Excel"},
    'tab_results': {'id': "🌳 Hasil & Ringkasan", 'en': "🌳 Results & Summary"},
    'tab_chatbot': {'id': "💬 Chat dengan AI", 'en': "💬 Chat with AI"},
    'processing_status': {'id': "Memproses", 'en': "Processing"},
    'processing_complete': {'id': "Pemrosesan selesai!", 'en': "Processing complete!"},
    'error_processing': {'id': "⚠️ Kesalahan proses", 'en': "⚠️ Error processing"},
    'error_pdf_text': {'id': "Tidak dapat mengekstrak teks dari PDF", 'en': "Could not extract text from PDF"},
    'error_api_key': {'id': "Kunci API OpenAI hilang atau tidak valid.", 'en': "OpenAI API Key is missing or invalid."},
    'summary_header': {'id': "🌿 Ringkasan Pemrosesan", 'en': "🌿 Processing Summary"},
    'total_processed': {'id': "Total Diproses", 'en': "Total Processed"},
    'selected_label': {'id': "Direkomendasikan ✅", 'en': "Recommended ✅"},
    'rejected_label': {'id': "Tidak direkomendasikan ❌", 'en': "Not Recommended ❌"}, 
    'errors_label': {'id': "Kesalahan ⚠️", 'en': "Errors ⚠️"},
    
    # Chatbot - TEMA NATURE
    'chatbot_header': {'id': "💬 Chat dengan AI Recruiter", 'en': "💬 Chat with AI Recruiter"},
    'chatbot_placeholder': {'id': "Tanyakan tentang kandidat, hasil analisa, atau minta saran rekrutmen...", 'en': "Ask about candidates, analysis results, or request recruitment advice..."},
    'chatbot_help': {'id': "AI dapat membantu Anda memahami hasil analisa dan memberikan rekomendasi", 'en': "AI can help you understand analysis results and provide recommendations"},
    'clear_chat': {'id': "🍂 Hapus Riwayat Chat", 'en': "🍂 Clear Chat History"},
    'chat_cleared': {'id': "✅ Riwayat chat berhasil dihapus", 'en': "✅ Chat history cleared successfully"},
    'no_results_for_chat': {'id': "Belum ada hasil analisa. Proses beberapa resume terlebih dahulu.", 'en': "No analysis results yet. Process some resumes first."},
    
    # Excel Integration
    'upload_excel_label': {'id': "📊 Unggah File Excel dengan Link CV", 'en': "📊 Upload Excel File with CV Links"},
    'excel_uploaded': {'id': "File Excel terunggah", 'en': "Excel file uploaded"},
    'excel_info': {'id': "Format Excel harus memiliki kolom: `Nama` atau `Name`, dan `Link CV` atau `CV Link` atau `URL`", 'en': "Excel format must have columns: `Nama` or `Name`, and `Link CV` or `CV Link` or `URL`"},
    'download_all_cv': {'id': "🌳 Unduh & Proses Semua CV", 'en': "🌳 Download & Process All CVs"},
    'downloading_cv': {'id': "Mengunduh dan memproses CV...", 'en': "Downloading and processing CVs..."},
    'error_download_cv': {'id': "Gagal mengunduh CV dari link", 'en': "Failed to download CV from link"},
    'invalid_excel_format': {'id': "Format Excel tidak valid. Pastikan ada kolom Link CV.", 'en': "Invalid Excel format. Make sure there's a CV Link column."},
    'no_valid_links': {'id': "Tidak ada link CV yang valid ditemukan di file Excel.", 'en': "No valid CV links found in Excel file."},
    'google_drive_guide': {'id': "📘 Panduan Link Google Drive", 'en': "📘 Google Drive Link Guide"},
    
    # Export & Download - TEMA NATURE
    'download_excel_button': {'id': "📥 Download Hasil (Excel)", 'en': "📥 Download Results (Excel)"},
    'download_json_button': {'id': "📥 Download Hasil (JSON)", 'en': "📥 Download Results (JSON)"},
    'no_results_yet': {'id': "Belum ada hasil. Proses beberapa resume terlebih dahulu.", 'en': "No results yet. Process some resumes first."},
    
    # Hasil Detail
    'candidate_name': {'id': "Nama Kandidat", 'en': "Candidate Name"},
    'status': {'id': "Status", 'en': "Status"},
    'match_score': {'id': "Skor Kesesuaian", 'en': "Match Score"},
    'feedback': {'id': "Umpan Balik", 'en': "Feedback"},
    'processed_at': {'id': "Diproses Pada", 'en': "Processed At"},
    'view_details': {'id': "Lihat Detail", 'en': "View Details"},
}

def get_text(key: str) -> str:
    """Mengambil teks berdasarkan bahasa yang dipilih"""
    lang = st.session_state.get('language', 'id')
    return TEXTS.get(key, {}).get(lang, key)


# --- 2. FUNGSI PERSISTENT STORAGE ---

def save_roles_to_disk():
    """Simpan roles ke disk sebagai JSON"""
    try:
        with open(ROLES_FILE, 'w', encoding='utf-8') as f:
            json.dump(st.session_state.roles, f, ensure_ascii=False, indent=2)
        logger.info("Roles saved to disk")
    except Exception as e:
        logger.error(f"Error saving roles: {e}")

def load_roles_from_disk() -> Dict:
    """Load roles dari disk"""
    try:
        if ROLES_FILE.exists():
            with open(ROLES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading roles: {e}")
    return {}

def save_memory_to_disk():
    """Simpan analysis memory ke disk"""
    try:
        with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(st.session_state.analysis_memory, f, ensure_ascii=False, indent=2)
        logger.info("Memory saved to disk")
    except Exception as e:
        logger.error(f"Error saving memory: {e}")

def load_memory_from_disk() -> List[Dict]:
    """Load analysis memory dari disk"""
    try:
        if MEMORY_FILE.exists():
            with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading memory: {e}")
    return []

def save_chat_history_to_disk():
    """Simpan chat history ke disk"""
    try:
        with open(CHAT_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(st.session_state.chat_history, f, ensure_ascii=False, indent=2)
        logger.info("Chat history saved to disk")
    except Exception as e:
        logger.error(f"Error saving chat history: {e}")

def load_chat_history_from_disk() -> List[Dict]:
    """Load chat history dari disk"""
    try:
        if CHAT_HISTORY_FILE.exists():
            with open(CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading chat history: {e}")
    return []

def save_results_to_disk():
    """Simpan batch results ke disk"""
    try:
        with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(st.session_state.batch_results, f, ensure_ascii=False, indent=2)
        logger.info("Results saved to disk")
    except Exception as e:
        logger.error(f"Error saving results: {e}")

def load_results_from_disk() -> List[Dict]:
    """Load batch results dari disk"""
    try:
        if RESULTS_FILE.exists():
            with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading results: {e}")
    return []


# --- 3. FUNGSI UTILITAS ---

def validate_role_id(role_id: str) -> bool:
    """Validasi format role_id"""
    return bool(re.match(r'^[a-z0-9_]+$', role_id))

def load_roles() -> Dict:
    """Load roles dari session state"""
    return st.session_state.get('roles', {})

def save_roles(roles: Dict):
    """Simpan roles ke session state dan disk"""
    st.session_state.roles = roles
    save_roles_to_disk()


# --- 4. FUNGSI EKSTRAKSI PDF ---

def extract_text_from_pdf(pdf_file_or_bytes, use_ocr: bool = False) -> str:
    """
    Ekstrak teks dari PDF file atau bytes.
    Args:
        pdf_file_or_bytes: Bisa berupa file object atau bytes
        use_ocr: Jika True, gunakan OCR untuk PDF berbasis gambar
    """
    try:
        # Handle BytesIO atau bytes
        if isinstance(pdf_file_or_bytes, bytes):
            pdf_bytes = pdf_file_or_bytes
            pdf_file = BytesIO(pdf_bytes)
        else:
            pdf_file = pdf_file_or_bytes
            pdf_bytes = pdf_file.read()
            pdf_file.seek(0)
        
        # Coba ekstraksi teks normal terlebih dahulu
        reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        
        # Jika teks terlalu sedikit dan OCR tersedia, coba OCR
        if (len(text.strip()) < 100 and use_ocr and OCR_AVAILABLE):
            logger.info("Text too short, attempting OCR...")
            try:
                images = convert_from_bytes(pdf_bytes)
                ocr_text = ""
                for i, image in enumerate(images):
                    page_text = pytesseract.image_to_string(image, lang='eng+ind')
                    ocr_text += page_text + "\n"
                
                if len(ocr_text.strip()) > len(text.strip()):
                    text = ocr_text
                    logger.info(f"OCR successful, extracted {len(ocr_text)} characters")
            except Exception as ocr_error:
                logger.warning(f"OCR failed: {ocr_error}")
        
        return text.strip()
    
    except Exception as e:
        logger.error(f"Error extracting PDF text: {e}")
        return ""


# --- 5. FUNGSI ANALISIS AI ---

def create_agent(api_key: str) -> Agent:
    """Buat agent AI untuk analisis resume"""
    model = OpenAIChat(
        id="gpt-4o-mini",
        api_key=api_key
    )
    
    agent = Agent(
        model=model,
        markdown=True,
        show_tool_calls=False,
        add_datetime_to_instructions=True
    )
    
    return agent

def analyze_resume_with_agent(cv_text: str, role: str, candidate_name: str = "Candidate") -> Optional[Dict]:
    """
    Analisis resume menggunakan AI Agent
    
    Returns:
        Dict dengan keys: status, feedback, match_percentage, ocr_used
    """
    api_key = st.session_state.get('openai_api_key')
    if not api_key:
        return None
    
    roles = load_roles()
    requirements = roles.get(role, "")
    
    if not requirements:
        logger.error(f"No requirements found for role: {role}")
        return None
    
    # Deteksi apakah OCR digunakan
    ocr_used = st.session_state.get('enable_ocr', False) and len(cv_text) > 100
    
    prompt = f"""
    Anda adalah AI Recruitment Specialist yang ahli dalam mengevaluasi CV kandidat.
    
    **ROLE/POSISI YANG DIBUTUHKAN**: {role.replace('_', ' ').title()}
    
    **PERSYARATAN & KETERAMPILAN YANG DIBUTUHKAN**:
    {requirements}
    
    **CV KANDIDAT** ({candidate_name}):
    {cv_text[:3000]}  
    
    **INSTRUKSI**:
    1. Evaluasi kesesuaian kandidat dengan posisi dan persyaratan di atas
    2. Berikan skor kesesuaian dalam bentuk persentase (0-100%)
    3. Berikan feedback yang konstruktif dan spesifik
    4. Tentukan apakah kandidat DIREKOMENDASIKAN atau TIDAK DIREKOMENDASIKAN
    
    **FORMAT RESPONS** (WAJIB mengikuti format ini):
    STATUS: [SELECTED atau REJECTED]
    MATCH_SCORE: [angka 0-100]
    FEEDBACK: [feedback detail Anda dalam 3-5 kalimat]
    
    Contoh:
    STATUS: SELECTED
    MATCH_SCORE: 85
    FEEDBACK: Kandidat memiliki pengalaman yang sangat baik dalam pengembangan web dengan Python dan Django. Portfolio menunjukkan proyek-proyek yang relevan. Namun, pengalaman dengan cloud computing masih terbatas. Secara keseluruhan, kandidat ini sangat sesuai untuk posisi ini dan direkomendasikan untuk interview.
    """
    
    try:
        agent = create_agent(api_key)
        response = agent.run(prompt)
        
        if not response or not response.content:
            return None
        
        response_text = response.content
        
        # Parse respons
        status_match = re.search(r'STATUS:\s*(SELECTED|REJECTED)', response_text, re.IGNORECASE)
        score_match = re.search(r'MATCH_SCORE:\s*(\d+)', response_text)
        feedback_match = re.search(r'FEEDBACK:\s*(.+?)(?=\n\n|\Z)', response_text, re.DOTALL)
        
        status = status_match.group(1).lower() if status_match else 'rejected'
        match_percentage = int(score_match.group(1)) if score_match else 0
        feedback = feedback_match.group(1).strip() if feedback_match else response_text
        
        # Simpan ke memory
        memory_entry = {
            'candidate_name': candidate_name,
            'role': role,
            'status': status,
            'match_percentage': match_percentage,
            'feedback': feedback,
            'timestamp': datetime.now().isoformat(),
            'ocr_used': ocr_used
        }
        
        if 'analysis_memory' not in st.session_state:
            st.session_state.analysis_memory = []
        
        st.session_state.analysis_memory.append(memory_entry)
        save_memory_to_disk()
        
        return {
            'status': status,
            'feedback': feedback,
            'match_percentage': match_percentage,
            'ocr_used': ocr_used
        }
    
    except Exception as e:
        logger.error(f"Error in AI analysis: {e}")
        return None


# --- 6. FUNGSI CHAT AI ---

def chat_with_ai(user_message: str) -> str:
    """
    Chat dengan AI tentang hasil rekrutmen
    """
    api_key = st.session_state.get('openai_api_key')
    if not api_key:
        return get_text('error_api_key')
    
    # Ambil context dari hasil analisa
    results = st.session_state.get('batch_results', [])
    memory = st.session_state.get('analysis_memory', [])
    
    context = "**DATA KANDIDAT YANG SUDAH DIANALISA:**\n\n"
    
    if results:
        for idx, result in enumerate(results, 1):
            context += f"{idx}. {result.get('name', 'Unknown')}\n"
            context += f"   - Status: {result.get('status', 'unknown').upper()}\n"
            context += f"   - Match Score: {result.get('match_percentage', 0)}%\n"
            context += f"   - Feedback: {result.get('feedback', 'N/A')[:200]}\n\n"
    else:
        context += "Belum ada kandidat yang dianalisa.\n\n"
    
    prompt = f"""
    Anda adalah AI Recruitment Assistant yang membantu HR dalam proses rekrutmen.
    
    {context}
    
    **PERTANYAAN USER**: {user_message}
    
    **INSTRUKSI**:
    - Jawab pertanyaan user dengan profesional dan informatif
    - Gunakan data kandidat di atas sebagai referensi
    - Berikan insight dan rekomendasi yang berguna
    - Jika ditanya tentang kandidat tertentu, berikan detail yang spesifik
    - Jika tidak ada data yang relevan, jelaskan dengan sopan
    
    Jawab dalam bahasa yang sama dengan pertanyaan user.
    """
    
    try:
        agent = create_agent(api_key)
        response = agent.run(prompt)
        
        if response and response.content:
            return response.content
        else:
            return "Maaf, saya tidak dapat memproses pertanyaan Anda saat ini."
    
    except Exception as e:
        logger.error(f"Error in chat: {e}")
        return f"Terjadi kesalahan: {str(e)}"


# --- 7. FUNGSI DOWNLOAD & EXCEL INTEGRATION ---

def convert_google_drive_link(url: str) -> str:
    """
    Konversi Google Drive share link ke direct download link
    """
    if 'drive.google.com' in url:
        # Extract file ID
        file_id_match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
        if file_id_match:
            file_id = file_id_match.group(1)
            return f"https://drive.google.com/uc?export=download&id={file_id}"
    return url

def download_pdf_from_url(url: str, timeout: int = 30) -> Optional[bytes]:
    """
    Download PDF dari URL
    Support: Direct link, Google Drive, Dropbox, dll
    """
    try:
        # Konversi Google Drive link jika perlu
        url = convert_google_drive_link(url)
        
        # Untuk Dropbox, ubah dl=0 menjadi dl=1
        if 'dropbox.com' in url:
            url = url.replace('dl=0', 'dl=1')
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        
        # Cek apakah response adalah PDF
        content_type = response.headers.get('Content-Type', '')
        if 'pdf' not in content_type.lower() and not url.endswith('.pdf'):
            # Cek magic number untuk PDF
            if not response.content.startswith(b'%PDF'):
                logger.warning(f"URL does not seem to be a PDF: {url}")
                return None
        
        return response.content
    
    except requests.exceptions.Timeout:
        logger.error(f"Timeout downloading from {url}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading from {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error downloading from {url}: {e}")
        return None

def read_excel_with_cv_links(excel_file) -> Optional[pd.DataFrame]:
    """
    Baca Excel file dan ekstrak nama kandidat & link CV
    
    Expected columns:
    - 'Nama' atau 'Name' atau 'Candidate Name'
    - 'Link CV' atau 'CV Link' atau 'URL' atau 'Link'
    """
    try:
        df = pd.read_excel(excel_file)
        
        # Normalisasi nama kolom
        df.columns = df.columns.str.strip()
        
        # Cari kolom nama
        name_col = None
        for col in df.columns:
            if any(keyword in col.lower() for keyword in ['nama', 'name', 'candidate']):
                name_col = col
                break
        
        # Cari kolom link
        link_col = None
        for col in df.columns:
            if any(keyword in col.lower() for keyword in ['link', 'url', 'cv']):
                link_col = col
                break
        
        if not name_col or not link_col:
            logger.error(f"Required columns not found. Available: {df.columns.tolist()}")
            return None
        
        # Filter baris yang memiliki link
        df_filtered = df[[name_col, link_col]].copy()
        df_filtered.columns = ['candidate_name', 'cv_link']
        df_filtered = df_filtered.dropna(subset=['cv_link'])
        df_filtered = df_filtered[df_filtered['cv_link'].str.strip() != '']
        
        # Fill missing names
        df_filtered['candidate_name'] = df_filtered['candidate_name'].fillna('Unknown')
        
        return df_filtered
    
    except Exception as e:
        logger.error(f"Error reading Excel: {e}")
        return None

def process_excel_cv_links(excel_file, role: str, max_cvs: int = 50) -> List[Dict]:
    """
    Download dan process CV dari Excel yang berisi link
    PERBAIKAN: Improved error handling dan progress tracking
    """
    results = []
    progress_bar = None
    status_text = None
    
    try:
        df = read_excel_with_cv_links(excel_file)
        
        if df is None or df.empty:
            st.error(get_text('invalid_excel_format'))
            return results
        
        # Batasi jumlah CV yang diproses
        df = df.head(max_cvs)
        
        # Buat progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        total = len(df)
        
        for idx, row in df.iterrows():
            try:
                candidate_name = row.get('candidate_name', f"Kandidat {idx+1}")
                cv_link = row.get('cv_link', '')
                
                if not cv_link:
                    continue
                
                # Update progress
                progress = (idx + 1) / total
                progress_bar.progress(progress)
                status_text.text(f"{get_text('processing_status')} {idx+1}/{total}: {candidate_name}")
                
                # Download PDF
                pdf_content = download_pdf_from_url(cv_link)
                
                if not pdf_content:
                    results.append({
                        'name': candidate_name,
                        'status': 'error',
                        'feedback': get_text('error_download_cv'),
                        'match_percentage': 0,
                        'cv_link': cv_link,
                        'timestamp': datetime.now().isoformat()
                    })
                    continue
                
                # Extract text dari PDF
                use_ocr = st.session_state.get('enable_ocr', False)
                cv_text = extract_text_from_pdf(pdf_content, use_ocr=use_ocr)
                
                if not cv_text or len(cv_text.strip()) < 100:
                    results.append({
                        'name': candidate_name,
                        'status': 'error',
                        'feedback': get_text('error_pdf_text'),
                        'match_percentage': 0,
                        'cv_link': cv_link,
                        'ocr_used': False,
                        'timestamp': datetime.now().isoformat()
                    })
                    continue
                
                # Analisis CV dengan AI
                analysis = analyze_resume_with_agent(cv_text, role, candidate_name)
                
                if analysis:
                    result = {
                        'name': candidate_name,
                        'status': analysis['status'],
                        'feedback': analysis['feedback'],
                        'match_percentage': analysis.get('match_percentage', 0),
                        'cv_link': cv_link,
                        'ocr_used': analysis.get('ocr_used', False),
                        'timestamp': datetime.now().isoformat()
                    }
                    results.append(result)
                else:
                    results.append({
                        'name': candidate_name,
                        'status': 'error',
                        'feedback': get_text('error_processing'),
                        'match_percentage': 0,
                        'cv_link': cv_link,
                        'timestamp': datetime.now().isoformat()
                    })
            
            except Exception as e:
                logger.error(f"Error processing {candidate_name}: {e}")
                results.append({
                    'name': candidate_name,
                    'status': 'error',
                    'feedback': f"{get_text('error_processing')}: {str(e)}",
                    'match_percentage': 0,
                    'cv_link': cv_link if 'cv_link' in locals() else '',
                    'timestamp': datetime.now().isoformat()
                })
        
    except Exception as e:
        logger.error(f"Fatal error in process_excel_cv_links: {e}")
        st.error(f"Error: {str(e)}")
    
    finally:
        # PERBAIKAN: Pastikan progress bar dan status text selalu dibersihkan
        if progress_bar is not None:
            progress_bar.empty()
        if status_text is not None:
            status_text.empty()
    
    return results


# --- 8. FUNGSI TAMPILAN ---

def display_results_table(results: List[Dict], language: str = 'id'):
    """Tampilkan hasil dalam bentuk tabel interaktif"""
    if not results:
        st.info(get_text('no_results_yet'))
        return
    
    st.markdown(f"### {get_text('summary_header')}")
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    total = len(results)
    selected = sum(1 for r in results if r['status'] == 'selected')
    rejected = sum(1 for r in results if r['status'] == 'rejected')
    errors = sum(1 for r in results if r['status'] == 'error')
    
    col1.metric(get_text('total_processed'), total)
    col2.metric(get_text('selected_label'), selected)
    col3.metric(get_text('rejected_label'), rejected)
    col4.metric(get_text('errors_label'), errors)
    
    st.markdown("---")
    
    # Tabel hasil
    df_results = pd.DataFrame([
        {
            get_text('candidate_name'): r['name'],
            get_text('status'): "✅ " + get_text('selected_label') if r['status'] == 'selected' 
                              else "❌ " + get_text('rejected_label') if r['status'] == 'rejected'
                              else "⚠️ " + get_text('errors_label'),
            get_text('match_score'): f"{r.get('match_percentage', 0)}%",
            get_text('feedback'): r.get('feedback', '')[:200] + "..." if len(r.get('feedback', '')) > 200 else r.get('feedback', ''),
            get_text('processed_at'): r.get('timestamp', '')[:19]
        }
        for r in results
    ])
    
    st.dataframe(
        df_results,
        use_container_width=True,
        hide_index=True
    )
    
    # Download buttons
    col1, col2 = st.columns(2)
    
    with col1:
        if PANDAS_AVAILABLE:
            # Export ke Excel
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_results.to_excel(writer, index=False, sheet_name='Results')
            
            st.download_button(
                label=get_text('download_excel_button'),
                data=buffer.getvalue(),
                file_name=f"recruitment_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
    
    with col2:
        # Export ke JSON
        json_str = json.dumps(results, ensure_ascii=False, indent=2)
        st.download_button(
            label=get_text('download_json_button'),
            data=json_str,
            file_name=f"recruitment_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True
        )

def display_chatbot_interface():
    """Tampilkan interface chatbot"""
    st.markdown(f"### {get_text('chatbot_header')}")
    
    results = st.session_state.get('batch_results', [])
    
    if not results:
        st.info(get_text('no_results_for_chat'))
        return
    
    st.markdown(get_text('chatbot_help'))
    st.markdown("---")
    
    # Chat history
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    
    # Display chat messages
    for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input(get_text('chatbot_placeholder')):
        # Add user message
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Get AI response
        with st.chat_message("assistant"):
            with st.spinner("🤔 Berpikir..."):
                response = chat_with_ai(prompt)
                st.markdown(response)
        
        # Add assistant message
        st.session_state.chat_history.append({"role": "assistant", "content": response})
        save_chat_history_to_disk()
    
    # Clear chat button
    if st.session_state.chat_history:
        if st.button(get_text('clear_chat'), use_container_width=True):
            st.session_state.chat_history = []
            save_chat_history_to_disk()
            st.success(get_text('chat_cleared'))
            st.rerun()

def display_role_management():
    """Tampilkan interface manajemen posisi"""
    st.markdown(f"### {get_text('tab_manage_roles')}")
    
    roles = load_roles()
    
    tab1, tab2 = st.tabs([get_text('add_role_header'), get_text('edit_role_header')])
    
    # Tab 1: Add Role
    with tab1:
        st.markdown(f"#### {get_text('add_role_header')}")
        
        with st.form("add_role_form"):
            role_id = st.text_input(
                get_text('role_id_label'),
                help=get_text('role_id_help'),
                placeholder="contoh: senior_developer"
            )
            
            role_name = st.text_input(
                get_text('role_name_label'),
                placeholder="contoh: Senior Developer"
            )
            
            requirements = st.text_area(
                get_text('required_skills_label'),
                height=200,
                help=get_text('required_skills_help'),
                placeholder="""Contoh:
- Minimal 5 tahun pengalaman sebagai developer
- Menguasai Python, JavaScript, React
- Pengalaman dengan cloud (AWS/GCP)
- Kemampuan leadership dan mentoring"""
            )
            
            submitted = st.form_submit_button(get_text('add_role_button'), use_container_width=True)
            
            if submitted:
                if not role_id or not role_name or not requirements:
                    st.error("❌ Semua field harus diisi!")
                elif not validate_role_id(role_id):
                    st.error(get_text('role_id_invalid'))
                elif role_id in roles:
                    st.error(get_text('role_exists_error'))
                else:
                    roles[role_id] = requirements
                    save_roles(roles)
                    st.success(get_text('role_added_success'))
                    st.rerun()
    
    # Tab 2: Edit/Delete Role
    with tab2:
        if not roles:
            st.info(get_text('no_roles_available'))
        else:
            st.markdown(f"#### {get_text('edit_role_header')}")
            
            selected_role = st.selectbox(
                get_text('select_role_to_edit'),
                list(roles.keys()),
                format_func=lambda x: x.replace('_', ' ').title()
            )
            
            if selected_role:
                with st.form("edit_role_form"):
                    new_requirements = st.text_area(
                        get_text('required_skills_label'),
                        value=roles[selected_role],
                        height=200
                    )
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        update_button = st.form_submit_button(
                            get_text('update_role_button'),
                            use_container_width=True
                        )
                    
                    with col2:
                        delete_button = st.form_submit_button(
                            get_text('delete_role_button'),
                            use_container_width=True,
                            type="secondary"
                        )
                    
                    if update_button:
                        if new_requirements.strip():
                            roles[selected_role] = new_requirements
                            save_roles(roles)
                            st.success(get_text('role_updated_success'))
                            st.rerun()
                        else:
                            st.error("❌ Persyaratan tidak boleh kosong!")
                    
                    if delete_button:
                        del roles[selected_role]
                        save_roles(roles)
                        st.success(get_text('role_deleted_success'))
                        st.rerun()
    
    # Display current roles
    if roles:
        st.markdown("---")
        st.markdown(f"### {get_text('current_roles_header')}")
        
        for role_id, requirements in roles.items():
            with st.expander(f"📋 {role_id.replace('_', ' ').title()}"):
                st.markdown(requirements)
        
        # Export/Import
        col1, col2 = st.columns(2)
        
        with col1:
            roles_json = json.dumps(roles, ensure_ascii=False, indent=2)
            st.download_button(
                label=get_text('export_roles_button'),
                data=roles_json,
                file_name="roles_export.json",
                mime="application/json",
                use_container_width=True
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
                    st.error(get_text('import_roles_error'))
                    logger.error(f"Import error: {e}")

def display_data_management():
    """Tampilkan interface manajemen data"""
    st.markdown(f"### {get_text('tab_data_management')}")
    
    st.markdown("---")
    
    # Clear history & results
    st.markdown("#### 🍂 " + get_text('clear_all_data'))
    st.markdown(get_text('confirm_clear_data'))
    
    if st.button(get_text('clear_all_data'), type="secondary", use_container_width=True):
        st.session_state.chat_history = []
        st.session_state.batch_results = []
        st.session_state.analysis_memory = []
        
        save_chat_history_to_disk()
        save_results_to_disk()
        save_memory_to_disk()
        
        st.success(get_text('all_data_cleared'))
        st.rerun()
    
    st.markdown("---")
    
    # Export/Import All Data
    st.markdown("#### 🌳 " + get_text('export_all_data'))
    
    all_data = {
        'roles': st.session_state.get('roles', {}),
        'analysis_memory': st.session_state.get('analysis_memory', []),
        'chat_history': st.session_state.get('chat_history', []),
        'batch_results': st.session_state.get('batch_results', []),
        'export_date': datetime.now().isoformat()
    }
    
    backup_json = json.dumps(all_data, ensure_ascii=False, indent=2)
    
    st.download_button(
        label=get_text('export_all_data'),
        data=backup_json,
        file_name=f"recruitment_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json",
        use_container_width=True
    )
    
    st.markdown("---")
    st.markdown("#### 🌲 " + get_text('import_all_data'))
    
    uploaded_backup = st.file_uploader(
        get_text('import_all_data'),
        type=['json'],
        key='import_backup'
    )
    
    if uploaded_backup:
        try:
            backup_data = json.load(uploaded_backup)
            
            # Restore data
            if 'roles' in backup_data:
                st.session_state.roles = backup_data['roles']
                save_roles_to_disk()
            
            if 'analysis_memory' in backup_data:
                st.session_state.analysis_memory = backup_data['analysis_memory']
                save_memory_to_disk()
            
            if 'chat_history' in backup_data:
                st.session_state.chat_history = backup_data['chat_history']
                save_chat_history_to_disk()
            
            if 'batch_results' in backup_data:
                st.session_state.batch_results = backup_data['batch_results']
                save_results_to_disk()
            
            st.success(get_text('restore_success'))
            st.rerun()
        except Exception as e:
            st.error(f"Error importing backup: {str(e)}")
            logger.error(f"Backup import error: {e}")


# --- 9. FUNGSI UTAMA ---

def initialize_session_state():
    """Inisialisasi session state dengan data dari disk"""
    if 'initialized' not in st.session_state:
        # Load dari disk
        st.session_state.roles = load_roles_from_disk()
        st.session_state.analysis_memory = load_memory_from_disk()
        st.session_state.chat_history = load_chat_history_from_disk()
        st.session_state.batch_results = load_results_from_disk()
        
        # Default values
        if 'language' not in st.session_state:
            st.session_state.language = 'id'
        
        if 'enable_ocr' not in st.session_state:
            st.session_state.enable_ocr = False
        
        st.session_state.initialized = True
        
        logger.info("Session state initialized from disk")

def main():
    """Fungsi utama aplikasi"""
    
    # Page config
    st.set_page_config(
        page_title="PT Srikandi Mitra Karya - AI Recruitment",
        page_icon="🌿",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize session state
    initialize_session_state()
    
    # Sidebar
    with st.sidebar:
        st.markdown(f"## {get_text('config_header')}")
        
        # Language selector
        language = st.selectbox(
            get_text('language_select'),
            ['id', 'en'],
            format_func=lambda x: "🇮🇩 Bahasa Indonesia" if x == 'id' else "🇬🇧 English",
            key='language'
        )
        
        st.markdown("---")
        
        # OpenAI Settings
        st.markdown(f"### {get_text('openai_settings')}")
        
        api_key = st.text_input(
            get_text('api_key_label'),
            type="password",
            help=get_text('api_key_help'),
            key='openai_api_key'
        )
        
        st.markdown("---")
        
        # OCR Settings
        if OCR_AVAILABLE:
            st.markdown(f"### {get_text('ocr_settings')}")
            st.checkbox(
                get_text('enable_ocr'),
                help=get_text('ocr_help'),
                key='enable_ocr'
            )
            st.markdown("---")
        
        # Storage info
        st.info(get_text('storage_info'))
    
    # Main area
    st.title(get_text('app_title'))
    
    # Check configuration
    if not st.session_state.get('openai_api_key'):
        st.warning(get_text('warning_missing_config') + "OpenAI API Key")
        return
    
    # Tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        get_text('tab_upload'),
        get_text('tab_download_excel'),
        get_text('tab_results'),
        get_text('tab_chatbot'),
        get_text('tab_manage_roles'),
        get_text('tab_data_management')
    ])
    
    # TAB 1: Upload & Process
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
            st.markdown(get_text('batch_info'))
            
            uploaded_files = st.file_uploader(
                get_text('upload_resume_label'),
                type=['pdf'],
                accept_multiple_files=True,
                key='batch_uploader'
            )
            
            if uploaded_files:
                st.success(f"{len(uploaded_files)} {get_text('resumes_uploaded')}")
                
                col1, col2 = st.columns([3, 1])
                with col2:
                    if st.button(get_text('clear_resumes_button'), help=get_text('clear_resumes_help')):
                        st.rerun()
                
                if st.button(get_text('process_all_button'), type='primary', use_container_width=True):
                    results = []
                    
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    for idx, uploaded_file in enumerate(uploaded_files):
                        progress = (idx + 1) / len(uploaded_files)
                        progress_bar.progress(progress)
                        status_text.text(f"{get_text('processing_status')} {idx+1}/{len(uploaded_files)}: {uploaded_file.name}")
                        
                        # Extract text
                        use_ocr = st.session_state.get('enable_ocr', False)
                        cv_text = extract_text_from_pdf(uploaded_file, use_ocr=use_ocr)
                        
                        if not cv_text or len(cv_text.strip()) < 100:
                            results.append({
                                'name': uploaded_file.name,
                                'status': 'error',
                                'feedback': get_text('error_pdf_text'),
                                'match_percentage': 0,
                                'timestamp': datetime.now().isoformat()
                            })
                            continue
                        
                        # Analyze
                        analysis = analyze_resume_with_agent(cv_text, role, uploaded_file.name)
                        
                        if analysis:
                            result = {
                                'name': uploaded_file.name,
                                'status': analysis['status'],
                                'feedback': analysis['feedback'],
                                'match_percentage': analysis.get('match_percentage', 0),
                                'ocr_used': analysis.get('ocr_used', False),
                                'timestamp': datetime.now().isoformat()
                            }
                            results.append(result)
                        else:
                            results.append({
                                'name': uploaded_file.name,
                                'status': 'error',
                                'feedback': get_text('error_processing'),
                                'match_percentage': 0,
                                'timestamp': datetime.now().isoformat()
                            })
                    
                    progress_bar.empty()
                    status_text.empty()
                    
                    # Sort by match percentage
                    results.sort(key=lambda x: x.get('match_percentage', 0), reverse=True)
                    
                    # Save to session state
                    st.session_state.batch_results = results
                    save_results_to_disk()
                    
                    st.success(get_text('processing_complete'))
                    st.info(f"👉 {get_text('tab_results')} atau {get_text('tab_chatbot')}")
    
    # TAB 2: Download from Excel
    with tab2:
        st.markdown(f"### {get_text('tab_download_excel')}")
        st.markdown(get_text('excel_info'))
        
        # Panduan Google Drive
        guide_content = f"""
        **{get_text('google_drive_guide')}**
        
        Untuk membagikan file dari Google Drive:
        
        1. **Buka file di Google Drive** → Klik kanan → "Get link" / "Dapatkan link"
        2. **Ubah akses** → Pilih "Anyone with the link" / "Siapa saja yang memiliki link"
        3. **Copy link** → Format: `https://drive.google.com/file/d/FILE_ID/view`
        
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
                            # PERBAIKAN: Tanpa st.spinner agar tidak bentrok dengan progress bar internal
                            try:
                                # Process up to 50 CVs
                                results = process_excel_cv_links(excel_file, role, max_cvs=50)
                                
                                if results:
                                    # Sort results by match percentage
                                    results.sort(key=lambda x: x.get('match_percentage', 0), reverse=True)
                                    
                                    # Save to session state and disk
                                    st.session_state.batch_results = results
                                    save_results_to_disk()
                                    
                                    # Show success message
                                    st.success(get_text('processing_complete'))
                                    
                                    # Show summary
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
                                    
                                    # PERBAIKAN: Rerun untuk memastikan hasil ditampilkan
                                    time.sleep(1)  # Brief pause untuk memastikan toast terlihat
                                    st.rerun()
                                else:
                                    st.error(get_text('no_valid_links'))
                            
                            except Exception as e:
                                st.error(f"Error processing CVs: {str(e)}")
                                logger.error(f"Processing error: {e}")
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
