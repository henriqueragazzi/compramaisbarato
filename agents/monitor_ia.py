"""AGENTE 6 — Monitor de IA. MEDE se o ChatGPT/Perplexity citam o seu site (não "ranqueia" nada).

Faz as perguntas de perguntas.yaml às IAs com busca na web ligada e registra:
- se o seu domínio apareceu nas fontes;
- quais concorrentes apareceram (para estudar o formato deles).

Chaves (use uma ou as duas): OPENAI_API_KEY  e/ou  PERPLEXITY_API_KEY
Modelos configuráveis: MONITOR_OPENAI_MODEL (padrão gpt-5-mini), MONITOR_PPLX_MODEL (padrão sonar)
Uso: python agents/monitor_ia.py --max 40
Custo aproximado: centavos de dólar por pergunta. Rode 1x por semana.
"""
import argparse
import json
import os
import re
from collections import Counter
from datetime import datetime
from urllib.parse import urlparse

import requests
import yaml

from comum import DADOS, RAIZ, config, salvar_json

URL_RE = re.compile(r'https?://[^\s"\'<>)\]]+')


def dominios(texto):
    ds = []
    for u in URL_RE.findall(texto):
        h = (urlparse(u).hostname or "").removeprefix("www.")
        if h and h not in ds:
            ds.append(h)
    return ds


def perguntar_openai(q):
    r = requests.post("https://api.openai.com/v1/responses", timeout=180,
                      headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                      json={"model": os.environ.get("MONITOR_OPENAI_MODEL", "gpt-5-mini"),
                            "tools": [{"type": "web_search"}],
                            "input": q + " Responda para alguém no Brasil, com links."})
    r.raise_for_status()
    return json.dumps(r.json(), ensure_ascii=False)


def perguntar_pplx(q):
    r = requests.post("https://api.perplexity.ai/chat/completions", timeout=120,
                      headers={"Authorization": f"Bearer {os.environ['PERPLEXITY_API_KEY']}"},
                      json={"model": os.environ.get("MONITOR_PPLX_MODEL", "sonar"),
                            "messages": [{"role": "user", "content": q + " (Brasil)"}]})
    r.raise_for_status()
    return json.dumps(r.json(), ensure_ascii=False)


def rodar(maximo=40):
    meu = (urlparse(config()["site"]["url"]).hostname or "").removeprefix("www.")
    perguntas = yaml.safe_load((RAIZ / "perguntas.yaml").read_text(encoding="utf-8"))
    lista = [(n, i["pergunta"]) for n, itens in perguntas.items() for i in itens][:maximo]
    fontes = {}
    if os.environ.get("OPENAI_API_KEY"):
        fontes["chatgpt"] = perguntar_openai
    if os.environ.get("PERPLEXITY_API_KEY"):
        fontes["perplexity"] = perguntar_pplx
    if not fontes:
        raise SystemExit("Defina OPENAI_API_KEY e/ou PERPLEXITY_API_KEY")

    resultado, concorrentes, citado = [], Counter(), Counter()
    for nicho, q in lista:
        linha = {"nicho": nicho, "pergunta": q}
        for nome, fn in fontes.items():
            try:
                ds = dominios(fn(q))
            except Exception as e:
                linha[nome] = {"erro": str(e)[:200]}
                continue
            ds = [d for d in ds if not d.endswith(("openai.com", "perplexity.ai"))]
            achou = any(d == meu or d.endswith("." + meu) for d in ds)
            linha[nome] = {"citado": achou, "fontes": ds[:15]}
            citado[nome] += achou
            concorrentes.update(d for d in ds if d != meu)
        resultado.append(linha)
        print(f"  {'✓' if any(v.get('citado') for v in linha.values() if isinstance(v, dict)) else '·'} {q}")

    hoje = datetime.now().strftime("%Y-%m-%d")
    salvar_json(DADOS / "monitor" / f"{hoje}.json", resultado)
    rel = [f"# Monitor de IA — {hoje}", "", f"Domínio: **{meu}** · perguntas: {len(lista)}", ""]
    for nome in fontes:
        rel.append(f"- **{nome}**: citado em {citado[nome]} de {len(lista)} ({citado[nome]*100//max(len(lista),1)}%)")
    rel += ["", "## Perguntas em que NÃO aparecemos (prioridade do Redator)"]
    rel += [f"- {l['pergunta']}" for l in resultado if not any(v.get("citado") for v in l.values() if isinstance(v, dict))]
    rel += ["", "## Sites mais citados (estude o formato deles)"] + [f"- {d}: {c}x" for d, c in concorrentes.most_common(20)]
    (DADOS / "monitor" / f"{hoje}.md").write_text("\n".join(rel), encoding="utf-8")
    print("\n".join(rel[:6]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=40)
    rodar(ap.parse_args().max)
