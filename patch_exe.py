#!/usr/bin/env python3
"""Patch Panzer Dragoon's exe and movie DLL in place (the PC disc's GAME\\PANZERDG.EXE, 209,408 bytes,
MD5 d303b01482ec162bba5cd1011a255eb5, "V1.000"; GAME\\PANZ_AVI.DLL, 20,992 bytes).

  patch_exe.py [--windows] PANZERDG.EXE PANZ_AVI.DLL      (build.py runs it for you)

Applies every patch not yet applied and reports each; refuses (writes nothing) on unexpected bytes.
docs/TECHNICAL.md has more on each one.

  nocd    0x41a6e0 (at start-up, before the window: 0x41a650 scans drives A: to Z: for a DRIVE_CDROM
          holding game\\PanzerDG.exe, "Please insert Panzer Dragoon CD." Retry/Cancel until it finds one)
          returns 1 at once. The drive index 0x42c4b4 keeps its initial -1, which the game already handles
          as "no drive": CD audio opens the plain "cdaudio" device (0x4147b0), and the movie player
          (PANZ_AVI.DLL) opens the bare AVI name in the working directory, trying <drive>:\\game\\ only
          after that fails. The scan routine and the rest of 0x41a6e0 become room for the caves below.
  ini     the settings file "PANZERDG.INI" (0x42c38c) becomes ".\\PANZERDG.INI". A bare name sends
          GetPrivateProfileString / WritePrivateProfileString to the Windows folder (the installer put
          it there); with a path it is the game folder, so the package carries its own settings.
  escquit Esc quits at once, as Alt+F4. The game had no use for Esc: its keys are the twelve bindable
          ones (arrows, X V B A S D Z C), Enter (Start) and F1..F8 (its own screens). WM_KEYDOWN without
          Alt (0x4185e7: lea eax,[esi-0x71] / cmp eax,6 / ja) jumps to a cave at 0x41a6e8: VK_ESCAPE goes to
          the Alt+F4 handler 0x418577 (stops the game, DestroyWindow; WM_DESTROY saves the settings and
          posts WM_QUIT), anything else runs the three replaced instructions and on to the F2..F8 table.
  dpad    the D-pad works. Both pad modes read joystick 0 with joyGetPosEx asking only for X, Y and the
          buttons (dwFlags 0xc83 at 0x40e163), so the POV hat (an Xbox pad's D-pad) did nothing. The flags
          now include JOY_RETURNPOV (0xcc3), and after a successful read both readers (0x413eff Saturn
          pad, 0x40e18d PC pad) call a cave at 0x41a650 in place of their first threshold load: a pressed
          POV moves the stick record to the JOYCAPS extremes (8 directions; up 0, right 9000, down 18000,
          left 27000 hundredths of a degree, the diagonals in between), then the replaced load and ret.
          The game turns the stick into digital directions anyway (1/8 of the range off centre).
  start   the Saturn pad's Start is joystick button 9 (mask 0x100 at 0x42b498, copied into 0x435d10 at every
          start; the INI holds only SA..SR). An Xbox pad has 8 buttons, its Menu being button 8 (0x80),
          so the pad could not pause or start. The default becomes 0x80.
  idle    the frame wait (0x415770) spun on timeGetTime until the 16 ms multimedia timer (timeSetEvent,
          timeBeginPeriod on) had counted the frame's three ticks (20 fps): one core flat out for the whole
          session (hot Deck, fans on). The loop's call edi (timeGetTime) / sub eax,esi / mov ebx,[0x42c590]
          at 0x41577e becomes a call to a routine in the .text section's slack (0x423eb0; the section's
          VirtualSize grows from 0x22ea2 to its raw size 0x23000 so that part is mapped as code) doing
          Sleep(1) first (found with GetModuleHandleA + GetProcAddress, both imported; the exe imports no
          Sleep), then the three replaced instructions. Pacing is still the timer's.
  cdnotify  the game plays CD tracks with MCI_NOTIFY and loops the music from the MM_MCINOTIFY handler
          (0x414d40). Each of its MCI_STOPs (0x414b60, 0x414930) adds one to 0x42c1bc, the number of
          notifications to swallow: Windows' MCI answers a stopped play with MCI_NOTIFY_ABORTED, and the
          handler only decrements while the count is above 0. Leaving the title (0x418e50) waits for the
          count to reach 0. ogg-winmm sends no notification for a stopped track (only "successful" at a
          natural end), so the count stayed at 1 and Start on the title froze the game (Deck, 15 Oct 2026).
          The two inc eax (0x414b9d, 0x41494a) become nop: stops expect no notification; a track's natural
          end still restarts it.

PANZ_AVI.DLL (the movie player, an MCI avivideo child window of the game's window):
  moviewin  movies at AVI size Double were played with MCI_MCIAVI_PLAY_FULLSCREEN (0x100023cd, when the size
          flag 0x1000561c is negative), Video for Windows' low-res full-screen mode. Wine's mciavi ignores it
          and Windows 10/11 no longer have it: the 320x200 picture sat in the top-left corner. Always
          MCI_MCIAVI_PLAY_WINDOW; the movies are encoded at 640x400 (encode_videos.sh) to fill the window.
  movieplace  the window placement (0x10002660) centred the movie in the game's 640x480 (mode table, or the
          client rect in a window) and sent exactly 640x400 to (0,0): on Windows 95 the display really was
          640x480. Under dgVoodoo the display never changes mode: the game's window stays the size of the
          real screen (1280x800 on the Deck) and dgVoodoo scales its picture into it, while the
          MCI window is a plain child window placed in real pixels: the movie sat in the top-left corner.
          0x10002729 (the MoveWindow call's arguments) jumps to a routine in the .text slack (0x10003d10;
          VirtualSize 0x2d10 -> raw size 0x2e00) that takes the parent's real client rect, works out the
          picture inside it, scales the requested size (640x400 or 320x200) to
          that picture, centres the MCI window there (MoveWindow) and has MCI stretch the video to it
          (MCI_PUT, MCI_DGV_PUT_DESTINATION | MCI_DGV_RECT). Position-independent (call/pop): Wine loads
          the DLL away from its 0x10000000 base. The picture is 16:10, width min(cw, ch*8/5): dgVoodoo shows
          only the game's 640x400 image (DisplayROI 16_10 in dgVoodoo.conf, cutting the 640x480 mode's
          40-line black bars), and the 640x400 movie fills exactly that.
"""
import os, sys

