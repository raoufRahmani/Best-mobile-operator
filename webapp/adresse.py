import requests
from config import API_ADRESSE

URL = API_ADRESSE


def geocoder(adresse):
    """Transforme une adresse en position GPS. Renvoie None si introuvable."""
    reponse = requests.get(URL, params={"q": adresse, "limit": 1}, timeout=10)
    resultats = reponse.json()["features"]
    if not resultats:
        return None

    lon, lat = resultats[0]["geometry"]["coordinates"]
    infos = resultats[0]["properties"]
    return {
        "adresse": infos["label"],
        "latitude": lat,
        "longitude": lon,
        "code_insee": infos["citycode"],
        "confiance": infos["score"],
    }


def chercher_adresses(texte, nb=5):
    """Les nb adresses qui correspondent le mieux au texte tapé."""
    reponse = requests.get(URL, params={"q": texte, "limit": nb}, timeout=10)
    return [f["properties"]["label"] for f in reponse.json().get("features", [])]


if __name__ == "__main__":
    print(geocoder("112 Bd de l'Hôpital"))