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
# MIDI out test 7 (the user: "can't the SG tones be reduced to one patch"): the Sound Generator as one patch, CTRL 1
# picks its wave (32 zones), TONE its DUTY, the FILTER page's ENV its ENV preset
P_WAVE = 12
WAVE_NAMES = ['Sine', 'Sine1', 'Sine2', 'Cos', 'Cos1', 'Cos2', 'Saw', 'Saw+', 'Saw2', 'Tri', 'Tri2', 'Pulse',
              'Pulse+', 'Noise1', 'Noise2', 'FM1:1', 'FM1:2', 'FM1:7', 'CZSaw', 'CZSqr', 'CZRes', 'Sync', 'Fold',
              'Drive', 'LPSaw', 'LPSqr', 'Organ', 'Vowel', 'Table', 'Logic', 'Metal', 'Grit']
# each wave's gain in SG SYNTH, so every wave plays at Pulse's loudness (measured on the twin: sg_wave_gains.py)
WAVE_GAINS = [1.446, 1.447, 1.463, 1.447, 1.447, 1.468, 1.537, 3.064, 1.61, 1.775, 1.775, 1.0, 1.987, 2.105, 2.105,
              1.573, 1.208, 1.423, 1.44, 1.276, 1.956, 1.214, 1.058, 2.022, 0.85, 1.016, 0.874, 1.75, 2.012, 0.74,
              1.208, 0.987]   # 11-11, ENV OFF on the model lead phrase, K-weighted (BS.1770), Pulse = 1
# SY test 34: each tone's own setting in tests 11-33 (settings files version 4 and 5): a file from them moves a
# changed tone's old ENV / RESO to the FILTER page and sets its CTRL 1 to the middle (tune_test.c, sy_load)
P2_BEFORE_34 = [P_ATTACK, P_ATTACK, P_ENV, P_ENV, P_ENV, P_RATE, P_ENV, P_GLIDE, P_ENV, P_RESO, P_ENV, P_DETUNE, P_FM,
                P_FM] + [P_ENVSEL] * 6
