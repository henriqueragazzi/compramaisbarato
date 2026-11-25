"""AGENTE 9 — Vendas para o painel. Lê o relatório de conversões da Shopee dos últimos dias
e grava os totais por dia (e os produtos vendidos) no banco do app (Cloudflare D1).
Nada disso vai para o repositório, que é público. Precisa de CLOUDFLARE_API_TOKEN.
Uso: python agents/vendas.py --dias 10
"""
import argparse
import os
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import requests

from comum import PRODUTOS, ler_json
from shopee import Shopee

CONTA = "fc2bbe24f2304a4688a3b7e0a75463ec"
BANCO = "compramaisbarato"
BRT = timezone(timedelta(hours=-3))
API = f"https://api.cloudflare.com/client/v4/accounts/{CONTA}/d1/database"


def d1(token):
    h = {"Authorization": f"Bearer {token}"}
    r = requests.get(API, headers=h, params={"name": BANCO}, timeout=30).json()
    uuid = next(d["uuid"] for d in r["result"] if d["name"] == BANCO)

    def sql(consulta, params=None):
        resp = requests.post(f"{API}/{uuid}/query", headers=h, json={"sql": consulta, "params": params or []}, timeout=30).json()
        if not resp.get("success"):
            raise RuntimeError(resp.get("errors"))
        return resp["result"]
    return sql


def rodar(dias=10):
    bruto = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    m = re.search(r"[A-Za-z0-9_-]{30,}", bruto)  # tolera espaço ou quebra de linha colados junto
    token = m.group(0) if m else ""
    if not token:
        print("Sem CLOUDFLARE_API_TOKEN: vendas não enviadas ao painel.")
        return
    api, produtos = Shopee(), ler_json(PRODUTOS, {})
    fim = int(time.time())
    ini = fim - dias * 86400
    por_dia = defaultdict(lambda: {"pedidos": 0, "itens": 0, "comissao": 0.0, "valor": 0.0})
    por_item = defaultdict(lambda: {"nome": "", "nicho": "", "qtd": 0, "comissao": 0.0})
    scroll = ""
    while True:
        rep = api.relatorio_conversoes(ini, fim, scroll)
        for n in rep["nodes"]:
            dia = datetime.fromtimestamp(int(n.get("purchaseTime") or fim), BRT).strftime("%Y-%m-%d")
            por_dia[dia]["pedidos"] += 1
            por_dia[dia]["comissao"] += float(n.get("totalCommission") or 0)
            for o in n.get("orders") or []:
                for it in o.get("items") or []:
                    q = int(it.get("qty") or 1)
                    pid = str(it.get("itemId"))
                    por_dia[dia]["itens"] += q
                    por_dia[dia]["valor"] += float(it.get("itemPrice") or 0) * q
                    k = (dia, pid)
                    por_item[k]["nome"] = (it.get("itemName") or "")[:90]
                    por_item[k]["nicho"] = produtos.get(pid, {}).get("nicho", "fora do catálogo")
                    por_item[k]["qtd"] += q
                    por_item[k]["comissao"] += float(it.get("itemTotalCommission") or 0)
        if not rep["pageInfo"]["hasNextPage"]:
            break
        scroll = rep["pageInfo"]["scrollId"]

    sql = d1(token)
    sql("CREATE TABLE IF NOT EXISTS vendas (dia TEXT PRIMARY KEY, pedidos INTEGER, itens INTEGER, comissao REAL, valor REAL, atualizado TEXT)")
    sql("CREATE TABLE IF NOT EXISTS vendas_itens (dia TEXT, item TEXT, nome TEXT, nicho TEXT, qtd INTEGER, comissao REAL, PRIMARY KEY (dia, item))")
    agora = datetime.now(BRT).isoformat(timespec="minutes")
    primeiro = datetime.fromtimestamp(ini, BRT).strftime("%Y-%m-%d")
    # dias inteiros cobertos pela consulta são regravados (o relatório da Shopee muda: pedidos confirmados/cancelados)
    sql("DELETE FROM vendas_itens WHERE dia > ?", [primeiro])
    sql("DELETE FROM vendas WHERE dia > ?", [primeiro])
    for dia, v in por_dia.items():
        if dia <= primeiro:
            continue
        sql("INSERT OR REPLACE INTO vendas VALUES (?,?,?,?,?,?)",
            [dia, v["pedidos"], v["itens"], round(v["comissao"], 2), round(v["valor"], 2), agora])
    for (dia, pid), v in por_item.items():
        if dia <= primeiro:
            continue
        sql("INSERT OR REPLACE INTO vendas_itens VALUES (?,?,?,?,?,?)",
            [dia, pid, v["nome"], v["nicho"], v["qtd"], round(v["comissao"], 2)])
    total = sum(v["comissao"] for d, v in por_dia.items() if d > primeiro)
    print(f"Vendas: {sum(v['pedidos'] for v in por_dia.values())} pedidos em {len(por_dia)} dias, comissão R$ {total:.2f} (enviado ao painel)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dias", type=int, default=10)
    rodar(ap.parse_args().dias)
