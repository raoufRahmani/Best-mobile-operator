"""
clean.py — Étape 2 du pipeline
Lit les fichiers bruts téléchargés (data_raw/) et produit des fichiers propres et compressés :
data/sites.csv.gz   = 1 ligne par site × opérateur × techno × fréquence (France métropolitaine, 4G/5G).
data/mesures.csv.gz = 1 ligne par test Arcep.
Les fichiers de data/ sont dans le dépôt Git : un clone n'a rien à télécharger.
Une source n'est traitée que si collect.py vient d'en télécharger une nouvelle version ; le brut est ensuite supprimé.
L'ancienne version de chaque fichier est rangée dans archived/.
Lancement, depuis la racine du projet : python -m pipeline.clean

En résumé :
  ANFR  : 3 tables SUP_*.txt (~60 Mo)   -> data/sites.csv.gz   (4,9 Mo)
  Arcep : data_habitations.csv (93 Mo)  -> data/mesures.csv.gz (1,4 Mo)
  (la couverture 4G n'est pas traitée ici : collect.py la transforme déjà en grille)
"""
import os                                  # remplacer un fichier d'un coup (os.replace)
import shutil                              # supprimer un dossier entier (le brut)
import pandas as pd                        # lire, filtrer et assembler les tableaux
from config import BRUT, SITES, MESURES    # les chemins viennent de config.py
from pipeline.archive import archiver      # range l'ancienne version dans archived/

# Où lire le brut, où écrire le résultat
ANFR = BRUT / "anfr"                       # data_raw/anfr/   (rempli par collect.py)
SORTIE = SITES                             # data/sites.csv.gz
ARCEP = BRUT / "arcep"                     # data_raw/arcep/  (rempli par collect.py)
SORTIE_MESURES = MESURES                   # data/mesures.csv.gz


