#!/usr/bin/env python3
"""Álbum "Caixinha de Música do Pingo" — canções de ninar instrumentais 100% originais.

    python3 musica.py            # álbum (WAV) + capa 3000x3000 + metadados
    python3 musica.py --video    # também gera vídeo de 1 hora "para dormir" para o YouTube

Melodias compostas por algoritmo (semente fixa → sempre as mesmas músicas),
sintetizadas por código: sem samples, sem trechos de músicas de terceiros.
"""
import math, subprocess, sys, wave
from pathlib import Path

import numpy as np
import pyloudnorm as pyln
from PIL import Image, ImageDraw
from scipy.signal import butter, fftconvolve, sosfilt

import gerar as g

SR = 44100
OUT = g.OUT / "album"
ARTISTA = "Turminha do Pingo"
ALBUM = "Caixinha de Música do Pingo: Canções de Ninar para Bebês"

FAIXAS = [
    ("Ninar do Pingo", 11), ("Estrelinha Sonolenta", 23), ("Nuvem de Algodão", 37),
    ("Gotinha de Chuva", 41), ("Carneirinhos no Céu", 53), ("Boa Noite, Sol", 67),
    ("Barquinho no Mar Calmo", 71), ("Sonho Colorido", 89), ("Abraço Quentinho", 97),
    ("Lua de Travesseiro", 103),
]

MAJOR = [0, 2, 4, 5, 7, 9, 11]
PROGS = [[0, 5, 3, 4], [0, 3, 0, 4], [0, 2, 3, 4], [5, 3, 0, 4], [0, 3, 5, 4], [3, 4, 0, 0]]
RHY3 = [[2, 1], [1, 1, 1], [3], [1, 2], [2, 1]]
RHY4 = [[2, 2], [1, 1, 2], [2, 1, 1], [3, 1], [4]]


def midi2hz(m):
    return 440 * 2 ** ((m - 69) / 12)


# ---------------------------------------------------------------- timbres
def inst(kind, f, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    att = np.minimum(1, t / (.004 if kind != "piano" else .018))
    if kind == "caixinha":       # caixinha de música
        w = (np.sin(2 * np.pi * f * t) * np.exp(-2.2 * t)
             + .25 * np.sin(2 * np.pi * f * 2 * t) * np.exp(-5 * t)
             + .08 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-12 * t))
    elif kind == "celesta":
        w = (np.sin(2 * np.pi * f * t) + .3 * np.sin(2 * np.pi * f * 4 * t) * np.exp(-6 * t)) * np.exp(-1.6 * t)
    elif kind == "kalimba":
        w = (np.sin(2 * np.pi * f * t) + .18 * np.sin(2 * np.pi * f * 5.95 * t) * np.exp(-14 * t)) * np.exp(-2.8 * t)
    elif kind == "piano":        # piano macio para o acompanhamento
        w = (np.sin(2 * np.pi * f * t) + .35 * np.sin(2 * np.pi * f * 2 * t) * np.exp(-3 * t)
             + .1 * np.sin(2 * np.pi * f * 3 * t) * np.exp(-6 * t)) * np.exp(-1.8 * t)
    elif kind == "pad":
        a = np.minimum(1, t / .9) * np.minimum(1, (dur - t) / .9)
        w = (np.sin(2 * np.pi * f * t) + .2 * np.sin(2 * np.pi * f * 2.003 * t)) * a
        return (w * .5).astype(np.float32)
    rel = np.minimum(1, np.maximum(0, (dur - t) / .08))
    return (w * att * rel).astype(np.float32)


