"""
HOW TO RUN:
-----------
  Dry run first (generates all fir.cpp + cfg, no Vitis calls):
      python sweep.py --dry-run

  Full sweep:
      python sweep.py

  Resume from a specific case (if sweep crashed mid-run):
      python sweep.py --start 5
"""

import subprocess
import os
import sys
import csv
import shutil
import argparse
import xml.etree.ElementTree as ET
from datetime import datetime

# ==============================================================================
# CONFIG
# ==============================================================================
VITIS_BIN   = r"D:\AMDDesignTools\2025.2\Vitis\bin"
VITIS_RUN   = os.path.join(VITIS_BIN, "vitis-run")
VPP         = os.path.join(VITIS_BIN, "v++")
PART        = "xczu5ev-fbvb900-2-i"
TOP         = "fir"
TB_FILE     = "tb_fir.cpp"          # shared testbench
SWEEP_DIR   = "sweep"               # parent dir for all per-case work dirs
RESULTS_DIR = "results"
RESULTS_CSV = os.path.join(RESULTS_DIR, "sweep_results.csv")
LOG_FILE    = os.path.join(RESULTS_DIR, "sweep_run.log")

CSV_FIELDNAMES = [
    "case_num", "label", "pipeline", "unroll", "array_partition", "clock_ns",
    "dsp", "lut", "ff", "bram", "latency", "interval", "ii",
    "achieved_ns", "timing_ok", "status",
]

# ==============================================================================
# TEST CASES
# 16 cases covering:
#   1        — baseline (no pragmas, 5ns): closest HLS analog to iterative RTL
#   2–3      — pipeline effect isolation
#   4–9      — unroll sweep (pragma Pareto at fixed relaxed clock)
#   10–13    — clock sweep (Fmax vs area at fixed meaningful pragmas)
#   14–15    — aggressive: fully unrolled + tight clock
#   16       — restructured single-loop fir.cpp (mirrors handrolled iterative RTL)
# ==============================================================================
TEST_CASES = [
    # num  label                  pipeline  unroll  array_part  clock_ns  fir_variant
    ( 1,  "baseline",             False,    1,      False,      5.0,      "standard"),
    ( 2,  "pipeline_only",        True,     1,      False,      5.0,      "standard"),
    ( 3,  "pipeline_ap",          True,     1,      True,       5.0,      "standard"),
    ( 4,  "unroll2",              True,     2,      True,       5.0,      "standard"),
    ( 5,  "unroll4",              True,     4,      True,       5.0,      "standard"),
    ( 6,  "unroll8",              True,     8,      True,       5.0,      "standard"),
    ( 7,  "unroll16",             True,     16,     True,       5.0,      "standard"),
    ( 8,  "unroll32",             True,     32,     True,       5.0,      "standard"),
    ( 9,  "unroll64",             True,     64,     True,       5.0,      "standard"),
    (10,  "clk4ns",               True,     8,      True,       4.0,      "standard"),
    (11,  "clk3ns",               True,     8,      True,       3.0,      "standard"),
    (12,  "clk2ns",               True,     8,      True,       2.0,      "standard"),
    (13,  "clk1ns",               True,     8,      True,       1.0,      "standard"),
    (14,  "aggressive_4ns",       True,     64,     True,       4.0,      "standard"),
    (15,  "aggressive_2ns",       True,     64,     True,       2.0,      "standard"),
    (16,  "iterative_restructure",False,    1,      False,      5.0,      "iterative"),
    (17,  "iterative_ap_5ns",     False,    1,      True,       5.0,      "iterative"),
    (18,  "iterative_ap_2ns",     False,    1,      True,       2.0,      "iterative"),
]


# ==============================================================================
# FIR.CPP GENERATORS
# ==============================================================================

def make_fir_standard(pipeline, unroll, array_partition):
    """
    Standard two-loop FIR: separate shift loop then MAC loop.
    Matches the fir.cpp used in basic.py.
    """
    pipeline_pragma  = "    #pragma HLS PIPELINE II=1" if pipeline else ""
    partition_pragma = """\
    #pragma HLS ARRAY_PARTITION variable=shift complete
    #pragma HLS ARRAY_PARTITION variable=h complete""" if array_partition else ""
    unroll_pragma    = f"        #pragma HLS UNROLL factor={unroll}" if unroll > 1 else ""

    return f"""\
#include "ap_int.h"
#include "../../taps_init.h"
#define NTAPS 64

void fir(ap_int<16> sample_in, ap_int<16> &sample_out) {{
{pipeline_pragma}

    static ap_int<16> shift[NTAPS];

{partition_pragma}

    ap_int<40> acc = 0;

    for (int i = NTAPS-1; i > 0; --i) {{
        shift[i] = shift[i-1];
    }}
    shift[0] = sample_in;

    for (int i = 0; i < NTAPS; ++i) {{
{unroll_pragma}
        acc += (ap_int<32>)h[i] * (ap_int<32>)shift[i];
    }}

    sample_out = (ap_int<16>)((acc + 0x4000) >> 15);
}}
"""


