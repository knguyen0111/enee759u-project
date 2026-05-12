# Makefile for HLS C++ functional simulation (test.cpp)
# Uses Xilinx ap_int.h header — runs on any platform (no Vitis needed)
#
# Usage:
#   make          — compile and run functional simulation
#   make build    — compile test.cpp + tb_fir.cpp -> sim
#   make run      — run simulation (prints PASS or FAIL)
#   make clean    — remove binary
#
# Note: fir.cpp uses ap_int<> types and is compiled by Vitis HLS (PC only).
#       test.cpp is the platform-independent functional reference.

CXX      = g++
CXXFLAGS = -std=c++14 -Wall -O2 -I include/
TARGET   = fir
SRCS     = test.cpp tb_fir.cpp

.PHONY: all build run clean

all: build run

build: $(TARGET)

$(TARGET): $(SRCS)
	$(CXX) $(CXXFLAGS) -o $(TARGET) $(SRCS)

run: $(TARGET)
	./$(TARGET)

clean:
	rm -f $(TARGET)
