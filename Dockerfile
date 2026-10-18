# 1) Partir d'un Linux avec Python déjà installé
FROM python:3.14-slim

# 2) Se placer dans un dossier /app à l'intérieur du conteneur
WORKDIR /app

# 3) Installer les librairies (d'abord, pour profiter du cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4) Copier le code du projet
COPY . .

# 5) Dire que l'appli utilise le port 8501
EXPOSE 8501

# 6) La commande lancée au démarrage du conteneur
CMD ["bash", "run.sh"]