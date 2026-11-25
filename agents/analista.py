"""AGENTE 7 — Analista de comissões (sem IA). Lê o relatório de conversões da Shopee
e mostra o que está dando dinheiro por nicho e por produto (últimos N dias).
Uso: python agents/analista.py --dias 7
"""
import argparse
import time
from collections import defaultdict

from comum import DADOS, PRODUTOS, ler_json
from shopee import Shopee


def rodar(dias=7):
    api = Shopee()
    fim = int(time.time())
    ini = fim - dias * 86400
    produtos = ler_json(PRODUTOS, {})
    por_nicho, por_item, total, pedidos, scroll = defaultdict(float), defaultdict(float), 0.0, 0, ""
    while True:
        rep = api.relatorio_conversoes(ini, fim, scroll)
        for n in rep["nodes"]:
            pedidos += 1
            total += float(n.get("totalCommission") or 0)
            for o in n.get("orders") or []:
                for it in o.get("items") or []:
                    c = float(it.get("itemTotalCommission") or 0)
                    pid = str(it.get("itemId"))
                    por_item[(pid, it.get("itemName", "")[:60])] += c
                    por_nicho[produtos.get(pid, {}).get("nicho", "fora do catálogo")] += c
        if not rep["pageInfo"]["hasNextPage"]:
            break
        scroll = rep["pageInfo"]["scrollId"]
    linhas = [f"# Comissões — últimos {dias} dias", "", f"Pedidos: {pedidos} · Comissão estimada: R$ {total:.2f}", "", "## Por nicho"]
    linhas += [f"- {k}: R$ {v:.2f}" for k, v in sorted(por_nicho.items(), key=lambda x: -x[1])]
    linhas += ["", "## Top 15 produtos"] + [f"- {n} (id {i}): R$ {v:.2f}" for (i, n), v in sorted(por_item.items(), key=lambda x: -x[1])[:15]]
    (DADOS / "relatorio_comissoes.md").write_text("\n".join(linhas), encoding="utf-8")
    print("\n".join(linhas))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dias", type=int, default=7)
    rodar(ap.parse_args().dias)