P2_NAMES = {P_RESO: 'RESO', P_ENV: 'ENV', P_ATTACK: 'ATTACK', P_DETUNE: 'DETUNE', P_GLIDE: 'GLIDE', P_DUTY: 'WIDTH',
            P_DRIVE: 'DRIVE', P_RATE: 'WOBBLE', P_MIX: 'MIX', P_FM: 'FM', P_ENVSEL: 'ENV', P_WAVE: 'WAVE'}
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
         o1=SAW, o1_lev=0.8, o2=PULSE, o2_lev=0.6, lfo_pw=0.25, lfo_rate=0.45, sub=0.29, flt=LP24, cut=2700,
         keytrk=0.1, reso=0.01, fenv=1.3, fa=400, fd=21, fs=0.04, fr=900, aa=10, ad=93, as_=0.7, ar=1000, avel=0.3,
         chorus=2, p2=P_RATE),
    dict(name='STRINGS', about='string machine: two detuned saws, gentle 12 dB filter, delayed vibrato, ensemble',
         o1=SAW, o2=SAW, o2_cent=9, o2_lev=0.8, flt=LP12, cut=4670, keytrk=0, reso=0.01, aa=220, ad=400, as_=1.0,
         ar=2980, lfo_rate=5.2, lfo_delay=350, lfo_pitch=7, chorus=3, avel=0.3, p2=P_RATE),
    dict(name='POLY BRASS', about='Jupiter / Prophet-style brass: two detuned saws, a 24 dB filter blooming on each note',
         o1=SAW, o2=SAW, o2_cent=-8, o2_lev=0.9, flt=LP24, cut=2190, keytrk=0.55, reso=0.17, fenv=3.0, fa=70, fd=580,
         fs=0.44, fr=300, aa=8, ad=198, as_=0.9, ar=2410, fvel=0.5, chorus=1, p2=P_DRIVE),
    dict(name='ENSEMBLE', about='Polysix-style poly: saw and sub, 24 dB filter with a short pluck, ensemble',
         o1=SAW, sub=0.24, flt=LP24, cut=2180, keytrk=0.1, reso=0.09, fenv=1.8, fa=3, fd=607, fs=0.013, aa=1, ad=3790,
         as_=0.76, ar=2810, chorus=3, p2=P_DRIVE),
    dict(name='POLY KEYS', about='Poly-800-style keys: narrow pulse and a saw an octave up, plucky filter, chorus I',
         o1=PULSE, o1_pw=0.175, o2=SAW, o2_semi=12, o2_lev=0.5, flt=LP24, cut=3240, keytrk=0.37, reso=0.073, fenv=2.25,
         fa=2, fd=453, fs=0.146, fr=300, aa=2, ad=14300, as_=0.236, ar=572, chorus=1, p2=P_DUTY),
    dict(name='VECTOR PAD', about='Wavestation-style pad: the SG FM1:2 and Table waves crossfading over a sine',
         o1=SINE, o1_lev=0.3, o2=SG, o2_wave=16, o2_duty=0.4, o2_lev=0.9, o3=SG, o3_wave=28, o3_duty=0.7, o3_lev=0.9,
         lfo_vec=1.0, lfo_rate=0.15, flt=LP12, cut=5000, keytrk=0.3, aa=700, ad=800, as_=1.0, ar=1600, chorus=3,
         half=1, voices=3, p2=P_RATE),
    dict(name='SYNC LEAD', about='Mono/Poly / MS-20-style lead: a hard-synced saw swept down on each pick, glide',
         o1=SAW, o1_lev=0.0, o2=SAW, o2_lev=1.0, o2_sync=1, o2_semi=7, o2_penv=16.9, flt=LP12, cut=4470, keytrk=0.43,
         reso=0.75, fa=1, fd=3730, fs=0.53, aa=2, ad=153, as_=1.0, ar=70, mono=1, glide=35, retrig=1, lfo_rate=5.5,
         lfo_delay=500, lfo_pitch=10, fenv=4.5, p2=P_DRIVE),
    dict(name='LADDER LEAD', about='Minimoog-style lead: three saws (one an octave down), driven ladder, glide, vibrato',
         o1=SAW, o2=SAW, o2_cent=6, o2_lev=0.9, o3=SAW, o3_semi=-12, o3_lev=0.6, flt=LP24, cut=800, keytrk=0.8,
         reso=0.38, fenv=2.4, fa=4, fd=450, fs=0.5, fr=200, aa=3, ad=200, as_=0.95, ar=220, mono=1, glide=60, retrig=1,
         lfo_rate=5.3, lfo_delay=450, lfo_pitch=14, drive=1.8, p2=P_DRIVE),
    dict(name='FAT BASS', about='Moog-style bass: saw and a pulse an octave down, driven ladder, quick filter decay',
         o1=SAW, o2=PULSE, o2_semi=-12, o2_lev=0.7, flt=LP24, cut=300, keytrk=0.4, reso=0.22, fenv=3.2, fa=1, fd=280,
         fs=0.15, fr=120, aa=1, ad=500, as_=0.8, ar=110, mono=1, drive=2.2, p2=P_DRIVE),
    # MIDI out test 2: retrig 1 (every pick attacks; slides and hammer-ons still slide). As a legato tone (retrig 0) a
    # pick over its ringing note slid in with no attack (a repeat: nothing) while test 33's 303 envelope had fallen to
    # 12%: "missing notes" on the unit.
    dict(name='ACID BASS', about='303-style bass: saw through a squelchy resonant 18 dB filter, accent, slides',
         o1=SAW, flt=LP18, cut=223, keytrk=0, reso=0.88, fenv=4.36, fvel=0.6, fa=0.5, fd=224, fs=0.0, fr=80, aa=1,
         ad=437, as_=0.12, ar=37.5, mono=1, glide=70, retrig=1, drive=1.41, p2=P_DRIVE),
    dict(name='PUNCH BASS', about='SH-101-style bass: pulse and sub, a short filter snap', o1=PULSE, o1_pw=0.4,
         sub=0.6, flt=LP24, cut=500, keytrk=0.5, reso=0.15, fenv=2.4, fa=1, fd=190, fs=0.15, aa=1, ad=350, as_=0.65,
         ar=90, mono=1, p2=P_DUTY),
    dict(name='SUPERSAW', about='JP-8000 / Virus-style supersaw: seven detuned saws, wide chorus', o1=SUPERSAW,
         uni_spread=0.55, uni_mix=0.75, flt=LP12, cut=7000, keytrk=0.2, reso=0.05, aa=12, ad=900, as_=0.9, ar=500,
         chorus=4, voices=3, p2=P_DETUNE),
    dict(name='FM PIANO', about='DX7-style electric piano: FM with a bright tine on the attack, piano-like decay',
         o1=FM, fm_ratio=1.0, fm_index=4.86, fm_floor=0.38, fm_decay=661, fm2_ratio=14.0, fm2_index=0.73,
         fm2_decay=40, flt=0, aa=1, ad=11800, as_=0.0, ar=768, avel=0.8, chorus=1, p2=P_FM),
    dict(name='FM BELL', about='FM bell an octave up: inharmonic ratio, long ring', o1=FM, fm_ratio=3.5,
         fm_index=2.03, fm_floor=0.22, fm_decay=1100, fm2_index=1.92, fm2_decay=5.33, flt=0, aa=1, ad=1980, as_=0.0,
         ar=2810, chorus=4, oct=1, p2=P_FM),
    dict(name='SG ACID', about='the Sound Generator exactly: Saw with ENV Acid', o1=SG, o1_wave=6, flt=SGF,
         sg_preset=7, p2=P_ENVSEL),
    dict(name='SG VOWEL', about='the Sound Generator exactly: Vowel (DUTY 40) with ENV FPad', o1=SG, o1_wave=27,
         o1_duty=0.4, flt=SGF, sg_preset=9, voices=3, p2=P_ENVSEL),
    dict(name='SG ORGAN', about='the Sound Generator exactly: Organ (DUTY 90) with ENV OFF', o1=SG, o1_wave=26,
         o1_duty=0.9, flt=SGF, sg_preset=0, voices=4, p2=P_ENVSEL),
    dict(name='SG CZ KEYS', about='the Sound Generator exactly: CZSaw (DUTY 90) with ENV Keys', o1=SG, o1_wave=18,
         o1_duty=0.9, flt=SGF, sg_preset=3, p2=P_ENVSEL),
    dict(name='SG PLUCK', about='the Sound Generator exactly: Pulse (DUTY 30) with ENV Pluck', o1=SG,
         o1_wave=11, o1_duty=0.3, flt=SGF, sg_preset=1, p2=P_ENVSEL),
    dict(name='SG FM BELL', about='the Sound Generator exactly: FM1:7 (DUTY 60) with ENV Perc', o1=SG, o1_wave=17,
         o1_duty=0.6, flt=SGF, sg_preset=2, p2=P_ENVSEL),
]
# MIDI out test 4 (the user: "fill pad 16 with a tone ... shift + pad page of tones could fill 1-16"): twelve more
# tones, 32 in all. Pads 1-15 and SHIFT + pads 1-5 keep theirs; pad 16 and SHIFT + pads 6-16 play tones 21-32
# (SLOT_TONE). NEW_VOICES: their designs (analysis/midi-out/test4-tones).
# The designs (analysis/midi-out/test4-tones/new_voices.py: levelled at the 20's median momentary loudness,
# -27.92 LUFS-M; mono and dry; leads and basses mono 1 / retrig 1; only the pads swell; checked on the model
# guitar through the twin, every knob at its ends finite):
NEW_VOICES = [
    # RATE: the pulse-width wobble's speed (WOBBLE: its depth too)
    dict(name='SQUARE LEAD', about='Prophet / Oberheim-style lead: two near-square pulses a few cents apart, a slow '
                                   'pulse-width wobble, 24 dB filter, glide',
         o1=PULSE, o1_pw=0.44, o2=PULSE, o2_pw=0.44, o2_cent=7, o2_lev=0.8, lfo_pw=0.1, lfo_rate=0.8, flt=LP24,
         cut=2000, keytrk=0.6, reso=0.18, fenv=1.2, fa=1, fd=400, fs=0.5, fr=200, aa=2, ad=500, as_=0.85, ar=160,
         mono=1, retrig=1, glide=60, chorus=0, p2=P_RATE),
    # an octave down (OCTAVE moves it from there); the 808's pitch drop is a 20 ms FM thump here (no pitch envelope on
    # oscillator 1); DRIVE from a pure sine to a distorted 808; the 24 dB filter only for TONE (on the drive's grit)
    dict(name='SUB BASS', about='808-style sub: a sine an octave down with a short thump, long decay, a touch of drive',
         o1=FM, fm_ratio=1.0, fm_index=1.5, fm_floor=0.0, fm_decay=20, oct=-1, flt=LP24, cut=1000, keytrk=0.0,
         reso=0.0, drive=1.4, aa=1, ad=2000, as_=0.55, ar=160, avel=0.5, mono=1, retrig=1, glide=70, chorus=0,
         p2=P_DRIVE),
    # the saws at 0.7 so DRIVE 1.5 grits it without flattening the beat (2.0 at full level: 1.9 dB of beat left)
    dict(name='REESE BASS', about='Reese bass: two saws 13 cents apart beating slowly, driven into a dark 24 dB filter',
         o1=SAW, o1_lev=0.7, o2=SAW, o2_cent=13, o2_lev=0.7, flt=LP24, cut=600, keytrk=0.2, reso=0.15, fenv=0.8,
         fa=2, fd=300, fs=0.3, fr=150, drive=1.5, aa=2, ad=900, as_=0.9, ar=120, mono=1, retrig=1, glide=45,
         chorus=0, p2=P_DRIVE),
    # FM: the index (TONE moves it too, as on the other FM tones)
    dict(name='FM BASS', about='DX7-style FM bass: a bright, knocking attack falling to a warm hollow tone',
         o1=FM, fm_ratio=1.0, fm_index=5.0, fm_floor=0.3, fm_decay=120, fm2_ratio=7.0, fm2_index=1.5, fm2_decay=10,
         flt=0, aa=1, ad=600, as_=0.55, ar=90, avel=0.7, mono=1, retrig=1, glide=30, chorus=0, p2=P_FM),
    # an octave up; RATE: the vibrato's speed (WOBBLE: its depth too); the filter only for TONE (the triangle's edge)
    dict(name='WHISTLE', about='G-funk whistle lead: a sine an octave up with delayed vibrato and a long glide',
         o1=SINE, o2=TRI, o2_lev=0.12, oct=1, flt=LP12, cut=3500, keytrk=0.3, reso=0.0, aa=5, ad=800, as_=0.92,
         ar=200, lfo_pitch=28, lfo_rate=5.6, lfo_delay=280, avel=0.5, mono=1, retrig=1, glide=60, chorus=0,
         p2=P_RATE),
    # WIDTH: the pulse from thin and nasal to hollow
    dict(name='CLAV', about='Clavinet-style pluck: a narrow pulse through a band-pass that snaps shut, quick mute',
         o1=PULSE, o1_pw=0.25, flt=BP12, cut=1300, keytrk=0.7, reso=0.2, fenv=0.7, fa=0.5, fd=120, fs=0.2, fr=60,
         fvel=0.4, aa=0.5, ad=1100, as_=0.4, ar=50, avel=0.75, chorus=0, p2=P_DUTY),
    # RATE: the vibraphone motor's tremolo (WOBBLE: none at the bottom, a marimba); TONE: the mallet's hardness (FM)
    dict(name='MALLET', about='FM marimba / vibes: a woody strike on a sine, a vibraphone tremolo as it rings',
         o1=FM, fm_ratio=1.0, fm_index=1.0, fm_floor=0.1, fm_decay=150, fm2_ratio=4.0, fm2_index=2.5, fm2_decay=22,
         flt=0, aa=0.5, ad=1300, as_=0.0, ar=350, avel=0.75, lfo_amp=0.3, lfo_rate=4.5, lfo_delay=200, chorus=0,
         p2=P_RATE),
    # designed clean (drive 1: any drive aliased at the top), so DRIVE's left half does nothing (as POLY BRASS)
    dict(name='OB PAD', about='Oberheim-style pad: two saws 16 cents apart, a resonant 12 dB filter swelling open',
         o1=SAW, o2=SAW, o2_cent=16, o2_lev=0.9, sub=0.15, flt=LP12, cut=900, keytrk=0.35, reso=0.5, fenv=1.6,
         fa=900, fd=2500, fs=0.45, fr=1500, aa=650, ad=1500, as_=0.9, ar=1800, avel=0.35, chorus=0, p2=P_DRIVE),
    dict(name='BRASS STAB', about='Jupiter-style brass stab: two detuned saws, a fast 24 dB filter blat, short',
         o1=SAW, o1_lev=0.8, o2=SAW, o2_cent=-11, o2_lev=0.75, flt=LP24, cut=900, keytrk=0.5, reso=0.22, fenv=2.5,
         fa=12, fd=230, fs=0.12, fr=120, fvel=0.6, drive=1.3, aa=3, ad=380, as_=0.25, ar=150, avel=0.7, chorus=0,
         p2=P_DRIVE),
    # the dive: oscillator 2 hard-synced to a silent oscillator 1, swept from 2 octaves over the note down to 3.6
    # semitones (held, a nasal sync edge) by the pick's filter envelope, and the rest of the way on release (o2_penv only
    # works on a synced oscillator 2); the 12 dB filter (the ladder's input clip aliased); FILTER's ENV scales the dive
    dict(name='HOOVER', about='rave hoover: a synced saw diving onto the note over a detuned saw and a sub, long glide',
         o1=SAW, o1_lev=0.0, o2=SAW, o2_sync=1, o2_lev=0.65, o2_penv=24.0, o3=SAW, o3_cent=25, o3_lev=0.4, sub=0.22,
         flt=LP12, cut=2400, keytrk=0.3, reso=0.15, fenv=1.2, fa=1, fd=500, fs=0.15, fr=350, drive=1.15, aa=2,
         ad=600, as_=0.9, ar=250, avel=0.5, mono=1, retrig=1, glide=60, chorus=0, p2=P_DRIVE),
    # no filter to hear (a 12 dB one wide open at 20 kHz, only so TONE still darkens it: with none TONE would move an
    # unused FM index); WIDTH: the duty from thin to square (the NES's 12.5 / 25 / 50 %)
    dict(name='CHIP LEAD', about='8-bit chip lead: a bare 25% pulse, organ-like gate, delayed vibrato, quick slides',
         o1=PULSE, o1_pw=0.25, flt=LP12, cut=20000, keytrk=0.0, reso=0.3, aa=0.5, ad=1, as_=1.0, ar=25,
         lfo_pitch=18, lfo_rate=6.5, lfo_delay=350, avel=0.3, mono=1, retrig=1, glide=25, chorus=0, p2=P_DUTY),
    # RATE: the sweep's speed (WOBBLE: its depth too); each strum also opens the filter over 1.5 s (the pick's filter
    # envelope, every voice's) and lets it close over 3.5 s; the LFO is each voice's own (they stayed together in the
    # twin's pad phrases: six voices sounding, 0.001 cycle apart)
    dict(name='SWEEP PAD', about='sweep pad: two saws and a sub through a resonant 24 dB filter that slowly opens and '
                                 'closes (LFO)',
         o1=SAW, o1_lev=0.6, o2=SAW, o2_cent=-9, o2_lev=0.5, sub=0.12, flt=LP24, cut=750, keytrk=0.3, reso=0.4,
         fenv=1.6, fa=1500, fd=3500, fs=0.25, fr=2000, lfo_cut=1.4, lfo_rate=0.16, aa=350, ad=2000, as_=0.9, ar=1800,
         avel=0.35, chorus=0, p2=P_RATE),
]