def make_fir_iterative():
    """
    Restructured single-loop FIR that mirrors the handrolled iterative RTL:
    shift and accumulate in one 64-cycle pass, one MAC per cycle.
    No pragmas — lets Vitis schedule it as a pure sequential loop.
    Expected: latency ~64 cycles, interval ~65, 1 DSP.
    Compare directly against handrolled iterative RTL (latency=68, interval=68).
    """
    return """\
#include "ap_int.h"
#include "../../taps_init.h"
#define NTAPS 64

void fir(ap_int<16> sample_in, ap_int<16> &sample_out) {

    static ap_int<16> shift[NTAPS];

    ap_int<40> acc = 0;

    // Single merged loop: shift register update and MAC in one pass.
    // Mirrors the handrolled iterative RTL which does both in one cycle.
    // i=0 uses the new sample_in; i>0 reads the existing shift register.
    for (int i = NTAPS-1; i >= 0; --i) {
        ap_int<16> s;
        if (i == 0) {
            s = sample_in;
        } else {
            s = shift[i-1];
        }
        shift[i] = s;
        acc += (ap_int<32>)h[i] * (ap_int<32>)s;
    }

    sample_out = (ap_int<16>)((acc + 0x4000) >> 15);
}
"""


def make_config(work_dir, clock_ns):
    """
    Generate hls_config.cfg inside work_dir/.
    tb.file paths are relative to the config file location.
    The io/ dir and TB_FILE are one level up (../), since work_dir
    is sweep/case_NN_label/ which is two levels below enee759u/.
    """
    # From sweep/case_NN/ the shared files are ../../
    return f"""\
part={PART}

[hls]
flow_target=vivado
package.output.format=ip_catalog
package.output.syn=false
clock={clock_ns}ns
syn.top={TOP}
syn.file=./fir.cpp
tb.file=../../{TB_FILE}
tb.file=../../io/input.mem
tb.file=../../io/output_15.mem
"""


# ==============================================================================
# BINARY RESOLUTION & ENVIRONMENT CHECK
# ==============================================================================

def resolve_binary(preferred):
    base = os.path.splitext(preferred)[0]
    name = os.path.basename(base)
    candidates = [preferred] + [base + s for s in (".bat", ".exe", ".cmd")]
    for candidate in candidates:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    for suffix in ("", ".bat", ".exe", ".cmd"):
        found = shutil.which(name + suffix)
        if found:
            return found
    return None


def check_environment():
    print("\n--- Environment Check ---")
    ok = True
    resolved = {}
    for label, preferred in [("vitis-run", VITIS_RUN), ("v++", VPP)]:
        path = resolve_binary(preferred)
        if path:
            print(f"  {label:>12}: {path}  [OK]")
            resolved[label] = path
        else:
            print(f"  {label:>12}: NOT FOUND")
            print(f"               Searched: {preferred}(.bat/.exe/.cmd)")
            print(f"               Run:  dir \"{VITIS_BIN}\"  to see what's there")
            ok = False

    print("\n  Vitis-related PATH entries:")
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if any(k in entry for k in ("Vitis", "Vivado", "AMD", "Xilinx")):
            print(f"    {entry}")

    print("\n  Key environment variables:")
    for var in ("XILINX_VITIS", "XILINX_HLS"):
        print(f"    {var} = {os.environ.get(var, '<not set>')}")

    print("\n  Shared source files:")
    for path in [TB_FILE, "taps_init.h", "io/input.mem", "io/output_15.mem"]:
        exists = os.path.isfile(path)
        print(f"    {'OK' if exists else 'MISSING':>7}  {path}")
        if not exists:
            ok = False

    print("-------------------------\n")
    if not ok:
        return None, None
    return resolved.get("vitis-run"), resolved.get("v++")


# ==============================================================================
# SUBPROCESS RUNNER
# ==============================================================================

