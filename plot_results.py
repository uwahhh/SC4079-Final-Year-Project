# plot_results.py
# Single-graph comparison: all test cases sorted by mean_us (ascending),
# with each point labeled by ds/mode/k/bucket.

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
# pip install statsmodels
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.stats.anova import anova_lm
CSV_PATH = "results_testcases_rebuilt.csv"


def partial_eta_squared(anova_df: pd.DataFrame) -> pd.DataFrame:
    # partial eta^2 = SS_effect / (SS_effect + SS_error)
    # assumes last row is Residual
    if "sum_sq" not in anova_df.columns:
        return anova_df
    ss_error = anova_df.loc["Residual", "sum_sq"] if "Residual" in anova_df.index else None
    if ss_error is None or ss_error == 0:
        return anova_df
    anova_df = anova_df.copy()
    anova_df["partial_eta2"] = anova_df["sum_sq"] / (anova_df["sum_sq"] + ss_error)
    return anova_df

def main():
    df = pd.read_csv(CSV_PATH)

    # --- clean / normalize ---
    for col in ["ds", "mode", "bucket"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    df["k"] = pd.to_numeric(df["k"], errors="coerce")
    df["mean_us"] = pd.to_numeric(df["mean_us"], errors="coerce")
    df = df.dropna(subset=["ds", "mode", "bucket", "k", "mean_us"])

    # keep only needed columns
    d = df[["ds", "mode", "k", "bucket", "mean_us"]].copy()

    # build label per point
    d["k_int"] = d["k"].astype(int)
    d["label"] = d.apply(
        lambda r: f"{r['ds']}|{r['mode']}|k={r['k_int']}|{r['bucket']}",
        axis=1
    )

    # sort ascending by mean_us
    d = d.sort_values("mean_us", ascending=True).reset_index(drop=True)

    x = np.arange(len(d))
    y = d["mean_us"].to_numpy()

    # --- plot ---
    # width scales with number of points so labels are less cramped
    fig_w = max(12, len(d) * 0.45)
    plt.figure(figsize=(fig_w, 7))
    plt.plot(x, y, marker="o", linewidth=1)

    plt.title("All test cases sorted by mean_us (lower is faster)")
    plt.xlabel("Rank (sorted ascending by mean_us)")
    plt.ylabel("mean_us")

    # label every point (set STEP=2 or 3 if too crowded)
    STEP = 1
    for i, (yy, lab) in enumerate(zip(y, d["label"])):
        if i % STEP == 0:
            plt.annotate(
                lab,
                (x[i], yy),
                textcoords="offset points",
                xytext=(0, 6),
                ha="center",
                fontsize=8,
                rotation=60
            )

    plt.tight_layout()
    plt.savefig("all_cases_sorted_mean_us.png", dpi=200)
    plt.close()

    print("Saved: all_cases_sorted_mean_us.png")
        # =========================
    # Factor impact (ANOVA on log(mean_us))
    # =========================
    df2 = df.copy()
    df2["log_mean_us"] = np.log(df2["mean_us"])

    # Main effects model: ds + mode + bucket + k
    m1 = smf.ols("log_mean_us ~ C(ds) + C(mode) + C(bucket) + k", data=df2).fit()
    df2["fitted"] = m1.fittedvalues
    df2["residual"] = m1.resid
    df2["abs_residual"] = df2["residual"].abs()

    anoms = df2.sort_values("abs_residual", ascending=False).head(10)
    print("\n=== Top anomalous cases (largest absolute residuals) ===")
    print(anoms[["ds", "mode", "k", "bucket", "mean_us", "fitted", "residual"]])
    a1 = anova_lm(m1, typ=2)
    a1 = partial_eta_squared(a1)
    # save anomaly table
    anoms[["ds", "mode", "k", "bucket", "mean_us", "fitted", "residual"]].to_csv(
        "top_anomalous_cases.csv", index=False
    )
    print("Saved: top_anomalous_cases.csv")

    a1 = anova_lm(m1, typ=2)
    a1 = partial_eta_squared(a1)

    print("\n=== ANOVA table ===")
    print(a1)

    # save ANOVA table
    a1.to_csv("anova_factor_impact.csv")
    print("Saved: anova_factor_impact.csv")

    # Keep only factors (drop residual), sort by impact
    impact = a1.drop(index=["Residual"], errors="ignore")[["partial_eta2"]].copy()
    impact = impact.sort_values("partial_eta2", ascending=False)

    print("\n=== Factor impact (partial eta^2, bigger => more effect on runtime) ===")
    print(impact)

    # Plot impact as a bar chart
    plt.figure(figsize=(8, 4.5))
    plt.bar(impact.index.astype(str), impact["partial_eta2"].to_numpy())
    plt.title("Which factor affects runtime most (ANOVA on log(mean_us))")
    plt.ylabel("partial eta^2")
    plt.xticks(rotation=25, ha="right")
    plt.tight_layout()
    plt.savefig("factor_impact_partial_eta2.png", dpi=200)
    plt.close()

    print("Saved: factor_impact_partial_eta2.png")
    print("\n=== Marginal means (mean_us) ===")
    for factor in ["ds", "mode", "bucket", "k"]:
        plt.figure(figsize=(7, 4.5))
        df2.boxplot(column="mean_us", by=factor)
        plt.title(f"Runtime distribution by {factor}")
        plt.suptitle("")
        plt.ylabel("mean_us")
        plt.xticks(rotation=25)
        plt.tight_layout()
        plt.savefig(f"boxplot_{factor}_mean_us.png", dpi=200)
        plt.close()

    print(f"Saved: boxplot_{factor}_mean_us.png")
    print("\nBy ds:\n", df2.groupby("ds")["mean_us"].mean().sort_values())
    print("\nBy mode:\n", df2.groupby("mode")["mean_us"].mean().sort_values())
    print("\nBy bucket:\n", df2.groupby("bucket")["mean_us"].mean().sort_values())
    print("\nBy k:\n", df2.groupby("k")["mean_us"].mean().sort_index())



if __name__ == "__main__":
    main()
