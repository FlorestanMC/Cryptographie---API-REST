import os
import tempfile

os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

STAGE = {
    "nom_etudiant": "Alice Martin",
    "entreprise": "Airbus",
    "intitule": "Développeur Backend",
    "date_debut": "2026-02-01",
    "date_fin": "2026-07-31",
}


def test_crud_complet():
    with TestClient(app) as client:
        # Création
        r = client.post("/stages", json=STAGE)
        assert r.status_code == 201
        stage_id = r.json()["id"]

        # Liste
        r = client.get("/stages")
        assert r.status_code == 200
        assert any(s["id"] == stage_id for s in r.json())

        # Consultation
        assert client.get(f"/stages/{stage_id}").json()["entreprise"] == "Airbus"

        # Modification
        r = client.put(f"/stages/{stage_id}", json={"entreprise": "Thales"})
        assert r.status_code == 200
        assert r.json()["entreprise"] == "Thales"
        assert r.json()["nom_etudiant"] == "Alice Martin"

        # Suppression
        assert client.delete(f"/stages/{stage_id}").status_code == 204
        assert client.get(f"/stages/{stage_id}").status_code == 404


def test_stage_inexistant():
    with TestClient(app) as client:
        assert client.get("/stages/9999").status_code == 404
        assert client.put("/stages/9999", json={"entreprise": "X"}).status_code == 404
        assert client.delete("/stages/9999").status_code == 404


def test_validation_dates():
    with TestClient(app) as client:
        bad = {**STAGE, "date_debut": "2026-08-01", "date_fin": "2026-01-01"}
        assert client.post("/stages", json=bad).status_code == 422
        r = client.post("/stages", json=STAGE)
        sid = r.json()["id"]
        assert client.put(f"/stages/{sid}", json={"date_fin": "2020-01-01"}).status_code == 422


def test_champ_manquant():
    with TestClient(app) as client:
        incomplet = {k: v for k, v in STAGE.items() if k != "entreprise"}
        assert client.post("/stages", json=incomplet).status_code == 422
