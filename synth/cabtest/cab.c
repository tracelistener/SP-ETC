/* Cabinet test: the cabinet (see cab.h). Runs on the audio task through cab_fp_call. */
#include "cab.h"
#include "cab_tables.h"                      /* from the builder: CAB_TW[65][2] = cos, -sin of 2 pi k / 128;
                                                CAB_REV[64] = 6-bit reversal */

typedef unsigned int u32;

/* In place, 64 points; the inverse leaves out the 1/64. W64^j = W128^(2j): the 128-point table serves both. */
static void fft64(cab_cpx *x, int inverse) {
    for (unsigned i = 0; i < 64; i++) {
        unsigned j = CAB_REV[i];
        if (i < j) {
            cab_cpx t = x[i];
            x[i] = x[j];
            x[j] = t;
        }
    }
    for (unsigned width = 2; width <= 64; width <<= 1) {
        unsigned half = width >> 1, step = 128 / width;
        for (unsigned j = 0; j < half; j++) {
            const float wr = CAB_TW[j * step][0];
            const float wi = inverse ? -CAB_TW[j * step][1] : CAB_TW[j * step][1];
            for (unsigned start = j; start < 64; start += width) {
                cab_cpx a = x[start], b = x[start + half];
                float tr = wr * b.re - wi * b.im, ti = wr * b.im + wi * b.re;
                x[start].re = a.re + tr;
                x[start].im = a.im + ti;
                x[start + half].re = a.re - tr;
                x[start + half].im = a.im - ti;
            }
        }
    }
}

/* Bins 0..64 of the 128-point FFT of 64 real samples followed by 64 zeros: the even and odd samples as one
 * 64-point complex transform, then X[k] = (Z[k] + conj Z[64-k]) / 2 - i W^k (Z[k] - conj Z[64-k]) / 2. */
static void rfft(cab_cpx *z, const float *x, cab_cpx *out) {
    for (unsigned n = 0; n < 32; n++) {
        z[n].re = x[2 * n];
        z[n].im = x[2 * n + 1];
        z[n + 32].re = z[n + 32].im = 0.0f;
    }
    fft64(z, 0);
    for (unsigned k = 0; k <= 64; k++) {
        cab_cpx a = z[k & 63], b = z[(64 - k) & 63];
        float er = 0.5f * (a.re + b.re), ei = 0.5f * (a.im - b.im);       /* (a + conj b) / 2 */
        float orr = 0.5f * (a.im + b.im), oi = -0.5f * (a.re - b.re);     /* (a - conj b) / 2i */
        float wr = CAB_TW[k][0], wi = CAB_TW[k][1];
        out[k].re = er + wr * orr - wi * oi;
        out[k].im = ei + wr * oi + wi * orr;
    }
}

/* 128 real samples from bins 0..64 (scaled by 1/64): Z[k] = Fe[k] + i Fo[k], Fe = (X[k] + conj X[64-k]) / 2,
 * Fo = (X[k] - conj X[64-k]) / 2 * conj W^k; the inverse 64-point transform; even samples from the real parts. */
static void irfft(cab_cpx *z, const cab_cpx *in, float *x) {
    for (unsigned k = 0; k < 64; k++) {
        cab_cpx a = in[k], b = in[64 - k];
        float er = 0.5f * (a.re + b.re), ei = 0.5f * (a.im - b.im);
        float dr = 0.5f * (a.re - b.re), di = 0.5f * (a.im + b.im);
        float wr = CAB_TW[k][0], wi = -CAB_TW[k][1];
        float fr = dr * wr - di * wi, fi = dr * wi + di * wr;
        z[k].re = er - fi;
        z[k].im = ei + fr;
    }
    fft64(z, 1);
    const float s = 1.0f / 64.0f;
    for (unsigned n = 0; n < 64; n++) {
        x[2 * n] = z[n].re * s;
        x[2 * n + 1] = z[n].im * s;
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
    float part[64];
    if (taps < 1 || taps > CAB_TAPS)
        return -1;
    for (unsigned n = 0; n < taps; n++)
        if (!finite(ir[n]))
            return -2;
    c->parts = (taps + 63u) / 64u;
    for (unsigned p = 0; p < c->parts; p++) {
        for (unsigned j = 0; j < 64; j++)
            part[j] = p * 64u + j < taps ? ir[p * 64u + j] : 0.0f;
        rfft(c->z, part, c->h[p]);
    }
    c->slot = 0;
    return 0;
}

void cab_process(cab_t *c, const float *in, float *out) {
    const unsigned parts = c->parts, slot = c->slot;
    cab_cpx *sum = c->sum;
    float y[128];
    rfft(c->z, in, c->x[slot]);
    for (unsigned k = 0; k < CAB_BINS; k++)
        sum[k].re = sum[k].im = 0.0f;
    for (unsigned p = 0; p < parts; p++) {
        const cab_cpx *h = c->h[p], *xp = c->x[slot >= p ? slot - p : slot + parts - p];
        for (unsigned k = 0; k < CAB_BINS; k++) {
            sum[k].re += h[k].re * xp[k].re - h[k].im * xp[k].im;
            sum[k].im += h[k].re * xp[k].im + h[k].im * xp[k].re;
        }
    }
    irfft(c->z, sum, y);
    for (unsigned i = 0; i < 64; i++) {
        out[i] = y[i] + c->overlap[i];
        c->overlap[i] = y[i + 64];
    }
    c->slot = slot + 1 == parts ? 0 : slot + 1;
}
