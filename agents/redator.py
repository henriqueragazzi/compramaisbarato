"""AGENTE 3 — Redator de guias (usa modelo barato; ~1 chamada por guia).

Para cada pergunta em perguntas.yaml, escolhe os melhores produtos do catálogo
e pede ao modelo um guia curto e direto, no formato que o ChatGPT gosta de citar.
Só reescreve guias novos, com produtos que sumiram ou com mais de 21 dias.

Uso:  python agents/redator.py              (até 15 guias por rodada)
      python agents/redator.py --max 60 --forcar
"""
import argparse
import unicodedata

import yaml

from comum import GUIAS, PRODUTOS, RAIZ, agora, ler_json, salvar_json, slug
from llm import gerar_json

DIAS_REESCREVER = 21

SISTEMA = """Você é redator de um site brasileiro de guias de compra. Escreve em português do Brasil, claro, direto e honesto.
Regras obrigatórias:
- Use SOMENTE os produtos da lista recebida, pelo "id". Não invente produtos, marcas, medidas ou especificações que não estejam no nome.
- O "id" serve só para o campo "id": nunca escreva o id nem "(id ...)" nos textos.
- NUNCA diga que testou, usou ou avaliou pessoalmente. Baseie-se em nota, número de vendas, preço e no que o nome descreve.
- Não prometa resultados (saúde, segurança) nem use superlativos falsos.
- "resposta_curta" responde a pergunta em 2 ou 3 frases logo de cara, citando o produto principal e a faixa de preço.
- Escolha de 3 a 6 produtos, cada um para um perfil diferente (melhor geral, mais barato, mais vendido, etc.).
- Dicas e FAQ devem ser úteis de verdade (como escolher, cuidados, erros comuns), mesmo sem produto.
- Seja ENXUTO: intro com até 3 frases; "porque" e "ideal_para" com até 2 frases cada; 3 a 5 itens em "como_escolher"; 3 perguntas no "faq"; "descricao_meta" com até 155 caracteres.
Responda APENAS com o JSON, sem ``` e sem texto antes ou depois, neste formato:
{"titulo": str, "resposta_curta": str, "intro": str,
 "escolhas": [{"id": str, "rotulo": str, "porque": str, "ideal_para": str}],
 "como_escolher": [str], "faq": [{"q": str, "a": str}], "descricao_meta": str}"""


def norm(t):
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()


def candidatos(produtos, item, nicho):
    termos = [norm(b) for b in item["busca"]]
    teto = item.get("ate")
    achados = []
    for p in produtos.values():
        if nicho != "presentes" and p["nicho"] != nicho:
            continue
        nome = norm(p["nome"] + " " + " ".join(p.get("palavras", [])))
        if not any(t in nome for t in termos):
            continue
        if teto and p["preco"] > teto:
            continue
        achados.append(p)
    return sorted(achados, key=lambda p: -p["score"])[:12]


def precisa_reescrever(guia, produtos, forcar):
    if forcar or not guia:
        return True
    if agora() - guia.get("escrito_em", 0) > DIAS_REESCREVER * 86400:
        return True
    vivos = [e for e in guia.get("escolhas", []) if e["id"] in produtos]
    return len(vivos) < 3


def rodar(maximo=15, forcar=False):
    perguntas = yaml.safe_load((RAIZ / "perguntas.yaml").read_text(encoding="utf-8"))
    produtos = ler_json(PRODUTOS, {})
    feitos = 0
    for nicho, itens in perguntas.items():
        for item in itens:
            if feitos >= maximo:
                print(f"Limite de {maximo} guias nesta rodada.")
                return
            s = slug(item["pergunta"])
            caminho = GUIAS / f"{s}.json"
            guia = ler_json(caminho, None)
            if not precisa_reescrever(guia, produtos, forcar):
                continue
            cands = candidatos(produtos, item, nicho)
            if len(cands) < 3:
                print(f"  - pulando (poucos produtos): {item['pergunta']}")
                continue
            lista = "\n".join(
                f'- id={p["id"]} | {p["nome"]} | R$ {p["preco"]:.2f} | nota {p["nota"]} | {p["vendas"]} vendidos'
                + (f' | {p["desconto"]}% off' if p["desconto"] else "")
                for p in cands
            )
            usuario = f"Pergunta do leitor: {item['pergunta']}\n" + (
                f"Orçamento máximo: R$ {item['ate']}\n" if item.get("ate") else "") + f"\nProdutos disponíveis:\n{lista}"
            try:
                g = gerar_json(SISTEMA, usuario, max_tokens=5000)
            except Exception as e:
                print(f"  ! erro no guia '{item['pergunta']}': {e}")
                continue
            ids_validos = {p["id"] for p in cands}
            g["escolhas"] = [e for e in g.get("escolhas", []) if str(e.get("id")) in ids_validos]
            for e in g["escolhas"]:
                e["id"] = str(e["id"])
            if len(g["escolhas"]) < 3:
                print(f"  ! guia descartado (escolhas inválidas): {item['pergunta']}")
                continue
            g.update({"slug": s, "pergunta": item["pergunta"], "nicho": nicho,
                      "escrito_em": agora(), "criado_em": (guia or {}).get("criado_em", agora())})
            salvar_json(caminho, g)
            feitos += 1
            print(f"  ✓ guia: {item['pergunta']}")
    print(f"Redator: {feitos} guias escritos.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=15)
    ap.add_argument("--forcar", action="store_true")
    a = ap.parse_args()
    rodar(a.max, a.forcar)
