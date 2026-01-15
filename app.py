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

client = genai.Client(api_key='AIzaSyCF3kGE1ASH8Z0Dr-lS_E4-TStHDJXJUMM')

st.set_page_config(page_title="Tableau de bord CPVO", layout="wide")

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

@st.dialog("Informations")
def name_dialog(nomLatin, nomEn):
    st.markdown(f"Nom Latin: {nomLatin}")
    st.markdown(f"Nom Anglais: {nomEn}")

@st.cache_data
def load_data():
    df = pd.read_csv('data/dataset_cleaned.csv')

    df = df[~((df['COUNTRYID'] == 'QZ') & (df['PublicationType'] == 'National Listing'))]

    df = deduplicate_within_species(df)

    df['APPLICATIONDATE'] = pd.to_datetime(df['APPLICATIONDATE'], format='%d/%m/%Y', errors='coerce')
    df['Year'] = df['APPLICATIONDATE'].dt.year

    df = df.dropna(subset=['Year'])
    df['Year'] = df['Year'].astype(int)
    df = df[df['Year'] <= 2026]

    df['Sector'] = df.apply(get_sector, axis=1)

    all_species_list = df['SPECIEID'].dropna().unique().tolist()
    df['SpecieGroup'] = df['SPECIEID'].apply(lambda x: get_specie_group(x, all_species_list))

    df['CompanyGroup'] = df['FINAL_APPLICANT'].apply(get_company_group)

    return df

df = load_data()

st.sidebar.header("Filtres")

