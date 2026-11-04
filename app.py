import math
import pandas as pd
from flask import Flask, jsonify, render_template, request
from score import score_adresse
from antennes_proches import distance_km
from adresse import chercher_adresses

app = Flask(__name__)

# Marque moins chère qui utilise le même réseau
MOINS_CHER = {"Orange": "Sosh", "SFR": "RED by SFR", "Bouygues": "B&You"}

# Les données sont lues une seule fois, au démarrage (pas à chaque recherche)
sites = pd.read_csv("data/sites.csv", dtype={"site_id": str, "code_insee": str},
                    parse_dates=["date_service"])
mesures = pd.read_csv("data/mesures.csv")


def propre(valeur):
    """NaN -> None, pour que le JSON reste valide."""
    return None if isinstance(valeur, float) and math.isnan(valeur) else valeur


@app.route("/")
def accueil():
    return render_template("index.html")


@app.route("/api/adresses")
def adresses():
    """Suggestions d'adresses pendant la frappe."""
    texte = request.args.get("q", "")
    return jsonify(chercher_adresses(texte) if len(texte) >= 3 else [])


@app.route("/api/score")
def score():
    """Adresse -> verdict, classement des 4 opérateurs et antennes à moins d'1 km."""
    lieu, tableau = score_adresse(request.args.get("adresse", ""), sites, mesures)
    if lieu is None:
        return jsonify({"erreur": "Adresse introuvable"}), 404

    operateurs = [{
        "nom": nom,
        "score": round(ligne["score"] * 100),
        "couverture_4g": ligne["couverture_4g"],
        "taux": propre(ligne["taux_ajuste"]),
        "debit": propre(ligne["debit_ajuste"]),
        "plus_proche_m": propre(ligne["plus_proche_km"] * 1000),
        "nb_sites_4g": int(ligne["nb_sites_4g"]),
        "nb_sites_5g": int(ligne["nb_sites_5g"]),
        "nb_sites_5g_3500": int(ligne["nb_sites_5g_3500"]),
    } for nom, ligne in tableau.iterrows()]

    # Les antennes autour, 1 point par site (5G si le site a au moins un émetteur 5G)
    distance = distance_km(lieu["latitude"], lieu["longitude"], sites["latitude"], sites["longitude"])
    proches = sites[distance <= 1]
    antennes = (proches.groupby(["site_id", "operateur"])
                       .agg(lat=("latitude", "first"), lon=("longitude", "first"),
                            techno=("techno", "max"))
                       .reset_index())
    derniere = proches["date_service"].max()

    gagnant = operateurs[0]["nom"]
    return jsonify({
        "adresse": lieu["adresse"],
        "latitude": lieu["latitude"],
        "longitude": lieu["longitude"],
        "gagnant": gagnant,
        "moins_cher": MOINS_CHER.get(gagnant),
        "operateurs": operateurs,
        "antennes": antennes[["operateur", "lat", "lon", "techno"]].to_dict("records"),
        "derniere_mise_en_service": None if pd.isna(derniere) else derniere.strftime("%Y-%m"),
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8501)
