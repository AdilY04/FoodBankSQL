import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
import psycopg2
from dotenv import load_dotenv
import os

# ── CONFIG ──────────────────────────────────────────────
st.set_page_config(
    page_title="LondonAid Dashboard",
    page_icon="🥫",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── CUSTOM CSS ───────────────────────────────────────────
st.markdown("""
    <style>
        /* Global background */
        .stApp {
            background-color: #0d1117;
        }

        /* Metric cards */
        [data-testid="metric-container"] {
            background-color: #161b22;
            border: 1px solid #00b4d8;
            border-radius: 12px;
            padding: 20px 24px;
        }
        [data-testid="metric-container"] label {
            color: #8b949e !important;
            font-size: 0.85rem !important;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        [data-testid="metric-container"] [data-testid="metric-value"] {
            color: #00b4d8 !important;
            font-size: 2rem !important;
            font-weight: 700 !important;
        }
        [data-testid="metric-container"] [data-testid="metric-delta"] {
            color: #f85149 !important;
        }

        /* Chart containers */
        .chart-card {
            background-color: #161b22;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #21262d;
            margin-bottom: 1rem;
        }

        /* Section titles */
        .section-title {
            color: #ffffff;
            font-size: 1rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 0.5rem;
        }

        /* Divider */
        hr {
            border-color: #21262d !important;
        }

        /* Expander */
        .streamlit-expanderHeader {
            background-color: #161b22 !important;
            color: #8b949e !important;
            border-radius: 8px !important;
        }

        /* Dataframe */
        .dataframe {
            background-color: #161b22 !important;
        }

        /* Hide streamlit branding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}

        /* Main title */
        .main-title {
            font-size: 1.8rem;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 0;
        }
        .main-subtitle {
            font-size: 0.9rem;
            color: #8b949e;
            margin-top: 4px;
        }
    </style>
""", unsafe_allow_html=True)

load_dotenv()

# ── MATPLOTLIB DARK THEME ────────────────────────────────
plt.rcParams.update({
    'figure.facecolor': '#161b22',
    'axes.facecolor': '#161b22',
    'axes.edgecolor': '#21262d',
    'axes.labelcolor': '#8b949e',
    'xtick.color': '#8b949e',
    'ytick.color': '#8b949e',
    'text.color': '#ffffff',
    'grid.color': '#21262d',
    'grid.linestyle': '--',
    'grid.alpha': 0.5
})

# ── CONNECTION ───────────────────────────────────────────
@st.cache_resource
def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        port=os.getenv("DB_PORT"),
        sslmode="require"
    )

conn = get_connection()

# ── QUERIES ──────────────────────────────────────────────
@st.cache_data
def load_depletion():
    return pd.read_sql("""
        SELECT 
            f.item_name,
            f.category,
            i.stock_quantity AS current_stock,
            SUM(ri.quantity_requested) AS total_requested,
            ROUND(SUM(ri.quantity_requested)::numeric / 
                NULLIF(i.stock_quantity, 0), 2) AS depletion_ratio
        FROM food_items f
        JOIN inventory i ON f.food_item_id = i.food_item_id
        JOIN request_items ri ON f.food_item_id = ri.food_item_id
        GROUP BY f.item_name, f.category, i.stock_quantity
        ORDER BY depletion_ratio DESC;
    """, conn)

@st.cache_data
def load_volunteer():
    return pd.read_sql("""
        SELECT 
            DATE(vs.shift_date) AS activity_date,
            COUNT(DISTINCT vs.volunteer_id) AS volunteers_on_shift,
            SUM(vs.hours_worked) AS total_volunteer_hours,
            COUNT(DISTINCT r.request_id) AS requests_handled,
            COUNT(DISTINCT CASE WHEN r.status = 'fulfilled' 
                THEN r.request_id END) AS fulfilled_requests
        FROM volunteer_shifts vs
        LEFT JOIN requests r ON DATE(vs.shift_date) = DATE(r.request_date)
        GROUP BY DATE(vs.shift_date)
        ORDER BY activity_date;
    """, conn)

@st.cache_data
def load_demand():
    return pd.read_sql("""
        SELECT 
            TO_CHAR(r.request_date, 'YYYY-MM') AS month,
            b.borough,
            COUNT(r.request_id) AS total_requests,
            SUM(ri.quantity_requested) AS total_items_requested,
            ROUND(AVG(b.household_size), 2) AS avg_household_size
        FROM requests r
        JOIN beneficiaries b ON r.beneficiary_id = b.beneficiary_id
        JOIN request_items ri ON r.request_id = ri.request_id
        GROUP BY TO_CHAR(r.request_date, 'YYYY-MM'), b.borough
        ORDER BY month, total_requests DESC;
    """, conn)

@st.cache_data
def load_borough_totals():
    return pd.read_sql("""
        SELECT 
            b.borough,
            COUNT(r.request_id) AS total_requests
        FROM requests r
        JOIN beneficiaries b ON r.beneficiary_id = b.beneficiary_id
        GROUP BY b.borough
        ORDER BY total_requests DESC;
    """, conn)

# ── LOAD DATA ────────────────────────────────────────────
df_dep = load_depletion()
df_vol = load_volunteer()
df_dem = load_demand()
df_bor = load_borough_totals()

