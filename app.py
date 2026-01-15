import os

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
import unicodedata

# Configuration du client API

client = genai.Client(api_key="")


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


def generate_pdf(figures, metrics_data, year_range):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=False)

    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 24)
    pdf.cell(0, 40, '', ln=True)
    pdf.cell(0, 15, 'Tableau de bord CPVO', ln=True, align='C')
    pdf.set_font('Helvetica', '', 14)
    pdf.cell(0, 10, f'Rapport des varietes vegetales', ln=True, align='C')
    pdf.cell(0, 10, f'Periode: {year_range[0]} - {year_range[1]}', ln=True, align='C')
    pdf.cell(0, 10, f'Date: {datetime.now().strftime("%d/%m/%Y")}', ln=True, align='C')

    pdf.cell(0, 20, '', ln=True)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 10, 'Resume des indicateurs:', ln=True)
    pdf.set_font('Helvetica', '', 11)
    for key, value in metrics_data.items():
        pdf.cell(0, 8, f'  - {key}: {value}', ln=True)

    fig_list = list(figures.items())
    for i in range(0, len(fig_list), 2):
        pdf.add_page()

        title1, fig1 = fig_list[i]
        pdf.set_font('Helvetica', 'B', 11)
        pdf.set_xy(10, 10)
        pdf.cell(190, 8, title1, ln=True, align='C')
        img_bytes1 = fig1.to_image(format="png", width=900, height=400, scale=2)
        img_stream1 = BytesIO(img_bytes1)
        pdf.image(img_stream1, x=10, y=20, w=190)

        if i + 1 < len(fig_list):
            title2, fig2 = fig_list[i + 1]
            pdf.set_font('Helvetica', 'B', 11)
            pdf.set_xy(10, 145)
            pdf.cell(190, 8, title2, ln=True, align='C')
            img_bytes2 = fig2.to_image(format="png", width=900, height=400, scale=2)
            img_stream2 = BytesIO(img_bytes2)
            pdf.image(img_stream2, x=10, y=155, w=190)

    return bytes(pdf.output())


def render_markdown_to_pdf(pdf, markdown_text):
    """Render markdown text to PDF."""
    def clean_text(text):
        return text.encode('latin-1', 'replace').decode('latin-1')

    pdf.set_left_margin(15)
    pdf.set_right_margin(15)
    pdf.set_x(15)

    lines = markdown_text.split('\n')

    for line in lines:
        stripped = line.strip()

        if not stripped:
            pdf.ln(4)
            continue

        if stripped.startswith('### '):
            pdf.set_font('Helvetica', 'B', 12)
            pdf.multi_cell(180, 7, clean_text(stripped[4:]))
            pdf.ln(2)
        elif stripped.startswith('#### '):
            pdf.set_font('Helvetica', 'B', 10)
            pdf.multi_cell(180, 8, clean_text(stripped[5:]))
            pdf.ln(1)
        elif stripped.startswith('## '):
            pdf.set_font('Helvetica', 'B', 14)
            pdf.multi_cell(180, 8, clean_text(stripped[3:]))
            pdf.ln(3)
        elif stripped.startswith('# '):
            pdf.set_font('Helvetica', 'B', 16)
            pdf.multi_cell(180, 9, clean_text(stripped[2:]))
            pdf.ln(4)
        elif stripped.startswith('- ') or stripped.startswith('* '):
            pdf.set_font('Helvetica', '', 11)
            bullet_text = stripped[2:]
            bullet_text = re.sub(r'\*\*(.+?)\*\*', r'\1', bullet_text)
            pdf.set_x(20)
            pdf.multi_cell(170, 6, clean_text('- ' + bullet_text))
        elif re.match(r'^\d+\.\s', stripped):
            pdf.set_font('Helvetica', '', 11)
            list_text = re.sub(r'\*\*(.+?)\*\*', r'\1', stripped)
            pdf.set_x(20)
            pdf.multi_cell(170, 6, clean_text(list_text))
        else:
            pdf.set_font('Helvetica', '', 11)
            clean_line = re.sub(r'\*\*(.+?)\*\*', r'\1', stripped)
            clean_line = re.sub(r'\*(.+?)\*', r'\1', clean_line)
            clean_line = re.sub(r'__(.+?)__', r'\1', clean_line)
            clean_line = re.sub(r'_(.+?)_', r'\1', clean_line)
            pdf.set_x(15)
            pdf.multi_cell(180, 6, clean_text(clean_line))


@st.dialog("Informations")
def name_dialog(nomLatin, nomEn):
    st.markdown(f"**Nom Latin:** {nomLatin}")
    st.markdown(f"**Nom Anglais:** {nomEn}")


# --- CONFIGURATION INTERFACE ---

st.set_page_config(page_title="Tableau de bord CPVO", layout="wide")

# CSS for info tooltips
st.markdown("""
<style>
.title-with-info {
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: 10px;
    margin-bottom: 1rem;
}
.title-with-info h2, .title-with-info h3 {
    margin: 0;
    padding: 0;
}
.info-tooltip {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 18px;
    width: 18px;
    height: 18px;
    background-color: #e0e0e0;
    color: #555;
    border-radius: 50%;
    font-size: 12px;
    font-weight: bold;
    cursor: help;
    font-family: serif;
    font-style: italic;
    flex-shrink: 0;
}
.info-tooltip:hover {
    background-color: #2E86AB;
    color: white;
}
.info-tooltip .tooltip-text {
    visibility: hidden;
    width: 280px;
    background-color: #333;
    color: #fff;
    text-align: left;
    border-radius: 8px;
    padding: 12px;
    position: absolute;
    z-index: 1000;
    top: 125%;
    left: 50%;
    transform: translateX(-50%);
    opacity: 0;
    transition: opacity 0.3s;
    font-size: 13px;
    font-weight: normal;
    font-style: normal;
    line-height: 1.4;
    box-shadow: 0 4px 6px rgba(0,0,0,0.3);
}
.info-tooltip .tooltip-text::after {
    content: "";
    position: absolute;
    bottom: 100%;
    left: 50%;
    margin-left: -6px;
    border-width: 6px;
    border-style: solid;
    border-color: transparent transparent #333 transparent;
}
.info-tooltip:hover .tooltip-text {
    visibility: visible;
    opacity: 1;
}
.tooltip-title {
    font-weight: bold;
    margin-bottom: 6px;
    font-size: 14px;
    color: #7eb8da;
}
</style>
""", unsafe_allow_html=True)


def info_icon(title, description):
    return f'''<span class="info-tooltip">i<span class="tooltip-text"><div class="tooltip-title">{title}</div>{description}</span></span>'''


