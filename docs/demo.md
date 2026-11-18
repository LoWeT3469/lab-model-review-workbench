# Five-minute interview walkthrough

Start with a new demo database so the active version is `v1` and the shift cohort is fresh. Launch Docker Compose or follow the README. Open the UI before the interview. Keep the [example CSV](../data/example_panel.csv) available.

| Time | Action | What to explain |
| --- | --- | --- |
| 0:00–0:35 | Open **Predict** and select the baseline panel or CSV row 1. | “This is a personal project for exploring lab model operations. The four measurements and the review target are synthetic. I wanted to make the path from serving to human review visible.” |
| 0:35–1:20 | Submit, point to the score, version and request ID, and submit again. | “Training and serving share the fitted pipeline. A retry with the same UUID and panel returns the original result and preserves one prediction record.” |
| 1:20–1:55 | Select the out-of-range example and submit it. | “The API returns 422 before model inference. The rejected attempt contributes to the service metrics. One explicitly null optional field is supported through training-median imputation.” |
| 1:55–2:45 | Go to **Review**, select the case, choose **flagged**, add ‘Verify source value’ and save. | “The reviewer sees the exact panel and version. The note and disposition form a separate event. Feedback is useful for investigating issues and can reflect the score the reviewer already saw.” |
| 2:45–3:45 | Go to **Monitoring**, send the shift scenario and select white blood cells. | “Attempts include retries and rejects. Drift uses unique accepted panels. These bins show a change in the synthetic inputs. Online performance measurement would require linked outcome labels.” |
| 3:45–4:40 | In **Models**, activate `v2` with a reason. Return to **Predict**, choose the baseline, generate a new ID and submit. Activate `v1` again. | “Both versions use the same holdout. New requests use the active model, while old requests retain the version and exact score recorded at prediction time.” |
| 4:40–5:00 | Show activation history and wrap up. | “Compose gives me a reproducible local environment. The implementation makes the data contract, review trail and rollback behavior easy to inspect.” |

### Likely follow-up questions

- **Why SQLite?** It keeps the local system small and gives atomic prediction and audit writes. Serialization bounds throughput and is an explicit demo tradeoff.
- **How would you validate a real use case?** Define the decision and time of use with users first. Verify feature availability, label provenance and review workload before designing a cohort and prospective evaluation.
- **How much work did it save?** No time study was performed. The concrete behavior shown is avoiding repeated scoring and duplicate prediction records on retries and consolidating the case details and feedback in the review view.
