import json
import os
import math
import re
import time
import unicodedata
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
DADOS = Path(os.environ.get("ACHADINHO_DADOS", RAIZ / "data"))  # demo usa outra pasta
PRODUTOS = DADOS / "produtos.json"
HISTORICO = DADOS / "historico_precos.json"
GUIAS = DADOS / "guias"


def config():
    return yaml.safe_load((RAIZ / "config.yaml").read_text(encoding="utf-8"))


def ler_json(caminho, padrao):
    p = Path(caminho)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else padrao


def salvar_json(caminho, dados):
    p = Path(caminho)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def slug(texto, maximo=80):
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:maximo].rstrip("-")


def agora():
    return int(time.time())


def pontuacao(p):
    """Nota de 0 a ~100 usada para ordenar: qualidade + popularidade + desconto + comissão."""
    nota = float(p.get("nota") or 0)
    vendas = int(p.get("vendas") or 0)
    desconto = float(p.get("desconto") or 0)
    comissao = float(p.get("comissao") or 0)
    preco = float(p.get("preco") or 0)
    ganho = preco * comissao  # comissão estimada em R$ por venda
    return round(
        math.log10(ganho + 1) * 15  # R$1→4,5 · R$5→11,7 · R$20→19,8 · R$100→30
        +
        (nota - 4) * 30            # 4.0→0, 5.0→30
        + math.log10(vendas + 1) * 10   # 1k vendas→30, 10k→40
        + min(desconto, 70) * 0.2  # até 14
        + min(comissao, 0.2) * 80, # até 16
        2,
    )