def s(text, size):                     # string patch, NUL-padded to the original's room
    b = text.encode() + b"\0"
    assert len(b) <= size
    return b + b"\0" * (size - len(b))

def rel32(src, dst):                   # e8/e9 at src (5 bytes) -> dst
    return (dst - (src + 5)).to_bytes(4, "little", signed=True)

TEXT = 0x400c00                        # .text: VA 0x401000 at file offset 0x400
DATA = 0x401800                        # .data: VA 0x425000 at file offset 0x23800

# Cave 0x41a650 (dead CD scan, 142 bytes): POV -> stick extremes. Assembled with clang (i686, Intel syntax):
#   mov eax,[0x435efc]          ; dwPOV, 0xFFFF centred
#   cmp eax,36000 / jae out
#   cmp eax,4500 / jbe up / cmp eax,31500 / jae up                       ; 315..45 degrees: up
#   cmp eax,13500 / jb horiz / cmp eax,22500 / ja horiz                   ; 135..225: down
#   mov ecx,[0x435d70] (wYmax) / jmp sety
#   up: mov ecx,[0x435d6c] (wYmin)
#   sety: mov [0x435ee0],ecx    ; dwYpos
#   horiz: cmp eax,4500 / jb out / cmp eax,31500 / ja out
#   cmp eax,13500 / jbe right / cmp eax,22500 / jb out                    ; 45..135 right, 225..315 left
#   mov ecx,[0x435d64] (wXmin) / jmp setx
#   right: mov ecx,[0x435d68] (wXmax)
#   setx: mov [0x435edc],ecx    ; dwXpos
#   out: mov eax,[0x435f08] / ret                                         ; the replaced instruction
POV = bytes.fromhex(
    "a1fc5e43003da08c000073603d94110000761d3d0c7b000073163dbc340000721b3de457000077148b0d705d4300eb06"
    "8b0d6c5d4300890de05e43003d9411000072293d0c7b000077223dbc340000760f3de457000072148b0d645d4300eb06"
    "8b0d685d4300890ddc5e4300a1085f4300c3")