# ---------------------------------------------------------------- composição
def compose(seed):
    rng = np.random.default_rng(seed)
    meter = 3 if rng.random() < .55 else 4
    bpm = int(rng.integers(60, 74))
    root = int(rng.choice([60, 62, 65, 67, 58]))
    lead = str(rng.choice(["caixinha", "celesta", "kalimba"]))
    pa, pb = (PROGS[i] for i in rng.choice(len(PROGS), 2, replace=False))
    rhy = RHY3 if meter == 3 else RHY4

    def deg2midi(d, octv=0):
        return root + MAJOR[d % 7] + 12 * (d // 7) + 12 * octv

    def phrase(prog):
        notes, prev = [], 7 + 2  # começa perto da terça na oitava de cima
        bars = prog + prog
        for bi, ch in enumerate(bars):
            last = bi in (3, 7)
            pat = [meter] if bi == 7 else ([meter - 1, 1] if last else list(rhy[rng.integers(len(rhy))]))
            chord = [ch, ch + 2, ch + 4]
            for k, dur in enumerate(pat):
                if k == 0 or bi == 7:
                    cands = [c + 7 * o for c in chord for o in (0, 1, 2)]
                    if bi == 7:
                        cands = [7, 14]
                    d = min(cands, key=lambda c: abs(c - prev) + rng.random() * 1.5)
                else:
                    d = prev + int(rng.choice([-2, -1, -1, 1, 1, 2]))
                d = int(np.clip(d, 5, 16))
                notes.append((d, dur))
                prev = d
        return bars, notes

    A = phrase(pa)
    B = phrase(pb)
    form = [A, A, B, A]
    return dict(meter=meter, bpm=bpm, root=root, lead=lead, form=form, deg2midi=deg2midi)


def render(seed):
    c = compose(seed)
    beat = 60 / c["bpm"]
    bar = beat * c["meter"]
    passes = 2
    nbars = sum(len(sec[0]) for sec in c["form"]) * passes + 2
    total = nbars * bar + 8
    L = np.zeros(int(total * SR), np.float32)
    R = np.zeros_like(L)
    cache = {}

    def add(kind, m, dur, t0, vol, pan):
        k = (kind, m, round(dur, 3))
        if k not in cache:
            cache[k] = inst(kind, midi2hz(m), dur)
        s = cache[k] * vol
        o = int(t0 * SR)
        e = min(len(L), o + len(s))
        L[o:e] += s[:e - o] * (1 - pan) * 1.4
        R[o:e] += s[:e - o] * pan * 1.4

    t = bar  # 1 compasso de respiro no início
    rng = np.random.default_rng(seed + 1)
    d2m = c["deg2midi"]
    for p in range(passes):
        for si, (bars, notes) in enumerate(c["form"]):
            # melodia
            tm = t
            for d, dur in notes:
                octv = 1 if (p == 1 and si == 2) else 0
                hum = rng.normal(0, .008)
                add(c["lead"], d2m(d, octv), max(dur * beat * 1.6, 1.2), tm + hum, .32, .55)
                tm += dur * beat
            # acompanhamento: arpejo suave + pad + baixo
            for bi, ch in enumerate(bars):
                tb = t + bi * bar
                chord = [d2m(ch, -1), d2m(ch + 4, -1), d2m(ch + 2, 0)]
                pat = [0, 1, 2] if c["meter"] == 3 else [0, 1, 2, 1]
                for k, idx in enumerate(pat):
                    add("piano", chord[idx], beat * 2.2, tb + k * beat, .13 if k else .17, .4)
                add("pad", d2m(ch, -1), bar, tb, .05, .5)
                add("pad", d2m(ch + 2, -1), bar, tb, .035, .5)
                add("piano", d2m(ch, -2), bar * 1.2, tb, .12, .5)
            t += len(bars) * bar
    # final: acorde de tônica longo
    for m in (d2m(0, -2), d2m(0, -1), d2m(4, -1), d2m(2, 0), d2m(7, 0)):
        add("piano", m, 6, t, .13, .5)
    add(c["lead"], d2m(7, 0), 4, t + beat, .3, .55)
    end = int((t + 7) * SR)
    x = np.stack([L[:end], R[:end]], 1)

    # suaviza (passa-baixa) + reverb de sala grande
    x = sosfilt(butter(2, 5200, fs=SR, output="sos"), x, axis=0)
    x = sosfilt(butter(2, 45, btype="highpass", fs=SR, output="sos"), x, axis=0)
    rr = np.random.default_rng(5)
    tt = np.arange(int(2.6 * SR)) / SR
    irs = [rr.normal(0, 1, len(tt)) * np.exp(-tt / .55) for _ in range(2)]
    irs = [sosfilt(butter(1, 3500, fs=SR, output="sos"), ir) for ir in irs]
    wet = np.stack([fftconvolve(x[:, i], irs[i])[:len(x)] for i in range(2)], 1)
    wet *= np.abs(x).max() / (np.abs(wet).max() + 1e-9)
    y = x * .75 + wet * .45
    # fades
    n = len(y)
    fi, fo = int(1.5 * SR), int(6 * SR)
    y[:fi] *= np.linspace(0, 1, fi)[:, None]
    y[-fo:] *= np.linspace(1, 0, fo)[:, None] ** 1.5
    # loudness: -16 LUFS (calmo), pico <= -1 dBFS
    meter = pyln.Meter(SR)
    y = pyln.normalize.loudness(y, meter.integrated_loudness(y), -16.0)
    pk = np.abs(y).max()
    if pk > .89:
        y *= .89 / pk
    return y.astype(np.float32), c


def write_wav(path, y):
    with wave.open(str(path), "w") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(y, -1, 1) * 32767).astype("<i2").tobytes())


# ---------------------------------------------------------------- arte
def night_bg(W, H):
    return g.bg_gradient(W, H, "#1B1F5E", "#5B4FA8").copy()


