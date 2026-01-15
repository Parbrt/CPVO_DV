import pandas as pd
import re


def clean_company_name(name):
    if pd.isna(name):
        return name

    # 1. Mise en minuscule et suppression des adresses/codes pays entre parenthèses
    name = str(name).split(' - ')[0]  # Coupe après le tiret (souvent la ville/pays)
    name = re.sub(r'\(.*?\)', '', name)  # Supprime (BG), (DE), etc.

    # 2. Suppression des formes juridiques (suffixes courants)
    suffixes = [
        r'\bLTD\b', r'\bLTD\.\b', r'\bOOD\b', r'\bEOOD\b', r'\bAD\b', r'\bEAD\b',
        r'\bSP\b', r'\bZ O\.O\.\b', r'\bSP\. Z O\.O\.\b', r'\bS\.P\.A\.\b',
        r'\bS\.R\.L\.\b', r'\bSRL\b', r'\bS\.A\.S\.\b', r'\bSAS\b', r'\bS\.A\.\b',
        r'\bGMBH\b', r'\bKG\b', r'\bCO\b', r'\bS\.C\.A\.\b', r'\bS\.L\.\b',
        r'\bB\.V\.\b', r'\bNV\b', r'\bA/S\b', r'\bAPS\b'
    ]

    name = name.upper()
    for suffix in suffixes:
        name = re.sub(suffix, '', name, flags=re.IGNORECASE)

    # 3. Suppression des guillemets et espaces doubles
    name = name.replace('"', '').replace("'", "").strip()
    name = re.sub(r'\s+', ' ', name)

    # 4. Regroupements manuels spécifiques (Mapping)
    # On peut ajouter les gros groupes ici pour les unifier totalement
    mapping = {
        'SYNGENTA': 'SYNGENTA',
        'LIMAGRAIN': 'LIMAGRAIN',
        'KWS': 'KWS',
        'BARENBRUG': 'BARENBRUG',
        'BAYER': 'BAYER',
        'PIONEER': 'PIONEER / CORTEVA',
        'CORTEVA': 'PIONEER / CORTEVA',
        'LIDEA': 'LIDEA',
        'RAGT': 'RAGT',
        'STRUBE': 'STRUBE',
        'DLF': 'DLF SEEDS',
        'AGRONOM I HOLDING': 'AGRONOM I HOLDING',
        'AGESOYA': 'AGESOYA'
    }

    for key in mapping:
        if key in name:
            return mapping[key]

    return name


def process_csv(input_file, output_file, column_name):
    # Lecture du CSV
    df = pd.read_csv(input_file)

    # Création d'une colonne de sauvegarde du nom original
    df['NOM_ORIGINAL'] = df[column_name]

    # Application du nettoyage
    df[column_name] = df[column_name].apply(clean_company_name)

    # Sauvegarde
    df.to_csv(output_file, index=False, encoding='utf-8')
    print(f"Traitement terminé. Fichier sauvegardé sous : {output_file}")


# --- CONFIGURATION ---
# Remplacez par vos vrais noms de fichiers et de colonnes
file_path = 'data/dataset_cleaned.csv'
target_column = 'FINAL_APPLICANT'  # Le nom de la colonne dans votre CSV

process_csv(file_path, 'data/dataset_cleaned_name.csv', target_column)