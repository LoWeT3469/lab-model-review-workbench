from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from lab_workbench.api import create_app
from lab_workbench.synthetic import generate
from lab_workbench.train import train

PANEL = {"hemoglobin_g_dl": 13.1, "wbc_10e9_l": 8.2, "platelets_10e9_l": 206, "mcv_fl": 94}


@pytest.fixture(scope="session")
def release(tmp_path_factory):
    output = tmp_path_factory.mktemp("models") / "release"
    train(output)
    return output


@pytest.fixture
def client(release, tmp_path):
    with TestClient(create_app(release, tmp_path / "audit.sqlite3")) as instance:
        yield instance


def send(client, panel=None, request_id=None):
    return client.post("/predictions", json={
        "request_id": request_id or str(uuid4()), "panel": PANEL if panel is None else panel,
    })


@pytest.mark.parametrize("panel", [
    {k: v for k, v in PANEL.items() if k != "hemoglobin_g_dl"},
    {k: v for k, v in PANEL.items() if k != "mcv_fl"},
    {**PANEL, "wbc_10e9_l": -1},
    {**PANEL, "wbc_10e9_l": "8.2"},
    {**PANEL, "wbc_10e9_l": True},
    {**PANEL, "wbc_10e9_l": None, "mcv_fl": None},
    {**PANEL, "patient_id": "demo"},
])
def test_bad_input_records_telemetry_only(client, panel):
    assert send(client, panel).status_code == 422
    assert client.get("/predictions").json() == []
    metrics = client.get("/monitor").json()
    assert metrics["validation_failures"] == 1
    assert metrics["failure_rate"] == 1
    assert metrics["missingness_denominator"] == 1


def test_nonfinite_and_malformed_json(client):
    invalid = ('{"request_id":"%s","panel":{"hemoglobin_g_dl":NaN}}' % uuid4())
    for content in [invalid, '{"unfinished":']:
        response = client.post("/predictions", content=content, headers={"Content-Type": "application/json"})
        assert response.status_code == 422
    metrics = client.get("/monitor").json()
    assert metrics["attempts"] == 2
    assert metrics["missingness_denominator"] == 1


def test_null_imputation_and_idempotent_concurrent_submission(client):
    request_id = str(uuid4())
    panel = {**PANEL, "mcv_fl": None}
    with ThreadPoolExecutor(max_workers=5) as pool:
        responses = list(pool.map(lambda _: send(client, panel, request_id), range(5)))
    assert all(response.status_code == 200 for response in responses)
    records = [response.json() for response in responses]
    assert sum(not result["replayed"] for result in records) == 1
    assert len({(result["created_at"], result["score"]) for result in records}) == 1
    assert send(client, PANEL, request_id).status_code == 409
    metrics = client.get("/monitor").json()
    assert (metrics["attempts"], metrics["unique_predictions"], metrics["deduplicated"]) == (6, 1, 4)
    assert metrics["missing_rates"]["mcv_fl"] == pytest.approx(5 / 6)


def test_review_history_and_retries(client):
    case = send(client).json()
    url = f"/predictions/{case['request_id']}"
    review = {"review_id": str(uuid4()), "reviewer": "demo", "disposition": "flagged", "note": "Verify source"}
    assert client.post(f"{url}/reviews", json={**review, "note": ""}).status_code == 422
    assert client.post(f"{url}/reviews", json=review).json()["replayed"] is False
    assert client.post(f"{url}/reviews", json=review).json()["replayed"] is True
    assert client.post(f"{url}/reviews", json={**review, "note": "Updated"}).status_code == 409
    followup = {**review, "review_id": str(uuid4()), "disposition": "accepted", "note": "Source verified"}
    assert client.post(f"{url}/reviews", json=followup).status_code == 200
    assert [event["note"] for event in client.get(url).json()["reviews"]] == ["Verify source", "Source verified"]
    assert client.get("/predictions").json()[0]["latest_review"] == "accepted"


def test_rollout_replay_and_rollback_survive_restart(release, tmp_path):
    database = tmp_path / "durable.sqlite3"
    with TestClient(create_app(release, database)) as client:
        first = send(client).json()
        assert first["model_version"] == "v1"
        assert client.post("/models/activate", json={"version": "bogus", "reason": "test"}).status_code == 404
        assert client.post("/models/activate", json={"version": "v2", "reason": "trial"}).json()["changed"]
        assert send(client).json()["model_version"] == "v2"
        assert send(client, request_id=first["request_id"]).json() == {**first, "replayed": True}
    with TestClient(create_app(release, database)) as client:
        assert client.get("/health").json()["active_version"] == "v2"
        assert client.post("/models/activate", json={"version": "v1", "reason": "rollback"}).json()["changed"]
        assert not client.post("/models/activate", json={"version": "v1", "reason": "retry"}).json()["changed"]
        assert send(client).json()["model_version"] == "v1"
        assert [event["version"] for event in client.get("/models").json()["history"]] == ["v1", "v2", "v1"]


def test_failed_inference_leaves_no_prediction_and_can_retry(client, monkeypatch):
    def fail(*args):
        raise RuntimeError("Injected failure")

    request_id = str(uuid4())
    with monkeypatch.context() as patch:
        patch.setattr(client.app.state.models["v1"], "predict_proba", fail)
        assert send(client, request_id=request_id).status_code == 500
        assert client.get(f"/predictions/{request_id}").status_code == 404
    assert send(client, request_id=request_id).json()["replayed"] is False
    assert client.get("/monitor").json()["service_errors"] == 1


def test_shift_uses_only_unique_successful_inputs(client):
    assert client.get("/monitor").json()["drift"]["wbc_10e9_l"]["status"] == "insufficient data"
    data, _ = generate(30, seed=421, shifted=True)
    panels = data.astype(object).where(data.notna(), None).to_dict("records")
    for panel in panels:
        case = send(client, panel).json()
        assert send(client, panel, case["request_id"]).json()["replayed"]
    metrics = client.get("/monitor").json()
    wbc = metrics["drift"]["wbc_10e9_l"]
    assert wbc["n"] == sum(panel["wbc_10e9_l"] is not None for panel in panels)
    assert wbc["status"] == "shift signal"
    assert metrics["attempts"] == 60
    assert metrics["unique_predictions"] == 30
