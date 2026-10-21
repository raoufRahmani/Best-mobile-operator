#!/bin/bash
# run.sh : pipeline une 1re fois, puis en boucle en arrière-plan, + l'appli

export PYTHONIOENCODING=utf-8
INTERVALLE=86400        # temps entre 2 passages, en secondes (86400 = 24 h)
mkdir -p log

# Quand le script s'arrête (Ctrl+C), on arrête aussi la boucle
trap 'kill 0' EXIT

# --- Le pipeline, rangé dans une fonction ---
pipeline() {
    LOG="log/pipeline_$(date +%Y-%m-%d_%H-%M).log"
    echo "=== Début : $(date) ===" >> "$LOG"
    python collect.py >> "$LOG" 2>&1 \
        && python clean.py >> "$LOG" 2>&1 \
        || echo "!!! Échec du pipeline" >> "$LOG"
    echo "=== Fin : $(date) ===" >> "$LOG"
    echo "Pipeline terminé, voir $LOG"
}

# 1) Premier passage : l'appli a besoin des données
pipeline

# 2) Les passages suivants, en boucle, en arrière-plan
(
    while true; do
        sleep "$INTERVALLE"
        pipeline
    done
) &

# 3) L'appli, au premier plan
streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --browser.gatherUsageStats false