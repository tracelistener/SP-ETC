"""SY synth test 11: the tones of the voice-per-note engine (sy_voice.c), their C table, and a host build of the engine
(the same C, built for this computer with the Sound Generator's own wave code) for renders and checks.

A tone is a dict in the prototype's terms (times in ms, levels, cents); patch() turns it into syv_patch_t's fields
(coefficients per sample at 48 kHz). c_header() writes syv_tables.h: the bands' centre pitches, the Sound Generator's
ENV presets (env_presets.h's values), the tones and their names."""
import ctypes
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SYNTH = HERE.parent
sys.path.insert(0, str(HERE))
import sy_ref as ref  # noqa: E402

FS = 48000.0
NV = 8
# env_presets.h (v9): ra rd sus rr, fra frd fsus frr, base amount k drive gain, filter
PRESETS = [
    [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 2.0, 1.0, 1.0, 0],
    [0.984845175, 0.999520393, 0.0, 0.999280676, 1.0, 1.0, 0.0, 1.0, 0.0, 0.0, 2.0, 1.0, 1.0, 0],
    [0.984845175, 0.999880077, 0.0, 0.999760168, 1.0, 1.0, 0.0, 1.0, 0.0, 0.0, 2.0, 1.0, 1.0, 0],
    [0.993910285, 0.999910056, 0.45, 0.999640273, 1.0, 1.0, 0.0, 1.0, 0.0, 0.0, 2.0, 1.0, 1.0, 0],
    [0.999912742, 0.999760168, 1.0, 0.999897208, 1.0, 1.0, 0.0, 1.0, 0.0, 0.0, 2.0, 1.0, 1.0, 0],
    [0.999980912, 0.999760168, 1.0, 0.999934585, 1.0, 1.0, 0.0, 1.0, 0.0, 0.0, 2.0, 1.0, 1.0, 0],
    [0.984845175, 0.99982012, 0.65, 0.998801413, 0.984845175, 0.999588894, 0.0, 0.998801413, 0.8, 4.2, 1.1, 1.0, 1.15, 1],
    [0.984845175, 0.999280676, 0.9, 0.997125805, 0.984845175, 0.999520393, 0.0, 0.997125805, 0.4, 5.6, 0.22, 1.5, 0.85, 1],
    [0.996950493, 0.999712208, 1.0, 0.99982012, 0.999989092, 0.99990406, 1.0, 0.99982012, -0.8, 6.5, 0.55, 1.0, 1.1, 1],
    [0.999932132, 0.99982012, 1.0, 0.999910056, 0.999978185, 0.999942435, 0.45, 0.999910056, 0.3, 3.6, 0.9, 1.0, 1.15, 1],
]
SAW, PULSE, TRI, SINE, SUPERSAW, SG, FM = 1, 2, 3, 4, 5, 6, 7
LP12, BP12, HP12, LP24, LP18, SGF = 1, 2, 3, 4, 5, 6
# P2 (CTRL 1 on the screen): what it moves, from -1 (knob 0) to +1 (knob 127), 0 as designed
P_RESO, P_ENV, P_ATTACK, P_DETUNE, P_GLIDE, P_DUTY, P_DRIVE, P_RATE, P_MIX, P_FM, P_ENVSEL = range(1, 12)
P2_NAMES = {P_RESO: 'RESO', P_ENV: 'ENV', P_ATTACK: 'ATTACK', P_DETUNE: 'DETUNE', P_GLIDE: 'GLIDE', P_DUTY: 'DUTY',
            P_DRIVE: 'DRIVE', P_RATE: 'RATE', P_MIX: 'MIX', P_FM: 'FM', P_ENVSEL: 'ENV'}
PRESET_NAMES = ['OFF', 'Pluck', 'Perc', 'Keys', 'Pad', 'Swell', 'Bass', 'Acid', 'Sweep', 'FPad']

