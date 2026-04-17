# Typing Simulator

Typing Simulator is a small Windows desktop app that takes source text from its own input box and replays it into any focused text field by sending real keyboard input through the Windows `SendInput` API.

It is designed for cases where the destination text box blocks paste and requires typed input instead.

## What it does

- Reproduces the source text in order with simulated keyboard input
- Works with normal browser text fields as long as they accept typed characters
- Preserves line breaks and tabs as far as the target field allows them
- Lets you choose a countdown delay so you can click into Chrome or another browser before typing starts
- Supports optional humanized timing based on typing speed and approximate QWERTY travel distance
- Uses only the Python standard library

## Run it

```powershell
python main.py
```

## Basic workflow

1. Paste or enter the text in the large source area.
2. Set the countdown and words-per-minute pace.
3. Click `Start Typing`.
4. While the countdown runs, click into the destination browser field.
5. Let the simulator type the content. Hold `Esc` to cancel.

## Notes

- The app types into whichever field currently has focus when the countdown ends.
- New lines are sent as the `Enter` key. In single-line fields, the browser or page may reject them.
- Tabs are sent as the `Tab` key. Some sites treat `Tab` as focus navigation instead of literal indentation.
- Characters not available through the current keyboard layout fall back to Unicode input packets for reliability.

## Verification

```powershell
python -m unittest discover -s tests -p "test*.py"
```
