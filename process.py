import pandas as pd

# 1) Lire la table produite par clean.py
sites = pd.read_csv(
    "data/sites.csv",
    dtype={"site_id": str, "code_insee": str},
    parse_dates=["date_service"],
)

print(sites.shape)
print(sites.head())


# 2) Compter les sites 4G et 5G par commune et par opérateur
comptage = (
    sites.groupby(["code_insee", "operateur", "techno"])["site_id"]
         .nunique()
         .unstack("techno", fill_value=0)
         .reset_index()
         .rename(columns={"4G": "nb_sites_4g", "5G": "nb_sites_5g"})
)

print(comptage.shape)
print(comptage[comptage["code_insee"] == "92050"])