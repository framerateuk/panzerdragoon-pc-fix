# Panzer Dragoon (PC, 1996) on modern PCs and the Steam Deck

## Why this exists

The PC version of Panzer Dragoon is a faithful conversion of the original Saturn game, and it has
beautiful music. Like a lot of Sega PC games from the 90s, it's tough to get running on modern
systems: its movies use a video codec nothing decodes any more, the title screen freezes waiting
for the CD player, the D-pad and Start don't work on a modern pad, and it looks for a CD drive.
This kit sorts all of that out, so it can be played again.

## What this does

Turns **your own** Panzer Dragoon PC CD into a folder that runs on the Steam Deck (Proton) or on
Windows 10/11, with no installer and no registry entries:

- **Copied straight from the CD**: the game runs from its disc files, so nothing is installed.
- **The movies play again**: they're Indeo 4.1, which neither Windows 10/11 nor Proton can decode.
  `build.py` re-encodes them to Cinepak at 640x400, frame for frame, and the movie player is patched
  to play them full screen and centred instead of small in a corner (or, on Windows, not at all).
- **CD soundtrack** from OGG files ripped from your disc, and a fix for the title screen freezing
  when you press Start (the game waited for a CD-audio message that never comes).
- **No black bars**: the game draws a 16:10 picture inside a 4:3 mode, so on the Steam Deck it
  fills the whole screen with nothing cut or stretched (thin bars at the sides on a 16:9 monitor).
- **Gamepad laid out like the Saturn pad**, with the D-pad and Start working on an Xbox-style pad.
- **Smaller fixes**: settings kept in the game folder, Esc quits, and the game no longer keeps a
  CPU core at 100% (a cooler, quieter Deck).
- **The CD check** is patched out (6 bytes; the space it frees holds the D-pad fix).

**No game files are in this repository.** Everything from the game comes from your disc when you
run `build.py`.

## What you need