# ── HEADER ───────────────────────────────────────────────
st.markdown('<p class="main-title">🥫 LondonAid Food Bank</p>', 
            unsafe_allow_html=True)
st.markdown('<p class="main-subtitle">Operational Analytics Dashboard — London Boroughs</p>', 
            unsafe_allow_html=True)

st.divider()

# ── KPI ROW ──────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)

k1.metric(
    label="Food Items Tracked",
    value=len(df_dep)
)
k2.metric(
    label="Critical Stock Items",
    value=int((df_dep['depletion_ratio'] > 1).sum()),
    delta=f"{int((df_dep['depletion_ratio'] > 1).sum())} need restocking",
    delta_color="inverse"
)
k3.metric(
    label="Total Volunteer Hours",
    value=int(df_vol['total_volunteer_hours'].sum())
)
k4.metric(
    label="Requests Handled",
    value=int(df_vol['requests_handled'].sum())
)

st.divider()

# ── ROW 1: DEPLETION + BOROUGH PIE ───────────────────────
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown('<p class="section-title">📦 Stock Depletion Ratio by Item</p>', 
                unsafe_allow_html=True)
    
    colors = ['#f85149' if x > 1 else '#00b4d8' for x in df_dep['depletion_ratio']]
    
    fig1, ax1 = plt.subplots(figsize=(10, 5))
    bars = ax1.barh(df_dep['item_name'], df_dep['depletion_ratio'], 
                    color=colors, height=0.6)
    ax1.axvline(x=1, color='#ffffff', linestyle='--', 
                linewidth=1, alpha=0.5, label='Critical threshold')
    ax1.set_xlabel('Depletion Ratio', color='#8b949e')
    ax1.grid(axis='x')
    ax1.legend(facecolor='#161b22', edgecolor='#21262d')
    
    critical = mpatches.Patch(color='#f85149', label='Critical')
    healthy = mpatches.Patch(color='#00b4d8', label='Healthy')
    ax1.legend(handles=[critical, healthy], 
               facecolor='#161b22', edgecolor='#21262d')
    
    plt.tight_layout()
    st.pyplot(fig1)

with col2:
    st.markdown('<p class="section-title">🗺️ Requests by Borough</p>', 
                unsafe_allow_html=True)
    
    fig2, ax2 = plt.subplots(figsize=(5, 5))
    teal_shades = ['#00b4d8', '#0096c7', '#0077b6', '#023e8a', '#03045e']
    wedges, texts, autotexts = ax2.pie(
        df_bor['total_requests'],
        labels=df_bor['borough'],
        autopct='%1.0f%%',
        colors=teal_shades,
        startangle=90,
        wedgeprops=dict(width=0.6)
    )
    for text in texts:
        text.set_color('#8b949e')
        text.set_fontsize(9)
    for autotext in autotexts:
        autotext.set_color('#ffffff')
        autotext.set_fontsize(9)
    
    plt.tight_layout()
    st.pyplot(fig2)

st.divider()

# ── ROW 2: VOLUNTEER CHART ───────────────────────────────
st.markdown('<p class="section-title">🙋 Volunteer Hours vs Fulfilled Requests</p>', 
            unsafe_allow_html=True)

fig3, ax3 = plt.subplots(figsize=(14, 4))

ax3.bar(
    df_vol['activity_date'].astype(str),
    df_vol['total_volunteer_hours'],
    color='#00b4d8', alpha=0.6, label='Volunteer Hours', width=0.5
)
ax3.set_ylabel('Volunteer Hours', color='#00b4d8')
ax3.tick_params(axis='x', rotation=45)
ax3.grid(axis='y')

ax4 = ax3.twinx()
ax4.plot(
    df_vol['activity_date'].astype(str),
    df_vol['fulfilled_requests'],
    color='#f0e68c', marker='o', linewidth=2,
    markersize=6, label='Fulfilled Requests'
)
ax4.set_ylabel('Fulfilled Requests', color='#f0e68c')
ax4.tick_params(colors='#f0e68c', axis='y')

lines1, labels1 = ax3.get_legend_handles_labels()
lines2, labels2 = ax4.get_legend_handles_labels()
ax3.legend(lines1 + lines2, labels1 + labels2,
           facecolor='#161b22', edgecolor='#21262d', loc='upper left')

plt.tight_layout()
st.pyplot(fig3)

st.divider()

# ── ROW 3: HEATMAP ───────────────────────────────────────
st.markdown('<p class="section-title">🌡️ Demand Heatmap — Borough × Month</p>', 
            unsafe_allow_html=True)

pivot = df_dem.pivot_table(
    index='borough',
    columns='month',
    values='total_requests',
    fill_value=0
)

fig5, ax5 = plt.subplots(figsize=(14, 4))
sns.heatmap(
    pivot, annot=True, fmt='d',
    cmap='YlOrRd', linewidths=0.5,
    linecolor='#0d1117',
    cbar_kws={'label': 'Requests'},
    ax=ax5
)
ax5.set_xlabel('Month', color='#8b949e')
ax5.set_ylabel('Borough', color='#8b949e')

plt.tight_layout()
st.pyplot(fig5)

st.divider()
st.caption("LondonAid Analytics Dashboard · IOT552U Assessment · Synthetic data · Built with Streamlit + Supabase")