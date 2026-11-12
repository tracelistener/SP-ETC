# Third-party notices

## DM-404: core/fx/fxmap.json

FX deep edit (`synth/fx_deep_edit.c`, built by `synth/build_fx_deep_edit.py`) takes its effect parameter table
from DM-404's `core/fx/fxmap.json` (https://github.com/nickpetty/dm-404): the parameter IDs, names and ranges
of the settings it edits. The table is compiled into the firmware overlay in `kits-data.js`.
That part of DM-404 is under the MIT License:

```
MIT License

Copyright (c) 2026 Nicholas Petty and the dm-404 contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## DOOM OS 0.6.1 ED5E

The base is DOOM OS 0.6.1 (build ED5E) by Quintus Oostendorp / Klangfeld Labs, under the MIT License in
[LICENSE](LICENSE).

## TONE3000 embedded NAM: synth/namtest/third_party/tone3000-embedded

The NAM test (`synth/namtest`, a development test build; it is not part of the firmware the patcher makes) uses
TONE3000's embedded Neural Amp Modeler code, with NeuralAmpModelerCore's A2-Lite test model and a golden input. Both
are under the MIT License (Copyright (c) 2026 TONE3000; Copyright (c) 2023 Steven Atkinson). The full texts are kept
beside the code, in that folder's `LICENSE` and `NOTICE`.
