#!/bin/bash
# =====================================================================
# extraction.sh — Étape 1 du pipeline : l'extraction des données, en bash (curl)
# Télécharge les données brutes dans data_raw/, seulement si une source a publié une nouvelle version
# (les versions déjà traitées sont notées dans data/derniere_version.json, « le carnet »).
# Lancement, depuis n'importe où : bash pipeline/extraction.sh   (run.sh le lance toutes les 24 h)
#
# Le principe, pour chacune des 3 sources :
#   1. regarder quelle est la dernière version publiée en ligne (curl + grep)
#   2. la comparer avec celle notée dans le carnet
#   3. si c'est la même : on ne fait rien
#   4. sinon : on télécharge, on fait le ménage, et on note la version dans le carnet EN DERNIER
#      (si ça plante au milieu, le passage suivant recommence au lieu de croire que c'est fait)
# Seule la couverture a besoin de Python (pipeline/grille.py) : ouvrir les .7z et calculer la grille.
# =====================================================================

cd "$(dirname "$0")/.." || exit 1          # on travaille depuis la racine du projet

# curl (télécharger) et unzip (ouvrir les zips ANFR) sont indispensables
for outil in curl unzip; do
    if ! command -v "$outil" > /dev/null; then
        echo "Il manque « $outil » : l'installer (Ubuntu : sudo apt install $outil)"
        exit 1
    fi
done

# Le Python du projet (seulement pour la grille de couverture)
[ -z "$PYTHON" ] && source bin/trouver_python.sh


# ---------- Les réglages : lus dans config.py (un seul fichier de configuration pour tout le projet)
conf() { sed -n "s/^$1 *= *\"\([^\"]*\)\".*/\1/p" config.py; }
API_DATAGOUV=$(conf API_DATAGOUV)
JEU_ANFR=$(conf JEU_ANFR)
JEU_ARCEP=$(conf JEU_ARCEP)
PAGE_COUVERTURE=$(conf PAGE_COUVERTURE)
BRUT=data_raw
MEMO=data/derniere_version.json

# Télécharger une page ou un fichier : -f = échec si erreur HTTP, -L = suivre les redirections,
# abandon si moins de 1 ko/s pendant 60 s (plutôt que d'attendre indéfiniment)
telecharger() { curl -sSfL --retry 3 --connect-timeout 30 -y 60 -Y 1000 "$@"; }

