# run_impl.tcl — Batch Vivado implementation for selected HLS sweep cases
# Run from enee759u/ in Git Bash:
#   /d/AMDDesignTools/2025.2/Vivado/bin/vivado -mode batch -source run_impl.tcl
# Outputs:
#   results/impl_summary.csv       — DSP, LUT, FF, BRAM, WNS, Fmax per case
#   results/impl_<label>.rpt       — full timing summary per case
#   results/vivado_<label>/        — Vivado project per case

set part       "xczu5ev-fbvb900-2-i"
set results_dir "results"

# Cases: {label  clock_ns  syn_verilog_dir}
# Case 2  — representative pipelined HLS result (all unroll cases identical)
# Case 13 — architectural anomaly (44 DSPs at 1ns, suspected ~787 MHz)
# Case 18 — iterative HLS Fmax verification vs handrolled iterative RTL
set cases {
    {"case_02_pipeline_only"    5.0  "sweep/case_02_pipeline_only/hls/syn/verilog"}
    {"case_13_clk1ns"           1.0  "sweep/case_13_clk1ns/hls/syn/verilog"}
    {"case_18_iterative_ap_2ns" 2.0  "sweep/case_18_iterative_ap_2ns/hls/syn/verilog"}
}

# CSV header
file mkdir $results_dir
set csv_path "${results_dir}/impl_summary.csv"
set csv_fh [open $csv_path w]
puts $csv_fh "label,clock_ns,dsp,lut,ff,bram,wns,fmax_mhz,timing_met"
flush $csv_fh

foreach case_entry $cases {
    set label    [lindex $case_entry 0]
    set clock_ns [lindex $case_entry 1]
    set src_dir  [lindex $case_entry 2]
    set proj_dir "${results_dir}/vivado_${label}"
    set rpt_path "${results_dir}/impl_${label}.rpt"

    puts ""
    puts "============================================================"
    puts "  Implementing: ${label}"
    puts "  Clock target: ${clock_ns}ns"
    puts "  Sources:      ${src_dir}"
    puts "============================================================"

    # Verify source directory exists
    if {![file isdirectory $src_dir]} {
        puts "  ERROR: source directory not found: ${src_dir}"
        puts $csv_fh "${label},${clock_ns},ERROR,ERROR,ERROR,ERROR,ERROR,ERROR,ERROR"
        flush $csv_fh
        continue
    }

    # Collect .v and .sv source files
    set src_files [concat \
        [glob -nocomplain "${src_dir}/*.v"]  \
        [glob -nocomplain "${src_dir}/*.sv"] \
    ]

    if {[llength $src_files] == 0} {
        puts "  ERROR: no .v/.sv files found in ${src_dir}"
        puts $csv_fh "${label},${clock_ns},ERROR,ERROR,ERROR,ERROR,ERROR,ERROR,ERROR"
        flush $csv_fh
        continue
    }
    puts "  Found [llength $src_files] source files"

    # Create Vivado project
    create_project ${label} ${proj_dir} -part ${part} -force
    add_files ${src_files}
    set_property top fir [current_fileset]
    update_compile_order -fileset sources_1

    # Write XDC — HLS top-level clock port is ap_clk
    set xdc_path "${proj_dir}/${label}.xdc"
    set xdc_fh [open $xdc_path w]
    puts $xdc_fh "create_clock -period ${clock_ns} -name ap_clk \[get_ports ap_clk\]"
    close $xdc_fh
    add_files -fileset constrs_1 -norecurse ${xdc_path}

    # Synthesis with retiming enabled
    puts "  Running synthesis (retiming enabled)..."
    set_property STEPS.SYNTH_DESIGN.ARGS.RETIMING true [get_runs synth_1]
    launch_runs synth_1 -jobs 4
    wait_on_run synth_1

    if {[get_property PROGRESS [get_runs synth_1]] != "100%"} {
        puts "  ERROR: synthesis failed"
        puts $csv_fh "${label},${clock_ns},SYNTH_FAIL,,,,,,"
        flush $csv_fh
        close_project
        continue
    }

    # Implementation through route_design
    puts "  Running implementation..."
    launch_runs impl_1 -to_step route_design -jobs 4
    wait_on_run impl_1

    if {[get_property PROGRESS [get_runs impl_1]] != "100%"} {
        puts "  ERROR: implementation failed"
        puts $csv_fh "${label},${clock_ns},IMPL_FAIL,,,,,,"
        flush $csv_fh
        close_project
        continue
    }

    # Open routed design
    open_run impl_1

    # Timing summary
    report_timing_summary -file ${rpt_path}
    set timing_str [report_timing_summary -return_string]

    # Parse WNS
    set wns "?"
    if {[regexp {WNS\(ns\)\s+([-\d.]+)} $timing_str m val]} {
        set wns $val
    }

    # Compute Fmax and timing_met
    set fmax       "?"
    set timing_met "NO"
    if {$wns ne "?"} {
        set slack  [expr {double($wns)}]
        set period [expr {double($clock_ns)}]
        # Fmax = 1 / (period - slack) regardless of sign
        # If slack > 0: period - slack < period → Fmax > target
        # If slack < 0: period - slack > period → Fmax < target
        set achieved_period [expr {$period - $slack}]
        set fmax [format "%.1f" [expr {1000.0 / $achieved_period}]]
        if {$slack >= 0} { set timing_met "YES" }
    }

    # Utilization report
    report_utilization -file "${results_dir}/util_${label}.rpt"
    set util_str [report_utilization -return_string]

    set dsp  "?"
    set lut  "?"
    set ff   "?"
    set bram "?"
    if {[regexp {DSPs\s*\|\s*(\d+)}            $util_str m v]} { set dsp  $v }
    if {[regexp {Slice LUTs\s*\|\s*(\d+)}      $util_str m v]} { set lut  $v }
    if {[regexp {Slice Registers\s*\|\s*(\d+)} $util_str m v]} { set ff   $v }
    if {[regexp {Block RAM Tile\s*\|\s*(\d+)}  $util_str m v]} { set bram $v }

    puts "  RESULT:"
    puts "    DSP=${dsp}  LUT=${lut}  FF=${ff}  BRAM=${bram}"
    puts "    WNS=${wns}ns  Fmax≈${fmax}MHz  timing_met=${timing_met}"

    puts $csv_fh "${label},${clock_ns},${dsp},${lut},${ff},${bram},${wns},${fmax},${timing_met}"
    flush $csv_fh

    close_project
    puts "  Done: ${label}"
}

close $csv_fh

puts ""
puts "============================================================"
puts "  All cases complete."
puts "  Summary CSV:     ${csv_path}"
puts "  Timing reports:  ${results_dir}/impl_<label>.rpt"
puts "  Util reports:    ${results_dir}/util_<label>.rpt"
puts "  Vivado projects: ${results_dir}/vivado_<label>/"
puts "============================================================"
