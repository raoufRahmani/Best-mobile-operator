"""
collect.py — Étape 1 du pipeline
Télécharge les données brutes dans data_raw/, seulement si une source a publié une nouvelle version
(les versions déjà traitées sont notées dans data/derniere_version.json).
Lancement, depuis la racine du projet : python -m pipeline.collect
"""
import io, json, os, re, zipfile
from urllib.parse import urljoin
import numpy as np
import requests
import py7zr
from config import API_DATAGOUV, JEU_ANFR, TITRES_ANFR, JEU_ARCEP, TITRE_ARCEP, PAGE_COUVERTURE, BRUT, GRILLE, MEMO
from pipeline.archive import archiver
from pipeline.couverture import CODES, vers_grille, assembler


def lire_memo():
    return json.loads(MEMO.read_text()) if MEMO.exists() else {}

def ecrire_memo(cle, valeur):
    memo = lire_memo()
    memo[cle] = valeur
    MEMO.parent.mkdir(parents=True, exist_ok=True)
    MEMO.write_text(json.dumps(memo, indent=2))

def plus_recent(ressources, debut_titre):
    candidats = [r for r in ressources if r["title"].startswith(debut_titre)]
    return max(candidats, key=lambda r: r["last_modified"])


# forcer=True : retélécharge même sans nouvelle version (sert au notebook d'exploration)

# ---------- Source 1 : ANFR (où sont les antennes)
def collect_anfr(forcer=False):
    ressources = requests.get(API_DATAGOUV + JEU_ANFR + "/", timeout=30).json()["resources"]
    a_jour = {t: plus_recent(ressources, t)["id"] for t in TITRES_ANFR}

    if lire_memo().get("anfr") == a_jour and not forcer:
        print("ANFR : pas de nouvelle version")
        return

    dossier = BRUT / "anfr"
    dossier.mkdir(parents=True, exist_ok=True)
    for t in TITRES_ANFR:
        r = plus_recent(ressources, t)
        print("ANFR : téléchargement de", r["title"])
        contenu = requests.get(r["url"], timeout=600).content
        zipfile.ZipFile(io.BytesIO(contenu)).extractall(dossier)
    for inutile in ["SUP_BANDE.txt", "SUP_ANTENNE.txt"]:      # 235 Mo dont clean.py ne se sert pas
        (dossier / inutile).unlink(missing_ok=True)
    ecrire_memo("anfr", a_jour)
    print("ANFR OK")


# ---------- Source 2 : Arcep (qualité mesurée)
def collect_arcep(forcer=False):
    ressources = requests.get(API_DATAGOUV + JEU_ARCEP + "/", timeout=30).json()["resources"]
    dossier_url = plus_recent(ressources, TITRE_ARCEP)["url"]

    # Un dossier par année ; la plus récente n'a pas toujours la Métropole (ex. 2026 : Outre-mer seulement)
    accueil = requests.get(urljoin(dossier_url, "index.html"), timeout=30).text
    annees = sorted(set(re.findall(r'href="(\d{4})/index\.html"', accueil)), reverse=True)
    fichier_url = None
    for annee in annees:
        page_url = urljoin(dossier_url, f"{annee}/Metropole/index.html")
        liens = re.findall(r'href="([^"]*data_habitations\.csv)"', requests.get(page_url, timeout=30).text)
        if liens:
            fichier_url = urljoin(page_url, liens[0])
            break
    if fichier_url is None:
        print("ARCEP : fichier data_habitations introuvable sous", dossier_url)
        return

    # On compare le nom du fichier (l'Arcep déplace parfois ses dossiers sans changer les données)
    if lire_memo().get("arcep", "").split("/")[-1] == fichier_url.split("/")[-1] and not forcer:
        print("ARCEP : pas de nouvelle version")
        return

    dossier = BRUT / "arcep"
    dossier.mkdir(parents=True, exist_ok=True)
    nom = fichier_url.split("/")[-1]
    print("ARCEP : téléchargement de", nom)
    with requests.get(fichier_url, stream=True, timeout=600) as r:
        with open(dossier / nom, "wb") as f:
            for morceau in r.iter_content(chunk_size=1 << 20):
                f.write(morceau)
    ecrire_memo("arcep", fichier_url)
    print("ARCEP OK")


# ---------- Source 3 : Arcep (couverture 4G théorique)
def collect_couverture():
    page = requests.get(PAGE_COUVERTURE, timeout=30).text
    liens = [urljoin(PAGE_COUVERTURE, lien) for lien in re.findall(r'href="([^"]*_4G_data\.gpkg\.7z)"', page)]
    if not liens:
        print("COUVERTURE : fichiers 4G introuvables sur", PAGE_COUVERTURE)
        return
    if lire_memo().get("couverture") == liens and GRILLE.exists():
        print("COUVERTURE : pas de nouvelle version")
        return

    dossier = BRUT / "couverture"
    dossier.mkdir(parents=True, exist_ok=True)
    for ancien in list(dossier.glob("*.gpkg")) + list(dossier.glob("*.7z")):
        ancien.unlink()                                  # restes d'un passage interrompu

    # Un opérateur à la fois : télécharger -> extraire -> grille 100 m -> supprimer (~1 Go max sur le disque)
    grilles = {}
    for url in liens:
        code = next(c for c in CODES if f"_{c}_4G" in url)
        fichier_7z = dossier / url.split("/")[-1]
        print("COUVERTURE : téléchargement de", fichier_7z.name)
        with requests.get(url, stream=True, timeout=600) as r:
            with open(fichier_7z, "wb") as f:
                for morceau in r.iter_content(chunk_size=1 << 20):
                    f.write(morceau)
        with py7zr.SevenZipFile(fichier_7z) as z:
            z.extractall(dossier)
        fichier_7z.unlink()
        gpkg = next(dossier.glob(f"*_{code}_4G_data.gpkg"))
        print("COUVERTURE : conversion en grille de", gpkg.name, "(~5 min)")
        grilles[code] = vers_grille(gpkg)
        gpkg.unlink()

    temporaire = GRILLE.with_suffix(".tmp.npz")         # écrit à côté puis renommé : l'appli ne lit jamais un fichier à moitié écrit
    np.savez_compressed(temporaire, grille=assembler(grilles))
    archiver(GRILLE)                                     # l'ancienne grille part dans archived/
    os.replace(temporaire, GRILLE)
    ecrire_memo("couverture", liens)
    print("COUVERTURE OK")


if __name__ == "__main__":
    collect_anfr()
    collect_arcep()
    collect_couverture()