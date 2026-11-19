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


def gerar(sistema, usuario, max_tokens=2500):
    prov = os.environ.get("LLM_PROVIDER", "anthropic").lower()
    modelo = os.environ.get("LLM_MODEL") or PADROES[prov]
    chave = os.environ["LLM_API_KEY"]

    if prov == "anthropic":
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": chave, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": modelo, "max_tokens": max_tokens, "system": sistema,
                  "messages": [{"role": "user", "content": usuario}]},
            timeout=120,
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
            timeout=120,
        )
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]

    base = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    r = requests.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {chave}", "content-type": "application/json"},
        json={"model": modelo, "max_tokens": max_tokens,
              "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}]},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def gerar_json(sistema, usuario, max_tokens=2500):
    texto = gerar(sistema, usuario, max_tokens)
    m = re.search(r"\{.*\}", texto, re.S)
    if not m:
        raise ValueError(f"Resposta sem JSON: {texto[:300]}")
    return json.loads(m.group(0))