# Cave 0x41a6e8 (dead rest of 0x41a6e0): cmp esi,0x1b / je 0x418577 / lea eax,[esi-0x71] / cmp eax,6 /
#   ja 0x4185f6 / jmp 0x4185ef
ESC = bytes.fromhex("83fe1b0f8486deffff8d468f83f8060f87f9deffffe9eddeffff")

# The CD scan's original bytes (the dpad cave's site), replaced by the dpad cave.
SCAN = bytes.fromhex(
    "83ec5053565733db55ff156cf350008bf88b3540f350008b2d68f35000b8010000008acbd3e085c774418d43418d4c2410"
    "50687cca420051ff1538f450008d4c241c83c40c51ffd583f805751e8d4424106868ca420050ff1564f350008d4424106a"
    "0050ffd683f8ff75084383fb207caceb")

# Routine 0x423eb0 (.text slack): push "KERNEL32.dll" / call [GetModuleHandleA] / push "Sleep" / push eax /
#   call [GetProcAddress] / push 1 / call eax / call edi / sub eax,esi / mov ebx,[0x42c590] / ret / the two strings
IDLE = bytes.fromhex(
    "68d63e4200ff1504f3500068e33e420050ff15e4f250006a01ffd0ffd729f08b1d90c54200c3"
    "4b45524e454c33322e646c6c00536c65657000")

PATCHES = {
    "nocd":    [(0x41a6e0 - TEXT, bytes.fromhex("56578b355cf4"), bytes.fromhex("b801000000c3"))],   # mov eax,1 / ret
    "ini":     [(0x42c38c - DATA, s("PANZERDG.INI", 16), s(".\\PANZERDG.INI", 16))],
    "escquit": [(0x41a6e8 - TEXT, bytes.fromhex("bfffffffffe85effffffa3b4c442003bc7a1e8c4420075166a35"), ESC),
                (0x4185e7 - TEXT, bytes.fromhex("8d468f83f8067707"), b"\xe9" + rel32(0x4185e7, 0x41a6e8) + b"\x90" * 3)],
    "dpad":    [(0x41a650 - TEXT, SCAN, POV),
                (0x40e169 - TEXT, bytes.fromhex("830c0000"), bytes.fromhex("c30c0000")),
                (0x413eff - TEXT, bytes.fromhex("a1085f4300"), b"\xe8" + rel32(0x413eff, 0x41a650)),
                (0x40e18d - TEXT, bytes.fromhex("a1085f4300"), b"\xe8" + rel32(0x40e18d, 0x41a650))],
    "start":   [(0x42b498 - DATA, bytes.fromhex("0001"), bytes.fromhex("8000"))],
    "idle":    [(0x180, bytes.fromhex("a22e0200"), bytes.fromhex("00300200")),                    # .text VirtualSize
                (0x423eb0 - TEXT, bytes(len(IDLE)), IDLE),
                (0x41577e - TEXT, bytes.fromhex("ffd72bc68b1d90c54200"), b"\xe8" + rel32(0x41577e, 0x423eb0) + b"\x90" * 5)],
    "cdnotify": [(0x414b9d - TEXT, b"\x40", b"\x90"), (0x41494a - TEXT, b"\x40", b"\x90")],
}

