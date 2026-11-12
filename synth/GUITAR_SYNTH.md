# The guitar synth (v9.53)

Plug a guitar into the SP-404MKII and it plays synth sounds: 32 of them, single-note leads and basses and chord
sounds, picked and shaped on a screen of their own. Your guitar can also play the Sound Generator or one of the drum
kits, and those notes can go out over MIDI to another synth or a computer. Everything runs on the SP; nothing extra to
install. How it works and how it was tested: [SY_TEST.md](SY_TEST.md) and [TUNE_TEST.md](TUNE_TEST.md).

In this guide, **A + B** means hold A and press B. "VALUE (press)" means pushing the VALUE knob in.

## Quick start

1. Plug the guitar into the front **INPUT** jack and set the **MIC/GUITAR** switch to **GUITAR** (to the right).
2. Choose **Bypass** (or a clean effect) as the input FX.
3. Press **EXT SOURCE** so it lights. Strum hard and set **GAIN** just below the point where EXT SOURCE blinks red.
4. Hold **VALUE** and press **RECORD SETTING**. The guitar synth screen opens (on SYNC LEAD the first time) and the
   synth plays.
5. Tap **pads 1-16** to pick a sound: pads 1-8 are leads and basses, pads 9-16 chord sounds. For the second bank, hold
   SHIFT and tap pad 2, then tap a pad (SHIFT + pad 1 goes back to bank 1).
6. Press **EXIT**. The synth keeps playing on every screen.
7. **HOLD + EXT SOURCE** switches the synth off and on. EXT SOURCE lights green while it plays.

To play the Sound Generator or a drum kit from the guitar instead, open it (SHIFT + RECORD SETTING or SHIFT + PATTERN
EDIT) with EXT SOURCE on, and play: see [Guitar notes](#guitar-notes-on-the-sound-generator-and-the-kits).

## Setting up

| What | Set it to | Why |
| --- | --- | --- |
| Guitar cable | The front INPUT jack | |
| MIC/GUITAR switch | GUITAR (to the right) | A guitar needs the high-impedance input. |
| GAIN | Strum hard, then set it just below the point where EXT SOURCE blinks red | A hot input makes the chord sounds busier, and a clipping one much worse (extra and wrong notes). |
| Input FX | Bypass, or a clean effect | The synth listens after the input FX. Distortion (the Gt Amp Sim too) adds tones of its own, and the synth plays those as well. |
| Pedals before the SP | A clean signal: no distortion, chorus or noisy pedals | A murkier signal plays fewer of the right notes. |
| EXT SOURCE | On (lit) | The synth and the guitar notes only listen while the input is on. |

- **The synth hears everything on the input:** the INPUT jack, LINE IN, and USB audio when USB In (SYSTEM > GENERAL)
  is set to LINE IN. A drum machine on LINE IN would play it too.
- **ROUTING doesn't need changing.** While the synth or the guitar notes listen, the SP keeps its effects chip on ExtIn
  by itself, so the synth hears only your guitar, never its own sound. Your ROUTING setting comes back as soon as
  nothing listens.
- **ROUTING still decides what recordings get** (sampling, RESAMPLE, the looper) while the synth listens:
  - **Mix:** your pads, the guitar, the guitar synth and the Sound Generator, with BUS 1/2 effects, but without BUS
    3/4 effects;
  - **ExtIn:** your guitar plus the guitar synth (without its bus effect), but not the pads or the Sound Generator.

### Where the dry guitar and the synth go

- **Your dry guitar** plays on the input bus: REMAIN + EXT SOURCE on the main screen steps it (EXT SOURCE dark = DRY,
  lit = BUS 1, blinking = BUS 2), as on a stock SP.
- **The synth** plays where **OUT** says. On the guitar synth screen, VALUE (press) steps **OUT: DRY, BUS 1, BUS 2,
  BOTH** (one setting for all sounds). BUS 1 or BUS 2 puts the synth through that bus's effect; BOTH puts half on each.
  The synth has no chorus, delay or reverb of its own: use the bus effects for those.
- **To hear the synth without your dry guitar:** put the input on BUS 1 (REMAIN + EXT SOURCE until it is lit) and turn
  all three Isolator bands down on BUS 1. The synth still hears the guitar. Keep the synth on OUT: DRY or OUT: BUS 2
  then, since the Isolator on BUS 1 would cut it too.

## Buttons

### Anywhere

| Buttons | What it does |
| --- | --- |
| **HOLD + EXT SOURCE** | Switches the guitar synth on or off (popup GUITAR SYNTH ON / OFF). The input itself isn't switched: if EXT SOURCE is off, turn it on too. The synth stays on or off while you switch EXT SOURCE off and on. |
| **VALUE + RECORD SETTING** | Opens the guitar synth screen, from the main screen, the Sound Generator, the kits or the looper. It also switches the input on, and the synth on. |
| **EXT SOURCE** (tap) | The input on and off, as on a stock SP; now also on the Sound Generator page and the kits, where stock ignores it (popup EXT IN ON / OFF). With EXT SOURCE's gate on (EXT SOURCE + GATE, as on stock), the input is on only while you hold EXT SOURCE. |
| **HOLD + MFX** | Hidden effect settings off and on (it was HOLD + VALUE before v9.53). |
| **HOLD + VALUE** | The input FX's hidden settings (it was VALUE + EXT SOURCE before v9.53). |
| **VALUE + EXT SOURCE** | Stock again: switches the input. |
| **EXIT held for 1 second** (main screen) | Shows or hides the CPU readout. |

**EXT SOURCE's light:** off = input off; white = input on, the guitar dry; green = input on and the guitar synth on (on
the Sound Generator and kits: the guitar notes or the synth play there); blinking red = stock's warning that the input
is too hot, so turn GAIN down.

