import pandas as pd
from config import SITES, MESURES
from webapp.adresse import geocoder
from webapp.antennes_proches import antennes_autour, mesures_autour
from pipeline.couverture import couverture_autour

POINTS_COUVERTURE = {"Très bonne couverture": 1, "Bonne couverture": 0.66, "Couverture limitée": 0.33}
POIDS = {"note_couverture": 0.3, "note_reussite": 0.3, "note_debit": 0.2,
         "note_5g": 0.1, "note_proximite": 0.1}


def score_adresse(adresse, sites, mesures):
    """Adresse -> (lieu, tableau des 4 opérateurs trié du meilleur au moins bon)."""
    lieu = geocoder(adresse)
    if lieu is None:
        return None, None
    lat, lon = lieu["latitude"], lieu["longitude"]

    # 1) On rassemble tout dans un seul tableau (1 ligne par opérateur)
    tableau = antennes_autour(sites, lat, lon).join(mesures_autour(mesures, lat, lon))
    tableau["couverture_4g"] = pd.Series(couverture_autour(lat, lon))

    # 2) Chaque critère devient une note entre 0 et 1
    tableau["note_couverture"] = tableau["couverture_4g"].map(POINTS_COUVERTURE).fillna(0)
    tableau["note_reussite"] = tableau["taux_ajuste"] / 100
    tableau["note_debit"] = tableau["debit_ajuste"] / tableau["debit_ajuste"].max()
    tableau["note_5g"] = (tableau["nb_sites_5g_3500"] / tableau["nb_sites_5g_3500"].max()).fillna(0)
    tableau["note_proximite"] = (tableau["plus_proche_km"].min() / tableau["plus_proche_km"]).fillna(1)

    # 3) Score = moyenne pondérée des notes
    tableau["score"] = sum(poids * tableau[note] for note, poids in POIDS.items()).round(2)
    return lieu, tableau.sort_values("score", ascending=False)


if __name__ == "__main__":
    sites = pd.read_csv(SITES, dtype={"site_id": str, "code_insee": str},
                        parse_dates=["date_service"])
    mesures = pd.read_csv(MESURES)

    lieu, tableau = score_adresse("8 rue du port nanterre", sites, mesures)
    print(lieu["adresse"])
    print(tableau[["couverture_4g", "taux_ajuste", "debit_ajuste",
                   "nb_sites_5g_3500", "plus_proche_km", "score"]])
    print("\nVerdict :", tableau.index[0])