DEFAULTS = dict(
    o1=SAW, o1_semi=0.0, o1_cent=0.0, o1_lev=1.0, o1_pw=0.5, o1_wave=6, o1_duty=0.5,
    o2=0, o2_semi=0.0, o2_cent=0.0, o2_lev=0.0, o2_pw=0.5, o2_wave=6, o2_duty=0.5, o2_sync=0, o2_penv=0.0,
    o3=0, o3_semi=0.0, o3_cent=0.0, o3_lev=0.0, o3_pw=0.5, o3_wave=6, o3_duty=0.5,
    sub=0.0, noise=0.0, ring=0.0, uni_spread=0.5, uni_mix=0.8,
    fm_ratio=1.0, fm_index=0.0, fm_floor=0.0, fm_decay=500.0, fm2_ratio=14.0, fm2_index=0.0, fm2_decay=50.0,
    flt=LP12, cut=2000.0, keytrk=0.5, reso=0.1, fenv=0.0, fvel=0.0, drive=1.0,
    fa=1.0, fd=300.0, fs=0.5, fr=300.0, aa=2.0, ad=300.0, as_=1.0, ar=200.0, avel=0.6, follow=0.0,
    lfo_rate=5.0, lfo_delay=0.0, lfo_pitch=0.0, lfo_cut=0.0, lfo_pw=0.0, lfo_amp=0.0, lfo_vec=0.0,
    mono=0, glide=0.0, retrig=1, sg_preset=0, chorus=0, gain=1.0, oct=0, p2=P_RESO,
)