### On the guitar synth screen

| Buttons | What it does |
| --- | --- |
| **Pads 1-16** | Pick a sound in the current bank. The pads never play samples here. The current sound's pad is bright (cyan on 1-8, magenta on 9-16), the others dim. |
| **SHIFT + pad 1 / pad 2** | Bank 1 / bank 2 (the sound stays until you tap a pad). While SHIFT is held, pads 1-2 show the banks, the current one white. |
| **VALUE** (turn) | Steps through all 32 sounds in order, bank 1 then bank 2; the bank follows. All the way down is SYNTH OFF. |
| **VALUE** (press) | OUT: DRY, BUS 1, BUS 2, BOTH. |
| **CTRL 1-3** | The three settings on the page shown. |
| **SHIFT** (tap) | The next page: main, OTHERS, TRACK, SHAPE, FILTER, then main again. |
| **SHIFT held + CTRL 1-3** | Edits the OTHERS page while held (from OTHERS: the main page); letting go keeps the page you were on. |
| **EXIT** | Back to the main screen; the synth keeps playing. |
| **SHIFT + RECORD SETTING** | Leaves to the Sound Generator. |
| **SHIFT + PATTERN EDIT** | Leaves to the kits. |
| **MARK** (MARK Function: Looper) | The looper; MARK again comes back to the guitar synth screen. |
| **An FX button** | Its effect screen; while it is up, the knobs, VALUE and SHIFT work the effect, and VALUE presses step into its hidden settings. The pads still pick sounds. |
| **MFX held + a pad** | Picks an MFX effect, as on stock (the pads show stock's colours while MFX is held). |
| **REC** | With looper mode on: the looper's REC. |

On this screen VALUE's press is always OUT, also with HOLD or SHIFT held (unless an effect screen is up). For the input
FX's hidden settings (HOLD + VALUE) or MARK Function (SHIFT + VALUE), leave the screen first.

### Guitar notes, effects and the looper

| Buttons | Where | What it does |
| --- | --- | --- |
| **HOLD + RECORD SETTING** | Sound Generator page | Guitar notes off / on (popup GUITAR NOTES OFF / ON; remembered). With them off, you hear the guitar dry, or the guitar synth if it is on. |
| **HOLD + PATTERN EDIT** | Kits | The same, for the kits. |
| **An FX button, then VALUE** | Every screen, the Sound Generator, the kits and the guitar synth screen too | The effect's hidden settings, as on the main screen. |
| **REMAIN + an FX button** | Sound Generator, kits, guitar synth screen | Keeps the effect screen up (lit effect or not) and leaves the effect as it is. A REMAIN tap still steps the preview bus. |
| **MARK** | Sound Generator or kits (MARK Function: Looper) | The looper; the guitar notes keep playing (and sending MIDI) there. |
| **MARK** on the looper, while it waits or records | Looper opened from the Sound Generator, kits or guitar synth screen | Goes back with looper mode still on: REC keeps flashing, a pad (or a sound with AUTO TRIG) starts the take, REC stops it, as after SHIFT + RECORD SETTING. |
| **SHIFT held** | Main screen | PATTERN EDIT pulses with RECORD SETTING and RESAMPLE: SHIFT + PATTERN EDIT opens the kits. |

- **VALUE on the Sound Generator page and kits** now does its own job (the VALUE menu, BOUNC) when you let go, so that
  VALUE + RECORD SETTING can open the guitar synth screen. VALUE + a knob, a pad or a turn, and ROLL, SHIFT, HOLD,
  REMAIN or EXT SOURCE + VALUE work as before.
- **REC's light** keeps flashing while the looper waits, and blinks while it records, on the Sound Generator, the
  kits, the guitar synth screen and the main screen (stock 5.52 leaves it dark after MARK).

## The guitar synth screen

Three knob columns, a bar (SHIFT:OTHERS on the left, OUT on the right) and the sound's name below.

| Page (tap SHIFT) | CTRL 1 | CTRL 2 | CTRL 3 | Applies to |
| --- | --- | --- | --- | --- |
| **main** | the sound's own setting (below) | **TONE** -50..+50 (SG SYNTH: DUTY 0-100) | **LEVEL** 0-100 | this sound |
| **OTHERS** | **OCTAVE** -2..+2 | **SUSTAIN** 0-100 | **DYNAMICS** 0-100 | this sound |
| **TRACK** | **GLITCH** 0-100 | **SENS** 0-100 | **VOICES** AUTO, MONO, 2-6 | all sounds |
| **SHAPE** | **ATTACK** 1 ms - 2 s | **RELEASE** 10 ms - 8 s | **GLIDE** OFF, 5 ms - 1 s | this sound |
| **FILTER** | **ENV** -50..+50 | **RESO** -50..+50 | nothing | this sound |

0 on the -50..+50 knobs and 50 on LEVEL, SUSTAIN and SENS are the sound as designed; DYNAMICS and the SHAPE page start
at each sound's own values. FM PIANO has no filter, so no FILTER page. On SG SYNTH and SG ORGAN the FILTER page's ENV is
their Sound Generator ENV preset, by name. The knobs set their value where they are (the first turn after a page or
sound change jumps to the knob's position).

**main page**
- **TONE:** darker or brighter (the filter, up to two octaves either way; FM PIANO: the FM brightness; SG ORGAN: its
  drawbar mix, or the ENV preset's filter if it has one; SG SYNTH: the wave's DUTY).
- **LEVEL:** the synth's volume: 50 as designed, 100 twice as loud (+6 dB), 0 silent. It is separate from the Sound
  Generator's LEVEL.

**OTHERS page**
- **OCTAVE:** two octaves down to two up.
- **SUSTAIN:** how long notes ring after you let go: 0 a quarter as long, 100 four times as long.
- **DYNAMICS:** how much picking harder makes the synth louder: 0 every note equally loud, 100 fully follows your pick.

**TRACK page** (one setting for all sounds)
- **GLITCH:** 0 is clean. Turning it up gives each voice its own attack and lets more of the guitar's flicker start
  notes; chord sounds get choppier attacks and releases (from 90 at most 4 voices). From 50 the older, glitchy
  tracking takes over, and toward 100 pops, wrong notes and stutter grow in.
- **SENS:** how soft a pick can be and still start a note (it moves the note tracker's thresholds by up to 12 dB). It
  acts on the single-note sounds, on VOICES MONO and on the guitar notes on the Sound Generator and kits; chord sounds
  follow every string whatever SENS is.
- **VOICES:** AUTO = each sound as designed; MONO = single notes from the note tracker, every pick attacking (use it
  for single-note lines on a chord sound); 2-6 = at most that many chord voices (on a single-note sound, it plays
  chords).

**SHAPE page**
- **ATTACK:** how fast a note fades in.
- **RELEASE:** how long a note rings after you let go (the tail you hear is about half the time shown).
- **GLIDE:** slides and hammer-ons glide to the new note on single-note sounds; picked notes always start on their own
  pitch. OFF jumps.

**FILTER page**
- **ENV:** how far the filter (and on the sync sounds the pitch sweep) moves at each pick: -50 none, +50 twice.
- **RESO:** the filter's resonance.

### CTRL 1: each sound's own setting

| On screen | What it does | Sounds |
| --- | --- | --- |
| **DRIVE** | Left: cleaner; right: grit, up to 16 times. | SYNC LEAD, LADDER LEAD, ODYSSEY LEAD, HOOVER, OB PAD, BREATH HORNS, FAT BASS, ACID BASS, SUB BASS, TAL 101 BASS, RAVE ORGAN, POLY BRASS, SQ PROPHET |
| **WIDTH** | The pulse's width: thin at the left, square and hollow at the right. | SH-101 LEAD, MARS LEAD, CHIP LEAD, PUNCH BASS, SH-101 BASS, M1 PIANO |
| **WOBBLE** | The sound's built-in wobble (vibrato, filter or pulse sweep), deeper and faster to the right. | SPOOKY 8-BIT, POLY PAD, STRINGS, VECTOR PAD, JP WARM PAD, AM STRINGS, AAH CHOIR, HEAVENS GATE |
| **FM** | The FM depth: a plain tone at the left, double at the right. | FM PIANO, FM CHORUS EP |
| **DETUNE** | How far apart the seven saws are. | SUPERSAW |
| **WAVE** | Any of the Sound Generator's 32 waves, by name, each at Pulse's loudness. | SG SYNTH |
| **ENV** | The Sound Generator ENV preset: OFF, Pluck, Perc, Keys, Pad, Swell, Bass, Acid, Sweep, FPad. | SG ORGAN |

## The 32 sounds

Pads 1-8 play **single notes**; pads 9-16 play **chords** (up to 6 notes, or the number shown).

| Pad | Bank 1 (SHIFT + pad 1) | Bank 2 (SHIFT + pad 2) |
| --- | --- | --- |
| 1 | SYNC LEAD: a hard-synced saw swept down on each pick (MS-20 / Mono/Poly style) | BREATH HORNS: a breathy saw through a resonant formant, an octave down (Wavestation style) |
| 2 | LADDER LEAD: three saws through a driven ladder filter, glide, vibrato (Minimoog style) | SG SYNTH: the Sound Generator as one patch: any of its waves (CTRL 1), DUTY (CTRL 2), the ENV preset on the FILTER page; starts as Pulse, DUTY 30, ENV Pluck |
| 3 | SH-101 LEAD: pulse, saw and a deep sub, bright filter, glide | FAT BASS: saw and a pulse an octave down, driven ladder (Moog style) |
| 4 | MARS LEAD: a bright square lead, glide, delayed vibrato (ProMars style) | ACID BASS: a saw through a squelchy resonant filter, slides (303 style) |
| 5 | ODYSSEY LEAD: two saws, a resonant filter opening slowly (Odyssey style) | PUNCH BASS: pulse and sub, a short filter snap (SH-101 style) |
| 6 | CHIP LEAD: a bare 25% pulse, 8-bit style | SUB BASS: a sine an octave down with a short thump (808 style) |
| 7 | HOOVER: a rave hoover diving onto the note, long glide | SH-101 BASS: square and saw an octave down, a closing resonant filter |
| 8 | SPOOKY 8-BIT: squares an octave apart, a slow fall, an octave down | TAL 101 BASS: saw, pulse and sub an octave down, filter snap |
| 9 | POLY PAD: saw and a slowly swept pulse with a sub (Juno style) | FM PIANO: FM electric piano with a bright tine (DX7 style) |
| 10 | STRINGS: a string machine, two detuned saws | M1 PIANO: a bright house piano (M1 style) |
| 11 | VECTOR PAD (3 notes): Sound Generator waves crossfading (Wavestation style) | FM CHORUS EP: FM electric piano (System-8 style) |
| 12 | OB PAD: two saws swelling through a resonant filter (Oberheim style) | SG ORGAN (4 notes): the Sound Generator's Organ wave |
| 13 | JP WARM PAD: saw and square with filter drift, an octave down (Jupiter-8 style) | RAVE ORGAN (4 notes): a house organ stab |
| 14 | AM STRINGS: detuned strings, an octave down (JX-8P style) | POLY BRASS: two detuned saws, a filter blooming on each note |
| 15 | AAH CHOIR (3 notes): three formant "aah" voices | SQ PROPHET: saw and pulse an octave down, a warm filter (Prophet style) |
| 16 | HEAVENS GATE: a slow dark-to-bright swell (Wavestation style) | SUPERSAW (3 notes): seven detuned saws (JP-8000 style) |

The names describe the style each sound is modelled on; no samples or other firmware are used.

## How it follows your playing

**Single-note sounds** (pads 1-8, or any sound on VOICES MONO) take their notes from a note tracker that reads the pitch
of what you pick. One note at a time, every pick attacks (repeats too), a newly fretted and picked note attacks; bends,
slides and hammer-ons move to the new pitch without a new attack (gliding if GLIDE is set). The note ends when you let
go.

**Chord sounds** (pads 9-16, or VOICES 2-6) work the way BOSS's SY pedals do: the guitar is split into 49 semitone
bands, from the low E to the high E's 24th fret, and each string you hear drives a voice of its own, at its exact
pitch (bends and vibrato as you play them) and level. Your pick starts every voice's attack and filter sweep; a string
that starts ringing without a pick fades in softly; a voice that changes note fades out and in instead of jumping.

## Guitar notes on the Sound Generator and the kits

With **EXT SOURCE on**, opening the **Sound Generator** (SHIFT + RECORD SETTING) or the **kits** (SHIFT + PATTERN
EDIT) lets your guitar play it. The guitar notes are on by default; **HOLD + RECORD SETTING** (Sound Generator) or
**HOLD + PATTERN EDIT** (kits) switches them off and on, and the choice is remembered. While they play, the guitar synth
is quiet on that page.

- **Sound Generator:** one note at a time, like a MIDI keyboard on its channel (a strummed chord plays one note).
  Slides and hammer-ons play the new note. The Sound Generator plays MIDI notes an octave low, so set OCT (VALUE menu)
  to +1 to hear your guitar's own pitch. Your pick sets the velocity (about 50 to 127), and LEVEL scales it. With ARP
  on, the arp plays your note.
- **Kits:** each pick strikes the pad of its note name, in every octave (slides and hammer-ons don't strike):

  | Note | E | F | F# | G | G# | A | A# | B | C | C# | D | D# |
  | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
  | Pad | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |

  Pads 13-16 stay for your hands.
- **SENS** on the guitar synth's TRACK page also sets how soft a pick can be here.
- The guitar notes listen to anything on the input, a mic too: switch them off when you don't want that.

## MIDI out

Turn **PAD Note Out** on (SHIFT + pad 13 > SYSTEM > the MIDI tab). Then, on the Sound Generator page and the kits (and
the looper reached from them with MARK), notes go out the same way stock's pad notes do:

| You play | Sound Generator | Kits |
| --- | --- | --- |
| A pad (ARP off) | The note you hear, on the Sound Generator's channel | Pads 1-16 = notes 36-51, on the kits' channel |
| With ARP on | The arp's notes | The arp's notes, as their pads' notes |
| The guitar | The note you hear (slides and hammer-ons too) on the Sound Generator's channel, and its pad (36-47) on the kits' channel, on picks | The pad it strikes (36-47) on the kits' channel, on picks, and the note on the Sound Generator's channel |

- **The guitar sends on both channels**, so a synth and a drum module can follow it together (one channel only when
  both modes share it).
- **Each mode has its own MIDI channel:** set M.CH (VALUE menu) in each mode. MIDI in follows the mode's channel too.
  At power-on the kits are on **10** (General MIDI drums) and the Sound Generator on 16 (or the project's M.CH).
- **Every note gets its note-off,** also when you leave the page, switch PAD Note Out off, change M.CH or switch modes.
- **Velocity:** pads send theirs, the guitar its pick's (not scaled by LEVEL), the arp its own.
- **Not sent:** the guitar synth's sounds, MIDI that comes in (stock's Soft Through does that), and sample pads (they
  stay stock's PAD Note Out).

## What is saved

- **The guitar synth:** the current sound, each sound's settings (main, OTHERS, SHAPE and FILTER pages), the TRACK page,
  OUT and the guitar notes switch are saved on the SP (`B:/_sy_sounds.bin`, one set for the unit, not per project), at
  the next button release after a change. If you switch the SP off right after turning knobs, press and release a
  button first (EXIT, for example).
- **At power-on** the guitar synth is off (HOLD + EXT SOURCE, or opening its screen, switches it on), the kits' MIDI
  channel is 10 and the CPU readout is off.
- **Testers of the test builds start fresh:** v9.53 doesn't read the test builds' settings files.

## The CPU readout

Hold **EXIT** for one second on the main screen (no SHIFT, nothing else pressed) to show it, and again to hide it. EXIT
still does its own job.

| Line | Example | Means |
| --- | --- | --- |
| 1 | `E2 +3c Q92` | The note the tracker holds; how far the newest reading is from it, in cents; its quality (85 or more is clean). |
| 2 | `82.4Hz LV45 X1` | The newest reading's frequency; the input's peak in % of full scale; EXT SOURCE on (X1) or off. |
| 3 | `SY 9/12 B14` | The guitar synth's average/peak share of each audio block (%) and how many bands sound; or SY OFF / SY SLOW. |
| 4 | `AVG 25 N12 P14` | The average ms from a pick to the tracker's note over N notes; P picks heard. |
| 5 | `TRK 4/6 MIX 9` | The note tracker's average/peak share (or OFF / SLOW); the mixer's average share. |
| 6 | `MAX 30 OVR 0` | The worst block since the readout came on (%), and blocks that ran over. |

If the synth ever needs more than 90% of the audio time twice in a row, it stops itself to protect the audio (SY
SLOW). Switch EXT SOURCE off and on to start it again. The heaviest sounds are AAH CHOIR and RAVE ORGAN; both play
fine on the unit.

## Tips and known limits

- **Latency:** single notes start about 7 ms (high strings) to 17 ms (low strings) after the pick, plus about 4 ms
  through the SP; chord sounds reach half their level about 30 ms after a low E pick, 7-18 ms on the other strings.
  Low strings are slowest because their waves are slowest.
- **Use a clean, not too hot signal** (see Setting up). Distortion and clipping make extra notes.
- **Chord sounds** also play some of the guitar's overtones (faded 12 dB); the 3- and 4-note sounds cover fewer notes
  of a big chord. For single-note lines on a chord sound, use VOICES MONO.
- **Repeated picks on one string** can come in soft on chord sounds; single-note sounds attack every pick.
- **Recording:** on ROUTING Mix, takes made while the synth or guitar notes listen have no BUS 3/4 effects; on ExtIn,
  the synth is recorded without its bus effect, and without the pads or the Sound Generator.
- **If the SP ever restarts by itself, or the synth stops and a box reads SY CRASH,** photograph the box and report it:
  it shows where the code stopped.

## Not yet checked on the unit

- Whether stock's red "input too hot" blink shows while EXT SOURCE is green (it probably does: the effects chip paints
  it itself).
- OUT: BUS 2 and BOTH through BUS 2's effect; MIDI out through the MIDI OUT jack (USB works).
- The guitar synth's settings coming back after a restart (they use the same saving as the hidden effect settings,
  which do).
- A project saved in drum mode: the project file still keeps one M.CH, which the Sound Generator takes after a reload.
- On the looper screen, VALUE + RECORD SETTING may also do VALUE's own press there.
