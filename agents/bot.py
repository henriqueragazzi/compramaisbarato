"""AGENTE 8 — Bot de alertas no Telegram (sem IA).

Lê as mensagens novas que chegaram ao bot e responde:
  /start a<ID>  → cria alerta de preço para o produto (link do botão do site)
  /start        → boas-vindas + convite para o canal
  /alertas      → lista os alertas da pessoa (com botão para remover)
  /parar        → remove todos os alertas
Roda a cada ~10 min pelo GitHub Actions (.github/workflows/bot.yml).
"""
import html

from comum import PRODUTOS, config, ler_json
from tg import MAX_ALERTAS_POR_PESSOA, api, brl, diagnostico, ler_cofre, salvar_cofre


def esc(t):
    return html.escape(str(t or ""))


def convite_canal(site):
    canal = site.get("telegram")
    return f"\n\n📢 Ofertas do dia, todo dia: {canal}" if canal else ""


def responder(chat_id, texto, botoes=None):
    params = {"chat_id": chat_id, "text": texto, "parse_mode": "HTML", "disable_web_page_preview": True}
    if botoes:
        params["reply_markup"] = {"inline_keyboard": botoes}
    return api("sendMessage", **params)


def criar_alerta(cofre, chat_id, nome, item_id, produtos, site):
    p = produtos.get(item_id)
    if not p:
        responder(chat_id, "Esse produto saiu do nosso catálogo (acabou ou caiu a nota). "
                           f"Veja outras opções em {site['url']}" + convite_canal(site))
        return
    u = cofre["usuarios"].setdefault(str(chat_id), {"nome": nome, "alertas": {}})
    if item_id not in u["alertas"] and len(u["alertas"]) >= MAX_ALERTAS_POR_PESSOA:
        responder(chat_id, f"Você já tem {MAX_ALERTAS_POR_PESSOA} alertas. Use /alertas para remover algum.")
        return
    u["alertas"][item_id] = p["preco"]
    selo = "\n🏷️ Já está no <b>menor preço dos últimos 30 dias</b>." if p.get("menor_30d") else ""
    responder(
        chat_id,
        f"🔔 <b>Alerta criado!</b>\n\n{esc(p['nome'][:150])}\n\nHoje: <b>{brl(p['preco'])}</b>{selo}\n"
        f"Vou te avisar aqui quando ficar mais barato.{convite_canal(site)}",
        [[{"text": "🛒 Ver na Shopee", "url": p["link"]}],
         [{"text": "❌ Cancelar este alerta", "callback_data": f"rm:{item_id}"}]],
    )


def listar(cofre, chat_id, produtos):
    alertas = cofre["usuarios"].get(str(chat_id), {}).get("alertas", {})
    if not alertas:
        responder(chat_id, "Você não tem alertas. No site, toque em <b>🔔 Me avise quando baixar</b> em qualquer produto.")
        return
    linhas, botoes = ["<b>Seus alertas:</b>"], []
    for i, (pid, base) in enumerate(alertas.items(), 1):
        p = produtos.get(pid)
        nome = p["nome"][:60] if p else "(produto fora do catálogo)"
        preco = brl(p["preco"]) if p else "-"
        linhas.append(f"{i}. {esc(nome)} — hoje {preco}")
        botoes.append([{"text": f"❌ Remover {i}", "callback_data": f"rm:{pid}"}])
    responder(chat_id, "\n".join(linhas), botoes[:30])


def rodar():
    site = config()["site"]
    produtos = ler_json(PRODUTOS, {})
    eu = api("getMe")
    print("Bot:", eu.get("username") if isinstance(eu, dict) and "username" in eu else eu)
    if site.get("telegram") and isinstance(eu, dict) and eu.get("id"):
        canal = "@" + site["telegram"].rstrip("/").split("/")[-1]
        m = api("getChatMember", chat_id=canal, user_id=eu["id"])
        ok = isinstance(m, dict) and m.get("status") == "administrator" and m.get("can_post_messages", True)
        print(f"Canal {canal}: " + ("bot é administrador ✓" if ok else f"bot NÃO é administrador ({m})"))
    cofre = ler_cofre()
    updates = api("getUpdates", offset=cofre.get("offset", 0), timeout=0, allowed_updates=["message", "callback_query"])
    if isinstance(updates, dict) and updates.get("erro"):
        dica = (" → o TOKEN está errado: no GitHub, Settings > Secrets > TELEGRAM_BOT_TOKEN, cole só o token"
                " (formato 123456789:AAH...). Diagnóstico: " + diagnostico()) if updates.get("codigo") in (401, 404) else ""
        raise SystemExit(f"Telegram: {updates['erro']}{dica}")

    for up in updates:
        cofre["offset"] = up["update_id"] + 1
        if "callback_query" in up:
            cq = up["callback_query"]
            chat_id = cq["message"]["chat"]["id"]
            if cq.get("data", "").startswith("rm:"):
                pid = cq["data"][3:]
                cofre["usuarios"].get(str(chat_id), {}).get("alertas", {}).pop(pid, None)
                api("answerCallbackQuery", callback_query_id=cq["id"], text="Alerta removido")
            continue

        msg = up.get("message") or {}
        if msg.get("chat", {}).get("type") != "private":
            continue
        chat_id = msg["chat"]["id"]
        nome = msg.get("from", {}).get("first_name", "")
        texto = (msg.get("text") or "").strip()

        if texto.startswith("/start"):
            arg = texto[6:].strip()
            if arg.startswith("a") and arg[1:].isdigit():
                criar_alerta(cofre, chat_id, nome, arg[1:], produtos, site)
            else:
                responder(chat_id,
                          f"Olá{', ' + esc(nome) if nome else ''}! 👋 Eu sou o robô do <b>{esc(site['nome'])}</b>.\n\n"
                          f"No site, toque em <b>🔔 Me avise quando baixar</b> em qualquer produto e eu te aviso aqui "
                          f"quando o preço cair.\n\n{site['url']}{convite_canal(site)}\n\n"
                          "Comandos: /alertas (ver seus alertas) · /parar (cancelar todos)")
        elif texto.startswith("/alertas"):
            listar(cofre, chat_id, produtos)
        elif texto.startswith("/parar"):
            cofre["usuarios"].pop(str(chat_id), None)
            responder(chat_id, "Pronto, cancelei todos os seus alertas. Se mudar de ideia, é só criar de novo pelo site.")
        else:
            responder(chat_id, f"Para criar um alerta, toque em <b>🔔 Me avise quando baixar</b> num produto do site: "
                               f"{site['url']}\n\n/alertas — ver seus alertas\n/parar — cancelar todos")

    if not updates:
        print("Bot: nenhuma mensagem nova.")
        return
    # remove quem ficou sem alerta
    cofre["usuarios"] = {k: v for k, v in cofre["usuarios"].items() if v.get("alertas")}
    salvar_cofre(cofre)
    print(f"Bot: {len(updates)} mensagens, {len(cofre['usuarios'])} pessoas com alerta.")


if __name__ == "__main__":
    rodar()