def moon_sprite(size):
    im = Image.new("RGBA", (size * 3, size * 3), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    S = size * 3
    d.ellipse([S * .05, S * .05, S * .95, S * .95], fill=(255, 228, 120, 255))
    d.ellipse([S * .32, -S * .08, S * 1.2, S * .78], fill=(0, 0, 0, 0))
    return im.resize((size, size), Image.LANCZOS)


def stars(W, H, n, seed):
    r = np.random.default_rng(seed)
    return [(r.uniform(0, W), r.uniform(0, H * .75), r.uniform(1.5, 4.5), r.uniform(0, 2 * math.pi), int(r.integers(1, 4))) for _ in range(n)]


def sleepy_frame(W, H, t, loop, star_list, bg, moon, moon_xy=(.8, .22)):
    fr = bg.copy()
    d = ImageDraw.Draw(fr)
    u = min(W, H)
    for x, y, r, ph, k in star_list:
        a = .55 + .45 * math.sin(2 * math.pi * k * t / loop + ph)
        c = int(150 + 105 * a)
        rr = r * (u / 1080) * (0.8 + .4 * a)
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=(c, c, int(c * .9)))
    g.paste_center(fr, moon, W * moon_xy[0], H * moon_xy[1])
    d.ellipse([-W * .2, H * .8, W * .7, H * 1.5], fill=(60, 70, 140))
    d.ellipse([W * .3, H * .84, W * 1.2, H * 1.6], fill=(50, 58, 125))
    breathe = 1 + .02 * math.sin(2 * math.pi * 2 * t / loop)
    g.paste_center(fr, g.pingo_sprite(int(u * .42), 0, True), W * .45, H * .66, breathe)
    for k in range(3):
        ph = ((t / loop) * 4 + k / 3) % 1
        z = g.text_sprite("z", int(u * (.05 + .03 * k)), "#FFFFFF", outline="#8E8EE8", shadow=False)
        g.paste_center(fr, z, W * .55 + ph * u * .12 + k * u * .02, H * .52 - ph * u * .3, alpha=math.sin(math.pi * ph))
    return fr


def cover(path):
    S = 3000
    im = night_bg(S, S)
    st = stars(S, S, 90, 3)
    im = sleepy_frame(S, S, 0, 20, st, im, moon_sprite(int(S * .22)), (.8, .4))
    g.paste_center(im, g.text_sprite("Caixinha de Música", 260, "#FFE478", outline="#3B3592"), S / 2, S * .1)
    g.paste_center(im, g.text_sprite("do Pingo", 300, "#FFFFFF", outline=g.PINGO_AZUL), S / 2, S * .2)
    g.paste_center(im, g.text_sprite("Canções de Ninar", 170, "#FFB8D9", outline="#3B3592"), S / 2, S * .92)
    im.convert("RGB").save(path, quality=95)


def sleep_video(album_wav, minutes=60):
    W, H, FPS, LOOP = 1920, 1080, 24, 20
    bg = night_bg(W, H)
    st = stars(W, H, 70, 9)
    moon = moon_sprite(int(H * .26))
    loop = OUT / "loop.mp4"
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", str(loop)],
                          stdin=subprocess.PIPE)
    for i in range(LOOP * FPS):
        ff.stdin.write(sleepy_frame(W, H, i / FPS, LOOP, st, bg, moon).convert("RGB").tobytes())
    ff.stdin.close(); ff.wait()
    out = OUT / "pingo-musica-para-dormir-1-hora.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", str(loop),
                    "-stream_loop", "-1", "-i", str(album_wav), "-t", str(minutes * 60),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", str(out)], check=True)
    loop.unlink()
    return out


def fmt(s):
    return f"{int(s // 60)}:{int(s % 60):02d}"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    all_audio, info = [], []
    for i, (nome, seed) in enumerate(FAIXAS, 1):
        y, c = render(seed)
        fn = OUT / f"{i:02d} - {nome}.wav"
        write_wav(fn, y)
        all_audio.append(y)
        info.append((i, nome, len(y) / SR, c))
        print(f"  {i:02d} {nome:28s} {fmt(len(y) / SR)}  {c['meter']}/4 {c['bpm']}bpm {c['lead']}")
    cover(OUT / "capa-3000.jpg")
    gap = np.zeros((int(1.5 * SR), 2), np.float32)
    full = np.concatenate([np.concatenate([a, gap]) for a in all_audio])
    write_wav(OUT / "album-completo.wav", full)
    total = sum(d for _, _, d, _ in info)
    meta = [f"ARTISTA: {ARTISTA}", f"ÁLBUM: {ALBUM}", "GÊNERO: Infantil (Children's Music) / subgênero: Canções de ninar",
            "IDIOMA: Instrumental", "COMPOSITOR/PRODUTOR: (seu nome)", "Selo: Turminha do Pingo",
            "Explícito: NÃO", "Conteúdo feito com IA: SIM — informe ao distribuidor se ele perguntar",
            f"Duração total: {fmt(total)}", "", "FAIXAS:"]
    meta += [f"{i:02d}. {n} ({fmt(d)})" for i, n, d, _ in info]
    (OUT / "metadados.txt").write_text("\n".join(meta) + "\n", encoding="utf-8")
    print(f"✔ álbum: {fmt(total)}")
    if "--video" in sys.argv:
        print("» vídeo de 1 hora…")
        print("✔", sleep_video(OUT / "album-completo.wav"))


if __name__ == "__main__":
    main()