# levelled by level_new.py: each at the 20's median momentary loudness (-27.92 LUFS-M, test 34's way)
NEW_GAINS = [0.0415, 0.0840, 0.0766, 0.0887, 0.0620, 0.2238, 0.1071, 0.0545, 0.1423, 0.0862, 0.0476, 0.0993]
VOICES = VOICES + NEW_VOICES
# The screen's sound slots, pads 1-16 then SHIFT + pads 1-16, and the tone each plays
SLOT_TONE = list(range(15)) + [20] + list(range(15, 20)) + list(range(21, 32))
assert sorted(SLOT_TONE) == list(range(len(VOICES))), 'every tone in one slot'
TONE_SPLIT = (16, 13)                # MIDI out test 4: the table in three slots: 16, 13, the rest
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
    h += '#define SYV_P_WAVE %d\n' % P_WAVE        # MIDI out test 7: SG SYNTH, each wave's gain
    h += 'static const float SYV_WAVE_GAIN[32] = {' + ', '.join(_cf(g) for g in WAVE_GAINS) + '};\n'
    h += 'static const float SYV_CENTRE[49] = {' + ', '.join(_cf(c) for c in centres()) + '};\n'
    h += 'static const float SYV_PRESET[10][14] = {\n' + ',\n'.join(
        '{' + ', '.join(_cf(x) for x in row) + '}' for row in PRESETS) + '};\n'
    # MIDI out test 4: the table out of the module (it filled it: 20 x 228 bytes), in three slots of its own
    # (.syvtone0..2, the builder's SYV_TONES0..2); sy_fp.c and the host build ask for it (SYV_WANT_TONES)
    pats = [c_patch(patch(t, g)) for t, g in zip(VOICES, gains)]
    n0 = min(len(pats), TONE_SPLIT[0])
    n1 = min(len(pats) - n0, TONE_SPLIT[1])
    n2 = len(pats) - n0 - n1
    assert n1 > 0 and n2 > 0, 'three tables, none empty'
    h += '#if defined(SYV_WANT_TONES)\n#ifdef SYV_HOST\n#define SYV_TONE_IN(n)\n#else\n'
    h += '#define SYV_TONE_IN(n) __attribute__((section(".syvtone" #n)))\n#endif\n'
    for k, (lo, n) in enumerate(((0, n0), (n0, n1), (n0 + n1, n2))):
        h += 'static const syv_patch_t SYV_TONE%d[%d] SYV_TONE_IN(%d) = {\n' % (k, n, k)
        h += ',\n'.join(pats[lo:lo + n]) + '\n};\n'
    h += ('static inline const syv_patch_t *syv_tone_at(unsigned t) {\n'
          '    return t < %du ? &SYV_TONE0[t] : t < %du ? &SYV_TONE1[t - %du] : &SYV_TONE2[t - %du];\n}\n'
          % (n0, n0 + n1, n0, n0 + n1))
    h += '#endif\n'
    return h


