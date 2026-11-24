"""AGENTE 1 — Caçador de ofertas (sem IA, custo zero de tokens).

Pesquisa cada palavra-chave dos nichos na API da Shopee, filtra por qualidade,
guarda o histórico de preço e marca "menor preço em 30 dias".

Uso:  python agents/cacador.py            (todos os nichos)
      python agents/cacador.py --nicho pet
"""
import argparse
import time
from datetime import datetime, timezone

from comum import HISTORICO, PRODUTOS, agora, config, ler_json, pontuacao, salvar_json, slug
from shopee import Shopee, ShopeeAPIError

DIAS_PARA_EXPIRAR = 7
DESCONTO_MAXIMO = 70


def num(v, padrao=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return padrao


def normalizar(n, nicho, palavra):
    preco = num(n.get("priceMin") or n.get("price"))
    preco_max = num(n.get("priceMax"))
    desconto = num(n.get("priceDiscountRate"))
    # desconto acima de 70% quase sempre é preço riscado inflado pela loja: não mostramos
    if desconto > DESCONTO_MAXIMO:
        desconto = 0
    preco_antigo = round(preco / (1 - desconto / 100), 2) if 0 < desconto <= DESCONTO_MAXIMO else None
    return {
        "id": str(n["itemId"]),
        "shop_id": str(n.get("shopId", "")),
        "nome": (n.get("productName") or "").strip(),
        "loja": n.get("shopName", ""),
        "preco": round(preco, 2),
        "a_partir": preco_max > preco * 1.05,  # tem variações mais caras (tamanho/cor)
        "preco_antigo": preco_antigo,
        "desconto": round(desconto),
        "vendas": int(num(n.get("sales"))),
        "nota": round(num(n.get("ratingStar")), 1),
        "comissao": num(n.get("commissionRate")),
        "imagem": n.get("imageUrl", ""),
        "link_produto": n.get("productLink", ""),
        "link": n.get("offerLink") or "",
        "nicho": nicho,
        "palavras": [palavra],
    }


def passa_filtro(p, f):
    f = {**f, **f.get("por_nicho", {}).get(p["nicho"], {})}
    return (
        p["nota"] >= f["nota_minima"]
        and p["vendas"] >= f["vendas_minimas"]
        and p["comissao"] >= f["comissao_minima"]
        and p["preco"] > 0
        and p["link"]
    )


def rodar(somente_nicho=None):
    cfg = config()
    f = cfg["filtros"]
    api = Shopee()
    produtos = ler_json(PRODUTOS, {})
    historico = ler_json(HISTORICO, {})
    hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    t = agora()
    novos = atualizados = 0

    for chave, nicho in cfg["nichos"].items():
        if somente_nicho and chave != somente_nicho:
            continue
        for palavra in nicho["palavras"]:
            for pagina in (1, 2):
                try:
                    nodes, tem_mais = api.buscar_produtos(palavra, ordem=2, pagina=pagina, limite=50)
                except ShopeeAPIError as e:
                    print(f"  ! erro em '{palavra}': {e}")
                    break
                for n in nodes:
                    p = normalizar(n, chave, palavra)
                    if not passa_filtro(p, f):
                        continue
                    antigo = produtos.get(p["id"])
                    if antigo:
                        p["palavras"] = sorted(set(antigo.get("palavras", [])) | set(p["palavras"]))
                        p["primeira_vez"] = antigo.get("primeira_vez", t)
                        p["slug"] = antigo["slug"]
                        atualizados += 1
                    else:
                        p["primeira_vez"] = t
                        p["slug"] = f"{slug(p['nome'], 70)}-{p['id']}"
                        novos += 1
                    p["visto_em"] = t
                    produtos[p["id"]] = p
                    # histórico: menor preço do dia
                    h = historico.setdefault(p["id"], {})
                    h[hoje] = min(h.get(hoje, p["preco"]), p["preco"])
                if not tem_mais:
                    break
                time.sleep(1)
            print(f"  ✓ {chave}: {palavra}")

    # expira produtos que sumiram da API (sem estoque / fora do programa)
    limite = t - DIAS_PARA_EXPIRAR * 86400
    for pid in [k for k, v in produtos.items() if v.get("visto_em", 0) < limite]:
        produtos.pop(pid)

    # selo "menor preço em 30 dias" e queda de preço
    for pid, p in produtos.items():
        h = historico.get(pid, {})
        ultimos = [v for d, v in sorted(h.items())[-30:]]
        p["menor_30d"] = len(ultimos) >= 7 and p["preco"] <= min(ultimos)
        anteriores = ultimos[:-1]
        p["queda"] = round((max(anteriores) - p["preco"]) / max(anteriores) * 100) if anteriores and max(anteriores) > p["preco"] else 0
        p["score"] = pontuacao(p)

    # limita tamanho por nicho
    for chave in cfg["nichos"]:
        do_nicho = sorted((p for p in produtos.values() if p["nicho"] == chave), key=lambda p: -p["score"])
        for p in do_nicho[f["max_produtos_por_nicho"]:]:
            produtos.pop(p["id"], None)

    # histórico só dos últimos 90 dias
    for pid in list(historico):
        if pid not in produtos:
            historico.pop(pid)
        else:
            historico[pid] = dict(sorted(historico[pid].items())[-90:])

    salvar_json(PRODUTOS, produtos)
    salvar_json(HISTORICO, historico)
    print(f"Caçador: {novos} novos, {atualizados} atualizados, {len(produtos)} no catálogo.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--nicho")
    rodar(ap.parse_args().nicho)