# The tones (sy-voice-demos1's 20, as the user heard them; gains levelled by level_voices()).
VOICES = [
    dict(name='POLY PAD', about='Juno-style pad: saw, pulse with slow PWM and a sub, smooth 24 dB filter, chorus II',
         o1=SAW, o1_lev=0.8, o2=PULSE, o2_lev=0.6, lfo_pw=0.25, lfo_rate=0.45, sub=0.35, flt=LP24, cut=900,
         keytrk=0.5, reso=0.15, fenv=1.5, fa=400, fd=1200, fs=0.4, fr=900, aa=350, ad=600, as_=0.9, ar=1000, avel=0.3,
         chorus=2, p2=P_ATTACK),
    dict(name='STRINGS', about='string machine: two detuned saws, gentle 12 dB filter, delayed vibrato, ensemble',
         o1=SAW, o2=SAW, o2_cent=9, o2_lev=0.8, flt=LP12, cut=2600, keytrk=0.6, reso=0.05, aa=220, ad=400, as_=1.0,
         ar=700, lfo_rate=5.2, lfo_delay=350, lfo_pitch=7, chorus=3, avel=0.3, p2=P_ATTACK),
    dict(name='POLY BRASS', about='Jupiter / Prophet-style brass: two detuned saws, a 24 dB filter blooming on each note',
         o1=SAW, o2=SAW, o2_cent=-8, o2_lev=0.9, flt=LP24, cut=450, keytrk=0.6, reso=0.18, fenv=3.0, fa=70, fd=500,
         fs=0.45, fr=300, aa=40, ad=300, as_=0.85, ar=250, fvel=0.5, chorus=1, p2=P_ENV),
    dict(name='ENSEMBLE', about='Polysix-style poly: saw and sub, 24 dB filter with a short pluck, ensemble',
         o1=SAW, sub=0.4, flt=LP24, cut=1500, keytrk=0.5, reso=0.12, fenv=1.2, fa=3, fd=700, fs=0.35, aa=3, ad=900,
         as_=0.75, ar=450, chorus=3, p2=P_ENV),
    dict(name='POLY KEYS', about='Poly-800-style keys: narrow pulse and a saw an octave up, plucky filter, chorus I',
         o1=PULSE, o1_pw=0.25, o2=SAW, o2_semi=12, o2_lev=0.5, flt=LP24, cut=1400, keytrk=0.6, reso=0.1, fenv=2.0,
         fa=2, fd=450, fs=0.2, fr=300, aa=2, ad=1100, as_=0.35, ar=350, chorus=1, p2=P_ENV),
    dict(name='VECTOR PAD', about='Wavestation-style pad: the SG FM1:2 and Table waves crossfading over a sine',
         o1=SINE, o1_lev=0.3, o2=SG, o2_wave=16, o2_duty=0.4, o2_lev=0.9, o3=SG, o3_wave=28, o3_duty=0.7, o3_lev=0.9,
         lfo_vec=1.0, lfo_rate=0.15, flt=LP12, cut=5000, keytrk=0.3, aa=700, ad=800, as_=1.0, ar=1600, chorus=3,
         half=1, voices=3, p2=P_RATE),
    dict(name='SYNC LEAD', about='Mono/Poly / MS-20-style lead: a hard-synced saw swept down on each pick, glide',
         o1=SAW, o1_lev=0.0, o2=SAW, o2_lev=1.0, o2_sync=1, o2_semi=7, o2_penv=14, flt=LP12, cut=6000, keytrk=0.3,
         reso=0.2, fa=1, fd=350, fs=0.0, aa=2, ad=300, as_=1.0, ar=150, mono=1, glide=35, retrig=1, lfo_rate=5.5,
         lfo_delay=500, lfo_pitch=10, p2=P_ENV),
    dict(name='LADDER LEAD', about='Minimoog-style lead: three saws (one an octave down), driven ladder, glide, vibrato',
         o1=SAW, o2=SAW, o2_cent=6, o2_lev=0.9, o3=SAW, o3_semi=-12, o3_lev=0.6, flt=LP24, cut=800, keytrk=0.8,
         reso=0.38, fenv=2.4, fa=4, fd=450, fs=0.5, fr=200, aa=3, ad=200, as_=0.95, ar=220, mono=1, glide=60, retrig=1,
         lfo_rate=5.3, lfo_delay=450, lfo_pitch=14, drive=1.8, p2=P_GLIDE),
    dict(name='FAT BASS', about='Moog-style bass: saw and a pulse an octave down, driven ladder, quick filter decay',
         o1=SAW, o2=PULSE, o2_semi=-12, o2_lev=0.7, flt=LP24, cut=300, keytrk=0.4, reso=0.22, fenv=3.2, fa=1, fd=280,
         fs=0.15, fr=120, aa=1, ad=500, as_=0.8, ar=110, mono=1, drive=2.2, p2=P_ENV),
    dict(name='ACID BASS', about='303-style bass: saw through a squelchy resonant 18 dB filter, accent, slides',
         o1=SAW, flt=LP18, cut=260, keytrk=0.5, reso=0.88, fenv=4.0, fvel=0.6, fa=0.5, fd=230, fs=0.0, fr=80, aa=1,
         ad=1500, as_=0.85, ar=45, mono=1, glide=70, retrig=0, drive=2.5, p2=P_RESO),
    dict(name='PUNCH BASS', about='SH-101-style bass: pulse and sub, a short filter snap', o1=PULSE, o1_pw=0.4,
         sub=0.6, flt=LP24, cut=500, keytrk=0.5, reso=0.15, fenv=2.4, fa=1, fd=190, fs=0.15, aa=1, ad=350, as_=0.65,
         ar=90, mono=1, p2=P_ENV),
    dict(name='SUPERSAW', about='JP-8000 / Virus-style supersaw: seven detuned saws, wide chorus', o1=SUPERSAW,
         uni_spread=0.55, uni_mix=0.75, flt=LP12, cut=7000, keytrk=0.2, reso=0.05, aa=12, ad=900, as_=0.9, ar=500,
         chorus=4, voices=3, p2=P_DETUNE),
    dict(name='FM PIANO', about='DX7-style electric piano: FM with a bright tine on the attack, piano-like decay',
         o1=FM, fm_ratio=1.0, fm_index=1.6, fm_floor=0.25, fm_decay=700, fm2_ratio=14.0, fm2_index=0.35,
         fm2_decay=40, flt=0, aa=1, ad=2600, as_=0.0, ar=350, avel=0.8, chorus=1, p2=P_FM),
    dict(name='FM BELL', about='FM bell an octave up: inharmonic ratio, long ring', o1=FM, fm_ratio=3.5,
         fm_index=2.6, fm_floor=0.05, fm_decay=1100, flt=0, aa=1, ad=3500, as_=0.0, ar=1800, chorus=4, oct=1, p2=P_FM),
    dict(name='SG ACID', about='the Sound Generator exactly: Saw with ENV Acid', o1=SG, o1_wave=6, flt=SGF,
         sg_preset=7, p2=P_ENVSEL),
    dict(name='SG VOWEL', about='the Sound Generator exactly: Vowel (DUTY 40) with ENV FPad', o1=SG, o1_wave=27,
         o1_duty=0.4, flt=SGF, sg_preset=9, voices=3, p2=P_ENVSEL),
    dict(name='SG ORGAN', about='the Sound Generator exactly: Organ (DUTY 75) with ENV OFF', o1=SG, o1_wave=26,
         o1_duty=0.75, flt=SGF, sg_preset=0, voices=4, p2=P_ENVSEL),
    dict(name='SG CZ KEYS', about='the Sound Generator exactly: CZSaw (DUTY 60) with ENV Keys', o1=SG, o1_wave=18,
         o1_duty=0.6, flt=SGF, sg_preset=3, p2=P_ENVSEL),
    dict(name='SG PLUCK', about='the Sound Generator exactly: Pulse (DUTY 30) with ENV Pluck', o1=SG,
         o1_wave=11, o1_duty=0.3, flt=SGF, sg_preset=1, p2=P_ENVSEL),
    dict(name='SG FM BELL', about='the Sound Generator exactly: FM1:7 (DUTY 60) with ENV Perc', o1=SG, o1_wave=17,
         o1_duty=0.6, flt=SGF, sg_preset=2, p2=P_ENVSEL),
]
NTONES = len(VOICES)


