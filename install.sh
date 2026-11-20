#!/bin/bash
# install.sh : à lancer une seule fois, juste après le git clone (comme le install.sh de l'appli du prof).
# Crée l'environnement Python du projet (.venv) avec uv, y installe les librairies, crée les dossiers de travail.
# Marche sous Windows (Git Bash), Mac et Linux. Ensuite : bash run.sh

cd "$(dirname "$0")" || exit 1        # on travaille toujours depuis le dossier du projet

# 1) uv : l'outil qui gère Python et les librairies du projet (https://docs.astral.sh/uv/)
if ! command -v uv > /dev/null 2>&1; then
    echo "Il faut d'abord installer uv :"
    echo "  Mac / Linux : curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "  Windows     : powershell -ExecutionPolicy ByPass -c \"irm https://astral.sh/uv/install.ps1 | iex\""
    echo "puis ferme et rouvre le terminal, et relance : bash install.sh"
    exit 1
fi

# 2) L'environnement .venv + les librairies, aux versions exactes de uv.lock.
#    uv télécharge lui-même Python 3.14 (.python-version) s'il n'est pas sur l'ordinateur.
if ! uv sync --frozen; then
    echo "Échec de l'installation des librairies"
    echo "Si le dossier .venv vient d'un autre ordinateur ou d'une autre version de Python :"
    echo "supprime-le, puis relance : bash install.sh"
    exit 1
fi

# 3) Les dossiers de travail (ignorés par Git)
mkdir -p log archived

echo
echo "Installation terminée ($(uv run --frozen python --version), dans .venv). Lance l'appli avec : bash run.sh"
