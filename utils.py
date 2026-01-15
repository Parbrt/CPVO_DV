def get_sector(row):
    sectors = ['AGRI', 'FOREST', 'FRUIT', 'ORNA', 'VEGE']
    for sector in sectors:
        if row[sector] == 1:
            return sector
    return 'MISC'


def get_specie_group(specie_id, all_species):
    if not specie_id or str(specie_id) == 'nan':
        return 'UNKNOWN'

    specie_id = str(specie_id).strip()

    for other_id in all_species:
        if specie_id == other_id:
            return specie_id

    for other_id in all_species:
        if specie_id in other_id or other_id in specie_id:
            return specie_id if len(specie_id) <= len(other_id) else other_id

    specie_prefix = specie_id[:9]
    for other_id in all_species:
        if other_id.startswith(specie_prefix):
            return specie_prefix

    return specie_prefix


def get_company_group(company_name):
    if not company_name or company_name == 'nan':
        return 'UNKNOWN'

    company_name = str(company_name).strip()

    first_word = company_name.split()[0] if company_name else 'UNKNOWN'

    return first_word


def normalize_reference(text):
    import unicodedata
    import re

    if not text or str(text) == 'nan':
        return ''

    text = str(text)

    text = text.lower()

    text = unicodedata.normalize('NFD', text)
    text = ''.join(char for char in text if unicodedata.category(char) != 'Mn')

    text = re.sub(r'[^\w]', '', text)

    return text


def deduplicate_within_species(df):
    import pandas as pd

    df['_compare_ref'] = df.apply(
        lambda row: row['BREEDERREFERENCE'] if row['BREEDERREFERENCE'] and str(row['BREEDERREFERENCE']) != 'nan'
        else row['DENOMINATION'],
        axis=1
    )

    df['_normalized_ref'] = df['_compare_ref'].apply(normalize_reference)

    # Parse dates for sorting (use APPLICATIONDATE, fallback to GRANTDATE)
    df['_app_date'] = pd.to_datetime(df['APPLICATIONDATE'], format='%d/%m/%Y', errors='coerce')
    df['_grant_date'] = pd.to_datetime(df['GRANTDATE'], format='%d/%m/%Y', errors='coerce')
    df['_sort_date'] = df['_app_date'].fillna(df['_grant_date'])

    # Sort by date (earliest first) to keep earliest when deduplicating
    df = df.sort_values('_sort_date', na_position='last')

    df_dedup = df.drop_duplicates(subset=['SPECIEID', '_normalized_ref', 'PublicationType'], keep='first')

    df_dedup = df_dedup.drop(columns=['_compare_ref', '_normalized_ref', '_app_date', '_grant_date', '_sort_date'])

    return df_dedup
