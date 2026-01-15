import streamlit as st
import pandas as pd
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.graph_objects as go
from utils import get_sector, get_specie_group, get_company_group, deduplicate_within_species
from fpdf import FPDF
from io import BytesIO
from datetime import datetime
from google import genai
import re

# Configuration du client API
client = genai.Client(api_key='VOTRE_CLE_API')


# --- FONCTIONS UTILITAIRES ---

def get_volume_trend(df, group_col, current_year, year_range_start, pub_type, lookback_years=3):
    """
    Compare le nombre brut de dépôts entre l'année actuelle et N années en arrière.
    Retourne un dictionnaire avec le symbole ▲ ou ▼.
    """
    start_year = current_year - lookback_years if current_year - lookback_years >= year_range_start else year_range_start

    # Filtrage par type (NLI ou PBR)
    df_type = df[df['PublicationType'] == pub_type]

    # Comptage par groupe pour l'année de début et de fin
    counts_start = df_type[df_type['Year'] == start_year][group_col].value_counts()
    counts_end = df_type[df_type['Year'] == current_year][group_col].value_counts()

    trends = {}
    for item in counts_end.index:
        val_end = counts_end[item]
        val_start = counts_start.get(item, 0)

        if val_end > val_start:
            trends[item] = f"▲ (+{val_end - val_start})"
        elif val_end < val_start:
            trends[item] = f"▼ ({val_end - val_start})"
        else:
            trends[item] = "="

    return trends, start_year


def render_markdown_to_pdf(pdf, markdown_text):
    def clean_text(text):
        return text.encode('latin-1', 'replace').decode('latin-1')

    pdf.set_left_margin(15)
    pdf.set_right_margin(15)
    lines = markdown_text.split('\n')
    for line in lines:
        stripped = line.strip()
        if not stripped:
            pdf.ln(4)
            continue
        if stripped.startswith('# '):
            pdf.set_font('Helvetica', 'B', 16)
            pdf.multi_cell(180, 9, clean_text(stripped[2:]))
        elif stripped.startswith('## '):
            pdf.set_font('Helvetica', 'B', 14)
            pdf.multi_cell(180, 8, clean_text(stripped[3:]))
        else:
            pdf.set_font('Helvetica', '', 11)
            clean_line = re.sub(r'\*\*(.+?)\*\*', r'\1', stripped)
            pdf.multi_cell(180, 6, clean_text(clean_line))


# --- CONFIGURATION INTERFACE ---

st.set_page_config(page_title="Tableau de bord CPVO", layout="wide")

st.markdown("""
<style>
.info-tooltip { position: relative; display: inline-flex; align-items: center; justify-content: center; min-width: 18px; width: 18px; height: 18px; background-color: #e0e0e0; color: #555; border-radius: 50%; font-size: 12px; cursor: help; margin-left: 8px; }
.info-tooltip .tooltip-text { visibility: hidden; width: 250px; background-color: #333; color: #fff; text-align: left; border-radius: 6px; padding: 10px; position: absolute; z-index: 1000; top: 125%; left: 50%; transform: translateX(-50%); opacity: 0; transition: opacity 0.3s; font-size: 12px; line-height: 1.4; }
.info-tooltip:hover .tooltip-text { visibility: visible; opacity: 1; }
.title-with-info { display: flex; align-items: center; }
</style>
""", unsafe_allow_html=True)


def header_with_info(level, title, info_title, info_desc):
    return f'''<div class="title-with-info"><h{level} style="margin:0;">{title}</h{level}><span class="info-tooltip">i<span class="tooltip-text"><b>{info_title}</b><br>{info_desc}</span></span></div>'''


# --- CHARGEMENT DES DONNÉES ---

@st.cache_data
def load_data():
    df = pd.read_csv('data/dataset_cleaned.csv')
    df = df[~((df['COUNTRYID'] == 'QZ') & (df['PublicationType'] == 'National Listing'))]
    df = deduplicate_within_species(df)
    df['APPLICATIONDATE'] = pd.to_datetime(df['APPLICATIONDATE'], format='%d/%m/%Y', errors='coerce')
    df['Year'] = df['APPLICATIONDATE'].dt.year
    df = df.dropna(subset=['Year'])
    df['Year'] = df['Year'].astype(int)
    df = df[df['Year'] <= datetime.now().year]
    df['Sector'] = df.apply(get_sector, axis=1)
    all_species_list = df['SPECIEID'].dropna().unique().tolist()
    df['SpecieGroup'] = df['SPECIEID'].apply(lambda x: get_specie_group(x, all_species_list))
    df['SpecieGroupShort'] = df['SpecieGroup'].apply(lambda x: x[:9] if isinstance(x, str) and len(x) > 9 else x)
    df['CompanyGroup'] = df['FINAL_APPLICANT'].apply(get_company_group)
    return df


df = load_data()

# --- SIDEBAR FILTRES ---

st.sidebar.header("Filtres")
year_range = st.sidebar.slider("Plage d'années", int(df['Year'].min()), int(df['Year'].max()),
                               (int(df['Year'].min()), int(df['Year'].max())))
selected_sectors = st.sidebar.multiselect("Secteurs", sorted(df['Sector'].unique()),
                                          default=list(df['Sector'].unique()))
selected_species = st.sidebar.multiselect("Espèces", sorted(df['SpecieGroup'].unique()))
selected_applicants = st.sidebar.multiselect("Entreprises", sorted(df['CompanyGroup'].unique()))

df_filtered = df[
    (df['Year'] >= year_range[0]) & (df['Year'] <= year_range[1]) & (df['Sector'].isin(selected_sectors))].copy()
if selected_species: df_filtered = df_filtered[df_filtered['SpecieGroup'].isin(selected_species)]
if selected_applicants: df_filtered = df_filtered[df_filtered['CompanyGroup'].isin(selected_applicants)]

