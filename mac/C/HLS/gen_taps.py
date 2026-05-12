with open("../../io/taps.mem") as f:
    vals = [int(line.strip(), 16) for line in f if line.strip()]

print("static const ap_int<16> h[NTAPS] = {")
entries = []
for v in vals:
    signed = v if v < 0x8000 else v - 0x10000
    entries.append(f"    {signed}")
print(",\n".join(entries))
print("};")
