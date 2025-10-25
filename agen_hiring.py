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
CACHE_FILE = DATA_DIR / "analysis_cache.json"  # NEW: Cache untuk hasil analisa

# Buat direktori jika belum ada
DATA_DIR.mkdir(exist_ok=True)

# --- KONFIGURASI BATCH PROCESSING ---
MAX_BATCH_SIZE = 50  # Maksimal file yang bisa diproses sekaligus
CONCURRENT_REQUESTS = 3  # Jumlah request paralel ke OpenAI
REQUEST_TIMEOUT = 60  # Timeout per request dalam detik


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
    'import_roles_button': {'id': "🌲 Import Posisi (JSON)", 'en': "🌲 Import Roles (JSON)"},
    'import_roles_success': {'id': "✅ Posisi berhasil diimport!", 'en': "✅ Roles imported successfully!"},
    'import_roles_error': {'id': "❌ Gagal import posisi. Pastikan format JSON benar.", 'en': "❌ Failed to import roles. Ensure JSON format is correct."},
    'storage_info': {'id': "💚 Data disimpan secara otomatis", 'en': "💚 Data saved automatically"},
    'data_loaded': {'id': "✅ Data berhasil dimuat dari penyimpanan", 'en': "✅ Data loaded from storage successfully"},
    'clear_all_data': {'id': "🍂 Hapus Semua Data", 'en': "🍂 Clear All Data"},
    'confirm_clear_data': {'id': "Apakah Anda yakin ingin menghapus SEMUA data termasuk posisi, hasil analisa, dan history chat?", 'en': "Are you sure you want to delete ALL data including roles, analysis results, and chat history?"},
    'all_data_cleared': {'id': "✅ Semua data berhasil dihapus", 'en': "✅ All data cleared successfully"},
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
    'batch_info': {'id': f"🌿 Unggah hingga {MAX_BATCH_SIZE} resume (PDF) untuk diproses secara otomatis.", 'en': f"🌿 Upload up to {MAX_BATCH_SIZE} resumes (PDF) to process them automatically."},
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
    'processing_complete': {'id': "✅ Pemrosesan selesai!", 'en': "✅ Processing complete!"},
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
    'chat_cleared': {'id': "✅ Riwayat chat berhasil dihapus", 'en': "✅ Chat history cleared"},
    
    # Excel Download - TEMA NATURE
    'upload_excel_label': {'id': "📊 Upload File Excel dengan Link CV", 'en': "📊 Upload Excel File with CV Links"},
    'upload_excel_help': {'id': "File Excel harus berisi kolom 'Link CV' atau 'CV Link'", 'en': "Excel file must contain 'Link CV' or 'CV Link' column"},
    'download_all_cv': {'id': "🌳 Download & Proses Semua CV", 'en': "🌳 Download & Process All CVs"},
    'downloading_cv': {'id': "Mengunduh dan memproses CV...", 'en': "Downloading and processing CVs..."},
    'excel_uploaded': {'id': "File Excel terunggah", 'en': "Excel file uploaded"},
    'no_valid_links': {'id': "❌ Tidak ditemukan link CV yang valid", 'en': "❌ No valid CV links found"},
    'invalid_excel_format': {'id': "❌ Format Excel tidak valid. Pastikan ada kolom 'Link CV' atau 'CV Link'", 'en': "❌ Invalid Excel format. Make sure there is a 'Link CV' or 'CV Link' column"},
    'google_drive_guide': {'id': "📘 Panduan Google Drive/Form", 'en': "📘 Google Drive/Form Guide"},
    'no_results_yet': {'id': "Belum ada hasil pemrosesan. Unggah resume terlebih dahulu.", 'en': "No processing results yet. Upload resumes first."},
    'export_excel_button': {'id': "📥 Export ke Excel", 'en': "📥 Export to Excel"},
    'export_json_button': {'id': "📥 Export ke JSON", 'en': "📥 Export to JSON"},
}


def get_text(key: str) -> str:
    """Helper untuk mendapatkan teks berdasarkan bahasa yang dipilih"""
    lang = st.session_state.get('language', 'id')
    return TEXTS.get(key, {}).get(lang, key)


# --- 2. FUNGSI PERSISTENT STORAGE ---

