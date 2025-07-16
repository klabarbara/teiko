import pandas as pd

import seaborn as sns
import matplotlib.pyplot as plt
from scipy.stats import mannwhitneyu

def compute_relative_frequencies(engine):
    """return a DataFrame with sample, total_count, population, count, percentage."""
    sql = """
    SELECT s.sample_id AS sample,
           SUM(c.count) OVER (PARTITION BY c.sample_id) AS total_count,
           c.population,
           c.count
    FROM cell_counts c
    JOIN samples s ON s.sample_id = c.sample_id
    """
    df = pd.read_sql(sql, engine)
    df["percentage"] = df["count"] / df["total_count"] * 100
    return df

def compare_responders(engine, condition="melanoma", treatment="miraclib"):
    """boxplot data & significance tests between responders vs non-responders."""
    freq = compute_relative_frequencies(engine)
    mask = (
        (freq["population"].notna()) &
        (freq["sample"].isin(
            pd.read_sql("SELECT sample_id FROM samples WHERE "
                        "condition=:cond AND treatment=:treat AND sample_type='PBMC'",
                        engine, params={"cond":condition,"treat":treatment})["sample_id"]
        ))
    )
    sub = freq[mask].merge(
         pd.read_sql("SELECT sample_id, response FROM samples", engine),
         left_on="sample", right_on="sample_id"
    )

    return sub

def plot_population_boxplots(engine, condition="melanoma", treatment="miraclib"):
    """
    returns a boxplot figure for each population,
    split by responder vs non-responder.
    """
    df = compare_responders(engine, condition, treatment)
    plt.figure(figsize=(10, 6))
    sns.boxplot(
        x="population", y="percentage", hue="response",
        data=df, fliersize=3
    )
    plt.title(f"{condition.capitalize()} + {treatment}: responders vs non-responders")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    return plt.gcf()  


def test_significant_populations(engine, condition="melanoma", treatment="miraclib", alpha=0.05):
    """
    FYI: little bit of AI help to select appropriate testing for this study
    runs a two-sided Mann–Whitney U test for each population,
    comparing percent frequencies in responders vs non-responders.
    returns a DataFrame with p-values and a boolean flag for significance.
    """
    df = compare_responders(engine, condition, treatment)
    pops = sorted(df["population"].unique())
    records = []
    for pop in pops:
        grp = df[df["population"] == pop]
        resp = grp[grp["response"] == True]["percentage"]
        nonr = grp[grp["response"] == False]["percentage"]
        stat, pval = mannwhitneyu(resp, nonr, alternative="two-sided")
        records.append({
            "population": pop,
            "u_stat": stat,
            "p_value": pval,
            "significant": pval < alpha
        })
    return pd.DataFrame.from_records(records)


def get_baseline_samples(engine,
                         condition="melanoma",
                         treatment="miraclib",
                         sample_type="PBMC",
                         time_point=0):
    """
    returns a DataFrame of all samples matching the filters at baseline.
    """
    sql = """
    SELECT * FROM samples
    WHERE condition = :cond
      AND treatment = :treat
      AND sample_type = :stype
      AND time_from_treatment_start = :t
    """
    return pd.read_sql(sql, engine,
                       params={
                         "cond": condition,
                         "treat": treatment,
                         "stype": sample_type,
                         "t": time_point
                       })


def summarize_baseline(df):
    """
    FYI: little bit of AI help to address "WHY WON'T YOU WORK" on three lines of code
    given the baseline-sample DataFrame, returns three summary tables:
      1) samples per project
      2) responders vs non-responders
      3) sex distribution
    """
    proj_counts = (
        df["project"]
        .value_counts()
        .rename_axis("project")
        .reset_index(name="num_samples")
    )

    resp_str = df["response"].astype(bool).map({
        True: "responder",
        False: "non-responder"
    })

    resp_counts = (
        resp_str
          .value_counts()
          .rename_axis("response")
          .reset_index(name="num_subjects")
    )
    sex_counts = (
        df["sex"]
        .value_counts()
        .rename_axis("sex")
        .reset_index(name="num_subjects")
    )
    return proj_counts, resp_counts, sex_counts
