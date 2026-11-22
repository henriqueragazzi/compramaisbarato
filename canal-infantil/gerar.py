#!/usr/bin/env python3
"""Turminha do Pingo — gerador de vídeos infantis educativos.

Uso:
    python3 gerar.py episodios/cores.json            # vídeo 16:9 + thumbnail + metadados
    python3 gerar.py episodios/cores.json --short    # Short vertical 9:16

Tudo é original: personagem desenhado por código, música gerada por código,
voz sintetizada (Piper, voz pt-BR "edresson", CC BY 4.0).
"""
import hashlib, json, math, subprocess, sys, tempfile, wave
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BASE = Path(__file__).resolve().parent
ASSETS = BASE / "assets"
OUT = BASE / "saida"
FONT = str(ASSETS / "Fredoka.ttf")
VOICE = str(ASSETS / "pt-br-edresson-low.onnx")
FPS = 24
SR = 44100
PITCH = 1.13          # deixa a voz mais "de personagem"
LENGTH_SCALE = 1.18   # fala mais devagar (público infantil)

PINGO_AZUL = "#2F8CFF"


# ---------------------------------------------------------------- utilidades
def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def ease_out_back(x):
    x = min(max(x, 0.0), 1.0)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


@lru_cache(maxsize=64)
def font(size, weight="Bold"):
    f = ImageFont.truetype(FONT, size)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f


def sprite(w, h, draw_fn):
    """Desenha em 3x e reduz (antialiasing)."""
    k = 3
    im = Image.new("RGBA", (w * k, h * k), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(im), w * k, h * k)
    return im.resize((w, h), Image.LANCZOS)


def paste_center(frame, spr, cx, cy, scale=1.0, rot=0.0, alpha=1.0):
    if scale <= 0.01 or alpha <= 0.01:
        return
    s = spr
    if abs(scale - 1) > 1e-3:
        s = s.resize((max(1, int(s.width * scale)), max(1, int(s.height * scale))), Image.BILINEAR)
    if abs(rot) > 0.1:
        s = s.rotate(rot, resample=Image.BICUBIC, expand=True)
    if alpha < 0.999:
        a = s.getchannel("A").point(lambda v: int(v * alpha))
        s = s.copy()
        s.putalpha(a)
    frame.alpha_composite(s, (int(cx - s.width / 2), int(cy - s.height / 2)))


