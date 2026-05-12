import numpy as np

NSAMPLES = 4096

# load files
out = np.loadtxt("out.txt")
expected = np.loadtxt("expected.txt")

# sanity check
if len(out) != NSAMPLES:
    raise ValueError(f"Output size mismatch: got {len(out)}")

# error metrics
abs_err = np.abs(out - expected)

print("Max abs error :", np.max(abs_err))
print("Mean abs error:", np.mean(abs_err))

# tolerance check (float32-level DSP tolerance)
tol = 1e-5
bad = np.where(abs_err > tol)[0]

if len(bad) == 0:
    print("PASS: outputs match within tolerance")
else:
    print(f"FAIL: {len(bad)} mismatches")
    print("First 10 bad indices:", bad[:10])