def _att(ms):
    return 1.0 - math.exp(-1.466 / (max(ms, 0.05) * 0.001 * FS))


def _dec(ms):
    return math.exp(-4.6 / (max(ms, 0.05) * 0.001 * FS))


def patch(t, gain=1.0):
    """A tone as syv_patch_t's fields (name -> value or list)."""
    v = dict(DEFAULTS)
    v.update(t)
    ratio = [2 ** ((v[f'o{i}_semi'] + v[f'o{i}_cent'] / 100.0) / 12.0) for i in (1, 2, 3)]
    return dict(
        kind=[v['o1'], v['o2'], v['o3']], wave=[v['o1_wave'], v['o2_wave'], v['o3_wave']], flt=v['flt'],
        preset=v['sg_preset'], mono=v['mono'], retrig=v['retrig'], chorus=v['chorus'], sync=v['o2_sync'],
        p2kind=v['p2'], flags=v.get('voices', 0) | (0x80 if v.get('half') else 0), ratio=ratio, lev=[v['o1_lev'], v['o2_lev'], v['o3_lev']],
        pw=[v['o1_pw'], v['o2_pw'], v['o3_pw']], duty=[v['o1_duty'], v['o2_duty'], v['o3_duty']],
        penv=v['o2_penv'], sub=v['sub'], noise=v['noise'], ring=v['ring'], spread=v['uni_spread'], mix=v['uni_mix'],
        fm_ratio=v['fm_ratio'], fm_index=v['fm_index'], fm_floor=v['fm_floor'],
        fm_dk=math.exp(-1.0 / (max(v['fm_decay'], 1.0) * 0.001 * FS)), fm2_ratio=v['fm2_ratio'],
        fm2_index=v['fm2_index'], fm2_dk=math.exp(-1.0 / (max(v['fm2_decay'], 1.0) * 0.001 * FS)),
        cut=v['cut'], keytrk=v['keytrk'], reso=v['reso'], fenv=v['fenv'], fvel=v['fvel'], drive=v['drive'],
        fa=_att(v['fa']), fd=_dec(v['fd']), fsus=v['fs'], fr=_dec(v['fr']),
        aa=_att(v['aa']), ad=_dec(v['ad']), asus=v['as_'], ar=_dec(v['ar']), avel=v['avel'], follow=v['follow'],
        lfo_inc=v['lfo_rate'] / FS, lfo_dk=1.0 / (max(v['lfo_delay'], 1.0) * 0.001 * FS),
        lfo_pitch=2 ** (v['lfo_pitch'] / 1200.0) - 1.0, lfo_cut=v['lfo_cut'], lfo_pw=v['lfo_pw'],
        lfo_amp=v['lfo_amp'], lfo_vec=v['lfo_vec'],
        glide=0.0 if v['glide'] <= 0 else math.exp(-1.0 / (v['glide'] * 0.001 * FS / 2.3)),
        gain=v['gain'] * gain, octm=2.0 ** v['oct'], p2base=0.0, p2span=0.0)


