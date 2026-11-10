#!/bin/bash
# run.sh : l'appli tout de suite (les données sont dans le dépôt) + le pipeline en boucle en arrière-plan

export PYTHONIOENCODING=utf-8
INTERVALLE=86400        # temps entre 2 passages, en secondes (86400 = 24 h)
mkdir -p log

# Le nom de Python change selon l'installation : python, python3, ou py (Windows)
for nom in python python3 py; do
    if $nom --version > /dev/null 2>&1; then PYTHON=$nom; break; fi
done
if [ -z "$PYTHON" ]; then
    echo "Python introuvable : installe-le depuis https://www.python.org (cocher « Add python.exe to PATH »)"
    exit 1
fi

# Quand le script s'arrête (Ctrl+C), on arrête aussi la boucle
trap 'kill 0' EXIT

# --- Le pipeline, rangé dans une fonction ---
# collect.py ne télécharge que si une source a publié une nouvelle version,
# clean.py ne traite que ce qui vient d'être téléchargé puis supprime le brut.
pipeline() {
    LOG="log/pipeline_$(date +%Y-%m-%d_%H-%M).log"
    echo "=== Début : $(date) ===" >> "$LOG"
    $PYTHON collect.py >> "$LOG" 2>&1 \
        && $PYTHON clean.py >> "$LOG" 2>&1 \
        || echo "!!! Échec du pipeline" >> "$LOG"
    echo "=== Fin : $(date) ===" >> "$LOG"
    echo "Pipeline terminé, voir $LOG"
}

# 1) Le pipeline en boucle, en arrière-plan (1er passage tout de suite)
(
    while true; do
        pipeline
        sleep "$INTERVALLE"
    done
) &

# 2) L'appli (Flask, port 8501), au premier plan : elle démarre avec les données du dépôt
#    et se recharge toute seule quand le pipeline les met à jour
$PYTHON app.py
