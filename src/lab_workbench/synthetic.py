"""Seeded simulator shared by training and the monitoring scenario."""

import numpy as np
import pandas as pd

from .schema import FEATURES


def generate(count: int, seed: int, shifted: bool = False) -> tuple[pd.DataFrame, np.ndarray]:
    rng = np.random.default_rng(seed)
    latent = rng.normal(size=count)
    panel = pd.DataFrame({
        "hemoglobin_g_dl": rng.normal(13.5 - 0.8 * latent, 1.1),
        "wbc_10e9_l": rng.normal(7.2 + 0.9 * latent + (5 if shifted else 0), 1.2),
        "platelets_10e9_l": rng.normal(245 - 24 * latent, 43),
        "mcv_fl": rng.normal(89 + 1.8 * latent, 5),
    })
    for name, (_, _, low, high) in FEATURES.items():
        panel[name] = panel[name].clip(low + 0.1, high).round(2)

    # Generate the toy label before introducing missingness. The added noise makes
    # identical-looking panels capable of having different underlying labels.
    logit = (
        -0.5 - 0.7 * (panel.hemoglobin_g_dl - 13.5)
        + 0.45 * (panel.wbc_10e9_l - 7.2)
        - 0.015 * (panel.platelets_10e9_l - 245)
        + 0.025 * (panel.mcv_fl - 89) ** 2
        + rng.normal(0, 0.45, count)
    )
    labels = rng.binomial(1, 1 / (1 + np.exp(-logit)))
    missing = rng.random(count) < (0.22 if shifted else 0.10)
    missing_column = rng.choice(list(FEATURES)[1:], count)
    for name in list(FEATURES)[1:]:
        panel.loc[missing & (missing_column == name), name] = np.nan
    return panel, labels
