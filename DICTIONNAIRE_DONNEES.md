# Dictionnaire des données — Best Mobile Operator

> Référentiel des tables, des variables et des codes utilisés dans le projet.
> À garder à jour à chaque changement du pipeline.
> Dernière mise à jour : 12/11/2026 (données ANFR de novembre 2026, mesures Arcep 2025, couverture Arcep T2 2026).

---

## 1. Le vocabulaire

| Mot | Définition | Exemple |
|---|---|---|
| **Support** | La structure physique qui porte les antennes | Un pylône, le toit d'un immeuble, un château d'eau |
| **Site** (= *station* dans l'ANFR) | L'installation **d'un opérateur** sur un support. Plusieurs opérateurs peuvent partager le même support | « L'installation Orange sur le toit du 12 rue X » |
| **Antenne** | L'équipement physique fixé sur le support | Les panneaux blancs sur les toits |
| **Émetteur** | Ce qu'une antenne émet : une technologie et une fréquence | « 5G en 3500 MHz » |
| **Technologie (techno)** | Génération du réseau mobile | 4G, 5G |
| **Fréquence** | Bande utilisée, en MHz. Basse fréquence = **porte loin** ; haute fréquence = **plus de débit** | 700 (portée), 3500 (5G rapide) |
| **Code INSEE** | Code officiel de la commune (5 caractères) | `92050` = Nanterre, `01053` = Bourg-en-Bresse |
| **Lambert-93** | Système de coordonnées officiel de la France métropolitaine, en mètres (code `EPSG:2154`). Le GPS, lui, est en degrés (`EPSG:4326`) | Utilisé par les cartes de couverture Arcep |

---

## 2. Les sources brutes

Toutes sont récupérées par `collect.py` dans `data_raw/`, **seulement si une nouvelle version est publiée**
(les versions déjà traitées sont notées dans `data/derniere_version.json`).
Le brut est supprimé dès qu'il a été nettoyé : `data_raw/` est un dossier temporaire.

### 2.1 ANFR — « Données sur les installations radioélectriques de plus de 5 watts »

- Récupération : API data.gouv.fr → 2 zips (« Tables supports antennes émetteurs bandes » + « Tables de référence ») → `data_raw/anfr/SUP_*.txt`
- Mise à jour : mensuelle
- Format : séparateur `;`, décimale `,`, lire en `dtype=str`
- Couverture : France entière (métropole + outre-mer), tous exploitants (mobile, radio, TV, réseaux privés…)

**Tables utilisées (4)**

| Table | Rôle | Colonnes gardées | Signification |
|---|---|---|---|
| `SUP_STATION` | Le site et son exploitant | `STA_NM_ANFR` | Numéro unique du site (**clé de jointure**) |
| | | `ADM_ID` | Code de l'exploitant → voir `SUP_EXPLOITANT` |
| `SUP_EXPLOITANT` | Dictionnaire des exploitants | `ADM_ID` | Code de l'exploitant |
| | | `ADM_LB_NOM` | Nom de l'exploitant |
| `SUP_EMETTEUR` | Ce que le site émet | `STA_NM_ANFR` | Numéro du site |
| | | `EMR_LB_SYSTEME` | Technologie + fréquence (ex. `LTE 800`, `5G NR 3500`) |
| | | `EMR_DT_SERVICE` | Date de mise en service (format `jj/mm/aaaa`) |
| `SUP_SUPPORT` | Où est le site | `STA_NM_ANFR` | Numéro du site |
| | | `COR_NB_DG_LAT`, `COR_NB_MN_LAT`, `COR_NB_SC_LAT` | Latitude en degrés / minutes / secondes |
| | | `COR_CD_NS_LAT` | `N` (Nord) ou `S` (Sud) |
| | | `COR_NB_DG_LON`, `COR_NB_MN_LON`, `COR_NB_SC_LON` | Longitude en degrés / minutes / secondes |
| | | `COR_CD_EW_LON` | `E` (Est) ou `W` (Ouest) |
| | | `COM_CD_INSEE` | Code INSEE de la commune |

**Tables non utilisées (5)** : `SUP_ANTENNE` (détails physiques des antennes, 30 Mo) et `SUP_BANDE` (fréquences détaillées, 205 Mo) — **supprimées par `collect.py` dès le téléchargement** —, puis `SUP_NATURE` (type de support), `SUP_PROPRIETAIRE` (propriétaire du support), `SUP_TYPE_ANTENNE` (type d'antenne).

**Jointures**
```
SUP_EMETTEUR ──STA_NM_ANFR──▶ SUP_STATION ──ADM_ID──▶ SUP_EXPLOITANT
      └──────────STA_NM_ANFR──▶ SUP_SUPPORT
```

### 2.2 Arcep — « Mon Réseau Mobile », mesures de qualité de service

- Récupération : API data.gouv.fr → dossier `https://data.arcep.fr/mobile/mesures_qualite_arcep/` → un sous-dossier par année. `collect.py` prend **l'année la plus récente qui a la Métropole** (en novembre 2026 : `2025/Metropole/`, car `2026` n'a que l'outre-mer) → `data_raw/arcep/2025_QoS_Metropole_data_habitations.csv` (93 Mo)
- Mise à jour : annuelle (campagne 2025 : 354 282 tests, 1 614 communes)
- Format : séparateur à détecter (`sep=None`), **encodage `latin-1`**, décimale `,`
- Une ligne = **un test réalisé sur le terrain**

| Colonne | Signification | Valeurs / remarques |
|---|---|---|
| `operator` | Opérateur testé | `Orange`, `SFR`, `Bouygues`, `Free` |
| `insee_com` | Code INSEE de la commune | Même code que `COM_CD_INSEE` (ANFR) |
| `latitude_start`, `longitude_start` | Position du test | Degrés décimaux |
| `date_start` | Date du test | `jj/mm/aaaa` |
| `protocole` | Type de test | `WEB` (72 %), `DOWNLOAD`, `UPLOAD`, `STREAM`, `ICMP` (ping), `ULH` |
| `Result` | Résultat du test | `Success`, `Traffic Fail`, `TimeOut`, `Drop`, `Setup Fail` |
| `situation` | Lieu du test | `indoor`, `outdoor`, `incar` (⚠️ majuscules mélangées) |
| `zone` | Type de territoire | `Zones denses`, `Zones intermediaires`, `Zones rurales`, `Zones touristiques` |
| `rsrp`, `rsrq` | Puissance et qualité du signal | Remplis à ~91 % |
| `loaded_in_less_5_secondes` | Page web chargée en moins de 5 s ? | Tests `WEB` |
| `bitrate_dl` | Débit descendant, en **Mb/s** (médiane ~143, max ~994) | Tests `DOWNLOAD` uniquement |
| `techno_start` | Mode du téléphone | Toujours `5G` en 2025 → **ne permet pas de comparer 4G et 5G** |

Colonnes gardées par `clean.py` : `operator`, `latitude_start`, `longitude_start`, `protocole`, `Result`, `bitrate_dl`.

### 2.3 Arcep — cartes de couverture 4G théorique

- Récupération : `https://data.arcep.fr/mobile/couvertures_theoriques/last/Metropole/00_Metropole/` → 4 archives `.7z`, une par opérateur (`<année>_T<trimestre>_couv_Metropole_<CODE>_4G_data.gpkg.7z`), ~1,3 Go compressés, ~3 Go une fois extraits
- Mise à jour : trimestrielle (version utilisée : 2026 T2)
- Format : GeoPackage (`.gpkg`) = des **polygones** (des zones sur la carte), en Lambert-93
- Ce sont des **simulations déclarées par les opérateurs**, pas des mesures

| Code dans le nom du fichier | Opérateur |
|---|---|
| `OF` | Orange |
| `SFR0` | SFR |
| `BOUY` | Bouygues |
| `FREE` | Free |

| Colonne | Valeurs | Signification |
|---|---|---|
| `niveau` | `TBC` | Très bonne couverture |
| | `BC` | Bonne couverture |
| | `CL` | Couverture limitée |
| | (pas de zone) | Pas de couverture |

`collect.py` traite un opérateur à la fois (télécharger → extraire → convertir en grille → supprimer), pour ne jamais avoir plus d'~1 Go sur le disque.

### 2.4 API Adresse (Géoplateforme IGN) — appelée en direct

- URL : `https://data.geopf.fr/geocodage/search?q=<adresse>&limit=<n>` (gratuite, sans clé)
- Utilisée par `adresse.py` : 1 résultat pour la recherche (`geocoder`), 5 pour les suggestions pendant la frappe (`chercher_adresses`)
- Rien n'est stocké

| Champ de la réponse | Devient |
|---|---|
| `geometry.coordinates` | `longitude`, `latitude` |
| `properties.label` | `adresse` (adresse complète, bien écrite) |
| `properties.citycode` | `code_insee` |
| `properties.score` | `confiance` (0 à 1) |

---

## 3. Les fichiers produits par le pipeline (dossier `data/`, dans le dépôt Git)

Les fichiers sont écrits d'abord sous un nom temporaire puis renommés : l'appli ne lit jamais un fichier à moitié écrit.
Juste avant, l'ancienne version est copiée dans `archived/` (ex. `archived/2026-11-12_20-30_sites.csv.gz`).
Les chemins de tous ces fichiers sont définis dans `config.py`.
Les CSV sont compressés en gzip (sans date dans l'en-tête : mêmes données = même fichier, donc pas de faux changement dans Git).

| Fichier | Produit par | Taille |
|---|---|---|
| `sites.csv.gz` | `clean.py` (ANFR) | 4,9 Mo |
| `mesures.csv.gz` | `clean.py` (Arcep mesures) | 1,4 Mo |
| `couverture_4g.npz` | `collect.py` + `couverture.py` (Arcep couverture) | 21 Mo |
| `derniere_version.json` | `collect.py` | < 1 Ko |

### 3.1 `data/sites.csv.gz` — les antennes

1 ligne = 1 site × 1 opérateur × 1 techno × 1 fréquence. France métropolitaine, 4G et 5G uniquement.
Volume (novembre 2026) : 641 292 lignes, 134 435 sites, 21 828 communes.

| Colonne | Type | Exemple | Origine | Description |
|---|---|---|---|---|
| `site_id` | texte | `0920000001` | `STA_NM_ANFR` | Numéro du site (garder en texte : zéros de tête) |
| `operateur` | texte | `Orange` | `ADM_ID` → référentiel §4.1 | `Orange`, `SFR`, `Bouygues`, `Free` |
| `techno` | texte | `5G` | `EMR_LB_SYSTEME` → référentiel §4.2 | `4G` ou `5G` |
| `frequence` | entier (MHz) | `3500` | `EMR_LB_SYSTEME` (nombre final) | 700, 800, 900, 1800, 2100, 2600, 3500 |
| `date_service` | date (`aaaa-mm-jj`) | `2021-06-05` | `EMR_DT_SERVICE` | Mise en service ; si plusieurs émetteurs identiques, la plus ancienne. Vide pour ~10 % des lignes. ⚠️ Quelques dates sont **dans le futur** (mises en service prévues) : l'appli les ignore |
| `latitude` | décimal | `48.8917` | `SUP_SUPPORT` (converti) | Degrés décimaux (WGS84) |
| `longitude` | décimal | `2.2014` | `SUP_SUPPORT` (converti) | Degrés décimaux, négatif à l'ouest de Greenwich |
| `code_insee` | texte (5 car.) | `92050` | `COM_CD_INSEE` | Complété à 5 caractères (`1053` → `01053`) |

Sites par opérateur (novembre 2026) :

| | 4G | 5G |
|---|---|---|
| Bouygues | 34 137 | 22 730 |
| Free | 33 669 | 26 455 |
| Orange | 33 723 | 21 131 |
| SFR | 32 888 | 20 194 |

### 3.2 `data/mesures.csv.gz` — les tests Arcep

1 ligne = 1 test avec une position. Volume : 354 236 lignes.

| Colonne | Type | Origine | Description |
|---|---|---|---|
| `operateur` | texte | `operator` | `Orange`, `SFR`, `Bouygues`, `Free` |
| `latitude` | décimal | `latitude_start` | Position du test |
| `longitude` | décimal | `longitude_start` | Position du test |
| `protocole` | texte | `protocole` | `WEB`, `DOWNLOAD`, `UPLOAD`, `STREAM`, `ICMP`, `ULH` |
| `reussi` | vrai / faux | `Result` | `True` si `Result == "Success"` |
| `debit` | décimal (Mb/s) | `bitrate_dl` | Débit descendant ; rempli seulement pour les tests `DOWNLOAD` (33 384 tests) |

### 3.3 `data/couverture_4g.npz` — la couverture 4G en grille

Les ~3 Go de polygones sont transformés en une **grille de cases de 100 m × 100 m** sur toute la métropole (`couverture.py`).
Chercher le niveau à une adresse revient alors à lire une case du tableau (instantané), au lieu de chercher dans des millions de polygones.

| Élément | Valeur |
|---|---|
| Tableau | `grille`, 10 650 lignes × 11 440 colonnes, 1 octet par case (`uint8`) |
| Emprise (Lambert-93, en mètres) | x de 99 000 à 1 243 000, y de 6 046 000 à 7 111 000 |
| Case d'un point | `ligne = (7 111 000 − y) // 100`, `colonne = (x − 99 000) // 100` |
| Contenu d'une case | Les 4 opérateurs dans un seul octet, **2 bits chacun** (4 niveaux possibles) |

| Opérateur | Bits | Lecture |
|---|---|---|
| Bouygues | 0-1 | `case & 3` |
| Free | 2-3 | `(case >> 2) & 3` |
| Orange | 4-5 | `(case >> 4) & 3` |
| SFR | 6-7 | `(case >> 6) & 3` |

Niveau lu : `0` = Pas de couverture, `1` = Couverture limitée, `2` = Bonne couverture, `3` = Très bonne couverture.
Si une case touche plusieurs zones, on garde le meilleur niveau. Précision vérifiée : 79 points sur 80 identiques aux polygones exacts.

### 3.4 `data/derniere_version.json` — la mémoire de `collect.py`

| Clé | Contenu | Sert à |
|---|---|---|
| `anfr` | Identifiants data.gouv.fr des 2 zips ANFR | Retélécharger seulement si l'ANFR publie un nouveau mois |
| `arcep` | Adresse du fichier `data_habitations.csv` | Comparer le nom du fichier (l'Arcep déplace parfois ses dossiers sans changer les données) |
| `couverture` | Adresses des 4 archives de couverture | Retélécharger seulement si un nouveau trimestre est publié |

### 3.5 Le résultat calculé en direct (pas de fichier)

À chaque recherche, `score.py` construit en mémoire un tableau de 4 lignes (1 par opérateur), renvoyé à la page par `app.py` (`/api/score`).

| Colonne | Calcul | Source |
|---|---|---|
| `nb_sites_4g`, `nb_sites_5g`, `nb_sites_5g_3500` | Sites à moins d'**1 km** (distance de haversine) | `sites.csv.gz` |
| `plus_proche_km` | Distance au site le plus proche de l'opérateur | `sites.csv.gz` |
| `nb_tests`, `taux_reussite`, `nb_debits`, `debit_median` | Tests Arcep à moins de **2 km** | `mesures.csv.gz` |
| `taux_ajuste`, `debit_ajuste` | Lissage : `(n × local + 20 × national) / (n + 20)`. Peu de tests → proche de la moyenne nationale | `mesures.csv.gz` |
| `couverture_4g` | Niveau lu dans la grille à l'adresse exacte | `couverture_4g.npz` |
| `note_couverture` | Très bonne = 1, Bonne = 0,66, Limitée = 0,33, aucune = 0 | |
| `note_reussite` | `taux_ajuste / 100` | |
| `note_debit` | `debit_ajuste / meilleur débit des 4` | |
| `note_5g` | `nb_sites_5g_3500 / meilleur des 4` (0 si aucun) | |
| `note_proximite` | `plus proche des 4 / plus_proche_km` | |
| `score` | `0,3 × couverture + 0,3 × réussite + 0,2 × débit + 0,1 × 5G + 0,1 × proximité` (affiché sur 100) | |

Le verdict est l'opérateur qui a le meilleur `score`. Si c'est Orange, SFR ou Bouygues, l'appli conseille la marque moins chère sur le même réseau (Sosh, RED by SFR, B&You).

---

## 4. Les référentiels (codes → valeurs)

### 4.1 Opérateurs (`ADM_ID` → `operateur`)

| `ADM_ID` | `ADM_LB_NOM` (ANFR) | `operateur` (projet) | Gardé ? |
|---|---|---|---|
| 6 | BOUYGUES TELECOM | Bouygues | ✅ |
| 23 | ORANGE | Orange | ✅ |
| 137 | SFR | SFR | ✅ |
| 240 | FREE MOBILE | Free | ✅ |
| 21 | ORANGE service fixe | — | ❌ réseau fixe |
| 307 | FREE CARAIBES | — | ❌ outre-mer |

Les marques Sosh (réseau Orange), RED by SFR (SFR) et B&You (Bouygues) n'ont pas d'antennes propres.

### 4.2 Technologies (`EMR_LB_SYSTEME` → `techno`)

| Libellés ANFR | `techno` | Gardé ? |
|---|---|---|
| `LTE 700`, `LTE 800`, `LTE 900`, `LTE 1800`, `LTE 2100`, `LTE 2600` | 4G | ✅ |
| `5G NR 700`, `5G NR 2100`, `5G NR 3500` | 5G | ✅ |
| `5G NR … Expe` | 5G expérimentale | ❌ |
| `GSM 900`, `GSM 1800` | 2G | ❌ |
| `UMTS 900`, `UMTS 2100` | 3G | ❌ |
| `FH`, `FH ABI` | Faisceaux hertziens (liaisons entre antennes) | ❌ |
| `BLR LTE 3500`, `SAT GEO`, `SAT NGEO` | Internet fixe radio, satellite | ❌ |

Règle dans le code : 4G = `^LTE \d+$` ; 5G = `^5G NR \d+$`.

### 4.3 Périmètre géographique

France **métropolitaine** uniquement : on exclut les codes INSEE commençant par `97` ou `98` (outre-mer).
Les mesures et la couverture Arcep utilisées sont, elles aussi, celles de la Métropole.

---

## 5. Conventions du projet

- **Noms de colonnes** des fichiers produits : en français, minuscules, avec `_` (ex. `code_insee`, `nb_sites_5g`).
- **Identifiants** (`site_id`, `code_insee`) : toujours en **texte**, jamais en nombre (pour garder les zéros de tête).
- **Dates** : format ISO `aaaa-mm-jj`.
- **Coordonnées** : degrés décimaux (WGS84) ; Lambert-93 seulement à l'intérieur de `couverture.py`.
- **Fréquences** : en MHz, entier.
- **Dossiers** :
  - `data_raw/` = brut téléchargé, **temporaire** (supprimé après nettoyage, jamais sur GitHub) ;
  - `data/` = fichiers produits par le pipeline, **envoyés sur GitHub** (~27 Mo) pour qu'un clone démarre sans rien télécharger ;
  - `archived/` = les anciennes versions des fichiers de `data/`, datées, jamais sur GitHub ;
  - `log/` = un journal par passage du pipeline + `webapp.log` pour l'appli (`run.sh`), jamais sur GitHub.
