# 📶 Quel opérateur chez moi ?

Tu tapes ton adresse, l'appli te dit quel opérateur mobile capte le mieux **chez toi** : Orange, SFR, Bouygues Telecom ou Free.

Elle ne se base pas sur la pub des opérateurs, mais sur des **données publiques** : les antennes déclarées à l'ANFR, les tests de débit faits sur le terrain par l'Arcep, et les cartes de couverture officielles.

> Projet du cours **Initiation au DevOps pour un Data Scientist** — M2 MoSEF, Université Paris 1 Panthéon-Sorbonne.

---

## Lancer l'appli

### Avec Docker (le plus simple)

Il faut juste [Docker Desktop](https://www.docker.com/products/docker-desktop/) installé et lancé.

```bash
docker run -p 8501:8501 -v bmo_data:/app/data raoufrhm/best-mobile-operator:latest
```

Puis ouvrir **http://localhost:8501**.

⚡ L'appli démarre **tout de suite** : les données déjà préparées (~27 Mo) sont dans le dépôt, dans `data/`. Rien à télécharger. En arrière-plan, le pipeline vérifie chaque jour si l'ANFR ou l'Arcep ont publié une nouvelle version, et ne télécharge que dans ce cas. Le volume `bmo_data` garde ces mises à jour d'un lancement à l'autre.

### Sans Docker

```bash
git clone https://github.com/raoufRahmani/Best-mobile-operator.git
cd Best-mobile-operator
pip install -r requirements.txt
bash run.sh
```

La page s'ouvre toute seule dans le navigateur (**http://localhost:8501**).

Sous Windows, `run.sh` se lance depuis **Git Bash**. Si `pip` n'est pas reconnu, utilise `py -m pip install -r requirements.txt`.

---

## Comment ça marche

1. **L'adresse devient un point GPS**, grâce à l'API Adresse de l'État.
2. **On regarde ce qu'il y a autour**, pour chacun des 4 opérateurs :
   - les antennes 4G et 5G à moins d'1 km, et la distance de la plus proche (ANFR) ;
   - les tests réalisés par l'Arcep à moins de 2 km : taux de réussite et débit ;
   - le niveau de couverture 4G annoncé à cette adresse précise (cartes Arcep).
3. **Chaque critère devient une note de 0 à 1**, puis on fait une moyenne pondérée :

| Critère | Poids | Source |
|---|---|---|
| Couverture 4G officielle | 30 % | Arcep |
| Tests réussis autour de l'adresse | 30 % | Arcep |
| Débit mesuré | 20 % | Arcep |
| Antennes 5G rapide (3500 MHz) à moins d'1 km | 10 % | ANFR |
| Distance à l'antenne la plus proche | 10 % | ANFR |

**Un détail important :** l'Arcep n'a fait des tests que dans environ 1 600 communes. Quand il y a peu de tests près de l'adresse, on ne leur fait pas aveuglément confiance : on les mélange avec la moyenne générale, et plus il y a de tests, plus le local pèse. Sans ça, un seul test raté pouvait suffire à faire perdre un opérateur.

---

## Les données

Toutes les données sont ouvertes, et elles sont récupérées automatiquement via l'API de [data.gouv.fr](https://www.data.gouv.fr) :

| Source | Contenu | Mise à jour |
|---|---|---|
| [ANFR – Installations radioélectriques](https://www.data.gouv.fr/datasets/donnees-sur-les-installations-radioelectriques-de-plus-de-5-watts-1) | Position, opérateur et technologie de chaque antenne | Mensuelle |
| [Arcep – Mon Réseau Mobile](https://www.data.gouv.fr/datasets/mon-reseau-mobile) | Mesures de qualité de service + cartes de couverture 4G | Annuelle / trimestrielle |
| [API Adresse (IGN)](https://geoservices.ign.fr/documentation/services/services-geoplateforme/geocodage) | Adresse → coordonnées GPS | En direct |

---

## Le pipeline

```
collect.py  →  clean.py  →  app.py
```

| Fichier | Rôle |
|---|---|
| `collect.py` | Télécharge une source seulement si elle a publié une nouvelle version (mémoire : `data/derniere_version.json`) |
| `clean.py` | Nettoie et assemble (4 opérateurs, 4G/5G, France métropolitaine) dans `data/*.csv.gz`, puis supprime les fichiers bruts |
| `adresse.py` | Transforme une adresse en coordonnées GPS |
| `antennes_proches.py` | Antennes et mesures Arcep autour d'un point |
| `couverture.py` | Transforme les cartes de couverture 4G (3 Go) en une grille de 100 m (21 Mo), et lit le niveau à un point |
| `score.py` | Combine tout en un score et un verdict |
| `app.py` + `templates/` + `static/` | L'interface (Flask + HTML/CSS/JS) |
| `run.sh` | Démarre l'appli tout de suite et lance le pipeline toutes les 24 h en arrière-plan (logs dans `log/`). L'appli recharge les données toute seule quand elles changent |
| `Dockerfile` | Emballe le tout dans une image Docker |

Pour comprendre les données : [`01_exploration.ipynb`](01_exploration.ipynb) (la première exploration, faite avant d'écrire `clean.py`) et [`DICTIONNAIRE_DONNEES.md`](DICTIONNAIRE_DONNEES.md) (chaque source, colonne et code, et le détail du score).

---

## Limites

- Les cartes de couverture de l'Arcep ne couvrent que la **4G**. La 5G est évaluée à partir des antennes.
- Les mesures Arcep sont faites dans environ 1 600 communes : ailleurs, le score s'appuie surtout sur les antennes et la couverture.
- La France d'outre-mer n'est pas prise en compte.
- Le résultat est une **estimation** : il ne remplace pas un test sur place avec son propre téléphone.

---

## Auteurs

- Aya WIFAK
- Abderraouf Rahmani


Image Docker : [raoufrhm/best-mobile-operator](https://hub.docker.com/r/raoufrhm/best-mobile-operator)
