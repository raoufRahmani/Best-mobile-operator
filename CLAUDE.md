# CONTEXTE DU PROJET — « Quel opérateur chez moi ? »

> Ce fichier résume tout le travail de préparation fait jusqu'ici (17/10/2026).
> **À donner à Claude au début d'une conversation** (claude.ai : joindre le fichier ;
> Claude Code : le renommer `CLAUDE.md` à la racine du projet).
> Consigne pour Claude : lis tout ce fichier avant de répondre, et repars de la section « Où on en est ».

---

## 1. Le cours et la consigne

- Cours : **« Initiation au DevOps pour un Data Scientist »**, M2 MoSEF, Université Paris 1 Panthéon-Sorbonne.
- Projet noté **en binôme** : créer une **application qui manipule des données open data**, puis la **pitcher** devant un board technique en montrant la maîtrise de **la conception, du développement et du déploiement**.
- Plan du cours : **Enjeux du DevOps → Linux → Git → Docker**. Le projet suit le même chemin.
- Idées clés du chapitre 1 : 85 % des projets data échouent (souvent faute de mise en production) ; DevOps = Dev + Ops (culture + pratiques + outils) ; 3 modes de déploiement : **local** (problème de portabilité), **on-premise** (ne tient pas la charge), **cloud** (la cible).
- Le chapitre 1 ne nomme **aucun fournisseur cloud** : le serveur de déploiement est **à confirmer avec le prof**.

### L'appli exemple du prof
- Repo : https://github.com/eliamosef/mosef_app — « Student Profiler ».
- Fonctionnement : Google Form des étudiants → téléchargement du Google Sheet (`curl`) → renommage des colonnes (pandas) → NLP spaCy (lemmatisation, comptage) → page Flask (nuage de mots + graphique à bulles).
- Structure : `data_collector/` → `data_integrator/` → `data_processor/` → `webapp/`, orchestrés par des scripts bash dans `bin/` (pipeline **en boucle**, logs dans `log/`, archivage du brut dans `archived/`), + un `Dockerfile` (Ubuntu 20.04).
- **On ne copie pas son code, on garde sa démarche** : étapes séparées, script bash, boucle, logs, archivage, Docker, déploiement.
- Bugs constatés dans son repo : `.venv/Scripts/activate` ne marche que sous Windows (`.venv/bin/activate` sur Mac/Linux) ; dans le conteneur Ubuntu, `python` n'existe pas (seulement `python3`).

---

## 2. Le sujet choisi

**« Quel opérateur chez moi ? »**
L'utilisateur tape **son adresse complète ou sa commune** → l'appli compare **Orange, SFR, Bouygues Telecom et Free** (antennes 4G/5G autour de lui, débits mesurés) → elle donne un **verdict** : « chez toi, prends X ».

Cadrage :
| | |
|---|---|
| **Persona** | Quelqu'un qui déménage ou veut changer de forfait et se demande quel opérateur capte le mieux chez lui |
| **Problème** | Les opérateurs disent tous « meilleur réseau » ; les vraies données existent mais sont éparpillées et illisibles |
| **Fonctionnalités** | Recherche adresse/commune → classement des 4 opérateurs + carte des antennes + verdict |
| **Risques** | Fichiers lourds ; mesures de débit pas disponibles partout ; antenne proche ≠ bonne réception garantie |

---

## 3. Les données (2 sources officielles, open data)

| | **ANFR** | **Arcep** |
|---|---|---|
| Question | **Où sont les antennes ?** | **Est-ce que ça marche bien en vrai ?** |
| Contenu | Toutes les installations radio > 5 W en France : exploitant, technologie, position, commune | Mesures de terrain (débit, appels) par opérateur |
| Image | L'annuaire des antennes | Le bulletin de notes |
| Mise à jour | Chaque mois | Chaque année |
| Version de l'appli | **V1** | **V2** |
| Page | https://www.data.gouv.fr/datasets/donnees-sur-les-installations-radioelectriques-de-plus-de-5-watts-1 | https://www.data.gouv.fr/datasets/mon-reseau-mobile |

