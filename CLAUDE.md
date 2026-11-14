# CONTEXTE DU PROJET — « Quel opérateur chez moi ? »

> Ce fichier résume le projet et son état (mis à jour le 12/11/2026).
> **À donner à Claude au début d'une conversation** (claude.ai : joindre le fichier ;
> Claude Code : il est lu automatiquement, car il s'appelle `CLAUDE.md` à la racine du projet).
> Consigne pour Claude : lis tout ce fichier avant de répondre, et repars de la section « Où on en est ».

---

## 1. Le cours et la consigne

- Cours : **« Initiation au DevOps pour un Data Scientist »**, M2 MoSEF, Université Paris 1 Panthéon-Sorbonne.
- Projet noté **en binôme** (Aya WIFAK et Abderraouf Rahmani) : créer une **application qui manipule des données open data**, puis la **pitcher** devant un board technique en montrant la maîtrise de **la conception, du développement et du déploiement**.
- Plan du cours : **Enjeux du DevOps → Linux → Git → Docker**. Le projet suit le même chemin.
- Idées clés du chapitre 1 : 85 % des projets data échouent (souvent faute de mise en production) ; DevOps = Dev + Ops (culture + pratiques + outils) ; 3 modes de déploiement : **local** (problème de portabilité), **on-premise** (ne tient pas la charge), **cloud** (la cible).
- Le chapitre 1 ne nomme **aucun fournisseur cloud** : le serveur de déploiement est **à confirmer avec le prof**.

### L'appli exemple du prof
- Repo : https://github.com/eliamosef/mosef_app — « Student Profiler ».
- Fonctionnement : Google Form → téléchargement du Google Sheet (`curl`) → pandas → NLP spaCy → page Flask.
- Structure : `data_collector/` → `data_integrator/` → `data_processor/` → `webapp/`, orchestrés par des scripts bash dans `bin/` (pipeline **en boucle**, logs dans `log/`, archivage du brut), + un `Dockerfile`.
- **On n'a pas copié son code, on a gardé sa démarche** : étapes séparées (un dossier par rôle + README), fichier de configuration, script bash, boucle, logs (pipeline + webapp), archivage, Docker, déploiement.
- Ce qu'on a adapté : on archive les données **préparées** (quelques Mo), pas le brut (1,5 Go par version) ; on ne télécharge que les nouvelles versions (lui retélécharge en permanence) ; le score est calculé en direct car il dépend de l'adresse ; un seul `run.sh` pour local et Docker (lui a `run.sh` + `run-local.sh`).

---

## 2. Le sujet

**« Quel opérateur chez moi ? »**
L'utilisateur tape **son adresse** → l'appli compare **Orange, SFR, Bouygues Telecom et Free** → elle donne un **verdict** : « chez toi, prends X ».

| | |
|---|---|
| **Persona** | Quelqu'un qui déménage ou veut changer de forfait et se demande quel opérateur capte le mieux chez lui |
| **Problème** | Les opérateurs disent tous « meilleur réseau » ; les vraies données existent mais sont éparpillées et illisibles |
| **Fonctionnalités** | Adresse (avec suggestions pendant la frappe) → classement des 4 opérateurs (score / 100) + carte des antennes à moins d'1 km + verdict + conseil « marque moins chère sur le même réseau » (Sosh, RED by SFR, B&You) |
| **Limites** | Antenne proche ≠ bonne réception ; mesures Arcep dans ~1 600 communes seulement ; couverture = simulation des opérateurs ; 4G seulement pour la couverture ; pas d'outre-mer |

---

## 3. Les données (3 sources open data + 1 API)

