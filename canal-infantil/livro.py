#!/usr/bin/env python3
"""Livro de colorir da Turminha do Pingo — gera PDFs prontos para o Amazon KDP.

    python3 livro.py

Saída (pasta saida/livro/):
  miolo.pdf  — 8,5 x 11 pol, sem sangria, 300 DPI, P&B, desenhos só na frente da folha
  capa.pdf   — capa completa (contracapa + lombada + capa), com sangria, colorida
  kdp.txt    — título, descrição, palavras-chave e configurações para preencher no KDP
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw

import gerar as g

OUT = g.OUT / "livro"
DPI = 300
K = 2                      # desenha em 2x e reduz
PW, PH = int(8.5 * DPI) * K, 11 * DPI * K
LW = 22 * K                # espessura do traço (~1,9 mm): fácil para criança pequena
BLACK, WHITE = 0, 255


# ---------------------------------------------------------------- caneta
class Pen:
    def __init__(self, d, x0, y0, size):
        self.d, self.x0, self.y0, self.s = d, x0, y0, size

    def P(self, x, y):
        return (self.x0 + x * self.s, self.y0 + y * self.s)

    def _ell(self, cx, cy, rx, ry, grow, fill):
        x, y = self.P(cx, cy)
        self.d.ellipse([x - rx * self.s - grow, y - ry * self.s - grow,
                        x + rx * self.s + grow, y + ry * self.s + grow], fill=fill)

    def _poly(self, pts, grow, fill):
        q = [self.P(*p) for p in pts]
        self.d.polygon(q, fill=fill)
        if grow:
            self.d.line(q + q[:2], fill=fill, width=int(grow * 2), joint="curve")
            for p in q:
                self.d.ellipse([p[0] - grow, p[1] - grow, p[0] + grow, p[1] + grow], fill=fill)

    def shape(self, *parts):
        """União de formas com contorno único. parts: ('e',cx,cy,rx,ry) | ('p',[pts]) | ('r',x0,y0,x1,y1)"""
        def norm(p):
            if p[0] == "r":
                _, a, b, c, e = p
                return ("p", [(a, b), (c, b), (c, e), (a, e)])
            if p[0] == "e" and len(p) == 4:
                return p + (p[3],)
            return p
        parts = [norm(p) for p in parts]
        for grow, fill in ((LW, BLACK), (0, WHITE)):
            for p in parts:
                if p[0] == "e":
                    self._ell(*p[1:], grow, fill)
                else:
                    self._poly(p[1], grow, fill)

    def e(self, cx, cy, rx, ry=None):
        self.shape(("e", cx, cy, rx, ry if ry is not None else rx))

    def poly(self, pts):
        self.shape(("p", pts))

    def line(self, pts, w=1.0):
        q = [self.P(*p) for p in pts]
        lw = int(LW * w)
        self.d.line(q, fill=BLACK, width=lw, joint="curve")
        for p in (q[0], q[-1]):
            self.d.ellipse([p[0] - lw / 2, p[1] - lw / 2, p[0] + lw / 2, p[1] + lw / 2], fill=BLACK)

    def arc(self, cx, cy, rx, ry, a0, a1, w=1.0):
        pts = [(cx + rx * math.cos(math.radians(a)), cy + ry * math.sin(math.radians(a)))
               for a in range(int(a0), int(a1) + 1, 3)]
        self.line(pts, w)

    def dot(self, cx, cy, r):
        x, y = self.P(cx, cy)
        self.d.ellipse([x - r * self.s, y - r * self.s, x + r * self.s, y + r * self.s], fill=BLACK)

    def face(self, cx, cy, sz, smile=True):
        for sx in (-1, 1):
            self.dot(cx + sx * sz * .35, cy - sz * .1, sz * .1)
        if smile:
            self.arc(cx, cy + sz * .05, sz * .3, sz * .22, 20, 160, .8)


def curve_pts(f, n=60):
    return [f(i / (n - 1)) for i in range(n)]


def tube(center, w0, w1):
    """Polígono ao redor de uma curva central com largura variável (banana, etc.)."""
    left, right = [], []
    for i in range(len(center)):
        a, b = center[max(0, i - 1)], center[min(len(center) - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy) or 1
        nx, ny = -dy / L, dx / L
        t = i / (len(center) - 1)
        w = (w0 + (w1 - w0) * t) * math.sin(math.pi * (0.08 + 0.84 * t)) ** .6
        x, y = center[i]
        left.append((x + nx * w, y + ny * w))
        right.append((x - nx * w, y - ny * w))
    return left + right[::-1]


def leaf(cx, cy, L, w, ang):
    return [((x - cx) / 1 + cx, y) for x, y in g.leaf_poly(cx, cy, L, w, ang)]


def star_pts(cx, cy, R, r, n=5, rot=-90):
    pts = []
    for i in range(n * 2):
        a = math.radians(rot + i * 180 / n)
        rr = R if i % 2 == 0 else r
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    return pts


# ---------------------------------------------------------------- desenhos (coordenadas 0..1)
def d_gota(p):
    pts = [((x - .5) * 1 + .5, y) for x, y in
           [((px - 500) / 1000 + .5, (py - 500) / 1000 + .5) for px, py in g.drop_points(500, 560, 400)]]
    p.poly(pts)
    p.e(.3, .5, .035, .06)
    for sx in (-1, 1):
        p.shape(("e", .5 + sx * .1, .62, .06, .075))
        p.dot(.5 + sx * .1, .635, .035)
        p.e(.5 + sx * .17, .74, .045, .025)
    p.arc(.5, .74, .09, .07, 20, 160)


def d_maca(p):
    p.line([(.5, .3), (.53, .14)])
    p.poly(leaf(.53, .2, .2, .06, -.5))
    p.shape(("e", .4, .55, .25, .3), ("e", .6, .55, .25, .3))
    p.arc(.32, .5, .08, .12, 190, 250, .7)


def d_sol(p):
    for i in range(12):
        a = 2 * math.pi * i / 12
        p.poly([(.5 + math.cos(a) * .45, .5 + math.sin(a) * .45),
                (.5 + math.cos(a + .2) * .3, .5 + math.sin(a + .2) * .3),
                (.5 + math.cos(a - .2) * .3, .5 + math.sin(a - .2) * .3)])
    p.e(.5, .5, .3)
    p.face(.5, .5, .32)


def d_folha(p):
    p.line([(.15, .85), (.3, .7)])
    p.poly(leaf(.28, .72, .7, .22, -.8))
    p.line([(.28, .72), (.75, .25)], .7)
    for k in (.3, .5, .7):
        bx, by = .28 + .47 * k, .72 - .47 * k
        p.line([(bx, by), (bx + .1, by + .02)], .6)
        p.line([(bx, by), (bx - .02, by - .1)], .6)


def d_laranja(p):
    p.e(.5, .56, .33)
    p.poly(leaf(.5, .24, .22, .07, -.4))
    p.dot(.5, .25, .02)
    p.arc(.5, .56, .24, .24, 200, 250, .6)


def d_uva(p):
    p.line([(.5, .2), (.52, .1)])
    p.poly(leaf(.52, .14, .22, .07, -.2))
    rows = [4, 3, 3, 2, 1]
    for ri, n in enumerate(rows):
        for j in range(n):
            p.e(.5 + (j - (n - 1) / 2) * .15, .28 + ri * .13, .085)


def d_flor(p):
    p.line([(.5, .5), (.5, .95)])
    p.poly(leaf(.5, .8, .2, .07, -.6))
    p.poly(leaf(.5, .72, .2, .07, math.pi + .6))
    for i in range(6):
        a = 2 * math.pi * i / 6
        p.e(.5 + math.cos(a) * .17, .38 + math.sin(a) * .17, .12)
    p.e(.5, .38, .1)
    p.face(.5, .38, .1)


def d_estrela(p):
    p.poly(star_pts(.5, .52, .45, .2))
    p.face(.5, .55, .2)


def d_coracao(p):
    pts = []
    for i in range(80):
        t = 2 * math.pi * i / 80
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((.5 + x * .026, .48 - y * .026))
    p.poly(pts)
    p.face(.5, .46, .22)


def d_nuvem(p):
    p.shape(("e", .3, .55, .17, .15), ("e", .5, .45, .22, .2), ("e", .7, .55, .17, .15), ("r", .3, .55, .7, .7))
    p.face(.5, .55, .2)
    for x in (.3, .5, .7):
        p.poly(g.drop_points(x * 1000, 880, 40) and [(x + (px - x * 1000) / 1000, py / 1000) for px, py in g.drop_points(x * 1000, 880, 40)])


def d_casa(p):
    p.line([(.68, .3), (.68, .12)], 1)
    p.shape(("r", .63, .12, .73, .35))
    p.poly([(.1, .45), (.5, .12), (.9, .45)])
    p.shape(("r", .18, .45, .82, .9))
    p.shape(("r", .42, .62, .58, .9))
    p.dot(.55, .77, .015)
    for x in (.24, .64):
        p.shape(("r", x, .53, x + .12, .65))
        p.line([(x + .06, .53), (x + .06, .65)], .6)
        p.line([(x, .59), (x + .12, .59)], .6)


def d_carro(p):
    p.shape(("p", [(.28, .5), (.36, .32), (.64, .32), (.74, .5)]), ("r", .08, .5, .92, .7))
    p.poly([(.34, .48), (.39, .36), (.49, .36), (.49, .48)])
    p.poly([(.53, .48), (.53, .36), (.62, .36), (.69, .48)])
    for x in (.27, .73):
        p.e(x, .72, .1)
        p.e(x, .72, .04)
    p.e(.87, .56, .03)


def d_peixe(p):
    p.poly([(.72, .5), (.92, .33), (.92, .67)])
    p.poly([(.45, .3), (.55, .18), (.62, .32)])
    p.e(.45, .5, .32, .22)
    p.e(.28, .45, .05)
    p.dot(.29, .45, .025)
    p.arc(.2, .56, .05, .04, 300, 400, .7)
    for x, y, r in [(.12, .2, .03), (.18, .1, .04)]:
        p.e(x, y, r)
    for k in range(3):
        p.arc(.5 + k * .07, .5, .06, .12, 300, 420, .6)


def d_balao(p):
    p.line(curve_pts(lambda t: (.5 + .04 * math.sin(t * 12), .7 + t * .28)))
    p.poly([(.5, .66), (.46, .72), (.54, .72)])
    p.e(.5, .38, .28, .32)
    p.arc(.4, .3, .1, .14, 190, 250, .7)


def d_arvore(p):
    p.shape(("p", [(.43, .55), (.57, .55), (.6, .92), (.4, .92)]))
    p.shape(("e", .5, .28, .2, .17), ("e", .3, .42, .18, .16), ("e", .7, .42, .18, .16), ("e", .5, .5, .2, .14))
    for x, y in [(.36, .36), (.6, .3), (.66, .48), (.44, .5)]:
        p.e(x, y, .03)
    p.arc(.58, .8, .03, .05, 0, 360, .6)


def d_borboleta(p):
    for sx in (-1, 1):
        p.e(.5 + sx * .2, .35, .19, .17)
        p.e(.5 + sx * .16, .64, .13, .13)
        p.e(.5 + sx * .2, .35, .07)
        p.e(.5 + sx * .16, .64, .045)
    p.e(.5, .5, .05, .27)
    for sx in (-1, 1):
        p.line([(.5, .26), (.5 + sx * .1, .1)], .7)
        p.dot(.5 + sx * .1, .1, .025)


def d_arcoiris(p):
    for k in range(4):
        r = .42 - k * .08
        p.arc(.5, .72, r, r, 180, 360)
    for x in (.15, .85):
        p.shape(("e", x - .07, .76, .08, .07), ("e", x, .7, .1, .09), ("e", x + .07, .76, .08, .07), ("r", x - .07, .76, x + .07, .83))


def d_bola(p):
    p.e(.5, .5, .38)
    p.arc(.5, .5, .15, .38, 270, 450, .8)
    p.arc(.5, .5, .15, .38, 90, 270, .8)
    p.arc(.5, .5, .38, .12, 0, 180, .8)
    p.e(.5, .5, .06)


def d_gato(p):
    p.e(.5, .78, .25, .18)
    p.line(curve_pts(lambda t: (.72 + t * .18, .82 - math.sin(t * 3) * .15)))
    for sx in (-1, 1):
        p.poly([(.5 + sx * .26, .42), (.5 + sx * .28, .12), (.5 + sx * .08, .28)])
    p.e(.5, .4, .27, .23)
    for sx in (-1, 1):
        p.e(.5 + sx * .1, .36, .045, .06)
        p.dot(.5 + sx * .1, .37, .02)
        for dy in (-.02, .03):
            p.line([(.5 + sx * .12, .47 + dy), (.5 + sx * .3, .44 + dy * 2)], .5)
    p.poly([(.47, .44), (.53, .44), (.5, .48)])
    p.arc(.47, .5, .03, .03, 0, 150, .6)
    p.arc(.53, .5, .03, .03, 30, 180, .6)


def d_sorvete(p):
    p.poly([(.3, .48), (.7, .48), (.5, .95)])
    for k in range(1, 4):
        p.line([(.3 + k * .1, .48), (.5 - (4 - k) * .03, .85 - k * .04)], .5)
    p.shape(("e", .5, .28, .18), ("e", .35, .44, .12, .1), ("e", .65, .44, .12, .1), ("e", .5, .46, .14, .08))
    p.e(.5, .1, .05)
    p.face(.5, .32, .2)


def d_lua(p):
    A, ra, B, rb = (.45, .52), .38, (.62, .4), .32
    pts = []
    for i in range(361):
        a = math.radians(i)
        q = (A[0] + ra * math.cos(a), A[1] + ra * math.sin(a))
        if math.dist(q, B) > rb:
            pts.append((i, q))
    # ordena o arco de fora contínuo (lida com a volta em 360°)
    idx = [i for i, _ in pts]
    gap = max(range(len(idx)), key=lambda k: (idx[k] - idx[k - 1]) % 360)
    outer = [q for _, q in pts[gap:] + pts[:gap]]
    a1 = math.atan2(outer[-1][1] - B[1], outer[-1][0] - B[0])
    a0 = math.atan2(outer[0][1] - B[1], outer[0][0] - B[0])
    inner = []
    for s in (1, -1):
        span = (a0 - a1) % (2 * math.pi) if s == 1 else -((a1 - a0) % (2 * math.pi))
        arc = [(B[0] + rb * math.cos(a1 + span * t / 60), B[1] + rb * math.sin(a1 + span * t / 60)) for t in range(61)]
        if math.dist(arc[30], A) < ra:
            inner = arc
            break
    p.poly(outer + inner)
    p.dot(.27, .5, .022)
    p.arc(.3, .6, .05, .04, 20, 140, .6)
    for x, y in [(.8, .8), (.85, .15)]:
        p.poly(star_pts(x, y, .07, .03))


def d_cogumelo(p):
    p.shape(("r", .4, .5, .6, .85), ("e", .5, .85, .1, .04))
    p.poly([(.1 + .8 * t, .52 - math.sin(math.pi * t) * .4) for t in [i / 40 for i in range(41)]])
    for x, y, r in [(.3, .38, .06), (.5, .24, .07), (.68, .36, .05)]:
        p.e(x, y, r)
    p.face(.5, .66, .17)


def d_barco(p):
    p.line([(.5, .65), (.5, .1)])
    p.poly([(.53, .14), (.85, .58), (.53, .58)])
    p.poly([(.47, .22), (.2, .58), (.47, .58)])
    p.poly([(.1, .65), (.9, .65), (.75, .82), (.25, .82)])
    for k in range(4):
        p.arc(.12 + k * .25, .9, .12, .05, 180, 360, .7)


def d_pirulito(p):
    p.shape(("r", .47, .55, .53, .97))
    p.e(.5, .36, .3)
    pts = [(.5 + math.cos(t * 7 * math.pi) * .27 * t, .36 + math.sin(t * 7 * math.pi) * .27 * t) for t in [i / 150 for i in range(1, 151)]]
    p.line(pts, .6)


def d_morango(p):
    pts = []
    for i in range(80):
        t = 2 * math.pi * i / 80
        x = math.sin(t) * (1 - .35 * math.cos(t) ** 0)
        r = .3 + .07 * math.cos(t)
        pts.append((.5 + math.sin(t) * r * (1.05 - .55 * (1 - math.cos(t)) / 2), .5 + math.cos(t) * -.36))
    p.poly(pts)
    p.poly(star_pts(.5, .18, .17, .07, 5, 90))
    for x, y in [(.38, .35), (.5, .32), (.62, .35), (.42, .5), (.58, .5), (.5, .65), (.36, .62), (.64, .62)]:
        p.e(x, y, .012, .02)


def d_banana(p):
    c = curve_pts(lambda t: (.12 + .76 * t, .35 + .28 * math.sin(math.pi * t)))
    p.shape(("r", .08, .26, .15, .36))
    p.poly(tube(c, .13, .11))
    p.line(curve_pts(lambda t: (.25 + .5 * t, .38 + .26 * math.sin(math.pi * (.12 + t * .76)))), .6)


def d_tartaruga(p):
    for x in (.28, .68):
        p.e(x, .72, .07, .09)
    p.e(.85, .55, .11, .1)
    p.dot(.88, .52, .018)
    p.poly([(.1, .62), (.03, .66), (.12, .66)])
    p.poly([(.1 + .7 * t, .66 - math.sin(math.pi * t) * .45) for t in [i / 40 for i in range(41)]])
    p.poly([(.36, .36), (.54, .36), (.6, .5), (.45, .6), (.3, .5)])
    for a, b in [((.36, .36), (.3, .26)), ((.54, .36), (.6, .26)), ((.3, .5), (.15, .55)), ((.6, .5), (.74, .55)), ((.45, .6), (.45, .66))]:
        p.line([a, b], .6)


def d_abelha(p):
    for sx in (-1, 1):
        p.e(.47 + sx * .12, .28, .12, .16)
    p.poly([(.85, .5), (.95, .53), (.85, .56)])
    p.e(.55, .55, .32, .2)
    for x in (.53, .68):
        p.line([(x, .37), (x, .73)], 1.6)
    p.e(.25, .5, .15)
    p.face(.24, .5, .16)
    for sx in (-1, 1):
        p.line([(.22 + sx * .05, .37), (.22 + sx * .1, .25)], .6)
        p.dot(.22 + sx * .1, .25, .02)


def d_pato(p):
    p.e(.55, .68, .35, .2)
    p.poly([(.85, .55), (.97, .45), (.9, .66)])
    p.e(.3, .35, .17)
    p.poly([(.15, .35), (.02, .4), (.15, .44)])
    p.dot(.32, .3, .025)
    p.arc(.6, .66, .15, .1, 0, 180, .7)
    for k in range(4):
        p.arc(.15 + k * .25, .95, .12, .04, 180, 360, .6)


def d_bolo(p):
    p.shape(("r", .15, .58, .85, .9))
    p.shape(("r", .25, .36, .75, .58))
    p.line(curve_pts(lambda t: (.15 + .7 * t, .68 + .04 * math.sin(t * 9 * math.pi))), .7)
    p.line(curve_pts(lambda t: (.25 + .5 * t, .45 + .03 * math.sin(t * 7 * math.pi))), .7)
    for x in (.35, .5, .65):
        p.shape(("r", x - .025, .2, x + .025, .36))
        p.poly([(x + (px - 500) / 1000 * .25, .08 + (py - 160) / 1000 * .25) for px, py in g.drop_points(500, 300, 200)])
    p.shape(("r", .05, .9, .95, .94))


PAGES = [
    ("GOTA", "Pinte o Pingo de azul!", d_gota),
    ("MAÇÃ", "Pinte de vermelho!", d_maca),
    ("SOL", "Pinte de amarelo!", d_sol),
    ("FOLHA", "Pinte de verde!", d_folha),
    ("LARANJA", "Pinte de laranja!", d_laranja),
    ("UVA", "Pinte de roxo!", d_uva),
    ("FLOR", "Pinte de rosa!", d_flor),
    ("ESTRELA", "Pinte de amarelo!", d_estrela),
    ("CORAÇÃO", "Pinte de vermelho!", d_coracao),
    ("NUVEM", "Pinte as gotinhas de azul!", d_nuvem),
    ("CASA", "Pinte com as cores que quiser!", d_casa),
    ("CARRO", "Qual a cor do seu carro?", d_carro),
    ("PEIXE", "Pinte com as cores que quiser!", d_peixe),
    ("BALÃO", "Pinte de vermelho!", d_balao),
    ("ÁRVORE", "Folhas verdes e tronco marrom!", d_arvore),
    ("BORBOLETA", "Pinte com muitas cores!", d_borboleta),
    ("ARCO-ÍRIS", "Use todas as cores!", d_arcoiris),
    ("BOLA", "Pinte com as cores que quiser!", d_bola),
    ("GATO", "Pinte com as cores que quiser!", d_gato),
    ("SORVETE", "Qual é o seu sabor favorito?", d_sorvete),
    ("LUA", "Pinte de amarelo!", d_lua),
    ("COGUMELO", "Pinte o chapéu de vermelho!", d_cogumelo),
    ("BARCO", "Pinte o mar de azul!", d_barco),
    ("PIRULITO", "Pinte com muitas cores!", d_pirulito),
    ("MORANGO", "Pinte de vermelho!", d_morango),
    ("BANANA", "Pinte de amarelo!", d_banana),
    ("TARTARUGA", "Pinte de verde!", d_tartaruga),
    ("ABELHA", "Listras amarelas e pretas!", d_abelha),
    ("PATO", "Pinte de amarelo!", d_pato),
    ("BOLO", "Pinte com as cores que quiser!", d_bolo),
]


# ---------------------------------------------------------------- páginas
def blank():
    im = Image.new("L", (PW, PH), WHITE)
    return im, ImageDraw.Draw(im)


def hollow_text(d, xy, txt, size, gray=BLACK):
    f = g.font(size)
    d.text(xy, txt, font=f, anchor="mm", fill=WHITE, stroke_width=int(size * .045), stroke_fill=gray)


def small_text(d, xy, txt, size, fill=60):
    d.text(xy, txt, font=g.font(size, "Medium"), anchor="mm", fill=fill)


def finish(im):
    im = im.resize((PW // K, PH // K), Image.LANCZOS)
    return im.point(lambda v: 255 if v > 150 else 0).convert("1")


def page_drawing(word, hint, fn, n):
    im, d = blank()
    m = 0.6 * DPI * K
    hollow_text(d, (PW / 2, 1.35 * DPI * K), word, int(1.05 * DPI * K) if len(word) <= 7 else int(.8 * DPI * K))
    size = PW - 2 * m - 0.6 * DPI * K
    fn(Pen(d, (PW - size) / 2, 2.35 * DPI * K, size))
    small_text(d, (PW / 2, PH - 1.05 * DPI * K), hint, int(.3 * DPI * K))
    small_text(d, (PW / 2, PH - .65 * DPI * K), f"{n}", int(.2 * DPI * K), 120)
    return finish(im)


def page_back():
    im, d = blank()
    small_text(d, (PW / 2, PH / 2), "Esta página ficou em branco para a tinta não passar para o próximo desenho.", int(.13 * DPI * K), 170)
    return finish(im)


def page_title():
    im, d = blank()
    hollow_text(d, (PW / 2, 2.2 * DPI * K), "Meu Livro de", int(.7 * DPI * K))
    hollow_text(d, (PW / 2, 3.1 * DPI * K), "Colorir", int(1.1 * DPI * K))
    d_gota(Pen(d, PW / 2 - 2.2 * DPI * K, 4.0 * DPI * K, 4.4 * DPI * K))
    small_text(d, (PW / 2, 8.9 * DPI * K), "Este livro pertence a:", int(.35 * DPI * K), 40)
    d.line([(1.5 * DPI * K, 9.9 * DPI * K), (PW - 1.5 * DPI * K, 9.9 * DPI * K)], fill=BLACK, width=6 * K)
    return finish(im)


def page_copyright():
    im, d = blank()
    lines = ["Turminha do Pingo — Meu Livro de Colorir", "", "Copyright © 2026. Todos os direitos reservados.",
             "Nenhuma parte deste livro pode ser reproduzida sem autorização,",
             "exceto para uso pessoal da criança que o colore.", "", "Assista aos vídeos da Turminha do Pingo no YouTube!",
             "", "Dica para os pais: comece pelas primeiras páginas (formas maiores)", "e diga o nome da cor em voz alta enquanto a criança pinta."]
    for i, l in enumerate(lines):
        small_text(d, (PW / 2, PH * .62 + i * .3 * DPI * K), l, int(.15 * DPI * K), 50)
    return finish(im)


def page_certificate():
    im, d = blank()
    m = .7 * DPI * K
    d.rounded_rectangle([m, m, PW - m, PH - m], radius=int(.4 * DPI * K), outline=BLACK, width=LW)
    hollow_text(d, (PW / 2, 1.9 * DPI * K), "PARABÉNS!", int(1.0 * DPI * K))
    small_text(d, (PW / 2, 3.0 * DPI * K), "Você terminou o livro de colorir!", int(.32 * DPI * K), 30)
    p = Pen(d, PW / 2 - 1.6 * DPI * K, 3.4 * DPI * K, 3.2 * DPI * K)
    d_estrela(p)
    small_text(d, (PW / 2, 7.4 * DPI * K), "Certificado de Pequeno Artista", int(.36 * DPI * K), 30)
    d.line([(1.6 * DPI * K, 8.6 * DPI * K), (PW - 1.6 * DPI * K, 8.6 * DPI * K)], fill=BLACK, width=6 * K)
    small_text(d, (PW / 2, 8.9 * DPI * K), "nome", int(.2 * DPI * K), 120)
    return finish(im)


# ---------------------------------------------------------------- capa
def cover(n_pages):
    bleed, spine = .125, n_pages * 0.002252           # papel branco
    Wi, Hi = 2 * bleed + 2 * 8.5 + spine, 11 + 2 * bleed
    W, H = int(Wi * DPI), int(Hi * DPI)
    im = g.bg_gradient(W, H, "#8FDBFF", "#FFE6F2").copy()
    d = ImageDraw.Draw(im)
    fx0 = int((bleed + 8.5 + spine) * DPI)             # início da capa (frente)
    fw = int(8.5 * DPI)
    cx = fx0 + fw / 2
    cores = ["#E8342E", "#FF8A1F", "#FFC90E", "#3DBE4B", "#2F8CFF", "#8E44C9", "#FF6FAE"]
    for k, c in enumerate(cores):
        r = 1230 - k * 70
        d.ellipse([cx - r, H * .98 - r, cx + r, H * .98 + r], outline=g.hex2rgb(c), width=75)
    d.ellipse([fx0 - 400, H * .86, fx0 + fw + 400, H * 1.4], fill=(120, 205, 90))
    g.paste_center(im, g.text_sprite("Meu Livro de", 190, "#FFFFFF", outline=g.PINGO_AZUL), cx, H * .11)
    g.paste_center(im, g.text_sprite("COLORIR", 330, "#FF6FAE"), cx, H * .21)
    g.paste_center(im, g.text_sprite("da Turminha do Pingo", 150, g.PINGO_AZUL), cx, H * .31)
    g.paste_center(im, g.pingo_sprite(1150, 2), cx, H * .6)
    for o, x, y, s in [("maca", .12, .55, 520), ("sol", .86, .45, 560), ("flor", .85, .78, 520), ("uva", .14, .82, 480)]:
        g.paste_center(im, g.object_sprite(o, s), fx0 + fw * x, H * y)
    badge = g.text_sprite("30 desenhos • 2 a 5 anos", 110, "#FFFFFF", outline="#FF6FAE")
    g.paste_center(im, badge, cx, H * .93)
    # contracapa
    bx = int(bleed * DPI) + fw / 2
    g.paste_center(im, g.pingo_sprite(600, 0), bx, H * .2)
    texto = ["Oi! Eu sou o Pingo, a gotinha", "mais animada da turminha!", "",
             "Neste livro tem 30 desenhos grandes,", "com traço grosso, perfeitos para", "mãozinhas de 2 a 5 anos.", "",
             "• Cada página mostra o nome do desenho", "• Desenhos só de um lado da folha", "• Certificado de Pequeno Artista no final"]
    for i, l in enumerate(texto):
        d.text((bx, H * .37 + i * 95), l, font=g.font(64, "Medium"), anchor="mm", fill=(40, 40, 90))
    # área do código de barras (a Amazon imprime aqui): canto inferior direito da contracapa
    bw, bh = int(2 * DPI), int(1.2 * DPI)
    x1, y1 = int((bleed + 8.5 - .25) * DPI), int((bleed + 11 - .25) * DPI)
    d.rectangle([x1 - bw, y1 - bh, x1, y1], fill="white")
    return im.convert("RGB"), (Wi, Hi, spine)


def kdp_text(n_pages, dims):
    Wi, Hi, spine = dims
    return f"""=== DADOS PARA O KDP (kdp.amazon.com) ===

