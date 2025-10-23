# 🤖 AI Recruitment System

Sistem rekrutmen berbasis AI untuk menganalisa CV/resume secara otomatis menggunakan OpenAI GPT-4.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://your-app-url.streamlit.app)

## 🌟 Fitur Utama

### ✅ Analisa Resume Otomatis
- Upload PDF resume (single atau batch)
- Analisa menggunakan AI (GPT-4)
- Scoring & rekomendasi otomatis
- Support OCR untuk PDF scan

### 📥 Import dari Excel
- Import kandidat dari file Excel
- Auto-download CV dari URL
- Support Google Drive, Dropbox, direct links
- Batch processing multiple kandidat

### 💬 Chat dengan AI Recruiter
- Tanya jawab tentang kandidat
- Analisa perbandingan kandidat
- Rekomendasi rekrutmen

### 📊 Manajemen Posisi
- Kelola posisi pekerjaan
- Custom requirements per posisi
- Export/import posisi

### 📈 Hasil & Laporan
- View hasil analisa lengkap
- Filter & sort kandidat
- Export ke Excel
- Dashboard ringkasan

## 🚀 Demo

Aplikasi live: [https://your-app-url.streamlit.app](https://your-app-url.streamlit.app)

## 📋 Requirements

- Python 3.8+
- OpenAI API Key (untuk AI features)
- Internet connection

## 🔧 Installation & Setup

### Option 1: Streamlit Cloud (Recommended)

1. Fork/Clone repository ini
2. Deploy ke Streamlit Cloud
3. Set OpenAI API key di Secrets (optional)
4. Done! ✅

### Option 2: Local Development

```bash
# Clone repository
git clone https://github.com/yourusername/ai-recruitment-system.git
cd ai-recruitment-system

# Install dependencies
pip install -r requirements.txt

# Run aplikasi
streamlit run agen_hiring.py
```

Aplikasi akan buka di: http://localhost:8501

## ⚙️ Configuration

### OpenAI API Key

Ada 2 cara setup API key:

**Option 1: Via Streamlit Secrets (Recommended untuk production)**

Buat file `.streamlit/secrets.toml`:
```toml
OPENAI_API_KEY = "sk-your-api-key-here"
```

**Option 2: Via Sidebar (User input)**

User bisa input API key di sidebar setiap session.

### Google Drive Files

Jika menggunakan fitur download dari Excel dengan Google Drive links:

1. Buka Google Drive
2. Klik kanan folder/file → Share
3. Ubah ke: "Anyone with the link"
4. Permission: "Viewer"
5. Done!

Aplikasi akan otomatis convert Google Drive links ke direct download format.

## 📖 User Guide

### 1. Setup Posisi

1. Buka tab "Kelola Posisi"
2. Klik "➕ Tambah Posisi Baru"
3. Isi ID dan persyaratan
4. Save

### 2. Upload & Analisa Resume

**Manual Upload:**
1. Tab "Unggah & Proses"
2. Pilih posisi
3. Upload PDF (bisa multiple)
4. Klik "🚀 Proses Semua Resume"

**Via Excel:**
1. Tab "📥 Download dari Excel"
2. Upload Excel dengan kolom: Nama, Link CV
3. Klik "Download & Proses Semua CV"

### 3. View Hasil

1. Tab "Hasil & Ringkasan"
2. Filter & sort kandidat
3. Export ke Excel jika perlu

### 4. Chat dengan AI

1. Tab "💬 Chat dengan AI"
2. Tanya tentang kandidat atau minta rekomendasi
3. AI akan memberikan insights

## 🔒 Privacy & Security

- ✅ Data disimpan lokal (session-based)
- ✅ No data dikirim ke server lain (kecuali OpenAI untuk analisa)
- ✅ API keys tidak di-log
- ✅ File temporary only (tidak disimpan permanent)
- ✅ GDPR compliant

## 🛠️ Tech Stack

- **Framework:** Streamlit
- **AI Model:** OpenAI GPT-4o
- **PDF Processing:** PyPDF2
- **OCR:** Tesseract (optional)
- **Data:** Pandas, JSON
- **Agent Framework:** Phidata

## 📦 Project Structure

```
ai-recruitment-system/
├── agen_hiring.py          # Main application
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── .gitignore             # Git ignore rules
├── .streamlit/
│   └── config.toml        # Streamlit configuration
└── recruitment_data/      # Data storage (auto-created)
    ├── roles.json
    ├── analysis_memory.json
    ├── batch_results.json
    └── chat_history.json
```

## 🐛 Troubleshooting

### Google Drive Files Error

**Problem:** "File bukan PDF valid" atau "Download error"

**Solution:** 
- Pastikan file di-set PUBLIC
- Cek link accessible (test di browser incognito)
- Aplikasi auto-convert Google Drive links

### API Key Invalid

**Problem:** "OpenAI API Key invalid"

**Solution:**
- Cek API key di: https://platform.openai.com/api-keys
- Pastikan API key ada credit
- Hapus spasi di awal/akhir key

### Module Not Found

**Problem:** Import errors

**Solution:**
```bash
pip install -r requirements.txt --upgrade
```

## 📊 Features Roadmap

- [x] Basic resume analysis
- [x] Batch processing
- [x] Excel import
- [x] Google Drive support
- [x] Chat with AI
- [x] Export results
- [ ] Advanced analytics dashboard
- [ ] Email notifications
- [ ] Candidate tracking system
- [ ] Integration with ATS
- [ ] Multi-language support

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 👤 Author

**PT Srikandi Mitra Karya**

## 🙏 Acknowledgments

- OpenAI for GPT-4 API
- Streamlit for amazing framework
- Phidata for agent framework
- All contributors

## 📞 Support

Untuk pertanyaan atau support:
- 📧 Email: support@example.com
- 🐛 Issues: [GitHub Issues](https://github.com/yourusername/ai-recruitment-system/issues)
- 📖 Docs: [Documentation](https://github.com/yourusername/ai-recruitment-system/wiki)

---

⭐ Star this repo if you find it helpful!

Made with ❤️ using Streamlit