@lru_cache(maxsize=256)
def text_sprite(txt, size, color, outline="#FFFFFF", shadow=True):
    f = font(size)
    lines = txt.split("\n")
    pad = size // 3
    boxes = [f.getbbox(l, stroke_width=size // 9) for l in lines]
    lw = max(b[2] - b[0] for b in boxes)
    lh = int(size * 1.15)
    W, H = lw + pad * 2, lh * len(lines) + pad * 2
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, l in enumerate(lines):
        x, y = W / 2, pad + lh * i + lh / 2
        if shadow:
            d.text((x + size * 0.05, y + size * 0.07), l, font=f, anchor="mm",
                   fill=(20, 30, 70, 150), stroke_width=size // 6, stroke_fill=(20, 30, 70, 150))
        d.text((x, y), l, font=f, anchor="mm", fill=(40, 40, 90), stroke_width=size // 6, stroke_fill=(40, 40, 90))
        d.text((x, y), l, font=f, anchor="mm", fill=color, stroke_width=size // 10, stroke_fill=outline)
    return im


# ---------------------------------------------------------------- desenhos
def drop_points(cx, cy, r, n=120):
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = math.sin(t) * math.sin(t / 2) ** 1.15
        y = math.cos(t)
        pts.append((cx + x * r * 1.05, cy - y * r))
    return pts


@lru_cache(maxsize=64)
def pingo_sprite(size, mouth=0, blink=False, face=True):
    def draw(d, W, H):
        cx, cy, r = W / 2, H * 0.52, H * 0.46
        body, dark = hex2rgb(PINGO_AZUL), (24, 92, 200)
        d.polygon(drop_points(cx, cy + W * 0.012, r), fill=dark)
        d.polygon(drop_points(cx, cy, r * 0.965), fill=body)
        # brilho
        d.ellipse([cx - r * .55, cy - r * .05, cx - r * .30, cy + r * .28], fill=(160, 210, 255))
        d.ellipse([cx - r * .50, cy + r * .33, cx - r * .40, cy + r * .43], fill=(160, 210, 255))
        if not face:
            return
        ey, ex, er = cy + r * 0.18, r * 0.22, r * 0.13
        for sx in (-1, 1):
            x = cx + sx * ex
            if blink:
                d.arc([x - er, ey - er * .4, x + er, ey + er * .9], 200, 340, fill=(30, 30, 60), width=int(W * .018))
            else:
                d.ellipse([x - er, ey - er * 1.25, x + er, ey + er * 1.25], fill="white")
                d.ellipse([x - er * .62, ey - er * .55, x + er * .62, ey + er * .95], fill=(30, 30, 60))
                d.ellipse([x - er * .1, ey - er * .35, x + er * .3, ey + er * .05], fill="white")
            d.ellipse([x + sx * er * .6 - er * .7, ey + er * 1.5, x + sx * er * .6 + er * .7, ey + er * 2.2], fill=(255, 140, 180))
        my, mw = cy + r * 0.55, r * 0.22
        if mouth == 0:
            d.arc([cx - mw, my - mw * .9, cx + mw, my + mw * .6], 20, 160, fill=(30, 30, 60), width=int(W * .02))
        else:
            mh = mw * (0.25 + 0.22 * mouth)
            d.ellipse([cx - mw * .85, my - mh * .6, cx + mw * .85, my + mh * 1.2], fill=(120, 20, 50))
            d.ellipse([cx - mw * .45, my + mh * .45, cx + mw * .45, my + mh * 1.15], fill=(255, 110, 130))
    return sprite(size, size, draw)


def leaf_poly(cx, cy, L, wdt, ang):
    pts = []
    for i in range(41):
        u = i / 40
        pts.append((u * L, math.sin(math.pi * u) * wdt))
    for i in range(40, -1, -1):
        u = i / 40
        pts.append((u * L, -math.sin(math.pi * u) * wdt))
    ca, sa = math.cos(ang), math.sin(ang)
    return [(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in pts]


@lru_cache(maxsize=32)
def object_sprite(name, size):
    if name == "gota":
        return pingo_sprite(size, 0, False)

    def draw(d, W, H):
        cx, cy, r = W / 2, H / 2, W * 0.36
        ol = (40, 40, 90)
        if name == "maca":
            red, hi = (232, 52, 46), (255, 140, 130)
            d.rectangle([cx - r * .06, cy - r * 1.15, cx + r * .06, cy - r * .7], fill=(110, 70, 40))
            d.polygon(leaf_poly(cx + r * .05, cy - r * .9, r * .65, r * .2, -0.5), fill=(70, 180, 70))
            for sx in (-1, 1):
                d.ellipse([cx + sx * r * .38 - r * .7, cy - r * .85, cx + sx * r * .38 + r * .7, cy + r * .95], fill=red)
            d.ellipse([cx - r * .7, cy - r * .5, cx - r * .4, cy - r * .05], fill=hi)
        elif name == "sol":
            yel = (255, 201, 14)
            for i in range(12):
                a = 2 * math.pi * i / 12
                p = [(cx + math.cos(a) * r * 1.32, cy + math.sin(a) * r * 1.32),
                     (cx + math.cos(a + .17) * r * .9, cy + math.sin(a + .17) * r * .9),
                     (cx + math.cos(a - .17) * r * .9, cy + math.sin(a - .17) * r * .9)]
                d.polygon(p, fill=(255, 160, 20))
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=yel)
            for sx in (-1, 1):
                d.ellipse([cx + sx * r * .35 - r * .1, cy - r * .3, cx + sx * r * .35 + r * .1, cy], fill=ol)
            d.arc([cx - r * .45, cy - r * .3, cx + r * .45, cy + r * .5], 20, 160, fill=ol, width=int(W * .025))
        elif name == "folha":
            d.line([cx - r * 1.1, cy + r * .9, cx - r * .6, cy + r * .45], fill=(40, 120, 40), width=int(W * .03))
            d.polygon(leaf_poly(cx - r * .7, cy + r * .5, r * 2.0, r * .75, -0.75), fill=(61, 190, 75))
            d.line([cx - r * .7, cy + r * .5, cx + r * .75, cy - r * .85], fill=(40, 130, 50), width=int(W * .02))
            for k in (0.3, 0.5, 0.7):
                bx, by = cx - r * .7 + r * 1.45 * k, cy + r * .5 - r * 1.35 * k
                d.line([bx, by, bx + r * .35, by + r * .05], fill=(40, 130, 50), width=int(W * .012))
                d.line([bx, by, bx - r * .05, by - r * .35], fill=(40, 130, 50), width=int(W * .012))
        elif name == "laranja":
            org = (255, 138, 31)
            d.ellipse([cx - r, cy - r * .9, cx + r, cy + r * 1.05], fill=org)
            rng = np.random.default_rng(3)
            for _ in range(40):
                a, rr = rng.uniform(0, 2 * math.pi), rng.uniform(0, r * .85)
                x, y = cx + math.cos(a) * rr, cy + .1 * r + math.sin(a) * rr
                d.ellipse([x - r * .025, y - r * .025, x + r * .025, y + r * .025], fill=(235, 110, 20))
            d.ellipse([cx - r * .65, cy - r * .55, cx - r * .3, cy - r * .15], fill=(255, 190, 120))
            d.polygon(leaf_poly(cx, cy - r * .85, r * .7, r * .22, -0.35), fill=(70, 180, 70))
        elif name == "uva":
            pur, hi = (142, 68, 201), (190, 130, 235)
            d.line([cx, cy - r * 1.15, cx + r * .1, cy - r * .7], fill=(110, 70, 40), width=int(W * .03))
            d.polygon(leaf_poly(cx + r * .05, cy - r * .95, r * .7, r * .25, -0.3), fill=(70, 180, 70))
            gr = r * .27
            rows = [4, 3, 3, 2, 1]
            for ri, n in enumerate(rows):
                y = cy - r * .55 + ri * gr * 1.55
                for j in range(n):
                    x = cx + (j - (n - 1) / 2) * gr * 1.75
                    d.ellipse([x - gr, y - gr, x + gr, y + gr], fill=pur, outline=(110, 40, 160), width=int(W * .006))
                    d.ellipse([x - gr * .55, y - gr * .55, x - gr * .1, y - gr * .1], fill=hi)
        elif name == "flor":
            d.line([cx, cy, cx, cy + r * 1.35], fill=(40, 140, 50), width=int(W * .035))
            d.polygon(leaf_poly(cx, cy + r * 1.0, r * .6, r * .2, -0.6), fill=(70, 180, 70))
            d.polygon(leaf_poly(cx, cy + r * .8, r * .6, r * .2, math.pi + 0.6), fill=(70, 180, 70))
            pr = r * .38
            for i in range(6):
                a = 2 * math.pi * i / 6
                x, y = cx + math.cos(a) * r * .5, cy - r * .25 + math.sin(a) * r * .5
                d.ellipse([x - pr, y - pr, x + pr, y + pr], fill=(255, 111, 174))
            d.ellipse([cx - r * .3, cy - r * .55, cx + r * .3, cy + r * .05], fill=(255, 201, 14))
    return sprite(size, size, draw)


@lru_cache(maxsize=32)
def disc_sprite(size, color, ring=True):
    def draw(d, W, H):
        c = hex2rgb(color)
        if ring:
            d.ellipse([0, 0, W - 1, H - 1], fill="white")
            m = W * 0.06
        else:
            m = 0
        d.ellipse([m, m, W - m, H - m], fill=c)
        d.ellipse([W * .22, H * .18, W * .42, H * .34], fill=mix(c, (255, 255, 255), .5))
    return sprite(size, size, draw)


@lru_cache(maxsize=32)
def plate_sprite(size, color):
    def draw(d, W, H):
        c = hex2rgb(color)
        d.ellipse([0, 0, W - 1, H - 1], fill=c)
        m = W * 0.05
        d.ellipse([m, m, W - m, H - m], fill="white")
        m = W * 0.08
        d.ellipse([m, m, W - m, H - m], fill=mix(c, (255, 255, 255), .82))
    return sprite(size, size, draw)


@lru_cache(maxsize=8)
def cloud_sprite(size):
    def draw(d, W, H):
        for x, y, r in [(.3, .6, .22), (.5, .45, .28), (.7, .6, .22), (.5, .68, .2)]:
            d.ellipse([W * (x - r), H * (y - r), W * (x + r), H * (y + r)], fill=(255, 255, 255, 235))
    return sprite(size, size // 2, draw)


@lru_cache(maxsize=32)
def bg_gradient(W, H, top, bottom):
    t, b = np.array(hex2rgb(top), float), np.array(hex2rgb(bottom), float)
    y = np.linspace(0, 1, H)[:, None, None]
    arr = (t * (1 - y) + b * y).astype(np.uint8)
    arr = np.repeat(arr, W, axis=1)
    return Image.fromarray(arr, "RGB").convert("RGBA")


@lru_cache(maxsize=8)
def bg_intro(W, H):
    im = bg_gradient(W, H, "#7FD3FF", "#D8F3FF").copy()
    d = ImageDraw.Draw(im)
    d.ellipse([-W * .2, H * .78, W * .65, H * 1.5], fill=(120, 205, 90))
    d.ellipse([W * .35, H * .82, W * 1.25, H * 1.6], fill=(95, 185, 75))
    return im


@lru_cache(maxsize=32)
def bg_color(W, H, color):
    c = hex2rgb(color)
    top = "#%02x%02x%02x" % mix((255, 255, 255), c, .18)
    bot = "#%02x%02x%02x" % mix((255, 255, 255), c, .42)
    im = bg_gradient(W, H, top, bot).copy()
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(int(hashlib.md5(color.encode()).hexdigest()[:6], 16))
    u = min(W, H)
    for _ in range(18):
        x, y, r = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(.01, .04) * u
        d.ellipse([x - r, y - r, x + r, y + r], fill=mix((255, 255, 255), c, .28))
    return im


# ---------------------------------------------------------------- áudio
def tts(text, cache_dir):
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = cache_dir / (hashlib.md5(f"{text}|{PITCH}|{LENGTH_SCALE}".encode()).hexdigest()[:16] + ".wav")
    if not key.exists():
        subprocess.run([sys.executable, "-m", "piper", "-m", VOICE, "-f", str(key),
                        "--length-scale", str(LENGTH_SCALE)], input=text.encode(),
                       check=True, capture_output=True)
    with wave.open(str(key)) as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    # pitch up (reamostragem) + conversão para 44.1k
    n = int(len(x) * SR / (sr * PITCH))
    x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)
    # corta silêncio das pontas
    idx = np.where(np.abs(x) > 0.02)[0]
    if len(idx):
        x = x[max(0, idx[0] - 800): idx[-1] + 2000]
    return (x / (np.abs(x).max() + 1e-6) * 0.85).astype(np.float32)


def tone(freq, dur, decay=4.0, harm=(1, .35, .12), vol=1.0):
    t = np.arange(int(dur * SR)) / SR
    w = sum(a * np.sin(2 * np.pi * freq * (k + 1) * t) for k, a in enumerate(harm))
    env = np.exp(-decay * t) * np.minimum(1, t / 0.005)
    return (w * env * vol).astype(np.float32)


def sfx(kind):
    if kind == "pop":
        t = np.arange(int(.12 * SR)) / SR
        f = 350 + 1600 * t / .12
        return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-30 * t) * .5).astype(np.float32)
    if kind == "tick":
        return tone(1800, .06, 60, (1,), .35)
    if kind == "ding":
        return tone(1318.5, .9, 4, (1, .2), .3) + np.pad(tone(1760, .75, 4, (1, .2), .3), (int(.15 * SR), 0))[:int(.9 * SR)]
    if kind == "tada":
        out = np.zeros(int(1.2 * SR), np.float32)
        for i, f in enumerate([523.25, 659.25, 783.99, 1046.5]):
            s = tone(f, 1.2 - i * .1, 3, (1, .3, .1), .25)
            o = int(i * .1 * SR)
            out[o:o + len(s)] += s[:len(out) - o]
        return out
    raise ValueError(kind)


def music(total):
    """Trilha original: I–V–vi–IV em Dó maior, arpejo + baixo."""
    bpm = 104
    beat = 60 / bpm
    n = int(total * SR) + SR
    out = np.zeros(n, np.float32)
    prog = [[60, 64, 67, 72], [55, 62, 67, 71], [57, 64, 69, 72], [53, 60, 65, 69]]
    melody = [76, 74, 72, 74, 76, 76, 76, -1, 74, 74, 74, -1, 76, 79, 79, -1]
    midi = lambda m: 440 * 2 ** ((m - 69) / 12)
    cache = {}

    def note(m, dur, dec, harm, vol):
        k = (m, dur, dec, harm, vol)
        if k not in cache:
            cache[k] = tone(midi(m), dur, dec, harm, vol)
        return cache[k]

    bar = 4 * beat
    nb = int(total / bar) + 1
    for b in range(nb):
        ch = prog[b % 4]
        t0 = b * bar
        for i in range(8):
            m = ch[[0, 1, 2, 3, 2, 1, 2, 3][i]]
            s = note(m, .5, 7, (1, .4, .15), .10)
            o = int((t0 + i * beat / 2) * SR)
            out[o:o + len(s)] += s[:max(0, n - o)]
        for i in (0, 2):
            s = note(ch[0] - 24, .9, 3, (1, .5), .16)
            o = int((t0 + i * beat) * SR)
            out[o:o + len(s)] += s[:max(0, n - o)]
        if (b // 4) % 2 == 1:  # melodia de "sininho" em metade das voltas
            for i in range(4):
                m = melody[(b % 4) * 4 + i]
                if m > 0:
                    s = note(m + 12, .7, 5, (1, .1, .05), .07)
                    o = int((t0 + i * beat) * SR)
                    out[o:o + len(s)] += s[:max(0, n - o)]
    return out[:int(total * SR)]


# ---------------------------------------------------------------- linha do tempo
class Seg:
    def __init__(self, kind, **kw):
        self.kind, self.kw = kind, kw
        self.lines = []   # (t_rel, texto)
        self.marks = {}   # eventos nomeados (t_rel)
        self.sfx = []     # (t_rel, tipo)
        self.dur = 0.0


class Builder:
    def __init__(self, cache):
        self.cache = cache
        self.segs = []
        self.voice = {}

    def seg(self, kind, **kw):
        s = Seg(kind, **kw)
        self.segs.append(s)
        return s

    def say(self, s, text, gap_before=0.0, gap_after=0.45):
        s.dur += gap_before
        if text not in self.voice:
            self.voice[text] = tts(text, self.cache)
        s.lines.append((s.dur, text))
        s.dur += len(self.voice[text]) / SR + gap_after

    def wait(self, s, secs, mark=None):
        if mark:
            s.marks[mark] = s.dur
        s.dur += secs


def build_timeline(ep, short, cache):
    B = Builder(cache)
    items = {i["objeto"]: i for i in ep["itens"]}
    if not short:
        s = B.seg("intro", title=ep["titulo_tela"])
        B.wait(s, 0.6)
        s.sfx.append((0.5, "tada"))
        for l in ep["intro"]:
            B.say(s, l)
        B.wait(s, 1.0)
        for it in ep["itens"]:
            s = B.seg("color", item=it)
            s.sfx += [(0.15, "pop"), (0.55, "pop")]
            B.wait(s, 0.9)
            B.say(s, f"Este é o {it['nome']}!", gap_after=.6)
            B.say(s, it["frase"], gap_after=.6)
            B.say(s, f"Repita comigo: {it['nome']}!", gap_after=.3)
            B.wait(s, max(2.2, 10.6 - s.dur), "repete")  # capítulo >= 10 s
    else:
        s = B.seg("intro", title="QUIZ DAS\nCORES")
        s.sfx.append((0.2, "tada"))
        B.wait(s, 0.3)
        for l in ep["short_intro"]:
            B.say(s, l, gap_after=.2)
        B.wait(s, .3)

    quiz = ep["quiz_short"] if short else ep["quiz"]
    palette = [i for i in ep["itens"]]
    rng = np.random.default_rng(7)
    for qi, obj in enumerate(quiz):
        it = items[obj]
        others = [p for p in palette if p is not it]
        opts = [it] + list(rng.choice(others, 2, replace=False))
        rng.shuffle(opts)
        s = B.seg("quiz", item=it, opts=opts, n=qi + 1)
        s.sfx.append((0.1, "pop"))
        B.wait(s, 0.5)
        B.say(s, it["pergunta"], gap_after=.3)
        s.marks["count"] = s.dur
        for k in range(3):
            s.sfx.append((s.dur + k, "tick"))
        B.wait(s, 3.0)
        s.marks["reveal"] = s.dur
        s.sfx.append((s.dur, "ding"))
        B.say(s, it["resposta"], gap_before=.15, gap_after=.9)

    if not short:
        s = B.seg("recap", items=ep["itens"])
        B.say(s, ep["recap_intro"], gap_after=.3)
        s.marks["start"] = s.dur
        for k, it in enumerate(ep["itens"]):
            s.marks[f"i{k}"] = s.dur
            s.sfx.append((s.dur, "pop"))
            B.say(s, it["nome"].capitalize() + "!", gap_after=.35)
        B.wait(s, 1.2)

    s = B.seg("outro")
    s.sfx.append((0.1, "tada"))
    B.wait(s, .3)
    for l in (ep["short_outro"] if short else ep["outro"]):
        B.say(s, l, gap_after=.5)
    B.wait(s, 1.5)

    t = 0.0
    for s in B.segs:
        s.t0 = t
        t += s.dur
    return B, t


# ---------------------------------------------------------------- render
class Renderer:
    def __init__(self, W, H, B, total, envelope):
        self.W, self.H, self.B, self.total, self.env = W, H, B, total, envelope
        self.u = min(W, H)
        self.vertical = H > W

    def mouth(self, t):
        i = int(t * FPS)
        v = self.env[i] if i < len(self.env) else 0
        return 0 if v < .08 else min(3, 1 + int(v * 3.2))

    def pingo(self, fr, t, cx, cy, size, wave=False):
        blink = (t % 3.7) < 0.12
        spr = pingo_sprite(size, self.mouth(t), blink)
        bob = math.sin(t * 2 * math.pi * 1.6) * size * 0.025
        squash = 1 + math.sin(t * 2 * math.pi * 1.6) * 0.015
        rot = math.sin(t * 2 * math.pi * 1.2) * (9 if wave else 3)
        paste_center(fr, spr, cx, cy + bob, squash, rot)

    def frame(self, t):
        W, H, u = self.W, self.H, self.u
        seg = self.B.segs[-1]
        for s in self.B.segs:
            if s.t0 <= t < s.t0 + s.dur:
                seg = s
                break
        lt = t - seg.t0
        getattr(self, "f_" + seg.kind)(seg, lt, t)
        fr = self.fr
        # fade entre segmentos
        fade = min(1, lt / .25, (seg.dur - lt) / .2 if seg is not self.B.segs[-1] else 1)
        if t > self.total - .5:
            fade = min(fade, (self.total - t) / .5)
        if fade < 1:
            fr = Image.blend(Image.new("RGBA", fr.size, (255, 255, 255, 255)), fr, max(0, fade))
        return fr.convert("RGB")

    def clouds(self, fr, t):
        W, H, u = self.W, self.H, self.u
        for k, (y, sp, sz) in enumerate([(.12, 25, .35), (.25, 15, .25), (.08, 10, .2)]):
            cs = cloud_sprite(int(u * sz))
            x = ((k * .37 * W + t * sp * u / 400) % (W + cs.width)) - cs.width / 2
            paste_center(fr, cs, x, H * y)

    def f_intro(self, seg, lt, t):
        W, H, u = self.W, self.H, self.u
        self.fr = fr = bg_intro(W, H).copy()
        self.clouds(fr, t)
        ts = text_sprite(seg.kw["title"], int(u * .13), "#FFD23F")
        k = ease_out_back((lt - .4) / .6) * (1 + .03 * math.sin(lt * 4))
        if self.vertical:
            paste_center(fr, ts, W / 2, H * .25, k)
            self.pingo(fr, t, W / 2, H * .62, int(u * .7) // 1)
        else:
            paste_center(fr, ts, W * .63, H * .42, k)
            self.pingo(fr, t, W * .25, H * .55, int(u * .62))

    def f_color(self, seg, lt, t):
        W, H, u = self.W, self.H, self.u
        it = seg.kw["item"]
        self.fr = fr = bg_color(W, H, it["cor"]).copy()
        disc = plate_sprite(int(u * .66), it["cor"])
        obj = object_sprite(it["objeto"], int(u * .5))
        word = text_sprite(it["nome"].upper(), int(u * .15), it["cor"])
        pulse = 1.0
        if "repete" in seg.marks and lt > seg.marks["repete"]:
            pulse = 1 + .08 * abs(math.sin((lt - seg.marks["repete"]) * math.pi * 1.5))
        if self.vertical:
            dc, wc, pc, ps = (W / 2, H * .45), (W / 2, H * .17), (W * .5, H * .8), int(u * .45)
        else:
            dc, wc, pc, ps = (W * .26, H * .5), (W * .7, H * .36), (W * .72, H * .74), int(u * .36)
        paste_center(fr, disc, *dc, ease_out_back(lt / .45))
        paste_center(fr, obj, dc[0], dc[1] + math.sin(lt * 3) * u * .01, ease_out_back((lt - .4) / .5))
        paste_center(fr, word, *wc, ease_out_back((lt - .7) / .5) * pulse)
        if it["objeto"] != "gota":
            self.pingo(fr, t, *pc, ps)

    def f_quiz(self, seg, lt, t):
        W, H, u = self.W, self.H, self.u
        it, opts = seg.kw["item"], seg.kw["opts"]
        self.fr = fr = bg_gradient(W, H, "#FFF6D6", "#FFE08A").copy()
        tag = text_sprite(f"QUIZ {seg.kw['n']}", int(u * .07), "#FF6FAE")
        paste_center(fr, tag, W * (.5 if self.vertical else .12), H * (.06 if self.vertical else .1), ease_out_back(lt / .4))
        reveal = lt >= seg.marks["reveal"]
        obj = object_sprite(it["objeto"], int(u * (.42 if self.vertical else .4)))
        oc = (W / 2, H * .33) if self.vertical else (W / 2, H * .33)
        paste_center(fr, obj, *oc, ease_out_back((lt - .1) / .5) * (1 + (.06 * math.sin(lt * 6) if reveal else 0)))
        # opções
        n = len(opts)
        for k, o in enumerate(opts):
            if self.vertical:
                cx, cy = W * (.2 + .3 * k), H * .62
            else:
                cx, cy = W * (.55 + (k - 1) * .2), H * .76
            sz = int(u * .2)
            sc = ease_out_back((lt - .5 - .15 * k) / .4)
            alpha = 1.0
            if reveal:
                rt = lt - seg.marks["reveal"]
                if o is it:
                    sc *= 1 + .25 * ease_out(rt / .3) + .04 * math.sin(rt * 8)
                else:
                    alpha, sc = .35, sc * .9
            paste_center(fr, disc_sprite(sz, o["cor"]), cx, cy, sc, alpha=alpha)
            lbl = text_sprite(o["nome"].upper(), int(u * .045), o["cor"])
            paste_center(fr, lbl, cx, cy + sz * .72, sc, alpha=alpha)
        # contagem regressiva
        c0 = seg.marks["count"]
        if c0 <= lt < seg.marks["reveal"]:
            num = 3 - int(lt - c0)
            ph = (lt - c0) % 1
            ns = text_sprite(str(num), int(u * .16), "#FFFFFF", outline="#FF6FAE")
            pos = (W / 2, H * .5) if self.vertical else (W * .86, H * .33)
            paste_center(fr, ns, *pos, ease_out_back(ph / .35), alpha=1 - max(0, ph - .7) / .3)
        if reveal:
            rt = lt - seg.marks["reveal"]
            star = text_sprite("★", int(u * .12), "#FFD23F")
            for k in range(6):
                a = 2 * math.pi * k / 6 + rt
                rr = u * .18 * ease_out(rt / .5)
                paste_center(fr, star, oc[0] + math.cos(a) * rr * 1.4, oc[1] + math.sin(a) * rr, .6, alpha=max(0, 1 - rt / 2.5))
        pc = (W * .5, H * .86) if self.vertical else (W * .12, H * .78)
        self.pingo(fr, t, *pc, int(u * (.26 if self.vertical else .3)))

    def f_recap(self, seg, lt, t):
        W, H, u = self.W, self.H, self.u
        self.fr = fr = bg_intro(W, H).copy()
        self.clouds(fr, t)
        items = seg.kw["items"]
        n = len(items)
        for k, it in enumerate(items):
            t0 = seg.marks[f"i{k}"]
            if lt < t0:
                continue
            if self.vertical:
                cx, cy = W * (.3 if k % 2 == 0 else .7), H * (.15 + .1 * k)
            else:
                cx, cy = W * (.1 + .8 * k / (n - 1)), H * .42 + math.sin(k / (n - 1) * math.pi) * -H * .12
            sz = int(u * .2)
            sc = ease_out_back((lt - t0) / .35) * (1 + .04 * math.sin(lt * 5 + k))
            paste_center(fr, disc_sprite(sz, it["cor"]), cx, cy, sc)
            paste_center(fr, text_sprite(it["nome"].upper(), int(u * .04), it["cor"]), cx, cy + sz * .68, sc)
        self.pingo(fr, t, W / 2, H * (.85 if self.vertical else .78), int(u * .33))

    def f_outro(self, seg, lt, t):
        W, H, u = self.W, self.H, self.u
        self.fr = fr = bg_intro(W, H).copy()
        self.clouds(fr, t)
        logo = text_sprite("Turminha\ndo Pingo", int(u * .12), PINGO_AZUL)
        tchau = text_sprite("TCHAU!", int(u * .1), "#FF6FAE")
        if self.vertical:
            paste_center(fr, logo, W / 2, H * .2, ease_out_back(lt / .6))
            self.pingo(fr, t, W / 2, H * .55, int(u * .7), wave=True)
            paste_center(fr, tchau, W / 2, H * .82, ease_out_back((lt - 1.2) / .5))
        else:
            paste_center(fr, logo, W * .66, H * .38, ease_out_back(lt / .6))
            paste_center(fr, tchau, W * .66, H * .7, ease_out_back((lt - 1.2) / .5))
            self.pingo(fr, t, W * .27, H * .56, int(u * .62), wave=True)


def thumbnail(ep, path):
    W, H = 1280, 720
    u = H
    fr = bg_gradient(W, H, "#FFF6D6", "#FFD9EC").copy()
    d = ImageDraw.Draw(fr)
    cols = [i["cor"] for i in ep["itens"]]
    for k, c in enumerate(cols):  # arco-íris
        r = W * .62 - k * 34
        d.ellipse([W * .5 - r, H * 1.05 - r, W * .5 + r, H * 1.05 + r], outline=hex2rgb(c), width=36)
    paste_center(fr, pingo_sprite(int(u * .78), 2), W * .25, H * .58, rot=6)
    paste_center(fr, object_sprite("maca", int(u * .3)), W * .62, H * .78)
    paste_center(fr, object_sprite("sol", int(u * .3)), W * .88, H * .2)
    paste_center(fr, object_sprite("flor", int(u * .28)), W * .9, H * .76)
    paste_center(fr, text_sprite("AS CORES", int(u * .2), "#FF6FAE"), W * .66, H * .45, rot=4)
    fr.convert("RGB").save(path, quality=92)


def fmt(t):
    return f"{int(t // 60):02d}:{int(t % 60):02d}"


def metadata(ep, B, short, path):
    y = ep["youtube"]
    if short:
        txt = f"TÍTULO:\n{y['titulo_short']}\n\nDESCRIÇÃO:\nQual é a cor? Brinque de quiz com o Pingo! 🎨\n#shorts #cores #infantil\n"
    else:
        ch, names = [], {"intro": "Oi, eu sou o Pingo!", "recap": "Todas as cores juntas", "outro": "Tchau!"}
        quiz_done = False
        for s in B.segs:
            if s.kind == "color":
                ch.append((s.t0, f"Cor {s.kw['item']['nome']}"))
            elif s.kind == "quiz":
                if not quiz_done:
                    ch.append((s.t0, "Quiz: qual é a cor?"))
                    quiz_done = True
            elif s.kind == "outro":
                pass  # o encerramento fica dentro do último capítulo (mín. 10 s por capítulo)
            else:
                ch.append((s.t0, names[s.kind]))
        if len(ch) > 1 and ch[1][0] - ch[0][0] < 10:  # capítulo precisa de >= 10 s
            ch = [(0.0, ch[0][1] + " / " + ch[1][1])] + ch[2:]
        ch[0] = (0.0, ch[0][1])
        chapters = "\n".join(f"{fmt(a)} {b}" for a, b in ch)
        cores = ", ".join(i["nome"] for i in ep["itens"])
        txt = (f"TÍTULO:\n{y['titulo']}\n\nDESCRIÇÃO:\n"
               f"Vamos aprender as cores com o Pingo, a gotinha mais animada do YouTube! 💧🌈\n"
               f"Neste vídeo a criança aprende: {cores}. No final tem um quiz para brincar junto!\n\n"
               f"Ideal para crianças de 2 a 5 anos. Assista junto e repita as palavras em voz alta. 💙\n\n"
               f"CAPÍTULOS:\n{chapters}\n\n"
               f"Voz sintetizada (Piper TTS, voz 'edresson', CC BY 4.0). Música e animação originais.\n\n"
               f"TAGS:\n{', '.join(y['tags'])}\n\n"
               f"CONFIGURAÇÃO NO UPLOAD:\n- Público: SIM, é conteúdo para crianças (COPPA)\n"
               f"- Conteúdo alterado/sintético: NÃO é necessário marcar (animação claramente fictícia)\n"
               f"- Categoria: Educação | Idioma: Português (Brasil)\n")
    Path(path).write_text(txt, encoding="utf-8")


def main():
    ep_path = Path(sys.argv[1])
    short = "--short" in sys.argv
    preview = "--preview" in sys.argv
    ep = json.loads(ep_path.read_text(encoding="utf-8"))
    W, H = (1080, 1920) if short else (1920, 1080)
    if preview:
        W, H = W // 2, H // 2
    OUT.mkdir(exist_ok=True)
    name = ep["slug"] + ("-short" if short else "")
    cache = BASE / ".cache_voz"

    print("» sintetizando voz e montando linha do tempo…")
    B, total = build_timeline(ep, short, cache)
    print(f"  duração: {fmt(total)} ({total:.1f}s), {len(B.segs)} cenas")

    n = int(total * SR) + SR
    voice = np.zeros(n, np.float32)
    fx = np.zeros(n, np.float32)
    for s in B.segs:
        for tr, text in s.lines:
            v = B.voice[text]
            o = int((s.t0 + tr) * SR)
            voice[o:o + len(v)] += v
        for tr, kind in s.sfx:
            x = sfx(kind)
            o = int((s.t0 + tr) * SR)
            fx[o:o + len(x)] += x[:n - o]
    # envelope da voz por frame (boca do Pingo)
    hop = SR // FPS
    env = np.array([np.sqrt(np.mean(voice[i:i + hop] ** 2)) for i in range(0, n - hop, hop)])
    env = env / (env.max() + 1e-6)
    # trilha com "ducking"
    m = music(n / SR)
    act = np.repeat((env > .05).astype(np.float32), hop)[:n]
    act = np.pad(act, (0, n - len(act)))
    k = int(.25 * SR)
    duck = np.convolve(act, np.ones(k) / k, mode="same")
    mixd = voice + fx + m * (1 - .6 * duck)
    mixd = np.tanh(mixd * 1.1) * .9
    mixd = mixd[:int(total * SR)]
    tmp = Path(tempfile.mkdtemp())
    wav = tmp / "a.wav"
    with wave.open(str(wav), "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mixd * 32767).astype(np.int16).tobytes())

    print(f"» renderizando {W}x{H} @ {FPS}fps…")
    R = Renderer(W, H, B, total, env)
    mp4 = OUT / f"{name}.mp4"
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(wav),
                           "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(mp4)],
                          stdin=subprocess.PIPE)
    nf = int(total * FPS)
    for i in range(nf):
        ff.stdin.write(R.frame(i / FPS).tobytes())
        if i % (FPS * 20) == 0:
            print(f"  {i / FPS:5.0f}s / {total:.0f}s", flush=True)
    ff.stdin.close()
    ff.wait()
    if not short:
        thumbnail(ep, OUT / f"{name}-thumb.jpg")
    metadata(ep, B, short, OUT / f"{name}-youtube.txt")
    print(f"✔ {mp4}")


if __name__ == "__main__":
    main()
