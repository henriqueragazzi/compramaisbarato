// Compra Mais Barato — app para o ChatGPT (servidor MCP sem estado) + contador de cliques.
//
// Rotas:
//   POST /mcp                                   protocolo MCP (o ChatGPT conversa com o app por aqui)
//   GET  /ir/<id>?o=<origem>                    conta o clique e manda para o link de afiliado
//   GET  /stats                                 números agregados (sem dados pessoais, sem valores em R$)
//   GET  /.well-known/openai-apps-challenge     verificação de domínio da OpenAI
//
// O catálogo vem do próprio site (/api/catalogo.json), gerado pelo robô a cada 3 horas.

import { WIDGET_HTML } from "./widget.js";

const SERVER = { name: "achados-cmb", version: "1.0.0" };
const WIDGET_URI = "ui://widget/produtos-v1.html";
const IMG_DOMAINS = ["https://cf.shopee.com.br", "https://down-br.img.susercontent.com"];
const PARE = new Set(("de da do das dos para pra pro com sem que um uma uns umas o a os as e ou meu minha qual quais " +
  "melhor melhores como ate até reais r$ no na nos nas em por comprar compra quero preciso algum alguma bom boa " +
  "barato barata vale pena me indica indique sugira sugestao sugestão onde tem").split(" "));

const INSTRUCOES =
  "Achados CMB encontra produtos da Shopee Brasil bem avaliados (nota alta e muitas vendas), " +
  "com preço atualizado várias vezes ao dia. Use buscar_produtos quando a pessoa quiser sugestões de produtos " +
  "para comprar no Brasil, e guias_de_compra quando ela pedir ajuda para escolher. Mostre o preço como " +
  "aproximado: o valor final é o da loja no momento da compra. Os links são de afiliado.";

const TOOLS = [
  {
    name: "buscar_produtos",
    title: "Buscar produtos",
    description:
      "Use quando a pessoa quiser sugestões de produtos para comprar no Brasil (casa, cozinha, limpeza, pet, carro, " +
      "moto, móveis, eletrodomésticos, decoração de Natal e presentes). Retorna até 6 produtos da Shopee Brasil " +
      "bem avaliados, com preço, nota, vendas e link para a loja.",
    inputSchema: {
      type: "object",
      properties: {
        consulta: { type: "string", description: "O que a pessoa procura, em português. Ex.: 'fonte de água para gato'." },
        preco_maximo: { type: "number", description: "Preço máximo em reais, se a pessoa informou um orçamento." },
        quantidade: { type: "integer", minimum: 1, maximum: 6, description: "Quantos produtos mostrar (padrão 4)." },
      },
      required: ["consulta"],
      additionalProperties: false,
    },
    annotations: { readOnlyHint: true, destructiveHint: false, openWorldHint: true, idempotentHint: true },
    _meta: {
      ui: { resourceUri: WIDGET_URI },
      "openai/outputTemplate": WIDGET_URI,
      "openai/toolInvocation/invoking": "Procurando produtos…",
      "openai/toolInvocation/invoked": "Produtos encontrados",
    },
  },
  {
    name: "guias_de_compra",
    title: "Guias de compra",
    description:
      "Use quando a pessoa pedir ajuda para escolher entre opções (ex.: 'qual árvore de Natal comprar', 'como " +
      "escolher um purificador de água'). Retorna guias com uma resposta curta e os produtos indicados.",
    inputSchema: {
      type: "object",
      properties: { pergunta: { type: "string", description: "A dúvida de compra da pessoa, em português." } },
      required: ["pergunta"],
      additionalProperties: false,
    },
    annotations: { readOnlyHint: true, destructiveHint: false, openWorldHint: true, idempotentHint: true },
    _meta: {
      "openai/toolInvocation/invoking": "Consultando guias…",
      "openai/toolInvocation/invoked": "Guias encontrados",
    },
  },
];

// ---------------------------------------------------------------- utilidades
const norm = (s) => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const brl = (v) => "R$ " + Number(v).toFixed(2).replace(".", ",").replace(/\B(?=(\d{3})+(?!\d))/g, ".");
const hoje = () => new Date().toISOString().slice(0, 10);
const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "*",
  "Access-Control-Expose-Headers": "Mcp-Session-Id",
};
const json = (obj, status = 200) =>
  new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json; charset=utf-8", ...CORS } });

