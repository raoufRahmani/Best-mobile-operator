"""
config.py — la configuration du projet, au même endroit
(l'équivalent du conf/collector.conf de l'appli du prof).
D'où viennent les données, où elles sont rangées, sur quel port tourne l'appli :
pour changer un réglage, on le change ici, pas dans le code.
"""
from pathlib import Path

# ---------- Les sources
API_DATAGOUV = "https://www.data.gouv.fr/api/1/datasets/"
JEU_ANFR = "donnees-sur-les-installations-radioelectriques-de-plus-de-5-watts-1"
TITRES_ANFR = ["Tables supports antennes émetteurs bandes", "Tables de référence"]
JEU_ARCEP = "mon-reseau-mobile"
TITRE_ARCEP = "Mesures de qualité de service"
PAGE_COUVERTURE = "https://data.arcep.fr/mobile/couvertures_theoriques/last/Metropole/00_Metropole/index.html"
API_ADRESSE = "https://data.geopf.fr/geocodage/search"

# ---------- Les dossiers
BRUT = Path("data_raw")        # fichiers téléchargés, temporaires (supprimés après nettoyage)
DONNEES = Path("data")         # fichiers préparés, dans le dépôt Git
ARCHIVES = Path("archived")    # anciennes versions des fichiers de data/

# ---------- Les fichiers préparés
SITES = DONNEES / "sites.csv.gz"                 # antennes (ANFR)
MESURES = DONNEES / "mesures.csv.gz"             # tests de terrain (Arcep)
GRILLE = DONNEES / "couverture_4g.npz"           # couverture 4G (Arcep)
MEMO = DONNEES / "derniere_version.json"         # versions déjà téléchargées

# ---------- L'appli
PORT = 8501
