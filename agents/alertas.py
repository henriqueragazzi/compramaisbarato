"""AGENTE 9 — Disparo dos alertas de preço (sem IA). Roda depois do Caçador.

Para cada pessoa com alerta: se o preço caiu pelo menos 5% desde a última referência
(preço quando criou o alerta, ou o último aviso enviado), manda mensagem com o link de afiliado.
Guarda os avisos já enviados em data/alertas_enviados.enc (separado do cofre do bot para os dois
robôs nunca brigarem pelo mesmo arquivo).
"""
import html
import json
import time

from comum import DADOS, PRODUTOS, config, ler_json
from tg import _fernet, api, brl, ler_cofre

ENVIADOS = DADOS / "alertas_enviados.enc"
QUEDA_MINIMA = 0.05


def ler_enviados():
    if not ENVIADOS.exists():
        return {"avisos": {}, "bloqueados": []}
    return json.loads(_fernet().decrypt(ENVIADOS.read_bytes()))


def salvar_enviados(d):
    ENVIADOS.write_bytes(_fernet().encrypt(json.dumps(d, separators=(",", ":")).encode()))


def rodar():
    site = config()["site"]
    produtos = ler_json(PRODUTOS, {})
    cofre = ler_cofre()
    env = ler_enviados()
    antes = json.dumps(env, sort_keys=True)
    bloqueados = set(env.get("bloqueados", []))
    enviados = 0
    for chat_id, u in cofre["usuarios"].items():
        if chat_id in bloqueados:
            continue
        for pid, base in u.get("alertas", {}).items():
            p = produtos.get(pid)
            if not p:
                continue
            chave = f"{chat_id}:{pid}"
            ultimo = env["avisos"].get(chave)
            # alerta novo (recriado) com base menor que o último aviso → a base vale
            referencia = min(base, ultimo) if ultimo else base
            if p["preco"] > referencia * (1 - QUEDA_MINIMA):
                continue
            queda = round((referencia - p["preco"]) / referencia * 100)
            selo = "\n🏷️ <b>Menor preço dos últimos 30 dias</b>" if p.get("menor_30d") else ""
            r = api("sendMessage", chat_id=int(chat_id), parse_mode="HTML", disable_web_page_preview=True,
                    text=f"📉 <b>Baixou {queda}%!</b>\n\n{html.escape(p['nome'][:150])}\n\n"
                         f"<s>{brl(referencia)}</s> → <b>{brl(p['preco'])}</b>{selo}\n\n"
                         "Preço pode mudar a qualquer momento na loja.",
                    reply_markup={"inline_keyboard": [
                        [{"text": "🛒 Ver na Shopee", "url": p["link"]}],
                        [{"text": "🔎 Parecidos no site", "url": f"{site['url']}/p/{p['slug']}/"}],
                        [{"text": "❌ Parar este alerta", "callback_data": f"rm:{pid}"}]]})
            if isinstance(r, dict) and r.get("codigo") == 403:
                bloqueados.add(chat_id)   # a pessoa bloqueou o bot
                break
            env["avisos"][chave] = p["preco"]
            enviados += 1
            time.sleep(0.05)
    env["bloqueados"] = sorted(bloqueados)
    if json.dumps(env, sort_keys=True) != antes:
        salvar_enviados(env)
    print(f"Alertas: {enviados} avisos enviados, {len(cofre['usuarios'])} pessoas com alerta.")


if __name__ == "__main__":
    rodar()
