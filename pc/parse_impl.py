"""
parse_impl.py — Extract LUT, FF, BRAM, WNS from Vivado implementation reports
Run from enee759u/:
    python parse_impl.py
Reads results/impl_<label>.rpt and results/util_<label>.rpt
Outputs results/impl_summary.csv
"""

import re
import os
import csv

RESULTS_DIR = "results"

CASES = [
    {"label": "case_02_pipeline_only",    "clock_ns": 5.0,  "dsp": 28},
    {"label": "case_13_clk1ns",           "clock_ns": 1.0,  "dsp": 45},
    {"label": "case_18_iterative_ap_2ns", "clock_ns": 2.0,  "dsp": 1},
]

def parse_utilization(rpt_path):
    """Extract CLB LUTs, CLB Registers, Block RAM from utilization report."""
    result = {"lut": None, "ff": None, "bram": None}
    if not os.path.isfile(rpt_path):
        print(f"  WARNING: not found: {rpt_path}")
        return result

    with open(rpt_path) as f:
        content = f.read()

    # CLB LUTs — first occurrence in the CLB Logic table
    m = re.search(r'\|\s*CLB LUTs\s*\|\s*(\d+)', content)
    if m:
        result["lut"] = int(m.group(1))

    # CLB Registers (Flip Flops)
    m = re.search(r'\|\s*CLB Registers\s*\|\s*(\d+)', content)
    if m:
        result["ff"] = int(m.group(1))

    # Block RAM Tile
    m = re.search(r'\|\s*Block RAM Tile\s*\|\s*(\d+)', content)
    if m:
        result["bram"] = int(m.group(1))
    else:
        # Some reports use "RAMB36/FIFO" instead
        m = re.search(r'\|\s*RAMB36/FIFO\*?\s*\|\s*(\d+)', content)
        if m:
            result["bram"] = int(m.group(1))

    return result


def parse_timing(rpt_path):
    """Extract WNS from timing summary report."""
    result = {"wns": None}
    if not os.path.isfile(rpt_path):
        print(f"  WARNING: not found: {rpt_path}")
        return result

    with open(rpt_path) as f:
        content = f.read()

    # WNS appears in the Design Timing Summary table
    # Format: | WNS(ns) | TNS(ns) | ...
    #         | x.xxx   | ...
    m = re.search(
        r'WNS\(ns\)\s+TNS\(ns\).*?\n[-\s|]+\n\s*\|\s*([-\d.]+)',
        content, re.DOTALL
    )
    if m:
        result["wns"] = float(m.group(1))
    else:
        # Fallback: find first numeric value after WNS header line
        m = re.search(r'WNS\(ns\)[^\n]*\n[^\n]*\n\s*\|\s*([-\d.]+)', content)
        if m:
            result["wns"] = float(m.group(1))

    return result


def main():
    out_path = os.path.join(RESULTS_DIR, "impl_summary.csv")
    fieldnames = ["label", "clock_ns", "dsp", "lut", "ff", "bram",
                  "wns", "achieved_ns", "fmax_mhz", "timing_met"]

    rows = []
    for case in CASES:
        label    = case["label"]
        clock_ns = case["clock_ns"]
        dsp      = case["dsp"]

        util_path   = os.path.join(RESULTS_DIR, f"util_{label}.rpt")
        timing_path = os.path.join(RESULTS_DIR, f"impl_{label}.rpt")

        print(f"\n  Parsing: {label}")
        util   = parse_utilization(util_path)
        timing = parse_timing(timing_path)

        wns = timing["wns"]
        if wns is not None:
            achieved_ns = clock_ns - wns
            fmax_mhz    = round(1000.0 / achieved_ns, 1)
            timing_met  = "YES" if wns >= 0 else "NO"
        else:
            achieved_ns = None
            fmax_mhz    = None
            timing_met  = "UNKNOWN"

        row = {
            "label"      : label,
            "clock_ns"   : clock_ns,
            "dsp"        : dsp,
            "lut"        : util["lut"],
            "ff"         : util["ff"],
            "bram"       : util["bram"],
            "wns"        : wns,
            "achieved_ns": achieved_ns,
            "fmax_mhz"   : fmax_mhz,
            "timing_met" : timing_met,
        }
        rows.append(row)

        print(f"    DSP={dsp}  LUT={util['lut']}  FF={util['ff']}  "
              f"BRAM={util['bram']}  WNS={wns}ns  "
              f"Fmax={fmax_mhz}MHz  timing_met={timing_met}")

    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n  Saved: {out_path}")


if __name__ == "__main__":
    main()