def c_names():
    """For the screen: the tones' names (16 bytes each), their CTRL 1 setting's name and kind, each one's designed
    DYNAMICS (0..100), the ENV presets' names."""
    h = '/* Generated by sy_voices.py (SY synth test 11): the names on the screen. */\n'
    h += '#define SYV_NTONES %d\n#define SY_OCT_ZERO 3u\n#define SY_OCTAVES 5u\n' % len(VOICES)
    h += '#define SYV_FILE_NAME "%s"\n' % FILE_NAME   # MIDI out test 4: the settings file (audition builds)
    h += '#define SYV_SLOTS %d\n' % len(SLOT_TONE)    # MIDI out test 4: pads 1-16, SHIFT + pads 1-16
    h += 'static const unsigned char SYV_SLOT_TONE[%d] = {' % len(SLOT_TONE)
    h += ', '.join(str(t) for t in SLOT_TONE) + '};\n'
    h += 'static const unsigned char SYV_TONE_SLOT[%d] = {' % len(VOICES)
    h += ', '.join(str(SLOT_TONE.index(t)) for t in range(len(VOICES))) + '};\n'
    h += '#define SYV_P_ENVSEL %d\n' % P_ENVSEL
    h += '#define SYV_P_WAVE %d\n' % P_WAVE         # MIDI out test 7: SG SYNTH's waves by name, each tone's DUTY
    h += 'static const char SYV_WAVE_NAME[32][7] = {' + ', '.join('"%s"' % n for n in WAVE_NAMES) + '};\n'
    h += 'static const unsigned char SYV_WAVE_OF[%d] = {' % len(VOICES)
    h += ', '.join(str(dict(DEFAULTS, **t)['o1_wave']) for t in VOICES) + '};\n'
    h += 'static const unsigned char SYV_DUTY0[%d] = {' % len(VOICES)
    h += ', '.join(str(int(round(100 * dict(DEFAULTS, **t)['o1_duty']))) for t in VOICES) + '};\n'
    h += ('#define SYV_PK_RESO %d\n#define SYV_PK_ENV %d\n#define SYV_PK_ATTACK %d\n#define SYV_PK_GLIDE %d\n'
          % (P_RESO, P_ENV, P_ATTACK, P_GLIDE))     # SY test 32: own settings the SHAPE and FILTER pages share
    h += 'static const char SYV_NAME[%d][16] = {' % len(VOICES)
    h += ', '.join('"%s"' % t['name'] for t in VOICES) + '};\n'
    h += 'static const char SYV_P2NAME[%d][8] = {' % len(VOICES)
    h += ', '.join('"%s"' % P2_NAMES[t.get('p2', P_RESO)] for t in VOICES) + '};\n'
    h += 'static const unsigned char SYV_P2KIND[%d] = {' % len(VOICES)
    h += ', '.join(str(t.get('p2', P_RESO)) for t in VOICES) + '};\n'
    h += 'static const unsigned char SYV_P2KIND_V5[%d] = {' % len(VOICES)   # SY test 34: the own settings before
    h += ', '.join(str(k) for k in P2_BEFORE_34 + [t.get('p2', P_RESO) for t in VOICES[len(P2_BEFORE_34):]])
    h += '};\n'
    h += 'static const unsigned char SYV_DYN_DESIGN[%d] = {' % len(VOICES)
    h += ', '.join(str(int(round(100 * dict(DEFAULTS, **t)['avel']))) for t in VOICES) + '};\n'
    h += 'static const unsigned char SYV_PRESET_OF[%d] = {' % len(VOICES)
    h += ', '.join(str(dict(DEFAULTS, **t)['sg_preset']) for t in VOICES) + '};\n'
    h += 'static const char SYV_PRESET_NAME[10][6] = {' + ', '.join('"%s"' % n for n in PRESET_NAMES) + '};\n'
    # SY test 32: the SHAPE page's designed values (ms; a Sound Generator tone's are its ENV preset's: 0, shown AUTO;
    # GLIDE 0 = off) and the filter (0 none, 6 the Sound Generator's: FILTER's ENV and RESO do nothing there)
    def ms(t, key):
        v = dict(DEFAULTS, **t)
        return 0 if v['flt'] == SGF and key != 'glide' else int(round(v[key]))
    for name, key in (('SYV_ATK_MS', 'aa'), ('SYV_REL_MS', 'ar'), ('SYV_GLI_MS', 'glide')):
        h += 'static const unsigned short %s[%d] = {' % (name, len(VOICES))
        h += ', '.join(str(ms(t, key)) for t in VOICES) + '};\n'
    h += 'static const unsigned char SYV_FLT[%d] = {' % len(VOICES)
    h += ', '.join(str(dict(DEFAULTS, **t)['flt']) for t in VOICES) + '};\n'
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
#define SYV_WANT_TONES 1
#include <xmmintrin.h>
#include "{(HERE / 'sy_voice.c').as_posix()}"
__declspec(dllexport) float syv_block_host(syv_state_t *s, const syv_patch_t *p, const syv_knobs_t *k,
                                           const float *tg, const float *per, const float *e,
                                           const unsigned char *struck, float vref, float mg, float mgt, float fade,
                                           float scale, int *out) {{
    unsigned int old = _mm_getcsr();
    _mm_setcsr((old & ~0x6000u) | 0x8040u);
    float r = syv_block(s, p, k, tg, per, e, struck, vref, mg, mgt, fade, scale, out);
    _mm_setcsr(old);
    return r;
}}
__declspec(dllexport) void syv_reset_host(syv_state_t *s) {{ syv_reset(s); }}
__declspec(dllexport) unsigned syv_state_bytes(void) {{ return sizeof(syv_state_t); }}
__declspec(dllexport) unsigned syv_patch_bytes(void) {{ return sizeof(syv_patch_t); }}
__declspec(dllexport) const syv_patch_t *syv_tone(unsigned i) {{ return syv_tone_at(i); }}
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
                ('sus', ctypes.c_uint8), ('dyn', ctypes.c_uint8), ('glitch', ctypes.c_uint8), ('sens', ctypes.c_uint8),
                ('guard', ctypes.c_uint8), ('since', ctypes.c_uint8),
                ('law', ctypes.c_uint8),       # SY test 15: the TRACK page; 16: since, blocks since the last pick;
                ('ynote', ctypes.c_uint8),     # 18: LAW (0 off, 1 SY 1:1, 2 SY 2:1); 19: the SG tracker's analysis
                ('yflag', ctypes.c_uint8),     # this block (its note + 1 if voiced), flags (1 an analysis, 2 clean,
                ('ysince', ctypes.c_uint8),    # 0x80 the tracker runs), blocks since its pluck, its own note
                ('ysyn', ctypes.c_uint8),      # (the SG's) + 1; 20: its note-ons' count (low byte)
                ('yseq', ctypes.c_uint8),
                ('voices', ctypes.c_uint8),    # SY test 24: TRACK's CTRL 3 (0 the tone's, 1 single notes, 2..6 a cap)
                ('env', ctypes.c_int8), ('res', ctypes.c_int8),   # SY test 32: FILTER (knob offsets, 0 as designed)
                ('atk', ctypes.c_uint16), ('rel', ctypes.c_uint16), ('gli', ctypes.c_uint16)]   # SHAPE (ms, 0 as
                                                                                              # designed; gli 0xFFFF off)


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

    def set_knobs(self, tone=0, p2=0, level=0, oct=0, sus=0, dyn=0, glitch=0, sens=0, guard=0, since=255, law=0,
                  ynote=0, yflag=0, ysince=255, ysyn=0, yseq=0, voices=0, env=0, res=0, atk=0, rel=0, gli=0):
        self.knobs.env, self.knobs.res = env, res                                # SY test 32: FILTER, SHAPE
        self.knobs.atk, self.knobs.rel, self.knobs.gli = atk, rel, gli
        self.knobs.tone, self.knobs.p2, self.knobs.level = tone, p2, level
        self.knobs.oct, self.knobs.sus, self.knobs.dyn = oct, sus, dyn
        self.knobs.glitch, self.knobs.sens, self.knobs.guard = glitch, sens, guard   # SY test 15: TRACK; 24: GLITCH
        self.knobs.since = since                                                 # SY test 16
        self.knobs.law = law                                                     # SY test 18
        self.knobs.ynote, self.knobs.yflag, self.knobs.ysince = ynote, yflag, ysince   # SY test 19: the tracker
        self.knobs.ysyn = ysyn
        self.knobs.yseq = yseq & 0xFF                                            # SY test 20
        self.knobs.voices = voices                                               # SY test 24

    def block(self, tone_index, tg, per, e, struck, vref=None, mg=1.0, mgt=1.0, fade=1.0, scale=1.0):
        """One block from the bands' levels, periods (12 kHz samples), energies and, SY test 18, the blocks left of
        each band's strike (tests 12-17: periods counted since each woke, unused): (64 ints, the fade after it)."""
        a = (ctypes.c_float * 49)(*map(float, tg))
        f = (ctypes.c_float * 49)(*map(float, per))
        g = (ctypes.c_float * 49)(*map(float, e))
        n8 = (ctypes.c_uint8 * 49)(*[min(int(v), 255) for v in struck])
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
# SY test 34: every tone 6 dB down (resampled to a pad the synth was at full scale: a hard strum at the soft clip),
# SG ORGAN and SG CZ KEYS (new DUTY / ENV) at the others' median loudness (momentary, K-weighted, E2..E4): a hard
# six-string strum now peaks near -7..-11 dBFS on the DRY stem (SG PLUCK's attack -4.5), one note -12..-25
VOICE_GAINS = [0.1231, 0.0526, 0.0597, 0.0688, 0.0869, 0.0609, 0.0848, 0.0661, 0.0902, 0.1896, 0.0977, 0.1023, 0.0789, 0.086, 0.0794, 0.0832, 0.0222, 0.0839, 0.1351, 0.1114]
VOICE_GAINS = VOICE_GAINS + NEW_GAINS   # MIDI out test 4: the 12 new tones

