#include "ap_int.h"
#include "../../taps_init.h"
#define NTAPS 64

void fir(ap_int<16> sample_in, ap_int<16> &sample_out) {
    #pragma HLS PIPELINE II=1

    static ap_int<16> shift[NTAPS];

    #pragma HLS ARRAY_PARTITION variable=shift complete
    #pragma HLS ARRAY_PARTITION variable=h complete

    ap_int<40> acc = 0;

    for (int i = NTAPS-1; i > 0; --i) {
        shift[i] = shift[i-1];
    }
    shift[0] = sample_in;

    for (int i = 0; i < NTAPS; ++i) {
        #pragma HLS UNROLL factor=2
        acc += (ap_int<32>)h[i] * (ap_int<32>)shift[i];
    }

    sample_out = (ap_int<16>)((acc + 0x4000) >> 15);
}
