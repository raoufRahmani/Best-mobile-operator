import io, json, re, zipfile
from pathlib import Path
from urllib.parse import urljoin
import requests
import py7zr

API = "https://www.data.gouv.fr/api/1/datasets/"
MEMO = Path("data_raw/derniere_version.json")   # ce qu'on a déjà téléchargé


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


# ---------- Source 1 : ANFR (où sont les antennes)
def collect_anfr():
    ressources = requests.get(API + "donnees-sur-les-installations-radioelectriques-de-plus-de-5-watts-1/",
                              timeout=30).json()["resources"]
    titres = ["Tables supports antennes émetteurs bandes", "Tables de référence"]
    a_jour = {t: plus_recent(ressources, t)["id"] for t in titres}

    if lire_memo().get("anfr") == a_jour:
        print("ANFR : pas de nouvelle version")
        return

    dossier = Path("data_raw/anfr")
    dossier.mkdir(parents=True, exist_ok=True)
    for t in titres:
        r = plus_recent(ressources, t)
        print("ANFR : téléchargement de", r["title"])
        contenu = requests.get(r["url"], timeout=600).content
        zipfile.ZipFile(io.BytesIO(contenu)).extractall(dossier)
    ecrire_memo("anfr", a_jour)
    print("ANFR OK")


# ---------- Source 2 : Arcep (qualité mesurée)
def collect_arcep():
    ressources = requests.get(API + "mon-reseau-mobile/", timeout=30).json()["resources"]
    dossier_url = plus_recent(ressources, "Mesures de qualité de service")["url"]

    page_url = urljoin(dossier_url, "last/Metropole/")
    page = requests.get(page_url, timeout=30).text

    liens = re.findall(r'href="([^"]*data_habitations\.csv)"', page)
    if not liens:
        print("ARCEP : fichier data_habitations introuvable sur", page_url)
        return
    fichier_url = urljoin(page_url, liens[0])

    if lire_memo().get("arcep") == fichier_url:
        print("ARCEP : pas de nouvelle version")
        return

    dossier = Path("data_raw/arcep")
    dossier.mkdir(parents=True, exist_ok=True)
    nom = fichier_url.split("/")[-1]
    print("ARCEP : téléchargement de", nom)
    with requests.get(fichier_url, stream=True, timeout=600) as r:
        with open(dossier / nom, "wb") as f:
            for morceau in r.iter_content(chunk_size=1 << 20):
                f.write(morceau)
    ecrire_memo("arcep", fichier_url)
    print("ARCEP OK")


def collect_couverture():
    page_url = "https://data.arcep.fr/mobile/couvertures_theoriques/last/Metropole/00_Metropole/index.html"
    page = requests.get(page_url, timeout=30).text
    liens = [urljoin(page_url, l) for l in re.findall(r'href="([^"]*_4G_data\.gpkg\.7z)"', page)]
    if not liens:
        print("COUVERTURE : fichiers 4G introuvables sur", page_url); return
    if lire_memo().get("couverture") == liens:
        print("COUVERTURE : pas de nouvelle version"); return

    dossier = Path("data_raw/couverture"); dossier.mkdir(parents=True, exist_ok=True)
    for ancien in list(dossier.glob("*.gpkg")) + list(dossier.glob("*.7z")):
        ancien.unlink()                                  # on supprime l'ancien trimestre

    for url in liens:
        archive = dossier / url.split("/")[-1]
        print("COUVERTURE : téléchargement de", archive.name)
        with requests.get(url, stream=True, timeout=600) as r:
            with open(archive, "wb") as f:
                for morceau in r.iter_content(chunk_size=1 << 20):
                    f.write(morceau)
        with py7zr.SevenZipFile(archive) as z:
            z.extractall(dossier)
        archive.unlink()                                 # on garde le .gpkg, on jette le .7z
    ecrire_memo("couverture", liens); print("COUVERTURE OK")


if __name__ == "__main__":
    collect_anfr()
    collect_arcep()
    collect_couverture()