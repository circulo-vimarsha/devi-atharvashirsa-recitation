# Devī Atharvaśīrṣa — whole recitation

A single static page for reciting the Devī Atharvaśīrṣa along with a teacher's voice:
the whole text is shown, and as the recording plays each word lights up and the page
scrolls to keep the voice's line in view. Made for the Vimarsha study circle.

The page asks for the circle's password. The text, the word timings and the recording are stored
here only encrypted (AES-256-GCM, key from the password by PBKDF2); the browser decrypts them once the
password is typed and remembers it on that device. A short password keeps out casual visitors and
search engines, not a determined guesser.

- **Speed**: 0.5× to 1.5× in steps of 0.05, pitch kept (slider, − / + buttons, or the − + keys).
- **Follow**: the page follows the voice; scroll by hand and it waits, with a *Follow the voice* button to come back.
- **Tap a word** to hear the recitation from there. ⏮ ⏭ (or ← →) move by line, space plays and pauses.
- **IAST** on or off, text size A− / A+, Spanish or English labels. Choices are remembered on the device.
- **Links to a moment**: `…/#t=42` opens at 42 s.
- Phone, tablet and laptop layouts; keeps the screen awake while playing; lock-screen controls.

## Files

| Path | What |
| --- | --- |
| `index.html` | the page (no build step, no libraries) |
| `sealed/lock.json` | salt and iteration count for the key |
| `sealed/data.bin` | encrypted: the Sanskrit text (Devanagari and IAST, verse by verse, line by line) and when each word sounds |
| `sealed/audio.bin` | encrypted: the recording (mp3) |
| `tools/build_data.py` | writes `private/text.json` from the akṣara app's devi data |
| `tools/align.py` | times every word in a continuous recitation, writes `private/timing.json` |
| `tools/seal.py` | encrypts `private/` into `sealed/` with the password |

`private/` holds the plain files and is never committed.

## Updating the recording

```sh
python3 tools/build_data.py ~/canopy-sync/sanskrit/.devi            # the text
python3 tools/align.py recording.wav --from-verse 1 --start 5 \
        --who "Ācārya Sthaneshwar Timalsina" --report report.txt     # the timing (read report.txt)
# encode private/recitation.mp3 (mono, 96 kbps CBR), then
python3 tools/seal.py <password>
```

`align.py` needs no speech recognition: the reciter breathes between phrases, and a dynamic programme
shares the words out among the phrases at a steady pace, preferring line ends. `--start` skips what is
chanted before the text begins. In the current recording the viniyoga is not recited and verses 1–3
were checked against Guruji's teaching recording of them (they agree to the phrase).

## Run it locally

Any static server over http on localhost or https (WebCrypto needs a secure context).

## Publish on GitHub Pages

Settings → Pages → Deploy from a branch → `main`, folder `/`.
