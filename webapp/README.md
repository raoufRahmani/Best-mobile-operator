# webapp — l'appli web

Le but : à partir d'une adresse, comparer Orange, SFR, Bouygues et Free, et afficher le verdict.
Lit les fichiers préparés par le pipeline (`data/`) et les relit tout seul quand ils changent.

| Fichier | Rôle |
|---|---|
| `app.py` | Flask : la page (`/`), les suggestions d'adresses (`/api/adresses`), le verdict (`/api/score`) |
| `adresse.py` | Adresse → coordonnées GPS (API Adresse de l'IGN) |
| `antennes_proches.py` | Antennes à moins d'1 km, tests Arcep à moins de 2 km (lissés avec la moyenne nationale) |
| `score.py` | Combine tout en un score sur 100 et un verdict |
| `templates/index.html` | La page |
| `static/style.css`, `static/app.js` | Le design et l'interactivité (carte Leaflet) |

## Lancement

Automatique avec `bash run.sh` : port 8501, la page s'ouvre toute seule, log dans `log/webapp.log`.

À la main, **depuis la racine du projet** :

```bash
python -m webapp.app
```
