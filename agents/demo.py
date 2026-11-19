"""Gera dados FALSOS só para ver o visual do site sem as chaves da API.
NUNCA publique o resultado. Uso:
  ACHADINHO_DADOS=/tmp/demo python agents/demo.py && ACHADINHO_DADOS=/tmp/demo python agents/publicador.py
"""
import random
import time

import yaml

from comum import GUIAS, HISTORICO, PRODUTOS, RAIZ, config, pontuacao, salvar_json, slug

random.seed(7)
cfg = config()
produtos, hist = {}, {}
i = 1000
for k, n in cfg["nichos"].items():
    for palavra in n["palavras"]:
        for j in range(4):
            i += 1
            preco = round(random.uniform(15, 220), 2)
            desc = random.choice([0, 10, 20, 35, 50])
            p = {"id": str(i), "shop_id": "1", "nome": f"[EXEMPLO] {palavra.title()} modelo {j+1}", "loja": "Loja Exemplo",
                 "preco": preco, "preco_antigo": round(preco / (1 - desc / 100), 2) if desc else None, "desconto": desc,
                 "vendas": random.randint(100, 30000), "nota": round(random.uniform(4.6, 5.0), 1), "comissao": 0.08,
                 "imagem": f"https://picsum.photos/seed/{i}/400/400", "link_produto": "#", "link": "https://shopee.com.br",
                 "nicho": k, "palavras": [palavra], "primeira_vez": int(time.time()), "visto_em": int(time.time()),
                 "menor_30d": random.random() < .2, "queda": random.choice([0, 0, 0, 12, 25])}
            p["slug"] = f"{slug(p['nome'])}-{p['id']}"
            p["score"] = pontuacao(p)
            produtos[p["id"]] = p
            hist[p["id"]] = {"2026-11-18": preco + 5, "2026-11-19": preco}
salvar_json(PRODUTOS, produtos)
salvar_json(HISTORICO, hist)

perg = yaml.safe_load((RAIZ / "perguntas.yaml").read_text(encoding="utf-8"))
from redator import candidatos
for nicho, itens in perg.items():
    for it in itens[:4]:
        c = candidatos(produtos, it, nicho)
        if len(c) < 3:
            continue
        salvar_json(GUIAS / f"{slug(it['pergunta'])}.json", {
            "slug": slug(it["pergunta"]), "pergunta": it["pergunta"], "nicho": nicho, "titulo": it["pergunta"],
            "resposta_curta": f"[TEXTO DE EXEMPLO] A melhor opção custo-benefício é o {c[0]['nome']}, por cerca de R$ {c[0]['preco']:.0f}.",
            "intro": "Texto de exemplo. Aqui o Redator escreve uma introdução curta e útil.",
            "escolhas": [{"id": p["id"], "rotulo": r, "porque": "Explicação de exemplo baseada em nota, vendas e preço.", "ideal_para": "quem quer exemplo"}
                         for p, r in zip(c, ["Melhor geral", "Mais barato", "Mais vendido", "Premium"])],
            "como_escolher": ["Dica de exemplo 1", "Dica de exemplo 2"], "faq": [{"q": "Pergunta de exemplo?", "a": "Resposta de exemplo."}],
            "descricao_meta": it["pergunta"], "escrito_em": int(time.time()), "criado_em": int(time.time())})
print(f"Demo: {len(produtos)} produtos falsos e guias de exemplo em {PRODUTOS.parent}")
