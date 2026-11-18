# Lab Model Review Workbench

A local portfolio demo for serving a versioned lab-panel model, reviewing its output, and monitoring the service. All training and demo panels are synthetic. The score represents a simulated review label. This independent project has no clinical use or Mayo Clinic affiliation.

## Run locally

With Docker Compose:

```sh
docker compose up --build --wait
```

Open the [review UI](http://127.0.0.1:8501) and [API documentation](http://127.0.0.1:8000/docs). `docker compose down` stops the services and retains the SQLite volume. `docker compose down -v` also deletes the demo records.

To run without Docker, use Python 3.11. In the current checkout the parent path contains a colon, so create the virtual environment outside the checkout. From the repository root:

```sh
python3.11 -m venv "$HOME/.venvs/lab-workbench"
source "$HOME/.venvs/lab-workbench/bin/activate"
python -m pip install -r requirements-dev.txt
export PYTHONPATH=src
python -m lab_workbench.train
python -m uvicorn lab_workbench.api:app --host 127.0.0.1 --port 8000
```

In a second terminal, from the repository root:

```sh
source "$HOME/.venvs/lab-workbench/bin/activate"
PYTHONPATH=src python -m streamlit run src/lab_workbench/ui.py --server.address=127.0.0.1
```

Training is a one-time step for each artifact directory. Use `--output` to train into a new directory, and set `MODEL_DIR` when serving it. Use `WORKBENCH_DB` to isolate demo runs. By default the service uses `artifacts/models` and `data/workbench.sqlite3`. The UI uses `WORKBENCH_API` to find the API. Run the local tests with `PYTHONPATH=src python -m pytest -q`. GitHub Actions defines unit and integration tests plus Compose smoke checks.

## Walkthrough

1. In **Predict**, submit the baseline panel or upload [example_panel.csv](data/example_panel.csv) and choose row 1. Submit it again with the same request ID to replay the saved result.
2. Try the out-of-range panel and watch the API reject it with HTTP 422. Choose **New request ID** before scoring a different valid panel.
3. In **Review**, open the case, flag it with a note and inspect the history.
4. In **Monitoring**, submit the synthetic shift scenario and compare the white blood cell distribution with the training reference.
5. In **Models**, compare the holdout metrics, activate `v2`, score a fresh request, then activate `v1` to roll back. Replaying the `v2` request still returns its original version.

See the [five-minute demo](docs/demo.md) and [architecture and data notes](docs/architecture.md).

## Interview materials

- [Captioned demo video](docs/lab-workbench-demo.mp4)
- [Four-slide briefing deck](docs/lab-workbench-slides.pptx)
