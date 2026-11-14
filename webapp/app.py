"""
app.py — l'appli web (Flask) : la page + les routes /api/... qui renvoient le verdict.
Lancement, depuis la racine du projet : python -m webapp.app
"""
import math
import os
import sys
import threading
import webbrowser
import pandas as pd
from flask import Flask, jsonify, render_template, request
from waitress import serve
from config import SITES, MESURES, GRILLE, PORT
from webapp.score import score_adresse
from webapp.antennes_proches import distance_km
from webapp.adresse import chercher_adresses

app = Flask(__name__)

# Marque moins chère qui utilise le même réseau
MOINS_CHER = {"Orange": "Sosh", "SFR": "RED by SFR", "Bouygues": "B&You"}

_cache = {"date": None}


def donnees():
    """Les données, lues une fois puis relues seulement si le pipeline les a mises à jour."""
    date = (SITES.stat().st_mtime, MESURES.stat().st_mtime)
    if _cache["date"] != date:
        _cache["sites"] = pd.read_csv(SITES, dtype={"site_id": str, "code_insee": str},
                                      parse_dates=["date_service"])
        _cache["mesures"] = pd.read_csv(MESURES)
        _cache["date"] = date
    return _cache["sites"], _cache["mesures"]


def propre(valeur):
    """NaN -> None, pour que le JSON reste valide."""
    return None if isinstance(valeur, float) and math.isnan(valeur) else valeur


@app.after_request
def journal(reponse):
    """Une ligne par requête dans le log (log/webapp.log), comme le serveur de développement de Flask."""
    if request.path != "/sante":                 # Docker appelle /sante toutes les 30 s : pas dans le log
        print(f"{request.remote_addr} {request.method} {request.full_path.rstrip('?')} {reponse.status_code}")
    return reponse


@app.route("/")
def accueil():
    return render_template("index.html")


@app.route("/sante")
def sante():
    """Supervision : l'appli répond-elle, et ses données sont-elles là ? (utilisée par le HEALTHCHECK de Docker)"""
    fichiers = {f.name: f.exists() for f in (SITES, MESURES, GRILLE)}
    ok = all(fichiers.values())
    return jsonify({"statut": "ok" if ok else "données manquantes", "fichiers": fichiers}), 200 if ok else 503


@app.route("/api/adresses")
def adresses():
    """Suggestions d'adresses pendant la frappe."""
    texte = request.args.get("q", "")
    return jsonify(chercher_adresses(texte) if len(texte) >= 3 else [])


@app.route("/api/score")
def score():
    """Adresse -> verdict, classement des 4 opérateurs et antennes à moins d'1 km."""
    sites, mesures = donnees()
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
    # L'ANFR déclare aussi des mises en service prévues (dans le futur) : on ne garde que celles déjà passées
    derniere = proches.loc[proches["date_service"] <= pd.Timestamp.today(), "date_service"].max()

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
    donnees()                                    # lecture au démarrage, pas à la 1re recherche
    # Ouvre la page dans le navigateur une fois le serveur prêt, seulement s'il y a un écran :
    # Windows, Mac, ou Linux avec un bureau. Pas sur un serveur ni dans Docker.
    ecran = sys.platform in ("win32", "darwin") or os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
    if ecran:
        threading.Timer(1.5, webbrowser.open, [f"http://localhost:{PORT}"]).start()
    print(f"Appli prête : http://localhost:{PORT}")
    # waitress : un vrai serveur web (le serveur intégré à Flask n'est fait que pour développer).
    # Il marche sous Windows, Mac et Linux. threads=8 : plusieurs visiteurs en même temps.
    serve(app, host="0.0.0.0", port=PORT, threads=8)
