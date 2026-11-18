"""Streamlit client for the local workbench API."""

import csv
import os
import re
from io import StringIO
from uuid import uuid4

import pandas as pd
import requests
import streamlit as st

from lab_workbench.schema import AUDIENCE_NOTICE, FEATURES
from lab_workbench.synthetic import generate

API = os.getenv("WORKBENCH_API", "http://127.0.0.1:8000")
BASE_PANEL = dict(zip(FEATURES, [13.1, 8.2, 206.0, 94.0]))
SAMPLES = {
    "Baseline panel": BASE_PANEL,
    "One null measurement": {**BASE_PANEL, "mcv_fl": None},
    "Out-of-range white blood cells": {**BASE_PANEL, "wbc_10e9_l": -2.0},
    "Missing hemoglobin field": {key: value for key, value in BASE_PANEL.items() if key != "hemoglobin_g_dl"},
}
NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")


def call(method, path, payload=None):
    try:
        response = requests.request(method, f"{API}{path}", json=payload, timeout=10)
        result = response.json()
    except (requests.RequestException, ValueError):
        st.error("API unavailable. Check the service and retry with the same ID.")
        return None
    if not response.ok:
        detail = result.get("detail", "Request failed")
        if isinstance(detail, list):
            detail = " · ".join(f"{'.'.join(map(str, item['loc'][1:]))}: {item['msg']}" for item in detail)
        st.error(f"HTTP {response.status_code} · {detail}")
        return None
    return result


def parse_cell(value):
    value = value.strip()
    if not value:
        return None
    if NUMBER.fullmatch(value):
        number = float(value)
        if abs(number) != float("inf"):
            return number
    return value


def import_csv(upload):
    if upload.size > 64_000:
        raise ValueError("The demo accepts CSV files up to 64 KB.")
    reader = csv.DictReader(StringIO(upload.getvalue().decode("utf-8-sig"), newline=""), strict=True)
    headers = reader.fieldnames or []
    if not headers or len(headers) != len(set(headers)) or any(name not in FEATURES for name in headers):
        raise ValueError("Use unique column names from the displayed input contract.")
    rows = []
    for row in reader:
        if len(rows) == 100:
            raise ValueError("Upload at most 100 rows.")
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"Row {reader.line_num} has a different number of cells than the header.")
        rows.append({key: parse_cell(value) for key, value in row.items()})
    if not rows:
        raise ValueError("Add at least one data row.")
    return rows


def panel_table(panel):
    st.dataframe(
        [{"Measurement": label, "Value": "Missing" if name not in panel else
          "Null" if panel[name] is None else str(panel[name]), "Unit": unit}
         for name, (label, unit, _, _) in FEATURES.items()],
        hide_index=True, use_container_width=True,
    )


def prediction_details(result):
    score, decision, version = st.columns(3)
    score.metric("Simulated review score", f"{result['score']:.1%}")
    decision.metric("Model suggestion", "Review" if result["suggested_review"] else "Routine")
    version.metric("Model version", result["model_version"])
    st.caption(f"Saved {result['created_at']} UTC · Request {result['request_id']}")
    with st.expander("Artifact checksum"):
        st.code(result["model_sha256"], language=None)
    st.caption("The demo threshold is 0.50. A blank optional value uses the training median.")


