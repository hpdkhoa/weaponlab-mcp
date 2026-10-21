"""A built gun's showcase: a title card, the source figure beside the copy, the copy turned once round, then its own
clips (fire slowed down, the reloads, the chamber check) as Gun Kit made them. Written as an animated GIF and an
MP4 (H.264, made by Blender's encoder) under <gun>/showcase/. Every frame says it is a Blueprint Lab model view, not a
game view."""
import json
import shutil
import subprocess
from pathlib import Path

from ..config import project
from . import figures as F
from . import store

HERE = Path(__file__).resolve().parent / "blender"
CLIPS = [  # action suffix, label, slow, view, repeat, zoom (the camera's distance)
    ("fire", "Firing: the slide cycles (6x slow)", 6, "right_close", 2, 1.0),
    ("reload_empty", "Empty reload: the empty magazine drops free, a new one goes in, the slide runs forward (2x slow)", 2, "right", 1, 1.7),
    ("check_chamber", "Chamber check: the slide eased back to see the round", 1, "right", 1, 1.0),
    ("check_mag", "Magazine check: out, looked at, back in", 1, "left", 1, 1.5),
]


def _font(size):
    from PIL import ImageFont
    for name in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _label(img, top, bottom):
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    w, h = img.size
    d.rectangle([0, 0, w, 34], fill=(255, 255, 255))
    d.text((12, 6), top, fill=(20, 20, 20), font=_font(18))
    d.rectangle([0, h - 30, w, h], fill=(30, 30, 34))
    d.text((12, h - 26), bottom, fill=(235, 235, 235), font=_font(15))
    return img


def _card(size, lines):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", size, (24, 26, 30))
    d = ImageDraw.Draw(img)
    y = size[1] // 2 - 30 * len(lines) // 2 - 10
    for k, (text, big) in enumerate(lines):
        f = _font(34 if big else 18)
        tw = d.textlength(text, font=f)
        d.text(((size[0] - tw) / 2, y), text, fill=(240, 240, 240) if big else (190, 190, 195), font=f)
        y += 48 if big else 30
    return img


def _side_by_side(gun, size, fig_id, view_png, source_caption=None, copy_caption=None):
    from PIL import Image
    w, h = size
    src = Image.open(store.abspath(gun, F.figure(gun, fig_id)["image"])).convert("RGB")
    mod = Image.open(view_png).convert("RGB")
    out = Image.new("RGB", size, (236, 236, 240))
    for k, im in enumerate((src, mod)):
        im.thumbnail((w // 2 - 24, h - 110))
        out.paste(im, (k * w // 2 + (w // 2 - im.size[0]) // 2, 50 + (h - 110 - im.size[1]) // 2))
    from PIL import ImageDraw
    d = ImageDraw.Draw(out)
    d.text((24, h - 58), source_caption or "Source: FM 23-35 (1940), Figure 2", fill=(40, 40, 40), font=_font(15))
    d.text((w // 2 + 24, h - 58), copy_caption or "Copy: built from the manual's figures and data", fill=(40, 40, 40), font=_font(15))
    return out


def make(gun, title=None, source_note=None, fps=15, size=(960, 600), turn_frames=60, compare_figure=None, timeout=3600,
         compare_view="view_left", source_caption=None, copy_caption=None, subtitle=None):
    """Renders and writes showcase/<gun>.gif and showcase/<gun>.mp4. Needs the gun built and through Gun Kit."""
    from PIL import Image
    from ..gunkit import run as R
    clips_blend = Path(R.folder(gun)) / ("%s_clips.blend" % gun)
    if not clips_blend.exists():
        raise FileNotFoundError("run the gun through Gun Kit first (%s)" % clips_blend)
    out = store.folder(gun, "showcase")
    frames_dir = out / "frames"
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir()
    clips = [{"action": "A_%s_%s" % (gun, a), "label": lab, "slow": s, "view": v, "repeat": r, "zoom": z} for a, lab, s, v, r, z in CLIPS]
    jf = out / "showcase.job.json"
    jf.write_text(json.dumps({"out": str(frames_dir), "size": list(size), "fps": fps, "turn_frames": turn_frames, "clips": clips}), encoding="utf-8")
    p = subprocess.run([str(project().blender()), "-b", str(clips_blend), "-P", str(HERE / "blueprint_showcase.py"), "--", str(jf)],
                       capture_output=True, text=True, timeout=timeout)
    (out / "showcase.log").write_text((p.stdout or "") + "\n" + (p.stderr or ""), encoding="utf-8", errors="replace")
    if p.returncode != 0 or "SHOWCASE FRAMES" not in (p.stdout or ""):
        tail = [l for l in ((p.stdout or "") + (p.stderr or "")).splitlines() if l.strip()][-12:]
        raise RuntimeError("the showcase render failed (see %s):\n%s" % (out / "showcase.log", "\n".join(tail)))
    shots = json.loads((frames_dir / "shots.json").read_text(encoding="utf-8"))["shots"]
    head = "BLUEPRINT LAB MODEL %s (not a game view)" % gun
    bp = store.load(gun, "blueprint")
    seq = []
    card = _card(size, [(title or bp.get("title", gun), True), (subtitle or "A visual copy made from its public sources", False),
                        (source_note or "", False), ("Blueprint Lab and Gun Kit, weaponlab-mcp", False)])
    seq += [card] * int(fps * 2.5)
    view = store.folder(gun, "model", "views") / ("%s.png" % compare_view)
    if compare_figure and view.exists():
        sbs = _label(_side_by_side(gun, size, compare_figure, view, source_caption, copy_caption), head,
                     "The source figure and the copy, side by side")
        seq += [sbs] * int(fps * 3)
    for s in shots:
        im = Image.open(frames_dir / ("f%05d.png" % s["frame"])).convert("RGB")
        seq.append(_label(im, head, "Turned once round" if s["shot"] == "turn" else s["shot"]))
    seq += [card] * int(fps * 1.5)
    gif = out / ("%s.gif" % gun)
    small = [im.resize((size[0] * 3 // 4, size[1] * 3 // 4), Image.LANCZOS) for im in seq]
    pal = [im.convert("P", palette=Image.ADAPTIVE, colors=128) for im in small]
    pal[0].save(gif, save_all=True, append_images=pal[1:], duration=int(1000 / fps), loop=0, optimize=True)
    comp = out / "composed"
    if comp.exists():
        shutil.rmtree(comp)
    comp.mkdir()
    for k, im in enumerate(seq):
        im.save(comp / ("c%05d.png" % k))
    mp4 = out / ("%s.mp4" % gun)
    enc = out / "encode.job.json"
    enc.write_text(json.dumps({"frames": str(comp), "count": len(seq), "fps": fps, "size": list(size), "out": str(mp4)}), encoding="utf-8")
    p = subprocess.run([str(project().blender()), "-b", "--factory-startup", "-P", str(HERE / "blueprint_encode.py"), "--", str(enc)],
                       capture_output=True, text=True, timeout=timeout)
    (out / "encode.log").write_text((p.stdout or "") + "\n" + (p.stderr or ""), encoding="utf-8", errors="replace")
    return {"gif": str(gif), "mp4": str(mp4) if mp4.exists() else None, "frames": len(seq), "seconds": round(len(seq) / fps, 1),
            "gif_mb": round(gif.stat().st_size / 1e6, 2)}
