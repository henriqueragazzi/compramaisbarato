# Site de afiliados Shopee — automático

Casa · Pet · Carro e moto · Presentes. Feito para ser **citado pelo ChatGPT** e por outras IAs.

## Os agentes

| # | Agente | Arquivo | Usa IA? | Quando roda |
|---|--------|---------|---------|-------------|
| 1 | Caçador de ofertas | `agents/cacador.py` | Não | a cada 3h |
| 2 | Curador (filtros + pontuação) | dentro do Caçador / `config.yaml` | Não | a cada 3h |
| 3 | Redator de guias | `agents/redator.py` | Sim, modelo barato | a cada 3h (só o que precisa) |
| 4 | Publicador + IndexNow | `agents/publicador.py` | Não | a cada 3h |
| 5 | Telegram | `agents/telegram.py` | Não | a cada 3h |
| 6 | Monitor de IA | `agents/monitor_ia.py` | Usa a busca do ChatGPT/Perplexity | segunda-feira |
| 7 | Analista de comissões | `agents/analista.py` | Não | segunda-feira |

Tudo roda sozinho no **GitHub Actions** (grátis) e o site fica no **GitHub Pages** (grátis).
Custo esperado: domínio (~R$40/ano) + IA dos guias (centavos a poucos reais por mês) + monitor (opcional, ~US$1–3/mês).

---

## Passo a passo (uma vez só)

### 1. Cadastros (só você pode fazer)
1. **Afiliados Shopee:** https://affiliate.shopee.com.br → cadastre-se. Depois de aprovado: **Open API** → copie **App ID** e **Secret**. (A aprovação da API pode levar alguns dias.)
2. **Domínio:** registro.br (ex.: `seunome.com.br`).
3. **GitHub:** crie uma conta em github.com.
4. **Chave de IA barata** (escolha uma):
   - Anthropic (Claude Haiku): console.anthropic.com → `LLM_PROVIDER=anthropic`
   - Google (Gemini Flash): aistudio.google.com → `LLM_PROVIDER=gemini`
   - DeepSeek: platform.deepseek.com → `LLM_PROVIDER=openai`, `LLM_BASE_URL=https://api.deepseek.com/v1`, `LLM_MODEL=deepseek-chat`

### 2. Subir o projeto
1. No GitHub: **New repository**, **público** (o GitHub Pages grátis exige isso; as chaves ficam protegidas nos Secrets e não aparecem).
2. Envie esta pasta inteira para o repositório.
3. Edite `config.yaml`: `nome`, `url` (seu domínio), links do Telegram/WhatsApp.

### 3. Segredos (Settings → Secrets and variables → Actions)
**Secrets:** `SHOPEE_APP_ID`, `SHOPEE_SECRET`, `LLM_API_KEY`, `INDEXNOW_KEY` (invente 32 letras/números), opcionais: `TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY`, `PERPLEXITY_API_KEY`
**Variables:** `LLM_PROVIDER`, `LLM_MODEL` (opcional), `LLM_BASE_URL` (só DeepSeek), `TELEGRAM_CANAL` (ex.: `@meucanal`)

### 4. Publicar
1. **Settings → Pages → Source: GitHub Actions.**
2. **Actions → Robô do site → Run workflow.** Em ~5 min o site está no ar.
3. No registro.br, aponte o domínio para o GitHub Pages (registros A para 185.199.108.153, .109, .110, .111 e CNAME `www` → `seuusuario.github.io`). Em Settings → Pages, coloque o domínio e marque **Enforce HTTPS**.

### 5. Fazer as IAs acharem o site
1. **Bing Webmaster Tools** (bing.com/webmasters): adicione o site e envie `/sitemap.xml`. O ChatGPT usa muito o índice do Bing.
2. **Google Search Console:** adicione o site e envie `/sitemap.xml`.
3. O `robots.txt` já libera OAI-SearchBot, ChatGPT-User, PerplexityBot, ClaudeBot e Googlebot, e o `llms.txt` já é gerado.

---

## Rodar no seu computador (opcional)
```bash
pip install -r requirements.txt
# Ver o visual com dados FALSOS (não publique):
ACHADINHO_DADOS=/tmp/demo python agents/demo.py && ACHADINHO_DADOS=/tmp/demo python agents/publicador.py
cd dist && python -m http.server 8000   # abra http://localhost:8000
```

## Crescer
- **Novas perguntas** → `perguntas.yaml` (use as que o Monitor mostra que você ainda não aparece).
- **Novas palavras/nichos** → `config.yaml`.
- **Qualidade** → `filtros` no `config.yaml` (nota mínima, vendas mínimas).
- Relatórios ficam em `data/monitor/` e `data/relatorio_comissoes.md`.

## Regras que protegem o site
- Os guias nunca dizem que "testamos" o produto e só usam produtos reais do catálogo (o Redator descarta qualquer ID inventado).
- Todo link de compra tem `rel="sponsored nofollow"` e o rodapé informa que o site é afiliado.
- Nada de texto escondido para IAs. O site é citado pelo conteúdo, não por truque.