def predict_page():
    st.header("Run a prediction")
    st.caption("Choose a synthetic example or import a synthetic panel from CSV.")
    source = st.radio("Input source", ["Synthetic example", "CSV"], horizontal=True)
    if source == "CSV":
        st.caption("CSV schema fields: " + ", ".join(FEATURES))
        upload = st.file_uploader("Synthetic panel CSV", type=["csv"])
        if not upload:
            return
        try:
            rows = import_csv(upload)
        except (ValueError, UnicodeError, csv.Error) as error:
            st.error(str(error))
            return
        row = st.number_input("Row to score", 1, len(rows), 1)
        panel = rows[row - 1]
    else:
        panel = SAMPLES[st.selectbox("Example", SAMPLES)]
    panel_table(panel)
    if "request_id" not in st.session_state:
        st.session_state.request_id = str(uuid4())
    left, right = st.columns([4, 1], vertical_alignment="bottom")
    request_id = left.text_input("Request ID", key="request_id")
    right.button("New request ID", on_click=lambda: st.session_state.update(
        request_id=str(uuid4()), last_prediction=None
    ), use_container_width=True)
    if st.button("Submit panel", type="primary"):
        st.session_state.last_prediction = call("POST", "/predictions", {"request_id": request_id, "panel": panel})
    result = st.session_state.get("last_prediction")
    if result and result["request_id"] == request_id and result["panel"] == panel:
        message = "Existing prediction returned. Audit record reused." if result["replayed"] else "Prediction saved."
        st.success(message)
        prediction_details(result)


def review_page():
    st.header("Review cases")
    cases = call("GET", "/predictions")
    if cases is None:
        return
    if not cases:
        st.info("Submit a panel to create a review case.")
        return
    labels = {row["request_id"]: f"{row['request_id'][:8]} · {row['model_version']} · "
              f"{(row['latest_review'] or 'pending').capitalize()}" for row in cases}
    request_id = st.selectbox("Recent cases", list(labels), format_func=labels.__getitem__)
    result = call("GET", f"/predictions/{request_id}")
    if result is None:
        return
    prediction_details(result)
    panel_table(result["panel"])
    with st.form(f"review-{request_id}"):
        reviewer = st.text_input("Reviewer alias", "demo-reviewer", max_chars=64)
        disposition = st.radio("Disposition", ["accepted", "flagged"], horizontal=True)
        note = st.text_area("Review note", max_chars=1000, placeholder="Required for a flagged case")
        submitted = st.form_submit_button("Save review", type="primary")
    if submitted:
        signature = (request_id, reviewer.strip(), disposition, note.strip())
        if st.session_state.get("review_signature") != signature:
            st.session_state.update(review_signature=signature, review_id=str(uuid4()))
        payload = {"review_id": st.session_state.review_id, "reviewer": reviewer,
                   "disposition": disposition, "note": note}
        saved = call("POST", f"/predictions/{request_id}/reviews", payload)
        if saved is not None:
            st.session_state.review_notice = (request_id, saved["replayed"])
            st.rerun()
    notice = st.session_state.pop("review_notice", None)
    if notice and notice[0] == request_id:
        st.success("Existing review returned." if notice[1] else "Review saved.")
    st.subheader("Review history")
    if result["reviews"]:
        st.dataframe(pd.DataFrame(result["reviews"])[
            ["created_at", "reviewer", "disposition", "note", "review_id"]
        ], hide_index=True, use_container_width=True)
    else:
        st.caption("This case is awaiting review.")


