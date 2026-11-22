"""Gera foto de perfil (800x800) e banner (2560x1440) do canal."""
import math
from PIL import ImageDraw
import gerar as g

# Foto de perfil: o YouTube recorta em círculo
av = g.bg_gradient(800, 800, "#7FD3FF", "#D8F3FF").copy()
d = ImageDraw.Draw(av)
for k, c in enumerate([i for i in ["#E8342E", "#FFC90E", "#3DBE4B", "#FF6FAE"]]):
    a = math.radians(200 + k * 45); x, y = 400 + math.cos(a) * 330, 400 + math.sin(a) * 330
    d.ellipse([x - 28, y - 28, x + 28, y + 28], fill=g.hex2rgb(c))
g.paste_center(av, g.pingo_sprite(600, 0), 400, 430)
av.convert("RGB").save("saida/foto-perfil.png")

# Banner: a área segura (aparece em todos os aparelhos) é 1546x423, no centro
W, H = 2560, 1440
bn = g.bg_intro(W, H).copy()
d = ImageDraw.Draw(bn)
cores = ["#E8342E", "#FF8A1F", "#FFC90E", "#3DBE4B", "#2F8CFF", "#8E44C9", "#FF6FAE"]
for k, c in enumerate(cores):
    r = 1500 - k * 60
    d.ellipse([W / 2 - r, H * 1.15 - r, W / 2 + r, H * 1.15 + r], outline=g.hex2rgb(c), width=60)
for x, y, s in [(.15, .2, .5), (.8, .15, .4), (.6, .3, .3)]:
    g.paste_center(bn, g.cloud_sprite(int(1440 * s)), W * x, H * y)
g.paste_center(bn, g.pingo_sprite(380, 0), 760, 720)
g.paste_center(bn, g.text_sprite("Turminha do Pingo", 112, g.PINGO_AZUL), 1480, 680)
g.paste_center(bn, g.text_sprite("cores • números • formas • diversão", 52, "#FF6FAE"), 1480, 790)
for o, x in [("maca", 1830), ("sol", 600), ("flor", 1960)]:
    g.paste_center(bn, g.object_sprite(o, 180), x, 1000 if o != "sol" else 380)
bn.convert("RGB").save("saida/banner.png")