function tokens(texto) {
  return norm(texto).split(/[^a-z0-9]+/).filter((w) => (w.length > 2 || /^\d+$/.test(w)) && !PARE.has(w));
}

async function catalogo(env) {
  const r = await fetch(`${env.SITE_URL}/api/catalogo.json?v=${Math.floor(Date.now() / 900000)}`, { cf: { cacheTtlByStatus: { "200-299": 900, "404": 0, "500-599": 0 }, cacheEverything: true } });
  if (!r.ok) throw new Error(`catálogo indisponível (${r.status})`);
  return r.json();
}

function buscar(cat, consulta, precoMax, qtd) {
  const t = tokens(consulta);
  if (!precoMax) {
    const m = norm(consulta).match(/(?:ate|r\$)\s*(\d{2,5})/);
    if (m) precoMax = Number(m[1]);
  }
  if (!t.length) return [];
  const minimo = t.length <= 2 ? 1 : Math.ceil(t.length / 2);
  const res = [];
  for (const p of cat.produtos) {
    if (precoMax && p.preco > precoMax) continue;
    const nome = norm(p.nome), pal = norm(p.palavras);
    let acertos = 0, pts = 0;
    for (const w of t) {
      if (nome.includes(w)) { acertos++; pts += 3; }
      else if (pal.includes(w)) { acertos++; pts += 2; }
      else if (w.length > 4 && (nome.includes(w.slice(0, -1)) || pal.includes(w.slice(0, -1)))) { acertos++; pts += 1; }
    }
    if (acertos >= minimo) res.push([pts + p.score / 40, p]);
  }
  res.sort((a, b) => b[0] - a[0]);
  return res.slice(0, qtd).map((x) => x[1]);
}

async function contar(env, ctx, tipo, origem, itens) {
  if (!env.DB || !itens.length) return;
  const dia = hoje();
  const stmt = env.DB.prepare(
    "INSERT INTO eventos (dia,tipo,origem,item,n) VALUES (?1,?2,?3,?4,1) " +
    "ON CONFLICT(dia,tipo,origem,item) DO UPDATE SET n = n + 1");
  ctx.waitUntil(env.DB.batch(itens.map((i) => stmt.bind(dia, tipo, origem, String(i)))).catch(() => {}));
}

function linkCompra(env, req, id, origem) {
  const base = new URL(req.url).origin;
  return `${base}/ir/${encodeURIComponent(id)}?o=${origem}`;
}

