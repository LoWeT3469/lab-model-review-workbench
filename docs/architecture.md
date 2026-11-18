# Architecture and data decisions

The Streamlit user interface (UI) uses FastAPI as its application programming interface (API) for prediction, review and monitoring. See the [English–Chinese glossary](glossary.md) for terms used below.

```mermaid
flowchart LR
  subgraph CLIENT["Browser clients"]
    UI["Streamlit · current workbench"]
    WEB["Custom web front end · proposed"]
  end
  subgraph SERVICE["Docker-packaged FastAPI service"]
    CONTRACT["Shared interface and input validation"]
    LIVE["Live prediction · one active release"]
    REPLAY["Offline replay · compare labels and cascade"]
  end
  TRAIN["Seeded training and holdout evaluation"] --> RELEASE["Versioned pipelines and manifest"]
  RELEASE --> LIVE
  RELEASE --> REPLAY
  UI --> CONTRACT
  WEB -.-> CONTRACT
  CONTRACT --> LIVE
  CONTRACT --> REPLAY
  LIVE --> DB[("SQLite · predictions, review history, activation log")]
  DB --> MON["Windowed service metrics and input drift"]
  MON --> CONTRACT
```

The proposed custom front end can start with a queue and case-detail view. React and TypeScript would handle browser interaction and typed responses. Vite would build the web assets. Both clients call the same endpoints. Input checks, review persistence and model activation belong to the service, so a browser reload or a change of client does not change those rules.

## Data and model

The simulator draws four numeric fields with weak latent correlations. A noisy nonlinear logistic rule generates a binary *simulated need for review*. It introduces training missingness after drawing the label. Seed 42 produces 2,400 panels, split once into 1,800 training and 600 stratified holdout rows. Both releases use the same split. Preprocessing fits the training medians and scaling parameters inside the pipeline. Inference loads that fitted pipeline. The model manifest records the generator ID, seed, feature order, library version, holdout metrics, training distribution bins and each file checksum. The area under the receiver operating characteristic curve (ROC AUC) summarizes how well a model ranks positives above negatives. Average precision summarizes the trade-off between precision and recall as the threshold changes. Both are illustrative offline metrics on synthetic labels. The 0.50 display threshold has no clinical calibration.

The input contract requires all four keys. Hemoglobin needs a finite numeric value. At most one of white blood cells, platelets or mean corpuscular volume may be explicitly null. Types and broad ingestion bounds catch likely formatting or unit mistakes. They carry no clinical interpretation. A one-row-at-a-time comma-separated values (CSV) import keeps validation and review behavior the same for uploaded and built-in examples.

