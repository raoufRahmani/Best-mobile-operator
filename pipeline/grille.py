"""
grille.py — la partie Python de l'extraction de la couverture, appelée par extraction.sh
Le téléchargement se fait en bash (curl) ; ici on fait ce que bash ne sait pas faire :
ouvrir une archive .7z et transformer les polygones en grille (librairies py7zr et rasterio).

Deux commandes, lancées depuis la racine du projet :
  python -m pipeline.grille <fichier.7z>   -> grille d'UN opérateur, rangée à côté (<code>.npy), puis supprime le .7z et le .gpkg
  python -m pipeline.grille --assembler    -> les 4 grilles -> data/couverture_4g.npz (l'ancienne part dans archived/)
"""
import os
import sys
from pathlib import Path
import numpy as np
import py7zr
from config import GRILLE
from pipeline.archive import archiver
from pipeline.couverture import CODES, vers_grille, assembler

DOSSIER = Path("data_raw") / "couverture"


# Une archive .7z (un opérateur) -> sa grille de 100 m, gardée dans data_raw/couverture/<code>.npy
def grille_operateur(fichier_7z):
    fichier_7z = Path(fichier_7z)
    # Quel opérateur ? On retrouve son code (OF, SFR0, BOUY ou FREE) dans le nom du fichier
    code = next(c for c in CODES if f"_{c}_4G" in fichier_7z.name)

    # Extraire (-> un fichier .gpkg de polygones), puis supprimer le .7z
    with py7zr.SevenZipFile(fichier_7z) as z:
        z.extractall(fichier_7z.parent)
    fichier_7z.unlink()

    # Convertir les polygones en grille (voir couverture.py), puis supprimer le .gpkg
    gpkg = next(fichier_7z.parent.glob(f"*_{code}_4G_data.gpkg"))
    print("COUVERTURE : conversion en grille de", gpkg.name, "(~5 min)")
    np.save(fichier_7z.parent / f"{code}.npy", vers_grille(gpkg))
    gpkg.unlink()


# Les 4 grilles -> une seule (1 octet par case), mise en place sans risque :
# écrite à côté, l'ancienne archivée, puis remplacée d'un coup (os.replace)
def assembler_grilles():
    grilles = {code: np.load(DOSSIER / f"{code}.npy") for code in CODES}
    temporaire = GRILLE.with_suffix(".tmp.npz")         # l'appli ne lit jamais un fichier à moitié écrit
    np.savez_compressed(temporaire, grille=assembler(grilles))
    archiver(GRILLE)                                     # l'ancienne grille part dans archived/
    os.replace(temporaire, GRILLE)
    for code in CODES:
        (DOSSIER / f"{code}.npy").unlink()


if __name__ == "__main__":
    if sys.argv[1] == "--assembler":
        assembler_grilles()
    else:
        grille_operateur(sys.argv[1])
