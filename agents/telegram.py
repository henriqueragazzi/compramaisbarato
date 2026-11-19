"""AGENTE 5 — Distribuidor no Telegram (sem IA).

Posta no seu canal as melhores ofertas novas (menor preço em 30 dias ou queda forte),
sem repetir o mesmo produto em 7 dias. Crie o bot no @BotFather e adicione-o como admin do canal.
Variáveis: TELEGRAM_BOT_TOKEN, TELEGRAM_CANAL (ex.: @meucanal)
Uso: python agents/telegram.py --max 5
"""
import argparse
import os
import time

import requests

from comum import DADOS, PRODUTOS, config, ler_json, salvar_json

POSTADOS = DADOS / "telegram_postados.json"


def brl(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def rodar(maximo=5):
    token, canal = os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CANAL"]
    site = config()["site"]["url"]
    produtos = ler_json(PRODUTOS, {})
    postados = ler_json(POSTADOS, {})
    agora = time.time()
    postados = {k: v for k, v in postados.items() if agora - v < 7 * 86400}
    cands = [p for p in produtos.values() if p["id"] not in postados and (p.get("menor_30d") or p.get("queda", 0) >= 15 or p["desconto"] >= 40)]
    cands.sort(key=lambda p: -(p["score"] + p.get("queda", 0)))
    for p in cands[:maximo]:
        selo = "📉 MENOR PREÇO EM 30 DIAS\n" if p.get("menor_30d") else ""
        antigo = f"<s>{brl(p['preco_antigo'])}</s> " if p.get("preco_antigo") else ""
        desc = f"  (-{p['desconto']}%)" if p["desconto"] else ""
        texto = (f"{selo}<b>{p['nome'][:120]}</b>\n\n{antigo}<b>{brl(p['preco'])}</b>"
                 f"{desc}\n⭐ {p['nota']} · {p['vendas']} vendidos\n\n"
                 f"🛒 {p['link']}\n🔎 Mais opções: {site}/p/{p['slug']}/")
        r = requests.post(f"https://api.telegram.org/bot{token}/sendPhoto", timeout=30,
                          data={"chat_id": canal, "photo": p["imagem"], "caption": texto[:1024], "parse_mode": "HTML"})
        if r.ok:
            postados[p["id"]] = agora
            print(f"  ✓ {p['nome'][:60]}")
        else:
            print(f"  ! {r.text[:200]}")
        time.sleep(3)
    salvar_json(POSTADOS, postados)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=5)
    rodar(ap.parse_args().max)
