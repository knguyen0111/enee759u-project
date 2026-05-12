# Makefile for floating-point FIR reference
# Usage:
#   make          — generate inputs, compile, run, compare
#   make gen      — generate h.txt, in.txt, expected.txt
#   make build    — compile fir.c → fir
#   make run      — run fir, produce out.txt
#   make check    — compare out.txt against expected.txt
#   make clean    — remove binary and generated files

CC      = gcc
CFLAGS  = -Wall -O2
TARGET  = fir
SRC     = fir.c
GEN     = gen.py
COMP    = comp.py

.PHONY: all gen build run check clean

all: gen build run check

gen:
	python3 $(GEN)

build: $(TARGET)

$(TARGET): $(SRC)
	$(CC) $(CFLAGS) -o $(TARGET) $(SRC)

run: $(TARGET)
	./$(TARGET) h.txt  in.txt out.txt

check:
	python3 $(COMP)

clean:
	rm -f $(TARGET) h.txt in.txt expected.txt out.txt
