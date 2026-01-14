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