# =====================================================================
# Écrire un fichier sans risque
# =====================================================================
# 1) on écrit dans un fichier temporaire, 2) on range l'ancienne version dans archived/,
# 3) on remplace l'ancien par le nouveau d'un coup (os.replace).
# mtime=0 : le gzip n'inscrit pas l'heure dedans -> mêmes données = même fichier,
#           et Git ne voit pas de faux changement.
def enregistrer(df, chemin):
    """Écrit le CSV compressé d'un coup (fichier temporaire puis renommage) : l'appli ne lit jamais un fichier à moitié écrit."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.with_suffix(".tmp")
    df.to_csv(temporaire, index=False, compression={"method": "gzip", "mtime": 0})
    archiver(chemin)                                     # l'ancienne version part dans archived/
    os.replace(temporaire, chemin)


# =====================================================================
# Les outils pour lire l'ANFR
# =====================================================================

# Les 4 opérateurs mobiles (ADM_ID dans SUP_EXPLOITANT) : numéro ANFR -> nom
OPERATEURS = {"6": "Bouygues", "23": "Orange", "137": "SFR", "240": "Free"}


# Lit une table ANFR : séparateur « ; », tout en texte (dtype=str, pour garder les zéros devant les codes),
# seulement les colonnes utiles (plus rapide, moins de mémoire).
# On essaie l'encodage UTF-8, puis latin-1 : on ne plante pas si l'ANFR change d'encodage.
def lire(nom, colonnes):
    """Lit une table ANFR (séparateur ;) en texte, seulement les colonnes utiles."""
    for enc in ["utf-8", "latin-1"]:
        try:
            return pd.read_csv(ANFR / f"{nom}.txt", sep=";", dtype=str, encoding=enc, usecols=colonnes)
        except UnicodeDecodeError:
            continue                                     # mauvais encodage : on essaie le suivant


# L'ANFR donne les positions en degrés / minutes / secondes (ex. 48° 51' 24" N).
# La carte et le calcul des distances ont besoin de degrés décimaux (ex. 48,8567).
# Formule : degrés + minutes/60 + secondes/3600, et négatif si Sud ou Ouest.
def en_decimal(deg, minu, sec, sens, negatif):
    """Degrés / minutes / secondes -> degrés décimaux (négatif si Sud ou Ouest)."""
    num = lambda s: pd.to_numeric(s.str.replace(",", "."), errors="coerce")   # "24,5" -> 24.5 (vide -> NaN)
    val = num(deg) + num(minu) / 60 + num(sec) / 3600
    return val.where(sens != negatif, -val)


# =====================================================================
# ANFR : les antennes -> data/sites.csv.gz
# On part de 3 tables techniques et on en fait UNE table simple :
# quelles antennes, de quel opérateur, où, depuis quand.
# =====================================================================
def clean():
    # 1) Les sites des 4 opérateurs (on enlève pompiers, TNT, radios...) + le nom de l'opérateur
    station = lire("SUP_STATION", ["STA_NM_ANFR", "ADM_ID"])
    station = station[station["ADM_ID"].isin(OPERATEURS)]
    station["operateur"] = station["ADM_ID"].map(OPERATEURS)
    print("Sites des 4 opérateurs :", len(station))

    # 2) Les émetteurs 4G / 5G de ces sites (on enlève la 2G, la 3G et les essais)
    em = lire("SUP_EMETTEUR", ["STA_NM_ANFR", "EMR_LB_SYSTEME", "EMR_DT_SERVICE"])
    em = em[em["STA_NM_ANFR"].isin(station["STA_NM_ANFR"])]
    lib = em["EMR_LB_SYSTEME"].fillna("")
    em["techno"] = None
    em.loc[lib.str.match(r"^LTE \d+$"), "techno"] = "4G"        # LTE 700, 800, 1800...
    em.loc[lib.str.match(r"^5G NR \d+$"), "techno"] = "5G"      # 5G NR 700, 2100, 3500 (pas les "Expe")
    em = em.dropna(subset=["techno"])                            # tout le reste est supprimé
    # La fréquence = le nombre à la fin du nom (« 5G NR 3500 » -> 3500 : la 5G rapide, 10 % du score)
    em["frequence"] = em["EMR_LB_SYSTEME"].str.extract(r"(\d+)$", expand=False).astype(int)
    # La date de mise en service, au format français jour/mois/année (dayfirst=True)
    em["date_service"] = pd.to_datetime(em["EMR_DT_SERVICE"], dayfirst=True, errors="coerce")
    print("Émetteurs 4G/5G :", len(em))

    # 3) La position et la commune (1 support par site : le premier)
    sup = lire("SUP_SUPPORT", [
        "STA_NM_ANFR",
        "COR_NB_DG_LAT", "COR_NB_MN_LAT", "COR_NB_SC_LAT", "COR_CD_NS_LAT",
        "COR_NB_DG_LON", "COR_NB_MN_LON", "COR_NB_SC_LON", "COR_CD_EW_LON",
        "COM_CD_INSEE",
    ]).drop_duplicates("STA_NM_ANFR")
    sup["latitude"] = en_decimal(sup["COR_NB_DG_LAT"], sup["COR_NB_MN_LAT"],
                                 sup["COR_NB_SC_LAT"], sup["COR_CD_NS_LAT"], "S")
    sup["longitude"] = en_decimal(sup["COR_NB_DG_LON"], sup["COR_NB_MN_LON"],
                                  sup["COR_NB_SC_LON"], sup["COR_CD_EW_LON"], "W")
    # Code commune toujours sur 5 chiffres (« 1004 » -> « 01004 »)
    sup["code_insee"] = sup["COM_CD_INSEE"].str.strip().str.zfill(5)

    # 4) On assemble les 3 tables grâce à leur clé commune STA_NM_ANFR (le numéro du site)
    sites = (
        em.merge(station[["STA_NM_ANFR", "operateur"]], on="STA_NM_ANFR")
          .merge(sup[["STA_NM_ANFR", "latitude", "longitude", "code_insee"]], on="STA_NM_ANFR", how="left")
          .rename(columns={"STA_NM_ANFR": "site_id"})
    )

    # 5) France métropolitaine uniquement (codes INSEE 97 et 98 = outre-mer), positions valides
    sites = sites[~sites["code_insee"].str.startswith(("97", "98"), na=True)]
    sites = sites.dropna(subset=["latitude", "longitude"])

    # 6) 1 ligne par site × opérateur × techno × fréquence (on garde la date la plus ancienne)
    sites = (
        sites.sort_values("date_service")
             .drop_duplicates(["site_id", "operateur", "techno", "frequence"])
             [["site_id", "operateur", "techno", "frequence", "date_service",
               "latitude", "longitude", "code_insee"]]
             .sort_values(["code_insee", "operateur", "techno", "frequence"])
    )

    # 7) On enregistre (sans risque : voir enregistrer plus haut)
    enregistrer(sites, SORTIE)

    # Petit résumé pour vérifier (il apparaît dans le log du pipeline)
    print("\nLignes dans", SORTIE, ":", len(sites))
    print("Communes :", sites["code_insee"].nunique())
    print("\nSites par opérateur et techno :")
    print(sites.drop_duplicates(["site_id", "techno"])
               .pivot_table(index="operateur", columns="techno", values="site_id", aggfunc="count", fill_value=0))
    print("\nclean OK")



# =====================================================================
# Arcep : les tests de terrain -> data/mesures.csv.gz
# On passe de 93 Mo à 1,4 Mo en ne gardant que ce dont le score a besoin.
# =====================================================================
# Les colonnes utiles. Le format change selon l'année : jusqu'en 2025, « Result » dit si le test a réussi ;
# en 2026 cette colonne a disparu, on utilise « page web chargée en moins de 10 s » et « vidéo de qualité correcte ».
COLONNES_ARCEP = {"operator", "latitude_start", "longitude_start", "protocole", "bitrate_dl",
                  "Result", "loaded_in_less_10_secondes", "quality_correct"}


def clean_arcep():
    # 1) Lire le fichier Arcep (seulement les colonnes utiles)
    #    sep=None : pandas devine tout seul le séparateur ; decimal="," : virgules françaises ;
    #    latin-1 : l'encodage utilisé par l'Arcep
    fichier = sorted(ARCEP.glob("*data_habitations.csv"))[-1]   # le plus récent s'il y en a plusieurs
    m = pd.read_csv(
        fichier, sep=None, engine="python", encoding="latin-1", decimal=",",
        usecols=lambda c: c in COLONNES_ARCEP,
    )

    # 2) Noms en français, comme sites.csv
    m = m.rename(columns={
        "operator": "operateur",
        "latitude_start": "latitude",
        "longitude_start": "longitude",
        "bitrate_dl": "debit",                           # débit descendant, en Mb/s
    })

    # 3) Le test a-t-il réussi ? (True / False) -> le taux de réussite sera simplement la moyenne
    if "Result" in m:                                    # format jusqu'en 2025
        m["reussi"] = m["Result"] == "Success"
    else:                                                # format 2026 : plus de colonne « Result »
        # Pages web : chargée en moins de 10 s (en 2025, c'était exactement la définition de « Success ») ;
        # vidéos : qualité correcte. Téléchargements, envois, latence : pas d'info -> vide (seul le débit sert)
        m["reussi"] = m["loaded_in_less_10_secondes"].fillna(m["quality_correct"])

    # 4) On garde les tests avec une position, et on enregistre
    m = m.dropna(subset=["latitude", "longitude"])
    m = m[["operateur", "latitude", "longitude", "protocole", "reussi", "debit"]]
    enregistrer(m, SORTIE_MESURES)

    # Petit résumé pour vérifier (dans le log) : nombre de tests, taux de réussite et débit par opérateur
    print("Mesures Arcep :", len(m))
    print(m.groupby("operateur").agg(nb_tests=("reussi", "count"),
                                     taux_reussite=("reussi", "mean"),
                                     nb_debits=("debit", "count"),
                                     debit_median=("debit", "median")))



# =====================================================================
# Lancement : python -m pipeline.clean (ou run.sh, juste après collect.py)
# On ne nettoie une source QUE si son brut est là, c'est-à-dire si collect.py vient de la télécharger.
# Ensuite on supprime le brut : il ne sert plus, et on libère la place sur le disque.
# =====================================================================
if __name__ == "__main__":
    if (ANFR / "SUP_STATION.txt").exists():
        clean()
        shutil.rmtree(ANFR)                  # le brut ne sert plus : on libère la place
    else:
        print("ANFR : rien de nouveau à nettoyer")

    if list(ARCEP.glob("*data_habitations.csv")):
        clean_arcep()
        shutil.rmtree(ARCEP)
    else:
        print("ARCEP : rien de nouveau à nettoyer")