def header_with_info(level, title, info_title, info_desc):
    return f'''<div class="title-with-info"><h{level}>{title}</h{level}>{info_icon(info_title, info_desc)}</div>'''


# --- CHARGEMENT DES DONNÉES ---

@st.cache_data
def load_data(file_content=None):
    if file_content is not None:
        df = pd.read_csv(BytesIO(file_content))
    else:
        df = pd.read_csv('data/dataset_cleaned_name.csv')
    print(len(df))

    # Define the mapping for GROUPVARIETAL
    sector_mapping = {
        1.0: 'Agricultural',
        2.0: 'Vegetable',
        3.0: 'Fruit',
        4.0: 'Ornamental',
        5.0: 'Forest',
        6.0: 'Miscellaneous'
    }

    # Data Cleaning
    df = df[~((df['COUNTRYID'] == 'QZ') & (df['PublicationType'] == 'National Listing'))]
    df = deduplicate_within_species(df)

    # Date Handling - use APPLICATIONDATE, fallback to GRANTDATE if null
    app_date = pd.to_datetime(df['APPLICATIONDATE'].astype(str).str.strip(), format='%d/%m/%Y', errors='coerce')
    grant_date = pd.to_datetime(df['GRANTDATE'].astype(str).str.strip(), format='%d/%m/%Y', errors='coerce')
    df['ParsedDate'] = app_date.combine_first(grant_date)

    df['Year'] = df['ParsedDate'].dt.year
    df = df.dropna(subset=['Year'])

    df['Year'] = df['Year'].astype(int)
    df = df[df['Year'] <= datetime.now().year]

    # --- UPDATED SECTOR LOGIC ---
    # Ensure GROUPVARIETAL is numeric to match the mapping keys
    df['GROUPVARIETAL'] = pd.to_numeric(df['GROUPVARIETAL'], errors='coerce')
    df['Sector'] = df['GROUPVARIETAL'].map(sector_mapping).fillna('Unknown')
    # ----------------------------

    # Species and Company Processing
    all_species_list = df['SPECIEID'].dropna().unique().tolist()
    df['SpecieGroup'] = df['SPECIEID'].apply(lambda x: get_specie_group(x, all_species_list))
    df['SpecieGroupShort'] = df['SpecieGroup'].apply(lambda x: x[:9] if isinstance(x, str) and len(x) > 9 else x)
    df['CompanyGroup'] = df['FINAL_APPLICANT'].apply(get_company_group)
    mask = app_date.isna() & grant_date.isna()
    print(df.loc[mask, ['APPLICATIONDATE', 'GRANTDATE']].head(20))
    print(
        f"Valid app_date: {app_date.notna().sum()}, Valid grant_date: {grant_date.notna().sum()}, Combined: {df['ParsedDate'].notna().sum()}")

    return df


# --- FILE UPLOADER ---

st.sidebar.header("Source des données")
uploaded_file = st.sidebar.file_uploader(
    "Glissez-déposez un fichier CSV",
    type=['csv'],
    help="Téléchargez un fichier CSV personnalisé ou utilisez le fichier par défaut (data/dataset_cleaned.csv)"
)

if uploaded_file is not None:
    st.sidebar.success(f"Fichier chargé: {uploaded_file.name}")
    # Read file content for caching purposes
    file_content = uploaded_file.getvalue()
    df = load_data(file_content)
else:
    st.sidebar.info("Fichier par défaut: dataset_cleaned.csv")
    df = load_data(None)

# --- SIDEBAR FILTRES ---

st.sidebar.header("Filtres")

# Handle case where Year column has no valid values
year_min = df['Year'].min()
year_max = df['Year'].max()
if pd.isna(year_min) or pd.isna(year_max):
    st.error("Aucune donnée valide trouvée. Vérifiez le fichier CSV.")
    st.stop()

year_range = st.sidebar.slider(
    "Plage d'années",
    min_value=int(year_min),
    max_value=int(year_max),
    value=(int(year_min), int(year_max))
)

all_sectors = sorted([x for x in df['Sector'].unique() if pd.notna(x)])
selected_sectors = st.sidebar.multiselect(
    "Secteurs",
    options=all_sectors,
    default=all_sectors
)

all_species = sorted([x for x in df['SpecieGroup'].unique() if pd.notna(x)])
selected_species = st.sidebar.multiselect(
    "Espèces (laisser vide = toutes)",
    options=all_species,
    default=[]
)

all_applicants = sorted([x for x in df['CompanyGroup'].unique() if pd.notna(x)])
selected_applicants = st.sidebar.multiselect(
    "Entreprises (laisser vide = toutes)",
    options=all_applicants,
    default=[]
)

df_filtered = df[
    (df['Year'] >= year_range[0]) &
    (df['Year'] <= year_range[1]) &
    (df['Sector'].isin(selected_sectors))
    ].copy()

df_filtered = df_filtered.dropna(subset=['CompanyGroup', 'SpecieGroup'])

if selected_species:
    df_filtered = df_filtered[df_filtered['SpecieGroup'].isin(selected_species)]

if selected_applicants:
    df_filtered = df_filtered[df_filtered['CompanyGroup'].isin(selected_applicants)]

st.sidebar.markdown("---")
vue_donnee = st.sidebar.toggle("Vue données", value=False, help="Basculer entre les graphiques et la vue des données")

# --- CORPS PRINCIPAL ---

st.title("Tableau de bord des variétés végétales CPVO")

pdf_figures = {}

st.markdown("**Données CPVO**")
st.markdown(f"**{len(df_filtered)}** variétés affichées sur **{len(df)}** au total")

