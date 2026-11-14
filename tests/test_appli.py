"""Tests de l'appli web (Flask), sans Internet : l'API Adresse est remplacée par une fausse."""
import pytest
from webapp.app import app

NANTERRE = {"adresse": "8 Rue du Port 92000 Nanterre", "latitude": 48.893461,
            "longitude": 2.178892, "code_insee": "92050", "confiance": 0.97}


@pytest.fixture
def client():
    return app.test_client()


@pytest.fixture
def fausse_api_adresse(monkeypatch):
    """Remplace le géocodage : Nanterre si on tape « nanterre », sinon introuvable."""
    monkeypatch.setattr("webapp.score.geocoder",
                        lambda adresse: NANTERRE if "nanterre" in adresse.lower() else None)


def test_page_accueil(client):
    reponse = client.get("/")
    assert reponse.status_code == 200
    assert "Quel opérateur chez moi" in reponse.text


def test_sante(client):
    reponse = client.get("/sante")
    assert reponse.status_code == 200
    assert reponse.json["statut"] == "ok"


def test_suggestions_texte_trop_court(client):
    assert client.get("/api/adresses?q=ab").json == []


def test_adresse_introuvable(client, fausse_api_adresse):
    reponse = client.get("/api/score?adresse=zzzz")
    assert reponse.status_code == 404


def test_score_nanterre(client, fausse_api_adresse):
    data = client.get("/api/score?adresse=8 rue du Port, Nanterre").json
    scores = [op["score"] for op in data["operateurs"]]

    assert sorted(op["nom"] for op in data["operateurs"]) == ["Bouygues", "Free", "Orange", "SFR"]
    assert all(0 <= s <= 100 for s in scores)
    assert scores == sorted(scores, reverse=True)       # classés du meilleur au moins bon
    assert data["gagnant"] == data["operateurs"][0]["nom"]
    assert len(data["antennes"]) > 0                    # Nanterre : des antennes à moins d'1 km