# Routine 0x10003d10 (PANZ_AVI.DLL .text slack), assembled with clang; ebx = runtime address of 0x10003d27:
#   mov ebp,esp / movsx esi,cx (640 for 639) / call+pop ebx / GetClientRect(parent [ebp+0x24]) /
#   pic_w = min(cw, ch*8/5) / mw = pic_w*w/640 / mh = pic_w*h/640 / MoveWindow(mci wnd, (cw-mw)/2, (ch-mh)/2,
#   mw, mh, TRUE) / mciSendCommandA([ebp+0x28], MCI_PUT, 0x50000, {0, 0,0,mw,mh}) / mov esp,ebp / jmp 0x1000273e
PLACE = bytes.fromhex(
    "89e50fbff181fe7f0200007505be80020000e8000000005b83ec1054ff7524ff93553400008b44240cc1e00399b90500"
    "0000f7f93b4424087e048b442408b980020000500fafc699f7f989c6580fafc799f7f989c78b44240829f0d1f88b5424"
    "0c29fad1fa6a0157565250ffb37d290000ff936134000057566a006a006a005468000005006842080000ff7528ff938d"
    "34000089ece994e9ffff"
)

AVI_TEXT = 0x10000c00                  # PANZ_AVI.DLL .text: VA 0x10001000 at file offset 0x400
AVI_PATCHES = {
    "moviewin":    [(0x100023cd - AVI_TEXT, bytes.fromhex("81c900000002"), bytes.fromhex("81c900000001"))],
    "movieplace":  [(0x180, bytes.fromhex("102d0000"), bytes.fromhex("002e0000")),                 # .text VirtualSize
                    (0x10003d10 - AVI_TEXT, bytes(len(PLACE)), PLACE),
                    (0x10002729 - AVI_TEXT, bytes.fromhex("0fbfc96a0157515053"), b"\xe9" + rel32(0x10002729, 0x10003d10) + b"\x90" * 4)],
}

# Windows variant of the routine (patch_exe.py --windows; build.py --windows). On Windows dgVoodoo's output
# hides the MCI window unless EnableGDIHooking copies GDI drawing into the picture, and that copy is in the
# game's own 640x480 space, not real screen pixels (a window sized to the screen showed its top-left corner,
# zoomed). So the parent's client rect is a fixed 640x480 instead of GetClientRect:
# sub esp,0x10 / push esp / push [ebp+0x24] / call [GetClientRect] (13 bytes) become push 480 / push 640 /
# push eax / push eax / nop (right and bottom are all the routine reads): the 640x400 movie goes to (0,40).
PLACE_GDI = PLACE[:0x18] + bytes.fromhex("68e00100006880020000505090") + PLACE[0x25:]
assert len(PLACE_GDI) == len(PLACE)
AVI_PATCHES_GDI = dict(AVI_PATCHES, movieplace=[AVI_PATCHES["movieplace"][0],
                                                (0x10003d10 - AVI_TEXT, bytes(len(PLACE_GDI)), PLACE_GDI),
                                                AVI_PATCHES["movieplace"][2]])

FILES = {209408: ("the disc's GAME\\PANZERDG.EXE", PATCHES), 20992: ("the disc's GAME\\PANZ_AVI.DLL", AVI_PATCHES)}

def patch(data, label="file", windows=False):
    """Returns `data` with every patch applied (windows: the Windows movie placement); exits on unexpected bytes."""
    data = bytearray(data)
    if len(data) not in FILES:
        sys.exit("%s: %d bytes, expected 209,408 or 20,992 (the disc's PANZERDG.EXE or PANZ_AVI.DLL)" % (label, len(data)))
    what, patches = FILES[len(data)]
    if windows and patches is AVI_PATCHES: patches = AVI_PATCHES_GDI
    todo = []
    for name, sites in patches.items():
        state = []
        for off, old, new in sites:
            cur = bytes(data[off:off + len(new)])
            state.append("new" if cur == new else "old" if cur == old[:len(new)] else "?")
        if all(x == "new" for x in state):
            print("  %-11s already applied" % name)
        elif all(x == "old" for x in state):
            todo.append(name)
        else:
            sys.exit("%s: %s has unexpected bytes (%s); nothing written" % (label, name, state))
    for name in todo:
        for off, old, new in patches[name]:
            data[off:off + len(new)] = new
        print("  %-11s applied" % name)
    return bytes(data)

def main(path, windows=False):
    out = patch(open(path, "rb").read(), path, windows)
    tmp = path + ".tmp"
    open(tmp, "wb").write(out)
    os.replace(tmp, path)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    win = "--windows" in sys.argv
    for f in [a for a in sys.argv[1:] if a != "--windows"]:
        main(f, win)