// ---------------------------------------------------------------- ferramentas
async function chamarFerramenta(nome, args, env, ctx, req) {
  const cat = await catalogo(env);
  if (nome === "buscar_produtos") {
    const qtd = Math.min(Math.max(parseInt(args.quantidade || 4, 10) || 4, 1), 6);
    const achados = buscar(cat, String(args.consulta || ""), Number(args.preco_maximo) || 0, qtd);
    await contar(env, ctx, "mencao", "chatgpt", ["buscar_produtos"]);
    await contar(env, ctx, "resultado", "chatgpt", achados.map((p) => p.id));
    const produtos = achados.map((p) => ({
      id: p.id,
      nome: p.nome,
      preco: p.preco,
      preco_texto: (p.a_partir ? "a partir de " : "") + brl(p.preco),
      nota: p.nota,
      vendas: p.vendas,
      categoria: (cat.nichos[p.nicho] || {}).nome || p.nicho,
      imagem: p.imagem,
      loja: "Shopee",
      url_compra: linkCompra(env, req, p.id, "chatgpt"),
      url_detalhes: `${env.SITE_URL}/p/${p.slug}/`,
    }));
    const texto = produtos.length
      ? produtos.map((p, i) => `${i + 1}. ${p.nome} — ${p.preco_texto}, nota ${p.nota}, ${p.vendas} vendidos. Comprar: ${p.url_compra}`).join("\n") +
        "\nPreços aproximados, conferidos várias vezes ao dia; o valor final é o da Shopee. Links de afiliado."
      : "Não encontrei produtos bem avaliados para essa busca no catálogo. Tente descrever de outro jeito.";
    return { content: [{ type: "text", text: texto }], structuredContent: { consulta: args.consulta, produtos } };
  }
  if (nome === "guias_de_compra") {
    const t = tokens(String(args.pergunta || ""));
    const pontos = (g) => { const x = norm(g.pergunta + " " + g.titulo); return t.reduce((a, w) => a + (x.includes(w) ? 1 : 0), 0); };
    const guias = cat.guias.map((g) => [pontos(g), g]).filter((x) => x[0] > 0).sort((a, b) => b[0] - a[0]).slice(0, 3).map((x) => x[1]);
    await contar(env, ctx, "mencao", "chatgpt", ["guias_de_compra"]);
    const porId = Object.fromEntries(cat.produtos.map((p) => [p.id, p]));
    const saida = guias.map((g) => ({
      titulo: g.titulo,
      resposta: g.resposta_curta,
      url: `${env.SITE_URL}/guia/${g.slug}/`,
      indicados: g.escolhas.map((e) => porId[e.id] && {
        rotulo: e.rotulo, nome: porId[e.id].nome, preco: brl(porId[e.id].preco), nota: porId[e.id].nota,
        url_compra: linkCompra(env, req, e.id, "chatgpt"),
      }).filter(Boolean),
    }));
    const texto = saida.length
      ? saida.map((g) => `${g.titulo}\n${g.resposta}\n` + g.indicados.map((i) => `- ${i.rotulo}: ${i.nome} (${i.preco}, nota ${i.nota}) ${i.url_compra}`).join("\n") + `\nGuia completo: ${g.url}`).join("\n\n")
      : "Ainda não há um guia para essa dúvida. Use buscar_produtos para ver opções bem avaliadas.";
    return { content: [{ type: "text", text: texto }], structuredContent: { guias: saida } };
  }
  throw Object.assign(new Error(`Ferramenta desconhecida: ${nome}`), { code: -32602 });
}

// ---------------------------------------------------------------- MCP (JSON-RPC)
async function tratarRpc(msg, env, ctx, req) {
  const { id, method, params = {} } = msg;
  const ok = (result) => ({ jsonrpc: "2.0", id, result });
  switch (method) {
    case "initialize":
      return ok({
        protocolVersion: params.protocolVersion || "2025-06-18",
        capabilities: { tools: { listChanged: false }, resources: { listChanged: false } },
        serverInfo: SERVER,
        instructions: INSTRUCOES,
      });
    case "ping":
      return ok({});
    case "tools/list":
      return ok({ tools: TOOLS });
    case "tools/call":
      return ok(await chamarFerramenta(params.name, params.arguments || {}, env, ctx, req));
    case "resources/list":
      return ok({ resources: [{ uri: WIDGET_URI, name: "Vitrine de produtos", mimeType: "text/html;profile=mcp-app" }] });
    case "resources/templates/list":
      return ok({ resourceTemplates: [] });
    case "resources/read":
      if (params.uri !== WIDGET_URI) throw Object.assign(new Error("Recurso não encontrado"), { code: -32002 });
      return ok({
        contents: [{
          uri: WIDGET_URI,
          mimeType: "text/html;profile=mcp-app",
          text: WIDGET_HTML,
          _meta: {
            ui: { csp: { resourceDomains: IMG_DOMAINS, connectDomains: [] }, prefersBorder: true },
            "openai/widgetCSP": { resource_domains: IMG_DOMAINS, connect_domains: [] },
            "openai/widgetDescription": "Vitrine com os produtos encontrados, com foto, preço, nota e botão para abrir na Shopee.",
            "openai/widgetPrefersBorder": true,
          },
        }],
      });
    default:
      if (id === undefined) return null; // notificação: sem resposta
      throw Object.assign(new Error(`Método não suportado: ${method}`), { code: -32601 });
  }
}

