# 1) Partir d'un Linux avec Python déjà installé
FROM python:3.14-slim

# 2) Se placer dans un dossier /app à l'intérieur du conteneur
WORKDIR /app

# 3) Installer les librairies (d'abord, pour profiter du cache)
#    rasterio a besoin de libexpat1, absente de l'image "slim"
RUN apt-get update && apt-get install -y --no-install-recommends libexpat1 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4) Copier le code du projet
COPY . .

# 5) Dire que l'appli utilise le port 8501
EXPOSE 8501

# 6) Supervision : toutes les 30 s, Docker vérifie que l'appli répond sur /sante
#    (« docker ps » affiche alors healthy ou unhealthy). Python suffit, pas besoin de curl.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3     CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/sante', timeout=4)"

# 7) La commande lancée au démarrage du conteneur
CMD ["bash", "run.sh"]