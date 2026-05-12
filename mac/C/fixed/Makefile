# Makefile for fixed-point FIR reference
# Usage:
#   make          — compile, run, and verify against golden reference
#   make build    — compile fir.c -> fir
#   make run      — run fir, produce output.txt
#   make check    — diff output.txt against golden reference
#   make clean    — remove binary and output

CC     = gcc
CFLAGS = -Wall -O2
TARGET = fir
SRC    = fir.c
H      = ../../io/taps.mem
INPUT  = ../../io/input.mem
GOLDEN = ../../io/output_15.mem

.PHONY: all build run check clean

all: build run check

build: $(TARGET)

$(TARGET): $(SRC)
	$(CC) $(CFLAGS) -o $(TARGET) $(SRC)

run: $(TARGET)
	./$(TARGET) $(H) $(INPUT) output.txt

check:
	diff output.txt $(GOLDEN) && echo "PASS" || echo "FAIL"

clean:
	rm -f $(TARGET) output.txt
