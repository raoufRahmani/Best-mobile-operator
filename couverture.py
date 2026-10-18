import time
from pyproj import Transformer
from shapely.geometry import Point
import geopandas as gpd
from adresse import geocoder
from pathlib import Path


# Convertisseur : GPS (degrés) -> Lambert-93 (mètres)
VERS_L93 = Transformer.from_crs("EPSG:4326", "EPSG:2154", always_xy=True)

NIVEAUX = {"TBC": "Très bonne couverture", "BC": "Bonne couverture", "CL": "Couverture limitée"}

DOSSIER = Path("data_raw/couverture")
CODES = {"BOUY": "Bouygues", "FREE": "Free", "OF": "Orange", "SFR0": "SFR"}

def niveau_couverture(gpkg, lat, lon):
    """Niveau de couverture 4G à un point, pour UN fichier opérateur."""
    x, y = VERS_L93.transform(lon, lat)

    # On ne lit que les zones autour du point (pas tout le fichier)
    zones = gpd.read_file(gpkg, bbox=(x - 1, y - 1, x + 1, y + 1), columns=["niveau"])

    # On garde les zones qui contiennent vraiment le point
    zones = zones[zones.contains(Point(x, y))]

    for code in ["TBC", "BC", "CL"]:
        if code in zones["niveau"].values:
            return NIVEAUX[code]
    return "Pas de couverture"


def couverture_autour(lat, lon):
    """Niveau de couverture 4G des 4 opérateurs à un point."""
    resultat = {}
    for code, operateur in CODES.items():
        gpkg = next(DOSSIER.glob(f"*_{code}_4G_data.gpkg"), None)
        resultat[operateur] = niveau_couverture(gpkg, lat, lon) if gpkg else "Données absentes"
    return resultat


if __name__ == "__main__":
    lieu = geocoder("8 rue du port nanterre")
    debut = time.time()
    for operateur, niveau in couverture_autour(lieu["latitude"], lieu["longitude"]).items():
        print(f"{operateur:10} {niveau}")
    print("Temps :", round(time.time() - debut, 1), "secondes")