# SY synth test 9: test 8 with the quieter Sound Generator and kits

A test build: {{PARENT_REVISION}} (v9.52 with LEVEL for MIDI notes, and the Sound Generator and kits at about a
sample's loudness) plus the SY synth and guitar synth test 6 on the Sound Generator page. Not for sharing. To go back,
patch v9.52 again.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

What's new:

- **The Sound Generator and kits are quieter** (combined-test19). One Sound Generator note at LEVEL 127 now peaks at
  about -12 dBFS (it was -1.2), four notes at about -1.5 dBFS without clipping, and kit hits at -6.4 dBFS at most (they
  were -1.3). REC and BOUNC record the same as before.
- Everything from test 8 stays:
  - the guitar synth starts from its screen (hold EXT SOURCE, press RECORD SETTING) and plays until EXT SOURCE goes off;
  - push VALUE on the screen for the synth's bus (OUT: DRY / BUS 1 / BUS 2 / BOTH);
  - LEVEL turns down MIDI notes on the Sound Generator.

1. Volume low at first. On the plain Sound Generator, play single notes and four-note chords at LEVEL 127, then a
   sample pad: are they about as loud?
2. On a kit, play hits against a sample pad.
3. Test 8's steps: EXT SOURCE on (only your guitar), the guitar synth screen (the synth), EXIT (still the synth),
   EXT SOURCE off and on (only your guitar).
4. The synth on BUS 2 with DELAY on BUS 2 (OUT: BUS 2), then BUS 1 and BOTH.

Tell me: are the Sound Generator and kits about as loud as a sample now? Does the synth start only from its screen?
Does it get the effect on BUS 2 and BUS 1?
