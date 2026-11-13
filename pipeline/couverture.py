"""
couverture.py — la couverture 4G Arcep en grille
Les cartes Arcep (3 Go de polygones) sont transformées en une grille de cases de 100 m :
1 case = 1 octet qui contient le niveau des 4 opérateurs (2 bits chacun). Résultat : ~20 Mo.
Utilisé par le pipeline (vers_grille, assembler) et par l'appli (couverture_autour).
"""
import time
import numpy as np
import pyogrio
from pyproj import Transformer
from rasterio.features import rasterize
from rasterio.transform import from_origin
from config import GRILLE

X0, Y0, X1, Y1, PAS = 99_000, 6_046_000, 1_243_000, 7_111_000, 100    # France métropolitaine en Lambert-93
LARGEUR, HAUTEUR = (X1 - X0) // PAS, (Y1 - Y0) // PAS

# Convertisseur : GPS (degrés) -> Lambert-93 (mètres)
VERS_L93 = Transformer.from_crs("EPSG:4326", "EPSG:2154", always_xy=True)

CODES = {"BOUY": "Bouygues", "FREE": "Free", "OF": "Orange", "SFR0": "SFR"}
DECALAGE = {"BOUY": 0, "FREE": 2, "OF": 4, "SFR0": 6}                    # place des 2 bits de chaque opérateur
VALEUR = {"CL": 1, "BC": 2, "TBC": 3}
NIVEAUX = {0: "Pas de couverture", 1: "Couverture limitée", 2: "Bonne couverture", 3: "Très bonne couverture"}


def vers_grille(gpkg):
    """Carte de couverture d'UN opérateur (.gpkg) -> grille 100 m (0 à 3 par case). ~5 min."""
    grille = np.zeros((HAUTEUR, LARGEUR), np.uint8)
    nb = pyogrio.read_info(gpkg)["features"]
    for debut in range(0, nb, 20):                     # 20 polygones à la fois, pour la mémoire
        zones = pyogrio.read_dataframe(gpkg, columns=["niveau"], skip_features=debut, max_features=20)
        valeurs = zones["niveau"].map(VALEUR).fillna(0).astype(int)
        morceau = rasterize(zip(zones.geometry, valeurs), out_shape=grille.shape,
                            transform=from_origin(X0, Y1, PAS, PAS), dtype=np.uint8)
        np.maximum(grille, morceau, out=grille)        # on garde le meilleur niveau
    return grille


def assembler(grilles):
    """{code opérateur: grille} -> une seule grille de 1 octet par case."""
    return sum(grilles[code] << DECALAGE[code] for code in CODES).astype(np.uint8)


_grille, _date = None, None


def couverture_autour(lat, lon):
    """Niveau de couverture 4G des 4 opérateurs à un point."""
    global _grille, _date
    if not GRILLE.exists():
        return {operateur: "Données absentes" for operateur in CODES.values()}
    if _date != GRILLE.stat().st_mtime:                 # relue seulement si le pipeline l'a mise à jour
        with np.load(GRILLE) as fichier:                # « with » : le fichier est refermé tout de suite
            _grille, _date = fichier["grille"], GRILLE.stat().st_mtime

    x, y = VERS_L93.transform(lon, lat)
    ligne, colonne = int((Y1 - y) // PAS), int((x - X0) // PAS)
    if not (0 <= ligne < HAUTEUR and 0 <= colonne < LARGEUR):
        return {operateur: "Pas de couverture" for operateur in CODES.values()}
    case = int(_grille[ligne, colonne])
    return {operateur: NIVEAUX[(case >> DECALAGE[code]) & 3] for code, operateur in CODES.items()}


if __name__ == "__main__":
    from webapp.adresse import geocoder
    lieu = geocoder("8 rue du port nanterre")
    debut = time.time()
    for operateur, niveau in couverture_autour(lieu["latitude"], lieu["longitude"]).items():
        print(f"{operateur:10} {niveau}")
    print("Temps :", round(time.time() - debut, 1), "secondes")
