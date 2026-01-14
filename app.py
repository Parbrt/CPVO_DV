import streamlit as st
import pandas as pd
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.graph_objects as go
from utils import get_sector, get_specie_group

st.set_page_config(page_title="Tableau de bord CPVO", layout="wide")

@st.cache_data
def load_data():
    df = pd.read_csv('data/dataset_cleaned.csv')
    df['APPLICATIONDATE'] = pd.to_datetime(df['APPLICATIONDATE'], format='%d/%m/%Y', errors='coerce')
    df['Year'] = df['APPLICATIONDATE'].dt.year

    # Filtrer les lignes sans année valide
    df = df.dropna(subset=['Year'])
    df['Year'] = df['Year'].astype(int)

    df['Sector'] = df.apply(get_sector, axis=1)

    all_species_list = df['SPECIEID'].dropna().unique().tolist()
    df['SpecieGroup'] = df['SPECIEID'].apply(lambda x: get_specie_group(x, all_species_list))

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

all_applicants = sorted([x for x in df['FINAL_APPLICANT'].unique() if pd.notna(x)])
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

# Filtrer les NaN dans les colonnes critiques
df_filtered = df_filtered.dropna(subset=['FINAL_APPLICANT', 'SpecieGroup'])

if selected_species:
    df_filtered = df_filtered[df_filtered['SpecieGroup'].isin(selected_species)]

if selected_applicants:
    df_filtered = df_filtered[df_filtered['FINAL_APPLICANT'].isin(selected_applicants)]

st.title("Tableau de bord des variétés végétales CPVO")
st.markdown(f"**{len(df_filtered)}** variétés affichées sur **{len(df)}** au total")

st.header("1. Évolution annuelle par type de protection")

col1, col2 = st.columns([2, 1])

with col1:
    df_protection = df_filtered.groupby(['Year', 'PublicationType']).size().reset_index(name='Count')

    fig1 = px.area(
        df_protection,
        x='Year',
        y='Count',
        color='PublicationType',
        title='Évolution du nombre de variétés par type de protection',
        labels={'Count': 'Nombre de variétés', 'Year': 'Année'},
        color_discrete_map={
            'Plant Breeders Rights': '#2E86AB',
            'National Listing': '#A23B72'
        }
    )
    fig1.update_layout(hovermode='x unified')
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    total_pbr = len(df_filtered[df_filtered['PublicationType'] == 'Plant Breeders Rights'])
    total_nl = len(df_filtered[df_filtered['PublicationType'] == 'National Listing'])

    st.metric("Plant Breeders Rights", total_pbr, f"{total_pbr/(total_pbr+total_nl)*100:.1f}%")
    st.metric("National Listing", total_nl, f"{total_nl/(total_pbr+total_nl)*100:.1f}%")

    recent_years = df_filtered[df_filtered['Year'] >= max_year - 3]
    recent_pbr_pct = len(recent_years[recent_years['PublicationType'] == 'Plant Breeders Rights']) / len(recent_years) * 100 if len(recent_years) > 0 else 0
    st.metric("% PBR (3 dernières années)", f"{recent_pbr_pct:.1f}%")

st.header("2. Top espèces et secteurs")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Top 15 espèces")
    top_species = df_filtered['SpecieGroup'].value_counts().head(15).reset_index()
    top_species.columns = ['Espèce', 'Count']

    fig2 = px.bar(
        top_species,
        y='Espèce',
        x='Count',
        orientation='h',
        title='Espèces les plus représentées',
        labels={'Count': 'Nombre de variétés'},
        color='Count',
        color_continuous_scale='Blues'
    )
    fig2.update_layout(yaxis={'categoryorder': 'total ascending'}, showlegend=False)
    st.plotly_chart(fig2, use_container_width=True)

with col2:
    st.subheader("Répartition par secteur")
    sector_counts = df_filtered['Sector'].value_counts().reset_index()
    sector_counts.columns = ['Secteur', 'Count']

    fig3 = px.bar(
        sector_counts,
        y='Secteur',
        x='Count',
        orientation='h',
        title='Distribution par secteur',
        labels={'Count': 'Nombre de variétés'},
        color='Count',
        color_continuous_scale='Greens'
    )
    fig3.update_layout(yaxis={'categoryorder': 'total ascending'}, showlegend=False)
    st.plotly_chart(fig3, use_container_width=True)

st.header("3. Top entreprises en dépôts de titres")

col1, col2 = st.columns([2, 1])

with col1:
    top_companies = df_filtered['FINAL_APPLICANT'].value_counts().head(20).reset_index()
    top_companies.columns = ['Entreprise', 'Count']

    fig4 = px.bar(
        top_companies,
        y='Entreprise',
        x='Count',
        orientation='h',
        title='Top 20 entreprises par nombre de dépôts',
        labels={'Count': 'Nombre de dépôts'},
        color='Count',
        color_continuous_scale='Reds'
    )
    fig4.update_layout(yaxis={'categoryorder': 'total ascending'}, showlegend=False)
    st.plotly_chart(fig4, use_container_width=True)

with col2:
    st.subheader("Statistiques")
    total_companies = df_filtered['FINAL_APPLICANT'].nunique()
    st.metric("Nombre d'entreprises", total_companies)

    avg_per_company = len(df_filtered) / total_companies if total_companies > 0 else 0
    st.metric("Moyenne par entreprise", f"{avg_per_company:.1f}")

    top_10_count = df_filtered['FINAL_APPLICANT'].value_counts().head(10).sum()
    concentration = top_10_count / len(df_filtered) * 100 if len(df_filtered) > 0 else 0
    st.metric("Concentration Top 10", f"{concentration:.1f}%")

