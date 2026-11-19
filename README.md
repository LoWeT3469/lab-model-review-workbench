# Lab Model Review Workbench

A local portfolio demo for serving a versioned lab-panel model, reviewing its output, and monitoring the service. All training and demo panels are synthetic. The score represents a simulated review label. This independent project has no clinical use or Mayo Clinic affiliation.

This first version is a minimum viable product (MVP). It is small enough to run locally and complete the full workflow from importing a synthetic panel to reviewing a result and rolling back a model. See the [English–Chinese glossary](docs/glossary.md) for terms used in the interface, video, and slides.

## Run locally

With Docker Compose:

```sh
docker compose up --build --wait
```

Open the [review user interface (UI)](http://127.0.0.1:8501) and [application programming interface (API) documentation](http://127.0.0.1:8000/docs). `docker compose down` stops the services and retains the SQLite volume. `docker compose down -v` also deletes the demo records.

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

Training is a one-time step for each artifact directory. Use `--output` to train into a new directory, and set `MODEL_DIR` when serving it. Use `WORKBENCH_DB` to isolate demo runs. By default the service uses `artifacts/models` and `data/workbench.sqlite3`. The UI uses `WORKBENCH_API` to find the API. Run the local tests with `PYTHONPATH=src python -m pytest -q`. GitHub Actions runs continuous integration (CI), which checks the code with tests and verifies that both Compose services start.

## Walkthrough

1. In **Predict**, submit the baseline panel or upload the [comma-separated values (CSV) example](data/example_panel.csv) and choose row 1. Submit it again with the same request identifier (ID) to replay the saved result.
2. Try the out-of-range panel and watch the API reject it with Hypertext Transfer Protocol (HTTP) status 422, which indicates that the submitted input failed validation. Choose **New request ID** before scoring a different valid panel.
3. In **Review**, open the case, flag it with a note and inspect the history.
4. In **Monitoring**, submit the synthetic shift scenario and compare the white blood cell distribution with the training reference.
5. In **Models**, run **Offline replay**. Compare how label source affects agreement and how many panels the two-stage routing policy would escalate.
6. Compare the live release metrics, activate `v2`, score a fresh request, then activate `v1` to roll back. Replaying the `v2` request still returns its original version.

See the [five-minute walkthrough and recording guide](docs/demo.md) and [architecture and data notes](docs/architecture.md).

## Interview materials

- [Expanded interview deck](docs/lab-workbench-interview-deck.pptx)
- [CARE close-reading guide](docs/care-reading-guide.md)
