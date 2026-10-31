#!/usr/bin/env python3
"""Build a ready-to-run Panzer Dragoon (PC) folder for modern PCs from your own CD.

Usage:
  python3 build.py DISC.cue|DISC.ccd --dgvoodoo DGVOODOO.zip --ogg-winmm OGG-WINMM.zip [--out DIR]
                   [--windows] [--jobs N]

  DISC          your Panzer Dragoon PC CD (Sega, 1996, "V1.000") as .cue + .bin/.img or .ccd + .img
  --dgvoodoo    dgVoodoo2 2.79.3 zip (or its unpacked folder)
  --ogg-winmm   ogg-winmm release zip (or folder)
  --out         where to create PanzerDragoon/ (default: this folder)
  --windows     a folder for Windows instead of the Steam Deck: the movie player and dgVoodoo set up so the
                movies show on Windows (see README), no launch script
  --jobs        movie encodes run at once (default: one per CPU core)

Needs Python 3.8+, ffmpeg and ffprobe on the PATH (the movies are re-encoded, and ffmpeg encodes
the soundtrack too unless oggenc is there).
Nothing from the game is in this repository: every game file comes from your disc.
"""
import argparse, hashlib, os, shutil, struct, subprocess, sys, tempfile, zipfile
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import disc, patch_exe

EXE_MD5 = "d303b01482ec162bba5cd1011a255eb5"           # GAME\PANZERDG.EXE on the disc, "V1.000"
PATCHED_MD5 = {"PANZERDG.EXE": "7f01515369a05200f90b6f863aa9b2d6",
               "PANZ_AVI.DLL": "de67b571d35359c3cf16a15a2a3e26a2"}           # Steam Deck
PATCHED_MD5_WINDOWS = dict(PATCHED_MD5, **{"PANZ_AVI.DLL": "5f8a6d46c6fac41f46b2ac6458158ca2"})
CHUNK = 500                # frames per encode job; every frame is a key frame, so chunks join cleanly


def md5(data): return hashlib.md5(data).hexdigest()


def need(tool):
    if not shutil.which(tool): sys.exit(f"needs {tool} on the PATH (part of ffmpeg)")


def run(cmd): subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL)


def probe(path, entry, extra=()):
    return subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", *extra, "-show_entries",
                           "stream=" + entry, "-of", "csv=p=0", path],
                          check=True, capture_output=True, text=True).stdout.strip()


def encode_movie(src, dst, tmp, jobs):
    """Indeo 4.1 320x200 -> Cinepak 640x400, every frame a key frame (the player seeks inside EXOPEN.AVI,
    which holds all the episode intros), the same frame slots (empty chunks repeat the previous picture;
    each picture keeps its slot, the end is padded and cut to the header's count), the sound copied as it is."""
    name = os.path.splitext(os.path.basename(src))[0]
    slots = int(probe(src, "nb_frames"))
    rate = probe(src, "r_frame_rate")

    def chunk(a):
        b = min(a + CHUNK, slots); out = os.path.join(tmp, f"{name}.{a:05d}.avi")
        run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", src, "-an", "-vf",
             f"fps=source_fps,tpad=stop_mode=clone:stop=60,trim=end_frame={slots},"
             f"select='between(n\\,{a}\\,{b - 1})',setpts=N/FRAME_RATE/TB,scale=640:400:flags=lanczos",
             "-c:v", "cinepak", "-g", "1", "-pix_fmt", "rgb24", "-max_extra_cb_iterations", "0",
             "-frames:v", str(b - a), out])
        return out

    with ThreadPoolExecutor(jobs) as pool: parts = list(pool.map(chunk, range(0, slots, CHUNK)))
    lst = os.path.join(tmp, name + ".list")
    with open(lst, "w") as f: f.writelines(f"file '{os.path.basename(p)}'\n" for p in parts)
    video = os.path.join(tmp, name + ".video.avi")
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", "-r", rate, video])
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", video, "-i", src, "-map", "0:v", "-map", "1:a", "-c", "copy", dst])
    got = int(probe(dst, "nb_read_packets", ["-count_packets"]))
    if got != slots: sys.exit(f"{name}.AVI: {got} frames after encoding, expected {slots}")
    for p in parts + [lst, video]: os.remove(p)
    print(f"  {name}.AVI  {slots} frames, {rate} fps")


def encoder():
    if shutil.which("oggenc"): return lambda wav, ogg: ["oggenc", "-Q", "-q", "7", wav, "-o", ogg]
    return lambda wav, ogg: ["ffmpeg", "-loglevel", "error", "-y", "-i", wav, "-c:a", "libvorbis", "-q:a", "7", ogg]


def rip(tracks, music):
    enc = encoder(); os.makedirs(music, exist_ok=True); zero = bytes(2352)
    with tempfile.TemporaryDirectory() as tmp:
        for t in tracks:
            if t.kind != "AUDIO": continue
            data = disc.audio(t)          # INDEX 01 to the next track's start
            tail = 0                      # minus up to 2 s of digital silence at the end (the gap before the next track)
            while tail < 150 and data[len(data) - (tail + 1) * 2352:len(data) - tail * 2352] == zero: tail += 1
            if tail: data = data[:len(data) - tail * 2352]
            wav = os.path.join(tmp, f"track{t.n:02d}.wav")
            with open(wav, "wb") as o:
                o.write(b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt " +
                        struct.pack("<IHHIIHH", 16, 1, 2, 44100, 176400, 4, 16) + b"data" +
                        struct.pack("<I", len(data)) + data)
            subprocess.run(enc(wav, os.path.join(music, f"Track{t.n:02d}.ogg")), check=True); os.remove(wav)
            print(f"  Music/Track{t.n:02d}.ogg  {len(data) / 2352 / 75:6.1f} s")