FIELDS = ['kind', 'wave', 'flt', 'preset', 'mono', 'retrig', 'chorus', 'sync', 'p2kind', 'flags', 'ratio', 'lev', 'pw',
          'duty', 'penv', 'sub', 'noise', 'ring', 'spread', 'mix', 'fm_ratio', 'fm_index', 'fm_floor', 'fm_dk',
          'fm2_ratio', 'fm2_index', 'fm2_dk', 'cut', 'keytrk', 'reso', 'fenv', 'fvel', 'drive', 'fa', 'fd', 'fsus',
          'fr', 'aa', 'ad', 'asus', 'ar', 'avel', 'follow', 'lfo_inc', 'lfo_dk', 'lfo_pitch', 'lfo_cut', 'lfo_pw',
          'lfo_amp', 'lfo_vec', 'glide', 'gain', 'octm', 'p2base', 'p2span']
U8 = {'kind', 'wave', 'flt', 'preset', 'mono', 'retrig', 'chorus', 'sync', 'p2kind', 'flags'}


def _cf(x):
    x = float(np.float32(x))
    return f'{x!r}f' if math.isfinite(x) else '0.0f'


def c_patch(p):
    out = []
    for k in FIELDS:
        v = p[k]
        if isinstance(v, list):
            out.append(f'.{k} = {{' + ', '.join(str(int(a)) if k in U8 else _cf(a) for a in v) + '}')
        else:
            out.append(f'.{k} = ' + (str(int(v)) if k in U8 else _cf(v)))
    return '{' + ', '.join(out) + '}'


def centres():
    return [1200 * math.log2(12000.0 / float(pc) / 440.0) for pc in ref.BAND['pc']]


def c_header(gains=None):
    gains = gains or VOICE_GAINS
    h = '/* Generated by sy_voices.py (SY synth test 11): band centres, the SG ENV presets, the tones. */\n'
    h += '#define SYV_PRESETS 10\n#define SYV_TONES %d\n#define SYV_VREF %sf\n' % (len(VOICES), repr(float(np.float32(VREF))))
    h += 'static const float SYV_CENTRE[49] = {' + ', '.join(_cf(c) for c in centres()) + '};\n'
    h += 'static const float SYV_PRESET[10][14] = {\n' + ',\n'.join(
        '{' + ', '.join(_cf(x) for x in row) + '}' for row in PRESETS) + '};\n'
    h += 'static const syv_patch_t SYV_TONE[%d] = {\n' % len(VOICES)
    h += ',\n'.join(c_patch(patch(t, g)) for t, g in zip(VOICES, gains)) + '\n};\n'
    return h