Idioma: Português
Título: Meu Livro de Colorir da Turminha do Pingo
Subtítulo: 30 desenhos grandes e fáceis para crianças de 2 a 5 anos — aprenda as cores e as primeiras palavras
Autor: (seu nome ou "Turminha do Pingo")

Descrição:
Oi! Eu sou o Pingo, a gotinha mais animada da turminha! 💧

Este livro de colorir foi feito para as primeiras pinturas da criança:
• 30 desenhos grandes com traço grosso: fácil de pintar sem sair da linha
• O nome de cada desenho em letras vazadas para colorir também
• Dicas de cor em cada página ("Pinte de vermelho!") para aprender as cores brincando
• Desenhos só na frente da folha: a tinta não estraga o próximo desenho
• Página "Este livro pertence a" e Certificado de Pequeno Artista no final

Ótimo presente de aniversário, Dia das Crianças ou Natal para crianças de 2, 3, 4 e 5 anos.

Palavras-chave (7 campos):
1. livro de colorir infantil 2 anos
2. livro para colorir criança 3 4 5 anos
3. desenhos para colorir grandes traço grosso
4. aprender as cores educação infantil
5. presente criança pequena livro atividades
6. livro de pintar menino menina
7. primeiras palavras colorir pré-escola

Categorias: Infantil > Atividades > Livros de colorir | Infantil > Aprendizagem > Cores
Faixa etária: 2 a 5 anos

