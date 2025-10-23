def set_futuristic_purple_theme():
    """Ocean Light Theme - Soft & Friendly"""
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        /* ===== MAIN BACKGROUND ===== */
        .stApp {
            background: linear-gradient(180deg, 
                #67e8f9 0%,
                #22d3ee 20%,
                #06b6d4 40%,
                #0891b2 60%,
                #0e7490 100%
            );
            font-family: 'Inter', sans-serif;
        }
        
        /* ===== SIDEBAR ===== */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #22d3ee 0%, #0891b2 100%);
        }
        
        [data-testid="stSidebar"] * {
            color: #ffffff;
        }
        
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {
            color: #ffffff;
            font-weight: 700;
        }
        
        /* ===== MAIN CONTENT ===== */
        .main h1, .main h2, .main h3 {
            color: #ffffff;
            font-weight: 700;
            text-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
        }
        
        .main p, .main div, .main span, .main label {
            color: #ffffff;
        }
        
        /* ===== BUTTONS ===== */
        .stButton > button {
            background: linear-gradient(135deg, #f472b6, #ec4899);
            color: white;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            padding: 12px 24px;
            box-shadow: 0 4px 8px rgba(236, 72, 153, 0.3);
        }
        
        .stButton > button:hover {
            background: linear-gradient(135deg, #ec4899, #db2777);
            box-shadow: 0 6px 12px rgba(236, 72, 153, 0.4);
            transform: translateY(-2px);
        }
        
        /* Secondary buttons */
        .stButton > button[kind="secondary"] {
            background: rgba(255, 255, 255, 0.2);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.5);
            color: white;
        }
        
        /* Download button */
        .stDownloadButton > button {
            background: linear-gradient(135deg, #fb923c, #f97316);
            color: white;
            border: none;
            font-weight: 600;
        }
        
        /* ===== INPUTS ===== */
        .stTextInput input,
        .stTextArea textarea {
            background: rgba(255, 255, 255, 0.15);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.3);
            color: white;
            border-radius: 8px;
        }
        
        .stTextInput input::placeholder,
        .stTextArea textarea::placeholder {
            color: rgba(255, 255, 255, 0.6);
        }
        
        .stSelectbox select {
            background: rgba(255, 255, 255, 0.15);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.3);
            color: white;
        }
        
        /* ===== EXPANDERS ===== */
        .streamlit-expanderHeader {
            background: rgba(255, 255, 255, 0.2);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-radius: 8px;
            color: white;
        }
        
        .streamlit-expanderContent {
            background: rgba(255, 255, 255, 0.15);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-top: none;
            color: white;
        }
        
        /* ===== TABS ===== */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        
        .stTabs [data-baseweb="tab"] {
            background: rgba(255, 255, 255, 0.2);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-radius: 8px 8px 0 0;
            color: white;
            font-weight: 600;
        }
        
        .stTabs [data-baseweb="tab"][aria-selected="true"] {
            background: linear-gradient(135deg, #f472b6, #ec4899);
            border: 1px solid #ec4899;
            color: white;
        }
        
        /* ===== METRICS ===== */
        [data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.2);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-radius: 12px;
            padding: 20px;
        }
        
        [data-testid="stMetricValue"] {
            color: white;
            font-weight: 700;
        }
        
        [data-testid="stMetricLabel"] {
            color: rgba(255, 255, 255, 0.8);
        }
        
        /* ===== DATAFRAMES ===== */
        .dataframe {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            color: white;
        }
        
        .dataframe thead tr th {
            background: rgba(255, 255, 255, 0.25);
            color: white;
            font-weight: 700;
            border-bottom: 2px solid rgba(255, 255, 255, 0.4);
        }
        
        .dataframe tbody tr:nth-child(even) {
            background: rgba(255, 255, 255, 0.05);
        }
        
        /* ===== ALERTS ===== */
        .stInfo {
            background: rgba(14, 165, 233, 0.3);
            backdrop-filter: blur(10px);
            border-left: 4px solid #0ea5e9;
            color: white;
        }
        
        .stSuccess {
            background: rgba(34, 197, 94, 0.3);
            backdrop-filter: blur(10px);
            border-left: 4px solid #22c55e;
            color: white;
        }
        
        .stWarning {
            background: rgba(251, 146, 60, 0.3);
            backdrop-filter: blur(10px);
            border-left: 4px solid #fb923c;
            color: white;
        }
        
        .stError {
            background: rgba(239, 68, 68, 0.3);
            backdrop-filter: blur(10px);
            border-left: 4px solid #ef4444;
            color: white;
        }
        
        /* ===== FILE UPLOADER ===== */
        [data-testid="stFileUploadDropzone"] {
            background: rgba(255, 255, 255, 0.15);
            backdrop-filter: blur(10px);
            border: 2px dashed rgba(255, 255, 255, 0.4);
            border-radius: 12px;
        }
        
        /* ===== PROGRESS BAR ===== */
        .stProgress > div > div {
            background: rgba(255, 255, 255, 0.2);
        }
        
        .stProgress > div > div > div {
            background: linear-gradient(90deg, #f472b6, #ec4899);
        }
        
        </style>
    """, unsafe_allow_html=True)
