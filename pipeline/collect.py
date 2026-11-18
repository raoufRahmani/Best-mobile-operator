"""
collect.py — Étape 1 du pipeline
Télécharge les données brutes dans data_raw/, seulement si une source a publié une nouvelle version
(les versions déjà traitées sont notées dans data/derniere_version.json).
Lancement, depuis la racine du projet : python -m pipeline.collect

Le principe, pour chacune des 3 sources :
  1. regarder quelle est la dernière version publiée en ligne
  2. la comparer avec celle notée dans le carnet (data/derniere_version.json)
  3. si c'est la même : on ne fait rien
  4. sinon : on télécharge, on fait le ménage, et on note la version dans le carnet EN DERNIER
     (si ça plante au milieu, le passage suivant recommence au lieu de croire que c'est fait)
"""
# Outils fournis avec Python
import io, json, os, re, zipfile          # io : fichier en mémoire ; re : chercher des liens dans une page web
from urllib.parse import urljoin          # assembler une adresse web (dossier + nom de fichier)

# Librairies installées (requirements.txt)
import numpy as np                        # enregistrer la grille de couverture
import requests                           # télécharger
import py7zr                              # ouvrir les archives .7z de l'Arcep

# Notre projet : les réglages viennent de config.py (rien n'est écrit en dur ici)
from config import API_DATAGOUV, JEU_ANFR, TITRES_ANFR, JEU_ARCEP, TITRE_ARCEP, PAGE_COUVERTURE, BRUT, GRILLE, MEMO
from pipeline.archive import archiver                              # range l'ancienne version dans archived/
from pipeline.couverture import CODES, vers_grille, assembler      # cartes de couverture -> grille de 100 m


# =====================================================================
# Le carnet des versions : data/derniere_version.json
# Il se souvient de ce qu'on a déjà téléchargé, pour ne télécharger que le nouveau.
# =====================================================================

# Lit le carnet. S'il n'existe pas encore (1er lancement), renvoie {} : tout sera considéré comme nouveau.
def lire_memo():
    return json.loads(MEMO.read_text()) if MEMO.exists() else {}

# Met à jour UNE entrée du carnet ("anfr", "arcep" ou "couverture") sans toucher aux autres.
def ecrire_memo(cle, valeur):
    memo = lire_memo()                                   # on relit tout le carnet
    memo[cle] = valeur                                   # on change une seule ligne
    MEMO.parent.mkdir(parents=True, exist_ok=True)       # on crée le dossier data/ s'il manque
    MEMO.write_text(json.dumps(memo, indent=2))          # on réécrit (indent=2 : lisible par un humain)

# data.gouv.fr garde tout l'historique (novembre, octobre...) : on garde le fichier le plus récent
# parmi ceux dont le titre commence par le bon texte.
def plus_recent(ressources, debut_titre):
    candidats = [r for r in ressources if r["title"].startswith(debut_titre)]
    return max(candidats, key=lambda r: r["last_modified"])


# forcer=True : retélécharge même sans nouvelle version (sert au notebook d'exploration)

# =====================================================================
# Source 1 : ANFR — où sont les antennes (mise à jour chaque mois)
# =====================================================================
def collect_anfr(forcer=False):
    # 1) On demande à l'API data.gouv la liste des fichiers du jeu de données,
    #    et on garde l'identifiant de la dernière version de chacun des 2 fichiers utiles
    ressources = requests.get(API_DATAGOUV + JEU_ANFR + "/", timeout=30).json()["resources"]
    a_jour = {t: plus_recent(ressources, t)["id"] for t in TITRES_ANFR}

    # 2) Mêmes identifiants que dans le carnet : rien de nouveau, on s'arrête
    if lire_memo().get("anfr") == a_jour and not forcer:
        print("ANFR : pas de nouvelle version")
        return

    # 3) Nouvelle version : on télécharge les 2 zips (~30 Mo chacun) en mémoire
    #    (io.BytesIO les fait passer pour des fichiers) et on les extrait dans data_raw/anfr/
    dossier = BRUT / "anfr"
    dossier.mkdir(parents=True, exist_ok=True)
    for t in TITRES_ANFR:
        r = plus_recent(ressources, t)
        print("ANFR : téléchargement de", r["title"])
        contenu = requests.get(r["url"], timeout=600).content
        zipfile.ZipFile(io.BytesIO(contenu)).extractall(dossier)

    # 4) On supprime tout de suite 2 tables dont on ne se sert pas (235 Mo de place libérée)
    for inutile in ["SUP_BANDE.txt", "SUP_ANTENNE.txt"]:
        (dossier / inutile).unlink(missing_ok=True)

    # 5) Tout a réussi : on note la version dans le carnet (en dernier)
    ecrire_memo("anfr", a_jour)
    # Le mois de la version (le titre finit par « novembre 2026 ») : affiché sur la page
    ecrire_memo("anfr_mois", plus_recent(ressources, TITRES_ANFR[0])["title"].removeprefix(TITRES_ANFR[0]).strip())
    print("ANFR OK")


