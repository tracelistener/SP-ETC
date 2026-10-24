/* NAM test 1: the cabinet (see cab.h). Runs on the audio task through nam_fp_call. */
#include "cab.h"
#include "cab_tables.h"                      /* from the builder: CAB_TW[64][2] = cos, -sin of 2 pi k / 128 */

typedef unsigned int u32;

/* In place; the inverse leaves out the 1/128 (cab_process applies it). */
static void fft128(cab_cpx *x, int inverse) {
    for (unsigned i = 1, j = 0; i < 128; i++) {
        unsigned bit = 64;
        while (j & bit) {
            j ^= bit;
            bit >>= 1;
        }
        j ^= bit;
        if (i < j) {
            cab_cpx t = x[i];
            x[i] = x[j];
            x[j] = t;
        }
    }
    for (unsigned width = 2; width <= 128; width <<= 1) {
        unsigned half = width >> 1, step = 128 / width;
        for (unsigned start = 0; start < 128; start += width) {
            for (unsigned j = 0; j < half; j++) {
                const float wr = CAB_TW[j * step][0];
                const float wi = inverse ? -CAB_TW[j * step][1] : CAB_TW[j * step][1];
                cab_cpx a = x[start + j], b = x[start + j + half];
                float tr = wr * b.re - wi * b.im, ti = wr * b.im + wi * b.re;
                x[start + j].re = a.re + tr;
                x[start + j].im = a.im + ti;
                x[start + j + half].re = a.re - tr;
                x[start + j + half].im = a.im - ti;
            }
        }
    }
}

static int finite(float v) {
    union {
        float f;
        u32 u;
    } c = {v};
    return (c.u & 0x7F800000u) != 0x7F800000u;
}

int cab_prepare(cab_t *c, const float *ir, unsigned taps) {
    if (taps < 1 || taps > CAB_TAPS)
        return -1;
    for (unsigned n = 0; n < taps; n++)
        if (!finite(ir[n]))
            return -2;
    c->parts = (taps + 63u) / 64u;
    for (unsigned p = 0; p < c->parts; p++) {
        for (unsigned j = 0; j < 128; j++) {
            unsigned n = p * 64u + j;
            c->h[p][j].re = j < 64 && n < taps ? ir[n] : 0.0f;
            c->h[p][j].im = 0.0f;
        }
        fft128(c->h[p], 0);
    }
    c->slot = 0;
    return 0;
}

void cab_process(cab_t *c, const float *in, float *out) {
    const unsigned parts = c->parts, slot = c->slot;
    cab_cpx *x = c->x[slot], *sum = c->sum;
    for (unsigned i = 0; i < 64; i++) {
        x[i].re = in[i];
        x[i].im = 0.0f;
        x[i + 64].re = 0.0f;
        x[i + 64].im = 0.0f;
    }
    fft128(x, 0);
    for (unsigned k = 0; k < 128; k++)
        sum[k].re = sum[k].im = 0.0f;
    for (unsigned p = 0; p < parts; p++) {
        const cab_cpx *h = c->h[p], *xp = c->x[slot >= p ? slot - p : slot + parts - p];
        for (unsigned k = 0; k < 128; k++) {
            sum[k].re += h[k].re * xp[k].re - h[k].im * xp[k].im;
            sum[k].im += h[k].re * xp[k].im + h[k].im * xp[k].re;
        }
    }
    fft128(sum, 1);
    const float s = 1.0f / 128.0f;
    for (unsigned i = 0; i < 64; i++) {
        out[i] = sum[i].re * s + c->overlap[i];
        c->overlap[i] = sum[i + 64].re * s;
    }
    c->slot = slot + 1 == parts ? 0 : slot + 1;
}