| | |
|---|---|
| The game | The **Panzer Dragoon PC CD** (Sega, 1996, version "V1.000") as `.cue` + `.bin`/`.img` or CloneCD `.ccd` + `.img`, with its 15 audio tracks. `build.py` checks the exe and stops on another version. |
| Python | 3.8 or newer (python.org on Windows; already on macOS/Linux). |
| ffmpeg | `ffmpeg` and `ffprobe` on the PATH (Windows builds at ffmpeg.org). They re-encode the movies, and encode the soundtrack unless `oggenc` is there too. |
| dgVoodoo2 **2.79.3** | by Dege: [GitHub release v2.79.3](https://github.com/dege-diosg/dgVoodoo2/releases/tag/v2.79.3). Use 2.79.3: newer versions don't start under Wine/Proton. Keep the zip as downloaded. |
| ogg-winmm | by AyuanX: [GitHub releases](https://github.com/ayuanx/ogg-winmm/releases) (tested with v2025.01.16). Keep the zip as downloaded. |

## Build

```
python3 build.py PanzerDragoon.cue --dgvoodoo dgVoodoo2_79_3.zip --ogg-winmm ogg-winmm_binary.zip
```

creates `PanzerDragoon/` with `game/` and `panzer_launch.sh` (for the Steam Deck). The movie
encode is the slow part: about half an hour on an 8-core Mac, longer on fewer cores.

For Windows, add `--windows`. The movie player is placed differently and dgVoodoo copies it into
its picture (`EnableGDIHooking`); without that, Windows shows the movies' sound but no picture. No
launch script. `--out DIR` puts the result somewhere else.

The disc's original exe, movie player and Indeo movies are kept unchanged in `game/_spare/`.

## Play on the Steam Deck

1. Copy `PanzerDragoon/` to the Deck, for example to `/home/deck/Games/PanzerDragoon/`.
2. Desktop Mode: Steam > Add a Non-Steam Game > Browse > `.../PanzerDragoon/game/PANZERDG.EXE`.
   Rename the shortcut "Panzer Dragoon".
3. Properties > Compatibility: force **Proton 9.0**. Pin it rather than floating on Experimental.
4. Properties > Launch Options:
   ```
   /home/deck/Games/PanzerDragoon/panzer_launch.sh %command%
   ```
5. Launch: Sega logo, intro movie, title music. `launch.log` beside the script shows what it did.

## Play on Windows

Build with `--windows`, then run `game/PANZERDG.EXE`. A shortcut must start in the `game` folder.
dgVoodoo is needed on Windows too: Windows' own DirectDraw can't set the game's 640x480 16-bit mode
("No changed display mode(DirectDraw)").

## Controls

The pad is read as a Saturn pad (`[Input] Device=SEGA_DIGITAL` in `game/PANZERDG.INI`); F6 in the
game rebinds keys and buttons.

| Saturn | Does | Xbox-style pad / Steam Deck | Keyboard |
|---|---|---|---|
| D-pad | aim / move | left stick or D-pad | arrows |
| A, B, C | fire (hold and sweep: lock-on lasers) | A, B (C unbound) | X, V, B |
| X, Y, Z | camera distance | X, Y, View / Back | A, S, D |
| L, R | turn the view 90 degrees | LB, RB | Z, C |
| Start | start, pause | Menu / Start | Enter |
| - | quit at once | - | Esc |

Other keys: F1 help (needs WinHelp, which Windows 10/11 no longer have), F2 replay, F3 pause, F5
control type, F7 configuration (video mode, detail), F8 mixer (volumes).

## Tuning

- Video mode and detail: F7 in the game, or `[Screen]` in `game/PANZERDG.INI`. The shipped mode
  is 640x480 16-bit.
- Sharp pixels: `Resampling = pointsampled` in `game/dgVoodoo.conf`.
- The 4:3 frame with black bars back: empty `DisplayROI =` in `game/dgVoodoo.conf` (the movies are
  then placed for the 16:10 picture and won't line up exactly).
- Deck renderer: put `RENDERER=wined3d` (plain Wine DirectDraw) before the script path in the launch
  options. Default: dgVoodoo.
- Frame rate overlay on the Deck: a file `DXVK_HUD` beside the launch script holding `fps`.
- Music level: `CDDAVolume` in `game/winmm.ini` (0-100), or F8 in the game.

## Troubleshooting

- *"Please insert Panzer Dragoon CD."*: you're running the unpatched exe (from `_spare/` or a fresh
  copy of the disc).
- *No music*: `launch.log` must exist and show `WINEDLLOVERRIDES=winmm=n,b;...` (no log: the launch
  option is missing `%command%`), and `game/Music/Track02.ogg` must exist.
- *Movies with sound but no picture on Windows*: the folder was built without `--windows` (the
  Steam Deck build). Rebuild with `--windows`, or check `EnableGDIHooking = true` in
  `game/dgVoodoo.conf`.
- *A movie zoomed in, only its top-left part showing*: the other way round, a `--windows`
  movie player on the Deck, or a Deck one with `EnableGDIHooking` on. Use the build made for that
  system.
- *Movies black or missing*: the `.AVI` files in `game/` must be the re-encoded ones (about 375 MB
  for `EXOPEN.AVI`); the Indeo originals don't play on modern systems.
- *Judder on a G-Sync / FreeSync monitor*: turn variable refresh off for this game.

## What's in this repository

| File | What |
|---|---|
| `build.py` | Builds the folder: copies the CD's game files, patches the exe and movie player, re-encodes the movies, rips the soundtrack, adds the wrappers and settings. Python standard library only (plus ffmpeg). |
| `patch_exe.py` | The exe and movie player patches, each explained; also runs on its own. |
| `disc.py` | Reads the CD image: `.cue`/`.bin` or `.ccd`/`.img`, ISO 9660 and audio tracks. |
| `config/dgVoodoo-deck.conf`, `config/dgVoodoo-windows.conf`, `config/PANZERDG.INI` | dgVoodoo2 settings for each build; the game's settings with the pad set up. |
| `steamdeck/panzer_launch.sh` | Proton launch wrapper: DLL overrides. |
| `docs/TECHNICAL.md` | How each part works. |

## Credits

- **Team Andromeda** made Panzer Dragoon for the Saturn; **Sega** published the PC version under
  its Sega PC label. Please own the game: this kit needs your disc.
- **Dege**: dgVoodoo2. **AyuanX**: ogg-winmm. **FFmpeg**: the Indeo decoder and Cinepak encoder.

## License

The scripts and docs in this repository: MIT (see `LICENSE`). The license covers only this
repository's own files, not the game, dgVoodoo2, ogg-winmm or ffmpeg.

Not affiliated with or endorsed by the game's rights holders.
