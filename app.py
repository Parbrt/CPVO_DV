import streamlit as st
import pandas as pd
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.graph_objects as go

@st.cache_data
def load_data():
    df = pd.read_csv('data/dataset_cleaned.csv')
    df['APPLICATIONDATE'] = pd.to_datetime(df['APPLICATIONDATE'], format='%d/%m/%Y', errors='coerce')
    df['Year'] = df['APPLICATIONDATE'].dt.year
    return df

df = load_data()

df_counts = df.groupby(['FINAL_APPLICANT', 'Year']).size().reset_index(name='Count')

df_pbr = df[df['PublicationType'] == 'Plant Breeders Rights'].groupby(['FINAL_APPLICANT', 'Year']).size().reset_index(name='PBR_Count')
df_counts = df_counts.merge(df_pbr, on=['FINAL_APPLICANT', 'Year'], how='left')
df_counts['PBR_Count'] = df_counts['PBR_Count'].fillna(0)
df_counts['PBR_Percentage'] = (df_counts['PBR_Count'] / df_counts['Count'] * 100).round(2)

all_applicants = sorted(df_counts['FINAL_APPLICANT'].unique())
top_applicants = df_counts.groupby('FINAL_APPLICANT')['Count'].sum().nlargest(5).index.tolist()

selected_applicants = st.multiselect(
    'Entreprises sélectionées:',
    options=all_applicants,
    default=top_applicants
)

if selected_applicants:
    df_filtered = df_counts[df_counts['FINAL_APPLICANT'].isin(selected_applicants)]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    for applicant in selected_applicants:
        df_app = df_filtered[df_filtered['FINAL_APPLICANT'] == applicant]

        fig.add_trace(
            go.Scatter(
                x=df_app['Year'],
                y=df_app['Count'],
                name=applicant,
                mode='lines+markers',
                line=dict(width=2),
                marker=dict(size=8)
            ),
            secondary_y=False
        )

        fig.add_trace(
            go.Scatter(
                x=df_app['Year'],
                y=df_app['PBR_Percentage'],
                name=f'{applicant} (PBR %)',
                mode='lines+markers',
                line=dict(width=2, dash='dot'),
                marker=dict(size=6, symbol='diamond'),
                opacity=0.7
            ),
            secondary_y=True
        )

    fig.update_layout(
        title='Nombre de demandes par entreprises et par années avec % Plant Breeders Rights',
        hovermode='x unified',
        legend_title='Entreprises'
    )

    fig.update_xaxes(title_text='Année')
    fig.update_yaxes(title_text='Nombre de demandes', secondary_y=False)
    fig.update_yaxes(title_text='% Plant Breeders Rights', secondary_y=True)

    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning('Veuillez sélectionner au moins une entreprise.')