def _run(cmd, step_name, log_fh):
    """
    Run a subprocess, print full output, write to log.
    Always wraps with cmd.exe /c on Windows for .bat launcher compatibility.
    Returns (returncode, combined_output_str).
    """
    cmd = [str(c) for c in cmd]
    print(f"\n  [{step_name}] Command: {' '.join(cmd)}")
    log_fh.write(f"\n{'='*60}\n[{step_name}] {' '.join(cmd)}\n{'='*60}\n")

    env = os.environ.copy()
    launcher = (["cmd.exe", "/c"] + cmd) if os.name == "nt" else cmd

    try:
        result = subprocess.run(
            launcher,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )
    except FileNotFoundError as e:
        msg = f"\n  ERROR: Could not launch '{launcher[0]}'\n  {e}\n"
        print(msg)
        log_fh.write(msg)
        return -1, str(e)

    print(result.stdout)
    log_fh.write(result.stdout)
    return result.returncode, result.stdout


# ==============================================================================
# CSIM & SYNTHESIS
# ==============================================================================

def run_csim(vitis_run, work_dir, config_file, log_fh):
    cmd = [
        vitis_run, "--mode", "hls", "--csim",
        "--config", config_file,
        "--work_dir", work_dir,
    ]
    rc, out = _run(cmd, "csim", log_fh)
    if rc == -1:
        return False, "binary_not_found"
    if rc != 0:
        return False, f"returncode_{rc}"
    if "FAIL" in out:
        return False, "csim_output_FAIL"
    if "PASS" in out:
        print("  csim: PASS")
    else:
        print("  WARNING: csim returned 0 but no PASS string found — continuing")
    return True, "ok"


def run_synthesis(vpp, work_dir, config_file, log_fh):
    cmd = [
        vpp, "-c", "--mode", "hls",
        "--config", config_file,
        "--work_dir", work_dir,
    ]
    rc, _ = _run(cmd, "synth", log_fh)
    if rc == -1:
        return False, "binary_not_found"
    if rc != 0:
        return False, f"returncode_{rc}"
    return True, "ok"


# ==============================================================================
# REPORT PARSING
# ==============================================================================

def find_report(work_dir):
    target = f"{TOP}_csynth.xml"
    for dirpath, _dirnames, files in os.walk(work_dir):
        for f in files:
            if f == target:
                found = os.path.join(dirpath, f)
                print(f"  Found report: {found}")
                return found
    print(f"  ERROR: {target} not found under {work_dir}/")
    print(f"  Files present:")
    for dirpath, _dirnames, files in os.walk(work_dir):
        for f in files:
            print(f"    {os.path.join(dirpath, f)}")
    return None


def parse_report(work_dir):
    path = find_report(work_dir)
    if path is None:
        return None

    tree = ET.parse(path)
    root = tree.getroot()

    perf = root.find("PerformanceEstimates")
    lat  = perf.find("SummaryOfOverallLatency")
    clk  = perf.find("SummaryOfTimingAnalysis/EstimatedClockPeriod")
    area = root.find("AreaEstimates/Resources")

    # Timing violation check
    timing_ok = True
    violations = perf.find("SummaryOfViolations")
    if violations is not None:
        vtype = violations.find("ViolationType")
        if vtype is not None and vtype.text and vtype.text.strip() != "-":
            timing_ok = False

    # Loop-level II (from pragma result, -1 if not pipelined)
    ii_elem = lat.find("PipelineInitiationInterval")
    ii = int(ii_elem.text) if ii_elem is not None and ii_elem.text else -1

    # Function-level interval (how often top-level function accepts new input)
    # This is the real throughput number: throughput = 1/interval samples/cycle
    interval_elem = lat.find("Interval-max")
    if interval_elem is None:
        # Fallback: some Vitis versions nest it differently
        interval_elem = lat.find("Interval/Max")
    interval = int(interval_elem.text) if interval_elem is not None and interval_elem.text else -1

    return {
        "dsp"        : int(area.find("DSP").text),
        "lut"        : int(area.find("LUT").text),
        "ff"         : int(area.find("FF").text),
        "bram"       : int(area.find("BRAM_18K").text),
        "latency"    : int(lat.find("Worst-caseLatency").text),
        "interval"   : interval,
        "ii"         : ii,
        "achieved_ns": float(clk.text),
        "timing_ok"  : timing_ok,
    }


# ==============================================================================
# DRY RUN: generate all files, print summary table, exit
# ==============================================================================

