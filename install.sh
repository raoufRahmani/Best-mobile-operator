#!/bin/bash
# install.sh : à lancer une seule fois, juste après le git clone (comme le install.sh de l'appli du prof).
# Trouve Python, installe les librairies et crée les dossiers de travail. Ensuite : bash run.sh

# Le nom de Python change selon l'installation : python, python3, ou py (Windows)
for nom in python python3 py; do
    if $nom --version > /dev/null 2>&1; then PYTHON=$nom; break; fi
done
if [ -z "$PYTHON" ]; then
    echo "Python introuvable : installe-le depuis https://www.python.org (cocher « Add python.exe to PATH »)"
    exit 1
fi
echo "Python trouvé : $($PYTHON --version)"

# Les dossiers de travail (ignorés par Git)
mkdir -p log archived

# Les librairies
if ! $PYTHON -m pip install -r requirements.txt; then
    echo "Échec de l'installation des librairies"
    exit 1
fi

echo
echo "Installation terminée. Lance l'appli avec : bash run.sh"
