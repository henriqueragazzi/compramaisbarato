"""Base do Telegram: chamadas à API e o cofre de alertas.

Os alertas (quem pediu aviso de qual produto) ficam CRIPTOGRAFADOS em data/alertas.enc,
porque o repositório é público. A chave vem do token do bot (secret TELEGRAM_BOT_TOKEN),
então não precisa de nenhuma senha extra.
"""
import base64
import hashlib
import json
import os

import requests
from cryptography.fernet import Fernet, InvalidToken

from comum import DADOS

COFRE = DADOS / "alertas.enc"
MAX_ALERTAS_POR_PESSOA = 30


def token():
    t = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not t:
        raise SystemExit("Defina TELEGRAM_BOT_TOKEN")
    return t


def api(metodo, **params):
    r = requests.post(f"https://api.telegram.org/bot{token()}/{metodo}", json=params, timeout=60)
    dados = r.json()
    if not dados.get("ok"):
        # 403 = a pessoa bloqueou o bot
        return {"erro": dados.get("description", ""), "codigo": dados.get("error_code")}
    return dados["result"]


def _fernet():
    chave = hashlib.sha256(("alertas:" + token()).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(chave))


def ler_cofre():
    """{"offset": int, "usuarios": {chat_id: {"nome":..., "alertas": {item_id: preco_base}}}}"""
    if not COFRE.exists():
        return {"offset": 0, "usuarios": {}}
    try:
        return json.loads(_fernet().decrypt(COFRE.read_bytes()))
    except InvalidToken:
        raise SystemExit("Não consegui abrir data/alertas.enc: o token do bot mudou? (apague o arquivo para recomeçar)")


def salvar_cofre(dados):
    COFRE.parent.mkdir(parents=True, exist_ok=True)
    COFRE.write_bytes(_fernet().encrypt(json.dumps(dados, separators=(",", ":")).encode()))


def brl(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
