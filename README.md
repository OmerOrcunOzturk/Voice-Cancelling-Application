# Mikrofon Filtre (Filtre)

A **real-time microphone processing** desktop app for Windows. It cleans your mic input with spectral noise reduction and a noise gate, then routes the result to the audio output you choose. It works well with **VB-Audio Virtual Cable** (or similar) when you want a clean mic feed into Discord, Zoom, or other VoIP apps.

Built with [sounddevice](https://python-sounddevice.readthedocs.io/) / PortAudio for low-latency **duplex** audio and [PySide6](https://doc.qt.io/qtforpython/) for the UI.

**Project status:** Experimental / proof-of-concept. Intended for learning and demos; Windows audio routing and latency can be finicky, and the DSP is not production-grade.

---

## Features

- **Live processing:** Full-duplex stream — input and output are driven in the same callback for stable timing on Windows.
- **Spectral noise reduction:** FFT-based processing with an adaptive noise profile and magnitude shaping.
- **Noise gate:** Attenuates audio below a threshold to reduce background hiss when you are quiet.
- **Controls:** Input gain, output level, noise-reduction strength (%), gate threshold (dB), and speaker monitoring (on/off).
- **Device management:** Input/output lists with refresh; prefers virtual-cable-style outputs when picking a default.
- **UI:** Card layout, light/dark theme, live level meter.

---

## Requirements

- Windows 10 or later (development and testing target)
- Python 3.10+ recommended
- A microphone and audio output (PortAudio-compatible drivers)

### Python packages

```text
pip install sounddevice numpy PySide6
```

The entry script (`filtre.py`) prints a clear message if a dependency is missing.

---

## Install and run

```bash
git clone <repo-url>
cd Filtre
python -m venv .venv
.\.venv\Scripts\activate
pip install sounddevice numpy PySide6
python filtre.py
```

---

## Using VB-Cable (virtual cable)

A virtual cable lets you hand **processed audio to a chat app as if it were a separate microphone**.

| Step | What to select |
|------|----------------|
| **Input in this app** | Your physical microphone |
| **Output in this app** | **`CABLE Input (VB-Audio Virtual Cable)`** — the *playback* endpoint; audio is written **to** the cable here |
| **Microphone in Discord / Zoom** | **`CABLE Output`** — the *recording* endpoint; the app reads **from** the cable here |

**Common mistake:** Choosing speakers as the filter output, or selecting the wrong cable endpoint in the chat app (mixing up Input vs Output).

**Monitoring:** If the filter output is **only** `CABLE Input`, nothing is sent to your physical speakers. To hear yourself, enable **Listen to this device** for **CABLE Output** in Windows and route playback to your speakers/headphones.

---

## Project layout

```text
Filtre/
├── filtre.py                 # Entry: dependency checks + main
├── filtre_app/
│   ├── app.py                # QApplication bootstrap
│   ├── config.py             # Default sample rate, block size, UI constants
│   ├── ui/
│   │   └── main_window.py    # Main window, theme, controls
│   └── audio/
│       ├── processor.py      # sounddevice duplex stream, metering
│       ├── filters.py        # Spectral noise reduction + gate
│       └── devices.py        # Device enumeration, rate/channel negotiation
└── README.md
```

---

## Technical notes

- **Sample rate:** Default target is 48 kHz; `devices.py` picks a rate supported by both the chosen input and output.
- **Block size:** `DEFAULT_BLOCK_SIZE` (e.g. 1024) trades FFT work against latency.
- **Signal chain:** Microphone → input gain → spectral cleanup → gate → output level → selected output device (when monitoring is off, the output buffer is zeroed while processing can still run for metering).

---

## Troubleshooting

1. **No audio on the cable:** Confirm filter **output** is `CABLE Input` and the chat app **microphone** is `CABLE Output`.
2. **Duplicate devices (MME / WASAPI):** Try the other host API entry in the list.
3. **Exclusive mode:** Another app may have locked the device; close it and retry.
4. **Meter moves but chat has no audio:** Re-check routing with the table above.

---

## License

Add a `LICENSE` file to make terms explicit on GitHub if you have not already.

---

## Contributing

Issues and pull requests are welcome.
