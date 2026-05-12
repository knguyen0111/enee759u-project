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