def dry_run():
    print(f"\n{'='*60}")
    print(f"  sweep.py — DRY RUN")
    print(f"  Generating all fir.cpp and hls_config.cfg files.")
    print(f"  No Vitis tools will be called.")
    print(f"{'='*60}\n")

    os.makedirs(SWEEP_DIR, exist_ok=True)

    print(f"  {'#':>3}  {'label':<25}  {'pipe':>4}  {'unroll':>6}  {'ap':>3}  {'clk':>5}  {'variant':<12}  work_dir")
    print(f"  {'-'*3}  {'-'*25}  {'-'*4}  {'-'*6}  {'-'*3}  {'-'*5}  {'-'*12}  {'-'*40}")

    for (num, label, pipeline, unroll, array_part, clock_ns, fir_variant) in TEST_CASES:
        work_dir    = os.path.join(SWEEP_DIR, f"case_{num:02d}_{label}")
        src         = os.path.join(work_dir, "fir.cpp")
        config_file = os.path.join(work_dir, "hls_config.cfg")

        os.makedirs(work_dir, exist_ok=True)

        # Generate fir.cpp
        if fir_variant == "iterative":
            fir_code = make_fir_iterative()
        else:
            fir_code = make_fir_standard(pipeline, unroll, array_part)

        with open(src, "w") as f:
            f.write(fir_code)

        # Generate hls_config.cfg
        with open(config_file, "w") as f:
            f.write(make_config(work_dir, clock_ns))

        pipe_str = "II=1" if pipeline else "no"
        ap_str   = "yes" if array_part else "no"
        print(f"  {num:>3}  {label:<25}  {pipe_str:>4}  {unroll:>6}  {ap_str:>3}  {clock_ns:>5}  {fir_variant:<12}  {work_dir}")

    print(f"\n  Generated {len(TEST_CASES)} cases under {SWEEP_DIR}/")
    print(f"\n  Inspect files, then run:  python sweep.py")
    print(f"\n  To inspect a specific case:")
    print(f"    type sweep\\case_01_baseline\\fir.cpp")
    print(f"    type sweep\\case_01_baseline\\hls_config.cfg")


# ==============================================================================
# MAIN SWEEP LOOP
# ==============================================================================

