import numpy as np

NTAPS = 64
NSAMPLES = 4096

np.random.seed(0)

# -------------------------
# FIR coefficients (stable low-pass)
# -------------------------
fc = 0.1
n = np.arange(NTAPS)

h = np.sinc(2 * fc * (n - (NTAPS - 1) / 2))
h *= np.hamming(NTAPS)
h /= np.sum(h)

# -------------------------
# Input signal
# pick ONE:
# -------------------------

# impulse (best debugging case)
x = np.zeros(NSAMPLES)
x[0] = 1.0

# step (uncomment if needed)
# x = np.ones(NSAMPLES)

# random (stress test)
# x = np.random.randn(NSAMPLES)

# -------------------------
# reference output
# -------------------------
y = np.convolve(x, h)[:NSAMPLES]

# -------------------------
# write files
# -------------------------
np.savetxt("h.txt", h, fmt="%.10f")
np.savetxt("in.txt", x, fmt="%.10f")
np.savetxt("expected.txt", y, fmt="%.10f")

print("Generated: h.txt, in.txt, expected.txt")
