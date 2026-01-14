import streamlit as st
import pandas as pd
from plotly.subplots import make_subplots
import plotly.graph_objects as go
from utils import get_sector, get_specie_group

@st.cache_data
def load_data():
    df = pd.read_csv('data/dataset_cleaned.csv')
    df['APPLICATIONDATE'] = pd.to_datetime(df['APPLICATIONDATE'], format='%d/%m/%Y', errors='coerce')
    df['Year'] = df['APPLICATIONDATE'].dt.year
    return df

df = load_data()

df['Sector'] = df.apply(get_sector, axis=1)

all_species_list = df['SPECIEID'].dropna().unique().tolist()
df['SpecieGroup'] = df['SPECIEID'].apply(lambda x: get_specie_group(x, all_species_list))

view_mode = st.radio(
    'Mode de visualisation:',
    options=['Par Entreprise', 'Par Secteur', 'Par Espèce'],
    horizontal=True
)

if view_mode == 'Par Entreprise':
    df_counts = df.groupby(['FINAL_APPLICANT', 'Year']).size().reset_index(name='Count')

    df_pbr = df[df['PublicationType'] == 'Plant Breeders Rights'].groupby(['FINAL_APPLICANT', 'Year']).size().reset_index(name='PBR_Count')
    df_counts = df_counts.merge(df_pbr, on=['FINAL_APPLICANT', 'Year'], how='left')
    df_counts['PBR_Count'] = df_counts['PBR_Count'].fillna(0)
    df_counts['PBR_Percentage'] = (df_counts['PBR_Count'] / df_counts['Count'] * 100).round(2)

    all_applicants = sorted(df_counts['FINAL_APPLICANT'].unique())
    top_applicants = df_counts.groupby('FINAL_APPLICANT')['Count'].sum().nlargest(5).index.tolist()

    selected_items = st.multiselect(
        'Entreprises sélectionées:',
        options=all_applicants,
        default=top_applicants,
        key='applicants'
    )

    group_col = 'FINAL_APPLICANT'
    title = 'Nombre de demandes par entreprises et par années avec % Plant Breeders Rights'
    legend_title = 'Entreprises'

elif view_mode == 'Par Secteur':
    df_counts = df.groupby(['Sector', 'Year']).size().reset_index(name='Count')

    df_pbr = df[df['PublicationType'] == 'Plant Breeders Rights'].groupby(['Sector', 'Year']).size().reset_index(name='PBR_Count')
    df_counts = df_counts.merge(df_pbr, on=['Sector', 'Year'], how='left')
    df_counts['PBR_Count'] = df_counts['PBR_Count'].fillna(0)
    df_counts['PBR_Percentage'] = (df_counts['PBR_Count'] / df_counts['Count'] * 100).round(2)

    all_sectors = sorted(df_counts['Sector'].unique())

    selected_items = st.multiselect(
        'Secteurs sélectionnés:',
        options=all_sectors,
        default=all_sectors,
        key='sectors'
    )

    group_col = 'Sector'
    title = 'Nombre de demandes par secteurs et par années avec % Plant Breeders Rights'
    legend_title = 'Secteurs'

else:
    df_counts = df.groupby(['SpecieGroup', 'Year']).size().reset_index(name='Count')

    df_pbr = df[df['PublicationType'] == 'Plant Breeders Rights'].groupby(['SpecieGroup', 'Year']).size().reset_index(name='PBR_Count')
    df_counts = df_counts.merge(df_pbr, on=['SpecieGroup', 'Year'], how='left')
    df_counts['PBR_Count'] = df_counts['PBR_Count'].fillna(0)
    df_counts['PBR_Percentage'] = (df_counts['PBR_Count'] / df_counts['Count'] * 100).round(2)

    top_species = df_counts.groupby('SpecieGroup')['Count'].sum().nlargest(10).index.tolist()

    selected_items = st.multiselect(
        'Espèces sélectionnées:',
        options=sorted(df_counts['SpecieGroup'].unique()),
        default=top_species,
        key='species'
    )

    group_col = 'SpecieGroup'
    title = 'Nombre de demandes par espèces et par années avec % Plant Breeders Rights'
    legend_title = 'Espèces'

if selected_items:
    df_filtered = df_counts[df_counts[group_col].isin(selected_items)]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    for item in selected_items:
        df_item = df_filtered[df_filtered[group_col] == item]

        fig.add_trace(
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

        fig.add_trace(
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

    fig.update_layout(
        title=title,
        hovermode='x unified',
        legend_title=legend_title
    )

    fig.update_xaxes(title_text='Année')
    fig.update_yaxes(title_text='Nombre de demandes', secondary_y=False)
    fig.update_yaxes(title_text='% Plant Breeders Rights', secondary_y=True)

    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning('Veuillez sélectionner au moins un élément.')