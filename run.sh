#!/bin/bash
# run.sh : l'appli tout de suite (les données sont dans le dépôt) + le pipeline en boucle en arrière-plan

export PYTHONIOENCODING=utf-8
INTERVALLE=86400        # temps entre 2 passages, en secondes (86400 = 24 h)
mkdir -p log

# Quand le script s'arrête (Ctrl+C), on arrête aussi la boucle
trap 'kill 0' EXIT

# --- Le pipeline, rangé dans une fonction ---
# collect.py ne télécharge que si une source a publié une nouvelle version,
# clean.py ne traite que ce qui vient d'être téléchargé puis supprime le brut.
pipeline() {
    LOG="log/pipeline_$(date +%Y-%m-%d_%H-%M).log"
    echo "=== Début : $(date) ===" >> "$LOG"
    python collect.py >> "$LOG" 2>&1 \
        && python clean.py >> "$LOG" 2>&1 \
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
python app.py
