"""
archive.py — garde l'ancienne version d'un fichier de data/ avant qu'il soit remplacé
(comme le dossier archived/ de l'appli du prof). Permet de revenir en arrière.
"""
import shutil
from datetime import datetime
from config import ARCHIVES


def archiver(chemin):
    """Copie le fichier dans archived/, avec la date devant son nom (ex. 2026-11-12_20-30_sites.csv.gz)."""
    if chemin.exists():
        ARCHIVES.mkdir(exist_ok=True)
        date = datetime.now().strftime("%Y-%m-%d_%H-%M")
        shutil.copy2(chemin, ARCHIVES / f"{date}_{chemin.name}")