def c_names():
    """For the screen: the tones' names (16 bytes each), their CTRL 1 setting's name and kind, each one's designed
    DYNAMICS (0..100), the ENV presets' names."""
    h = '/* Generated by sy_voices.py (SY synth test 11): the names on the screen. */\n'
    h += '#define SYV_NTONES %d\n#define SY_OFF_PAD 15u\n#define SY_OCT_ZERO 3u\n#define SY_OCTAVES 5u\n' % len(VOICES)
    h += '#define SYV_P_ENVSEL %d\n' % P_ENVSEL
    h += 'static const char SYV_NAME[%d][16] = {' % len(VOICES)
    h += ', '.join('"%s"' % t['name'] for t in VOICES) + '};\n'
    h += 'static const char SYV_P2NAME[%d][8] = {' % len(VOICES)
    h += ', '.join('"%s"' % P2_NAMES[t.get('p2', P_RESO)] for t in VOICES) + '};\n'
    h += 'static const unsigned char SYV_P2KIND[%d] = {' % len(VOICES)
    h += ', '.join(str(t.get('p2', P_RESO)) for t in VOICES) + '};\n'
    h += 'static const unsigned char SYV_DYN_DESIGN[%d] = {' % len(VOICES)
    h += ', '.join(str(int(round(100 * dict(DEFAULTS, **t)['avel']))) for t in VOICES) + '};\n'
    h += 'static const unsigned char SYV_PRESET_OF[%d] = {' % len(VOICES)
    h += ', '.join(str(dict(DEFAULTS, **t)['sg_preset']) for t in VOICES) + '};\n'
    h += 'static const char SYV_PRESET_NAME[10][6] = {' + ', '.join('"%s"' % n for n in PRESET_NAMES) + '};\n'
    return h


# ---- the host build ----

class _Patch(ctypes.Structure):
    _fields_ = ([('kind', ctypes.c_uint8 * 3), ('wave', ctypes.c_uint8 * 3)] +
                [(n, ctypes.c_uint8) for n in ('flt', 'preset', 'mono', 'retrig', 'chorus', 'sync', 'p2kind', 'flags')] +
                [('pad', ctypes.c_uint8 * 2)] +
                [(n, ctypes.c_float * 3) for n in ('ratio', 'lev', 'pw', 'duty')] +
                [(n, ctypes.c_float) for n in FIELDS[14:]])


def to_struct(p):
    s = _Patch()
    for k in FIELDS:
        v = p[k]
        if isinstance(v, list):
            arr = getattr(s, k)
            for i, a in enumerate(v):
                arr[i] = a
        else:
            setattr(s, k, v)
    return s


