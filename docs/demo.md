# Five-minute interview walkthrough

Start with a new demo database so the active version is `v1` and the shift cohort is fresh. Launch Docker Compose or follow the README. Open the user interface before the interview. Keep the [example comma-separated values (CSV) file](../data/example_panel.csv) and the [English–Chinese glossary](glossary.md) available.

| Time | Action | What to explain |
| --- | --- | --- |
| 0:00–0:30 | Show the deployment diagram and open **Predict**. | “Streamlit is the current browser client. A custom review front end can use the same FastAPI service. The service owns validation, audit history and release decisions.” |
| 0:30–1:20 | Import the first example row, submit it twice, then try the out-of-range example. | “The fitted preprocessing runs with the model. A repeat submission reuses the original prediction. Invalid input fails before inference.” |
| 1:20–2:05 | Flag the case in **Review** and inspect history. | “The reviewer saw the prediction. Their feedback is a valuable review event. Its provenance matters when we choose labels for evaluation.” |
| 2:05–2:50 | Send the shift scenario in **Monitoring**. | “White blood cell inputs shifted. I investigate the affected inputs and the ingestion path. Estimating an accuracy change requires independently sourced reference results.” |
| 2:50–4:05 | In **Models**, run **Offline replay**. Compare the reference-like cohort across both columns, then inspect the shifted cohort and routed count. | “The same predictions give different model rankings under different label sources. The two-stage cascade also shows how many cases a routing rule sends to the second model. Both comparisons are synthetic experiments.” |
| 4:05–5:00 | Activate `v2`, submit a fresh prediction, reactivate `v1` and point to the history. | “The deployment decision is explicit and audited. The new version handles new requests. Prior requests retain the original model and result.” |

### Likely follow-up questions

- **Why SQLite?** It keeps the local system small and gives atomic prediction and audit writes. Serialization bounds throughput and is an explicit demo tradeoff.
- **How would you validate a real use case?** Define the decision and time of use with users first. Verify feature availability, label provenance and review workload before designing a cohort and prospective evaluation.
- **How much work did it save?** No time study was performed. The concrete behavior shown is avoiding repeated scoring and duplicate prediction records on retries and consolidating the case details and feedback in the review view.

- **How does this build on your prelim?** Progressive Neural Networks (PNN) preserve old columns while adding capacity for new tasks. Here I keep the incumbent release fixed and compare policies on reference-like and shifted cohorts. The cascade addresses a separate question about routing at prediction time.
- **Why consider a custom front end?** The deployment diagram shows it calling the same service. I would start with a case queue and review pane and verify that the interaction reduces work before migrating more screens.
