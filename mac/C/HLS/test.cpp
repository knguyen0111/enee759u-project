#include "ap_int.h"     // provided by AMD for precise signed int
//#include <ap_fixed.h>
#define NTAPS 64
#include "taps_init.h"

// debug
//#include <stdio.h>

void fir(ap_int<16> sample_in, ap_int<16> &sample_out) {
    static ap_int<16> shift[NTAPS];  // static local array -> registers
    ap_int<40> acc = 0;
    
    // debug
    //for (int i = 0; i < 4; i++)
    //    printf("h[%d] = %lld\n", i, h[i].val);

    // shift delay line 
    for (int i = NTAPS-1; i > 0; --i)
        shift[i] = shift[i-1];
    shift[0] = sample_in;

    // MAC
    for (int i = 0; i < NTAPS; ++i)
        acc += h[i].val * shift[i].val;

    // round and truncate to Q1.15
    sample_out = ((acc.val + 0x4000) >> 15);
}
