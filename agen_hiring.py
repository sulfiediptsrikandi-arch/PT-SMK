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
    'import_roles_button': {'id': "🌲 Import Posisi (JSON)", 'en': "🌲 Import Roles (JSON)"},
    'import_roles_success': {'id': "✅ Posisi berhasil diimport!", 'en': "✅ Roles imported successfully!"},
    'import_roles_error': {'id': "❌ Gagal import posisi. Pastikan format JSON benar.", 'en': "❌ Failed to import roles. Ensure JSON format is correct."},
    'storage_info': {'id': "💚 Data disimpan secara otomatis", 'en': "💚 Data saved automatically"},
    'data_loaded': {'id': "✅ Data berhasil dimuat dari penyimpanan", 'en': "✅ Data loaded from storage successfully"},
    'clear_all_data': {'id': "🍂 Hapus Semua Data", 'en': "🍂 Clear All Data"},
    'confirm_clear_data': {'id': "Apakah Anda yakin ingin menghapus SEMUA data termasuk posisi, hasil analisa, dan history chat?", 'en': "Are you sure you want to delete ALL data including roles, analysis results, and chat history?"},
    'all_data_cleared': {'id': "✅ Semua data berhasil dihapus", 'en': "✅ All data cleared successfully"},
    'data_management': {'id': "Manajemen Data", 'en': "Data Management"},
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
    'upload_excel_label': {'id': "Unggah File Excel (.xlsx, .xls)", 'en': "Upload Excel File (.xlsx, .xls)"},
    'excel_format_info': {'id': "📋 Excel harus memiliki kolom: 'Link CV' atau 'CV Link' atau 'URL', dan 'Nama' atau 'Name'", 'en': "📋 Excel must have columns: 'Link CV' or 'CV Link' or 'URL', and 'Nama' or 'Name'"},
    'excel_uploaded': {'id': "File Excel terunggah", 'en': "Excel file uploaded"},
    'download_all_cv': {'id': "🌳 Download & Proses Semua CV", 'en': "🌳 Download & Process All CVs"},
    'downloading_cv': {'id': "Mengunduh CV", 'en': "Downloading CV"},
    'cv_downloaded': {'id': "CV berhasil diunduh", 'en': "CV downloaded successfully"},
    'download_error': {'id': "Gagal mengunduh CV", 'en': "Failed to download CV"},
    'invalid_excel_format': {'id': "Format Excel tidak valid atau kolom yang diperlukan tidak ditemukan", 'en': "Invalid Excel format or required columns not found"},
    'no_valid_links': {'id': "Tidak ada link CV yang valid ditemukan", 'en': "No valid CV links found"},
    'no_results_yet': {'id': "🌱 Belum ada hasil. Silakan proses resume terlebih dahulu.", 'en': "🌱 No results yet. Please process resumes first."},
    
    # Export/Download
    'export_results_excel': {'id': "🌳 Export ke Excel", 'en': "🌳 Export to Excel"},
    'export_results_csv': {'id': "🌲 Export ke CSV", 'en': "🌲 Export to CSV"},
    'export_results_json': {'id': "📋 Export ke JSON", 'en': "📋 Export to JSON"},
    'download_filename': {'id': "recruitment_results", 'en': "recruitment_results"},
}

def get_text(key: str) -> str:
    """Helper function untuk mengambil teks berdasarkan bahasa yang dipilih."""
    lang = st.session_state.get('language', 'id')
    return TEXTS.get(key, {}).get(lang, key)