# Assembler une adresse : un lien trouvé dans une page -> une adresse complète
joindre() {
    case "$2" in
        http*) echo "$2" ;;                                                        # déjà complète
        /*)    echo "$(echo "$1" | sed -E 's#^(https?://[^/]+).*#\1#')$2" ;;     # depuis la racine du site
        *)     echo "${1%/*}/$2" ;;                                                # dans le même dossier
    esac
}


# =====================================================================
# Le carnet des versions : data/derniere_version.json
# =====================================================================
carnet() { [ -f "$MEMO" ] && tr -d '\r\n' < "$MEMO"; }

# Lire une entrée texte du carnet ("anfr" ou "arcep")
lire_memo() { carnet | grep -o "\"$1\": *\"[^\"]*\"" | sed 's/.*: *"\(.*\)"/\1/'; }
# Lire la liste "couverture" (une adresse par ligne)
lire_memo_couverture() { carnet | grep -o '"couverture": *\[[^]]*\]' | grep -o 'https*://[^"]*'; }

# Réécrire le carnet en changeant UNE entrée : ecrire_memo anfr|anfr_mois|arcep|couverture "valeur"
# (écrit à côté puis renommé : jamais de carnet à moitié écrit)
# anfr_mois (ex. « novembre 2026 ») est affiché sur la page par l'appli (fraîcheur des données)
ecrire_memo() {
    local anfr anfr_mois arcep couv
    anfr=$(lire_memo anfr); anfr_mois=$(lire_memo anfr_mois); arcep=$(lire_memo arcep); couv=$(lire_memo_couverture)
    case "$1" in
        anfr) anfr=$2 ;;
        anfr_mois) anfr_mois=$2 ;;
        arcep) arcep=$2 ;;
        couverture) couv=$2 ;;
    esac
    mkdir -p data
    {
        printf '{\n  "anfr": "%s",\n  "anfr_mois": "%s",\n  "arcep": "%s",\n  "couverture": [' "$anfr" "$anfr_mois" "$arcep"
        local premier=1
        for url in $couv; do
            [ $premier = 1 ] && printf '\n' || printf ',\n'
            printf '    "%s"' "$url"; premier=0
        done
        [ $premier = 1 ] && printf ']\n}\n' || printf '\n  ]\n}\n'
    } > "$MEMO.tmp" && mv "$MEMO.tmp" "$MEMO"
}


# =====================================================================
# Source 1 : ANFR — où sont les antennes (mise à jour chaque mois)
# =====================================================================

# Le mois de publication d'un zip ANFR, en français, lu dans son adresse (.../20261106-083007/... -> « novembre 2026 »)
mois_anfr() {
    local date
    date=$(echo "$1" | grep -o '/[0-9]\{8\}-[0-9]\{6\}/' | cut -c2-9)
    set -- janvier février mars avril mai juin juillet août septembre octobre novembre décembre
    shift $(( 10#${date:4:2} - 1 ))
    echo "$1 ${date:0:4}"
}
extraction_anfr() {
    # 1) On demande à l'API data.gouv la liste des fichiers du jeu de données, et on garde
    #    les 2 zips les plus récents (leur adresse contient la date : le tri alphabétique suffit)
    local json data ref a_jour dossier
    json=$(telecharger "$API_DATAGOUV$JEU_ANFR/") || return 1
    data=$(echo "$json" | grep -o 'https://[^"]*export-etalab-data\.zip' | sort | tail -1)
    ref=$(echo "$json" | grep -o 'https://[^"]*export-etalab-ref\.zip' | sort | tail -1)
    if [ -z "$data" ] || [ -z "$ref" ]; then
        echo "ANFR : fichiers introuvables sur data.gouv.fr"; return 1
    fi
    a_jour="$data $ref"

    # 2) Mêmes fichiers que dans le carnet : rien de nouveau, on s'arrête
    if [ "$(lire_memo anfr)" = "$a_jour" ]; then
        echo "ANFR : pas de nouvelle version"; return 0
    fi

    # 3) Nouvelle version : on télécharge les 2 zips (~30 Mo chacun) et on les extrait dans data_raw/anfr/
    dossier="$BRUT/anfr"
    mkdir -p "$dossier"
    for url in $data $ref; do
        echo "ANFR : téléchargement de ${url##*/}"
        telecharger -o "$dossier/archive.zip" "$url" || return 1
        unzip -o -q "$dossier/archive.zip" -d "$dossier" || return 1
        rm -f "$dossier/archive.zip"
    done

    # 4) On supprime tout de suite 2 tables dont on ne se sert pas (235 Mo de place libérée)
    rm -f "$dossier/SUP_BANDE.txt" "$dossier/SUP_ANTENNE.txt"

    # 5) Tout a réussi : on note la version dans le carnet (en dernier)
    ecrire_memo anfr "$a_jour"
    # + le mois de publication, pour la page : la date est dans l'adresse (.../20261106-083007/... -> « novembre 2026 »)
    ecrire_memo anfr_mois "$(mois_anfr "$data")"
    echo "ANFR OK"
}


