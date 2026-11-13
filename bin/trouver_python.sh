#!/bin/bash
# trouver_python.sh : trouve un Python utilisable et le met dans la variable PYTHON.
# Utilisé par install.sh et run.sh : « source bin/trouver_python.sh ».
# Il faut Python 3.12, 3.13 ou 3.14 (numpy, pyproj et rasterio demandent au moins 3.12 ;
# certaines librairies n'existent pas encore pour 3.15).

version_ok() {
    $1 -c "import sys; sys.exit(not (3, 12) <= sys.version_info[:2] <= (3, 14))" > /dev/null 2>&1
}

PYTHON=""

# 1) L'environnement du projet (.venv), s'il existe : bin/ sous Mac et Linux, Scripts/ sous Windows
for candidat in .venv/bin/python .venv/Scripts/python.exe; do
    if [ -z "$PYTHON" ] && version_ok "$candidat"; then PYTHON="$candidat"; fi
done

# 2) Sinon, le Python de l'ordinateur : son nom change selon le système
#    (python3 sous Mac et Linux, python ou py sous Windows)
for candidat in python3.14 python3.13 python3.12 python3 python "py -3.14" "py -3.13" "py -3.12"; do
    if [ -z "$PYTHON" ] && version_ok "$candidat"; then PYTHON="$candidat"; fi
done