st.header("4. Évolution des stratégies de protection")

df_strategy = df_filtered.groupby(['Year', 'PublicationType']).size().reset_index(name='Count')
df_strategy_pivot = df_strategy.pivot(index='Year', columns='PublicationType', values='Count').fillna(0)
df_strategy_pivot['Total'] = df_strategy_pivot.sum(axis=1)
df_strategy_pivot['PBR_Percentage'] = (df_strategy_pivot.get('Plant Breeders Rights', 0) / df_strategy_pivot['Total'] * 100).round(2)
df_strategy_pivot = df_strategy_pivot.reset_index()

fig5 = go.Figure()

fig5.add_trace(go.Scatter(
    x=df_strategy_pivot['Year'],
    y=df_strategy_pivot['PBR_Percentage'],
    mode='lines+markers',
    name='% Plant Breeders Rights',
    line=dict(color='#2E86AB', width=3),
    marker=dict(size=8),
    fill='tonexty'
))

fig5.add_hline(y=50, line_dash="dash", line_color="gray", annotation_text="50%")

fig5.update_layout(
    title='Évolution de la proportion de Plant Breeders Rights vs National Listing',
    xaxis_title='Année',
    yaxis_title='% Plant Breeders Rights',
    hovermode='x unified',
    yaxis_range=[0, 100]
)

st.plotly_chart(fig5, use_container_width=True)

st.subheader("Stratégies des principales entreprises")

top_10_companies = df_filtered['FINAL_APPLICANT'].value_counts().head(10).index.tolist()
df_company_strategy = df_filtered[df_filtered['FINAL_APPLICANT'].isin(top_10_companies)]
df_company_strategy = df_company_strategy.groupby(['FINAL_APPLICANT', 'Year', 'PublicationType']).size().reset_index(name='Count')

df_company_pivot = df_company_strategy.pivot_table(
    index=['FINAL_APPLICANT', 'Year'],
    columns='PublicationType',
    values='Count',
    fill_value=0
).reset_index()

df_company_pivot['Total'] = df_company_pivot.get('Plant Breeders Rights', 0) + df_company_pivot.get('National Listing', 0)
df_company_pivot['PBR_Percentage'] = (df_company_pivot.get('Plant Breeders Rights', 0) / df_company_pivot['Total'] * 100).round(2)

fig6 = px.line(
    df_company_pivot,
    x='Year',
    y='PBR_Percentage',
    color='FINAL_APPLICANT',
    title='Évolution de la stratégie PBR par entreprise (Top 10)',
    labels={'PBR_Percentage': '% Plant Breeders Rights', 'Year': 'Année', 'FINAL_APPLICANT': 'Entreprise'},
    markers=True
)

fig6.update_layout(hovermode='x unified')
st.plotly_chart(fig6, use_container_width=True)

st.header("5. Analyse détaillée temporelle")

dimension = st.selectbox(
    "Sélectionnez une dimension d'analyse:",
    options=['Entreprise', 'Secteur', 'Espèce']
)

if dimension == 'Entreprise':
    group_col = 'FINAL_APPLICANT'
    top_items = df_filtered[group_col].value_counts().head(10).index.tolist()
elif dimension == 'Secteur':
    group_col = 'Sector'
    top_items = df_filtered[group_col].value_counts().index.tolist()
else:
    group_col = 'SpecieGroup'
    top_items = df_filtered[group_col].value_counts().head(15).index.tolist()

selected_items = st.multiselect(
    f"Sélectionnez les {dimension.lower()}s à afficher:",
    options=sorted([x for x in df_filtered[group_col].unique() if pd.notna(x)]),
    default=top_items
)

if selected_items:
    df_detail = df_filtered[df_filtered[group_col].isin(selected_items)]
    df_counts = df_detail.groupby([group_col, 'Year']).size().reset_index(name='Count')

    df_pbr = df_detail[df_detail['PublicationType'] == 'Plant Breeders Rights'].groupby([group_col, 'Year']).size().reset_index(name='PBR_Count')
    df_counts = df_counts.merge(df_pbr, on=[group_col, 'Year'], how='left')
    df_counts['PBR_Count'] = df_counts['PBR_Count'].fillna(0)
    df_counts['PBR_Percentage'] = (df_counts['PBR_Count'] / df_counts['Count'] * 100).round(2)

    fig7 = make_subplots(specs=[[{"secondary_y": True}]])

    for item in selected_items:
        df_item = df_counts[df_counts[group_col] == item]

        fig7.add_trace(
            go.Scatter(
                x=df_item['Year'],
                y=df_item['Count'],
                name=item,
                mode='lines+markers',
                line=dict(width=2),
                marker=dict(size=8)
            ),
            secondary_y=False
        )

        fig7.add_trace(
            go.Scatter(
                x=df_item['Year'],
                y=df_item['PBR_Percentage'],
                name=f'{item} (PBR %)',
                mode='lines+markers',
                line=dict(width=2, dash='dot'),
                marker=dict(size=6, symbol='diamond'),
                opacity=0.7
            ),
            secondary_y=True
        )

    fig7.update_layout(
        title=f'Évolution temporelle par {dimension.lower()} avec % Plant Breeders Rights',
        hovermode='x unified',
        legend_title=dimension
    )

    fig7.update_xaxes(title_text='Année')
    fig7.update_yaxes(title_text='Nombre de variétés', secondary_y=False)
    fig7.update_yaxes(title_text='% Plant Breeders Rights', secondary_y=True)

    st.plotly_chart(fig7, use_container_width=True)
else:
    st.warning('Veuillez sélectionner au moins un élément.')

st.markdown("---")
st.markdown("*Tableau de bord basé sur les données CPVO*")