def take(src, member):
    """Bytes of the file whose path ends with `member` (case-insensitive) in a zip or folder."""
    want = member.lower()
    if os.path.isdir(src):
        for d, _, fs in os.walk(src):
            for f in fs:
                p = os.path.join(d, f)
                if os.path.relpath(p, src).replace(os.sep, "/").lower().endswith(want): return open(p, "rb").read()
    else:
        with zipfile.ZipFile(src) as z:
            for name in z.namelist():
                if name.lower().endswith(want): return z.read(name)
    sys.exit(f"{member} not found in {src}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("disc"); ap.add_argument("--dgvoodoo", required=True); ap.add_argument("--ogg-winmm", required=True)
    ap.add_argument("--out", default=HERE); ap.add_argument("--windows", action="store_true")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    a = ap.parse_args()
    need("ffmpeg"); need("ffprobe")

    tracks = disc.tracks(a.disc)
    data = [t for t in tracks if t.kind != "AUDIO"]
    if not data: sys.exit("no data track in " + a.disc)
    dt = disc.DataTrack(data[0])
    entries = {p.upper(): (p, is_dir, l, s) for p, is_dir, l, s in dt.walk()}
    if "GAME/PANZERDG.EXE" not in entries: sys.exit("no GAME\\PANZERDG.EXE on this CD: it isn't the Panzer Dragoon PC disc")
    got = md5(dt.read_file(*entries["GAME/PANZERDG.EXE"][2:]))
    if got != EXE_MD5:
        sys.exit(f"this CD's PANZERDG.EXE is not the 1996 \"V1.000\" one the kit was made for (MD5 {got}); "
                 "nothing else is supported yet")

    pkg = os.path.join(os.path.abspath(a.out), "PanzerDragoon"); game = os.path.join(pkg, "game")
    if os.path.exists(pkg): sys.exit(f"{pkg} already exists: move or delete it first")

    print("1/6 game files from the CD")    # the disc's GAME\, which the installer copied; everything opens by bare name
    movies = []
    for key, (p, is_dir, l, s) in entries.items():
        if is_dir or not key.startswith("GAME/") or key.count("/") != 1: continue
        name = p.split("/")[1]
        if key.endswith(".AVI"):
            dt.copy_file(l, s, os.path.join(game, "_spare", "movies_indeo41", name)); movies.append(name)
        else:
            dt.copy_file(l, s, os.path.join(game, name))
    for src, dst in [("DOC/N_PANZ_E.HLP", "PD_E.HLP"), ("DOC/README_E.TXT", "README.TXT")]:   # F1 help, readme
        dt.copy_file(*entries[src][2:], os.path.join(game, dst))
    for src, dst in [("PANZERDG.EXE", "PANZERDG_retail.exe"), ("PANZ_AVI.DLL", "PANZ_AVI_retail.dll")]:
        shutil.copyfile(os.path.join(game, src), os.path.join(game, "_spare", dst))

    print("2/6 exe and movie player patches" + (" (Windows movie placement)" if a.windows else ""))
    for f in ("PANZERDG.EXE", "PANZ_AVI.DLL"):
        path = os.path.join(game, f)
        out = patch_exe.patch(open(path, "rb").read(), f, a.windows)
        if md5(out) != (PATCHED_MD5_WINDOWS if a.windows else PATCHED_MD5)[f]: sys.exit(f"patching gave an unexpected {f}")
        open(path, "wb").write(out)

    print(f"3/6 movies: Indeo 4.1 -> Cinepak 640x400 ({a.jobs} at once; this is the slow part)")
    with tempfile.TemporaryDirectory() as tmp:
        for m in sorted(movies):
            encode_movie(os.path.join(game, "_spare", "movies_indeo41", m), os.path.join(game, m), tmp, a.jobs)

    print("4/6 soundtrack")
    rip(tracks, os.path.join(game, "Music"))

    print("5/6 wrappers and settings")
    open(os.path.join(game, "ddraw.dll"), "wb").write(take(a.dgvoodoo, "MS/x86/DDraw.dll"))
    for name in ("winmm.dll", "winmm.ini"):
        open(os.path.join(game, name), "wb").write(take(a.ogg_winmm, name))
    conf = "dgVoodoo-windows.conf" if a.windows else "dgVoodoo-deck.conf"
    shutil.copyfile(os.path.join(HERE, "config", conf), os.path.join(game, "dgVoodoo.conf"))
    shutil.copyfile(os.path.join(HERE, "config", "PANZERDG.INI"), os.path.join(game, "PANZERDG.INI"))

    print("6/6 Steam Deck launch script" if not a.windows else "6/6 done")
    if not a.windows:
        launch = os.path.join(pkg, "panzer_launch.sh")
        shutil.copyfile(os.path.join(HERE, "steamdeck", "panzer_launch.sh"), launch); os.chmod(launch, 0o755)
    print(f"\ndone: {pkg}  (see README.md)")


if __name__ == "__main__":
    main()
