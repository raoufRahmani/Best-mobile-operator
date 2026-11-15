"""
couverture.py — la couverture 4G Arcep en grille
Les cartes Arcep (3 Go de polygones) sont transformées en une grille de cases de 100 m :
1 case = 1 octet qui contient le niveau des 4 opérateurs (2 bits chacun). Résultat : ~20 Mo.
Utilisé par le pipeline (vers_grille, assembler) et par l'appli (couverture_autour).

L'idée : au lieu de chercher « dans quel polygone tombe cette adresse ? » à chaque visite
(lent : 52 millions de points par opérateur), on découpe la France en cases de 100 m et on note
À L'AVANCE le niveau dans chaque case. Ensuite, répondre = lire une case (0,03 ms).
Comme une photo numérique : on remplace un dessin (des formes) par des pixels.

En entrée, 1 fichier .gpkg par opérateur = une table de 287 lignes (1 par département × niveau)
avec une colonne « geometry » qui contient les zones dessinées point par point.
Niveaux de l'Arcep : TBC = très bonne (marche dehors et, le plus souvent, à l'intérieur),
BC = bonne (dehors, parfois à l'intérieur), CL = limitée (dehors, probablement pas à l'intérieur).
Ce sont des simulations des opérateurs, pas des mesures : d'où seulement 30 % du score.
"""
import time                                     # ne sert qu'au test en bas du fichier
import numpy as np                              # la grille = un grand tableau de nombres
import pyogrio                                  # lire les fichiers .gpkg (tables avec des formes géographiques)
from pyproj import Transformer                  # convertir des coordonnées GPS en Lambert-93
from rasterio.features import rasterize         # « pixeliser » : formes -> cases
from rasterio.transform import from_origin      # dire où est la case (0, 0) et la taille des cases
from config import GRILLE                       # data/couverture_4g.npz


# =====================================================================
# La grille : un rectangle autour de la France, découpé en cases de 100 m
# =====================================================================
# En Lambert-93 (EPSG:2154), le système officiel français, qui compte en MÈTRES :
# une case de 100 m y est un vrai carré partout. Les cartes Arcep sont déjà dans ce système.
# Le rectangle vient de l'emprise des fichiers Arcep (Corse comprise).
X0, Y0, X1, Y1, PAS = 99_000, 6_046_000, 1_243_000, 7_111_000, 100    # France métropolitaine en Lambert-93
LARGEUR, HAUTEUR = (X1 - X0) // PAS, (Y1 - Y0) // PAS                 # 11 440 × 10 650 = 122 millions de cases

# Convertisseur : GPS (degrés) -> Lambert-93 (mètres)
VERS_L93 = Transformer.from_crs("EPSG:4326", "EPSG:2154", always_xy=True)

# Le code de chaque opérateur dans les noms de fichiers Arcep
CODES = {"BOUY": "Bouygues", "FREE": "Free", "OF": "Orange", "SFR0": "SFR"}
# Un niveau va de 0 à 3 : il tient sur 2 bits. On range les 4 opérateurs dans 1 octet (8 bits) :
#     bits 7-6 : SFR | bits 5-4 : Orange | bits 3-2 : Free | bits 1-0 : Bouygues
DECALAGE = {"BOUY": 0, "FREE": 2, "OF": 4, "SFR0": 6}                    # place des 2 bits de chaque opérateur
# Les niveaux de l'Arcep en nombres (0 = pas de couverture)
VALEUR = {"CL": 1, "BC": 2, "TBC": 3}
# Et dans l'autre sens, pour l'affichage
NIVEAUX = {0: "Pas de couverture", 1: "Couverture limitée", 2: "Bonne couverture", 3: "Très bonne couverture"}


