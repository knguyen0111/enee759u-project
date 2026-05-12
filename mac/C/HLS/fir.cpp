#include "ap_int.h"     // provided by AMD for precise signed int
//#include <ap_fixed.h>
#define NTAPS 64
#include "taps_init.h"


void fir(ap_int<16> sample_in, ap_int<16> &sample_out) {
    static ap_int<16> shift[NTAPS];  // static local array -> registers
    ap_int<40> acc = 0;
    
    // shift delay line 
    for (int i = NTAPS-1; i > 0; --i)
        shift[i] = shift[i-1];
    shift[0] = sample_in;

    // MAC
    for (int i = 0; i < NTAPS; ++i)
        acc += (ap_int<32>)h[i] * (ap_int<32>)shift[i];

    // round and truncate to Q1.15
    sample_out = (ap_int<16>)((acc + 0x4000) >> 15);
}
