"""AGENTE 4 — Publicador (sem IA). Gera o site estático em dist/ e avisa o Bing/IndexNow.

Uso:  python agents/publicador.py
      python agents/publicador.py --indexnow   (envia as URLs ao IndexNow; precisa INDEXNOW_KEY)
"""
import argparse
import json
import os
import shutil
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import requests
from jinja2 import Environment, FileSystemLoader, select_autoescape

from comum import GUIAS, HISTORICO, PRODUTOS, RAIZ, config, ler_json

DIST = RAIZ / "dist"
BRT = timezone(timedelta(hours=-3))


def brl(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def milhar(v):
    v = int(v)
    if v >= 1000:
        return f"{v/1000:.1f} mil".replace(".0 mil", " mil").replace(".", ",")
    return str(v)


def data_br(ts):
    return datetime.fromtimestamp(ts, BRT).strftime("%d/%m/%Y")


BASE = ""  # prefixo do caminho quando o site roda numa subpasta (ex.: /compramaisbarato no GitHub Pages)


def com_base(html):
    if not BASE:
        return html
    for a in ('href="/', 'src="/', 'action="/', "fetch('/"):
        html = html.replace(a, a[:-1] + BASE + "/")
    return html.replace(BASE + "//", "//")  # não mexe em links //cdn


def escrever(caminho_url, html):
    html = com_base(html)
    destino = DIST / caminho_url.strip("/") / "index.html" if caminho_url != "/" else DIST / "index.html"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")


def rodar(indexnow=False):
    global BASE
    cfg = config()
    site, nichos = cfg["site"], cfg["nichos"]
    BASE = (urlparse(site["url"]).path or "").rstrip("/")
    produtos = ler_json(PRODUTOS, {})
    historico = ler_json(HISTORICO, {})
    guias = [ler_json(p, {}) for p in sorted(GUIAS.glob("*.json"))]

    # monta guias só com escolhas que ainda existem
    guias_ok = []
    for g in guias:
        escolhas = [dict(e, p=produtos[e["id"]]) for e in g.get("escolhas", []) if e["id"] in produtos]
        if len(escolhas) >= 3:
            g["_escolhas"] = escolhas
            guias_ok.append(g)
    guias_ok.sort(key=lambda g: -g.get("escrito_em", 0))

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()

    env = Environment(loader=FileSystemLoader(RAIZ / "templates"), autoescape=select_autoescape(["html"]))
    env.filters.update(brl=brl, milhar=milhar)
    agora_ts = int(datetime.now(timezone.utc).timestamp())
    hoje = datetime.now(BRT)
    base = dict(site=site, nichos=nichos, filtros=cfg["filtros"], ano=hoje.year, jsonld=[], imagem=None,
                black_friday=(hoje.month == 11 or (hoje.month == 12 and hoje.day <= 2)))
    org = {"@context": "https://schema.org", "@type": "Organization", "name": site["nome"], "url": site["url"]}
    urls = []  # (caminho, lastmod)

    def render(tpl, caminho, **kw):
        ctx = {**base, "caminho": caminho, **kw}
        escrever(caminho, env.get_template(tpl).render(**ctx))
        urls.append((caminho, kw.get("_lastmod", agora_ts)))

    todos = sorted(produtos.values(), key=lambda p: -p["score"])
    ofertas = sorted([p for p in todos if p["desconto"] >= 15], key=lambda p: -(p["score"] + p["desconto"] * 0.5))
    quedas = sorted([p for p in todos if p.get("queda", 0) >= 10], key=lambda p: -p["queda"])

    # HOME
    render("home.html", "/", titulo=f"{site['nome']}: {site['slogan']}", descricao=site["descricao"],
           ofertas=ofertas or todos, quedas=quedas, guias=guias_ok,
           jsonld=[org, {"@context": "https://schema.org", "@type": "WebSite", "name": site["nome"], "url": site["url"],
                         "potentialAction": {"@type": "SearchAction", "target": site["url"] + "/busca/?q={q}",
                                             "query-input": "required name=q"}}])

    # NICHOS
    for k, n in nichos.items():
        ps = [p for p in todos if p["nicho"] == k][:60]
        gs = [g for g in guias_ok if g["nicho"] == k]
        render("lista.html", f"/n/{k}/", titulo=f"{n['nome']}: melhores produtos e guias de compra | {site['nome']}",
               descricao=f"Os produtos de {n['nome'].lower()} mais bem avaliados da Shopee, com preço atualizado e guias de compra.",
               h1=f"{n['emoji']} {n['nome']}", guias=gs, produtos=ps)

    render("lista.html", "/guias/", titulo=f"Guias de compra | {site['nome']}",
           descricao="Todos os guias de compra: casa, pet, carro e presentes.", h1="📘 Guias de compra", guias=guias_ok, produtos=[])
    render("lista.html", "/ofertas/", titulo=f"Ofertas do dia na Shopee | {site['nome']}",
           descricao="Produtos bem avaliados com desconto real e menor preço em 30 dias.", h1="🔥 Ofertas do dia",
           intro="Só entram produtos com boa nota e muitas vendas. O selo 'menor preço em 30 dias' vem do nosso histórico.",
           guias=[], produtos=(sorted([p for p in todos if p.get("menor_30d")], key=lambda p: -p["score"]) + ofertas)[:80],
           titulo_produtos="Em oferta agora")
    # BLACK FRIDAY (fica no ar o ano todo; o link no menu só aparece em novembro)
    def bf_nota(p):
        return p["score"] + p.get("queda", 0) * 1.5 + (15 if p.get("menor_30d") else 0) + min(p["desconto"], 70) * 0.3
    grupos = []
    for k in nichos:
        cand = [p for p in todos if p["nicho"] == k and (p["desconto"] >= 15 or p.get("queda", 0) >= 5)]
        grupos.append((k, sorted(cand, key=lambda p: -bf_nota(p))[:16]))
    guias_bf = [g for g in guias_ok if g["nicho"] == "presentes" or "black friday" in g.get("pergunta", "").lower()][:12]
    render("black-friday.html", "/black-friday/",
           titulo=f"Black Friday {datetime.now(BRT).year} Shopee: melhores ofertas de verdade | {site['nome']}",
           descricao="Ofertas da Black Friday na Shopee para casa, pet, carro e presentes: só produtos bem avaliados, com preço conferido várias vezes ao dia e sem desconto inflado.",
           grupos=grupos, guias=guias_bf, atualizado=data_br(agora_ts))

    render("sobre.html", "/sobre/", titulo=f"Como escolhemos os produtos | {site['nome']}",
           descricao=f"Critérios do {site['nome']} para escolher produtos e como o site ganha dinheiro.")
    render("busca.html", "/busca/", titulo=f"Buscar | {site['nome']}", descricao="Busque produtos e guias.")
    urls.pop()  # página de busca fora do sitemap

    # GUIAS
    por_produto = {}
    for g in guias_ok:
        for e in g["_escolhas"]:
            por_produto.setdefault(e["id"], []).append(g)
        rel = [r for r in guias_ok if r["nicho"] == g["nicho"] and r["slug"] != g["slug"]][:6]
        cam = f"/guia/{g['slug']}/"
        ld = [
            {"@context": "https://schema.org", "@type": "Article", "headline": g["titulo"],
             "datePublished": datetime.fromtimestamp(g.get("criado_em", agora_ts), timezone.utc).isoformat(),
             "dateModified": datetime.fromtimestamp(g["escrito_em"], timezone.utc).isoformat(),
             "author": org, "publisher": org, "mainEntityOfPage": site["url"] + cam},
            {"@context": "https://schema.org", "@type": "ItemList", "name": g["titulo"],
             "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": f"{site['url']}/p/{e['p']['slug']}/",
                                  "name": e["p"]["nome"]} for i, e in enumerate(g["_escolhas"])]},
        ]
        if g.get("faq"):
            ld.append({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
                {"@type": "Question", "name": f["q"], "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in g["faq"]]})
        render("guia.html", cam, titulo=f"{g['titulo']} ({datetime.now(BRT).year})",
               descricao=g.get("descricao_meta") or g["resposta_curta"][:155], g=g, escolhas=g["_escolhas"],
               relacionados=rel, atualizado=data_br(max(g["escrito_em"], agora_ts - 3600)), og_tipo="article",
               imagem=g["_escolhas"][0]["p"]["imagem"], jsonld=ld, _lastmod=g["escrito_em"])

    # PRODUTOS
    for p in todos:
        h = historico.get(p["id"], {})
        sim = [s for s in todos if s["nicho"] == p["nicho"] and s["id"] != p["id"]
               and set(s.get("palavras", [])) & set(p.get("palavras", []))][:8]
        cam = f"/p/{p['slug']}/"
        ld = [{"@context": "https://schema.org", "@type": "Product", "name": p["nome"], "image": p["imagem"],
               "offers": {"@type": "Offer", "price": f"{p['preco']:.2f}", "priceCurrency": "BRL",
                          "availability": "https://schema.org/InStock", "url": p["link"],
                          "seller": {"@type": "Organization", "name": p["loja"] or "Shopee"}}}]
        render("produto.html", cam, titulo=f"{p['nome'][:70]} por {brl(p['preco'])} | {site['nome']}",
               descricao=f"{p['nome'][:110]} — {brl(p['preco'])}, nota {p['nota']} e {milhar(p['vendas'])} vendidos na Shopee.",
               p=p, guias=por_produto.get(p["id"], []), similares=sim, hist=h,
               hist_min=min(h.values()) if h else 0, hist_max=max(h.values()) if h else 0,
               atualizado=data_br(p.get("visto_em", agora_ts)), imagem=p["imagem"], jsonld=ld, _lastmod=p.get("visto_em", agora_ts))

    # índice da busca (compacto)
    (DIST / "busca.json").write_text(json.dumps({
        "g": [{"s": g["slug"], "t": g["titulo"], "q": g["pergunta"], "r": g["resposta_curta"][:120]} for g in guias_ok],
        "p": [{"s": p["slug"], "n": p["nome"], "k": " ".join(p.get("palavras", [])), "pr": p["preco"], "nt": p["nota"],
               "v": p["vendas"], "i": p["imagem"], "sc": p["score"]} for p in todos],
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # 404
    (DIST / "404.html").write_text(com_base(env.get_template("lista.html").render(
        **base, caminho="/404", titulo="Página não encontrada", descricao="", h1="Ops, essa página saiu do ar",
        intro="O produto pode ter acabado. Veja os guias:", guias=guias_ok[:9], produtos=[])), encoding="utf-8")

    # sitemap, robots, llms.txt
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for cam, ts in urls:
        sm.append(f"<url><loc>{site['url']}{cam}</loc><lastmod>{datetime.fromtimestamp(ts, timezone.utc).strftime('%Y-%m-%d')}</lastmod></url>")
    sm.append("</urlset>")
    (DIST / "sitemap.xml").write_text("\n".join(sm), encoding="utf-8")

    robots = [f"User-agent: {b}\nAllow: /\n" for b in cfg["robos_permitidos"]]
    robots.append("User-agent: *\nAllow: /\nDisallow: /busca/\n")
    robots.append(f"Sitemap: {site['url']}/sitemap.xml")
    (DIST / "robots.txt").write_text("\n".join(robots), encoding="utf-8")

    llms = [f"# {site['nome']}", "", f"> {site['descricao']}", "",
            "Site brasileiro de guias de compra e ofertas da Shopee. Preços atualizados automaticamente várias vezes ao dia. "
            "Participamos do programa de afiliados da Shopee.", ""]
    for k, n in nichos.items():
        llms.append(f"## {n['nome']}")
        llms += [f"- [{g['titulo']}]({site['url']}/guia/{g['slug']}/): {g['resposta_curta'][:140]}" for g in guias_ok if g["nicho"] == k]
        llms.append("")
    llms += ["## Outras páginas", f"- [Ofertas do dia]({site['url']}/ofertas/)", f"- [Como escolhemos]({site['url']}/sobre/)"]
    (DIST / "llms.txt").write_text("\n".join(llms), encoding="utf-8")

    host = urlparse(site["url"]).hostname
    if host and "seudominio" not in host and not host.endswith("github.io"):
        (DIST / "CNAME").write_text(host, encoding="utf-8")

    chave = site.get("indexnow") or os.environ.get("INDEXNOW_KEY")
    if chave:
        (DIST / f"{chave}.txt").write_text(chave, encoding="utf-8")

    print(f"Publicador: {len(urls)} páginas ({len(guias_ok)} guias, {len(todos)} produtos) em dist/")

    if indexnow and chave:
        # envia só o que mudou nas últimas 6h (guias e produtos atualizados) + home
        recentes = [site["url"] + c for c, ts in urls if agora_ts - ts < 6 * 3600 and not c.startswith("/p/")][:10000]
        try:
            r = requests.post("https://api.indexnow.org/indexnow", json={
                "host": host, "key": chave, "keyLocation": f"{site['url']}/{chave}.txt", "urlList": recentes}, timeout=30)
            print(f"IndexNow: {len(recentes)} URLs → HTTP {r.status_code}")
        except Exception as e:
            print(f"IndexNow falhou: {e}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--indexnow", action="store_true")
    rodar(ap.parse_args().indexnow)
