import pandas as pd

# 1) Lire la table produite par clean.py
sites = pd.read_csv(
    "data/sites.csv",
    dtype={"site_id": str, "code_insee": str},
    parse_dates=["date_service"],
)

print(sites.shape)
print(sites.head())