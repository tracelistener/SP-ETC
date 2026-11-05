# The Sound Generator's level: LEVEL for MIDI notes (sg-level-test1), the output level (sg-level-test2)

A fork user's MIDI keyboard has no velocity: every note arrives at 127, and the Sound Generator plays it at full
volume with no way to turn it down. They asked for "a setting in tone generator to set a fixed velocity (or more like a
volume setting)". Test 1 makes LEVEL (CTRL 3) that volume for MIDI notes (sections 1-6, `combined-test18`). Test 2
(section 7, `combined-test19`) turns the Sound Generator and the kits down to about a sample's loudness. The user's
words: "at 127, sound generator is way too loud especially with 4 notes at a time. it should be similar to loudness
of a sample. same with kits". Both go on top of the finished combined APP1 (combined-test17 = v9.52, after the fast
boot and the kit footer), as one module.

## 1. What stock does (5.52, as v9.52 has it)

- **A note's level is its velocity.** The pad note-on (`0x80132428`) and the MIDI note-on (`0x80132118`, reached
  through v9.5's `midi_event`) both set the voice's level to velocity x 100: `+0x74` (the level now) and `+0x198`
  (the level it moves to). The render loop (`0x1cbcc`) moves `+0x74` one step a sample toward `+0x198`, and the
  oscillator scales each sample by `+0x74 / 12700` (velocity 127 = unity).
- **LEVEL is not a value of its own.** CTRL 3 (and CC 72 on M.CH, `kits/kit_midi.inc`) calls SetParam (`0x800dd0c0`,
  setting `0x7d`), which clamps the value to 0..127 and goes through `0x1ff20` to v9.5's parameter engine
  (`0x8353b180`). The engine runs the stock setter on all four voices: `+0x198` = LEVEL x 100 (`+0x74` too on an idle
  voice). LEVEL's getter (`0x80020480`) reads the singleton's `+0x198 / 100`. So turning LEVEL moves the notes that
  sound, and the next note sets its voice's level from its own velocity again. LEVEL then reads that note's velocity:
  in the emulator, a pad hit at 100 makes LEVEL read 100, a MIDI note at 90 makes it 90. Kits save stores that number
  with the project.
- **Only the page's pads read LEVEL.** With FIXED VELOCITY on (SHIFT + pad 1, project setting `0xdb`), the Sound
  Generator page's pad press uses LEVEL as its velocity (`0x8015c0c8`). With it off, a pad plays at its own velocity.
  MIDI notes never read LEVEL.
- **Velocity sets only the level** on the Sound Generator. The v9 envelopes and filters (`env.c`) don't read it. Drum
  mode's hits are pad strikes with each pad's own Level.

## 2. What this build does