# =====================================================================
# Source 2 : Arcep — les tests de terrain, « est-ce que ça marche en vrai ? » (chaque année)
# =====================================================================
def collect_arcep(forcer=False):
    # 1) data.gouv ne donne pas le fichier, mais l'adresse d'un dossier du site de l'Arcep
    ressources = requests.get(API_DATAGOUV + JEU_ARCEP + "/", timeout=30).json()["resources"]
    dossier_url = plus_recent(ressources, TITRE_ARCEP)["url"]

    # 2) On lit la page du dossier et on y repère les années ("2026", "2025"...), de la plus récente à la plus ancienne.
    #    Un dossier par année ; la plus récente n'a pas toujours la Métropole (ex. 2026 : Outre-mer seulement)
    accueil = requests.get(urljoin(dossier_url, "index.html"), timeout=30).text
    annees = sorted(set(re.findall(r'href="(\d{4})/index\.html"', accueil)), reverse=True)

    # 3) On essaie chaque année jusqu'à trouver le fichier data_habitations.csv de la Métropole
    fichier_url = None
    for annee in annees:
        page_url = urljoin(dossier_url, f"{annee}/Metropole/index.html")
        liens = re.findall(r'href="([^"]*data_habitations\.csv)"', requests.get(page_url, timeout=30).text)
        if liens:
            fichier_url = urljoin(page_url, liens[0])
            break                                        # trouvé : on arrête de chercher

    # Rien trouvé (l'Arcep a encore changé ses dossiers ?) : message clair, sans planter
    if fichier_url is None:
        print("ARCEP : fichier data_habitations introuvable sous", dossier_url)
        return

    # 4) On compare le nom du fichier avec le carnet (pas l'adresse complète :
    #    l'Arcep déplace parfois ses dossiers sans changer les données)
    if lire_memo().get("arcep", "").split("/")[-1] == fichier_url.split("/")[-1] and not forcer:
        print("ARCEP : pas de nouvelle version")
        return

    # 5) Nouveau fichier : on le télécharge par morceaux de 1 Mo (stream=True),
    #    pour ne jamais avoir les 93 Mo en mémoire d'un coup
    dossier = BRUT / "arcep"
    dossier.mkdir(parents=True, exist_ok=True)
    nom = fichier_url.split("/")[-1]
    print("ARCEP : téléchargement de", nom)
    with requests.get(fichier_url, stream=True, timeout=600) as r:
        with open(dossier / nom, "wb") as f:
            for morceau in r.iter_content(chunk_size=1 << 20):    # 1 << 20 = 1 048 576 octets = 1 Mo
                f.write(morceau)

    # 6) On note la version dans le carnet (en dernier)
    ecrire_memo("arcep", fichier_url)
    print("ARCEP OK")


# =====================================================================
# Source 3 : Arcep — la carte officielle de couverture 4G (chaque trimestre)
# C'est la plus lourde : 4 fichiers .7z (~1,3 Go), 3 Go une fois extraits.
# =====================================================================
def collect_couverture():
    # 1) On lit la page de l'Arcep et on y cherche les liens des 4 fichiers (un par opérateur)
    page = requests.get(PAGE_COUVERTURE, timeout=30).text
    liens = [urljoin(PAGE_COUVERTURE, lien) for lien in re.findall(r'href="([^"]*_4G_data\.gpkg\.7z)"', page)]
    if not liens:
        print("COUVERTURE : fichiers 4G introuvables sur", PAGE_COUVERTURE)
        return

    # 2) Mêmes fichiers que dans le carnet, et la grille existe déjà : rien à faire
    if lire_memo().get("couverture") == liens and GRILLE.exists():
        print("COUVERTURE : pas de nouvelle version")
        return

    # 3) On efface les restes d'un passage précédent qui aurait planté au milieu
    dossier = BRUT / "couverture"
    dossier.mkdir(parents=True, exist_ok=True)
    for ancien in list(dossier.glob("*.gpkg")) + list(dossier.glob("*.7z")):
        ancien.unlink()                                  # restes d'un passage interrompu

    # 4) Un opérateur à la fois : télécharger -> extraire -> grille 100 m -> supprimer (~1 Go max sur le disque)
    grilles = {}
    for url in liens:
        # Quel opérateur ? On retrouve son code (OF, SFR0, BOUY ou FREE) dans le nom du fichier
        code = next(c for c in CODES if f"_{c}_4G" in url)
        fichier_7z = dossier / url.split("/")[-1]

        # Télécharger le .7z par morceaux de 1 Mo
        print("COUVERTURE : téléchargement de", fichier_7z.name)
        with requests.get(url, stream=True, timeout=600) as r:
            with open(fichier_7z, "wb") as f:
                for morceau in r.iter_content(chunk_size=1 << 20):
                    f.write(morceau)

        # L'extraire (-> un fichier .gpkg de polygones), puis supprimer le .7z
        with py7zr.SevenZipFile(fichier_7z) as z:
            z.extractall(dossier)
        fichier_7z.unlink()

        # Convertir les polygones en grille de cases de 100 m (voir couverture.py), puis supprimer le .gpkg
        gpkg = next(dossier.glob(f"*_{code}_4G_data.gpkg"))
        print("COUVERTURE : conversion en grille de", gpkg.name, "(~5 min)")
        grilles[code] = vers_grille(gpkg)
        gpkg.unlink()

    # 5) On assemble les 4 grilles en une seule (21 Mo) et on la met en place sans risque :
    #    écrite à côté, l'ancienne archivée, puis remplacée d'un coup (os.replace)
    temporaire = GRILLE.with_suffix(".tmp.npz")         # écrit à côté puis renommé : l'appli ne lit jamais un fichier à moitié écrit
    np.savez_compressed(temporaire, grille=assembler(grilles))
    archiver(GRILLE)                                     # l'ancienne grille part dans archived/
    os.replace(temporaire, GRILLE)

    # 6) On note la version dans le carnet (en dernier)
    ecrire_memo("couverture", liens)
    print("COUVERTURE OK")


# =====================================================================
# Lancement : seulement quand on exécute ce fichier (python -m pipeline.collect, ou run.sh).
# Si un autre fichier fait « import » (ex. le notebook), rien ne se lance tout seul.
# =====================================================================
if __name__ == "__main__":
    collect_anfr()
    collect_arcep()
    collect_couverture()
