import streamlit as st
import pandas as pd
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.graph_objects as go
from utils import get_sector, get_specie_group, get_company_group, deduplicate_within_species

st.set_page_config(page_title="Tableau de bord CPVO", layout="wide")

@st.dialog("Informations")
def name_dialog(nomLatin, nomEn):
    st.markdown(f"Nom Latin: {nomLatin}")
    st.markdown(f"Nom Anglais: {nomEn}")

@st.cache_data
def load_data():
    df = pd.read_csv('data/dataset_cleaned.csv')

    df = df[~((df['COUNTRYID'] == 'QZ') & (df['PublicationType'] == 'National Listing'))]

    initial_count = len(df)
    df = deduplicate_within_species(df)
    dedup_count = len(df)

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

# Filtrer les NaN dans les colonnes critiques
df_filtered = df_filtered.dropna(subset=['CompanyGroup', 'SpecieGroup'])

if selected_species:
    df_filtered = df_filtered[df_filtered['SpecieGroup'].isin(selected_species)]

if selected_applicants:
    df_filtered = df_filtered[df_filtered['CompanyGroup'].isin(selected_applicants)]

st.title("Tableau de bord des variétés végétales CPVO")
st.markdown("**Données CPVO** (National Listing de QZ exclus, dédupliquées par BREEDERREFERENCE/DENOMINATION au sein de chaque espèce)")
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

    fig1 = px.area(
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
    fig1.update_layout(hovermode='x unified')
    fig1.update_xaxes(dtick=2, tickangle=45)
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    df_protection = (
        df_filtered
        .groupby(['Year', 'PublicationType'])
        .size()
        .reset_index(name='Count')
        .loc[lambda df: df['PublicationType'] == 'Plant Breeders Rights']
    )

    fig1 = px.area(
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
    fig1.update_layout(hovermode='x unified')
    fig1.update_xaxes(dtick=2, tickangle=45)
    st.plotly_chart(fig1, use_container_width=True)


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

    fig2 = px.bar(
        top_species,
        y='DisplayName',
        x='Count',
        orientation='h',
        title=f'Espèces les plus représentées ({("PBR" if is_pbr_part2 else "NLI")})',
        labels={'Count': 'Nombre de variétés', 'DisplayName': 'Espèce'},
        color='Count',
        color_continuous_scale='Blues'
    )
    fig2.update_layout(yaxis={'categoryorder': 'total ascending'}, showlegend=False)

    selected = st.plotly_chart(fig2, use_container_width=True, on_select="rerun", key="species_chart")

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
        fig3 = px.bar(
            sector_counts,
            y='Secteur',
            x='Count',
            orientation='h',
            title=f'Distribution par secteur ({("PBR" if is_pbr_part2 else "NLI")})',
            labels={'Count': 'Nombre de variétés'},
            color='Count',
            color_continuous_scale='Greens'
        )
        fig3.update_layout(yaxis={'categoryorder': 'total ascending'}, showlegend=False)
        st.plotly_chart(fig3, use_container_width=True)
    else:
       data_fig4 = px.pie(sector_counts, values='Count', names='Secteur', title=f'Distribution par secteur ({("PBR" if is_pbr_part2 else "NLI")})')
       st.plotly_chart(data_fig4, use_container_width=True)

st.header("3. Top entreprises")

is_pbr_part3 = st.toggle("Vue PBR (Par défaut NLI) ")

col1, col2 = st.columns([2, 1])

df_national = df_filtered[df_filtered["PublicationType"] == ("Plant Breeders Rights" if is_pbr_part3 else "National Listing")]

with col1:
    top_companies = df_national['CompanyGroup'].value_counts().head(10).reset_index()
    top_companies.columns = ['Entreprise', 'Count']

    fig4 = px.bar(
        top_companies,
        y='Entreprise',
        x='Count',
        orientation='h',
        title=f'Top entreprises par nombre de demandes ({("PBR" if is_pbr_part3 else "NLI")})',
        labels={'Count': 'Nombre de dépôts'},
        color='Count',
        color_continuous_scale='Reds'
    )
    fig4.update_layout(yaxis={'categoryorder': 'total ascending'}, showlegend=False)
    st.plotly_chart(fig4, use_container_width=True)

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
    title='Evolution des proportions de variété protégées (PBR (Europe)) parmis les variétés listés (NLI)',
    xaxis_title='Année',
    yaxis_title='% Plant Breeders Rights',
    hovermode='x unified',
    yaxis_range=[0, 100]
)

st.plotly_chart(fig5, use_container_width=True)

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

fig6 = px.line(
    df_company_pivot,
    x='Year',
    y='PBR_Percentage',
    color='CompanyGroup',
    title='Évolution de la stratégie PBR par entreprise (Top 10)',
    labels={'PBR_Percentage': '% Plant Breeders Rights', 'Year': 'Année', 'CompanyGroup': 'Entreprise'},
    markers=True
)

fig6.update_layout(hovermode='x unified')
st.plotly_chart(fig6, use_container_width=True)
dimension = st.multiselect(
    "Sélectionnez une ou plusieurs dimensions d'analyse:",
    options=['Entreprise', 'Secteur', 'Espèce'],
    default=['Entreprise']
)

if dimension:
    # Dictionary to store selections for each dimension
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

        fig7 = make_subplots(specs=[[{"secondary_y": True}]])

        for item in selected_groups:
            df_item = df_counts[df_counts['GroupKey'] == item]

            # NLI curve
            fig7.add_trace(
                go.Scatter(
                    x=df_item['Year'],
                    y=df_item['NLI_Count'],
                    name=f'{item} (NLI)',
                    mode='lines+markers',
                    line=dict(width=2),
                    marker=dict(size=8)
                ),
                secondary_y=False
            )

            # PBR curve
            fig7.add_trace(
                go.Scatter(
                    x=df_item['Year'],
                    y=df_item['PBR_Count'],
                    name=f'{item} (PBR)',
                    mode='lines+markers',
                    line=dict(width=2, dash='dash'),
                    marker=dict(size=8)
                ),
                secondary_y=False
            )

            # Ratio curve (PBR/NLI)
            fig7.add_trace(
                go.Scatter(
                    x=df_item['Year'],
                    y=df_item['Ratio'],
                    name=f'{item} (Ratio PBR/NLI)',
                    mode='lines+markers',
                    line=dict(width=2, dash='dot'),
                    marker=dict(size=6, symbol='diamond'),
                    opacity=0.7
                ),
                secondary_y=True
            )

        dimension_label = ' + '.join(dimension)
        fig7.update_layout(
            title=f'Évolution NLI, PBR et Ratio par {dimension_label}',
            hovermode='x unified',
            legend_title=dimension_label
        )

        fig7.update_xaxes(title_text='Année')
        fig7.update_yaxes(title_text='Nombre de variétés', secondary_y=False)
        fig7.update_yaxes(title_text='Ratio PBR/NLI', secondary_y=True)

        st.plotly_chart(fig7, use_container_width=True)
    else:
        st.warning('Veuillez sélectionner au moins un élément dans l\'une des dimensions.')
else:
    st.warning('Veuillez sélectionner au moins une dimension d\'analyse.')

st.markdown("---")
st.markdown("*Tableau de bord basé sur les données CPVO*")