#include <stdio.h>
#include <stdlib.h>
#include <inttypes.h>

#define NTAPS 64
#define NSAMPLES 4096

void fir(int16_t *h, int16_t *samples_in, int16_t *samples_out) {
    int i, j;
    int16_t delay[NTAPS] = {0};
    int64_t acc;
    for (i=0; i<NSAMPLES; ++i) {
        acc = 0;

        // shift the delay line
        for (j=NTAPS-1; j>0; --j)
            delay[j] = delay[j-1];
        delay[0] = samples_in[i];
    
        // convolution
        for (j=0; j<NTAPS; ++j) 
            acc += (int32_t)h[j] * (int32_t)delay[j];

        // round & truncate
        acc = (acc + 0x4000) >> 15;
        samples_out[i] = (int16_t)acc;
    }
}

int main(int argc, char **argv) {
    FILE *f_h, *f_in, *f_out;
    if (argc < 4) {
        fprintf(stderr, "Usage: %s h.txt input.txt output.txt\n", argv[0]);
        return 1;
    }

	f_h = fopen(argv[1], "r");
    if (!f_h) {
        perror("fopen h");
        fclose(f_h);
        return 1;
    }

    int i;
    uint16_t tmp;
    int16_t h[NTAPS];
    for (i = 0; i < NTAPS; i++) {
        if (fscanf(f_h, "%" SCNx16, &tmp) != 1) {
            fprintf(stderr, "Error reading h[%d]\n", i);
            fclose(f_h);
            return 1;
        }
        h[i] = (int16_t)tmp;
    }

    f_in = fopen(argv[2], "r");
    if (!f_in) {
        perror("fopen input");
        fclose(f_in);
        return 1;
    }

    int16_t samples_in[NSAMPLES];
    for (i = 0; i < NSAMPLES; i++) {
        if (fscanf(f_in, "%" SCNx16, &tmp) != 1) {
            fprintf(stderr, "Error reading samples_in[%d]\n", i);
            fclose(f_h);
            fclose(f_in);
            return 1;
        }
        samples_in[i] = (int16_t)tmp;
    }

	fclose(f_h);
	fclose(f_in);

    int16_t samples_out[NSAMPLES] = {0};
    
    fir(h, samples_in, samples_out);
    
	f_out = fopen(argv[3], "w");
    if (!f_out) {
        perror("fopen output");
        fclose(f_out);
        return 1;
    }
	
	for (i = 0; i < NSAMPLES; i++) {
        fprintf(f_out, "%04" PRIx16 "\n", (uint16_t)samples_out[i]);
    }

	fclose(f_out);
    return 0;
}
