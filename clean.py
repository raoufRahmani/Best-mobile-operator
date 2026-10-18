"""
clean.py — Étape 2 du pipeline
Lit les tables ANFR brutes (data_raw/anfr/) et produit un fichier propre :
data/sites.csv = 1 ligne par site × opérateur × techno × fréquence (France métropolitaine, 4G/5G).
"""
from pathlib import Path
import pandas as pd

ANFR = Path("data_raw/anfr")
SORTIE = Path("data/sites.csv")
ARCEP = Path("data_raw/arcep")
SORTIE_MESURES = Path("data/mesures.csv")
# Les 4 opérateurs mobiles (ADM_ID dans SUP_EXPLOITANT)
OPERATEURS = {"6": "Bouygues", "23": "Orange", "137": "SFR", "240": "Free"}


def lire(nom, colonnes):
    """Lit une table ANFR (séparateur ;) en texte, seulement les colonnes utiles."""
    for enc in ["utf-8", "latin-1"]:
        try:
            return pd.read_csv(ANFR / f"{nom}.txt", sep=";", dtype=str, encoding=enc, usecols=colonnes)
        except UnicodeDecodeError:
            continue


def en_decimal(deg, minu, sec, sens, negatif):
    """Degrés / minutes / secondes -> degrés décimaux (négatif si Sud ou Ouest)."""
    num = lambda s: pd.to_numeric(s.str.replace(",", "."), errors="coerce")
    val = num(deg) + num(minu) / 60 + num(sec) / 3600
    return val.where(sens != negatif, -val)


def clean():
    # 1) Les sites des 4 opérateurs
    station = lire("SUP_STATION", ["STA_NM_ANFR", "ADM_ID"])
    station = station[station["ADM_ID"].isin(OPERATEURS)]
    station["operateur"] = station["ADM_ID"].map(OPERATEURS)
    print("Sites des 4 opérateurs :", len(station))

    # 2) Les émetteurs 4G / 5G de ces sites
    em = lire("SUP_EMETTEUR", ["STA_NM_ANFR", "EMR_LB_SYSTEME", "EMR_DT_SERVICE"])
    em = em[em["STA_NM_ANFR"].isin(station["STA_NM_ANFR"])]
    lib = em["EMR_LB_SYSTEME"].fillna("")
    em["techno"] = None
    em.loc[lib.str.match(r"^LTE \d+$"), "techno"] = "4G"        # LTE 700, 800, 1800...
    em.loc[lib.str.match(r"^5G NR \d+$"), "techno"] = "5G"      # 5G NR 700, 2100, 3500 (pas les "Expe")
    em = em.dropna(subset=["techno"])
    em["frequence"] = em["EMR_LB_SYSTEME"].str.extract(r"(\d+)$", expand=False).astype(int)
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
    sup["code_insee"] = sup["COM_CD_INSEE"].str.strip().str.zfill(5)

    # 4) On assemble
    sites = (
        em.merge(station[["STA_NM_ANFR", "operateur"]], on="STA_NM_ANFR")
          .merge(sup[["STA_NM_ANFR", "latitude", "longitude", "code_insee"]], on="STA_NM_ANFR", how="left")
          .rename(columns={"STA_NM_ANFR": "site_id"})
    )

    # 5) France métropolitaine uniquement, positions valides
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

    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    sites.to_csv(SORTIE, index=False)

    # Petit résumé pour vérifier
    print("\nLignes dans", SORTIE, ":", len(sites))
    print("Communes :", sites["code_insee"].nunique())
    print("\nSites par opérateur et techno :")
    print(sites.drop_duplicates(["site_id", "techno"])
               .pivot_table(index="operateur", columns="techno", values="site_id", aggfunc="count", fill_value=0))
    print("\nclean OK")



def clean_arcep():
    # 1) Lire le fichier Arcep (seulement les colonnes utiles)
    fichier = sorted(ARCEP.glob("*data_habitations.csv"))[-1]
    m = pd.read_csv(
        fichier, sep=None, engine="python", encoding="latin-1", decimal=",",
        usecols=["operator", "latitude_start", "longitude_start", "protocole", "Result", "bitrate_dl"],
    )

    # 2) Noms en français, comme sites.csv
    m = m.rename(columns={
        "operator": "operateur",
        "latitude_start": "latitude",
        "longitude_start": "longitude",
        "bitrate_dl": "debit",
    })

    # 3) Le test a-t-il réussi ? (True / False)
    m["reussi"] = m["Result"] == "Success"

    # 4) On garde les tests avec une position, et on enregistre
    m = m.dropna(subset=["latitude", "longitude"])
    m = m[["operateur", "latitude", "longitude", "protocole", "reussi", "debit"]]
    m.to_csv(SORTIE_MESURES, index=False)

    print("Mesures Arcep :", len(m))
    print(m.groupby("operateur").agg(nb_tests=("reussi", "size"),
                                     taux_reussite=("reussi", "mean"),
                                     nb_debits=("debit", "count"),
                                     debit_median=("debit", "median")))



if __name__ == "__main__":
    clean()
    clean_arcep()