if vue_donnee:
    # Clean modern data view
    st.markdown("---")
    st.markdown(header_with_info(2, "Vue des données", "Vue données",
                                 "Cette vue présente les données filtrées sous forme de tableau interactif. Vous pouvez trier, rechercher et explorer les données en détail."),
                unsafe_allow_html=True)

    # Key metrics cards
    col1, col2, col3, col4 = st.columns(4)

    nli_count = len(df_filtered[df_filtered['PublicationType'] == 'National Listing'])
    pbr_count = len(df_filtered[df_filtered['PublicationType'] == 'Plant Breeders Rights'])
    unique_species = df_filtered['SpecieGroup'].nunique()
    unique_companies = df_filtered['CompanyGroup'].nunique()

    with col1:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #2E86AB 0%, #1a5276 100%); padding: 20px; border-radius: 12px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <p style="margin: 0; font-size: 32px; font-weight: bold; color: white;">{nli_count:,}</p>
            <p style="margin: 5px 0 0 0; font-size: 14px; color: rgba(255,255,255,0.8);">Variétés NLI</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #E94F37 0%, #c0392b 100%); padding: 20px; border-radius: 12px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <p style="margin: 0; font-size: 32px; font-weight: bold; color: white;">{pbr_count:,}</p>
            <p style="margin: 5px 0 0 0; font-size: 14px; color: rgba(255,255,255,0.8);">Variétés PBR</p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #27ae60 0%, #1e8449 100%); padding: 20px; border-radius: 12px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <p style="margin: 0; font-size: 32px; font-weight: bold; color: white;">{unique_species:,}</p>
            <p style="margin: 5px 0 0 0; font-size: 14px; color: rgba(255,255,255,0.8);">Espèces</p>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #8e44ad 0%, #6c3483 100%); padding: 20px; border-radius: 12px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <p style="margin: 0; font-size: 32px; font-weight: bold; color: white;">{unique_companies:,}</p>
            <p style="margin: 5px 0 0 0; font-size: 14px; color: rgba(255,255,255,0.8);">Entreprises</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("")

    # Data tables in tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Toutes les données", "🌱 Par espèce", "🏢 Par entreprise", "📊 Par secteur"])

    with tab1:
        # Display columns selection
        display_cols = ['DENOMINATION', 'SPECIENAME', 'CompanyGroup', 'Sector', 'PublicationType', 'Year',
                        'COUNTRYID']
        available_cols = [c for c in display_cols if c in df_filtered.columns]

        df_display = df_filtered[available_cols].copy()
        df_display.columns = ['Variété', 'Espèce', 'Entreprise', 'Secteur', 'Type', 'Année', 'Pays'][
            :len(available_cols)]

        st.dataframe(
            df_display,
            use_container_width=True,
            height=500,
            hide_index=True,
            column_config={
                "Type": st.column_config.TextColumn(
                    "Type",
                    help="National Listing: inscription au catalogue national du pays indiqué. Plant Breeders' Rights: protection pour l'ensemble de l'Union Européenne."
                )
            }
        )

        st.download_button(
            label="📥 Télécharger CSV",
            data=df_display.to_csv(index=False).encode('utf-8'),
            file_name="donnees_filtrees.csv",
            mime="text/csv"
        )

    with tab2:
        species_summary = df_filtered.groupby('SpecieGroup').agg({
            'DENOMINATION': 'count',
            'CompanyGroup': 'nunique',
            'Year': ['min', 'max']
        }).reset_index()
        species_summary.columns = ['Espèce', 'Nb variétés', 'Nb entreprises', 'Première année', 'Dernière année']
        species_summary = species_summary.sort_values('Nb variétés', ascending=False)

        st.dataframe(
            species_summary,
            use_container_width=True,
            height=500,
            hide_index=True
        )

        st.download_button(
            label="📥 Télécharger CSV",
            data=species_summary.to_csv(index=False).encode('utf-8'),
            file_name="par_espece.csv",
            mime="text/csv",
            key="download_species"
        )

    with tab3:
        company_summary = df_filtered.groupby('CompanyGroup').agg({
            'DENOMINATION': 'count',
            'SpecieGroup': 'nunique',
            'Sector': lambda x: ', '.join(x.dropna().unique()[:3]),
            'Year': ['min', 'max']
        }).reset_index()
        company_summary.columns = ['Entreprise', 'Nb variétés', 'Nb espèces', 'Secteurs', 'Première année',
                                   'Dernière année']
        company_summary = company_summary.sort_values('Nb variétés', ascending=False)

        st.dataframe(
            company_summary,
            use_container_width=True,
            height=500,
            hide_index=True
        )

        st.download_button(
            label="📥 Télécharger CSV",
            data=company_summary.to_csv(index=False).encode('utf-8'),
            file_name="par_entreprise.csv",
            mime="text/csv",
            key="download_company"
        )

    with tab4:
        sector_summary = df_filtered.groupby('Sector').agg({
            'DENOMINATION': 'count',
            'SpecieGroup': 'nunique',
            'CompanyGroup': 'nunique',
            'Year': ['min', 'max']
        }).reset_index()
        sector_summary.columns = ['Secteur', 'Nb variétés', 'Nb espèces', 'Nb entreprises', 'Première année',
                                  'Dernière année']
        sector_summary = sector_summary.sort_values('Nb variétés', ascending=False)

        st.dataframe(
            sector_summary,
            use_container_width=True,
            height=500,
            hide_index=True
        )

        st.download_button(
            label="📥 Télécharger CSV",
            data=sector_summary.to_csv(index=False).encode('utf-8'),
            file_name="par_secteur.csv",
            mime="text/csv",
            key="download_sector"
        )

    st.markdown("---")

    # Year breakdown
    st.markdown("### Répartition par année")
    year_summary = df_filtered.groupby(['Year', 'PublicationType']).size().unstack(fill_value=0)
    if 'National Listing' not in year_summary.columns:
        year_summary['National Listing'] = 0
    if 'Plant Breeders Rights' not in year_summary.columns:
        year_summary['Plant Breeders Rights'] = 0
    year_summary['Total'] = year_summary.sum(axis=1)
    year_summary = year_summary.reset_index()
    year_summary.columns = ['Année', 'NLI', 'PBR', 'Total']

    st.dataframe(
        year_summary,
        use_container_width=True,
        hide_index=True
    )