### 3.1 ANFR — les tables
Publiées chaque mois en 2 zips : « Tables supports antennes émetteurs bandes <mois> » (~63 Mo) et « Tables de référence <mois> » (~5 Ko).
Fichiers `SUP_*.txt` : **séparateur `;`**, **décimale `,`**, lire avec **`dtype=str`** (pour garder les zéros de tête de `STA_NM_ANFR`).

Hiérarchie : **STATION** (site d'un exploitant) → **SUPPORT** (pylône/toit, position) → **ANTENNE** → **ÉMETTEUR** (technologie) → **BANDE** (fréquences). Clé commune : **`STA_NM_ANFR`**.

| Table | Colonnes | Utile V1 ? |
|---|---|---|
| **SUP_STATION** | STA_NM_ANFR, ADM_ID (exploitant), DEM_NM_COMSIS, DTE_IMPLANTATION, DTE_MODIF, DTE_EN_SERVICE, STA_NM_USER | ✅ |
| **SUP_EXPLOITANT** | ADM_ID, ADM_LB_NOM (nom de l'exploitant) | ✅ |
| **SUP_EMETTEUR** | EMR_ID, EMR_LB_SYSTEME (techno : FM, GSM, LTE…, 5G…), STA_NM_ANFR, AER_ID, EMR_DT_SERVICE | ✅ |
| **SUP_SUPPORT** | SUP_ID, STA_NM_ANFR, NAT_ID, COR_NB_DG/MN/SC_LAT + COR_CD_NS_LAT, COR_NB_DG/MN/SC_LON + COR_CD_EW_LON (coordonnées en degrés/minutes/secondes), SUP_NM_HAUT, TPO_ID, ADR_LB_LIEU, ADR_LB_ADD1/2/3, ADR_NM_CP, COM_CD_INSEE | ✅ |
| SUP_ANTENNE | STA_NM_ANFR, AER_ID, TAE_ID, AER_NB_DIMENSION, AER_FG_RAYON, AER_NB_AZIMUT, AER_NB_ALT_BAS, SUP_ID | ❌ |
| SUP_BANDE | STA_NM_ANFR, BAN_ID, EMR_ID, BAN_NB_F_DEB, BAN_NB_F_FIN, BAN_FG_UNITE | ❌ |
| SUP_NATURE / SUP_PROPRIETAIRE / SUP_TYPE_ANTENNE | dictionnaires (type de support, propriétaire, type d'antenne) | ❌ |

⚠️ La base contient **tout** (radios FM, réseaux privés, etc.) → il faut **filtrer** : les 4 opérateurs (via SUP_EXPLOITANT) et la 4G/5G (via EMR_LB_SYSTEME).
⚠️ `COM_CD_INSEE` = code de commune, pas le nom → ajouter le référentiel des communes INSEE (ou l'API Géo).
⚠️ Conversion des coordonnées : `degrés + minutes/60 + secondes/3600`, négatif si `S` ou `W`.

### 3.2 Arcep — les mesures
Les « fichiers » de la page data.gouv.fr sont en fait des **liens vers des dossiers** sur `data.arcep.fr` :
```
https://data.arcep.fr/mobile/mesures_qualite_arcep/
   ├── 2016/ … 2025/   (un dossier par année)
   └── last/Metropole/
         ├── 2025_QoS_Metropole_data_habitations.csv   (89 Mo)  ← celui qu'on utilise (débits en zone d'habitation)
         ├── 2025_QoS_Metropole_data_transports.csv    (234 Mo)
         ├── 2025_QoS_Metropole_voix_habitations.csv   (65 Mo)
         ├── 2025_QoS_Metropole_voix_transports.csv    (81 Mo)
         └── 2025_QoS_indicateurs_globaux.xlsx
```
Les autres ressources du jeu Arcep : sites, couverture ciblée, cartes de couverture théorique (GPKG, pour une V3), extension 4G fixe, crowdsourcing.
Colonnes de `data_habitations` : **pas encore regardées**.

### 3.3 Géocodage d'adresse
API Adresse de l'État (gratuite, sans clé). L'URL a migré vers la Géoplateforme IGN : `https://data.geopf.fr/geocodage/search?q=<adresse>&limit=1` → coordonnées + `citycode` (code INSEE). **À vérifier qu'elle répond.**

---

## 4. Le chemin des données (architecture)

```
1. SOURCES (internet) : ANFR (mensuel) + Arcep (annuel)
        │  via l'API data.gouv.fr — automatique, personne ne télécharge à la main
        ▼
2. SERVEUR (dans le conteneur Docker)
   collect.py  → télécharge les fichiers bruts (~150 Mo), seulement s'il y a une nouvelle version
   clean.py    → relie les tables, garde 4 opérateurs + 4G/5G, convertit les positions
                 → 1 ligne par site (puis supprime les fichiers bruts)
   process.py  → agrège par commune × opérateur → petite table de résultats
   run.sh      → relance le pipeline en boucle + logs
   app.py      → page web (Streamlit) ; adresse → API Adresse → sites autour → score → verdict
        ▼
3. NAVIGATEUR DE L'UTILISATEUR : classement + carte + verdict. Aucun fichier sur sa machine.
```

Point important : **l'utilisateur ne télécharge rien**. Les fichiers sont téléchargés sur le serveur, dans le conteneur. Le téléchargement manuel fait jusqu'ici ne servait qu'à l'**exploration**.

### Structure cible du projet
```
mon_app/
├── collect.py
├── clean.py
├── process.py
├── app.py              # Streamlit, port 8501
├── run.sh              # 1er passage, puis boucle (sleep) + logs dans log/, puis lance l'appli
├── requirements.txt
├── Dockerfile          # FROM python:3.11-slim, EXPOSE 8501, CMD ["bash", "run.sh"]
├── .dockerignore       # .venv .git data data_raw log archived
├── .gitignore          # .venv/ data/ data_raw/ log/ archived/ __pycache__/
└── .gitattributes      # *.sh text eol=lf   (évite le bug des fins de ligne Windows)
```

---

## 5. Les variables et le « modèle »

**Table nettoyée (clean.py) — 1 ligne par site × opérateur × techno :**
`site_id` (STA_NM_ANFR), `operateur` (ADM_LB_NOM), `techno` (4G/5G), `frequence` (700, 800, 3500…), `date_service`, `latitude`, `longitude`, `code_insee`, `commune`.

**Table de résultats (process.py) — 1 ligne par commune × opérateur :**
`nb_sites_4g`, `nb_sites_5g`, `nb_sites_5g_3500` (la 5G rapide), `part_5g`, `nouveaux_sites_12m`, `debit_moyen` (V2, Arcep).

**Score (V1, pas de ML) :** indicateurs ramenés entre 0 et 1 (divisés par le meilleur opérateur de la zone), puis moyenne pondérée, par exemple :
`score = 0.35 × sites 4G + 0.35 × sites 5G (bonus 3500) + 0.30 × débit mesuré (V2)`. Verdict = meilleur score. Idée : curseurs dans l'appli pour que l'utilisateur choisisse les poids.

**Recherche par adresse :** géocodage → distance de Haversine à chaque site → sites dans un rayon (1 km en ville, 3-5 km à la campagne) → score. Calcul en direct dans `app.py` (≈100 000 sites, instantané).

**Bonus ML possible (après la V1) :** prédire où la 5G va arriver (historique mensuel ANFR ; régression logistique ou gradient boosting).

**Limite à dire au pitch :** une antenne proche ≠ bonne réception (bâtiments, relief, intérieur) → d'où la V2 (débits mesurés) et la V3 (cartes de couverture).

---

## 6. Récupération des données via l'API data.gouv.fr (proposition, PAS encore testée)

Aucun code du projet n'est encore écrit. Seule cette proposition de récupération automatique existe :
```python
import io, json, re, zipfile
from pathlib import Path
from urllib.parse import urljoin
import requests

API = "https://www.data.gouv.fr/api/1/datasets/"
MEMO = Path("data_raw/derniere_version.json")   # ce qu'on a déjà téléchargé


def lire_memo():
    return json.loads(MEMO.read_text()) if MEMO.exists() else {}

def ecrire_memo(cle, valeur):
    memo = lire_memo()
    memo[cle] = valeur
    MEMO.parent.mkdir(parents=True, exist_ok=True)
    MEMO.write_text(json.dumps(memo, indent=2))

def plus_recent(ressources, debut_titre):
    candidats = [r for r in ressources if r["title"].startswith(debut_titre)]
    return max(candidats, key=lambda r: r["last_modified"])


# ---------- Source 1 : ANFR (où sont les antennes)
def collect_anfr():
    ressources = requests.get(API + "donnees-sur-les-installations-radioelectriques-de-plus-de-5-watts-1/",
                              timeout=30).json()["resources"]
    titres = ["Tables supports antennes émetteurs bandes", "Tables de référence"]
    a_jour = {t: plus_recent(ressources, t)["id"] for t in titres}

    if lire_memo().get("anfr") == a_jour:
        print("ANFR : pas de nouvelle version")
        return

    dossier = Path("data_raw/anfr")
    dossier.mkdir(parents=True, exist_ok=True)
    for t in titres:
        r = plus_recent(ressources, t)
        print("ANFR : téléchargement de", r["title"])
        contenu = requests.get(r["url"], timeout=600).content
        zipfile.ZipFile(io.BytesIO(contenu)).extractall(dossier)
    ecrire_memo("anfr", a_jour)
    print("ANFR OK")


# ---------- Source 2 : Arcep (qualité mesurée)
def collect_arcep():
    ressources = requests.get(API + "mon-reseau-mobile/", timeout=30).json()["resources"]
    dossier_url = plus_recent(ressources, "Mesures de qualité de service")["url"]

    page_url = urljoin(dossier_url, "last/Metropole/")
    page = requests.get(page_url, timeout=30).text

    liens = re.findall(r'href="([^"]*data_habitations\.csv)"', page)
    if not liens:
        print("ARCEP : fichier data_habitations introuvable sur", page_url)
        return
    fichier_url = urljoin(page_url, liens[0])

    if lire_memo().get("arcep") == fichier_url:
        print("ARCEP : pas de nouvelle version")
        return

    dossier = Path("data_raw/arcep")
    dossier.mkdir(parents=True, exist_ok=True)
    nom = fichier_url.split("/")[-1]
    print("ARCEP : téléchargement de", nom)
    with requests.get(fichier_url, stream=True, timeout=600) as r:
        with open(dossier / nom, "wb") as f:
            for morceau in r.iter_content(chunk_size=1 << 20):
                f.write(morceau)
    ecrire_memo("arcep", fichier_url)
    print("ARCEP OK")


if __name__ == "__main__":
    collect_anfr()
    collect_arcep()
```
Test attendu : 1er lancement → télécharge les 2 sources ; 2e lancement → « pas de nouvelle version » ×2.
Incertitude : le format HTML exact de la page dossier Arcep n'a pas été vu → si « introuvable », ajuster la regex.

---

## 7. Bonus mis de côté : proposer des offres du meilleur opérateur

- **Les offres ne sont pas en open data** → soit scraping, soit fichier `offres.csv` rempli à la main (avec la date de relevé).
- Marques moins chères sur le même réseau : **Sosh (réseau Orange), RED by SFR (SFR), B&You (Bouygues)** ; Free est déjà « low cost ». Idée de conseil : « le meilleur réseau chez toi est Orange → Sosh utilise le même réseau, moins cher ».
- `robots.txt` des 4 sites vérifiés : pages forfaits non interdites (Sosh demande 10 s entre deux requêtes).
- Ce qu'on a observé en explorant les sites (aucun code conservé) :
  - **Free** : les offres sont rangées proprement dans un bloc JSON de la page (`__NEXT_DATA__` → `props.pageProps.plans` ; `price` en centimes ; `nationalData.fairuse` en Mo, -1 = illimité) → facile à automatiser avec un simple `requests`.
  - **B&You** : le prix n'est affiché que pour le forfait sélectionné → il faudrait simuler des clics (Playwright).
  - **RED** : offres dans le HTML (pas de JSON utile), plus fragile.
  - **Sosh** : URL à retrouver.
- Règle : ce qui marche proprement → automatique ; le reste → `offres.csv` à la main.

---

## 8. Docker et serveur

- Docker Desktop installé et fonctionnel sur le PC Windows (il a fallu activer **WSL 2** : `wsl --install` en administrateur + redémarrage ; la virtualisation était déjà activée). `docker run hello-world` OK.
- Commandes : `docker build -t mon_app .` puis `docker run -p 8501:8501 mon_app` → http://localhost:8501.
- Publication : `docker push PSEUDO/mon_app` (Docker Hub), puis sur le serveur `docker pull` + `docker run -d -p 8501:8501 …` + **ouvrir le port 8501** dans le pare-feu.
- **Serveur (vérifié en octobre 2026)** :
  - **Azure for Students** : 100 $ de crédits, **sans carte bancaire**, mail étudiant ; quand les crédits sont épuisés, l'abonnement est désactivé (pas de facture). ⭐ Choix conseillé.
  - Oracle Always Free : 2 cœurs / 12 Go RAM (réduit en juin 2026), carte demandée.
  - Google Cloud e2-micro : 1 Go RAM seulement, régions US, carte demandée → trop petit.
  - AWS : jusqu'à 200 $ de crédits pendant 6 mois, carte demandée.
  - ⚠️ Prévoir **≥ 2 Go de RAM** (tables ANFR lourdes) et/ou `usecols` dans `clean.py`. Éteindre la VM quand on ne s'en sert pas.
  - **D'abord demander au prof** s'il fournit un serveur.

### Pièges déjà rencontrés
| Erreur | Solution |
|---|---|
| `$'\r': command not found` dans le conteneur | `.gitattributes` avec `*.sh text eol=lf` (ou `git clone --config core.autocrlf=false`) |
| `python: command not found` dans Ubuntu | Image `python:3.11-slim` |
| Docker Desktop « Virtualization support not detected » | `wsl --install` en admin, redémarrer |
| L'appli tourne mais la page ne s'ouvre pas | Oubli du `-p 8501:8501` ou port fermé sur le serveur |
| Taper `code fichier.py` n'exécute rien | `code` ouvre VS Code ; pour exécuter : `python fichier.py` |

---

## 9. Où on en est (17/10/2026)

**Aucun code du projet n'est écrit.** Tout ce qui précède = exploration et réflexion.

Confirmé ✅ : sujet ; les 2 sources et leur contenu ; les tables ANFR utiles ; le chemin vers les fichiers Arcep ; Docker Desktop fonctionne.

À confirmer avant de démarrer ⏳ :
1. Libellés exacts des technologies 4G/5G (`value_counts` sur EMR_LB_SYSTEME).
2. Noms exacts des 4 opérateurs dans SUP_EXPLOITANT.
3. `collect.py` fonctionne (2 sources + mémoire).
4. (V2) Colonnes du fichier Arcep `data_habitations`.
5. Serveur de déploiement (demander au prof).

### Plan une fois tout confirmé
| Étape | Contenu |
|---|---|
| **V1** | collect → clean → process → app (ANFR seule, recherche commune ou adresse, carte + classement + verdict) |
| Mise en prod | run.sh (boucle + logs) → GitHub → Docker → Docker Hub → serveur |
| **V2** | + mesures Arcep (débits réels) + score complet |
| Bonus | offres opérateurs, modèle ML de prévision 5G, API FastAPI entre pipeline et appli (2 conteneurs) |
| Fin | Pitch : problème → démo live → schéma d'architecture → difficultés → limites |

---

## 10. Conventions de travail pour Claude
- Répondre en **français**, de façon **concise et simple**.
- Code **simple et lisible**, pas de sur-ingénierie.
- Modifications **minimales et ciblées** du code existant, pas de réécriture complète.
- Environnement : Windows, VS Code, Git Bash / cmd, Python 3.13, Docker Desktop (WSL 2), PC ~8 Go de RAM.
