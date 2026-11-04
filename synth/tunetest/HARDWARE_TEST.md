# SY synth test 1: a polyphonic guitar synth, the way BOSS's SY pedals do it

A test build: {{PARENT_REVISION}} (v9.52) plus the SY synth, and guitar synth test 6 on the Sound Generator page. Not
for sharing. To go back, patch v9.52 again.

| File | SHA-256 |
| --- | --- |
| SP404MKII_APP1.bin ({{APP1_SIZE}} bytes) | `{{APP1_SHA256}}` |
| SP404MKII_APP0.bin (stock 5.52) | `{{APP0_SHA256}}` |

What's new: on every screen except the Sound Generator's, the guitar plays a synth that follows each string on its
own, so chords and bends come through. The sound is a saw through a filter that opens the harder you pick. Like
tests 5 and 6, it needs EXT SOURCE on and ROUTING on ExtIn. The Sound Generator page still plays guitar synth test 6,
unchanged.

1. Volume low at first. Guitar in, EXT SOURCE on, input FX Bypass, ROUTING ExtIn. Stay on the main screen.
2. Play single notes, chords and bends. You hear the synth along with your guitar.
3. To hear the synth alone: hold REMAIN and press EXT SOURCE until it's lit, which puts the input on BUS 1. Then put
   the Isolator on BUS 1 with all three bands down, as you did for test 4's check.

Tell me: do chords come out as chords? Do low notes come in too late? Any wrong notes, warbling or crackles? If it
stutters, hold EXIT for a second on the main screen and tell me the SY and MAX numbers.