else:
    # Original graphs view
    st.markdown(header_with_info(2, "1. Evolution temporel par type de demande", "Evolution temporelle",
                                 "Ces graphiques montrent l évolution du nombre de demandes de variétés végétales au fil du temps, séparées par type: NLI (National Listing) pour les inscriptions nationales et PBR (Plant Breeders Rights) pour les droits d obtention végétale européens."),
                unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        df_protection = (
            df_filtered
            .groupby(['Year', 'PublicationType'])
            .size()
            .reset_index(name='Count')
            .loc[lambda df: df['PublicationType'] == 'National Listing']
        )

        fig_nli = px.area(
            df_protection,
            x='Year',
            y='Count',
            color='PublicationType',
            title='Evolution (NLI)',
            labels={'Count': 'Nombre de variétés', 'Year': 'Année'},
            color_discrete_map={
                'National Listing': '#2E86AB'
            }
        )
        fig_nli.update_layout(hovermode='x unified')
        fig_nli.update_xaxes(dtick=2, tickangle=45)
        st.plotly_chart(fig_nli, use_container_width=True)
        pdf_figures['1. Evolution NLI'] = fig_nli

    with col2:
        df_protection = (
            df_filtered
            .groupby(['Year', 'PublicationType'])
            .size()
            .reset_index(name='Count')
            .loc[lambda df: df['PublicationType'] == 'Plant Breeders Rights']
        )

        fig_pbr = px.area(
            df_protection,
            x='Year',
            y='Count',
            color='PublicationType',
            title='Evolution (PBR)',
            labels={'Count': 'Nombre de variétés', 'Year': 'Année'},
            color_discrete_map={
                'Plant Breeders Rights': '#E94F37'
            }
        )
        fig_pbr.update_layout(hovermode='x unified')
        fig_pbr.update_xaxes(dtick=2, tickangle=45)
        st.plotly_chart(fig_pbr, use_container_width=True)
        pdf_figures['2. Evolution PBR'] = fig_pbr

    count_nli_max_year = (
        df_filtered
        .loc[
            (df_filtered["PublicationType"] == "National Listing") &
            (df_filtered["Year"] == year_range[1])
            ]
        .shape[0]
    )

    year_sub3 = (year_range[1] - 3)
    if year_sub3 < year_range[0]:
        year_sub3 = year_range[0]

    count_nli_year_sub3 = (
        df_filtered
        .loc[
            (df_filtered["PublicationType"] == "National Listing") &
            (df_filtered["Year"] == year_sub3)
            ]
        .shape[0]
    )

    count_pbr_max_year = (
        df_filtered
        .loc[
            (df_filtered["PublicationType"] == "Plant Breeders Rights") &
            (df_filtered["Year"] == year_range[1])
            ]
        .shape[0]
    )
    count_pbr_year_sub3 = (
        df_filtered
        .loc[
            (df_filtered["PublicationType"] == "Plant Breeders Rights") &
            (df_filtered["Year"] == year_sub3)
            ]
        .shape[0]
    )

    avg_nli = len(df_filtered[df_filtered['PublicationType'] == 'National Listing']) / (
                year_range[1] - year_range[0] + 1)
    avg_pbr = len(df_filtered[df_filtered['PublicationType'] == 'Plant Breeders Rights']) / (
                year_range[1] - year_range[0] + 1)
    tc_nli = 0
    try:
        tc_nli = 100 * count_nli_max_year / count_nli_year_sub3
    except:
        tc_nli = -1000
    tc_pbr = 0
    try:
        tc_pbr = 100 * count_pbr_max_year / count_pbr_year_sub3
    except:
        tc_pbr = -1000

    col1, col2, col3, col4 = st.columns([1, 1.5, 1, 1.5])

    with col1:
        st.metric("Moyenne de dépot (NLI)", f"{avg_nli:.0f}")

    with col2:
        if tc_nli == -1000:
            color_nli = "#2E86AB"
            st.markdown(f"""
                             <div style="background-color: {color_nli}20; padding: 15px; border-radius: 10px; border-left: 4px solid {color_nli};">
                                 <p style="margin: 0; font-size: 14px; color: gray;">Taux de croissance (NLI)</p>
                                 <p style="margin: 0; font-size: 36px; font-weight: bold; color: {color_nli};">N/A</p>
                                 <p style="margin: 0; font-size: 12px; color: gray;">{year_sub3} → {year_range[1]}</p>
                             </div>
                             """, unsafe_allow_html=True)
        else:
            tc_nli_val = round(tc_nli - 100, 2)
            color_nli = "#2E86AB" if tc_nli_val >= 0 else "#E94F37"
            st.markdown(f"""
                  <div style="background-color: {color_nli}20; padding: 15px; border-radius: 10px; border-left: 4px solid {color_nli};">
                      <p style="margin: 0; font-size: 14px; color: gray;">Taux de croissance (NLI)</p>
                      <p style="margin: 0; font-size: 36px; font-weight: bold; color: {color_nli};">{tc_nli_val:+.2f}%</p>
                      <p style="margin: 0; font-size: 12px; color: gray;">{year_sub3} → {year_range[1]}</p>
                  </div>
                  """, unsafe_allow_html=True)

    with col3:
        st.metric("Moyenne de dépot (PBR)", f"{avg_pbr:.0f}")

    with col4:
        if tc_pbr == -1000:
            color_pbr = "#2E86AB"
            st.markdown(f"""
                                <div style="background-color: {color_pbr}20; padding: 15px; border-radius: 10px; border-left: 4px solid {color_pbr};">
                                    <p style="margin: 0; font-size: 14px; color: gray;">Taux de croissance (PBR)</p>
                                    <p style="margin: 0; font-size: 36px; font-weight: bold; color: {color_pbr};">N/A</p>
                                    <p style="margin: 0; font-size: 12px; color: gray;">{year_sub3} → {year_range[1]}</p>
                                </div>
                                """, unsafe_allow_html=True)
        else:
            tc_pbr_val = round(tc_pbr - 100, 2)
            color_pbr = "#2E86AB" if tc_pbr_val >= 0 else "#E94F37"
            st.markdown(f"""
                    <div style="background-color: {color_pbr}20; padding: 15px; border-radius: 10px; border-left: 4px solid {color_pbr};">
                        <p style="margin: 0; font-size: 14px; color: gray;">Taux de croissance (PBR)</p>
                        <p style="margin: 0; font-size: 36px; font-weight: bold; color: {color_pbr};">{tc_pbr_val:+.2f}%</p>
                        <p style="margin: 0; font-size: 12px; color: gray;">{year_sub3} → {year_range[1]}</p>
                    </div>
                    """, unsafe_allow_html=True)

    st.markdown(header_with_info(2, "2. Top espèces et secteurs", "Top espèces et secteurs",
                                 "Cette section présente les 15 espèces végétales les plus demandées ainsi que la répartition des demandes par secteur d activité (Agriculture, Fruits, Légumes, Ornementales). Cliquez sur une barre pour voir les détails de l espèce."),
                unsafe_allow_html=True)

    is_pbr_part2 = st.toggle("Vue PBR/NLI (Par défaut PBR)", value=True)

    col1, col2 = st.columns(2)

    with col1:
        # Calcul des tendances
        target_type = "Plant Breeders Rights" if is_pbr_part2 else "National Listing"
        trends_specie, start_yr_specie = get_volume_trend(df_filtered, 'SpecieGroupShort', year_range[1], year_range[0],
                                                          target_type)
        tooltip_specie = f"Les flèches indiquent l'évolution du volume de dépôts de l'espèce entre {start_yr_specie} et {year_range[1]}."

        st.markdown(header_with_info(3, "Top 15 espèces", "Tendances espèces", tooltip_specie), unsafe_allow_html=True)

        df_national = df_filtered[df_filtered["PublicationType"] == target_type]
        top_species = df_national['SpecieGroupShort'].value_counts().head(15).reset_index()
        top_species.columns = ['SpecieGroupShort', 'Count']

        # Fusion avec les noms et ajout de la tendance au label
        species_names = df_filtered.groupby('SpecieGroupShort')['SPECIENAME'].first().reset_index()
        top_species = top_species.merge(species_names, on='SpecieGroupShort', how='left')

        top_species['Trend'] = top_species['SpecieGroupShort'].map(trends_specie).fillna("")
        top_species['DisplayLabel'] = top_species.apply(lambda x: f"{x['Trend']} {x['SPECIENAME'][:20]}", axis=1)

        fig_species = px.bar(
            top_species,
            y='DisplayLabel',
            x='Count',
            orientation='h',
            title=f'Espèces (Evolution vs {start_yr_specie})',
            color='Count',
            color_continuous_scale='Blues',
            custom_data=['SpecieGroupShort']
        )
        fig_species.update_layout(yaxis={'categoryorder': 'total ascending'}, showlegend=False)

        # Display chart and handle clicks
        selected = st.plotly_chart(fig_species, use_container_width=True, key="species_chart", on_select="rerun")

        # Handle click events
        if selected and selected.selection and selected.selection.points:
            clicked_point = selected.selection.points[0]
            if 'customdata' in clicked_point:
                clicked_species = clicked_point['customdata'][0]

                # Get the full species info
                species_info = df_filtered[df_filtered['SpecieGroupShort'] == clicked_species].iloc[0]

                # Get Latin name (SPECIEID) and English name (SPECIENAME)
                latin_name = species_info.get('SPECIEID', 'N/A')
                english_name = species_info.get('SPECIENAME', 'N/A')

                name_dialog(latin_name, english_name)

    with col2:
        subcol1, subcol2 = st.columns(2)

        # Calcul des tendances pour les secteurs
        target_type = "Plant Breeders Rights" if is_pbr_part2 else "National Listing"
        trends_sect, start_yr_sect = get_volume_trend(df_filtered, 'Sector', year_range[1], year_range[0], target_type)
        tooltip_sect = f"Les flèches indiquent si le secteur a augmenté ou diminué en volume de dépôts entre {start_yr_sect} et {year_range[1]}."

        with subcol1:
            st.markdown(header_with_info(3, "Répartition par secteur", "Tendances secteurs", tooltip_sect),
                        unsafe_allow_html=True)

        with subcol2:
            is_camembert = st.toggle("Vue camembert")

        df_national = df_filtered[df_filtered["PublicationType"] == target_type]
        sector_counts = df_national['Sector'].value_counts().reset_index()
        sector_counts.columns = ['Secteur', 'Count']

        # Ajout de la tendance au nom du secteur
        sector_counts['Trend'] = sector_counts['Secteur'].map(trends_sect).fillna("")
        sector_counts['DisplayLabel'] = sector_counts.apply(lambda x: f"{x['Trend']} {x['Secteur']}", axis=1)

        if not is_camembert:
            fig_sectors = px.bar(
                sector_counts,
                y='DisplayLabel',
                x='Count',
                orientation='h',
                title=f'Secteurs (Evolution vs {start_yr_sect})',
                labels={'Count': 'Nombre de variétés', 'DisplayLabel': 'Secteur'},
                color='Count',
                color_continuous_scale='Greens'
            )
            fig_sectors.update_layout(yaxis={'categoryorder': 'total ascending'}, showlegend=False)
            st.plotly_chart(fig_sectors, use_container_width=True)
            pdf_figures['4. Distribution par secteur'] = fig_sectors
        else:
            # Pour le camembert, on utilise le label avec la flèche pour la légende
            fig_sectors_pie = px.pie(
                sector_counts,
                values='Count',
                names='DisplayLabel',
                title=f'Secteurs (Evolution vs {start_yr_sect})'
            )
            st.plotly_chart(fig_sectors_pie, use_container_width=True)
            pdf_figures['4. Distribution par secteur'] = fig_sectors_pie

    st.markdown(header_with_info(2, "3. Top entreprises", "Top entreprises",
                                 "Ce graphique montre les 10 entreprises ayant déposé le plus de demandes de variétés végétales. Les statistiques incluent le nombre total d entreprises, la moyenne de dépôts par entreprise et la concentration du marché (part des 10 premières entreprises)."),
                unsafe_allow_html=True)

    is_pbr_part3 = st.toggle("Vue PBR/NLI (Par défaut PBR) ", value=True)

    col1, col2 = st.columns([2, 1])

    df_national = df_filtered[
        df_filtered["PublicationType"] == ("Plant Breeders Rights" if is_pbr_part3 else "National Listing")]

    with col1:
        target_type_comp = "Plant Breeders Rights" if is_pbr_part3 else "National Listing"
        trends_comp, start_yr_comp = get_volume_trend(df_filtered, 'CompanyGroup', year_range[1], year_range[0],
                                                      target_type_comp)
        tooltip_comp = f"Les flèches indiquent l'évolution du volume de dépôts de l'entreprise entre {start_yr_comp} et {year_range[1]}."

        st.markdown(header_with_info(3, "Top entreprises", "Tendances entreprises", tooltip_comp),
                    unsafe_allow_html=True)

        top_companies = df_national['CompanyGroup'].value_counts().head(10).reset_index()
        top_companies.columns = ['Entreprise', 'Count']

        top_companies['Trend'] = top_companies['Entreprise'].map(trends_comp).fillna("")
        top_companies['DisplayLabel'] = top_companies.apply(lambda x: f"{x['Trend']} {x['Entreprise']}", axis=1)

        fig_companies = px.bar(
            top_companies,
            y='DisplayLabel',
            x='Count',
            orientation='h',
            color='Count',
            color_continuous_scale='Reds'
        )
        fig_companies.update_layout(yaxis={'categoryorder': 'total ascending'}, showlegend=False)
        st.plotly_chart(fig_companies, use_container_width=True)

    with col2:
        st.subheader(f'Statistiques ({("PBR" if is_pbr_part3 else "NLI")})')
        total_companies = df_national['CompanyGroup'].nunique()
        st.metric("Nombre d'entreprises", total_companies)

        avg_per_company = len(df_filtered) / total_companies if total_companies > 0 else 0
        st.metric("Moyenne par entreprise", f"{avg_per_company:.1f}")

        top_10_count = df_national['CompanyGroup'].value_counts().head(10).sum()
        concentration = top_10_count / len(df_filtered) * 100 if len(df_filtered) > 0 else 0
        st.metric("Concentration Top 10", f"{concentration:.1f}%")

    st.markdown(header_with_info(2, "4. Évolution des proportions PBR (Europe)/NLI", "Proportions PBR/NLI",
                                 "Ce graphique montre l'évolution du pourcentage de variétés protégées par des droits d'obtention végétale européens (PBR) parmis les inscriptions nationales (NLI). Une augmentation indique une tendance vers plus de protection intellectuelle au niveau européen. La ligne à 50% représente l équilibre entre les deux types."),
                unsafe_allow_html=True)

    # Count all NLI and PBR per year for the bars
    df_strategy = df_filtered.groupby(['Year', 'PublicationType']).size().reset_index(name='Count')
    df_strategy_pivot = df_strategy.pivot(index='Year', columns='PublicationType', values='Count').fillna(0)

    # Check if we have data to display
    has_nli = 'National Listing' in df_strategy_pivot.columns
    has_pbr = 'Plant Breeders Rights' in df_strategy_pivot.columns

    if has_nli or has_pbr:
        df_strategy_pivot['Total'] = df_strategy_pivot.sum(axis=1)
        if has_pbr:
            df_strategy_pivot['PBR_Percentage'] = (
                        df_strategy_pivot['Plant Breeders Rights'] / df_strategy_pivot['Total'] * 100).round(2)
        else:
            df_strategy_pivot['PBR_Percentage'] = 0
        df_strategy_pivot = df_strategy_pivot.reset_index()

        fig_pbr_pct = make_subplots(specs=[[{"secondary_y": True}]])

        # Bar for NLI (blue)
        if has_nli:
            fig_pbr_pct.add_trace(go.Bar(
                x=df_strategy_pivot['Year'],
                y=df_strategy_pivot['National Listing'],
                name='NLI',
                marker_color='#2E86AB',
                opacity=0.7
            ), secondary_y=False)

        # Bar for PBR (red)
        if has_pbr:
            fig_pbr_pct.add_trace(go.Bar(
                x=df_strategy_pivot['Year'],
                y=df_strategy_pivot['Plant Breeders Rights'],
                name='PBR',
                marker_color='#E94F37',
                opacity=0.7
            ), secondary_y=False)

        # Line for percentage (PBR / Total)
        fig_pbr_pct.add_trace(go.Scatter(
            x=df_strategy_pivot['Year'],
            y=df_strategy_pivot['PBR_Percentage'],
            mode='lines+markers',
            name='% PBR',
            line=dict(color='#4287f5', width=3),
            marker=dict(size=8, color='#4287f5')
        ), secondary_y=True)

        fig_pbr_pct.add_hline(y=50, line_dash="dash", line_color="gray", annotation_text="50%", secondary_y=True)

        fig_pbr_pct.update_layout(
            title='Evolution des proportions de variété protégées (PBR (Europe)) parmis les variétés listés (NLI)',
            xaxis_title='Année',
            hovermode='x unified',
            barmode='group',
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )

        fig_pbr_pct.update_yaxes(title_text='Nombre de variétés', secondary_y=False)
        fig_pbr_pct.update_yaxes(title_text='% PBR', range=[0, 100], secondary_y=True)

        st.plotly_chart(fig_pbr_pct, use_container_width=True)
        pdf_figures['6. Evolution proportions PBR/NLI'] = fig_pbr_pct
    else:
        st.info("Aucune donnée disponible pour ce graphique.")

    st.markdown(header_with_info(3,
                                 "Evolution des proportions de variété protégées (PBR) parmis les variétés listés (NLI) pour les 10 principales entreprises",
                                 "Stratégie par entreprise",
                                 "Ce graphique compare les stratégies de protection des 10 principales entreprises au fil du temps. Chaque ligne représente le pourcentage de PBR d une entreprise parmis les variétés listées (NLI), permettant d identifier les différences de stratégies de protection intellectuelle entre les acteurs du marché."),
                unsafe_allow_html=True)

    top_10_companies = df_filtered['CompanyGroup'].value_counts().head(10).index.tolist()
    df_company_strategy = df_filtered[df_filtered['CompanyGroup'].isin(top_10_companies)]
    df_company_strategy = df_company_strategy.groupby(['CompanyGroup', 'Year', 'PublicationType']).size().reset_index(
        name='Count')

    df_company_pivot = df_company_strategy.pivot_table(
        index=['CompanyGroup', 'Year'],
        columns='PublicationType',
        values='Count',
        fill_value=0
    ).reset_index()

    df_company_pivot['Total'] = df_company_pivot.get('Plant Breeders Rights', 0) + df_company_pivot.get(
        'National Listing', 0)
    df_company_pivot['PBR_Percentage'] = (
                df_company_pivot.get('Plant Breeders Rights', 0) / df_company_pivot['Total'] * 100).round(2)

    fig_strategy = px.line(
        df_company_pivot,
        x='Year',
        y='PBR_Percentage',
        color='CompanyGroup',
        title='Évolution de la stratégie PBR par entreprise (Top 10)',
        labels={'PBR_Percentage': '% Plant Breeders Rights', 'Year': 'Année', 'CompanyGroup': 'Entreprise'},
        markers=True,
        color_discrete_sequence=px.colors.qualitative.Plotly,
        template='plotly'
    )

    fig_strategy.update_layout(hovermode='x unified')
    st.plotly_chart(fig_strategy, use_container_width=True)
    pdf_figures['7. Strategie PBR par entreprise'] = fig_strategy

    st.markdown(
        f'''<div class="title-with-info"><span style="font-size: 14px; font-weight: 500;">Sélectionnez une ou plusieurs dimensions d'analyse:</span>{info_icon("Analyse détaillée", "Cette section permet d analyser en détail l évolution des demandes NLI et PBR selon différentes dimensions. Les courbes pleines représentent les NLI, les courbes en pointillés les PBR, et les courbes en points le ratio PBR/NLI. Vous pouvez combiner plusieurs dimensions pour une analyse croisée.")}</div>''',
        unsafe_allow_html=True)
    dimension = st.multiselect(
        "Dimensions:",
        options=['Entreprise', 'Secteur', 'Espèce'],
        default=['Entreprise'],
        label_visibility="collapsed"
    )

    if dimension:
        all_selected_items = {}

        for dim in dimension:
            if dim == 'Entreprise':
                group_col = 'CompanyGroup'
                top_items = df_filtered[group_col].value_counts().head(10).index.tolist()
            elif dim == 'Secteur':
                group_col = 'Sector'
                top_items = df_filtered[group_col].value_counts().index.tolist()
            else:
                group_col = 'SpecieGroup'
                top_items = df_filtered[group_col].value_counts().head(15).index.tolist()

            selected_items = st.multiselect(
                f"Sélectionnez les {dim.lower()}s à afficher:",
                options=sorted([x for x in df_filtered[group_col].unique() if pd.notna(x)]),
                default=top_items,
                key=f"select_{dim}"
            )

            if selected_items:
                all_selected_items[dim] = {'col': group_col, 'items': selected_items}

        if all_selected_items:
            # Apply filters for all selected dimensions
            df_detail = df_filtered.copy()
            for dim, config in all_selected_items.items():
                df_detail = df_detail[df_detail[config['col']].isin(config['items'])]

            # Create a combined grouping column for the chart
            if len(all_selected_items) == 1:
                # Single dimension - use it directly
                dim_name = list(all_selected_items.keys())[0]
                group_col = all_selected_items[dim_name]['col']
                df_detail['GroupKey'] = df_detail[group_col]
                selected_groups = all_selected_items[dim_name]['items']
            else:
                # Multiple dimensions - create combined labels
                cols_to_combine = [config['col'] for config in all_selected_items.values()]
                df_detail['GroupKey'] = df_detail[cols_to_combine].apply(
                    lambda x: ' - '.join(x.dropna().astype(str)), axis=1
                )
                selected_groups = df_detail['GroupKey'].unique().tolist()

            # Count NLI (National Listing)
            df_nli = df_detail[df_detail['PublicationType'] == 'National Listing'].groupby(
                ['GroupKey', 'Year']).size().reset_index(name='NLI_Count')

            # Count PBR (Plant Breeders Rights)
            df_pbr = df_detail[df_detail['PublicationType'] == 'Plant Breeders Rights'].groupby(
                ['GroupKey', 'Year']).size().reset_index(name='PBR_Count')

            # Merge both
            df_counts = df_nli.merge(df_pbr, on=['GroupKey', 'Year'], how='outer')
            df_counts['NLI_Count'] = df_counts['NLI_Count'].fillna(0)
            df_counts['PBR_Count'] = df_counts['PBR_Count'].fillna(0)

            # Calculate ratio (PBR / NLI)
            df_counts['Ratio'] = df_counts.apply(
                lambda x: (x['PBR_Count'] / x['NLI_Count']) if x['NLI_Count'] > 0 else 0,
                axis=1
            ).round(2)

            fig_detail = make_subplots(specs=[[{"secondary_y": True}]])

            # Color palette for different groups
            colors = px.colors.qualitative.Plotly

            for idx, item in enumerate(selected_groups):
                df_item = df_counts[df_counts['GroupKey'] == item]
                color = colors[idx % len(colors)]

                # NLI curve
                fig_detail.add_trace(
                    go.Scatter(
                        x=df_item['Year'],
                        y=df_item['NLI_Count'],
                        name=f'{item} (NLI)',
                        mode='lines+markers',
                        line=dict(width=2, color=color),
                        marker=dict(size=8, color=color)
                    ),
                    secondary_y=False
                )

                # PBR curve
                fig_detail.add_trace(
                    go.Scatter(
                        x=df_item['Year'],
                        y=df_item['PBR_Count'],
                        name=f'{item} (PBR)',
                        mode='lines+markers',
                        line=dict(width=2, dash='dash', color=color),
                        marker=dict(size=8, color=color, symbol='square')
                    ),
                    secondary_y=False
                )

                # Ratio curve (PBR/NLI)
                fig_detail.add_trace(
                    go.Scatter(
                        x=df_item['Year'],
                        y=df_item['Ratio'],
                        name=f'{item} (Ratio PBR/NLI)',
                        mode='lines+markers',
                        line=dict(width=2, dash='dot', color=color),
                        marker=dict(size=6, symbol='diamond', color=color),
                        opacity=0.7
                    ),
                    secondary_y=True
                )

            dimension_label = ' + '.join(dimension)
            fig_detail.update_layout(
                title=f'Évolution NLI, PBR et Ratio par {dimension_label}',
                hovermode='x unified',
                legend_title=dimension_label,
                template='plotly'
            )

            fig_detail.update_xaxes(title_text='Année')
            fig_detail.update_yaxes(title_text='Nombre de variétés', secondary_y=False)
            fig_detail.update_yaxes(title_text='Ratio PBR/NLI', secondary_y=True)

            st.plotly_chart(fig_detail, use_container_width=True)
            pdf_figures['8. Analyse detaillee'] = fig_detail
        else:
            st.warning('Veuillez sélectionner au moins un élément dans l\'une des dimensions.')
    else:
        st.warning('Veuillez sélectionner au moins une dimension d\'analyse.')

st.markdown("---")
st.markdown("*Tableau de bord basé sur les données CPVO*")

# --- SIDEBAR EXPORTS ---

st.sidebar.markdown("---")
st.sidebar.subheader("Analyse IA")
if st.sidebar.button("Résumer avec l'IA", type="secondary"):
    try:
        with st.sidebar.status("Génération de l'analyse IA...", expanded=True) as status:
            st.write("Chargement des données...")

            # Read the CSV data
            csv_data = pd.read_csv('data/fake_data.csv')
            csv_text = csv_data.to_string()

            # Prepare the prompt
            prompt = f"""
Rôle :
Vous êtes un expert senior en propriété intellectuelle végétale et analyse stratégique. Votre expertise combine le droit des obtentions végétales (système UPOV/COV), la data science et l'économie agricole mondiale. Vous travaillez en étroite collaboration avec l'OCVV, la commission européenne, l’UPOV et les offices d’examen des états membres de l’union européenne.

Objectif :
Produire une note de synthèse stratégique (Executive Briefing) de deux pages. L'enjeu est de transformer les données brutes du dashboard en renseignements exploitables en les corrélant ensuite aux cadres réglementaires (OCVV, commission européenne, UPOV) et aux réalités de terrain (entreprises de sélection végétale, OCDE, FAO).

Données d'entrée :
Données brutes permettant la réalisation du dashboard.
Documents de contexte : Références tels que des rapports annuels, traités et notes conjoncturelles.

Méthodologie d'analyse & seuil de criticité :
Analyser systématiquement le "Trend 3 ans" vs la "Moyenne Historique".
Toute variation (hausse ou baisse) supérieure ou égale à 5% est considérée comme étant significative. Si possible, cette dernière doit être expliquée et justifiée par un facteur externe (réglementaire, climatique ou économique).
 
Structure de la réponse :
"1. Résumé global
Diagnostic de la dynamique globale (croissance/stagnation/baisse ?). 
Analyse du ratio stratégique : Ratio PBR (Protection COV) vs NLI (Inscription catalogue). 
Interprétation type: Une baisse du ratio PBR indique-t-elle des changements de stratégie de protection intellectuelle pour les entreprises ? Une baisse du NLI indique-t-elle l’existence de nouvelles contraintes pour les entreprises ? 

Analyse segmentée & ruptures de tendances

Dynamique Sectorielle : Focus sur les secteurs Agri, Forest, Orna, Vege, Fruit. Identifier l’existence d’une évolution de la répartition des demandes en fonction des secteurs. 
Évolution des espèces : Identifier l’existence de la répartition des demandes en fonction des espèces. Signaler tout changement de comportement.
Analyse de la concentration du marché  : déterminer l’évolution du nombre d’entreprises qui représentent 50% du marché.

Diagnostic visuel

Interprétation analytique des graphiques et visuels du dashboard.

Justification sur la base de sources documentaires

Justifier les variations notables en citant les sources documentaires fournies (rapports annuels, traités, notes conjoncturelles). En cas d'usage de données externes (FAO, OCDE, Eurostat), la source doit être explicitement mentionnée."

Contraintes :
•    Langue : Français uniquement.
•    Ton : Institutionnel, analytique et factuel.
•    Format : markdown
•    Livrable : Une note structurée permettant au management de l'OCVV de prendre des décisions d'orientation budgétaire ou technique.
•    Source : Sources documentaires fournies. Dans le cas ou vous feriez référence à une source de données externe, précisez la source.

{csv_text}
"""


            st.write("Envoi à l'IA...")

            response = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=prompt
            )

            ai_analysis = response.text

            st.write("Génération du PDF...")

            pdf_ai = FPDF()
            pdf_ai.set_auto_page_break(auto=True, margin=15)
            pdf_ai.add_page()

            pdf_ai.set_font('Helvetica', 'B', 18)
            pdf_ai.cell(0, 15, 'Analyse IA - CPVO', ln=True, align='C')
            pdf_ai.set_font('Helvetica', '', 10)
            pdf_ai.cell(0, 8, f'Date: {datetime.now().strftime("%d/%m/%Y %H:%M")}', ln=True, align='C')
            pdf_ai.cell(0, 10, '', ln=True)

            render_markdown_to_pdf(pdf_ai, ai_analysis)

            pdf_ai_bytes = bytes(pdf_ai.output())

            status.update(label="Analyse terminée!", state="complete")

        st.sidebar.download_button(
            label="Télécharger l'analyse IA",
            data=pdf_ai_bytes,
            file_name=f"analyse_ia_cpvo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            mime="application/pdf"
        )
        st.sidebar.success("Analyse générée avec succès!")

    except Exception as e:
        st.sidebar.error(f"Erreur: {str(e)}")