min_year = df['Year'].min()
max_year = df['Year'].max()
year_range = st.sidebar.slider(
    "Plage d'années",
    min_value=min_year,
    max_value=max_year,
    value=(min_year, max_year)
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

st.title("Tableau de bord des variétés végétales CPVO")

pdf_figures = {}

st.markdown("**Données CPVO**")
st.markdown(f"**{len(df_filtered)}** variétés affichées sur **{len(df)}** au total")

st.header("1. Evolution temporel par type de demande")

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
if year_sub3 < 2011:
    year_sub3 = 2011

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

avg_nli = len(df_filtered[df_filtered['PublicationType'] == 'National Listing']) / (max_year - min_year)
avg_pbr =  len(df_filtered[df_filtered['PublicationType'] == 'Plant Breeders Rights']) / (max_year - min_year)
tc_nli = 100 * count_nli_max_year / count_nli_year_sub3
tc_pbr = 100 * count_pbr_max_year / count_pbr_year_sub3

col1, col2, col3, col4 = st.columns([1, 1.5, 1, 1.5])

with col1:
    st.metric("Moyenne de dépot (NLI)", f"{avg_nli:.0f}")

with col2:
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
    tc_pbr_val = round(tc_pbr - 100, 2)
    color_pbr = "#2E86AB" if tc_pbr_val >= 0 else "#E94F37"
    st.markdown(f"""
    <div style="background-color: {color_pbr}20; padding: 15px; border-radius: 10px; border-left: 4px solid {color_pbr};">
        <p style="margin: 0; font-size: 14px; color: gray;">Taux de croissance (PBR)</p>
        <p style="margin: 0; font-size: 36px; font-weight: bold; color: {color_pbr};">{tc_pbr_val:+.2f}%</p>
        <p style="margin: 0; font-size: 12px; color: gray;">{year_sub3} → {year_range[1]}</p>
    </div>
    """, unsafe_allow_html=True)


st.header("2. Top espèces et secteurs")
is_pbr_part2 = st.toggle("Vue PBR (Par défaut NLI)")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Top 15 espèces")
    df_national = df_filtered[df_filtered["PublicationType"] == ("Plant Breeders Rights" if is_pbr_part2 else "National Listing")]
    top_species = df_national['SpecieGroup'].value_counts().head(15).reset_index()

    top_species.columns = ['SpecieGroup', 'Count']

    species_names = df_filtered.groupby('SpecieGroup')['SPECIENAME'].first().reset_index()
    top_species = top_species.merge(species_names, on='SpecieGroup', how='left')

    top_species['DisplayName'] = top_species['SPECIENAME'].apply(lambda x: x[:15] if isinstance(x, str) else x)

    fig_species = px.bar(
        top_species,
        y='DisplayName',
        x='Count',
        orientation='h',
        title=f'Espèces les plus représentées ({("PBR" if is_pbr_part2 else "NLI")})',
        labels={'Count': 'Nombre de variétés', 'DisplayName': 'Espèce'},
        color='Count',
        color_continuous_scale='Blues'
    )
    fig_species.update_layout(yaxis={'categoryorder': 'total ascending'}, showlegend=False)
    pdf_figures['3. Top 15 especes'] = fig_species

    selected = st.plotly_chart(fig_species, use_container_width=True, on_select="rerun", key="species_chart")

    if selected and selected.selection and selected.selection.points:
        clicked_display_name = selected.selection.points[0]['y']

        clicked_row = top_species[top_species['DisplayName'] == clicked_display_name].iloc[0]
        clicked_species_group = clicked_row['SpecieGroup']

        species_info = df_filtered[df_filtered['SpecieGroup'] == clicked_species_group][['SPECIENAME', 'SPECIENAMEEN']].iloc[0]

        name_dialog(species_info['SPECIENAME'], species_info['SPECIENAMEEN'])

with col2:
    subcol1, subcol2 = st.columns(2)
    with subcol1:
        st.subheader("Répartition par secteur")

    with subcol2:
        is_camembert = st.toggle("Vue camembert")

    df_national = df_filtered[
        df_filtered["PublicationType"] == ("Plant Breeders Rights" if is_pbr_part2 else "National Listing")]
    sector_counts = df_national['Sector'].value_counts().reset_index()
    sector_counts.columns = ['Secteur', 'Count']

    if not is_camembert:
        fig_sectors = px.bar(
            sector_counts,
            y='Secteur',
            x='Count',
            orientation='h',
            title=f'Distribution par secteur ({("PBR" if is_pbr_part2 else "NLI")})',
            labels={'Count': 'Nombre de variétés'},
            color='Count',
            color_continuous_scale='Greens'
        )
        fig_sectors.update_layout(yaxis={'categoryorder': 'total ascending'}, showlegend=False)
        st.plotly_chart(fig_sectors, use_container_width=True)
        pdf_figures['4. Distribution par secteur'] = fig_sectors
    else:
        fig_sectors_pie = px.pie(sector_counts, values='Count', names='Secteur', title=f'Distribution par secteur ({("PBR" if is_pbr_part2 else "NLI")})')
        st.plotly_chart(fig_sectors_pie, use_container_width=True)
        pdf_figures['4. Distribution par secteur'] = fig_sectors_pie

st.header("3. Top entreprises")

is_pbr_part3 = st.toggle("Vue PBR (Par défaut NLI) ")

col1, col2 = st.columns([2, 1])

df_national = df_filtered[df_filtered["PublicationType"] == ("Plant Breeders Rights" if is_pbr_part3 else "National Listing")]

with col1:
    top_companies = df_national['CompanyGroup'].value_counts().head(10).reset_index()
    top_companies.columns = ['Entreprise', 'Count']

    fig_companies = px.bar(
        top_companies,
        y='Entreprise',
        x='Count',
        orientation='h',
        title=f'Top entreprises par nombre de demandes ({("PBR" if is_pbr_part3 else "NLI")})',
        labels={'Count': 'Nombre de dépôts'},
        color='Count',
        color_continuous_scale='Reds'
    )
    fig_companies.update_layout(yaxis={'categoryorder': 'total ascending'}, showlegend=False)
    st.plotly_chart(fig_companies, use_container_width=True)
    pdf_figures['5. Top entreprises'] = fig_companies

with col2:
    st.subheader(f'Statistiques ({("PBR" if is_pbr_part3 else "NLI")})')
    total_companies = df_national['CompanyGroup'].nunique()
    st.metric("Nombre d'entreprises", total_companies)

    avg_per_company = len(df_filtered) / total_companies if total_companies > 0 else 0
    st.metric("Moyenne par entreprise", f"{avg_per_company:.1f}")

    top_10_count = df_national['CompanyGroup'].value_counts().head(10).sum()
    concentration = top_10_count / len(df_filtered) * 100 if len(df_filtered) > 0 else 0
    st.metric("Concentration Top 10", f"{concentration:.1f}%")

st.header("4. Évolution des proportions PBR (Europe)/NLI")

df_strategy = df_filtered.groupby(['Year', 'PublicationType']).size().reset_index(name='Count')
df_strategy_pivot = df_strategy.pivot(index='Year', columns='PublicationType', values='Count').fillna(0)
df_strategy_pivot['Total'] = df_strategy_pivot.sum(axis=1)
df_strategy_pivot['PBR_Percentage'] = (df_strategy_pivot.get('Plant Breeders Rights', 0) / df_strategy_pivot['Total'] * 100).round(2)
df_strategy_pivot = df_strategy_pivot.reset_index()

fig_pbr_pct = go.Figure()

fig_pbr_pct.add_trace(go.Scatter(
    x=df_strategy_pivot['Year'],
    y=df_strategy_pivot['PBR_Percentage'],
    mode='lines+markers',
    name='% Plant Breeders Rights',
    line=dict(color='#2E86AB', width=3),
    marker=dict(size=8),
    fill='tonexty'
))

fig_pbr_pct.add_hline(y=50, line_dash="dash", line_color="gray", annotation_text="50%")

fig_pbr_pct.update_layout(
    title='Evolution des proportions de variété protégées (PBR (Europe)) parmis les variétés listés (NLI)',
    xaxis_title='Année',
    yaxis_title='% Plant Breeders Rights',
    hovermode='x unified',
    yaxis_range=[0, 100]
)

st.plotly_chart(fig_pbr_pct, use_container_width=True)
pdf_figures['6. Evolution proportions PBR/NLI'] = fig_pbr_pct

st.subheader("Evolution des proportions de variété protégées (PBR (Europe)) parmis les variétés listés (NLI) pour les 10 principales entreprises")

top_10_companies = df_filtered['CompanyGroup'].value_counts().head(10).index.tolist()
df_company_strategy = df_filtered[df_filtered['CompanyGroup'].isin(top_10_companies)]
df_company_strategy = df_company_strategy.groupby(['CompanyGroup', 'Year', 'PublicationType']).size().reset_index(name='Count')

df_company_pivot = df_company_strategy.pivot_table(
    index=['CompanyGroup', 'Year'],
    columns='PublicationType',
    values='Count',
    fill_value=0
).reset_index()

df_company_pivot['Total'] = df_company_pivot.get('Plant Breeders Rights', 0) + df_company_pivot.get('National Listing', 0)
df_company_pivot['PBR_Percentage'] = (df_company_pivot.get('Plant Breeders Rights', 0) / df_company_pivot['Total'] * 100).round(2)

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
dimension = st.multiselect(
    "Sélectionnez une ou plusieurs dimensions d'analyse:",
    options=['Entreprise', 'Secteur', 'Espèce'],
    default=['Entreprise']
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

# PDF Export in sidebar
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
            prompt = f"""Vous êtes un expert en Propriété Intellectuelle végétale. Votre mission est de croiser les variations statistiques du dashboard avec la documentation de référence (OCDE, FAO, UPOV...), le contexte politique ainsi que la conjoncture économique, afin de justifier les tendances issues des données.

Voici les données à analyser:

{csv_text}

Fournissez une analyse détaillée en français."""

            st.write("Envoi à l'IA...")

            # Call Gemini API
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt
            )

            ai_analysis = response.text

            st.write("Génération du PDF...")

            # Generate PDF with AI analysis
            pdf_ai = FPDF()
            pdf_ai.set_auto_page_break(auto=True, margin=15)
            pdf_ai.add_page()

            # Title
            pdf_ai.set_font('Helvetica', 'B', 18)
            pdf_ai.cell(0, 15, 'Analyse IA - CPVO', ln=True, align='C')
            pdf_ai.set_font('Helvetica', '', 10)
            pdf_ai.cell(0, 8, f'Date: {datetime.now().strftime("%d/%m/%Y %H:%M")}', ln=True, align='C')
            pdf_ai.cell(0, 10, '', ln=True)

            # Content
            pdf_ai.set_font('Helvetica', '', 11)

            # Handle text encoding and split into lines
            clean_text = ai_analysis.encode('latin-1', 'replace').decode('latin-1')
            pdf_ai.multi_cell(0, 6, clean_text)

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
            "Taux de croissance NLI": f"{tc_nli_val:+.2f}%",
            "Taux de croissance PBR": f"{tc_pbr_val:+.2f}%",
        }

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