| | **ANFR** | **Arcep — mesures** | **Arcep — couverture** | **API Adresse (IGN)** |
|---|---|---|---|---|
| Question | Où sont les antennes ? | Est-ce que ça marche en vrai ? | Que dit la carte officielle ici ? | Adresse → GPS |
| Mise à jour | Mensuelle | Annuelle | Trimestrielle | En direct |
| Brut | 2 zips `SUP_*.txt` (~60 Mo) | `data_habitations.csv` (93 Mo) | 4 × `.gpkg.7z` (~1,3 Go, 3 Go extraits) | — |
| Devient | `data/sites.csv.gz` (4,9 Mo) | `data/mesures.csv.gz` (1,4 Mo) | `data/couverture_4g.npz` (21 Mo) | rien de stocké |

Tout le détail (tables, colonnes, codes, score) est dans **`DICTIONNAIRE_DONNEES.md`**. L'exploration est dans **`01_exploration.ipynb`**.

Points à retenir :
- **ANFR** : séparateur `;`, décimale `,`, `dtype=str`. Clé commune `STA_NM_ANFR`. 4 tables utiles (STATION, EXPLOITANT, EMETTEUR, SUPPORT). Opérateurs : `ADM_ID` 6 Bouygues, 23 Orange, 137 SFR, 240 Free. 4G = `^LTE \d+$`, 5G = `^5G NR \d+$`. Coordonnées en degrés/minutes/secondes → `degrés + min/60 + sec/3600`, négatif si S ou W.
- **Arcep mesures** : `https://data.arcep.fr/mobile/mesures_qualite_arcep/` → un dossier par année avec un `index.html`. `last/` ne contient que l'outre-mer 2026 → la Métropole 2025 est sous `2025/Metropole/`. Encodage `latin-1`, `sep=None`. Débit `bitrate_dl` en Mb/s (tests `DOWNLOAD`).
- **Arcep couverture** : `https://data.arcep.fr/mobile/couvertures_theoriques/last/Metropole/00_Metropole/`, codes `OF` (Orange), `SFR0`, `BOUY`, `FREE`. Polygones en Lambert-93 (EPSG:2154), colonne `niveau` = `TBC` / `BC` / `CL`.
- **API Adresse** : `https://data.geopf.fr/geocodage/search?q=<adresse>&limit=1` (gratuite, sans clé) → coordonnées + `citycode`.

---

## 4. L'architecture (ce qui est codé)

```
INTERNET (open data)                      PIPELINE (tâche de fond, toutes les 24 h)                      APPLI

ANFR (mensuel) ───────┐
Arcep mesures (annuel) ┼─► collect.py ─► data_raw/ ─► clean.py ─────────────► data/ ──► app.py (Flask) ──► navigateur
Arcep couverture (trim.)┘   (si nouvelle   (temporaire,  (+ couverture.py      (~27 Mo,    + score.py
                             version)       supprimé)     pour la grille)       dans Git)   + API Adresse en direct
```

**Structure calquée sur l'appli du prof** (réorganisée le 12/11/2026) : un dossier par rôle avec son README, un fichier de configuration, un dossier d'archives, un log par composant.
On lance toujours **depuis la racine** : `bash run.sh`, ou à la main `python -m pipeline.collect`, `python -m pipeline.clean`, `python -m webapp.app` (sinon `import config` échoue).