def monitor_page():
    st.header("Service and data quality")
    hours = st.selectbox("Lookback window", [1, 24, 168], index=1, format_func=lambda value: f"{value} hours")
    first, second = st.columns(2)
    first.button("Refresh metrics")
    if second.button("Send 30 synthetic shifted panels", use_container_width=True):
        data, _ = generate(30, seed=421, shifted=True)
        panels = data.astype(object).where(data.notna(), None).to_dict("records")
        # Re-running the same scenario reuses the same cases and preserves the drift cohort.
        from uuid import NAMESPACE_URL, uuid5
        with st.spinner("Submitting simulated white blood cell shift"):
            sent = 0
            for index, panel in enumerate(panels):
                request_id = str(uuid5(NAMESPACE_URL, f"lab-workbench:shift-421:{index}"))
                if call("POST", "/predictions", {"request_id": request_id, "panel": panel}) is None:
                    break
                sent += 1
        st.caption(f"{sent} of 30 scenario requests completed. The scenario uses stable request IDs.")
    metric = call("GET", f"/monitor?hours={hours}")
    if metric is None:
        return
    fields = ["attempts", "unique_predictions", "deduplicated", "failure_rate", "p95_ms"]
    labels = ["Attempts", "Unique predictions", "Replays", "Failure rate", "p95 latency"]
    for column, key, label in zip(st.columns(5), fields, labels):
        value = metric[key]
        formatted = "—" if value is None else (
            f"{value:.1%}" if key == "failure_rate" else f"{value:.1f} ms" if key == "p95_ms" else value
        )
        column.metric(label, formatted)
    st.caption(f"{metric['validation_failures']} validation failures · {metric['service_errors']} service errors")
    st.subheader("Input missingness")
    st.caption(f"Denominator: {metric['missingness_denominator']} attempts with a panel object.")
    rates = [{"Measurement": FEATURES[name][0], "Missing": "—" if rate is None else f"{rate:.1%}"}
             for name, rate in metric["missing_rates"].items()]
    st.dataframe(rates, hide_index=True, use_container_width=True)
    st.subheader("Input distribution")
    st.caption("Compared with the synthetic training reference. Drift tracks input change. Live accuracy requires outcome labels.")
    feature = st.selectbox("Measurement", list(FEATURES), index=1, format_func=lambda name: FEATURES[name][0])
    drift = metric["drift"][feature]
    distance = "" if drift["distance"] is None else f" · distance {drift['distance']:.2f}"
    st.write(f"**{drift['status'].capitalize()}** · {drift['n']} non-null observations{distance}")
    edges = [f"{edge:g}" for edge in drift["edges"]]
    bins = [f"< {edges[0]}", *[f"{low}–{high}" for low, high in zip(edges, edges[1:])], f"≥ {edges[-1]}"]
    series = {"Training reference": drift["reference_fractions"]}
    if drift["live_fractions"] is not None:
        series["Observed"] = drift["live_fractions"]
    chart = pd.DataFrame(series, index=pd.Index([f"{i + 1}. {value}" for i, value in enumerate(bins)],
                                                name="Training bins"))
    st.bar_chart(chart, stack=False, y_label="Fraction of observations")


def models_page():
    st.header("Model releases")
    data = call("GET", "/models")
    if data is None:
        return
    st.metric("Active version", data["active_version"])
    st.caption(f"Same {data['holdout_rows']}-row synthetic holdout · simulator seed {data['seed']}")
    st.dataframe([
        {"Version": version, "Estimator": entry["name"], "ROC AUC": entry["roc_auc"],
         "Average precision": entry["average_precision"]}
        for version, entry in data["releases"].items()
    ], hide_index=True, use_container_width=True)
    with st.form("model-activation"):
        version = st.selectbox("Version to activate", list(data["releases"]))
        reason = st.text_input("Change reason", max_chars=200)
        submitted = st.form_submit_button("Activate version", type="primary")
    if submitted:
        result = call("POST", "/models/activate", {"version": version, "reason": reason})
        if result is not None:
            st.session_state.activation_notice = (
                f"{version} is now active." if result["changed"] else f"{version} was already active."
            )
            st.rerun()
    notice = st.session_state.pop("activation_notice", None)
    if notice:
        st.success(notice)
    st.subheader("Activation history")
    st.dataframe(pd.DataFrame(data["history"])[["created_at", "previous_version", "version", "reason"]],
                 hide_index=True, use_container_width=True)


def main():
    st.set_page_config(page_title="Lab Model Review Workbench", layout="wide")
    with st.sidebar:
        st.markdown("### Lab Workbench")
        st.caption("Synthetic lab model operations")
        selection = st.radio("Workspace", ["Predict", "Review", "Monitoring", "Models"])
        st.caption("Personal portfolio demo · Local sandbox")
    st.title("Lab Model Review Workbench" if selection == "Predict" else selection)
    st.caption(AUDIENCE_NOTICE)
    {"Predict": predict_page, "Review": review_page, "Monitoring": monitor_page, "Models": models_page}[selection]()


if __name__ == "__main__":
    main()