# =====================================================================
# Source 2 : Arcep — les tests de terrain, « est-ce que ça marche en vrai ? » (chaque année)
# =====================================================================
extraction_arcep() {
    # 1) data.gouv ne donne pas le fichier, mais l'adresse d'un dossier du site de l'Arcep
    local dossier_url annees page_url lien fichier_url nom dossier
    dossier_url=$(telecharger "$API_DATAGOUV$JEU_ARCEP/" | grep -o '"url": "https://data\.arcep\.fr/mobile/mesures_qualite_arcep/[^"]*"' \
                  | head -1 | cut -d'"' -f4)
    [ -z "$dossier_url" ] && { echo "ARCEP : dossier des mesures introuvable sur data.gouv.fr"; return 1; }

    # 2) On repère les années ("2026", "2025"...), de la plus récente à la plus ancienne
    #    (un dossier par année ; la plus récente n'a pas toujours la Métropole, ex. 2026 : Outre-mer seulement)
    annees=$(telecharger "${dossier_url}index.html" | grep -o 'href="[0-9]\{4\}/index\.html"' | grep -o '[0-9]\{4\}' | sort -ru)

    # 3) On essaie chaque année jusqu'à trouver le fichier data_habitations.csv de la Métropole
    fichier_url=""
    for annee in $annees; do
        page_url="${dossier_url}$annee/Metropole/index.html"
        lien=$(telecharger "$page_url" 2> /dev/null | grep -o 'href="[^"]*data_habitations\.csv"' | head -1 | cut -d'"' -f2)
        if [ -n "$lien" ]; then
            fichier_url=$(joindre "$page_url" "$lien")
            break                                        # trouvé : on arrête de chercher
        fi
    done
    # Rien trouvé (l'Arcep a encore changé ses dossiers ?) : message clair, sans planter le pipeline
    if [ -z "$fichier_url" ]; then
        echo "ARCEP : fichier data_habitations introuvable sous $dossier_url"; return 0
    fi

    # 4) On compare le nom du fichier avec le carnet (pas l'adresse complète :
    #    l'Arcep déplace parfois ses dossiers sans changer les données)
    nom="${fichier_url##*/}"
    if [ "$(lire_memo arcep | sed 's#.*/##')" = "$nom" ]; then
        echo "ARCEP : pas de nouvelle version"; return 0
    fi

    # 5) Nouveau fichier : on le télécharge (93 Mo)
    dossier="$BRUT/arcep"
    mkdir -p "$dossier"
    echo "ARCEP : téléchargement de $nom"
    telecharger -o "$dossier/$nom" "$fichier_url" || return 1

    # 6) On note la version dans le carnet (en dernier)
    ecrire_memo arcep "$fichier_url"
    echo "ARCEP OK"
}


# =====================================================================
# Source 3 : Arcep — la carte officielle de couverture 4G (chaque trimestre)
# C'est la plus lourde : 4 fichiers .7z (~1,3 Go), 3 Go une fois extraits.
# =====================================================================
extraction_couverture() {
    # 1) On lit la page de l'Arcep et on y cherche les liens des 4 fichiers (un par opérateur)
    local liens dossier
    liens=$(telecharger "$PAGE_COUVERTURE" | grep -o 'href="[^"]*_4G_data\.gpkg\.7z"' | cut -d'"' -f2 \
            | while read -r lien; do joindre "$PAGE_COUVERTURE" "$lien"; done)
    if [ -z "$liens" ]; then
        echo "COUVERTURE : fichiers 4G introuvables sur $PAGE_COUVERTURE"; return 0
    fi

    # 2) Mêmes fichiers que dans le carnet, et la grille existe déjà : rien à faire
    if [ "$(lire_memo_couverture)" = "$liens" ] && [ -f data/couverture_4g.npz ]; then
        echo "COUVERTURE : pas de nouvelle version"; return 0
    fi

    # 3) On efface les restes d'un passage précédent qui aurait planté au milieu
    dossier="$BRUT/couverture"
    mkdir -p "$dossier"
    rm -f "$dossier"/*.gpkg "$dossier"/*.7z "$dossier"/*.npy

    # 4) Un opérateur à la fois : télécharger (bash) -> extraire + grille 100 m (Python) -> supprimer
    #    (~1 Go max sur le disque)
    for url in $liens; do
        echo "COUVERTURE : téléchargement de ${url##*/}"
        telecharger -o "$dossier/${url##*/}" "$url" || return 1
        $PYTHON -m pipeline.grille "$dossier/${url##*/}" || return 1
    done

    # 5) On assemble les 4 grilles en une seule (21 Mo) et on la met en place sans risque (Python)
    $PYTHON -m pipeline.grille --assembler || return 1

    # 6) On note la version dans le carnet (en dernier)
    ecrire_memo couverture "$liens"
    echo "COUVERTURE OK"
}


# =====================================================================
# Lancement : les 3 sources l'une après l'autre ; on s'arrête à la première erreur
# (run.sh note alors « Échec du pipeline » dans le log, et réessaie au passage suivant)
# =====================================================================
extraction_anfr && extraction_arcep && extraction_couverture
