def set_futuristic_purple_theme():
    """Ocean Clean Theme - Simple & Stable"""
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        /* ===== MAIN BACKGROUND ===== */
        .stApp {
            background: linear-gradient(180deg, 
                #0891B2 0%,
                #0E7490 25%,
                #155E75 50%,
                #164E63 75%,
                #0F3B47 100%
            );
            font-family: 'Inter', sans-serif;
        }
        
        /* ===== SIDEBAR ===== */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0891B2 0%, #0E7490 100%);
        }
        
        [data-testid="stSidebar"] * {
            color: #ffffff;
        }
        
        /* ===== MAIN CONTENT TEXT ===== */
        .main * {
            color: #ffffff;
        }
        
        /* ===== BUTTONS ===== */
        .stButton > button {
            background: linear-gradient(135deg, #06B6D4, #0891B2);
            color: white;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            padding: 12px 24px;
        }
        
        .stButton > button:hover {
            background: linear-gradient(135deg, #22D3EE, #06B6D4);
            box-shadow: 0 4px 12px rgba(6, 182, 212, 0.4);
        }
        
        /* ===== INPUTS ===== */
        .stTextInput input,
        .stTextArea textarea,
        .stSelectbox select {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(6, 182, 212, 0.5);
            color: white;
            border-radius: 6px;
        }
        
        /* ===== EXPANDERS ===== */
        .streamlit-expanderHeader {
            background: rgba(6, 182, 212, 0.2);
            border: 1px solid rgba(6, 182, 212, 0.5);
            border-radius: 6px;
            color: white;
        }
        
        .streamlit-expanderContent {
            background: rgba(6, 182, 212, 0.1);
            border: 1px solid rgba(6, 182, 212, 0.3);
            border-top: none;
        }
        
        /* ===== TABS ===== */
        .stTabs [data-baseweb="tab"] {
            color: white;
            background: rgba(6, 182, 212, 0.2);
        }
        
        .stTabs [data-baseweb="tab"][aria-selected="true"] {
            background: linear-gradient(135deg, #F472B6, #EC4899);
            color: white;
        }
        
        /* ===== METRICS ===== */
        [data-testid="stMetric"] {
            background: rgba(6, 182, 212, 0.2);
            border: 1px solid rgba(6, 182, 212, 0.5);
            border-radius: 8px;
            padding: 16px;
        }
        
        /* ===== DATAFRAMES ===== */
        .dataframe {
            color: white;
        }
        
        .dataframe thead tr th {
            background: #0891B2;
            color: white;
        }
        
        /* ===== ALERTS ===== */
        .stAlert {
            color: white;
        }
        
        </style>
    """, unsafe_allow_html=True)