def load_roles() -> dict:
    """Load roles dari file JSON"""
    if ROLES_FILE.exists():
        try:
            with open(ROLES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading roles: {e}")
            return {}
    return {}


def save_roles(roles: dict):
    """Simpan roles ke file JSON"""
    try:
        with open(ROLES_FILE, 'w', encoding='utf-8') as f:
            json.dump(roles, f, indent=2, ensure_ascii=False)
        logger.info("Roles saved successfully")
    except Exception as e:
        logger.error(f"Error saving roles: {e}")


def load_memory() -> list:
    """Load analysis memory dari file JSON"""
    if MEMORY_FILE.exists():
        try:
            with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading memory: {e}")
            return []
    return []


def save_memory(memory: list):
    """Simpan analysis memory ke file JSON"""
    try:
        with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(memory, f, indent=2, ensure_ascii=False)
        logger.info("Memory saved successfully")
    except Exception as e:
        logger.error(f"Error saving memory: {e}")


def load_chat_history() -> list:
    """Load chat history dari file JSON"""
    if CHAT_HISTORY_FILE.exists():
        try:
            with open(CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading chat history: {e}")
            return []
    return []


def save_chat_history(history: list):
    """Simpan chat history ke file JSON"""
    try:
        with open(CHAT_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        logger.info("Chat history saved successfully")
    except Exception as e:
        logger.error(f"Error saving chat history: {e}")


def load_results_from_disk() -> list:
    """Load batch results dari file JSON"""
    if RESULTS_FILE.exists():
        try:
            with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading results: {e}")
            return []
    return []


def save_results_to_disk():
    """Simpan batch results ke file JSON"""
    try:
        with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(st.session_state.batch_results, f, indent=2, ensure_ascii=False)
        logger.info("Results saved successfully")
    except Exception as e:
        logger.error(f"Error saving results: {e}")


def load_analysis_cache() -> dict:
    """Load cache hasil analisa dari file JSON"""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading cache: {e}")
            return {}
    return {}


def save_analysis_cache(cache: dict):
    """Simpan cache hasil analisa ke file JSON"""
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
        logger.info("Cache saved successfully")
    except Exception as e:
        logger.error(f"Error saving cache: {e}")


def clear_all_data():
    """Hapus semua data termasuk roles, memory, chat history, results, dan cache"""
    try:
        # Delete files
        deleted_count = 0
        for file in [ROLES_FILE, MEMORY_FILE, CHAT_HISTORY_FILE, RESULTS_FILE, CACHE_FILE]:
            if file.exists():
                file.unlink()
                deleted_count += 1
                logger.info(f"Deleted: {file.name}")
        
        # Reset session state
        if 'batch_results' in st.session_state:
            st.session_state.batch_results = []
        if 'chat_messages' in st.session_state:
            st.session_state.chat_messages = []
        if 'analysis_memory' in st.session_state:
            st.session_state.analysis_memory = []
        if 'analysis_cache' in st.session_state:
            st.session_state.analysis_cache = {}
        
        logger.info(f"All data cleared successfully. Deleted {deleted_count} files")
        return True
    except Exception as e:
        logger.error(f"Error clearing data: {e}")
        return False


# --- 3. FUNGSI EKSTRAKSI PDF DENGAN OCR YANG LEBIH BAIK ---

def extract_text_from_pdf(pdf_file, use_ocr: bool = False) -> Tuple[str, bool]:
    """
    Ekstraksi teks dari PDF dengan OCR fallback yang lebih baik
    
    Args:
        pdf_file: File PDF (bytes atau file object)
        use_ocr: Apakah menggunakan OCR secara paksa
    
    Returns:
        Tuple[str, bool]: (teks yang diekstrak, apakah OCR digunakan)
    """
    ocr_used = False
    
    try:
        # Jika pdf_file adalah bytes, bungkus dengan BytesIO
        if isinstance(pdf_file, bytes):
            pdf_bytes = pdf_file
            pdf_file = BytesIO(pdf_bytes)
        else:
            pdf_file.seek(0)
            pdf_bytes = pdf_file.read()
            pdf_file.seek(0)
        
        # Coba ekstraksi teks normal terlebih dahulu
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        
        # Jika teks terlalu pendek atau OCR dipaksa, gunakan OCR
        if (len(text.strip()) < 100 or use_ocr) and OCR_AVAILABLE:
            logger.info("Using OCR for better text extraction")
            try:
                # Konversi PDF ke gambar
                images = convert_from_bytes(pdf_bytes, dpi=300)
                ocr_text = ""
                
                for i, image in enumerate(images):
                    # Ekstraksi teks dari gambar menggunakan Tesseract
                    page_text = pytesseract.image_to_string(image, lang='eng+ind')
                    ocr_text += page_text + "\n"
                
                # Gunakan OCR text jika lebih panjang
                if len(ocr_text.strip()) > len(text.strip()):
                    text = ocr_text
                    ocr_used = True
                    logger.info("OCR provided better results")
            except Exception as ocr_error:
                logger.warning(f"OCR failed: {ocr_error}")
        
        return text.strip(), ocr_used
    
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        return "", False


# --- 4. FUNGSI SKILL MATCHING ENGINE (BARU) ---

def parse_skills_from_requirement(requirement_text: str) -> List[str]:
    """
    Parse skill requirement menjadi list skill individual
    
    Args:
        requirement_text: Teks requirement dari user
    
    Returns:
        List[str]: List skill yang di-parse
    """
    # Split berdasarkan newline, bullet points, atau comma
    lines = re.split(r'[\n\r]+|[;]', requirement_text)
    skills = []
    
    for line in lines:
        # Hilangkan bullet points dan whitespace
        clean_line = re.sub(r'^[\s\-\*\•\d\.)]+', '', line).strip()
        
        # Split jika ada comma
        if ',' in clean_line:
            sub_skills = [s.strip() for s in clean_line.split(',') if s.strip()]
            skills.extend(sub_skills)
        elif clean_line:
            skills.append(clean_line)
    
    # Filter empty strings dan duplikat
    skills = list(set([s for s in skills if s and len(s) > 2]))
    
    return skills


def calculate_skill_match_score(cv_text: str, required_skills: List[str]) -> Tuple[float, List[Dict]]:
    """
    Hitung skor matching berdasarkan skill yang ditemukan di CV
    
    Args:
        cv_text: Teks dari CV kandidat
        required_skills: List skill yang dibutuhkan
    
    Returns:
        Tuple[float, List[Dict]]: (persentase match, detail skill matching)
    """
    cv_text_lower = cv_text.lower()
    matched_skills = []
    
    for skill in required_skills:
        skill_lower = skill.lower()
        
        # Cek apakah skill ada di CV (dengan fuzzy matching)
        if skill_lower in cv_text_lower:
            matched_skills.append({
                'skill': skill,
                'matched': True,
                'confidence': 'exact'
            })
        else:
            # Fuzzy matching - cek kata-kata dalam skill
            skill_words = set(skill_lower.split())
            cv_words = set(cv_text_lower.split())
            
            # Jika > 50% kata dalam skill ditemukan di CV
            common_words = skill_words.intersection(cv_words)
            if len(common_words) >= len(skill_words) * 0.5:
                matched_skills.append({
                    'skill': skill,
                    'matched': True,
                    'confidence': 'partial'
                })
            else:
                matched_skills.append({
                    'skill': skill,
                    'matched': False,
                    'confidence': 'none'
                })
    
    # Hitung persentase
    if not required_skills:
        return 0.0, []
    
    fully_matched = len([s for s in matched_skills if s['matched'] and s['confidence'] == 'exact'])
    partially_matched = len([s for s in matched_skills if s['matched'] and s['confidence'] == 'partial'])
    
    # Bobot: exact match = 1.0, partial match = 0.5
    score = ((fully_matched * 1.0) + (partially_matched * 0.5)) / len(required_skills) * 100
    
    return round(score, 2), matched_skills


# --- 5. FUNGSI ANALISA RESUME YANG DIPERBAIKI ---

def create_structured_prompt(role: str, requirements: str, cv_text: str, skill_matching_data: dict) -> str:
    """
    Buat prompt terstruktur untuk AI dengan instruksi yang jelas dan konsisten
    
    Args:
        role: Nama posisi
        requirements: Requirement posisi
        cv_text: Teks CV kandidat
        skill_matching_data: Data hasil skill matching
    
    Returns:
        str: Prompt terstruktur untuk AI
    """
    
    matched_skills = [s['skill'] for s in skill_matching_data['details'] if s['matched']]
    missing_skills = [s['skill'] for s in skill_matching_data['details'] if not s['matched']]
    
    prompt = f"""
You are an expert HR recruiter tasked with analyzing a candidate's CV for the position of **{role}**.

## STRICT REQUIREMENTS FOR THIS POSITION:
{requirements}

## SKILL MATCHING ANALYSIS (Pre-computed):
- **Match Score**: {skill_matching_data['score']}%
- **Skills Found**: {', '.join(matched_skills) if matched_skills else 'None'}
- **Missing Skills**: {', '.join(missing_skills) if missing_skills else 'None'}

## CANDIDATE'S CV TEXT:
{cv_text[:3000]}...

---

## YOUR TASK:
Analyze this CV and provide a **CONSISTENT and STRUCTURED** assessment based STRICTLY on the requirements above.

## OUTPUT FORMAT (JSON):
{{
    "candidate_name": "Extract full name from CV",
    "match_percentage": {skill_matching_data['score']},
    "status": "selected" or "rejected",
    "recommendation": "CLEAR recommendation: HIRE or DO NOT HIRE",
    
    "skills_analysis": {{
        "skills_found": ["List each skill found"],
        "skills_missing": ["List each required skill NOT found"],
        "skill_match_percentage": {skill_matching_data['score']}
    }},
    
    "strengths": ["Strength 1", "Strength 2", "Strength 3"],
    "weaknesses": ["Weakness 1", "Weakness 2"],
    
    "experience_years": "X years (estimate from CV)",
    "education": "Highest education level",
    
    "detailed_feedback": "2-3 sentence summary of why candidate is selected/rejected based on requirements",
    
    "reasoning": "Explain your decision based ONLY on the requirements listed above. Reference specific skills found/missing."
}}

## CRITICAL RULES:
1. **NEVER deviate from the requirements** listed above
2. **Base your match_percentage STRICTLY on skill matching** (use the {skill_matching_data['score']}% provided)
3. **Select ("selected") ONLY if match_percentage >= 70%**
4. **Reject ("rejected") if match_percentage < 70%**
5. **Be CONSISTENT** - same requirements = same criteria
6. **Reference specific skills** from requirements in your reasoning
7. **Do NOT add subjective opinions** not based on requirements

Return ONLY valid JSON, nothing else.
"""
    
    return prompt


def analyze_resume_with_agent(cv_text: str, role: str, requirements: str) -> dict:
    """
    Analisa resume menggunakan AI Agent dengan sistem yang lebih terstruktur dan konsisten
    
    Args:
        cv_text: Teks dari CV
        role: Nama posisi
        requirements: Requirement untuk posisi
    
    Returns:
        dict: Hasil analisa terstruktur
    """
    try:
        # 1. Ekstrak dan parse required skills
        required_skills = parse_skills_from_requirement(requirements)
        
        # 2. Hitung skill matching score
        skill_score, skill_details = calculate_skill_match_score(cv_text, required_skills)
        
        skill_matching_data = {
            'score': skill_score,
            'details': skill_details
        }
        
        # 3. Buat prompt terstruktur
        prompt = create_structured_prompt(role, requirements, cv_text, skill_matching_data)
        
        # 4. Panggil AI Agent
        agent = Agent(
            model=OpenAIChat(id="gpt-4o-mini"),
            markdown=False,
            structured_outputs=True,
        )
        
        # Run agent dengan timeout
        response = agent.run(prompt, stream=False)
        
        # 5. Parse response JSON
        try:
            # Ekstrak JSON dari response
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Coba parse sebagai JSON
            if response_text.strip().startswith('{'):
                result = json.loads(response_text)
            else:
                # Cari JSON dalam response
                json_match = re.search(r'\{[\s\S]*\}', response_text)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    raise ValueError("No valid JSON found in response")
            
            # 6. Validasi dan koreksi hasil
            result['match_percentage'] = skill_score  # Enforce skill matching score
            
            # Enforce decision rules
            if result['match_percentage'] >= 70:
                result['status'] = 'selected'
            else:
                result['status'] = 'rejected'
            
            # 7. Tambahkan metadata
            result['_metadata'] = {
                'analysis_timestamp': datetime.now().isoformat(),
                'skill_matching': skill_matching_data,
                'required_skills_count': len(required_skills),
                'role': role
            }
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            # Fallback result
            return create_fallback_result(cv_text, role, skill_matching_data)
    
    except Exception as e:
        logger.error(f"Error in analyze_resume_with_agent: {e}")
        return create_fallback_result(cv_text, role, {'score': 0, 'details': []})


def create_fallback_result(cv_text: str, role: str, skill_matching_data: dict) -> dict:
    """
    Buat hasil fallback jika AI gagal atau error
    
    Args:
        cv_text: Teks CV
        role: Nama posisi
        skill_matching_data: Data skill matching
    
    Returns:
        dict: Hasil analisa fallback
    """
    # Extract name dari CV (simple pattern matching)
    name_match = re.search(r'^([A-Z][a-z]+\s+[A-Z][a-z]+)', cv_text, re.MULTILINE)
    candidate_name = name_match.group(1) if name_match else "Unknown Candidate"
    
    matched_skills = [s['skill'] for s in skill_matching_data.get('details', []) if s.get('matched')]
    missing_skills = [s['skill'] for s in skill_matching_data.get('details', []) if not s.get('matched')]
    
    score = skill_matching_data.get('score', 0)
    
    return {
        'candidate_name': candidate_name,
        'match_percentage': score,
        'status': 'selected' if score >= 70 else 'rejected',
        'recommendation': 'HIRE' if score >= 70 else 'DO NOT HIRE',
        'skills_analysis': {
            'skills_found': matched_skills,
            'skills_missing': missing_skills,
            'skill_match_percentage': score
        },
        'strengths': matched_skills[:3] if matched_skills else ['Unable to analyze'],
        'weaknesses': missing_skills[:2] if missing_skills else ['Unable to analyze'],
        'experience_years': 'Unknown',
        'education': 'Unknown',
        'detailed_feedback': f'Automatic analysis based on skill matching. Score: {score}%',
        'reasoning': f'Based on skill matching algorithm, candidate meets {score}% of requirements.',
        '_metadata': {
            'analysis_timestamp': datetime.now().isoformat(),
            'skill_matching': skill_matching_data,
            'fallback': True,
            'role': role
        }
    }


# --- 6. FUNGSI CACHING DAN DEDUPLICATION ---

def generate_cv_hash(cv_text: str, role: str) -> str:
    """
    Generate hash unik untuk CV dan role combination
    
    Args:
        cv_text: Teks CV
        role: Nama posisi
    
    Returns:
        str: Hash string unik
    """
    content = f"{cv_text[:500]}{role}"  # Gunakan 500 karakter pertama CV + role
    return hashlib.md5(content.encode()).hexdigest()


def get_cached_analysis(cv_hash: str, cache: dict) -> Optional[dict]:
    """
    Ambil hasil analisa dari cache jika ada
    
    Args:
        cv_hash: Hash CV
        cache: Dictionary cache
    
    Returns:
        Optional[dict]: Hasil analisa dari cache atau None
    """
    if cv_hash in cache:
        cached_result = cache[cv_hash]
        # Check jika cache masih valid (< 7 hari)
        cache_time = datetime.fromisoformat(cached_result.get('_cache_time', '2000-01-01'))
        if (datetime.now() - cache_time).days < 7:
            logger.info(f"Using cached analysis for {cv_hash}")
            return cached_result
    return None


def save_to_cache(cv_hash: str, result: dict, cache: dict):
    """
    Simpan hasil analisa ke cache
    
    Args:
        cv_hash: Hash CV
        result: Hasil analisa
        cache: Dictionary cache
    """
    result['_cache_time'] = datetime.now().isoformat()
    cache[cv_hash] = result
    save_analysis_cache(cache)


# --- 7. BATCH PROCESSING YANG DIOPTIMALKAN ---

def process_batch_resumes(uploaded_files: list, role: str, requirements: str, 
                         progress_callback=None) -> List[dict]:
    """
    Proses batch resume dengan progress tracking dan caching
    
    Args:
        uploaded_files: List file yang diupload
        role: Nama posisi
        requirements: Requirement posisi
        progress_callback: Fungsi callback untuk update progress
    
    Returns:
        List[dict]: List hasil analisa
    """
    results = []
    total_files = len(uploaded_files)
    
    # Load cache
    cache = load_analysis_cache()
    
    # Validasi jumlah file
    if total_files > MAX_BATCH_SIZE:
        if progress_callback:
            progress_callback(f"⚠️ Hanya {MAX_BATCH_SIZE} file pertama yang akan diproses")
        uploaded_files = uploaded_files[:MAX_BATCH_SIZE]
        total_files = MAX_BATCH_SIZE
    
    for idx, uploaded_file in enumerate(uploaded_files, 1):
        try:
            # Update progress
            if progress_callback:
                progress_callback(f"📄 Memproses {idx}/{total_files}: {uploaded_file.name}")
            
            # Ekstrak teks dari PDF
            use_ocr = st.session_state.get('enable_ocr', False)
            cv_text, ocr_used = extract_text_from_pdf(uploaded_file, use_ocr)
            
            if not cv_text or len(cv_text.strip()) < 50:
                results.append({
                    'filename': uploaded_file.name,
                    'candidate_name': 'Unknown',
                    'status': 'error',
                    'match_percentage': 0,
                    'error_message': 'Tidak dapat mengekstrak teks dari PDF',
                    'ocr_used': ocr_used
                })
                continue
            
            # Generate hash untuk caching
            cv_hash = generate_cv_hash(cv_text, role)
            
            # Cek cache
            cached_result = get_cached_analysis(cv_hash, cache)
            
            if cached_result:
                # Gunakan hasil dari cache
                result = cached_result.copy()
                result['_from_cache'] = True
            else:
                # Analisa dengan AI
                result = analyze_resume_with_agent(cv_text, role, requirements)
                
                # Simpan ke cache
                save_to_cache(cv_hash, result, cache)
            
            # Tambahkan metadata file
            result['filename'] = uploaded_file.name
            result['ocr_used'] = ocr_used
            result['file_size'] = len(uploaded_file.getvalue())
            result['processed_at'] = datetime.now().isoformat()
            
            results.append(result)
            
            # Small delay untuk avoid rate limiting
            time.sleep(0.5)
            
        except Exception as e:
            logger.error(f"Error processing {uploaded_file.name}: {e}")
            results.append({
                'filename': uploaded_file.name,
                'candidate_name': 'Unknown',
                'status': 'error',
                'match_percentage': 0,
                'error_message': str(e),
                'ocr_used': False
            })
    
    return results


# --- 8. FUNGSI DOWNLOAD CV DARI LINK ---

def convert_google_drive_link(url: str) -> str:
    """
    Konversi Google Drive sharing link ke direct download link
    
    Args:
        url: URL Google Drive
    
    Returns:
        str: Direct download URL
    """
    # Pattern untuk berbagai format Google Drive URL
    patterns = [
        r'drive\.google\.com/file/d/([a-zA-Z0-9_-]+)',
        r'drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            file_id = match.group(1)
            return f"https://drive.google.com/uc?export=download&id={file_id}"
    
    return url


def download_pdf_from_url(url: str, timeout: int = 30, max_retries: int = 3) -> Optional[bytes]:
    """
    Download PDF dari URL dengan retry mechanism
    
    Args:
        url: URL file PDF
        timeout: Timeout dalam detik
        max_retries: Maksimal retry attempts
    
    Returns:
        Optional[bytes]: PDF bytes atau None jika gagal
    """
    for attempt in range(max_retries):
        try:
            # Konversi Google Drive link jika perlu
            if 'drive.google.com' in url:
                url = convert_google_drive_link(url)
            
            # Set headers untuk avoid blocking
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/pdf,application/octet-stream,*/*',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive'
            }
            
            # Download dengan timeout dan streaming untuk file besar
            response = requests.get(
                url, 
                headers=headers, 
                timeout=timeout, 
                allow_redirects=True,
                stream=True
            )
            
            if response.status_code == 200:
                # Validasi content type
                content_type = response.headers.get('Content-Type', '')
                
                # Read content dengan limit size (max 50MB)
                max_size = 50 * 1024 * 1024  # 50MB
                content = b''
                
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        content += chunk
                        if len(content) > max_size:
                            logger.warning(f"File too large (>50MB): {url}")
                            return None
                
                # Validasi bahwa ini adalah PDF
                if 'pdf' in content_type.lower() or content[:4] == b'%PDF':
                    logger.info(f"Successfully downloaded PDF from {url} ({len(content)} bytes)")
                    return content
                else:
                    logger.warning(f"URL does not point to a PDF file: {content_type}")
                    return None
            
            elif response.status_code == 404:
                logger.error(f"File not found (404): {url}")
                return None  # Don't retry for 404
            
            elif response.status_code == 403:
                logger.error(f"Access forbidden (403): {url}")
                return None  # Don't retry for 403
            
            else:
                logger.error(f"Failed to download from {url}: HTTP {response.status_code}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying... (attempt {attempt + 2}/{max_retries})")
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                return None
        
        except requests.exceptions.Timeout:
            logger.error(f"Timeout error for {url}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying... (attempt {attempt + 2}/{max_retries})")
                time.sleep(2 ** attempt)
                continue
            return None
        
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error for {url}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying... (attempt {attempt + 2}/{max_retries})")
                time.sleep(2 ** attempt)
                continue
            return None
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error for {url}: {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying... (attempt {attempt + 2}/{max_retries})")
                time.sleep(2 ** attempt)
                continue
            return None
        
        except Exception as e:
            logger.error(f"Unexpected error downloading from {url}: {e}")
            return None
    
    return None


def read_excel_with_cv_links(excel_file) -> Optional[pd.DataFrame]:
    """
    Baca file Excel dan ekstrak link CV
    
    Args:
        excel_file: File Excel (uploaded file atau path)
    
    Returns:
        Optional[pd.DataFrame]: DataFrame dengan kolom link CV atau None
    """
    try:
        df = pd.read_excel(excel_file)
        
        # Cari kolom yang berisi link CV (case-insensitive)
        possible_columns = ['link cv', 'cv link', 'link', 'url', 'cv url']
        link_column = None
        
        for col in df.columns:
            if col.lower() in possible_columns:
                link_column = col
                break
        
        if not link_column:
            logger.error("No CV link column found in Excel")
            return None
        
        # Filter rows dengan link yang valid
        df_filtered = df[df[link_column].notna()].copy()
        df_filtered = df_filtered[df_filtered[link_column].astype(str).str.startswith('http')]
        
        if df_filtered.empty:
            logger.error("No valid HTTP links found")
            return None
        
        return df_filtered
    
    except Exception as e:
        logger.error(f"Error reading Excel file: {e}")
        return None


def process_excel_cv_links(excel_file, role: str) -> List[dict]:
    """
    Proses CV dari link di file Excel dengan error handling yang lebih baik
    
    Args:
        excel_file: File Excel dengan link CV
        role: Nama posisi
    
    Returns:
        List[dict]: Hasil analisa
    """
    results = []
    
    try:
        # Baca Excel
        df = read_excel_with_cv_links(excel_file)
        
        if df is None or df.empty:
            st.error("❌ Tidak ada data valid di file Excel")
            return results
        
        # Load requirements
        roles = load_roles()
        requirements = roles.get(role, "No requirements specified")
        
        # Load cache
        cache = load_analysis_cache()
        
        # Identifikasi kolom
        link_column = None
        name_column = None
        
        for col in df.columns:
            col_lower = col.lower()
            if 'link' in col_lower or 'url' in col_lower:
                link_column = col
            if 'nama' in col_lower or 'name' in col_lower:
                name_column = col
        
        if not link_column:
            st.error("❌ Kolom link CV tidak ditemukan")
            return results
        
        # Reset index untuk sequential numbering
        df = df.reset_index(drop=True)
        total = min(len(df), MAX_BATCH_SIZE)
        
        # Progress tracking containers
        progress_bar = st.progress(0)
        status_text = st.empty()
        metrics_container = st.empty()
        
        # Process tracking
        processed = 0
        successful = 0
        failed = 0
        
        for idx in range(total):
            url = None
            candidate_name = "Unknown"
            
            try:
                row = df.iloc[idx]
                
                # Get URL and candidate name safely
                url = str(row[link_column]) if pd.notna(row[link_column]) else None
                
                if not url or not url.startswith('http'):
                    failed += 1
                    results.append({
                        'filename': url or 'N/A',
                        'candidate_name': 'Unknown',
                        'status': 'error',
                        'match_percentage': 0,
                        'error_message': 'Invalid URL format',
                        'url': url or 'N/A'
                    })
                    continue
                
                candidate_name = str(row[name_column]) if name_column and pd.notna(row.get(name_column)) else "Unknown"
                
                # Update progress
                progress_value = (idx + 1) / total
                progress_bar.progress(progress_value)
                
                # Update status
                status_text.text(f"📥 [{idx + 1}/{total}] Downloading: {candidate_name}")
                
                # Update metrics
                with metrics_container:
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Processed", processed)
                    col2.metric("Success", successful)
                    col3.metric("Failed", failed)
                
                # Download PDF with timeout and error handling
                try:
                    pdf_bytes = download_pdf_from_url(url, timeout=30)
                except Exception as download_error:
                    logger.error(f"Download error for {url}: {download_error}")
                    pdf_bytes = None
                
                if not pdf_bytes:
                    failed += 1
                    results.append({
                        'filename': url,
                        'candidate_name': candidate_name,
                        'status': 'error',
                        'match_percentage': 0,
                        'error_message': 'Gagal download PDF dari URL (timeout atau file tidak ditemukan)',
                        'url': url
                    })
                    processed += 1
                    continue
                
                # Ekstrak teks dengan error handling
                status_text.text(f"📄 [{idx + 1}/{total}] Extracting text: {candidate_name}")
                
                try:
                    use_ocr = st.session_state.get('enable_ocr', False)
                    cv_text, ocr_used = extract_text_from_pdf(pdf_bytes, use_ocr)
                except Exception as extract_error:
                    logger.error(f"Text extraction error: {extract_error}")
                    cv_text = ""
                    ocr_used = False
                
                if not cv_text or len(cv_text.strip()) < 50:
                    failed += 1
                    results.append({
                        'filename': url,
                        'candidate_name': candidate_name,
                        'status': 'error',
                        'match_percentage': 0,
                        'error_message': 'Tidak dapat mengekstrak teks dari PDF (mungkin PDF rusak atau terenkripsi)',
                        'url': url,
                        'ocr_used': ocr_used
                    })
                    processed += 1
                    continue
                
                # Generate hash untuk caching
                cv_hash = generate_cv_hash(cv_text, role)
                
                # Cek cache
                cached_result = get_cached_analysis(cv_hash, cache)
                
                if cached_result:
                    result = cached_result.copy()
                    result['_from_cache'] = True
                    status_text.text(f"💾 [{idx + 1}/{total}] Using cached result: {candidate_name}")
                else:
                    # Analisa dengan AI
                    status_text.text(f"🤖 [{idx + 1}/{total}] Analyzing: {candidate_name}")
                    
                    try:
                        result = analyze_resume_with_agent(cv_text, role, requirements)
                        
                        # Simpan ke cache
                        save_to_cache(cv_hash, result, cache)
                    except Exception as analysis_error:
                        logger.error(f"Analysis error: {analysis_error}")
                        failed += 1
                        results.append({
                            'filename': url,
                            'candidate_name': candidate_name,
                            'status': 'error',
                            'match_percentage': 0,
                            'error_message': f'Gagal analisa: {str(analysis_error)}',
                            'url': url
                        })
                        processed += 1
                        continue
                
                # Tambahkan metadata
                result['filename'] = url
                result['url'] = url
                result['ocr_used'] = ocr_used
                result['candidate_name'] = candidate_name if candidate_name != "Unknown" else result.get('candidate_name', 'Unknown')
                result['processed_at'] = datetime.now().isoformat()
                
                results.append(result)
                successful += 1
                processed += 1
                
                # Small delay untuk avoid rate limiting
                time.sleep(0.3)
                
            except KeyboardInterrupt:
                st.warning("⚠️ Proses dibatalkan oleh user")
                break
                
            except Exception as e:
                logger.error(f"Error processing row {idx}: {e}")
                failed += 1
                processed += 1
                
                results.append({
                    'filename': url or 'Unknown',
                    'candidate_name': candidate_name,
                    'status': 'error',
                    'match_percentage': 0,
                    'error_message': f'Error tidak terduga: {str(e)}',
                    'url': url or 'Unknown'
                })
        
        # Cleanup
        progress_bar.empty()
        status_text.empty()
        metrics_container.empty()
        
        # Final summary
        st.success(f"✅ Selesai! Processed: {processed}, Success: {successful}, Failed: {failed}")
        
        return results
        
    except Exception as e:
        logger.error(f"Fatal error in process_excel_cv_links: {e}")
        st.error(f"❌ Error fatal: {str(e)}")
        return results


# --- 9. TAMPILAN HASIL & UI COMPONENTS ---

def display_results_table(results: list, language: str = 'id'):
    """Tampilkan hasil dalam bentuk tabel dengan fitur export"""
    
    if not results:
        st.info(get_text('no_results_yet'))
        return
    
    st.markdown(f"### {get_text('summary_header')}")
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    selected_count = sum(1 for r in results if r.get('status') == 'selected')
    rejected_count = sum(1 for r in results if r.get('status') == 'rejected')
    error_count = sum(1 for r in results if r.get('status') == 'error')
    ocr_count = sum(1 for r in results if r.get('ocr_used', False))
    
    col1.metric(get_text('total_processed'), len(results))
    col2.metric(get_text('selected_label'), selected_count, delta=f"{selected_count/len(results)*100:.1f}%")
    col3.metric(get_text('rejected_label'), rejected_count)
    col4.metric(get_text('errors_label'), error_count)
    
    if ocr_count > 0:
        st.info(f"🔍 OCR digunakan untuk {ocr_count} file")
    
    st.markdown("---")
    
    # Filter options
    col_filter1, col_filter2 = st.columns(2)
    
    with col_filter1:
        status_filter = st.multiselect(
            "Filter berdasarkan Status:",
            options=['selected', 'rejected', 'error'],
            default=['selected', 'rejected', 'error'],
            format_func=lambda x: {
                'selected': '✅ Direkomendasikan',
                'rejected': '❌ Tidak Direkomendasikan',
                'error': '⚠️ Error'
            }.get(x, x)
        )
    
    with col_filter2:
        sort_option = st.selectbox(
            "Urutkan berdasarkan:",
            options=['match_percentage', 'candidate_name', 'processed_at'],
            format_func=lambda x: {
                'match_percentage': 'Match % (Tinggi ke Rendah)',
                'candidate_name': 'Nama (A-Z)',
                'processed_at': 'Waktu Proses (Terbaru)'
            }.get(x, x)
        )
    
    # Filter dan sort results
    filtered_results = [r for r in results if r.get('status') in status_filter]
    
    if sort_option == 'match_percentage':
        filtered_results.sort(key=lambda x: x.get('match_percentage', 0), reverse=True)
    elif sort_option == 'candidate_name':
        filtered_results.sort(key=lambda x: x.get('candidate_name', ''))
    elif sort_option == 'processed_at':
        filtered_results.sort(key=lambda x: x.get('processed_at', ''), reverse=True)
    
    # Display results as cards
    st.markdown("### 📋 Hasil Analisa Detail")
    
    for idx, result in enumerate(filtered_results, 1):
        status = result.get('status', 'unknown')
        match_pct = result.get('match_percentage', 0)
        
        # Status color
        if status == 'selected':
            status_color = '🟢'
            status_text = 'DIREKOMENDASIKAN'
        elif status == 'rejected':
            status_color = '🔴'
            status_text = 'TIDAK DIREKOMENDASIKAN'
        else:
            status_color = '⚠️'
            status_text = 'ERROR'
        
        with st.expander(f"{status_color} #{idx} | {result.get('candidate_name', 'Unknown')} | Match: {match_pct}% | {status_text}"):
            col_detail1, col_detail2 = st.columns(2)
            
            with col_detail1:
                st.markdown("**📄 Informasi Kandidat**")
                st.write(f"**Nama**: {result.get('candidate_name', 'N/A')}")
                st.write(f"**File**: {result.get('filename', 'N/A')}")
                st.write(f"**Pengalaman**: {result.get('experience_years', 'N/A')}")
                st.write(f"**Pendidikan**: {result.get('education', 'N/A')}")
                
                if result.get('ocr_used'):
                    st.write("🔍 **OCR digunakan**")
                
                if result.get('_from_cache'):
                    st.write("💾 **Dari cache**")
            
            with col_detail2:
                st.markdown("**📊 Analisa Skill**")
                st.progress(match_pct / 100, text=f"Match Score: {match_pct}%")
                
                if status != 'error':
                    skills_analysis = result.get('skills_analysis', {})
                    
                    st.markdown("**✅ Skills Ditemukan:**")
                    skills_found = skills_analysis.get('skills_found', [])
                    if skills_found:
                        for skill in skills_found[:5]:
                            st.write(f"  • {skill}")
                    else:
                        st.write("  • Tidak ada")
                    
                    st.markdown("**❌ Skills Hilang:**")
                    skills_missing = skills_analysis.get('skills_missing', [])
                    if skills_missing:
                        for skill in skills_missing[:5]:
                            st.write(f"  • {skill}")
                    else:
                        st.write("  • Semua skill terpenuhi")
            
            # Strengths & Weaknesses
            if status != 'error':
                col_sw1, col_sw2 = st.columns(2)
                
                with col_sw1:
                    st.markdown("**💪 Kelebihan:**")
                    strengths = result.get('strengths', [])
                    for strength in strengths:
                        st.write(f"  • {strength}")
                
                with col_sw2:
                    st.markdown("**⚠️ Kekurangan:**")
                    weaknesses = result.get('weaknesses', [])
                    for weakness in weaknesses:
                        st.write(f"  • {weakness}")
                
                # Feedback & Reasoning
                st.markdown("**📝 Feedback:**")
                st.write(result.get('detailed_feedback', 'N/A'))
                
                st.markdown("**💭 Alasan:**")
                st.write(result.get('reasoning', 'N/A'))
            else:
                st.error(f"❌ Error: {result.get('error_message', 'Unknown error')}")
    
    # Export buttons
    st.markdown("---")
    st.markdown("### 📥 Export Hasil")
    
    col_export1, col_export2 = st.columns(2)
    
    with col_export1:
        # Export to Excel
        if st.button(get_text('export_excel_button'), use_container_width=True):
            # Prepare data for Excel
            export_data = []
            for r in filtered_results:
                export_data.append({
                    'Nama Kandidat': r.get('candidate_name', 'N/A'),
                    'File/URL': r.get('filename', 'N/A'),
                    'Status': r.get('status', 'N/A'),
                    'Match %': r.get('match_percentage', 0),
                    'Rekomendasi': r.get('recommendation', 'N/A'),
                    'Pengalaman': r.get('experience_years', 'N/A'),
                    'Pendidikan': r.get('education', 'N/A'),
                    'Skills Ditemukan': ', '.join(r.get('skills_analysis', {}).get('skills_found', [])),
                    'Skills Hilang': ', '.join(r.get('skills_analysis', {}).get('skills_missing', [])),
                    'Feedback': r.get('detailed_feedback', 'N/A'),
                    'Waktu Proses': r.get('processed_at', 'N/A')
                })
            
            df_export = pd.DataFrame(export_data)
            
            # Create Excel file in memory
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_export.to_excel(writer, index=False, sheet_name='Hasil Analisa')
            
            excel_data = output.getvalue()
            
            st.download_button(
                label="📥 Download Excel",
                data=excel_data,
                file_name=f"hasil_rekrutmen_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    
    with col_export2:
        # Export to JSON
        json_data = json.dumps(filtered_results, indent=2, ensure_ascii=False)
        
        st.download_button(
            label=get_text('export_json_button'),
            data=json_data,
            file_name=f"hasil_rekrutmen_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True
        )


def display_role_management():
    """Tampilan untuk mengelola posisi/roles"""
    
    st.markdown(f"## {get_text('tab_manage_roles')}")
    
    tab_add, tab_edit, tab_view = st.tabs([
        get_text('add_role_header'),
        get_text('edit_role_header'),
        get_text('current_roles_header')
    ])
    
    roles = load_roles()
    
    # Tab 1: Tambah Role Baru
    with tab_add:
        st.markdown(f"### {get_text('add_role_header')}")
        
        with st.form("add_role_form"):
            new_role_id = st.text_input(
                get_text('role_id_label'),
                help=get_text('role_id_help'),
                placeholder="contoh: senior_developer"
            )
            
            new_role_name = st.text_input(
                get_text('role_name_label'),
                placeholder="contoh: Senior Software Developer"
            )
            
            new_requirements = st.text_area(
                get_text('required_skills_label'),
                help=get_text('required_skills_help'),
                height=300,
                placeholder="""Contoh:
- Minimal 5 tahun pengalaman sebagai Software Developer
- Menguasai Python dan/atau Java
- Pengalaman dengan framework Django atau Spring Boot
- Familiar dengan database SQL dan NoSQL
- Pengalaman dengan Git dan CI/CD
- Kemampuan komunikasi yang baik
- Problem solving skills
"""
            )
            
            submitted = st.form_submit_button(get_text('add_role_button'), use_container_width=True)
            
            if submitted:
                # Validasi
                if not new_role_id or not new_role_name or not new_requirements:
                    st.error("❌ Semua field harus diisi!")
                elif not re.match(r'^[a-z0-9_]+$', new_role_id):
                    st.error(get_text('role_id_invalid'))
                elif new_role_id in roles:
                    st.error(get_text('role_exists_error'))
                else:
                    # Tambah role
                    roles[new_role_id] = new_requirements
                    save_roles(roles)
                    st.success(get_text('role_added_success'))
                    st.rerun()
    
    # Tab 2: Edit Role
    with tab_edit:
        if not roles:
            st.info(get_text('no_roles_available'))
        else:
            st.markdown(f"### {get_text('edit_role_header')}")
            
            selected_role = st.selectbox(
                get_text('select_role_to_edit'),
                options=list(roles.keys()),
                format_func=lambda x: x.replace('_', ' ').title()
            )
            
            with st.form("edit_role_form"):
                edit_requirements = st.text_area(
                    get_text('required_skills_label'),
                    value=roles[selected_role],
                    height=300
                )
                
                col_update, col_delete = st.columns(2)
                
                with col_update:
                    update_submitted = st.form_submit_button(
                        get_text('update_role_button'),
                        use_container_width=True
                    )
                
                with col_delete:
                    delete_submitted = st.form_submit_button(
                        get_text('delete_role_button'),
                        use_container_width=True,
                        type="secondary"
                    )
                
                if update_submitted:
                    if not edit_requirements:
                        st.error("❌ Requirements tidak boleh kosong!")
                    else:
                        roles[selected_role] = edit_requirements
                        save_roles(roles)
                        st.success(get_text('role_updated_success'))
                        st.rerun()
                
                if delete_submitted:
                    del roles[selected_role]
                    save_roles(roles)
                    st.success(get_text('role_deleted_success'))
                    st.rerun()
    
    # Tab 3: View Current Roles
    with tab_view:
        if not roles:
            st.info(get_text('no_roles_available'))
        else:
            st.markdown(f"### {get_text('current_roles_header')}")
            
            for role_id, requirements in roles.items():
                with st.expander(f"📋 {role_id.replace('_', ' ').title()}"):
                    st.markdown(requirements)
            
            # Export/Import buttons
            st.markdown("---")
            
            col_exp, col_imp = st.columns(2)
            
            with col_exp:
                json_data = json.dumps(roles, indent=2, ensure_ascii=False)
                st.download_button(
                    label=get_text('export_roles_button'),
                    data=json_data,
                    file_name="roles_backup.json",
                    mime="application/json",
                    use_container_width=True
                )
            
            with col_imp:
                uploaded_json = st.file_uploader(
                    get_text('import_roles_button'),
                    type=['json'],
                    key='import_roles_uploader'
                )
                
                if uploaded_json:
                    try:
                        imported_roles = json.load(uploaded_json)
                        
                        if st.button("✅ Konfirmasi Import", use_container_width=True):
                            roles.update(imported_roles)
                            save_roles(roles)
                            st.success(get_text('import_roles_success'))
                            st.rerun()
                    except Exception as e:
                        st.error(get_text('import_roles_error'))
                        logger.error(f"Import error: {e}")


def display_data_management():
    """Tampilan untuk mengelola data aplikasi"""
    
    st.markdown(f"## {get_text('tab_data_management')}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📤 Export Data")
        
        # Export semua data
        if st.button(get_text('export_all_data'), use_container_width=True):
            all_data = {
                'roles': load_roles(),
                'results': load_results_from_disk(),
                'memory': load_memory(),
                'chat_history': load_chat_history(),
                'cache': load_analysis_cache(),
                'export_timestamp': datetime.now().isoformat()
            }
            
            json_data = json.dumps(all_data, indent=2, ensure_ascii=False)
            
            st.download_button(
                label="📥 Download Backup",
                data=json_data,
                file_name=f"recruitment_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True
            )
            
            st.success(get_text('backup_success'))
    
    with col2:
        st.markdown("### 📥 Import Data")
        
        uploaded_backup = st.file_uploader(
            get_text('import_all_data'),
            type=['json'],
            key='import_all_data_uploader'
        )
        
        if uploaded_backup:
            try:
                backup_data = json.load(uploaded_backup)
                
                st.info(f"📦 Backup dari: {backup_data.get('export_timestamp', 'Unknown')}")
                
                if st.button("✅ Restore Data", use_container_width=True, type="primary"):
                    # Restore semua data
                    if 'roles' in backup_data:
                        save_roles(backup_data['roles'])
                    if 'results' in backup_data:
                        st.session_state.batch_results = backup_data['results']
                        save_results_to_disk()
                    if 'memory' in backup_data:
                        save_memory(backup_data['memory'])
                    if 'chat_history' in backup_data:
                        save_chat_history(backup_data['chat_history'])
                    if 'cache' in backup_data:
                        save_analysis_cache(backup_data['cache'])
                    
                    st.success(get_text('restore_success'))
                    st.rerun()
                    
            except Exception as e:
                st.error(f"❌ Error: {e}")
    
    st.markdown("---")
    
    # Clear all data dengan proper confirmation
    st.markdown("### 🗑️ Hapus Semua Data")
    st.warning(get_text('confirm_clear_data'))
    
    # Use session state untuk confirmation
    if 'confirm_delete' not in st.session_state:
        st.session_state.confirm_delete = False
    
    col_del1, col_del2 = st.columns(2)
    
    with col_del1:
        if not st.session_state.confirm_delete:
            if st.button("🗑️ Hapus Semua Data", use_container_width=True, type="secondary"):
                st.session_state.confirm_delete = True
                st.rerun()
        else:
            if st.button("✅ YA, HAPUS SEMUA!", use_container_width=True, type="primary"):
                with st.spinner("Menghapus data..."):
                    if clear_all_data():
                        st.session_state.confirm_delete = False
                        st.success(get_text('all_data_cleared'))
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Gagal menghapus data")
    
    with col_del2:
        if st.session_state.confirm_delete:
            if st.button("❌ BATAL", use_container_width=True, type="secondary"):
                st.session_state.confirm_delete = False
                st.rerun()
    
    if st.session_state.confirm_delete:
        st.error("⚠️ **PERHATIAN**: Semua data akan dihapus permanen. Klik 'YA, HAPUS SEMUA!' untuk konfirmasi.")


def display_chatbot_interface():
    """Tampilan chatbot interface"""
    
    st.markdown(f"## {get_text('chatbot_header')}")
    
    # Load chat history
    if 'chat_messages' not in st.session_state:
        st.session_state.chat_messages = load_chat_history()
    
    # Display chat messages
    for message in st.session_state.chat_messages:
        with st.chat_message(message['role']):
            st.markdown(message['content'])
    
    # Chat input
    if prompt := st.chat_input(get_text('chatbot_placeholder')):
        # Add user message
        st.session_state.chat_messages.append({'role': 'user', 'content': prompt})
        
        with st.chat_message('user'):
            st.markdown(prompt)
        
        # Generate AI response
        with st.chat_message('assistant'):
            with st.spinner("Berpikir..."):
                # Buat context dari hasil analisa
                context = ""
                if st.session_state.batch_results:
                    context = f"\n\n### Konteks Analisa Terkini:\n"
                    context += f"Total kandidat diproses: {len(st.session_state.batch_results)}\n"
                    
                    selected = [r for r in st.session_state.batch_results if r.get('status') == 'selected']
                    context += f"Direkomendasikan: {len(selected)}\n\n"
                    
                    if selected:
                        context += "Kandidat Teratas:\n"
                        for idx, r in enumerate(selected[:3], 1):
                            context += f"{idx}. {r.get('candidate_name', 'Unknown')} - Match: {r.get('match_percentage', 0)}%\n"
                
                # Panggil AI agent
                full_prompt = f"{prompt}\n{context}"
                
                try:
                    agent = Agent(
                        model=OpenAIChat(id="gpt-4o-mini"),
                        markdown=True,
                    )
                    
                    response = agent.run(full_prompt, stream=False)
                    response_text = response.content if hasattr(response, 'content') else str(response)
                    
                    st.markdown(response_text)
                    
                    # Save to history
                    st.session_state.chat_messages.append({'role': 'assistant', 'content': response_text})
                    save_chat_history(st.session_state.chat_messages)
                    
                except Exception as e:
                    error_msg = f"❌ Error: {str(e)}"
                    st.error(error_msg)
                    st.session_state.chat_messages.append({'role': 'assistant', 'content': error_msg})
    
    # Clear chat button
    if st.button(get_text('clear_chat')):
        st.session_state.chat_messages = []
        save_chat_history([])
        st.success(get_text('chat_cleared'))
        st.rerun()


# --- 10. MAIN FUNCTION ---

def main():
    """Main function - Entry point aplikasi"""
    
    # Set page config
    st.set_page_config(
        page_title="PT Srikandi Mitra Karya - AI Recruitment System",
        page_icon="🌿",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize session state
    if 'batch_results' not in st.session_state:
        st.session_state.batch_results = load_results_from_disk()
    
    if 'language' not in st.session_state:
        st.session_state.language = 'id'
    
    if 'analysis_memory' not in st.session_state:
        st.session_state.analysis_memory = load_memory()
    
    if 'chat_messages' not in st.session_state:
        st.session_state.chat_messages = load_chat_history()
    
    if 'analysis_cache' not in st.session_state:
        st.session_state.analysis_cache = load_analysis_cache()
    
    # Sidebar configuration
    with st.sidebar:
        st.markdown(f"## {get_text('config_header')}")
        
        # Language selector
        language = st.selectbox(
            get_text('language_select'),
            options=['id', 'en'],
            format_func=lambda x: "🇮🇩 Bahasa Indonesia" if x == 'id' else "🇬🇧 English",
            key='language_selector'
        )
        st.session_state.language = language
        
        st.markdown("---")
        
        # OpenAI settings
        st.markdown(f"### {get_text('openai_settings')}")
        
        api_key = st.text_input(
            get_text('api_key_label'),
            type="password",
            help=get_text('api_key_help'),
            key='openai_api_key'
        )
        
        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
        
        st.markdown("---")
        
        # OCR settings
        st.markdown(f"### {get_text('ocr_settings')}")
        
        enable_ocr = st.checkbox(
            get_text('enable_ocr'),
            value=False,
            help=get_text('ocr_help'),
            key='enable_ocr'
        )
        
        if enable_ocr and not OCR_AVAILABLE:
            st.warning("⚠️ OCR libraries not installed. Please install: `pip install pdf2image pytesseract pillow`")
        
        st.markdown("---")
        
        # Storage info
        st.info(get_text('storage_info'))
        
        # Cache info
        cache_size = len(st.session_state.analysis_cache)
        if cache_size > 0:
            st.info(f"💾 Cache: {cache_size} analisa tersimpan")
    
    # Main content
    st.title(get_text('app_title'))
    
    # Check API key
    if not os.environ.get("OPENAI_API_KEY"):
        st.warning(f"{get_text('warning_missing_config')} OpenAI API Key")
        st.stop()
    
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
        st.markdown(f"## {get_text('tab_upload')}")
        
        roles = load_roles()
        
        if not roles:
            st.warning(get_text('no_roles_available'))
            st.info(f"👉 {get_text('tab_manage_roles')}")
        else:
            # Role selection
            role_options = list(roles.keys())
            role = st.selectbox(
                get_text('select_role'),
                role_options,
                format_func=lambda x: x.replace('_', ' ').title(),
                key='upload_selected_role'
            )
            
            # Show requirements
            with st.expander(get_text('view_skills_expander'), expanded=False):
                st.markdown(roles[role])
                
                # Parse dan tampilkan skill list
                parsed_skills = parse_skills_from_requirement(roles[role])
                st.markdown("**📋 Skill Terdeteksi:**")
                for skill in parsed_skills:
                    st.write(f"• {skill}")
            
            st.markdown("---")
            
            # File uploader
            st.markdown(get_text('batch_info'))
            
            uploaded_files = st.file_uploader(
                get_text('upload_resume_label'),
                type=['pdf'],
                accept_multiple_files=True,
                key='resume_uploader'
            )
            
            if uploaded_files:
                file_count = len(uploaded_files)
                
                if file_count > MAX_BATCH_SIZE:
                    st.warning(f"⚠️ Maksimal {MAX_BATCH_SIZE} file. Hanya {MAX_BATCH_SIZE} file pertama yang akan diproses.")
                    file_count = MAX_BATCH_SIZE
                
                st.success(f"📁 {file_count} {get_text('resumes_uploaded')}")
                
                # Show file list
                with st.expander("📋 Daftar File", expanded=False):
                    for i, f in enumerate(uploaded_files[:MAX_BATCH_SIZE], 1):
                        st.write(f"{i}. {f.name} ({f.size / 1024:.1f} KB)")
                
                st.markdown("---")
                
                col_process, col_clear = st.columns([3, 1])
                
                with col_process:
                    if st.button(get_text('process_all_button'), type='primary', use_container_width=True):
                        with st.spinner(get_text('processing_spinner')):
                            # Process batch
                            requirements = roles[role]
                            
                            # Progress container
                            progress_container = st.empty()
                            
                            def update_progress(message):
                                progress_container.info(message)
                            
                            results = process_batch_resumes(
                                uploaded_files,
                                role,
                                requirements,
                                progress_callback=update_progress
                            )
                            
                            if results:
                                # Sort by match percentage
                                results.sort(key=lambda x: x.get('match_percentage', 0), reverse=True)
                                
                                # Save results
                                st.session_state.batch_results = results
                                save_results_to_disk()
                                
                                # Show summary
                                progress_container.empty()
                                st.success(get_text('processing_complete'))
                                
                                selected_count = sum(1 for r in results if r['status'] == 'selected')
                                rejected_count = sum(1 for r in results if r['status'] == 'rejected')
                                error_count = sum(1 for r in results if r['status'] == 'error')
                                ocr_count = sum(1 for r in results if r.get('ocr_used', False))
                                
                                col_sum1, col_sum2, col_sum3, col_sum4 = st.columns(4)
                                col_sum1.metric("Total", len(results))
                                col_sum2.metric("✅ Direkomendasikan", selected_count)
                                col_sum3.metric("❌ Tidak", rejected_count)
                                col_sum4.metric("⚠️ Error", error_count)
                                
                                if ocr_count > 0:
                                    st.info(f"🔍 OCR digunakan untuk {ocr_count} file")
                                
                                st.info(f"👉 Lihat hasil detail di tab: {get_text('tab_results')}")
                
                with col_clear:
                    if st.button(get_text('clear_resumes_button'), help=get_text('clear_resumes_help'), use_container_width=True):
                        st.rerun()
    
    # TAB 2: Download from Excel
    with tab2:
        st.markdown(f"## {get_text('tab_download_excel')}")
        
        # Guide
        if st.session_state.language == 'id':
            guide_content = """
            Jika menggunakan Google Form/Drive, pastikan file **PUBLIC**:
            
            1. **Buka Google Drive**
            2. **Klik kanan folder/file** → **Bagikan**
            3. **Ubah ke:** *"Siapa saja yang memiliki link"*
            4. **Izin:** *"Viewer"*
            5. **Klik Selesai**
            
            ---
            
            ℹ️ **Link Google Drive akan otomatis dikonversi ke format direct download.**
            """
        else:
            guide_content = """
            If using Google Form/Drive, make sure the file is **PUBLIC**:
            
            1. **Open Google Drive**
            2. **Right-click folder/file** → **Share**
            3. **Change to:** *"Anyone with the link"*
            4. **Permission:** *"Viewer"*
            5. **Click Done**
            
            ---
            
            ℹ️ **Google Drive links will be automatically converted to direct download format.**
            """
        
        with st.expander(get_text('google_drive_guide'), expanded=False):
            st.markdown(guide_content)
        
        # Excel format example
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
        
        st.markdown("")
        
        # Role selection
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
            
            # Excel uploader
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
                        st.dataframe(df_preview.head(10), use_container_width=True)
                        
                        candidate_count = len(df_preview)
                        st.success(f"✅ Ditemukan {candidate_count} kandidat dengan link CV valid / Found {candidate_count} candidates with valid CV links")
                        
                        if candidate_count > MAX_BATCH_SIZE:
                            st.warning(f"⚠️ Maksimal {MAX_BATCH_SIZE} kandidat. Hanya {MAX_BATCH_SIZE} kandidat pertama yang akan diproses.")
                        
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
                                    
                                    col_sum1, col_sum2, col_sum3, col_sum4 = st.columns(4)
                                    col_sum1.metric("Total", len(results))
                                    col_sum2.metric("✅ Direkomendasikan", selected_count)
                                    col_sum3.metric("❌ Tidak", rejected_count)
                                    col_sum4.metric("⚠️ Error", error_count)
                                    
                                    if ocr_count > 0:
                                        st.info(f"🔍 OCR digunakan untuk {ocr_count} file")
                                    
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
