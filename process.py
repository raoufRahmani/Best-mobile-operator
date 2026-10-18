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

# 3) Sites 5G rapide (3500 MHz) par commune et par opérateur
s3500 = (
    sites[sites["frequence"] == 3500]
         .groupby(["code_insee", "operateur"])["site_id"]
         .nunique()
         .rename("nb_sites_5g_3500")
         .reset_index()
)

# 4) Nouveaux sites : mis en service dans les 12 derniers mois
il_y_a_12_mois = pd.Timestamp.today() - pd.DateOffset(months=12)

premiere_date = (
    sites.groupby(["code_insee", "operateur", "site_id"])["date_service"]
         .min()
         .reset_index()
)
nouveaux = (
    premiere_date[premiere_date["date_service"] >= il_y_a_12_mois]
         .groupby(["code_insee", "operateur"])["site_id"]
         .nunique()
         .rename("nouveaux_sites_12m")
         .reset_index()
)

# 5) On ajoute ces 2 colonnes au tableau "comptage"
comptage = (
    comptage.merge(s3500, on=["code_insee", "operateur"], how="left")
            .merge(nouveaux, on=["code_insee", "operateur"], how="left")
            .fillna({"nb_sites_5g_3500": 0, "nouveaux_sites_12m": 0})
            .astype({"nb_sites_5g_3500": int, "nouveaux_sites_12m": int})
)
print(comptage[comptage["code_insee"] == "92050"])