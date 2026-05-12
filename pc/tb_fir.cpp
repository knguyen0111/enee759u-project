#include <stdio.h>
#include <stdint.h>
#include "ap_int.h"

#define NSAMPLES 4096

void fir(ap_int<16> sample_in, ap_int<16> &sample_out);

int main() {
    FILE *f_in, *f_out_ref, *f_out;
    uint16_t tmp;
    int pass = 1;
    int mismatches = 0;

    f_in = fopen("input.mem", "r");
    if (!f_in) { perror("fopen input"); return 1; }
    f_out_ref = fopen("output_15.mem", "r");
    if (!f_out_ref) { perror("fopen output_15"); return 1; }

    for (int i = 0; i < NSAMPLES; i++) {
        // read input sample
        fscanf(f_in, "%hx", &tmp);
        ap_int<16> sample_in = (int16_t)tmp;
        // debug
        //if (i < 11)
        //    printf("sample[%d] = %04x\n", i, (uint16_t)(int16_t)sample_in.val);
        // run filter
        ap_int<16> sample_out;
        fir(sample_in, sample_out);

        // read expected
        fscanf(f_out_ref, "%hx", &tmp);
        ap_int<16> expected = (int16_t)tmp;

        if (sample_out != expected) {
            printf("MISMATCH at %d: got %04x expected %04x\n",
                i, (uint16_t)sample_out.to_int(), (uint16_t)expected.to_int());
            pass = 0;
            mismatches++;
            if (mismatches > 10) break;
        }
    }

    fclose(f_in);
    fclose(f_out_ref);

    if (pass)
        printf("PASS\n");
    else
        printf("FAIL: %d mismatches\n", mismatches);

    return !pass;
}