vue_donnee = st.sidebar.toggle("Vue données", value=False)

# --- CORPS PRINCIPAL ---

st.title("Tableau de bord des variétés végétales CPVO")
pdf_figures = {}

if vue_donnee:
    st.subheader("Exploration des données")
    st.dataframe(df_filtered, use_container_width=True)
else:
    # --- SECTION 1: ÉVOLUTION ---
    st.markdown(header_with_info(2, "1. Évolution temporelle", "Volume", "Évolution annuelle des dépôts NLI et PBR."),
                unsafe_allow_html=True)
    c1, c2 = st.columns(2)

    with c1:
        df_nli_evo = df_filtered[df_filtered['PublicationType'] == 'National Listing'].groupby(
            'Year').size().reset_index(name='Count')
        fig_nli = px.area(df_nli_evo, x='Year', y='Count', title="Evolution NLI", color_discrete_sequence=['#2E86AB'])
        st.plotly_chart(fig_nli, use_container_width=True)
        pdf_figures['Evolution NLI'] = fig_nli

    with c2:
        df_pbr_evo = df_filtered[df_filtered['PublicationType'] == 'Plant Breeders Rights'].groupby(
            'Year').size().reset_index(name='Count')
        fig_pbr = px.area(df_pbr_evo, x='Year', y='Count', title="Evolution PBR", color_discrete_sequence=['#E94F37'])
        st.plotly_chart(fig_pbr, use_container_width=True)
        pdf_figures['Evolution PBR'] = fig_pbr

    # --- SECTION 2: TOP ESPÈCES & SECTEURS AVEC TENDANCES ---
    st.markdown(header_with_info(2, "2. Top espèces et secteurs", "Tendances de volume",
                                 "Les flèches indiquent si le nombre de dépôts a augmenté ou baissé par rapport à il y a 3 ans (ou l'année min sélectionnée)."),
                unsafe_allow_html=True)
    is_pbr_s2 = st.toggle("Afficher PBR (si désactivé = NLI)", value=True, key="t1")
    target_type = "Plant Breeders Rights" if is_pbr_s2 else "National Listing"

    col_s1, col_s2 = st.columns(2)

    with col_s1:
        # Tendances Espèces
        trends_sp, start_sp = get_volume_trend(df_filtered, 'SpecieGroupShort', year_range[1], year_range[0], target_type)
        df_sp = df_filtered[df_filtered['PublicationType'] == target_type]['SpecieGroupShort'].value_counts().head(
            15).reset_index()
        df_sp.columns = ['Specie', 'Count']
        df_sp['Display'] = df_sp.apply(lambda x: f"{trends_sp.get(x['Specie'], '=')} {x['Specie']}", axis=1)

        fig_sp = px.bar(df_sp, y='Display', x='Count', orientation='h', title=f"Top 15 Espèces ({target_type})",
                        color='Count', color_continuous_scale='Blues')
        fig_sp.update_layout(yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig_sp, use_container_width=True)
        pdf_figures['Top Especes'] = fig_sp

    with col_s2:
        # Tendances Secteurs
        trends_sec, start_sec = get_volume_trend(df_filtered, 'Sector', year_range[1], year_range[0], target_type)
        df_sec = df_filtered[df_filtered['PublicationType'] == target_type]['Sector'].value_counts().reset_index()
        df_sec.columns = ['Sector', 'Count']
        df_sec['Display'] = df_sec.apply(lambda x: f"{trends_sec.get(x['Sector'], '=')} {x['Sector']}", axis=1)

        fig_sec = px.bar(df_sec, y='Display', x='Count', orientation='h', title=f"Secteurs ({target_type})",
                         color='Count', color_continuous_scale='Greens')
        fig_sec.update_layout(yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig_sec, use_container_width=True)
        pdf_figures['Secteurs'] = fig_sec

    # --- SECTION 3: TOP ENTREPRISES ---
    st.markdown(
        header_with_info(2, "3. Top Entreprises", "Performance", "Classement des déposants par volume de protection."),
        unsafe_allow_html=True)
    is_pbr_s3 = st.toggle("Afficher PBR (si désactivé = NLI)", value=True, key="t2")
    target_type_comp = "Plant Breeders Rights" if is_pbr_s3 else "National Listing"

    trends_cp, start_cp = get_volume_trend(df_filtered, 'CompanyGroup', year_range[1], year_range[0], target_type_comp)
    df_cp = df_filtered[df_filtered['PublicationType'] == target_type_comp]['CompanyGroup'].value_counts().head(
        10).reset_index()
    df_cp.columns = ['Company', 'Count']
    df_cp['Display'] = df_cp.apply(lambda x: f"{trends_cp.get(x['Company'], '=')} {x['Company']}", axis=1)

    fig_cp = px.bar(df_cp, y='Display', x='Count', orientation='h', title=f"Top 10 Entreprises ({target_type_comp})",
                    color='Count', color_continuous_scale='Reds')
    fig_cp.update_layout(yaxis={'categoryorder': 'total ascending'})
    st.plotly_chart(fig_cp, use_container_width=True)
    pdf_figures['Entreprises'] = fig_cp

# --- EXPORTS ---

if st.sidebar.button("Générer Rapport PDF"):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, "Rapport CPVO Automatisé", ln=True, align='C')
    pdf.ln(10)

    for title, fig in pdf_figures.items():
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 10, title, ln=True)
        img_bytes = fig.to_image(format="png")
        img_stream = BytesIO(img_bytes)
        pdf.image(img_stream, w=170)
        pdf.add_page()

    st.sidebar.download_button("Télécharger PDF", pdf.output(dest='S'), "rapport.pdf", "application/pdf")