def build_host(out_dir, zig, gains=None):
    """The engine as a DLL (x86-64, FTZ/DAZ as the module's FPSCR, no fused operations), with the firmware's wave
    code (waves_v8_ram/waves.c, the v9 Sound Generator's) for types 15-31."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'syv_tables.h').write_text(c_header(gains), encoding='ascii', newline='\n')
    shim = out / 'syv_host.c'
    shim.write_text(f'''#define SYV_HOST 1
#include <xmmintrin.h>
#include "{(HERE / 'sy_voice.c').as_posix()}"
__declspec(dllexport) float syv_block_host(syv_state_t *s, const syv_patch_t *p, const syv_knobs_t *k,
                                           const float *tg, const float *per, const float *e,
                                           const unsigned char *nper, float vref, float mg, float mgt, float fade,
                                           float scale, int *out) {{
    unsigned int old = _mm_getcsr();
    _mm_setcsr((old & ~0x6000u) | 0x8040u);
    float r = syv_block(s, p, k, tg, per, e, nper, vref, mg, mgt, fade, scale, out);
    _mm_setcsr(old);
    return r;
}}
__declspec(dllexport) void syv_reset_host(syv_state_t *s) {{ syv_reset(s); }}
__declspec(dllexport) unsigned syv_state_bytes(void) {{ return sizeof(syv_state_t); }}
__declspec(dllexport) unsigned syv_patch_bytes(void) {{ return sizeof(syv_patch_t); }}
__declspec(dllexport) const syv_patch_t *syv_tone(unsigned i) {{ return &SYV_TONE[i]; }}
__declspec(dllexport) unsigned syv_cost(const syv_state_t *s) {{ return s->cost; }}
''', encoding='ascii', newline='\n')
    waves = SYNTH / 'ram' / 'waves_v8_ram'
    dll = out / 'syv_host.dll'
    subprocess.run([str(zig), 'cc', '-target', 'x86_64-windows-gnu', '-shared', '-O2', '-ffp-contract=off',
                    '-fno-fast-math', '-DWAVE_HOST', '-I', str(out), '-I', str(HERE), '-I', str(waves),
                    str(shim), str(waves / 'waves.c'), '-o', str(dll)], check=True)
    return dll


class _Knobs(ctypes.Structure):
    _fields_ = [('tone', ctypes.c_int8), ('p2', ctypes.c_int8), ('level', ctypes.c_int8), ('oct', ctypes.c_uint8),
                ('sus', ctypes.c_uint8), ('dyn', ctypes.c_uint8), ('wait', ctypes.c_uint8), ('sens', ctypes.c_uint8),
                ('guard', ctypes.c_uint8), ('pad', ctypes.c_uint8 * 3)]   # SY test 15: the TRACK page


_DLLS = {}


class Host:
    """The host engine: one state, block by block (the module's numbers: the same C)."""
    def __init__(self, dll):
        if str(dll) not in _DLLS:
            lib = ctypes.CDLL(str(dll))
            lib.syv_block_host.restype = ctypes.c_float
            lib.syv_tone.restype = ctypes.POINTER(_Patch)
            if lib.syv_patch_bytes() != ctypes.sizeof(_Patch):
                raise ValueError(f'syv_patch_t {lib.syv_patch_bytes()} bytes, ctypes {ctypes.sizeof(_Patch)}')
            _DLLS[str(dll)] = lib
        self.lib = _DLLS[str(dll)]
        self.state = ctypes.create_string_buffer(self.lib.syv_state_bytes())
        self.out = (ctypes.c_int32 * 64)()
        self.knobs = _Knobs()

    def reset(self):
        ctypes.memset(self.state, 0, len(self.state))

    def tone(self, i):
        return self.lib.syv_tone(i)

    def set_knobs(self, tone=0, p2=0, level=0, oct=0, sus=0, dyn=0, wait=0, sens=0, guard=0):
        self.knobs.tone, self.knobs.p2, self.knobs.level = tone, p2, level
        self.knobs.oct, self.knobs.sus, self.knobs.dyn = oct, sus, dyn
        self.knobs.wait, self.knobs.sens, self.knobs.guard = wait, sens, guard   # SY test 15: the TRACK page

    def block(self, tone_index, tg, per, e, nper, vref=None, mg=1.0, mgt=1.0, fade=1.0, scale=1.0):
        """One block from the bands' levels, periods (12 kHz samples), energies and periods counted since each woke
        (SY test 12): (64 ints, the fade after it)."""
        a = (ctypes.c_float * 49)(*map(float, tg))
        f = (ctypes.c_float * 49)(*map(float, per))
        g = (ctypes.c_float * 49)(*map(float, e))
        n8 = (ctypes.c_uint8 * 49)(*[min(int(v), 255) for v in nper])
        mg = self.lib.syv_block_host(self.state, self.tone(tone_index), ctypes.byref(self.knobs), a, f, g, n8,
                                     ctypes.c_float(VREF if vref is None else vref), ctypes.c_float(mg),
                                     ctypes.c_float(mgt), ctypes.c_float(fade), ctypes.c_float(scale), self.out)
        return list(self.out), mg

    def cost(self):
        return self.lib.syv_cost(self.state)


VREF = 0.0908                        # a full pick's band level (the demo phrases' 95th percentile, 0.09078)
# level_voices (session scratchpad sy10/level11.py): each tone's RMS on its demo phrase at the old SAW LEAD's on the
# lead phrase (-17.7 dB of the clip), its peak before the soft clip at most 0.9 (FM PIANO, SG PLUCK, SG FM BELL);
# levelled again on test 11's final engine (4 voices, the block passes)
VOICE_GAINS = [0.1799, 0.1072, 0.1259, 0.1349, 0.1778, 0.1216, 0.1778, 0.1318, 0.1799, 0.1905, 0.195, 0.2042, 0.2362, 0.1622, 0.1585, 0.166, 0.0507, 0.1622, 0.2695, 0.2222]