# MIDI out test 4's audition builds (the user: "split into a test app1 with leads/bass and test app1 with chords"):
# SY_TONESET names a Python file whose VOICES (32 dicts), VOICE_GAINS and SLOT_TONE replace these, and FILE_NAME the
# settings file's, so a build can carry another set of 32 tones without touching this table. Unset: test 4's.
# MIDI out test 7: the six Sound Generator sounds (SG ACID .. SG FM BELL) as one: WAVE on CTRL 1, DUTY on TONE, the
# ENV preset on the FILTER page's ENV; as designed, SG PLUCK (Pulse, DUTY 30, ENV Pluck)
SG_SYNTH = dict(name='SG SYNTH', about='the Sound Generator as one patch: WAVE on CTRL 1, DUTY on TONE, the ENV '
                'preset on the FILTER page (as designed Pulse, DUTY 30, ENV Pluck)', o1=SG, o1_wave=11, o1_duty=0.3,
                flt=SGF, sg_preset=1, p2=P_WAVE)

# MIDI out test 14: test 4's 32 above stay as the pool the audition builds were drawn from (POOL_*, read by
# analysis/midi-out/candidates/make_tonesets.py and make_final.py). The build plays the user's final 32, sy_final.py
# (written by make_final.py, with its own settings file), or the set SY_TONESET names.
POOL_VOICES, POOL_GAINS, POOL_SLOT_TONE = VOICES, VOICE_GAINS, SLOT_TONE
FILE_NAME = 'B:/_sy_tones.bin'
_set = __import__('os').environ.get('SY_TONESET') or str(HERE / 'sy_final.py')
_ns = {'__file__': _set, '__name__': 'toneset'}
exec(compile(Path(_set).read_text(encoding='utf-8'), _set, 'exec'), _ns)
VOICES, VOICE_GAINS, SLOT_TONE = _ns['VOICES'], _ns['VOICE_GAINS'], _ns['SLOT_TONE']
FILE_NAME = _ns.get('FILE_NAME', FILE_NAME)
assert len(VOICES) == len(VOICE_GAINS) == 32 and sorted(SLOT_TONE) == list(range(32)), 'a toneset of 32'
NTONES = len(VOICES)
