# pipeline — préparer les données

Le but : récupérer les données ouvertes (ANFR, Arcep) et les transformer en petits fichiers prêts pour l'appli, dans `data/`.
Tourne en arrière-plan, toutes les 24 h.

| Fichier | Rôle |
|---|---|
| `collect.py` | **Étape 1** : télécharge dans `data_raw/`, seulement si une source a publié une nouvelle version (mémoire : `data/derniere_version.json`) |
| `clean.py` | **Étape 2** : nettoie, écrit `data/sites.csv.gz` et `data/mesures.csv.gz`, puis supprime le brut |
| `couverture.py` | Transforme les cartes de couverture Arcep en grille `data/couverture_4g.npz` (appelé par `collect.py`) ; lit aussi le niveau à un point pour l'appli |
| `archive.py` | Range l'ancienne version d'un fichier de `data/` dans `archived/` avant de la remplacer |

Les adresses des sources et les chemins des fichiers sont dans `config.py`, à la racine du projet.

## Lancement

Automatique avec `bash run.sh` (un log par passage dans `log/`).

À la main, **depuis la racine du projet**, avec le Python de `.venv` (`.venv/bin/python` sous Mac et Linux, `.venv/Scripts/python` sous Windows) à la place de `python` :

```bash
python -m pipeline.collect
python -m pipeline.clean
```
