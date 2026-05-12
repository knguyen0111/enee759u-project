"""
plot_pareto.py — 4 focused Pareto plots for HLS sweep vs handrolled RTL
========================================================================
Plot 1 — Throughput vs DSP (all cases, log x-axis) — headline result
Plot 2 — FF vs Throughput (pipelined cases) — retiming register story
Plot 3 — Latency vs LUT (iterative cases) — loop restructuring story
Plot 4 — Fmax vs DSP (post-impl points only) — direct comparison

Run from enee759u/:
    python plot_pareto.py

Output: results/plots/plot_01..04.png
Requires: pip install pandas matplotlib
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import os

# ==============================================================================
# PATHS
# ==============================================================================
CSV_PATH   = "sweep_results.csv"
OUTPUT_DIR = "plots"
DPI        = 150

# ==============================================================================
# RTL REFERENCE POINTS (post-implementation, Vivado 2025.2)
# ==============================================================================
RTL_ITER = dict(label="Iterative RTL", dsp=1,  lut=341,  ff=1084, latency=68, interval=68,  fmax=481.0)
RTL_PAR  = dict(label="Parallel RTL",  dsp=60, lut=1883, ff=3884, latency=9,  interval=1,   fmax=519.0, fmax_lb=True)

# ==============================================================================
# POST-IMPLEMENTATION HLS (from run_impl.tcl + manual WNS extraction)
# ==============================================================================
IMPL = {
    "case_02_pipeline_only": dict(
        label="HLS pipeline\n(case 02, impl)",
        dsp=28, lut=518, ff=1186,
        fmax=round(1000.0 / (5.0 - 1.911), 1),   # 324 MHz
        timing_met=True,
    ),
    "case_13_clk1ns": dict(
        label="HLS clk1ns\n(case 13, impl)",
        dsp=45, lut=204, ff=1546,
        fmax=round(1000.0 / (1.0 + 0.377), 1),    # 726 MHz
        timing_met=False,
    ),
    "case_18_iterative_ap_2ns": dict(
        label="HLS iterative\n(case 18, impl)",
        dsp=1, lut=66, ff=139,
        fmax=round(1000.0 / (2.0 - 0.413), 1),    # 630 MHz
        timing_met=True,
    ),
}

# ==============================================================================
# COLORS & STYLE
# ==============================================================================
C = dict(
    pipeline  = "#4CAF50",   # green  — pipelined HLS 5ns
    clk_sweep = "#FF9800",   # orange — clock sweep HLS
    iterative = "#2196F3",   # blue   — iterative HLS
    iter_rtl  = "#E91E63",   # pink   — iterative RTL
    par_rtl   = "#9C27B0",   # purple — parallel RTL
    impl_pass = "#00BCD4",   # cyan   — post-impl HLS, timing met
    impl_fail = "#FF5722",   # red    — post-impl HLS, timing violated
)

# ==============================================================================
# HELPERS
# ==============================================================================

def setup(title, xlabel, ylabel, figsize=(8, 5.5)):
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_title(title, fontsize=13, fontweight="bold", pad=10)
    ax.set_xlabel(xlabel, fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.grid(True, alpha=0.25, linestyle="--")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return fig, ax


def ann(ax, x, y, txt, color="#444", dx=6, dy=4, fs=8):
    ax.annotate(txt, (x, y), textcoords="offset points",
                xytext=(dx, dy), fontsize=fs, color=color,
                bbox=dict(boxstyle="round,pad=0.15", fc="white", alpha=0.6, ec="none"))


def star(ax, x, y, label, color, lb=False):
    suffix = "\n(≥ lower bound)" if lb else ""
    ax.scatter(x, y, c=color, marker="*", s=400, zorder=7,
               edgecolors="black", linewidths=0.5, label=f"{label}{suffix}")
    ann(ax, x, y, label + suffix, color=color, dx=8, dy=6, fs=8)


def diamond(ax, x, y, label, timing_met):
    c  = C["impl_pass"] if timing_met else C["impl_fail"]
    fc = c if timing_met else "none"
    viol = "" if timing_met else "\n(timing violated)"
    ax.scatter(x, y, facecolors=fc, edgecolors=c, marker="D",
               s=120, zorder=7, linewidths=1.8, label=f"{label}{viol}")
    ann(ax, x, y, label + viol, color=c, dx=7, dy=5, fs=7)


def save(fig, ax, fname, legend_loc="best"):
    handles, labels = ax.get_legend_handles_labels()
    seen = {}
    for h, l in zip(handles, labels):
        if l not in seen:
            seen[l] = h
    ax.legend(seen.values(), seen.keys(), fontsize=8,
              loc=legend_loc, framealpha=0.9)
    fig.tight_layout()
    path = os.path.join(OUTPUT_DIR, fname)
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {path}")


# ==============================================================================
# LOAD DATA
# ==============================================================================

def load():
    df = pd.read_csv(CSV_PATH)
    df["fmax_mhz"]        = 1000.0 / df["achieved_ns"]
    df["throughput"]      = 1.0 / df["interval"]
    df["timing_violated"] = ~df["status"].astype(str).str.strip().str.startswith("ok")
    return df


# ==============================================================================
# PLOT 1 — Throughput vs DSP (all cases + both RTL)
# Headline result: shows the full design space on one plot.
# Log x-axis separates the iterative cluster (DSP=1) from
# the pipelined cluster (DSP=26-45) and parallel RTL (DSP=60).
# ==============================================================================

def plot1_throughput_dsp(df):
    fig, ax = setup(
        "Plot 1 — Throughput vs DSP: Full Design Space",
        "DSP Slices (log scale)",
        "Throughput (samples/cycle)",
        figsize=(9, 6),
    )
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(ticker.ScalarFormatter())
    ax.set_xticks([1, 5, 10, 26, 45, 60])

    # ---- Iterative HLS cases (1, 16, 17, 18) ----
    iter_cases = df[df["case_num"].isin([1, 16, 17, 18])]
    ax.scatter(iter_cases["dsp"], iter_cases["throughput"],
               c=C["iterative"], marker="o", s=80, zorder=4,
               label="HLS iterative (cases 1, 16–18)")
    for _, r in iter_cases.iterrows():
        ann(ax, r["dsp"], r["throughput"],
            f"case {int(r['case_num'])}\n({r['label']})",
            color=C["iterative"], dx=6, dy=4, fs=7)

    # ---- Pipelined HLS: collapse 2-9 to one point, show 10-15 ----
    # Representative point for cases 2-9
    rep = df[df["case_num"] == 2].iloc[0]
    ax.scatter(rep["dsp"], rep["throughput"],
               c=C["pipeline"], marker="s", s=100, zorder=4,
               label="HLS pipelined 5 ns (cases 2–9, all identical)")
    ann(ax, rep["dsp"], rep["throughput"],
        "cases 2–9\n(unroll 1→64,\nall identical)",
        color=C["pipeline"], dx=6, dy=4, fs=7)

    # Clock sweep cases 10-15
    clk_cases = df[df["case_num"].between(10, 15)]
    ax.scatter(clk_cases["dsp"], clk_cases["throughput"],
               c=C["clk_sweep"], marker="^", s=80, zorder=4,
               label="HLS clock sweep (cases 10–15)")
    for _, r in clk_cases.iterrows():
        ann(ax, r["dsp"], r["throughput"],
            f"case {int(r['case_num'])}", color=C["clk_sweep"], dx=5, dy=3, fs=7)

    # ---- RTL reference stars ----
    star(ax, RTL_ITER["dsp"], 1/RTL_ITER["interval"], "Iterative RTL", C["iter_rtl"])
    star(ax, RTL_PAR["dsp"],  1/RTL_PAR["interval"],  "Parallel RTL",  C["par_rtl"])

    ax.set_ylim(bottom=0, top=1.3)
    ax.set_xlim(left=0.7)

    # Annotate the key story
    ax.annotate(
        "Vitis ignored UNROLL pragma:\ncases 2–9 all identical",
        xy=(26, 1.0), xytext=(15, 0.65),
        fontsize=8, color=C["pipeline"],
        arrowprops=dict(arrowstyle="->", color=C["pipeline"], lw=1.0),
    )

    save(fig, ax, "plot_01_throughput_vs_dsp.png", legend_loc="upper left")


# ==============================================================================
# PLOT 2 — FF vs Throughput (pipelined cases only)
# Shows the retiming register cost as clock tightens.
# All pipelined cases have throughput=1, so FF growth tells
# the entire story of what tighter constraints cost in registers.
# ==============================================================================

def plot2_ff_throughput(df):
    fig, ax = setup(
        "Plot 2 — FF Count vs Throughput: Pipelined HLS Cases",
        "Throughput (samples/cycle)",
        "Flip-Flop Count",
        figsize=(8, 5.5),
    )

    # Collapse 2-9 to case 2
    pipe_plot = pd.concat([
        df[df["case_num"] == 2],
        df[df["case_num"].between(10, 15)],
    ])

    for _, r in pipe_plot.iterrows():
        num = int(r["case_num"])
        viol = bool(r["timing_violated"])
        c  = C["clk_sweep"] if r["clock_ns"] != 5.0 else C["pipeline"]
        fc = c if not viol else "none"
        lbl = "HLS 5 ns" if r["clock_ns"] == 5.0 else f"HLS {r['clock_ns']} ns"
        ax.scatter(r["throughput"], r["ff"],
                   facecolors=fc, edgecolors=c, marker="s" if r["clock_ns"]==5.0 else "^",
                   s=100, zorder=4, linewidths=1.5, label=lbl)
        case_lbl = "cases 2–9" if num == 2 else f"case {num}\n({r['clock_ns']} ns)"
        ann(ax, r["throughput"], r["ff"], case_lbl, color=c, dx=6, dy=4, fs=7)

    # RTL parallel reference
    star(ax, 1/RTL_PAR["interval"], RTL_PAR["ff"], "Parallel RTL", C["par_rtl"])

    ax.set_xlim(left=0, right=1.4)
    ax.set_ylim(bottom=0)

    # Annotate FF growth story
    ax.annotate(
        "FF grows as clock tightens\n(retiming registers added)",
        xy=(1.0, 3400), xytext=(0.3, 3200),
        fontsize=8, color=C["clk_sweep"],
        arrowprops=dict(arrowstyle="->", color=C["clk_sweep"], lw=1.0),
    )

    save(fig, ax, "plot_02_ff_vs_throughput.png", legend_loc="upper left")


# ==============================================================================
# PLOT 3 — Latency vs LUT (iterative cases + iterative RTL)
# Shows how loop restructuring closes the latency gap between
# baseline HLS (139 cycles) and handrolled RTL (68 cycles).
# ==============================================================================

def plot3_latency_lut(df):
    fig, ax = setup(
        "Plot 3 — Latency vs LUT: Iterative Design Comparison",
        "LUT Count",
        "Latency (cycles) — lower is better",
        figsize=(8, 5.5),
    )

    case_styles = {
        1:  (C["iterative"], "o", "baseline, 2-loop (case 1)"),
        16: ("#FF9800",       "s", "single-loop (case 16)"),
        17: ("#4CAF50",       "^", "single-loop + AP, 5 ns (case 17)"),
        18: ("#9C27B0",       "D", "single-loop + AP, 2 ns (case 18)"),
    }

    iter_cases = df[df["case_num"].isin([1, 16, 17, 18])]
    for _, r in iter_cases.iterrows():
        num = int(r["case_num"])
        c, mk, lbl = case_styles[num]
        ax.scatter(r["lut"], r["latency"],
                   c=c, marker=mk, s=100, zorder=5, label=lbl)
        ann(ax, r["lut"], r["latency"],
            f"case {num}\n({int(r['latency'])} cyc)", color=c, dx=6, dy=4, fs=7)

    # RTL star
    star(ax, RTL_ITER["lut"], RTL_ITER["latency"], "Iterative RTL", C["iter_rtl"])

    # Annotate the gap closure
    ax.annotate(
        "Loop restructuring closes\n71-cycle gap to RTL (68 cyc)",
        xy=(202, 71), xytext=(240, 95),
        fontsize=8, color="#333",
        arrowprops=dict(arrowstyle="->", color="#333", lw=1.0),
    )

    ax.invert_yaxis()
    ax.set_ylim(top=50, bottom=155)

    save(fig, ax, "plot_03_latency_vs_lut.png", legend_loc="lower right")


# ==============================================================================
# PLOT 4 — Fmax vs DSP (post-implementation points only)
# The cleanest apples-to-apples comparison: only 5 points,
# all post-implementation, showing the true speed/area tradeoff.
# ==============================================================================

def plot4_fmax_dsp_impl():
    fig, ax = setup(
        "Plot 4 — Fmax vs DSP: Post-Implementation Comparison",
        "DSP Slices",
        "Fmax (MHz)",
        figsize=(8, 5.5),
    )

    # RTL stars
    star(ax, RTL_ITER["dsp"], RTL_ITER["fmax"], "Iterative RTL", C["iter_rtl"])
    star(ax, RTL_PAR["dsp"],  RTL_PAR["fmax"],  "Parallel RTL (≥)",  C["par_rtl"], lb=False)

    # HLS impl diamonds
    for key, impl in IMPL.items():
        diamond(ax, impl["dsp"], impl["fmax"], impl["label"], impl["timing_met"])

    # Annotate parallel RTL as lower bound
    ann(ax, RTL_PAR["dsp"], RTL_PAR["fmax"],
        "lower bound\n(met 2 ns constraint)", color=C["par_rtl"],
        dx=8, dy=-25, fs=7)

    ax.set_xlim(left=-2, right=70)
    ax.set_ylim(bottom=0, top=850)

    # Draw a "better" arrow annotation
    ax.annotate("", xy=(0, 800), xytext=(0, 650),
                arrowprops=dict(arrowstyle="->", color="#999", lw=1.0))
    ax.text(1, 720, "faster", fontsize=7, color="#999", va="center")
    ax.annotate("", xy=(3, 50), xytext=(15, 50),
                arrowprops=dict(arrowstyle="->", color="#999", lw=1.0))
    ax.text(4, 70, "smaller", fontsize=7, color="#999", va="center")

    save(fig, ax, "plot_04_fmax_vs_dsp_impl.png", legend_loc="upper right")


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Loading {CSV_PATH}...")
    df = load()
    print(f"  {len(df)} cases loaded\n")

    print("Generating plots...")
    plot1_throughput_dsp(df)
    plot2_ff_throughput(df)
    plot3_latency_lut(df)
    plot4_fmax_dsp_impl()

    print(f"\nDone. 4 plots saved to {OUTPUT_DIR}/")
    print("  plot_01_throughput_vs_dsp.png  — full design space")
    print("  plot_02_ff_vs_throughput.png   — retiming register cost")
    print("  plot_03_latency_vs_lut.png     — loop restructuring story")
    print("  plot_04_fmax_vs_dsp_impl.png   — post-impl comparison")


if __name__ == "__main__":
    main()
