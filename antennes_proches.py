import numpy as np
import pandas as pd
from adresse import geocoder

OPERATEURS = ["Bouygues", "Free", "Orange", "SFR"]


def distance_km(lat1, lon1, lat2, lon2):
    """Distance à vol d'oiseau entre deux points GPS (formule de haversine)."""
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * np.arcsin(np.sqrt(a))


def compter(df):
    """Nombre de sites différents par opérateur (0 si aucun)."""
    return df.groupby("operateur")["site_id"].nunique().reindex(OPERATEURS, fill_value=0)


def antennes_autour(sites, lat, lon, rayon_km=1):
    """Résumé par opérateur des antennes autour d'un point."""
    distance = distance_km(lat, lon, sites["latitude"], sites["longitude"])
    proches = sites[distance <= rayon_km]

    return pd.DataFrame({
        "nb_sites_4g": compter(proches[proches["techno"] == "4G"]),
        "nb_sites_5g": compter(proches[proches["techno"] == "5G"]),
        "nb_sites_5g_3500": compter(proches[proches["frequence"] == 3500]),
        "plus_proche_km": distance.groupby(sites["operateur"]).min().round(2),
    })

K = 20  # poids de la moyenne nationale (= comme si on avait 20 tests en plus)


def mesures_autour(mesures, lat, lon, rayon_km=2):
    """Résumé par opérateur des tests Arcep autour d'un point, lissé avec le national."""
    distance = distance_km(lat, lon, mesures["latitude"], mesures["longitude"])
    proches = mesures[distance <= rayon_km]

    # 1) Résultats locaux
    resume = (
        proches.groupby("operateur")
               .agg(nb_tests=("reussi", "size"),
                    taux_reussite=("reussi", "mean"),
                    nb_debits=("debit", "count"),
                    debit_median=("debit", "median"))
               .reindex(OPERATEURS)
    )
    resume[["nb_tests", "nb_debits"]] = resume[["nb_tests", "nb_debits"]].fillna(0).astype(int)

    # 2) Résultats nationaux de chaque opérateur
    national = mesures.groupby("operateur").agg(taux_nat=("reussi", "mean"),
                                                debit_nat=("debit", "median"))
    resume = resume.join(national)

    # 3) Lissage : peu de tests -> proche du national ; beaucoup -> proche du local
    n, d = resume["nb_tests"], resume["nb_debits"]
    resume["taux_ajuste"] = (n * resume["taux_reussite"].fillna(0) + K * resume["taux_nat"]) / (n + K)
    resume["debit_ajuste"] = (d * resume["debit_median"].fillna(0) + K * resume["debit_nat"]) / (d + K)

    # 4) Mise en forme : taux en %, arrondis
    resume["taux_reussite"] = resume["taux_reussite"] * 100
    resume["taux_ajuste"] = resume["taux_ajuste"] * 100
    return resume.drop(columns=["taux_nat", "debit_nat"]).round(0)

if __name__ == "__main__":
    sites = pd.read_csv(
        "data/sites.csv",
        dtype={"site_id": str, "code_insee": str},
        parse_dates=["date_service"],
    )
    lieu = geocoder("8 rue du port nanterre")
    print(lieu["adresse"])
    print(antennes_autour(sites, lieu["latitude"], lieu["longitude"]))
    mesures = pd.read_csv("data/mesures.csv")
    print(mesures_autour(mesures, lieu["latitude"], lieu["longitude"]))