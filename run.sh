#!/bin/bash
# run.sh : l'appli tout de suite (les données sont dans le dépôt) + le pipeline en boucle en arrière-plan
# Marche sous Windows (Git Bash), Mac, Linux et dans Docker.

cd "$(dirname "$0")" || exit 1   # on travaille toujours depuis le dossier du projet
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1        # les messages arrivent tout de suite dans les logs
INTERVALLE=86400                 # temps entre 2 passages, en secondes (86400 = 24 h)
mkdir -p log archived

# Le Python de .venv (créé par install.sh), sinon celui de l'ordinateur (ex. dans Docker)
source bin/trouver_python.sh
if [ -z "$PYTHON" ]; then
    echo "Python 3.12 à 3.14 introuvable : lance d'abord « bash install.sh »"
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
    $PYTHON -m pipeline.collect >> "$LOG" 2>&1 \
        && $PYTHON -m pipeline.clean >> "$LOG" 2>&1 \
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
#    et se recharge toute seule quand le pipeline les met à jour.
#    Ses messages s'affichent dans le terminal ET sont gardés dans log/webapp.log
$PYTHON -m webapp.app 2>&1 | tee -a log/webapp.log