- **LEVEL is a value of its own.** `sgl_param` (at SetParam's jump `0x1ff20`) keeps every LEVEL that SetParam sets:
  CTRL 3, CC 72, and a project's saved LEVEL (kits save, at each project load). Then the voices get it as before.
  `sgl_level_get` (LEVEL's getter case) returns that value, so the screen, FIXED VELOCITY's pads and kits save read the
  LEVEL that was set. The power-on LEVEL is 127, as in the stock data.
- **MIDI note-ons play at velocity x LEVEL / 127**, at least 1, so a note-on never becomes a note-off. This covers
  melodic mode, ARP on or off, and either M.CH route (M.CH 16 through the channel-16 handler `0x8005a680`, another
  channel through the kits' note-on gate). Every Sound Generator MIDI note enters `arp_midi_event` (`0x83fa3448`),
  and `sgl_midi_gate` scales the velocity there:
  - ARP off: the stock MIDI note-on plays the scaled velocity.
  - ARP on: the arp holds the key at the scaled velocity, and its steps start at it.
  - At LEVEL 127 nothing changes.
- **A latched arp chord follows the knob.** A LEVEL change scales the keys the arp holds from MIDI again, from each
  key's own velocity (`sgl_vel`). This happens only on the SG page (the arp holds keys only there), with dispatch off,
  as the VALUE menu's arp steps do it. A pad key the arp holds keeps its velocity.
- **What stays as it was:**
  - drum mode;
  - the pads (with FIXED VELOCITY on, they play at LEVEL as stock does, which is now the LEVEL set);
  - note-offs;
  - sounding voices still follow a LEVEL change as stock (the setter sets them to LEVEL itself).
- **Side effects:**
  - The LEVEL readout no longer jumps to each note's velocity.
  - Notes no longer change the project as kits save sees it, so SG_KITS.BIN is written less often.
  - A project saved before this build keeps the LEVEL it saved, which was the last note's velocity at that save. On
    load, MIDI notes play at that LEVEL (the screen shows it) until CTRL 3 is turned.

## 3. Fixed velocity: not added

On the Sound Generator, velocity sets only loudness. A keyboard without velocity sends 127, and 127 x LEVEL / 127 is
LEVEL: LEVEL already is the fixed velocity for that keyboard. A separate switch would only matter for someone with a
velocity keyboard who wants every MIDI note equal. Stock has that switch for the pads only (FIXED VELOCITY), and tying
MIDI to it would take velocity away from players who keep FIXED VELOCITY on for their sample pads. If someone asks for
it, it is a few lines in `sgl_midi_velocity` (play at LEVEL when project setting `0xdb` is 1).

## 4. Build

```
python synth/build_sg_level.py release/combined-test17/SP404MKII_APP1.bin OUT_DIR --zig ZIG \
    --kits release/bounce-3-test7/kits-manifest.json --revision combined-test18
```

The module (`sg_level.c`, Zig 0.13.0 `-Os`, 552 bytes) goes in a new boot copy row in a 2 KB slot at `0x83FA1800`:
past v9.6's scale module (ends `0x83fa17ec`), below the kit stage (`0x83fa2000`). No fork branch uses that RAM (the
fork's other modules take slots from `0x83FC9000` up). The builder checks that no row overlaps the slot and that
nothing in the input refers to it.

| Address | Bytes | Was | Now |
| --- | --- | --- | --- |
| `0x0001FF20` | 10 | SetParam's SG call: jump to v9.5's parameter engine `0x8353b181` | jump to `sgl_param`, which goes on there |
| `0x80020480` | 12 | the getter's LEVEL case: `+0x198 / 100` | jump to `sgl_level_get` (+ nop) |
| `0x83FA3448` | 10 | `arp_midi_event`'s first three instructions | jump to `sgl_midi_gate`: the velocity, those three, on at `0x83fa3452` |

- **Guards:** 11 SHA-256 ranges, plus the kit stage (v9.46's module as booted, the kit footer's byte aside):
  - SetParam and its SG case;
  - v9.5's parameter engine;
  - the stock setter and getter, and GetParam's SG case;
  - the channel-16 note handler;
  - the stock MIDI note-on;
  - the render loop's level step;
  - the SG pad's FIXED VELOCITY code.
- **No direct branch** in the image's copy rows lands inside a patched span.
- **The one patch inside another feature's guard:** `0x83FA3448` is inside kits save's guard over the whole kit stage
  (`0x83fa2000..0x83fc8450`). Kits save checks the kit stage for the addresses it uses. The patch moves none of them,
  and kits save never calls `arp_midi_event`. The kit footer's byte sits in the same guard (combined-test6 on).

## 5. Checked (Unicorn)

`test_sg_level.py BUILD PARENT KITS_MANIFEST` runs the build and combined-test17 side by side on `test_kit_midi.py`'s
machine (the real stock MIDI dispatcher). 26 of 26 pass:

- **Layout:** the patches and module in place, and the guards holding.
- **LEVEL:** set and clamped as stock, and it reads as set after pad and MIDI notes.
- **MIDI, ARP off:** every LEVEL (127, 100, 64, 40, 1, 0) x velocity (127, 100, 64, 10, 1) on M.CH 16 and M.CH 1.
  Note-offs and velocity-0 note-ons still release.
  - A note at velocity v and LEVEL l equals the parent's note at the scaled velocity, voices and audio sample for
    sample.
  - At LEVEL 127, a chord-and-steal sequence is the parent's.
- **ARP on:**
  - keys are held at the scaled velocity and the steps start at it;
  - a LEVEL change scales the MIDI keys again and not the pad key, and does nothing off the SG page;
  - at LEVEL 127 the steps are the parent's;
  - a key at 127 with LEVEL 64 steps exactly like the parent's key at 64.
- **Drum mode and pads:** as the parent's at any LEVEL. The SG pad press with FIXED VELOCITY on plays at the LEVEL
  set; the parent plays at the last MIDI note's velocity.
- **CC 72** sets LEVEL, and MIDI follows it.

The fork's other suites are in COMBINED.md section 19.

## 6. Checked (DM-404)

The real 5.52 firmware on an emulated i.MX RT1060, with snapshot disks. Each build boots, the Sound Generator page opens
(SHIFT + RECORD SETTING), and MIDI note 60 plays on channel 16 (USB-MIDI, cable 8). The table gives the output peak
of each note, read 0.35 s in for 0.5 s.

| CTRL 3 | LEVEL (screen) | vel 127 | vel 64 | combined-test17: vel 127, vel 64 | combined-test17 at the scaled velocity |
| --- | --- | --- | --- | --- | --- |
| at boot | 127 | 1780 | 1032 | 1780, 1033 | |
| 3000 | 35 | 565 | 275 | 1780, 1033 (LEVEL back to 127) | vel 35: 565, vel 17: 275 |
| 2000 | 67 | 1081 | 533 | 1780, 1032 | vel 67: 1081, vel 33: 533 |
| 40 | 127 | 1780 | 1032 | 1780, 1033 | |

- **The reported problem, on combined-test17:** CTRL 3 changes nothing for MIDI, and the next note puts the screen
  back to Level 127.
- **combined-test18:** a note at velocity v and LEVEL l peaks as combined-test17's note at v x l / 127 does, and the
  screen keeps showing the LEVEL set. That covers the knob path, the getter on the screen and kits save's restore at
  boot on the real firmware.

**Not checked:** the unit.

## 7. The output level (sg-level-test2, combined-test19)

### Measured (combined-test18)

The scale is the bus's signed 16-bit scale. A sample reaches the bus at that scale: on DM-404, a sine fed into the
input at -6 dBFS, sampled to a pad and played at full press, comes back at -6 dBFS. So a normalized sample at full press
peaks at 0 dBFS there. The main outputs keep 24 dB above that: the bus words go into the 20-bit DAC slots unsaturated
(`0x1c840`). The 16-bit ceiling is the sampling path's (RESAMPLE, skip-back, the SG's REC) and the kit stage's knee.

Emulator, at LEVEL 127, velocity 127, ENV OFF:
- **Raw:** one voice peaks at 16384 (-6 dBFS) for the full-scale TYPEs. Four voices reach up to 65532 (+6 dBFS).
- **The kit stage's master (since v9.39):** x2, then a knee from 24576 to 32000. One note comes out at -1.2 dBFS,
  squashed by the knee, with a sine's RMS at -3.6 dBFS: as loud as a normalized sine sample. Four notes come out at
  -0.3 dBFS, RMS -2.5 dBFS, held by the knee.
- **Kits:** raw hits peak at -6.3 dBFS at most (medians -7 to -12). After x2 they sit in the knee at -1.3 dBFS (8 to 16
  pads per kit). Four pads at once reach +4 dBFS raw.

DM-404 gives the same Sound Generator numbers through the real firmware: one note -1.2 dBFS peak, RMS -3.6 dBFS; four
notes -0.3 dBFS, RMS -2.5 dBFS.

### What this build does

The same stage runs on the kit stage's own capture of the bus, with another gain:

| | Live | REC / BOUNC | Was |
| --- | --- | --- | --- |
| Melodic | x0.5 | x1 | x2 |
| Drum mode | x1 | x2 (unchanged) | x2 |

- **The REC gain is twice the live gain**, because v9.5's export mix halves each voice. So a REC'd or bounced pad
  plays back at the level you heard. BOUNC writes exactly what it wrote before.
- **The knee is unchanged.** The gains are powers of two and the knee is the kit stage's own expression
  (`-ffp-contract=off`), so for the same input the results equal the kit stage's.
- **Melodic x0.5:** one voice at full level is -12 dBFS (RMS -15 dBFS for a sine), about as loud as typical normalized
  sample material (RMS -12 to -18 dBFS). Four voices can reach 0 dBFS only when in phase, so they never clip; the knee
  touches only those peaks.
- **Drum x1:** the kit engine's own level. Hits peak at -6.3 dBFS at most and never reach the knee alone.
- **Not one gain for both, and not per-voice headroom:** one gain for both would make either the kits too quiet or
  four SG notes clip. A gain that follows the number of sounding voices would pump as notes start and stop.

| Patch | Bytes | Was | Now |
| --- | --- | --- | --- |
| `0x0001FDD4` | 8 | the SG render stub's exit: movw/movt to `kit_mix_gate` | `sgl_mix_gate`: the same three movs, bl and pop, with `sgl_mix_finish` |
| `0x8353BA06` | 8 | the REC exporter bridge: movw/movt to `kit_export_mix` | `sgl_export_mix` |

- **New guards:** the render stub, the export bridge, v9.5's `export_mix`, and `kit_mix_gate`, `kit_mix_finish` and
  `kit_export_mix` by their instructions (the capture's state: count and bus at `0x83fc8324`/`0x83fc8328`, the bus
  before the SG at `0x83fc59e8`). No step guards either site.
- **The SY builds** (`claude/tune-test`) shape-check the render exit's target; `sgl_mix_gate` has `kit_mix_gate`'s
  shape. The module (912 bytes) stays in its 2 KB slot at `0x83FA1800`, clear of the SY slots.

### After (combined-test19)

| | combined-test18 | combined-test19 |
| --- | --- | --- |
| One note (full-scale TYPEs) | -1.2 dBFS peak (in the knee), RMS -3.6 (sine) | -12.0 dBFS peak, RMS -15.1 (sine), knee never |
| Four notes (C E G B) | -0.3 dBFS, RMS -2.5, knee on 3,000 to 6,000 samples | -1.2 to -2.0 dBFS, RMS -8.8, knee on in-phase peaks only |
| Kit pads alone | -1.3 dBFS, 8 to 16 pads per kit in the knee | at most -6.4 dBFS, none in the knee |
| Four kit pads at once | in the knee | up to +4 dBFS raw, held by the knee under 32000 |

DM-404 on combined-test19:
- The sample reference is unchanged (-6 dBFS).
- One note peaks at -12.0 dBFS, RMS -15.1; four notes at -1.3 dBFS, RMS -9.1. These match the emulator.
- The kit readings there missed the onsets (the measuring window starts after each hit), so the kit figures above
  are the emulator's.

`test_sg_level.py` (36 of 36) checks the stage sample for sample against a float32 model of the kit stage's knee:
melodic and drum mode, other audio already in the bus, and the REC mix (melodic x1; drum x2, the parent's exactly).
The SG's raw mix is the parent's.