# --- 2. FUNGSI UNTUK PERSISTENT STORAGE ---
def load_roles() -> Dict[str, str]:
    """Load roles from disk."""
    try:
        if ROLES_FILE.exists():
            with open(ROLES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading roles: {e}")
    return {}

def save_roles(roles: Dict[str, str]):
    """Save roles to disk."""
    try:
        with open(ROLES_FILE, 'w', encoding='utf-8') as f:
            json.dump(roles, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving roles: {e}")

def load_analysis_memory() -> List[Dict]:
    """Load analysis memory from disk."""
    try:
        if MEMORY_FILE.exists():
            with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading memory: {e}")
    return []

def save_analysis_memory(memory: List[Dict]):
    """Save analysis memory to disk."""
    try:
        with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(memory, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving memory: {e}")

def load_chat_history() -> List[Dict]:
    """Load chat history from disk."""
    try:
        if CHAT_HISTORY_FILE.exists():
            with open(CHAT_HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading chat history: {e}")
    return []

def save_chat_history(history: List[Dict]):
    """Save chat history to disk."""
    try:
        with open(CHAT_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving chat history: {e}")

def load_results_from_disk() -> List[Dict]:
    """Load batch results from disk."""
    try:
        if RESULTS_FILE.exists():
            with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading results: {e}")
    return []

def save_results_to_disk():
    """Save batch results to disk."""
    try:
        with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(st.session_state.get('batch_results', []), f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving results: {e}")

def clear_all_persistent_data():
    """Clear all persistent data files."""
    try:
        for file in [ROLES_FILE, MEMORY_FILE, CHAT_HISTORY_FILE, RESULTS_FILE]:
            if file.exists():
                file.unlink()
        st.session_state.clear()
        return True
    except Exception as e:
        logger.error(f"Error clearing data: {e}")
        return False

def export_all_data() -> dict:
    """Export all data as JSON for backup."""
    return {
        'roles': load_roles(),
        'analysis_memory': load_analysis_memory(),
        'chat_history': load_chat_history(),
        'batch_results': load_results_from_disk(),
        'export_date': datetime.now().isoformat()
    }

def import_all_data(data: dict) -> bool:
    """Import all data from backup JSON."""
    try:
        if 'roles' in data:
            save_roles(data['roles'])
        if 'analysis_memory' in data:
            save_analysis_memory(data['analysis_memory'])
        if 'chat_history' in data:
            save_chat_history(data['chat_history'])
        if 'batch_results' in data:
            st.session_state['batch_results'] = data['batch_results']
            save_results_to_disk()
        return True
    except Exception as e:
        logger.error(f"Error importing data: {e}")
        return False


# --- 3. FUNGSI ANALISIS RESUME (KONSISTEN & DETERMINISTIK) ---
def calculate_consistent_score(resume_text: str, requirements: str) -> Dict:
    """Calculate a deterministic baseline score based on keyword matching."""
    resume_lower = resume_text.lower()
    requirements_lower = requirements.lower()
    
    # Extract common keywords from requirements
    keywords = {
        'education': ['bachelor', 'master', 'phd', 'sarjana', 's1', 's2', 's3', 'degree', 'university', 'universitas'],
        'experience': ['year', 'tahun', 'experience', 'pengalaman', 'worked', 'bekerja'],
        'certifications': ['certificate', 'certification', 'sertifikat', 'certified', 'licensed'],
        'skills': []
    }
    
    # Extract skill keywords from requirements
    skill_patterns = [
        r'\b[A-Z][a-z]+\b',  # Capitalized words (often technologies)
        r'\b[A-Z]{2,}\b',     # Acronyms
    ]
    for pattern in skill_patterns:
        matches = re.findall(pattern, requirements)
        keywords['skills'].extend([m.lower() for m in matches if len(m) > 2])
    
    # Calculate matches
    education_match = any(kw in resume_lower for kw in keywords['education'])
    has_experience = any(kw in resume_lower for kw in keywords['experience'])
    has_certifications = any(kw in resume_lower for kw in keywords['certifications'])
    
    matching_skills = [skill for skill in keywords['skills'] if skill in resume_lower]
    total_skills = len(set(keywords['skills']))
    skill_match_ratio = len(matching_skills) / max(total_skills, 1)
    
    # Calculate score
    score = 0
    score += 30 if education_match else 0
    score += 30 if has_experience else 0
    score += 15 if has_certifications else 0
    score += int(25 * skill_match_ratio)
    
    return {
        'score': score,
        'education_match': education_match,
        'has_experience': has_experience,
        'has_certifications': has_certifications,
        'matching_keywords': matching_skills[:10],  # Top 10
        'skill_match_ratio': skill_match_ratio
    }

def extract_json_from_response(response: str) -> dict:
    """Extract JSON from AI response, handling markdown code blocks and other formatting."""
    response = response.strip()
    
    # Remove markdown code blocks
    if response.startswith('```'):
        response = re.sub(r'^```(?:json)?\s*\n', '', response)
        response = re.sub(r'\n```\s*$', '', response)
    
    # Find JSON object boundaries
    json_match = re.search(r'\{[\s\S]*\}', response)
    if json_match:
        response = json_match.group(0)
    
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}\nResponse: {response[:500]}")
        raise ValueError(f"Invalid JSON in AI response: {str(e)}")

def validate_analysis_result(result: dict) -> bool:
    """Validate that the analysis result has all required fields."""
    required_fields = ['selected', 'feedback', 'candidate_name']
    return all(field in result for field in required_fields)

def save_to_memory(result: dict):
    """Save analysis result to memory for chatbot context."""
    memory = load_analysis_memory()
    memory.append({
        'timestamp': datetime.now().isoformat(),
        'filename': result.get('filename', 'unknown'),
        'candidate_name': result.get('candidate_name', 'N/A'),
        'role': result.get('role', 'unknown'),
        'status': result.get('status', 'unknown'),
        'match_percentage': result.get('match_percentage', 0),
        'feedback': result.get('feedback', ''),
    })
    # Keep only last 100 entries
    if len(memory) > 100:
        memory = memory[-100:]
    save_analysis_memory(memory)


# --- 4. FUNGSI EKSTRAKSI PDF & OCR ---
def extract_text_from_pdf(pdf_file) -> str:
    """Extract text from PDF file."""
    try:
        pdf_file.seek(0)
        reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text.strip()
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        return ""

def extract_text_with_ocr(pdf_file) -> Tuple[str, bool]:
    """Extract text from PDF with OCR fallback for image-based PDFs."""
    # First try normal extraction
    text = extract_text_from_pdf(pdf_file)
    
    # If text is too short, it might be an image-based PDF
    if len(text.strip()) < 100 and OCR_AVAILABLE:
        try:
            pdf_file.seek(0)
            images = convert_from_bytes(pdf_file.read())
            
            ocr_text = ""
            for img in images:
                ocr_text += pytesseract.image_to_string(img) + "\n"
            
            if len(ocr_text.strip()) > len(text.strip()):
                logger.info("OCR produced better results")
                return ocr_text.strip(), True
        except Exception as e:
            logger.error(f"OCR error: {e}")
    
    return text, False


# --- 5. FUNGSI UNTUK MEMBUAT AGENT ---
def create_resume_analyzer() -> Optional[Agent]:
    """Create resume analyzer agent with API key from session state."""
    api_key = st.session_state.get('openai_api_key')
    
    if not api_key:
        return None
    
    try:
        return Agent(
            model=OpenAIChat(
                id="gpt-4o-mini",
                api_key=api_key
            ),
            markdown=False,
        )
    except Exception as e:
        logger.error(f"Error creating analyzer: {e}")
        return None


# --- 6. FUNGSI UNTUK ANALISIS RESUME ---
def analyze_resume(
    resume_text: str,
    role: str,
    analyzer: Agent,
    max_retries: int = 3
) -> Tuple[bool, str, Dict]:
    """Analyze resume with enhanced consistency and determinism."""
    
    roles = load_roles()
    requirements = roles.get(role, "")
    
    if not requirements:
        return False, f"Role '{role}' not found in system", {}
    
    lang = st.session_state.get('language', 'id')
    feedback_lang = "Bahasa Indonesia" if lang == 'id' else "English"
    
    # Calculate baseline score for consistency
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


# --- 7. FUNGSI URL VALIDATION & DOWNLOAD ---
def is_valid_url(url: str) -> bool:
    """Validate if string is a proper URL."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def convert_google_drive_link(url: str) -> str:
    """
    Convert various Google Drive link formats to direct download format.
    Supports:
    - /file/d/FILE_ID/view
    - /open?id=FILE_ID
    - /file/d/FILE_ID/edit
    - etc.
    """
    if 'drive.google.com' not in url:
        return url
    
    # Format 1: /file/d/FILE_ID/view or /file/d/FILE_ID/edit
    file_id = None
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
        
        # Process the downloaded CV
        processed_result = process_single_candidate(cv_file, role)
        processed_result['cv_link'] = cv_link
        processed_result['candidate_name'] = candidate_name  # Override with Excel name
        results.append(processed_result)
    
    progress_bar.progress(1.0)
    status_text.text(f"✅ {get_text('processing_complete')}")
    
    return results


# --- 8. FUNGSI PEMROSESAN KANDIDAT ---
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


# --- 9. FUNGSI UTILITY ---
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
    return "🌿"  # Nature theme icon

def display_logo_in_sidebar(logo_path: str = None):
    """Display logo in sidebar with 3D effect - NATURE THEME."""
    if logo_path and os.path.exists(logo_path):
        st.sidebar.markdown("""
            <style>
            section[data-testid="stSidebar"] img {
                border-radius: 15px;
                padding: 15px;
                background: linear-gradient(145deg, #c8e6c9, #a5d6a7);
                box-shadow: 
                    8px 8px 16px rgba(76, 175, 80, 0.3),
                    -8px -8px 16px rgba(200, 230, 201, 0.7),
                    inset 2px 2px 4px rgba(255, 255, 255, 0.3),
                    inset -2px -2px 4px rgba(76, 175, 80, 0.1);
                transition: all 0.3s ease;
            }
            section[data-testid="stSidebar"] img:hover {
                transform: translateY(-5px);
                box-shadow: 
                    12px 12px 24px rgba(76, 175, 80, 0.4),
                    -12px -12px 24px rgba(200, 230, 201, 0.8);
            }
            </style>
        """, unsafe_allow_html=True)
        st.sidebar.image(logo_path, use_container_width=True)
    else:
        st.sidebar.markdown("""
            <div style="text-align: center; padding: 20px;">
                <div style="
                    font-size: 80px;
                    background: linear-gradient(145deg, #66bb6a, #43a047);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    filter: drop-shadow(2px 2px 4px rgba(76, 175, 80, 0.3));
                ">
                    🌿
                </div>
            </div>
        """, unsafe_allow_html=True)


# --- 10. CHATBOT INTERFACE ---
def create_chatbot() -> Optional[Agent]:
    """Create chatbot agent with context."""
    api_key = st.session_state.get('openai_api_key')
    
    if not api_key:
        return None
    
    # Get context from analysis memory
    memory = load_analysis_memory()
    roles = load_roles()
    
    context = "You are an AI recruitment assistant. You help HR teams understand candidate analysis results.\n\n"
    
    if roles:
        context += "Available positions:\n"
        for role_id, requirements in roles.items():
            context += f"- {role_id.replace('_', ' ').title()}\n"
    
    if memory:
        context += f"\nRecent analysis results ({len(memory)} candidates analyzed):\n"
        for item in memory[-10:]:  # Last 10
            context += f"- {item['candidate_name']} ({item['role']}): {item['status']} - {item['match_percentage']}%\n"
    
    try:
        return Agent(
            model=OpenAIChat(
                id="gpt-4o-mini",
                api_key=api_key
            ),
            markdown=True,
            instructions=[
                context,
                "Always respond in the same language as the user's question.",
                "Be helpful, professional, and provide actionable insights.",
                "When discussing candidates, refer to specific data when available."
            ]
        )
    except Exception as e:
        logger.error(f"Error creating chatbot: {e}")
        return None

def display_chatbot_interface():
    """Display chatbot interface with nature theme."""
    st.header(get_text('chatbot_header'))
    
    # Initialize chat history
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = load_chat_history()
    
    # Clear chat button
    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button(get_text('clear_chat'), type="secondary"):
            st.session_state.chat_history = []
            save_chat_history([])
            st.success(get_text('chat_cleared'))
            st.rerun()
    
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
        
        # Get bot response
        chatbot = create_chatbot()
        if chatbot:
            with st.chat_message("assistant"):
                with st.spinner("🌿 Berpikir..."):
                    try:
                        response = chatbot.run(prompt)
                        assistant_message = ""
                        for m in response.messages:
                            if m.role == 'assistant' and m.content:
                                assistant_message = m.content
                                break
                        
                        if assistant_message:
                            st.markdown(assistant_message)
                            st.session_state.chat_history.append({
                                "role": "assistant",
                                "content": assistant_message
                            })
                            save_chat_history(st.session_state.chat_history)
                        else:
                            st.error("Tidak ada respons dari AI")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
        else:
            st.error(get_text('error_api_key'))


# --- 11. ROLE MANAGEMENT INTERFACE ---
def display_role_management():
    """Display role management interface with nature theme."""
    st.header(get_text('tab_manage_roles'))
    
    roles = load_roles()
    
    # Data Management Section
    with st.expander(f"💚 {get_text('data_management')}", expanded=False):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Export all data
            if st.button(get_text('export_all_data'), use_container_width=True):
                all_data = export_all_data()
                st.download_button(
                    label="📥 Download Backup",
                    data=json.dumps(all_data, indent=2, ensure_ascii=False),
                    file_name=f"recruitment_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    use_container_width=True
                )
                st.success(get_text('backup_success'))
        
        with col2:
            # Import all data
            uploaded_backup = st.file_uploader(
                get_text('import_all_data'),
                type=['json'],
                key='backup_uploader'
            )
            if uploaded_backup:
                try:
                    backup_data = json.load(uploaded_backup)
                    if import_all_data(backup_data):
                        st.success(get_text('restore_success'))
                        st.rerun()
                    else:
                        st.error("Error importing data")
                except Exception as e:
                    st.error(f"Error: {str(e)}")
        
        with col3:
            # Clear all data
            if st.button(get_text('clear_all_data'), type="secondary", use_container_width=True):
                if st.checkbox(get_text('confirm_clear_data')):
                    if clear_all_persistent_data():
                        st.success(get_text('all_data_cleared'))
                        st.rerun()
    
    st.markdown("---")
    
    # Add/Edit Role Section
    tab_add, tab_edit = st.tabs([get_text('add_role_header'), get_text('edit_role_header')])
    
    with tab_add:
        with st.form("add_role_form"):
            role_id = st.text_input(
                get_text('role_id_label'),
                help=get_text('role_id_help')
            )
            role_name = st.text_input(get_text('role_name_label'))
            role_requirements = st.text_area(
                get_text('required_skills_label'),
                height=200,
                help=get_text('required_skills_help')
            )
            
            if st.form_submit_button(get_text('add_role_button'), type="primary", use_container_width=True):
                if role_id and role_requirements:
                    # Validate role_id format
                    if not re.match(r'^[a-z0-9_]+$', role_id):
                        st.error(get_text('role_id_invalid'))
                    elif role_id in roles:
                        st.error(get_text('role_exists_error'))
                    else:
                        roles[role_id] = role_requirements
                        save_roles(roles)
                        st.success(get_text('role_added_success'))
                        st.rerun()
    
    with tab_edit:
        if roles:
            role_to_edit = st.selectbox(
                get_text('select_role_to_edit'),
                list(roles.keys()),
                format_func=lambda x: x.replace('_', ' ').title()
            )
            
            with st.form("edit_role_form"):
                edited_requirements = st.text_area(
                    get_text('required_skills_label'),
                    value=roles[role_to_edit],
                    height=200
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button(get_text('update_role_button'), type="primary", use_container_width=True):
                        roles[role_to_edit] = edited_requirements
                        save_roles(roles)
                        st.success(get_text('role_updated_success'))
                        st.rerun()
                
                with col2:
                    if st.form_submit_button(get_text('delete_role_button'), type="secondary", use_container_width=True):
                        del roles[role_to_edit]
                        save_roles(roles)
                        st.success(get_text('role_deleted_success'))
                        st.rerun()
        else:
            st.info(get_text('no_roles_available'))
    
    # Current Roles Display
    if roles:
        st.markdown("---")
        st.subheader(get_text('current_roles_header'))
        
        for role_id, requirements in roles.items():
            with st.expander(f"🌱 {role_id.replace('_', ' ').title()}", expanded=False):
                st.markdown(requirements)
        
        # Export/Import Roles
        col1, col2 = st.columns(2)
        with col1:
            if st.button(get_text('export_roles_button'), use_container_width=True):
                st.download_button(
                    label="📥 Download JSON",
                    data=json.dumps(roles, indent=2, ensure_ascii=False),
                    file_name="roles.json",
                    mime="application/json",
                    use_container_width=True
                )
        
        with col2:
            uploaded_roles = st.file_uploader(
                get_text('import_roles_button'),
                type=['json'],
                key='roles_uploader'
            )
            if uploaded_roles:
                try:
                    imported_roles = json.load(uploaded_roles)
                    save_roles(imported_roles)
                    st.success(get_text('import_roles_success'))
                    st.rerun()
                except:
                    st.error(get_text('import_roles_error'))


# --- 12. RESULTS TABLE DISPLAY ---
def create_excel_download(results: List[Dict], lang: str = 'id') -> BytesIO:
    """Create Excel file from results."""
    if not PANDAS_AVAILABLE:
        return None
    
    df_data = []
    for r in results:
        df_data.append({
            'Nama / Name': r.get('candidate_name', 'N/A'),
            'File': r.get('filename', 'N/A'),
            'Posisi / Role': r.get('role', 'N/A'),
            'Status': r.get('status', 'N/A'),
            'Match %': r.get('match_percentage', 0),
            'Telepon / Phone': r.get('candidate_phone', 'N/A'),
            'OCR': '✓' if r.get('ocr_used', False) else '✗',
            'Feedback': r.get('feedback', ''),
            'Error': r.get('error', '')
        })
    
    df = pd.DataFrame(df_data)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Results')
        
        # Auto-adjust column widths
        worksheet = writer.sheets['Results']
        for idx, col in enumerate(df.columns):
            max_length = max(
                df[col].astype(str).apply(len).max(),
                len(col)
            )
            worksheet.column_dimensions[chr(65 + idx)].width = min(max_length + 2, 50)
    
    output.seek(0)
    return output

def display_results_table(results: List[Dict], lang: str = 'id'):
    """Display results in a beautiful table with nature theme."""
    st.header(get_text('tab_results'))
    
    if not results:
        st.info(get_text('no_results_yet'))
        return
    
    # Summary cards with nature colors
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    
    selected_count = sum(1 for r in results if r['status'] == 'selected')
    rejected_count = sum(1 for r in results if r['status'] == 'rejected')
    error_count = sum(1 for r in results if r['status'] == 'error')
    
    with col1:
        st.metric(
            label="🌳 " + get_text('total_processed'),
            value=len(results)
        )
    with col2:
        st.metric(
            label="✅ " + get_text('selected_label'),
            value=selected_count
        )
    with col3:
        st.metric(
            label="❌ " + get_text('rejected_label'),
            value=rejected_count
        )
    with col4:
        st.metric(
            label="⚠️ " + get_text('errors_label'),
            value=error_count
        )
    
    st.markdown("---")
    
    # Export buttons
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if PANDAS_AVAILABLE:
            excel_file = create_excel_download(results, lang)
            if excel_file:
                st.download_button(
                    label=get_text('export_results_excel'),
                    data=excel_file,
                    file_name=f"{get_text('download_filename')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
    
    with col2:
        if PANDAS_AVAILABLE:
            df = pd.DataFrame(results)
            csv = df.to_csv(index=False)
            st.download_button(
                label=get_text('export_results_csv'),
                data=csv,
                file_name=f"{get_text('download_filename')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
    
    with col3:
        st.download_button(
            label=get_text('export_results_json'),
            data=json.dumps(results, indent=2, ensure_ascii=False),
            file_name=f"{get_text('download_filename')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True
        )
    
    st.markdown("---")
    
    # Display each result
    for idx, result in enumerate(sorted(results, key=lambda x: x.get('match_percentage', 0), reverse=True)):
        status = result['status']
        status_emoji = {
            'selected': '✅',
            'rejected': '❌',
            'error': '⚠️',
            'pending': '⏳'
        }.get(status, '❔')
        
        status_color = {
            'selected': '#4CAF50',  # Green
            'rejected': '#D32F2F',  # Red
            'error': '#FF9800',     # Orange
            'pending': '#2196F3'    # Blue
        }.get(status, '#9E9E9E')
        
        with st.expander(
            f"{status_emoji} {result.get('candidate_name', 'N/A')} - {result.get('match_percentage', 0)}%",
            expanded=False
        ):
            col1, col2 = st.columns([2, 3])
            
            with col1:
                st.markdown(f"**File:** {result.get('filename', 'N/A')}")
                st.markdown(f"**Posisi / Role:** {result.get('role', 'N/A')}")
                st.markdown(f"**Telepon / Phone:** {result.get('candidate_phone', 'N/A')}")
                
                # Progress bar for match percentage
                match_pct = result.get('match_percentage', 0)
                st.progress(match_pct / 100)
                st.markdown(f"**Match:** {match_pct}%")
                
                if result.get('ocr_used', False):
                    st.info("🔍 OCR digunakan / OCR used")
            
            with col2:
                st.markdown(f"**Status:** <span style='color: {status_color}; font-weight: bold;'>{status.upper()}</span>", unsafe_allow_html=True)
                
                if result.get('error'):
                    st.error(f"**Error:** {result['error']}")
                
                if result.get('feedback'):
                    st.markdown("**Feedback:**")
                    st.markdown(result['feedback'])
                
                if result.get('matching_skills'):
                    st.success(f"**✅ Matching Skills:** {', '.join(result['matching_skills'])}")
                
                if result.get('missing_skills'):
                    st.warning(f"**❌ Missing Skills:** {', '.join(result['missing_skills'])}")


# --- 13. MAIN APPLICATION ---
def main():
    """Main application with nature theme."""
    # Page config
    st.set_page_config(
        page_title="PT Srikandi Mitra Karya - Recruitment AI",
        page_icon="🌿",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # NATURE THEME CSS
    st.markdown("""
        <style>
        /* Main colors - Nature palette */
        :root {
            --primary-green: #4CAF50;
            --secondary-green: #66BB6A;
            --light-green: #C8E6C9;
            --dark-green: #2E7D32;
            --earth-brown: #8D6E63;
            --sky-blue: #81D4FA;
            --sand-beige: #EFEBE9;
            --forest-green: #388E3C;
            --leaf-green: #7CB342;
        }
        
        /* Main container */
        .stApp {
            background: linear-gradient(135deg, #f5f7fa 0%, #e8f5e9 100%);
        }
        
        /* Sidebar */
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #c8e6c9 0%, #a5d6a7 100%);
            border-right: 3px solid var(--primary-green);
        }
        
        section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
            color: #2E7D32;
        }
        
        /* Sidebar Expanders - Jarak konsisten */
        section[data-testid="stSidebar"] [data-testid="stExpander"] {
            margin-top: 15px !important;
            margin-bottom: 15px !important;
            background: linear-gradient(145deg, rgba(255, 255, 255, 0.9), rgba(200, 230, 201, 0.5));
            border-radius: 10px;
            border: 2px solid rgba(76, 175, 80, 0.3);
            box-shadow: 2px 2px 6px rgba(76, 175, 80, 0.2);
        }
        
        section[data-testid="stSidebar"] .streamlit-expanderHeader {
            background: linear-gradient(145deg, #c8e6c9, #a5d6a7);
            border-radius: 8px;
            color: var(--dark-green);
            font-weight: 600;
            padding: 10px 15px;
        }
        
        section[data-testid="stSidebar"] .streamlit-expanderHeader:hover {
            background: linear-gradient(145deg, #a5d6a7, #81c784);
        }
        
        /* Headers */
        h1, h2, h3 {
            color: var(--dark-green) !important;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            text-shadow: 2px 2px 4px rgba(76, 175, 80, 0.1);
        }
        
        /* Buttons */
        .stButton>button {
            background: linear-gradient(145deg, #66bb6a, #4caf50);
            color: white;
            border: none;
            border-radius: 10px;
            padding: 10px 20px;
            font-weight: 600;
            box-shadow: 4px 4px 8px rgba(76, 175, 80, 0.3),
                        -4px -4px 8px rgba(200, 230, 201, 0.5);
            transition: all 0.3s ease;
        }
        
        .stButton>button:hover {
            background: linear-gradient(145deg, #4caf50, #43a047);
            box-shadow: 6px 6px 12px rgba(76, 175, 80, 0.4),
                        -6px -6px 12px rgba(200, 230, 201, 0.6);
            transform: translateY(-2px);
        }
        
        /* Input fields */
        .stTextInput>div>div>input,
        .stTextArea>div>div>textarea,
        .stSelectbox>div>div>select {
            background-color: rgba(200, 230, 201, 0.3);
            border: 2px solid var(--light-green);
            border-radius: 8px;
            color: var(--dark-green);
        }
        
        .stTextInput>div>div>input:focus,
        .stTextArea>div>div>textarea:focus,
        .stSelectbox>div>div>select:focus {
            border-color: var(--primary-green);
            box-shadow: 0 0 0 2px rgba(76, 175, 80, 0.2);
        }
        
        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            background-color: rgba(200, 230, 201, 0.3);
            border-radius: 10px;
            padding: 5px;
        }
        
        .stTabs [data-baseweb="tab"] {
            background-color: transparent;
            border-radius: 8px;
            color: var(--dark-green);
            font-weight: 600;
            padding: 10px 20px;
        }
        
        .stTabs [aria-selected="true"] {
            background: linear-gradient(145deg, #66bb6a, #4caf50);
            color: white !important;
        }
        
        /* Expanders */
        .streamlit-expanderHeader {
            background: linear-gradient(145deg, #c8e6c9, #a5d6a7);
            border-radius: 10px;
            color: var(--dark-green);
            font-weight: 600;
        }
        
        /* Metrics - HUD Nature Theme */
        [data-testid="stMetricValue"] {
            color: var(--forest-green) !important;
            font-size: 2em;
            font-weight: 700;
            text-shadow: 1px 1px 2px rgba(76, 175, 80, 0.2);
        }
        
        [data-testid="stMetricLabel"] {
            color: var(--dark-green) !important;
            font-weight: 600;
        }
        
        [data-testid="stMetricDelta"] {
            color: var(--leaf-green) !important;
        }
        
        div[data-testid="metric-container"] {
            background: linear-gradient(145deg, rgba(200, 230, 201, 0.3), rgba(165, 214, 167, 0.2));
            border: 2px solid var(--light-green);
            border-radius: 12px;
            padding: 15px;
            box-shadow: 3px 3px 8px rgba(76, 175, 80, 0.15);
        }
        
        /* Progress bar */
        .stProgress > div > div > div > div {
            background: linear-gradient(90deg, #7cb342, #66bb6a, #4caf50);
        }
        
        /* Info/Success/Warning/Error boxes - Nature HUD */
        .stAlert {
            border-radius: 12px;
            border-left: 5px solid;
            box-shadow: 2px 2px 6px rgba(0, 0, 0, 0.1);
        }
        
        /* Info - Sky Blue untuk informasi */
        [data-baseweb="notification"][kind="info"] {
            background: linear-gradient(145deg, rgba(129, 212, 250, 0.15), rgba(100, 181, 246, 0.1));
            border-left-color: #29B6F6;
            color: #01579B;
        }
        
        /* Success - Hijau alam */
        [data-baseweb="notification"][kind="success"] {
            background: linear-gradient(145deg, rgba(76, 175, 80, 0.15), rgba(102, 187, 106, 0.1));
            border-left-color: #4CAF50;
            color: #1B5E20;
        }
        
        /* Warning - Kuning matahari/autumn */
        [data-baseweb="notification"][kind="warning"] {
            background: linear-gradient(145deg, rgba(255, 193, 7, 0.15), rgba(255, 179, 0, 0.1));
            border-left-color: #FFA000;
            color: #E65100;
        }
        
        /* Error - Merah natural (buah/bunga) */
        [data-baseweb="notification"][kind="error"] {
            background: linear-gradient(145deg, rgba(244, 67, 54, 0.15), rgba(229, 57, 53, 0.1));
            border-left-color: #E53935;
            color: #B71C1C;
        }
        
        /* File uploader */
        [data-testid="stFileUploadDropzone"] {
            background: linear-gradient(145deg, #f1f8f4, #e8f5e9);
            border: 2px dashed var(--primary-green);
            border-radius: 10px;
            transition: all 0.3s ease;
        }
        
        [data-testid="stFileUploadDropzone"]:hover {
            background: linear-gradient(145deg, #e8f5e9, #c8e6c9);
            border-color: var(--forest-green);
        }
        
        /* Dataframe - Nature themed table */
        [data-testid="stDataFrame"] {
            border: 2px solid var(--light-green);
            border-radius: 10px;
        }
        
        [data-testid="stDataFrame"] table {
            background: linear-gradient(145deg, #ffffff, #f1f8f4);
        }
        
        [data-testid="stDataFrame"] thead tr {
            background: linear-gradient(145deg, #66bb6a, #4caf50);
            color: white;
        }
        
        [data-testid="stDataFrame"] tbody tr:nth-child(even) {
            background-color: rgba(200, 230, 201, 0.1);
        }
        
        [data-testid="stDataFrame"] tbody tr:hover {
            background-color: rgba(76, 175, 80, 0.1);
        }
        
        /* Chat messages */
        .stChatMessage {
            background: linear-gradient(145deg, #f1f8f4, #e8f5e9);
            border-radius: 10px;
            padding: 15px;
            margin: 10px 0;
            box-shadow: 2px 2px 5px rgba(76, 175, 80, 0.1);
            border-left: 4px solid var(--primary-green);
        }
        
        .stChatMessage[data-testid="user-message"] {
            background: linear-gradient(145deg, #c8e6c9, #a5d6a7);
            border-left-color: var(--forest-green);
        }
        
        .stChatMessage[data-testid="assistant-message"] {
            background: linear-gradient(145deg, #ffffff, #f1f8f4);
            border-left-color: var(--leaf-green);
        }
        
        /* Scrollbar */
        ::-webkit-scrollbar {
            width: 10px;
            height: 10px;
        }
        
        ::-webkit-scrollbar-track {
            background: var(--sand-beige);
            border-radius: 10px;
        }
        
        ::-webkit-scrollbar-thumb {
            background: linear-gradient(180deg, #66bb6a, #4caf50);
            border-radius: 10px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: linear-gradient(180deg, #4caf50, #43a047);
        }
        
        /* Cards effect */
        div[data-testid="stExpander"] {
            background: linear-gradient(145deg, #ffffff, #f1f8f4);
            border-radius: 12px;
            border: 2px solid var(--light-green);
            box-shadow: 4px 4px 10px rgba(76, 175, 80, 0.1);
            margin: 10px 0;
        }
        
        /* Download button - Nature themed */
        .stDownloadButton>button {
            background: linear-gradient(145deg, #7cb342, #689f38);
            color: white;
            border: none;
            border-radius: 10px;
            padding: 10px 20px;
            font-weight: 600;
            box-shadow: 4px 4px 8px rgba(124, 179, 66, 0.3);
            transition: all 0.3s ease;
        }
        
        .stDownloadButton>button:hover {
            background: linear-gradient(145deg, #689f38, #558b2f);
            box-shadow: 6px 6px 12px rgba(124, 179, 66, 0.4);
            transform: translateY(-2px);
        }
        
        /* Status badges */
        .stStatus {
            border-radius: 8px;
            padding: 5px 10px;
            font-weight: 600;
        }
        
        /* Toast notifications */
        .stToast {
            background: linear-gradient(145deg, #c8e6c9, #a5d6a7);
            border-left: 5px solid var(--primary-green);
            border-radius: 10px;
            box-shadow: 4px 4px 10px rgba(76, 175, 80, 0.2);
        }
        
        /* Spinner */
        .stSpinner > div {
            border-top-color: var(--primary-green) !important;
            border-right-color: var(--secondary-green) !important;
            border-bottom-color: var(--leaf-green) !important;
        }
        
        /* Form containers */
        [data-testid="stForm"] {
            background: linear-gradient(145deg, #ffffff, #f1f8f4);
            border: 2px solid var(--light-green);
            border-radius: 12px;
            padding: 20px;
            box-shadow: 3px 3px 8px rgba(76, 175, 80, 0.1);
        }
        
        /* Columns */
        [data-testid="column"] {
            padding: 5px;
        }
        
        /* Divider */
        hr {
            border-color: rgba(76, 175, 80, 0.2);
            margin: 20px 0;
        }
        
        /* Select box dropdown */
        [data-baseweb="select"] {
            background: rgba(200, 230, 201, 0.2);
        }
        
        /* Checkbox */
        [data-testid="stCheckbox"] {
            color: var(--dark-green);
        }
        
        input[type="checkbox"]:checked {
            background-color: var(--primary-green) !important;
            border-color: var(--primary-green) !important;
        }
        
        /* Radio buttons */
        [data-baseweb="radio"] label {
            color: var(--dark-green);
        }
        
        input[type="radio"]:checked::before {
            background-color: var(--primary-green) !important;
        }
        
        /* Number input */
        input[type="number"] {
            background-color: rgba(200, 230, 201, 0.3);
            border: 2px solid var(--light-green);
            border-radius: 8px;
            color: var(--dark-green);
        }
        
        /* Text on sidebar elements */
        section[data-testid="stSidebar"] .stSelectbox label,
        section[data-testid="stSidebar"] .stTextInput label,
        section[data-testid="stSidebar"] .stCheckbox label {
            color: var(--dark-green) !important;
            font-weight: 600;
        }
        
        /* Links */
        a {
            color: var(--forest-green) !important;
            text-decoration: none;
        }
        
        a:hover {
            color: var(--primary-green) !important;
            text-decoration: underline;
        }
        
        /* Code blocks */
        code {
            background-color: rgba(200, 230, 201, 0.3);
            color: var(--dark-green);
            padding: 2px 6px;
            border-radius: 4px;
            border: 1px solid var(--light-green);
        }
        
        pre {
            background: linear-gradient(145deg, #f1f8f4, #e8f5e9);
            border: 2px solid var(--light-green);
            border-radius: 8px;
            padding: 15px;
        }
        
        /* Markdown text */
        .stMarkdown {
            color: var(--dark-green);
        }
        
        /* Widget labels */
        label {
            color: var(--dark-green) !important;
            font-weight: 600;
        }
        
        /* Caption text */
        .stCaption {
            color: var(--earth-brown) !important;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    if 'language' not in st.session_state:
        st.session_state.language = 'id'
    if 'batch_results' not in st.session_state:
        st.session_state.batch_results = load_results_from_disk()
    if 'uploader_key' not in st.session_state:
        st.session_state.uploader_key = str(uuid.uuid4())
    if 'enable_ocr' not in st.session_state:
        st.session_state.enable_ocr = False
    
    # Sidebar
    with st.sidebar:
        display_logo_in_sidebar()
        
        st.title(get_text('config_header'))
        
        # Language selector
        lang_options = ['Indonesia', 'English']
        current_lang = 'Indonesia' if st.session_state.language == 'id' else 'English'
        st.selectbox(
            get_text('language_select'),
            lang_options,
            index=lang_options.index(current_lang),
            key='lang_selector',
            on_change=set_language
        )
        
        st.markdown("---")
        
        # OpenAI Settings
        with st.expander(get_text('openai_settings'), expanded=True):
            api_key = st.text_input(
                get_text('api_key_label'),
                type="password",
                value=st.session_state.get('openai_api_key', ''),
                help=get_text('api_key_help'),
                key='api_key_input'
            )
            if api_key:
                st.session_state.openai_api_key = api_key
        
        # OCR Settings
        if OCR_AVAILABLE:
            with st.expander(get_text('ocr_settings'), expanded=False):
                st.session_state.enable_ocr = st.checkbox(
                    get_text('enable_ocr'),
                    value=st.session_state.get('enable_ocr', False),
                    help=get_text('ocr_help')
                )
        
        st.markdown("---")
        st.info(get_text('storage_info'))
        
        # Reset button
        if st.button(get_text('reset_button'), use_container_width=True):
            st.session_state.clear()
            st.rerun()
    
    # Main content
    st.title(get_text('app_title'))
    
    # Check configuration
    missing_config = []
    if not st.session_state.get('openai_api_key'):
        missing_config.append("OpenAI API Key")
    
    if missing_config:
        st.warning(f"{get_text('warning_missing_config')}{', '.join(missing_config)}")
        st.stop()
    
    # Tabs dengan emoji nature
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
                format_func=lambda x: x.replace('_', ' ').title(),
                key='batch_selected_role'
            )
            
            with st.expander(get_text('view_skills_expander'), expanded=False):
                st.markdown(roles[role])
            
            st.markdown("---")
            
            uploaded_files = st.file_uploader(
                get_text('upload_resume_label'),
                type=['pdf'],
                accept_multiple_files=True,
                key=f"batch_uploader_{st.session_state.uploader_key}",
                help=get_text('clear_resumes_help')
            )
            
            if uploaded_files:
                st.success(f"📁 {len(uploaded_files)} {get_text('resumes_uploaded')}")
                
                col1, col2 = st.columns([3, 1])
                with col2:
                    if st.button(get_text('clear_resumes_button'), type="secondary", use_container_width=True):
                        clear_batch_resumes()
                        st.rerun()
                
                st.markdown("---")
                
                if st.button(get_text('process_all_button'), type='primary', use_container_width=True):
                    results = []
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    for idx, resume_file in enumerate(uploaded_files):
                        progress = idx / len(uploaded_files)
                        progress_bar.progress(progress)
                        status_text.text(f"{get_text('processing_status')} {idx+1}/{len(uploaded_files)}: {resume_file.name}")
                        
                        result = process_single_candidate(resume_file, role)
                        results.append(result)
                        
                        if result['ocr_used']:
                            st.info(f"🔍 {resume_file.name}: {get_text('ocr_processing')}")
                    
                    progress_bar.progress(1.0)
                    status_text.text(f"✅ {get_text('processing_complete')}")
                    
                    # Sort by match percentage
                    results.sort(key=lambda x: x.get('match_percentage', 0), reverse=True)
                    
                    # Save to session state
                    st.session_state.batch_results = results
                    save_results_to_disk()
                    
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
                                    
                                    summary = f"🌿 {get_text('processing_complete')}\n"
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
            st.markdown(f"### 🌿 {get_text('tab_upload')}")
            st.markdown(get_text('batch_info'))
    
    # TAB 4: Chatbot
    with tab4:
        display_chatbot_interface()

    # TAB 5: Role Management
    with tab5:
        display_role_management()
    


if __name__ == "__main__":
    main()
