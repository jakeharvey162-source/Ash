# Third-party notices

## ronitparikh/jarvis

Ash's optional desktop voice runtime adapts portions of the local wake-word
listener, NDJSON event-stream architecture, and Claude Code CLI routing from:

- Project: https://github.com/ronitparikh/jarvis
- Source revision reviewed: `55bf5552c66627bbbaa53659de89ef2ddc650918`
- Copyright (c) 2026 Ronit
- License: MIT

Ash intentionally does not copy Jarvis's default pre-authorization of Bash or
computer-control tools. In Ash, optional Claude Code tool access is disabled
by default and only passes an allowlist when the user explicitly enables it.

### MIT License

Copyright (c) 2026 Ronit

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


## OpenJarvis

Ash's September 2026 desktop intelligence upgrade uses both an Ash-native
integration layer inspired by OpenJarvis's modular architecture and an optional
runtime bridge to the published OpenJarvis Python package:

- Project: https://github.com/open-jarvis/OpenJarvis
- Python package: OpenJarvis 1.0.3
- License: Apache-2.0
- Ash bridge: desktop_worker/openjarvis_bridge.py
- Optional dependency: desktop_worker/requirements-openjarvis.optional.txt

The Windows full-companion installer attempts to install the OpenJarvis
specialist. Ash remains functional when that optional package cannot be
installed. OpenJarvis is not granted unrestricted shell or computer-control
authority by the Ash bridge. Ash keeps its own security model, device pairing,
provider gateway, builder, confirmation gates, voice runtime and computer
controller.