st.sidebar.markdown("---")
st.sidebar.subheader("Export PDF")
if st.sidebar.button("Generer le rapport PDF", type="primary"):
    try:
        metrics_data = {
            "Varietes affichees": f"{len(df_filtered)} sur {len(df)}",
            "Periode": f"{year_range[0]} - {year_range[1]}",
            "Moyenne de depot NLI": f"{avg_nli:.0f}",
            "Moyenne de depot PBR": f"{avg_pbr:.0f}",
        }

        if tc_nli != -1000:
            metrics_data["Taux de croissance NLI"] = f"{tc_nli_val:+.2f}%"
        if tc_pbr != -1000:
            metrics_data["Taux de croissance PBR"] = f"{tc_pbr_val:+.2f}%"

        # Progress indicator
        progress_bar = st.sidebar.progress(0)
        status_text = st.sidebar.empty()

        pdf = FPDF()
        pdf.set_auto_page_break(auto=False)

        # Title page
        status_text.text("Creation de la page de titre...")
        progress_bar.progress(5)
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 24)
        pdf.cell(0, 40, '', ln=True)
        pdf.cell(0, 15, 'Tableau de bord CPVO', ln=True, align='C')
        pdf.set_font('Helvetica', '', 14)
        pdf.cell(0, 10, 'Rapport des varietes vegetales', ln=True, align='C')
        pdf.cell(0, 10, f'Periode: {year_range[0]} - {year_range[1]}', ln=True, align='C')
        pdf.cell(0, 10, f'Date: {datetime.now().strftime("%d/%m/%Y")}', ln=True, align='C')
        pdf.cell(0, 20, '', ln=True)
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 10, 'Resume des indicateurs:', ln=True)
        pdf.set_font('Helvetica', '', 11)
        for key, value in metrics_data.items():
            pdf.cell(0, 8, f'  - {key}: {value}', ln=True)

        # Add figures with progress
        fig_list = list(pdf_figures.items())
        total_figs = len(fig_list)

        for i in range(0, total_figs, 2):
            progress_pct = int(10 + (i / total_figs) * 85)
            title1, fig1 = fig_list[i]
            status_text.text(f"Rendu: {title1}...")
            progress_bar.progress(progress_pct)

            pdf.add_page()
            pdf.set_font('Helvetica', 'B', 11)
            pdf.set_xy(10, 10)
            pdf.cell(190, 8, title1, ln=True, align='C')
            img_bytes1 = fig1.to_image(format="png", width=900, height=400, scale=2)
            img_stream1 = BytesIO(img_bytes1)
            pdf.image(img_stream1, x=10, y=20, w=190)

            if i + 1 < total_figs:
                title2, fig2 = fig_list[i + 1]
                status_text.text(f"Rendu: {title2}...")
                progress_bar.progress(progress_pct + 5)

                pdf.set_font('Helvetica', 'B', 11)
                pdf.set_xy(10, 145)
                pdf.cell(190, 8, title2, ln=True, align='C')
                img_bytes2 = fig2.to_image(format="png", width=900, height=400, scale=2)
                img_stream2 = BytesIO(img_bytes2)
                pdf.image(img_stream2, x=10, y=155, w=190)

        status_text.text("Finalisation du PDF...")
        progress_bar.progress(95)
        pdf_bytes = bytes(pdf.output())

        progress_bar.progress(100)
        status_text.text("Termine!")

        st.sidebar.download_button(
            label="Telecharger le PDF",
            data=pdf_bytes,
            file_name=f"rapport_cpvo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            mime="application/pdf"
        )
        st.sidebar.success("PDF genere avec succes!")
    except Exception as e:
        st.sidebar.error(f"Erreur: {str(e)}")