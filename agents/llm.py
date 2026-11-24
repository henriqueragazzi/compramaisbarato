"""Chamada a um modelo BARATO de IA. Troque de provedor só com variáveis de ambiente.

LLM_PROVIDER = anthropic | gemini | openai   (openai = qualquer API compatível: OpenAI, DeepSeek, OpenRouter...)
LLM_MODEL    = ex.: claude-haiku-5-5 | gemini-flash-latest | deepseek-chat
LLM_API_KEY  = chave do provedor
LLM_BASE_URL = só para "openai" compatível (ex.: https://api.deepseek.com/v1)
"""
import json
import os
import re

import requests

PADROES = {
    "anthropic": "claude-haiku-5-5",
    "gemini": "gemini-flash-latest",
    "openai": "deepseek-chat",
}


def _gerar(sistema, usuario, max_tokens=2500):
    prov = os.environ.get("LLM_PROVIDER", "anthropic").lower()
    modelo = os.environ.get("LLM_MODEL") or PADROES[prov]
    bruto = os.environ["LLM_API_KEY"]
    achado = re.search(r"sk-ant-[A-Za-z0-9_-]{20,}", bruto)
    chave = achado.group(0) if achado else bruto.strip()

    if prov == "anthropic":
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": chave, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": modelo, "max_tokens": max_tokens, "system": sistema,
                  "messages": [{"role": "user", "content": usuario}]},
            timeout=90,
        )
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json()["content"])

    if prov == "gemini":
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent",
            headers={"x-goog-api-key": chave, "content-type": "application/json"},
            json={"systemInstruction": {"parts": [{"text": sistema}]},
                  "contents": [{"role": "user", "parts": [{"text": usuario}]}],
                  "generationConfig": {"maxOutputTokens": max_tokens, "responseMimeType": "application/json"}},
            timeout=90,
        )
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]

    base = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    r = requests.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {chave}", "content-type": "application/json"},
        json={"model": modelo, "max_tokens": max_tokens,
              "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}]},
        timeout=90,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def gerar(sistema, usuario, max_tokens=2500, tentativas=3):
    """Chama o modelo com novas tentativas em caso de lentidão, limite (429) ou erro do servidor."""
    import time
    ultimo = None
    for i in range(tentativas):
        try:
            return _gerar(sistema, usuario, max_tokens)
        except requests.HTTPError as e:
            codigo = e.response.status_code if e.response is not None else 0
            ultimo = f"HTTP {codigo}: {(e.response.text if e.response is not None else '')[:300]}"
            if codigo not in (408, 429, 500, 502, 503, 504, 529):
                raise RuntimeError(ultimo)
        except (requests.Timeout, requests.ConnectionError) as e:
            ultimo = f"tempo esgotado/conexão: {e}"
        espera = 10 * (i + 1)
        print(f"    (IA: {ultimo[:120]} — tentando de novo em {espera}s)")
        time.sleep(espera)
    raise RuntimeError(ultimo)


def gerar_json(sistema, usuario, max_tokens=2500):
    for tentativa in range(2):
        texto = gerar(sistema, usuario, max_tokens)
        m = re.search(r"\{.*\}", texto, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        print("    (IA devolveu JSON inválido, pedindo de novo)")
    raise ValueError(f"Resposta sem JSON válido: {texto[:200]}")
