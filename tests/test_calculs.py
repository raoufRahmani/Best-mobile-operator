"""Tests des calculs : distance, positions ANFR, grille de couverture, lissage des mesures."""
import numpy as np
import pandas as pd
import pytest
from pipeline.clean import en_decimal
from pipeline.couverture import assembler, DECALAGE, NIVEAUX
from webapp.antennes_proches import distance_km, mesures_autour, K
from webapp.score import POIDS


def test_distance_paris_lyon():
    # Notre-Dame de Paris -> place Bellecour à Lyon : environ 392 km à vol d'oiseau
    assert distance_km(48.8530, 2.3499, 45.7578, 4.8320) == pytest.approx(392, abs=2)


def test_distance_nulle():
    assert distance_km(48.89, 2.18, 48.89, 2.18) == 0


def test_degres_minutes_secondes():
    # 48° 51' 24" N et 2° 21' 0" W -> 48,8567 et -2,35
    lat = en_decimal(pd.Series(["48"]), pd.Series(["51"]), pd.Series(["24"]), pd.Series(["N"]), "S")
    lon = en_decimal(pd.Series(["2"]), pd.Series(["21"]), pd.Series(["0"]), pd.Series(["W"]), "W")
    assert lat[0] == pytest.approx(48.8567, abs=1e-4)
    assert lon[0] == pytest.approx(-2.35)


def test_grille_un_octet_pour_4_operateurs():
    # Chaque opérateur a un niveau différent (0 à 3) dans la même case : on doit tous les retrouver
    niveaux = {"BOUY": 3, "FREE": 0, "OF": 2, "SFR0": 1}
    grilles = {code: np.full((1, 1), n, np.uint8) for code, n in niveaux.items()}
    case = int(assembler(grilles)[0, 0])
    for code, n in niveaux.items():
        assert (case >> DECALAGE[code]) & 3 == n
    assert NIVEAUX[3] == "Très bonne couverture"


def test_lissage_sans_test_local():
    # Aucun test près de l'adresse -> on obtient la moyenne nationale
    mesures = pd.DataFrame({"operateur": ["Orange", "SFR"], "latitude": [45.0, 45.0],
                            "longitude": [5.0, 5.0], "reussi": [1, 0], "debit": [100.0, 20.0]})
    resume = mesures_autour(mesures, 48.89, 2.18)       # à Nanterre, loin des 2 tests
    assert (resume["nb_tests"] == 0).all()
    assert (resume["taux_ajuste"] == 50).all()          # moyenne nationale : 1 test réussi sur 2


def test_lissage_un_seul_test_rate():
    # Un seul test raté tout près ne fait pas tomber l'opérateur à 0 %
    mesures = pd.DataFrame({"operateur": ["Orange"] * 2, "latitude": [48.89, 45.0],
                            "longitude": [2.18, 5.0], "reussi": [0, 1], "debit": [10.0, 10.0]})
    taux = mesures_autour(mesures, 48.89, 2.18).loc["Orange", "taux_ajuste"]
    assert taux == round(100 * K * 0.5 / (1 + K))       # ≈ 48 %, pas 0 %


def test_poids_du_score():
    assert sum(POIDS.values()) == pytest.approx(1)
