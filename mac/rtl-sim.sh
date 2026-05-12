#!/bin/bash
clear
if [ "$1" == "iterative" ]; then
    iverilog -g2012 -o rtl-out src/iterative.sv sim/iterative_tb.sv && ./rtl-out
elif [ "$1" == "parallel" ]; then
    iverilog -g2012 -o rtl-out src/parallel.sv sim/parallel_tb.sv && ./rtl-out
else
    echo "Usage: ./run.sh [iterative/parallel]"
fi
