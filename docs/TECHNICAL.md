# How it works

Notes on the PC release of Panzer Dragoon (Sega PC, 1996, Windows 95 port of the 1995 Saturn game,
"Panzer Dragoon Native" V1.000; `GAME\PANZERDG.EXE` 209,408 bytes, MD5
`d303b01482ec162bba5cd1011a255eb5`). Addresses are virtual addresses in that exe, or in
`PANZ_AVI.DLL` where they start with 0x1000. `patch_exe.py` describes each patch in detail.

## Installing without the installer

The retail installer (`INSTALL\SETUP.EXE`, Sega's generic "SSP" setup) copied the disc's `GAME\`
folder to `C:\SEGA\PanzerDG`, installed DirectX 3 and Indeo 4.1, and the game kept its settings in
`C:\Windows\PANZERDG.INI`. Everything the game opens (stage DLLs, graphics, sound banks, movies,
`REPLAY*.DAT`) is opened by bare name from the working directory, so `build.py` copies `GAME\`
into `game/` with the English help and readme from `DOC\`. No registry keys are used.

## Disc check and settings (nocd, ini)

At start-up, before the window opens, 0x41a6e0 calls 0x41a650: drives A: to Z:
(`GetLogicalDrives`), the first of type `DRIVE_CDROM` holding `game\PanzerDG.exe` wins; none gives
"Please insert Panzer Dragoon CD." (Retry/Cancel). The drive index goes to 0x42c4b4, initially -1,
and is used twice: CD audio (0x4147b0) opens `cdaudio` with the element `X:`, or with -1 the plain
`cdaudio` device; the movie player opens the bare AVI name first and tries `X:\game\` only if that
fails.

`nocd` makes 0x41a6e0 return 1 at once, so the index stays -1. The dead scan routine becomes room
for the D-pad code below, which is why the check can't be kept as an option. `ini` changes the
settings file name to `.\PANZERDG.INI`, so `GetPrivateProfileString` uses the game folder, not
the Windows folder.

## CD audio (cdnotify)

`MCI_OPEN` of `cdaudio`, time format TMSF, tracks 2-16: the standard case ogg-winmm handles
(`Music\TrackNN.ogg`; `WINEDLLOVERRIDES=winmm=n,b` under Proton). Each track is ripped from its
INDEX 01 to the next track's start, minus up to two seconds of digital silence at its end.

Music loops through notifications: tracks play with `MCI_NOTIFY`, and the `MM_MCINOTIFY` handler
(0x414d40) restarts the track. Every `MCI_STOP` (0x414b60, 0x414930) added one to a count at
0x42c1bc of notifications to swallow, because Windows answers a stopped play with
`MCI_NOTIFY_ABORTED`; leaving the title screen (0x418e50) waits for that count to drop to 0.
ogg-winmm sends a notification only when a track ends by itself, so the count stayed at 1 and Start
on the title froze the game. `cdnotify` removes the two increments: stops expect nothing, a natural
end still restarts the track.

## Movies (moviewin, movieplace)

The three movies are Indeo 4.1 (`IV41`, 320x200, 15/20 fps) with PCM or MS ADPCM sound, played
through MCI (`mciavi`) by `PANZ_AVI.DLL` in a child window of the game's window. Neither Proton's
Wine nor Windows 10/11 can decode Indeo 4; both have Cinepak (`iccvid.dll`). `build.py` re-encodes
them with ffmpeg to Cinepak at 640x400 (Lanczos), every frame a key frame like the originals
(`EXOPEN.AVI` holds all the episode intros and the player seeks inside it), the sound copied
unchanged. `EXOPEN.AVI` has 8,863 frame slots of which 8,102 hold a picture (the rest repeat the
previous one); each picture keeps its slot, so frame numbers keep their times. The originals stay in
`_spare\movies_indeo41\`.

Size: at AVI size `Double` (`[Screen] AVI` in the INI) the DLL played with
`MCI_MCIAVI_PLAY_FULLSCREEN`, Video for Windows' low-res full-screen mode, which did the doubling.
Wine ignores the flag and Windows 10/11 dropped the mode, so the picture sat small in the top-left
corner. `moviewin` always plays in the window (0x100023cd).

Place: the DLL centred the movie in the game's 640x480, which on Windows 95 was the real display.
Under dgVoodoo the display never changes mode: the game's window is the size of the real screen and
dgVoodoo scales the picture into it, but the MCI window is an ordinary child window placed in real
pixels. `movieplace` sends the placement (0x10002729) to a routine in the DLL's `.text` slack
(0x10003d10) that reads the real client rect, finds the 16:10 picture dgVoodoo shows in it (below),
centres the MCI window over it and has MCI stretch the video to fit (`MCI_PUT`). Wine loads the DLL
away from its base address, so the routine is position-independent.

Windows is different. dgVoodoo's output there covers the MCI window, so the movies played with sound
and no picture, in real full screen, in a borderless window and with every presentation model.
`EnableGDIHooking = true` (`dgVoodoo-windows.conf`) makes dgVoodoo copy GDI drawing, which is how
the MCI window draws, into its picture. That copy is in the game's own 640x480 space, so a window
sized to the real screen showed only its top-left corner, zoomed in. The `--windows` movie player
gives the routine a fixed 640x480 client rect in place of `GetClientRect`: the 640x400 movie goes
to (0,40), where the game drew it on Windows 95. Under Wine, GDI hooking isn't needed (Wine draws
the child window over the picture) and the real-pixel routine is the one that works.

## Graphics

A software renderer into DirectDraw surfaces; three modes chosen in the INI (`[Screen] VMode`) or
the F7 screen: 320x200 8-bit, 640x480 8-bit, 640x480 16-bit (shipped). dgVoodoo2 2.79.3's
`ddraw.dll` takes the DirectDraw calls and renders through Direct3D 11 (Vulkan via DXVK under
Proton): full screen, bilinear, no frame cap. 2.80 and later fail to initialise DirectDraw under Wine
(Wine bug 58731). `RENDERER=wined3d` in the launch options uses Wine's own ddraw.

No black bars: the mode table (0x42b1fc) shows the game drawing a 640x400 picture centred in the
640x480 mode, with 40 black lines above and below. 640x400 is 16:10, the Steam Deck's own shape, so
`dgVoodoo.conf` has `DisplayROI = 16_10, pos:centered`: dgVoodoo shows only that region, scaled to
the screen, nothing cut or stretched. A 16:9 monitor gets thin bars at the sides. A wider view isn't
possible: the renderer, the Saturn-style background layers and the HUD are spread over a dozen stage
DLLs built for one view.

## Frame pacing (idle)

A 16 ms multimedia timer counts ticks; a frame is three ticks (20 fps, as on the Saturn). The wait
for them (0x415770) spun on `timeGetTime`, keeping one CPU core at 100% for the whole session. The
loop now calls `Sleep(1)` each turn, from a routine in the `.text` section's slack (0x423eb0) that
looks `Sleep` up with `GetProcAddress`, since the exe doesn't import it. Pacing is still the timer's.

## Keys and pad (escquit, dpad, start)

The keyboard: twelve bindable keys (`[Input] LEFT..R`: arrows, X V B A S D Z C), Enter as Start,
F1 help, F2-F8 the game's own screens, Alt+F4 quits. Esc did nothing; `escquit` makes it quit at
once like Alt+F4 (the INI is still written).

`[Input] Device` picks the pad reader. `SEGA_DIGITAL` (shipped) reads joystick 0 through
`joyGetPosEx` as a Saturn pad: `SA SB SC SX SY SZ SL SR` are the joystick button masks for the
Saturn's A B C X Y Z L R. Start was fixed at button 9 (`0x100`), which an Xbox-style pad doesn't
have; `start` makes it `0x80` (Menu). The game asked `joyGetPosEx` for X, Y and buttons only, so
the D-pad (POV hat) did nothing; `dpad` adds `JOY_RETURNPOV` and turns a pressed POV into a fully
pushed stick (8 directions) in both readers. The stick is read as digital directions anyway, as the
Saturn pad.
