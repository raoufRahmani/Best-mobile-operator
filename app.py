import pandas as pd
import streamlit as st
from score import score_adresse
from antennes_proches import distance_km
from adresse import chercher_adresses
from streamlit_searchbox import st_searchbox

COULEURS = {"Orange": "#FF7900", "SFR": "#E2001A", "Bouygues": "#009FE3", "Free": "#7A7A7A"}
COURT = {"Très bonne couverture": "Très bonne", "Bonne couverture": "Bonne",
         "Couverture limitée": "Limitée", "Pas de couverture": "Aucune"}

st.set_page_config(page_title="Quel opérateur chez moi ?", page_icon="📶", layout="wide")

# ---------- Style (CSS) ----------
st.markdown("""
<style>
.verdict {border-radius:20px; padding:26px 32px; margin:8px 0 28px; background:var(--c); color:white;}
.verdict .petit {opacity:.9; font-size:1rem;}
.verdict .grand {font-size:3rem; font-weight:800; line-height:1.1; margin:6px 0;}
.carte {border-radius:16px; padding:18px 20px; background:rgba(127,127,127,.08); border-top:6px solid var(--c);}
.carte .rang {font-size:.8rem; opacity:.6; letter-spacing:.08em;}
.carte .nom {font-size:1.4rem; font-weight:700; margin-bottom:6px;}
.carte .score {font-size:2.4rem; font-weight:800; color:var(--c); line-height:1;}
.carte .barre {height:8px; border-radius:4px; background:rgba(127,127,127,.2); margin:12px 0 14px;}
.carte .barre div {height:100%; border-radius:4px; background:var(--c);}
.carte .ligne {display:flex; justify-content:space-between; font-size:.92rem; padding:3px 0;}
.carte .ligne span:first-child {opacity:.65;}
</style>
""", unsafe_allow_html=True)


@st.cache_data
def charger():
    """Lit les données une seule fois (pas à chaque recherche)."""
    sites = pd.read_csv("data/sites.csv", dtype={"site_id": str, "code_insee": str},
                        parse_dates=["date_service"])
    mesures = pd.read_csv("data/mesures.csv")
    return sites, mesures


def carte_html(rang, operateur, l):
    """Le bloc HTML d'un opérateur (rang, score, barre, chiffres clés)."""
    return f"""
<div class="carte" style="--c:{COULEURS[operateur]}">
<div class="rang">#{rang}</div>
<div class="nom">{operateur}</div>
<div class="score">{l['score']:.2f}</div>
<div class="barre"><div style="width:{l['score'] * 100:.0f}%"></div></div>
<div class="ligne"><span>Couverture 4G</span><span>{COURT.get(l['couverture_4g'], l['couverture_4g'])}</span></div>
<div class="ligne"><span>Tests réussis</span><span>{l['taux_ajuste']:.0f} %</span></div>
<div class="ligne"><span>Débit</span><span>{l['debit_ajuste']:.0f} Mb/s</span></div>
<div class="ligne"><span>Antenne la + proche</span><span>{l['plus_proche_km'] * 1000:.0f} m</span></div>
</div>"""


sites, mesures = charger()

# ---------- 1) En-tête + recherche ----------
st.title("📶 Quel opérateur chez moi ?")
st.write("Orange, SFR, Bouygues ou Free ? On compare **les antennes, les mesures réelles et la couverture** "
         "autour de ton adresse, à partir des données ouvertes de l'ANFR et de l'Arcep.")
def suggestions(texte):
    """Appelée à chaque lettre tapée : renvoie les adresses à proposer."""
    return chercher_adresses(texte) if texte and len(texte) >= 3 else []


adresse = st_searchbox(suggestions, placeholder="Tape ton adresse... ex. : 11 rue Jean Jaurès", key="adresse")

if adresse:
    with st.spinner("Analyse en cours..."):
        lieu, tableau = score_adresse(adresse, sites, mesures)
    if lieu is None:
        st.error("Adresse introuvable, vérifie l'orthographe.")
        st.stop()

    # ---------- 2) Le verdict ----------
    gagnant = tableau.index[0]
    st.markdown(f"""
<div class="verdict" style="--c:{COULEURS[gagnant]}">
<div class="petit">🏆 Meilleur opérateur au {lieu['adresse']}</div>
<div class="grand">{gagnant}</div>
<div class="petit">Score {tableau['score'].iloc[0]:.2f} / 1</div>
</div>""", unsafe_allow_html=True)

    # ---------- 3) Les 4 cartes opérateurs ----------
    colonnes = st.columns(4)
    for rang, (operateur, ligne) in enumerate(tableau.iterrows(), start=1):
        colonnes[rang - 1].markdown(carte_html(rang, operateur, ligne), unsafe_allow_html=True)

    st.write("")

    # ---------- 4) Carte + explication ----------
    gauche, droite = st.columns([2, 1])
    with gauche:
        st.subheader("Antennes à moins d'1 km")
        st.caption("🟠 Orange · 🔴 SFR · 🔵 Bouygues · ⚫ Free · ⬛ ton adresse")
        distance = distance_km(lieu["latitude"], lieu["longitude"], sites["latitude"], sites["longitude"])
        carte = sites[distance <= 1].drop_duplicates("site_id")[["latitude", "longitude", "operateur"]]
        carte["couleur"] = carte["operateur"].map(COULEURS)
        moi = pd.DataFrame([{"latitude": lieu["latitude"], "longitude": lieu["longitude"], "couleur": "#000000"}])
        st.map(pd.concat([carte, moi]), latitude="latitude", longitude="longitude", color="couleur", size=25)

    with droite:
        st.subheader("Comment on calcule ?")
        st.markdown("""
- **30 %** Couverture 4G officielle (Arcep)
- **30 %** Tests réussis autour de chez toi (Arcep)
- **20 %** Débit mesuré (Arcep)
- **10 %** Antennes 5G rapide à moins d'1 km (ANFR)
- **10 %** Distance à l'antenne la plus proche (ANFR)

Quand il y a **peu de tests** près de chez toi, on complète avec la **moyenne nationale** de l'opérateur.
""")

    # ---------- 5) Le détail, caché par défaut ----------
    with st.expander("Voir le tableau détaillé"):
        st.dataframe(tableau, use_container_width=True)