=== IMPRESSÃO ===
Tamanho (trim): 8,5 x 11 pol (21,59 x 27,94 cm)
Tinta e papel: preto e branco, papel BRANCO
Sangria (bleed): NÃO (miolo sem sangria)
Acabamento da capa: fosco (matte)
Número de páginas: {n_pages}
Capa (capa.pdf): {Wi:.3f} x {Hi:.3f} pol, lombada {spine:.3f} pol (sem texto na lombada — o KDP exige 79+ páginas)

=== PERGUNTAS DO KDP ===
"Conteúdo gerado por IA?": responda SIM (texto e imagens foram criados com ajuda de IA).
ISBN: pode usar o ISBN gratuito do KDP.
Preço sugerido: veja o custo de impressão na calculadora do KDP; livros de colorir infantis
costumam ser vendidos entre US$ 6,99–8,99 na Amazon.com e R$ 29,90–39,90 na Amazon.com.br.
"""


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pages = [page_title(), page_copyright()]
    for i, (w, h, fn) in enumerate(PAGES, 1):
        pages += [page_drawing(w, h, fn, i), page_back()]
        print(f"  página {i}/{len(PAGES)} {w}")
    pages += [page_certificate(), page_back()]
    pages[0].save(OUT / "miolo.pdf", save_all=True, append_images=pages[1:], resolution=DPI)
    cv, dims = cover(len(pages))
    cv.save(OUT / "capa.pdf", resolution=DPI)
    cv.resize((cv.width // 4, cv.height // 4)).save(OUT / "capa-preview.jpg", quality=88)
    (OUT / "kdp.txt").write_text(kdp_text(len(pages), dims), encoding="utf-8")
    # folha de contato para revisão
    thumbs = [pg.convert("L").resize((425, 550)) for pg in pages[2:-2:2]]
    sheet = Image.new("L", (425 * 6, 550 * 5), 255)
    for k, t in enumerate(thumbs):
        sheet.paste(t, ((k % 6) * 425, (k // 6) * 550))
    sheet.save(OUT / "miolo-preview.jpg", quality=85)
    print(f"✔ {len(pages)} páginas → {OUT}")


if __name__ == "__main__":
    main()