# =====================================================================
# Pipeline : la carte d'UN opérateur -> une grille de niveaux (0 à 3)
# Appelée par collect.py, une fois par opérateur et par trimestre.
# =====================================================================
def vers_grille(gpkg):
    """Carte de couverture d'UN opérateur (.gpkg) -> grille 100 m (0 à 3 par case). ~5 min."""
    # 1) On part d'une grille vide : 0 partout (122 Mo en mémoire)
    grille = np.zeros((HAUTEUR, LARGEUR), np.uint8)
    nb = pyogrio.read_info(gpkg)["features"]           # nombre de lignes du fichier (287)

    # 2) On lit le fichier par paquets de 20 lignes (1 ligne = toutes les zones d'un niveau
    #    dans un département) : on ne charge jamais les 96 départements d'un coup
    for debut in range(0, nb, 20):                     # 20 polygones à la fois, pour la mémoire
        zones = pyogrio.read_dataframe(gpkg, columns=["niveau"], skip_features=debut, max_features=20)
        valeurs = zones["niveau"].map(VALEUR).fillna(0).astype(int)      # "TBC" -> 3, "BC" -> 2, "CL" -> 1

        # 3) On « colorie » les cases dont le centre tombe dans une zone, avec le niveau de la zone.
        #    from_origin(X0, Y1, ...) : la case (0, 0) est en haut à gauche (au nord-ouest), comme une image
        morceau = rasterize(zip(zones.geometry, valeurs), out_shape=grille.shape,
                            transform=from_origin(X0, Y1, PAS, PAS), dtype=np.uint8)

        # 4) Si des zones se chevauchent (ex. limite entre 2 départements), on garde le meilleur niveau
        np.maximum(grille, morceau, out=grille)        # on garde le meilleur niveau
    return grille


# =====================================================================
# Pipeline : les 4 grilles -> UNE grille de 1 octet par case
# 4 fois moins de place qu'avec 4 grilles : 122 Mo en mémoire, 21 Mo compressée sur le disque
# (55 % des cases valent 0 — mer, pays voisins, zones sans réseau — et se compressent très bien).
# =====================================================================
# « << » décale les bits vers la gauche : chaque opérateur va à sa place dans l'octet.
# Exemple : Bouygues 3, Free 0, Orange 2, SFR 1  ->  01 10 00 11 = 99
def assembler(grilles):
    """{code opérateur: grille} -> une seule grille de 1 octet par case."""
    return sum(grilles[code] << DECALAGE[code] for code in CODES).astype(np.uint8)


# =====================================================================
# Appli : le niveau des 4 opérateurs à une adresse (appelée par score.py à chaque recherche)
# =====================================================================

# La grille est gardée en mémoire entre deux recherches (avec la date du fichier, pour savoir
# si le pipeline l'a remplacée depuis)
_grille, _date = None, None


def couverture_autour(lat, lon):
    """Niveau de couverture 4G des 4 opérateurs à un point."""
    global _grille, _date

    # 1) Pas de grille (pipeline jamais passé) : on le dit au lieu de planter
    if not GRILLE.exists():
        return {operateur: "Données absentes" for operateur in CODES.values()}

    # 2) On charge la grille une seule fois, et on la recharge seulement si le fichier a changé
    #    (l'appli prend la nouvelle version toute seule, sans redémarrer)
    if _date != GRILLE.stat().st_mtime:                 # relue seulement si le pipeline l'a mise à jour
        with np.load(GRILLE) as fichier:                # « with » : le fichier est refermé tout de suite
            _grille, _date = fichier["grille"], GRILLE.stat().st_mtime

    # 3) Adresse GPS -> mètres Lambert-93 -> numéro de ligne et de colonne (on divise par 100 m).
    #    Les lignes se comptent depuis le nord (Y1), les colonnes depuis l'ouest (X0)
    x, y = VERS_L93.transform(lon, lat)
    ligne, colonne = int((Y1 - y) // PAS), int((x - X0) // PAS)

    # 4) En dehors du rectangle de la France
    if not (0 <= ligne < HAUTEUR and 0 <= colonne < LARGEUR):
        return {operateur: "Pas de couverture" for operateur in CODES.values()}

    # 5) On lit l'octet de la case et on en sort les 4 niveaux :
    #    « >> » ramène les 2 bits de l'opérateur tout à droite, « & 3 » ne garde que ces 2 bits.
    #    Ex. Orange : 255 = 11111111 -> >> 4 = 1111 -> & 3 = 11 = 3 = « Très bonne couverture »
    case = int(_grille[ligne, colonne])
    return {operateur: NIVEAUX[(case >> DECALAGE[code]) & 3] for code, operateur in CODES.items()}


# =====================================================================
# Test rapide à la main : python -m pipeline.couverture
# Affiche la couverture à Nanterre et le temps de réponse.
# =====================================================================
if __name__ == "__main__":
    from webapp.adresse import geocoder
    lieu = geocoder("8 rue du port nanterre")
    debut = time.time()
    for operateur, niveau in couverture_autour(lieu["latitude"], lieu["longitude"]).items():
        print(f"{operateur:10} {niveau}")
    print("Temps :", round(time.time() - debut, 1), "secondes")