The University of California, Irvine (UCI) Chronic Kidney Disease (CKD) dataset has 400 historical records and includes diagnostic correlates such as serum creatinine. A real benchmark would require defining the time of prediction and verifying which variables are available then. A simulator makes demo edge cases reproducible and decouples the example from any disease or institution. [UCI CKD dataset](https://archive.ics.uci.edu/dataset/336/chronic)

## Serving, audit and release control

Each request identifier (ID) uses a Universally Unique Identifier (UUID). In the Hypertext Transfer Protocol (HTTP), this service uses GET to read records and POST to submit data or initiate an action.

| Operation | Behavior |
| --- | --- |
| `POST /predictions` | Normalize numeric inputs and bind the request UUID to one panel. Same panel replays the saved response. Different valid panel with the same UUID returns 409. Invalid input returns 422. |
| `GET /predictions` and `GET /predictions/{id}` | List recent cases and show the saved panel, timestamp, score, version, checksum and review history. |
| `POST /predictions/{id}/reviews` | Append a reviewer alias, disposition and note with a review UUID. Retrying identical feedback reuses the event. Flagging requires a note. |
| `GET /models` and `POST /models/activate` | Compare releases on the same holdout and record a version switch with a reason. Rollback is the same operation targeting an older release. |
| `GET /evaluation/replay` | Run a deterministic, read-only comparison of label sources and routing policies. |
| `GET /monitor` and `GET /health` | Read operational metrics or API readiness. |

A SQLite write transaction serializes the duplicate check, model selection and insert. This keeps a second process from scoring the same ID and establishes a clear order between accepting a new request and activating a model. The cost is one write lane during inference. SQLite write-ahead logging (WAL) permits readers to access an existing snapshot while a write is in progress. The active version is the last activation event and survives restarts. For this two-release demo both models load at startup. Bindings prevent a version name in the database from silently pointing to different bytes. Load the joblib files only from the locally generated, trusted release. The manifest checksum detects a mismatched artifact. It provides no signature or independent trust anchor.

A failure before prediction commit leaves the request ID available for retry. Attempt telemetry is best effort and has its own transaction, so a telemetry write failure can undercount attempts without invalidating a committed result. A reviewer alias is self-entered. Review events have application-level history, with no authentication or tamper protection. The activation controls share the same local demo boundary.

## Monitoring

| Signal | Definition |
| --- | --- |
| Request volume | Number of prediction POST attempts in the selected time window, including replays and failures. Unique predictions have their own count. |
| Latency | The 95th percentile (p95) of API handling time in milliseconds (ms). About 95% of requests complete within that duration. Excludes telemetry persistence and network time. |
| Failure rate | HTTP status ≥400 divided by prediction POST attempts. Validation and service failures are shown separately. |
| Missingness | Per-field proportion of panel objects with an absent or null field. Includes rejected payloads with a panel object and retries. Malformed JavaScript Object Notation (JSON) has no measurable panel. |
| Input drift | Compare fixed training quantile-bin frequencies with successful unique panels. Nulls are excluded feature by feature, with counts shown. Total variation distance is half the sum of absolute bin-frequency differences. The demo signals at 0.20 with at least 20 observations. |

The drift scenario adds 5 simulator units to the mean white blood cell signal and increases simulated missingness. It posts 30 valid panels with stable IDs. The threshold and minimum count are demonstration settings. Observed shifts can come from ingestion changes, workflow changes, or a different population. Assessing performance requires trustworthy outcomes linked to predictions. Reviewers see the model output, so their feedback may be influenced by it. Feedback stays in the review history and is excluded from automatic retraining.

## Offline replay and release evidence

The replay scores a reference-like cohort and a cohort with a simulated input shift. Each contains 800 synthetic panels generated with seed 2026, separate from the training and holdout data. It compares agreement on the same cases using two reference definitions:

- **Independent simulator label.** Drawn before feature missingness and before either model scores the case.
- **Model-influenced comparison label.** On a seeded sample with a 70% selection probability, copy the `v1` suggestion. Keep the independent simulator label for other cases. This deliberately models one possible feedback mechanism. Real reviewer behavior and the Mayo study's case-selection rules may differ.

The third policy in the comparison is a **two-stage cascade (级联)**. Logistic regression (`v1`) goes first. For scores in the illustrative band [0.40, 0.60), the policy uses the random forest (`v2`) prediction. The replay scores both models on every row to compare policies on shared inputs. It reports the routed fraction and agreement by cohort and label source. A live rollout would also require measuring errors in the routed and retained groups, reviewer workload and latency. The replay has no authority to change the active release. Activation and rollback use the live version controls and record a reason.

**Progressive Neural Networks (PNN, 渐进式神经网络)** freeze earlier network columns and add a new column for adaptation across tasks. This motivates preserving an incumbent and assessing new behavior against old and shifted cohorts. A cascade decides which stage handles a request at inference. An independently sourced evaluation label remains necessary for both approaches. The displayed models are fixed tabular baselines. [Progressive Neural Networks](https://arxiv.org/abs/1606.04671) · [Classifier Cascade for Minimizing Feature Evaluation Cost](https://proceedings.mlr.press/v22/chen12c.html) · [Day and colleagues' label feedback abstract](https://doi.org/10.1093/clinchem/hvag001)

## Public context

The public Clinical AI Readiness Evaluator (CARE) paper describes eight workstreams spanning use case, data, pipeline, code, user experience, infrastructure, orchestration and regulatory compliance. Figure 7 describes a mass spectrometry model whose research and deployment environments required different languages. The demo uses a shared fitted pipeline, a documented input contract, and an automated container startup check. The data lineage companion also motivates documenting which inputs, transformations and labels were used for training and verification. The interview discussions about deployment, repetitive work and use of results motivated the walkthrough. The exact data and workflow for the role are unspecified. [CARE lifecycle overview, Figure 7](https://academic.oup.com/ajcp/article/164/3/424/8197944) · [Data lineage companion](https://academic.oup.com/ajcp/article-abstract/165/5/aqag029/8675909)
