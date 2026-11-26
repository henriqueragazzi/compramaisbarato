"""Arquivos de divulgação gerados junto com o site (sem IA), em /extras/ (fora do Google):

- /extras/pinterest.csv        → upload em massa no Pinterest (até 200 pins: guias + produtos indicados)
- /extras/pinterest-novos.csv  → só o que entrou ou mudou nos últimos 7 dias (para subir toda semana)
- /extras/whatsapp/            → ofertas do dia prontas para copiar e colar no canal/grupos do WhatsApp
- /extras/divulgacao/          → textos para divulgar o canal em grupos

Os pins usam como pasta (board) o nome do nicho: crie no Pinterest pastas com esses mesmos nomes.
"""
import csv
import html
import io
from datetime import datetime, timedelta, timezone

BRT = timezone(timedelta(hours=-3))
LIMITE_PINS = 200  # limite do Pinterest por arquivo


def brl(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _csv(linhas):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Title", "Media URL", "Pinterest board", "Thumbnail", "Description", "Link", "Publish date", "Keywords"])
    for l in linhas[:LIMITE_PINS]:
        w.writerow([l["titulo"][:100], l["imagem"], l["pasta"], "", l["descricao"][:500], l["link"], "", l["palavras"]])
    return buf.getvalue()


def pins(site, nichos, guias, produtos_idx):
    out = []
    for g in guias:
        n = nichos.get(g["nicho"], {})
        precos = [e["p"]["preco"] for e in g["_escolhas"]]
        out.append({"titulo": g["titulo"], "imagem": g["_escolhas"][0]["p"]["imagem"], "pasta": n.get("nome", "Achados"),
                    "descricao": f"{g['resposta_curta']} Opções de {brl(min(precos))} a {brl(max(precos))}, com preço atualizado.",
                    "link": f"{site['url']}/guia/{g['slug']}/?utm_source=pinterest", "palavras": ", ".join(n.get("palavras", [])[:5]),
                    "ts": max(g.get("escrito_em", 0), g.get("criado_em", 0)), "tipo": "guia"})
    vistos = set()
    for g in guias:  # produtos indicados nos guias (são os que o Google indexa)
        for e in g["_escolhas"]:
            p = e["p"]
            if p["id"] in vistos:
                continue
            vistos.add(p["id"])
            n = nichos.get(p["nicho"], {})
            out.append({"titulo": p["nome"][:100], "imagem": p["imagem"], "pasta": n.get("nome", "Achados"),
                        "descricao": (f"{e.get('rotulo') or 'Indicado'} em \"{g['titulo']}\". {brl(p['preco'])} na Shopee, "
                                      f"nota {p['nota']} e {p['vendas']} vendidos. {e.get('porque', '')}"),
                        "link": f"{site['url']}/p/{p['slug']}/?utm_source=pinterest", "palavras": ", ".join(p.get("palavras", [])[:5]),
                        "ts": p.get("primeira_vez", 0), "tipo": "produto"})
    return out


def ofertas_whatsapp(todos, compra, n=15):
    cands = [p for p in todos if p.get("menor_30d") or p.get("queda", 0) >= 10 or p["desconto"] >= 30]
    cands.sort(key=lambda p: -(p["score"] + p.get("queda", 0) * 1.5 + (15 if p.get("menor_30d") else 0)))
    textos, nichos_usados = [], {}
    for p in cands:
        if nichos_usados.get(p["nicho"], 0) >= 4:  # mistura os nichos
            continue
        nichos_usados[p["nicho"]] = nichos_usados.get(p["nicho"], 0) + 1
        selo = "📉 *MENOR PREÇO EM 30 DIAS*\n" if p.get("menor_30d") else "🔥 *OFERTA*\n"
        antigo = f"~{brl(p['preco_antigo'])}~ " if p.get("preco_antigo") else ""
        desc = f" (-{p['desconto']}%)" if p["desconto"] else ""
        textos.append({"p": p, "texto": (f"{selo}{p['nome'][:110]}\n\n{antigo}*{brl(p['preco'])}*{desc}\n"
                                         f"⭐ {p['nota']} · {p['vendas']} vendidos\n\n🛒 {compra(p, 'whatsapp')}")})
        if len(textos) >= n:
            break
    return textos


PAGINA = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow">
<title>{titulo}</title><style>
body{{font:16px system-ui,sans-serif;max-width:640px;margin:0 auto;padding:16px;color:#1d1d1f;background:#f5f5f7}}
h1{{font-size:22px}} .c{{background:#fff;border-radius:12px;padding:14px;margin:12px 0;box-shadow:0 1px 3px #0001}}
.c img{{width:90px;height:90px;object-fit:cover;border-radius:8px;float:right;margin-left:10px}}
pre{{white-space:pre-wrap;font:15px system-ui,sans-serif;margin:0 0 10px}}
button{{font:inherit;background:#25d366;color:#fff;border:0;border-radius:8px;padding:9px 14px;cursor:pointer}}
.s{{color:#666;font-size:14px}}</style></head><body><h1>{titulo}</h1><p class="s">{sub}</p>{corpo}
<script>function cp(b){{navigator.clipboard.writeText(b.previousElementSibling.innerText).then(()=>{{b.textContent='Copiado ✓';setTimeout(()=>b.textContent='Copiar',1500)}})}}</script>
</body></html>"""


def _cartao(texto, img=""):
    i = f'<img src="{html.escape(img)}" alt="">' if img else ""
    return f'<div class="c">{i}<pre>{html.escape(texto)}</pre><button onclick="cp(this)">Copiar</button></div>'


def divulgacao(site):
    tg, url = site.get("telegram", ""), site["url"]
    wa = site.get("whatsapp") or ""
    canal = f"\n\n📲 WhatsApp: {wa}" if wa else ""
    return [
        f"🛍️ Quem compra na Shopee: criei um canal que posta só ofertas de produtos bem avaliados, com preço conferido "
        f"várias vezes por dia (nada de desconto inflado de Black Friday).\n\n👉 Telegram: {tg}{canal}\n\n"
        f"E os guias de compra estão em {url}",
        f"Dica pra Black Friday: antes de comprar, vejam se o preço baixou de verdade. No {url.split('//')[-1]} cada "
        f"produto mostra o histórico de preço e avisa quando é o menor dos últimos 30 dias.\n\nOfertas todo dia no canal: {tg}",
        f"🎄 Procurando presente de Natal barato? Tem guias prontos por faixa de preço (até R$ 30, R$ 50, R$ 100) e "
        f"para mãe, pai, avó, professora, amigo secreto:\n{url}/guias/\n\nOfertas diárias: {tg}",
        f"🐾🏠🚗 Achadinhos da Shopee para casa, pet e carro, só com nota alta e muitas vendas. Entra no canal, é de graça "
        f"e dá pra silenciar: {tg}{canal}",
    ]


def gerar(pasta, site, nichos, guias, todos, compra, agora_ts):
    pasta.mkdir(parents=True, exist_ok=True)
    produtos_idx = {p["id"]: p for p in todos}
    lista = pins(site, nichos, guias, produtos_idx)
    (pasta / "pinterest.csv").write_text(_csv(lista), encoding="utf-8")
    novos = [l for l in lista if agora_ts - l["ts"] < 7 * 86400]
    (pasta / "pinterest-novos.csv").write_text(_csv(novos), encoding="utf-8")

    hoje = datetime.now(BRT).strftime("%d/%m/%Y %H:%M")
    ofs = ofertas_whatsapp(todos, compra)
    (pasta / "whatsapp").mkdir(exist_ok=True)
    (pasta / "whatsapp" / "index.html").write_text(PAGINA.format(
        titulo="Ofertas para o WhatsApp", sub=f"Atualizado em {hoje}. Toque em Copiar e cole no canal ou no grupo. "
        "Os links contam cliques com origem WhatsApp no painel.",
        corpo="".join(_cartao(o["texto"], o["p"]["imagem"]) for o in ofs)), encoding="utf-8")
    (pasta / "divulgacao").mkdir(exist_ok=True)
    (pasta / "divulgacao" / "index.html").write_text(PAGINA.format(
        titulo="Textos para divulgar o canal", sub="Use um texto diferente em cada grupo e respeite as regras do grupo.",
        corpo="".join(_cartao(t) for t in divulgacao(site))), encoding="utf-8")
    print(f"Extras: {len(lista[:LIMITE_PINS])} pins ({len(novos)} novos), {len(ofs)} ofertas para WhatsApp")
