# Dictionnaire des données — Best Mobile Operator

> Référentiel des tables, des variables et des codes utilisés dans le projet.
> À garder à jour à chaque nouvelle étape du pipeline.
> Dernière mise à jour : 17/10/2026 (après `clean.py`).

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

---

## 2. Les sources brutes

### 2.1 ANFR — « Données sur les installations radioélectriques de plus de 5 watts »

- Récupération : `collect.py` via l'API data.gouv.fr → `data_raw/anfr/SUP_*.txt`
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

**Tables non utilisées (6)** : `SUP_ANTENNE` (détails physiques des antennes), `SUP_BANDE` (fréquences détaillées, 205 Mo), `SUP_NATURE` (type de support), `SUP_PROPRIETAIRE` (propriétaire du support), `SUP_TYPE_ANTENNE` (type d'antenne).

**Jointures**
```
SUP_EMETTEUR ──STA_NM_ANFR──▶ SUP_STATION ──ADM_ID──▶ SUP_EXPLOITANT
      └──────────STA_NM_ANFR──▶ SUP_SUPPORT
```

### 2.2 Arcep — « Mon Réseau Mobile », mesures de qualité de service *(utilisé en V2)*

- Récupération : `collect.py` via l'API data.gouv.fr → `data_raw/arcep/<année>_QoS_Metropole_data_habitations.csv`
- Mise à jour : annuelle (campagne 2025 : 354 282 tests, 1 614 communes)
- Format : séparateur à détecter (`sep=None`), **encodage `latin-1`**, décimale `,`
- Une ligne = **un test réalisé sur le terrain**

| Colonne | Signification | Valeurs / remarques |
|---|---|---|
| `operator` | Opérateur testé | `Orange`, `SFR`, `Bouygues`, `Free` |
| `insee_com` | Code INSEE de la commune | Même code que `COM_CD_INSEE` (ANFR) → **permet de relier les 2 sources** |
| `latitude_start`, `longitude_start` | Position du test | Degrés décimaux |
| `date_start` | Date du test | `jj/mm/aaaa` → convertir avec `dayfirst=True` |
| `protocole` | Type de test | `WEB` (72 %), `DOWNLOAD`, `UPLOAD`, `STREAM`, `ICMP` (ping), `ULH` |
| `Result` | Résultat du test | `Success`, `Traffic Fail`, `TimeOut`, `Drop`, `Setup Fail` |
| `situation` | Lieu du test | `indoor`, `outdoor`, `incar` (⚠️ majuscules mélangées → mettre en minuscules) |
| `zone` | Type de territoire | `Zones denses`, `Zones intermediaires`, `Zones rurales`, `Zones touristiques` |
| `rsrp`, `rsrq` | Puissance et qualité du signal | Remplis à ~91 % |
| `loaded_in_less_5_secondes` | Page web chargée en moins de 5 s ? | Tests `WEB` |
| `bitrate_dl` | Débit descendant (probablement en Mb/s, à confirmer dans la doc Arcep) | Tests `DOWNLOAD` uniquement, décimale `,` |
| `techno_start` | Mode du téléphone | Toujours `5G` en 2025 → **ne permet pas de comparer 4G et 5G** |

---

## 3. Les fichiers produits par le pipeline

### 3.1 `data/sites.csv` — produit par `clean.py` ✅

1 ligne = 1 site × 1 opérateur × 1 techno × 1 fréquence. France métropolitaine, 4G et 5G uniquement.
Volume (octobre 2026) : 644 607 lignes, 21 781 communes.

| Colonne | Type | Exemple | Origine | Description |
|---|---|---|---|---|
| `site_id` | texte | `0920000001` | `STA_NM_ANFR` | Numéro du site (garder en texte : zéros de tête) |
| `operateur` | texte | `Orange` | `ADM_ID` → référentiel §4.1 | `Orange`, `SFR`, `Bouygues`, `Free` |
| `techno` | texte | `5G` | `EMR_LB_SYSTEME` → référentiel §4.2 | `4G` ou `5G` |
| `frequence` | entier (MHz) | `3500` | `EMR_LB_SYSTEME` (nombre final) | 700, 800, 900, 1800, 2100, 2600, 3500 |
| `date_service` | date (`aaaa-mm-jj`) | `2021-06-05` | `EMR_DT_SERVICE` | Mise en service ; si plusieurs émetteurs identiques, la plus ancienne. Peut être vide (~9 %) |
| `latitude` | décimal | `48.8917` | `SUP_SUPPORT` (converti) | Degrés décimaux (WGS84) |
| `longitude` | décimal | `2.2014` | `SUP_SUPPORT` (converti) | Degrés décimaux, négatif à l'ouest de Greenwich |
| `code_insee` | texte (5 car.) | `92050` | `COM_CD_INSEE` | Complété à 5 caractères (`1053` → `01053`) |

### 3.2 `data/communes_operateurs.csv` — produit par `process.py` ⏳ *(à venir)*

1 ligne = 1 commune × 1 opérateur. Colonnes prévues :

| Colonne | Description |
|---|---|
| `code_insee` | Code de la commune |
| `operateur` | Orange, SFR, Bouygues, Free |
| `nb_sites_4g` | Nombre de sites émettant en 4G |
| `nb_sites_5g` | Nombre de sites émettant en 5G |
| `nb_sites_5g_3500` | Nombre de sites 5G en 3500 MHz (5G rapide) |
| `nouveaux_sites_12m` | Sites mis en service dans les 12 derniers mois |
| `score` | Score de l'opérateur dans la commune (0 à 1) |

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

---

## 5. Conventions du projet

- **Noms de colonnes** des fichiers produits : en français, minuscules, avec `_` (ex. `code_insee`, `nb_sites_5g`).
- **Identifiants** (`site_id`, `code_insee`) : toujours en **texte**, jamais en nombre (pour garder les zéros de tête).
- **Dates** : format ISO `aaaa-mm-jj`.
- **Coordonnées** : degrés décimaux (WGS84).
- **Fréquences** : en MHz, entier.
- **Dossiers** : `data_raw/` = brut téléchargé (jamais modifié à la main) ; `data/` = fichiers produits par le pipeline. Aucun des deux n'est envoyé sur GitHub.