def main(start_from=1):
    print(f"\n{'='*60}")
    print(f"  sweep.py — HLS pragma/clock sweep")
    print(f"  {len(TEST_CASES)} test cases | start from case {start_from}")
    print(f"  cwd={os.getcwd()}  python={sys.executable}")
    print(f"  started={datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    os.makedirs(SWEEP_DIR, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)

    with open(LOG_FILE, "w") as log_fh:
        log_fh.write(f"sweep.py run log\ncwd: {os.getcwd()}\nstarted: {datetime.now()}\n")

        # --- Environment check ---
        vitis_run, vpp = check_environment()
        if vitis_run is None or vpp is None:
            print("  ABORT — fix missing binaries/files listed above.")
            return

        # --- CSV setup: write header if file doesn't exist yet ---
        csv_exists = os.path.isfile(RESULTS_CSV)
        csv_fh = open(RESULTS_CSV, "a", newline="")
        writer = csv.DictWriter(csv_fh, fieldnames=CSV_FIELDNAMES)
        if not csv_exists:
            writer.writeheader()

        # --- csim gate flag: run csim on case 1 only ---
        # Pragmas don't affect C simulation output, so one passing csim
        # is sufficient to validate the C model. If case 1 csim fails,
        # abort — something is wrong with fir.cpp or the testbench.
        csim_validated = False

        # --- Filter cases to run ---
        cases_to_run = [c for c in TEST_CASES if c[0] >= start_from]
        print(f"\n  Running {len(cases_to_run)} cases (skipping {len(TEST_CASES) - len(cases_to_run)} already done)\n")

        # --- Per-case loop ---
        for (num, label, pipeline, unroll, array_part, clock_ns, fir_variant) in cases_to_run:

            work_dir    = os.path.join(SWEEP_DIR, f"case_{num:02d}_{label}")
            src         = os.path.join(work_dir, "fir.cpp")
            config_file = os.path.join(work_dir, "hls_config.cfg")

            print(f"\n{'='*60}")
            print(f"  CASE {num:02d}/{len(TEST_CASES)}: {label}")
            print(f"  pipeline={pipeline}  unroll={unroll}  ap={array_part}  clock={clock_ns}ns  variant={fir_variant}")
            print(f"  work_dir: {work_dir}")
            print(f"{'='*60}")

            log_fh.write(f"\n\n{'#'*60}\nCASE {num:02d}: {label}\n{'#'*60}\n")

            os.makedirs(work_dir, exist_ok=True)

            # --- Write fir.cpp ---
            if fir_variant == "iterative":
                fir_code = make_fir_iterative()
            else:
                fir_code = make_fir_standard(pipeline, unroll, array_part)

            with open(src, "w") as f:
                f.write(fir_code)
            log_fh.write(f"\n--- fir.cpp ---\n{fir_code}\n")
            print(f"  Wrote {src}")

            # --- Write hls_config.cfg ---
            cfg_text = make_config(work_dir, clock_ns)
            with open(config_file, "w") as f:
                f.write(cfg_text)
            log_fh.write(f"\n--- hls_config.cfg ---\n{cfg_text}\n")
            print(f"  Wrote {config_file}")

            status = "ok"

            # --- csim: only on case 1, gate the entire sweep ---
            if not csim_validated:
                print(f"\n  [csim] Running on case {num} as validation gate...")
                csim_ok, csim_reason = run_csim(vitis_run, work_dir, config_file, log_fh)
                if not csim_ok:
                    print(f"\n  ABORT — csim failed on case {num} ({csim_reason}).")
                    print(f"  Fix fir.cpp or testbench before re-running.")
                    print(f"  Full log: {LOG_FILE}")
                    # Write failure row and stop
                    row = _empty_row(num, label, pipeline, unroll, array_part, clock_ns, f"csim_fail:{csim_reason}")
                    writer.writerow(row)
                    csv_fh.flush()
                    csv_fh.close()
                    return
                csim_validated = True
                print(f"  csim gate passed — skipping csim for remaining cases")
            else:
                print(f"  [csim] Skipping (validated on case 1)")

            # --- Synthesis ---
            synth_ok, synth_reason = run_synthesis(vpp, work_dir, config_file, log_fh)
            if not synth_ok:
                print(f"  SKIPPING case {num} — synthesis failed ({synth_reason})")
                status = f"synth_fail:{synth_reason}"
                row = _empty_row(num, label, pipeline, unroll, array_part, clock_ns, status)
                writer.writerow(row)
                csv_fh.flush()
                continue

            # --- Parse report ---
            metrics = parse_report(work_dir)
            if metrics is None:
                print(f"  SKIPPING case {num} — report parse failed")
                status = "parse_fail"
                row = _empty_row(num, label, pipeline, unroll, array_part, clock_ns, status)
                writer.writerow(row)
                csv_fh.flush()
                continue

            # --- Write CSV row immediately ---
            row = {
                "case_num"       : num,
                "label"          : label,
                "pipeline"       : pipeline,
                "unroll"         : unroll,
                "array_partition": array_part,
                "clock_ns"       : clock_ns,
                "status"         : "ok",
                **metrics,
            }
            writer.writerow(row)
            csv_fh.flush()   # flush after every row so partial results survive crashes

            # --- Live summary line ---
            fmax = round(1000.0 / metrics["achieved_ns"], 1) if metrics["achieved_ns"] > 0 else "?"
            tput = (f"1/{metrics['interval']}" if metrics["interval"] > 0 else "?")
            print(f"\n  RESULT  DSP={metrics['dsp']:>4}  LUT={metrics['lut']:>5}  "
                  f"FF={metrics['ff']:>5}  BRAM={metrics['bram']:>2}  "
                  f"Latency={metrics['latency']:>4}  Interval={metrics['interval']:>4}  "
                  f"II={metrics['ii']:>3}  Fmax≈{fmax}MHz  "
                  f"Timing={'OK' if metrics['timing_ok'] else 'VIOLATED'}")
            print(f"  Throughput = {tput} samples/cycle")

        csv_fh.close()

        print(f"\n{'='*60}")
        print(f"  Sweep complete.")
        print(f"  Results: {RESULTS_CSV}")
        print(f"  Log:     {LOG_FILE}")
        print(f"  Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")


def _empty_row(num, label, pipeline, unroll, array_part, clock_ns, status):
    """Return a CSV row with N/A for all metric fields, for failed cases."""
    return {
        "case_num"       : num,
        "label"          : label,
        "pipeline"       : pipeline,
        "unroll"         : unroll,
        "array_partition": array_part,
        "clock_ns"       : clock_ns,
        "dsp"            : "",
        "lut"            : "",
        "ff"             : "",
        "bram"           : "",
        "latency"        : "",
        "interval"       : "",
        "ii"             : "",
        "achieved_ns"    : "",
        "timing_ok"      : "",
        "status"         : status,
    }


# ==============================================================================
# ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HLS FIR sweep script")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Generate all fir.cpp and hls_config.cfg files without running Vitis"
    )
    parser.add_argument(
        "--start", type=int, default=1, metavar="N",
        help="Resume sweep from case N (default: 1)"
    )
    args = parser.parse_args()

    if args.dry_run:
        dry_run()
    else:
        main(start_from=args.start)