| Fichier | Rôle |
|---|---|
| `config.py` | La configuration (équivalent du `collector.conf` du prof) : adresses des sources, dossiers (`data_raw/`, `data/`, `archived/`), fichiers préparés, port |
| `pipeline/archive.py` | `archiver(chemin)` : copie l'ancienne version d'un fichier de `data/` dans `archived/<date>_<nom>` avant qu'il soit remplacé (appelé par `clean.py` et `collect.py`) |
| `pipeline/collect.py` | Interroge l'API data.gouv.fr / les pages Arcep, ne télécharge **que les nouvelles versions** (mémoire : `data/derniere_version.json`). Supprime tout de suite `SUP_BANDE` et `SUP_ANTENNE` (inutiles). Couverture : un opérateur à la fois (télécharger → extraire → grille → supprimer). `forcer=True` sert au notebook |
| `pipeline/clean.py` | ANFR : filtre 4 opérateurs + 4G/5G + métropole, convertit les positions → `sites.csv.gz`. Arcep : garde 6 colonnes → `mesures.csv.gz`. Écriture atomique (fichier `.tmp` puis `os.replace`), gzip sans date (`mtime=0`). Supprime le brut ensuite |
| `pipeline/couverture.py` | Polygones Arcep → grille de cases de 100 m (rasterio), 4 opérateurs × 2 bits dans 1 octet par case. Lit le niveau à un point (0,03 ms) |
| `webapp/adresse.py` | Géocodage (`geocoder`) et suggestions (`chercher_adresses`) via l'API Adresse |
| `webapp/antennes_proches.py` | Distance de haversine ; antennes à moins d'1 km ; tests Arcep à moins de 2 km, **lissés** avec la moyenne nationale (`K = 20`) |
| `webapp/score.py` | Notes de 0 à 1 et score pondéré : 30 % couverture 4G, 30 % tests réussis, 20 % débit, 10 % 5G 3500 MHz, 10 % proximité |
| `webapp/app.py` | Flask, port 8501 : `/` (page), `/api/adresses` (suggestions), `/api/score` (verdict + classement + antennes). Relit les données quand leur date change. Servie par **waitress** (vrai serveur, Windows/Mac/Linux), une ligne de log par requête. Ouvre le navigateur seulement s'il y a un écran (Windows, Mac, Linux avec bureau). Port : `PORT=8600 bash run.sh` |
| `webapp/templates/index.html`, `webapp/static/style.css`, `webapp/static/app.js` | L'interface : HTML/CSS/JS, carte Leaflet (fond CARTO), design sombre bleu/violet (police Geist) |
| `install.sh` | À lancer une fois après le clone (comme le `install.sh` du prof) : crée l'environnement **`.venv`** (obligatoire sur Linux récent et Mac Homebrew, qui refusent `pip install` hors environnement), y installe `requirements.txt`, crée `log/` et `archived/`. Messages clairs si Python manque, est trop vieux, si `python3-venv` manque (Debian/Ubuntu) ou sur Windows ARM |
| `bin/trouver_python.sh` | Partagé par `install.sh` et `run.sh` : prend le Python de `.venv` (`bin/` ou `Scripts/`), sinon `python3.14`… `python3`, `python`, `py -3.x`, en exigeant **Python 3.12 à 3.14** (numpy/pyproj/rasterio ≥ 3.12 ; des dépendances de py7zr n'existent pas encore en 3.15) |
| `run.sh` | Se place dans le dossier du projet (`cd "$(dirname "$0")"`), trouve Python via `bin/trouver_python.sh` ; lance le pipeline en boucle **en arrière-plan** (1 passage tout de suite, puis toutes les 24 h, un log par passage dans `log/`) ; lance l'appli au premier plan (messages affichés **et** gardés dans `log/webapp.log` grâce à `tee`). Ctrl+C arrête tout |
| `Dockerfile` | `python:3.14-slim`, installe `requirements.txt`, copie le projet, `EXPOSE 8501`, `HEALTHCHECK` sur `/sante` toutes les 30 s (avec Python, pas curl), `CMD ["bash", "run.sh"]` |
| `webapp/app.py` → `/sante` | Supervision : 200 `{"statut": "ok"}` si les 3 fichiers de `data/` sont là, sinon 503. Pas écrit dans le log (Docker l'appelle toutes les 30 s) |
| `tests/` + `pytest.ini` + `requirements-dev.txt` | 12 tests pytest (calculs + routes Flask), sans Internet (géocodage remplacé par un faux). `python -m pytest` depuis la racine |
| `.github/workflows/ci.yml` | CI/CD GitHub Actions à chaque push/PR sur `master` : tests → `docker build` → conteneur démarré et `/sante` vérifié → `docker push` sur Docker Hub seulement si le secret `DOCKERHUB_TOKEN` existe |
| `.gitignore` / `.dockerignore` | `.venv/`, `data_raw/`, `log/`, `archived/`, `__pycache__/`, fichiers `.tmp` (+ `.git/` et `*.ipynb` pour Docker). **`data/` n'est pas ignoré** |
| `.gitattributes` | `*.sh text eol=lf` (sinon bash plante dans Linux) ; `*.gz` et `*.npz` en binaire |

Nanterre (8 rue du Port), résultat de référence : SFR 90, Bouygues 89, Free 86, Orange 79 → « prends SFR », conseil RED by SFR.

---

## 5. Choix importants (à savoir expliquer au pitch)

- **Séparer préparer / répondre** : le pipeline (lent, rare) tourne en fond ; l'appli (rapide) ne fait que lire `data/` et calculer autour de l'adresse.
- **Les données préparées sont dans Git** (~27 Mo) : un clone démarre tout de suite, sans télécharger 1,5 Go. Avant, il fallait ~3,5 Go sur le disque.
- **Ne télécharger que le nouveau** (mémoire des versions) et **supprimer le brut** après nettoyage.
- **Grille de couverture** : 3 Go de polygones → 21 Mo, lecture instantanée, 79 points sur 80 identiques au calcul exact.
- **Lissage des mesures** : peu de tests près de l'adresse → on se rapproche de la moyenne nationale (sinon un seul test raté pouvait faire perdre un opérateur).
- **Flask + HTML/CSS/JS** plutôt que Streamlit (version d'avant) : vrai design de site, API séparée de la page.

---

## 6. Git, Docker et serveur

- GitHub : `raoufRahmani/Best-mobile-operator`, **privé** (le binôme a été ajouté ; le prof devra l'être aussi, ou le dépôt rendu public). Branche principale `master`.
- Docker Hub : `raoufrhm/best-mobile-operator:latest`.
- Lancer : `docker run -p 8501:8501 -v bmo_data:/app/data raoufrhm/best-mobile-operator:latest` → http://localhost:8501 (le volume garde les mises à jour du pipeline).
- Publier : `docker build -t raoufrhm/best-mobile-operator .` puis `docker push raoufrhm/best-mobile-operator`.
- Sur un serveur : `docker pull` + `docker run -d -p 8501:8501 …` + **ouvrir le port 8501** dans le pare-feu.
- Options de serveur (vérifiées en octobre 2026) :
  - **Azure for Students** : 100 $ de crédits, **sans carte bancaire**, mail étudiant ; quand les crédits sont épuisés, l'abonnement est désactivé (pas de facture). ⭐ Choix conseillé.
  - Oracle Always Free : 2 cœurs / 12 Go RAM, carte demandée.
  - Google Cloud e2-micro : 1 Go RAM seulement → trop petit.
  - AWS : jusqu'à 200 $ de crédits pendant 6 mois, carte demandée.
  - Prévoir **≥ 2 Go de RAM** (la conversion de la couverture est la plus gourmande). Éteindre la VM quand on ne s'en sert pas.
- Lien temporaire pour une démo : `cloudflared tunnel --url http://localhost:8501` (certains réseaux bloquent QUIC / le port 7844).

### Pièges déjà rencontrés
| Erreur | Solution |
|---|---|
| `$'\r': command not found` dans le conteneur | `.gitattributes` avec `*.sh text eol=lf` |
| `python: command not found` (Ubuntu, ou Windows avec seulement `py`) | `bin/trouver_python.sh` essaie tous les noms (`python3.x`, `python3`, `python`, `py -3.x`) |
| `error: externally-managed-environment` au `pip install` (Ubuntu 23+, Debian 12, Mac Homebrew) | Installer dans un `.venv` : c'est ce que fait `install.sh` |
| `pip install` échoue avec Python 3.11 ou 3.15 | Il faut Python 3.12 à 3.14 : `install.sh` le vérifie |
| Windows ARM : `pyogrio` ne s'installe pas | Installer la version x64 de Python |
| Docker Desktop « Virtualization support not detected » | `wsl --install` en admin, redémarrer |
| L'appli tourne mais la page ne s'ouvre pas | Oubli du `-p 8501:8501`, port fermé sur le serveur, ou port 8501 déjà pris en local |
| `Repository not found` au `git clone` | Le dépôt est privé : ajouter la personne comme collaboratrice |
| Push refusé (`fetch first`) | Quelqu'un a modifié sur GitHub (ex. README) : `git pull --rebase origin master` puis `git push` |
| 404 sur `last/Metropole/` (Arcep) | L'Arcep a réorganisé ses dossiers : `collect.py` parcourt les années |
| Ajouter une ligne à un fichier sans saut de ligne final | Les 2 lignes se collent (arrivé 3 fois : `.gitignore`, `.gitattributes`, `requirements.txt`) : vérifier la fin du fichier avant d'ajouter |

---

## 7. Bonus mis de côté

- **Offres des opérateurs** : pas en open data → scraping (Free : JSON `__NEXT_DATA__` facile ; B&You : clics nécessaires ; RED : HTML fragile ; Sosh : 10 s entre deux requêtes) ou `offres.csv` rempli à la main. Pour l'instant, seul le conseil « marque moins chère sur le même réseau » est fait.
- **ML** : prédire où la 5G va arriver (historique mensuel ANFR).
- **API FastAPI** séparée de l'interface (2 conteneurs).
- Curseurs pour que l'utilisateur choisisse les poids du score.

---

## 8. Où on en est (12/11/2026)

**Fait ✅**
- Pipeline complet : `pipeline/collect.py` → `pipeline/clean.py` (+ `couverture.py`), avec mémoire des versions, suppression du brut et archivage des anciennes versions.
- Structure alignée sur l'appli du prof : `pipeline/` et `webapp/` (chacun avec son README), `config.py`, `archived/`, `log/webapp.log`.
- Score à l'adresse (couverture + mesures lissées + antennes) et interface Flask/HTML/CSS/JS avec carte.
- `run.sh` (boucle 24 h + logs + appli), `Dockerfile`, image Docker Hub.
- Données préparées dans Git : `git clone` + `bash install.sh` + `bash run.sh` suffit, la page s'ouvre toute seule.
- Le binôme a cloné et lancé l'appli sur son PC.
- Documentation : `README.md`, `DICTIONNAIRE_DONNEES.md`, `01_exploration.ipynb` à jour.
- (14/11/2026) Tests pytest, CI/CD GitHub Actions, route `/sante` + `HEALTHCHECK` Docker. Fond de carte CARTO (qui exige maintenant une clé) remplacé par le Plan IGN.

**À faire ⏳**
1. Demander au prof s'il fournit un serveur ; sinon **déployer sur Azure for Students** pour avoir une URL permanente à lui donner.
2. Donner l'accès au dépôt au prof (collaborateur, ou dépôt public).
3. Préparer le pitch : problème → démo live → schéma d'architecture → difficultés (fichiers lourds, dossiers Arcep déplacés, fins de ligne Windows, place sur le disque) → limites.
4. Bonus éventuels (section 7).

---

## 9. Conventions de travail pour Claude
- Répondre en **français**, de façon **concise et simple**.
- Code **simple et lisible**, pas de sur-ingénierie.
- Modifications **minimales et ciblées** du code existant, pas de réécriture complète.
- Commits : **pas de ligne `Co-Authored-By: Claude`**, aucune mention de Claude dans les messages de commit ou de PR.
- Environnement : Windows, VS Code, Git Bash, Python 3.14, Docker Desktop (WSL 2), PC ~8 Go de RAM.
- **Le projet doit marcher partout** : Windows (Git Bash), Mac (bash 3.2 !), Linux (Ubuntu serveur, sans écran), Docker. Testé le 13/11/2026 : Windows (clone neuf), Ubuntu 24.04 (Python 3.12), bash 3.2 ; refus propre de Python 3.11 et d'Ubuntu sans `python3-venv`.
