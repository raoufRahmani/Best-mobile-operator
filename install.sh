#!/bin/bash
# install.sh : à lancer une seule fois, juste après le git clone (comme le install.sh de l'appli du prof).
# Crée l'environnement Python du projet (.venv), y installe les librairies, crée les dossiers de travail.
# Marche sous Windows (Git Bash), Mac et Linux. Ensuite : bash run.sh

cd "$(dirname "$0")" || exit 1        # on travaille toujours depuis le dossier du projet

source bin/trouver_python.sh
if [ -z "$PYTHON" ]; then
    echo "Il faut Python 3.12, 3.13 ou 3.14 : https://www.python.org/downloads/"
    echo "(Windows : cocher « Add python.exe to PATH » pendant l'installation)"
    exit 1
fi

# 1) L'environnement du projet : les librairies s'installent dans .venv, pas dans tout l'ordinateur
#    (c'est obligatoire sur les Linux récents et sur Mac avec Homebrew, qui refusent « pip install » ailleurs)
if [ ! -d .venv ]; then
    echo "Création de l'environnement .venv avec $($PYTHON --version)"
    if ! $PYTHON -m venv .venv; then
        echo "Impossible de créer .venv. Sous Debian/Ubuntu : sudo apt install python3-venv"
        exit 1
    fi
fi
source bin/trouver_python.sh          # cette fois, il trouve le Python de .venv
case "$PYTHON" in
    .venv/*) ;;
    *) echo "Le dossier .venv existe mais ne marche pas (autre système ou autre version de Python) :"
       echo "supprime-le, puis relance : bash install.sh"
       exit 1 ;;
esac

# 2) Les librairies
$PYTHON -m pip --version > /dev/null 2>&1 || $PYTHON -m ensurepip --upgrade > /dev/null   # .venv sans pip (ex. créé par uv)
if ! $PYTHON -m pip install -r requirements.txt; then
    echo "Échec de l'installation des librairies"
    exit 1
fi

# 3) Les dossiers de travail (ignorés par Git)
mkdir -p log archived

echo
echo "Installation terminée ($($PYTHON --version), dans .venv). Lance l'appli avec : bash run.sh"