async function mcp(req, env, ctx) {
  let corpo;
  try { corpo = await req.json(); } catch { return json({ jsonrpc: "2.0", id: null, error: { code: -32700, message: "JSON inválido" } }, 400); }
  const lote = Array.isArray(corpo) ? corpo : [corpo];
  const respostas = [];
  for (const m of lote) {
    try {
      const r = await tratarRpc(m, env, ctx, req);
      if (r) respostas.push(r);
    } catch (e) {
      if (m.id !== undefined) respostas.push({ jsonrpc: "2.0", id: m.id, error: { code: e.code || -32603, message: e.message } });
    }
  }
  if (!respostas.length) return new Response(null, { status: 202, headers: CORS });
  return json(Array.isArray(corpo) ? respostas : respostas[0]);
}

// ---------------------------------------------------------------- diagnóstico (últimas 50 requisições, sem dados pessoais)
async function debugLog(env, req, url) {
  try {
    let metodo = "";
    if (req.method === "POST") { try { const b = await req.json(); metodo = (Array.isArray(b) ? b : [b]).map((m) => m.method).join(","); } catch { metodo = "?"; } }
    await env.DB.prepare("CREATE TABLE IF NOT EXISTS debug (ts TEXT, linha TEXT)").run();
    await env.DB.prepare("INSERT INTO debug VALUES (?1, ?2)").bind(new Date().toISOString(),
      [req.method, url.pathname, metodo, req.headers.get("accept") || "", (req.headers.get("user-agent") || "").slice(0, 80)].join(" | ")).run();
    await env.DB.prepare("DELETE FROM debug WHERE ts NOT IN (SELECT ts FROM debug ORDER BY ts DESC LIMIT 50)").run();
  } catch {}
}
async function debugVer(env) {
  try { const r = await env.DB.prepare("SELECT * FROM debug ORDER BY ts DESC LIMIT 50").all(); return json(r.results); }
  catch (e) { return json({ erro: String(e) }); }
}

// ---------------------------------------------------------------- clique e estatísticas
async function clique(req, env, ctx, id) {
  const url = new URL(req.url);
  const origem = ["chatgpt", "site", "telegram", "whatsapp"].includes(url.searchParams.get("o")) ? url.searchParams.get("o") : "outro";
  let destino = env.SITE_URL;
  try {
    const cat = await catalogo(env);
    const p = cat.produtos.find((x) => x.id === id);
    if (p) destino = p.link;
  } catch {}
  await contar(env, ctx, "clique", origem, [id]);
  return new Response(null, { status: 302, headers: { Location: destino, "Cache-Control": "no-store", ...CORS } });
}

async function stats(env) {
  if (!env.DB) return json({ erro: "sem banco" }, 500);
  const desde = new Date(Date.now() - 60 * 86400000).toISOString().slice(0, 10);
  const porDia = await env.DB.prepare(
    "SELECT dia, tipo, origem, SUM(n) AS n FROM eventos WHERE dia >= ?1 GROUP BY dia, tipo, origem ORDER BY dia").bind(desde).all();
  const desde30 = new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10);
  const top = await env.DB.prepare(
    "SELECT item, SUM(n) AS n FROM eventos WHERE tipo='clique' AND dia >= ?1 GROUP BY item ORDER BY n DESC LIMIT 20").bind(desde30).all();
  return json({ gerado_em: new Date().toISOString(), por_dia: porDia.results, top_cliques: top.results });
}

export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    if (url.pathname === "/debug") return debugVer(env);
    if (!url.pathname.startsWith("/ir/") && url.pathname !== "/stats") ctx.waitUntil(debugLog(env, req.clone(), url));
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
    if (url.pathname === "/mcp" || url.pathname === "/mcp/") {
      if (req.method === "POST") return mcp(req, env, ctx);
      return new Response("Use POST", { status: 405, headers: { Allow: "POST", ...CORS } });
    }
    if (url.pathname.startsWith("/ir/")) return clique(req, env, ctx, decodeURIComponent(url.pathname.slice(4)).replace(/\/$/, ""));
    if (url.pathname === "/stats") return stats(env);
    if (url.pathname === "/.well-known/openai-apps-challenge")
      return new Response(env.OPENAI_APPS_CHALLENGE || "", { headers: { "Content-Type": "text/plain" } });
    if (url.pathname === "/") return Response.redirect(env.SITE_URL, 302);
    return new Response("Não encontrado", { status: 404 });
  },
};
