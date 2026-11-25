// Painel privado: visitas, cliques, menções no ChatGPT e vendas da Shopee.
// Acesso: /painel?k=SENHA uma vez (grava um cookie); a senha é o segredo PAINEL_SENHA do worker.

const HTML_HEAD = { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" };

async function sha(t) {
  const b = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(t));
  return [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, "0")).join("");
}

function cookie(req, nome) {
  const m = (req.headers.get("cookie") || "").match(new RegExp(`(?:^|; )${nome}=([^;]+)`));
  return m ? m[1] : "";
}

async function autorizado(req, env) {
  if (!env.PAINEL_SENHA) return false;
  return cookie(req, "painel") === (await sha("painel:" + env.PAINEL_SENHA));
}

function paginaSimples(msg) {
  return `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Painel</title><body style="font:16px system-ui;max-width:420px;margin:15vh auto;padding:0 20px;color:#1d1d1f">
<h2>Painel Compra Mais Barato</h2><p>${msg}</p>
<form method="get" action="/painel"><input name="k" type="password" placeholder="Senha" style="font:inherit;padding:10px;width:100%;box-sizing:border-box;border:1px solid #ccc;border-radius:8px">
<button style="margin-top:10px;font:inherit;padding:10px 16px;border:0;border-radius:8px;background:#ff5a1f;color:#fff">Entrar</button></form></body>`;
}

export async function painel(req, env) {
  const url = new URL(req.url);
  if (!env.PAINEL_SENHA) return new Response(paginaSimples("A senha do painel ainda não foi configurada."), { headers: HTML_HEAD });
  const k = url.searchParams.get("k");
  if (k !== null) {
    if (k === env.PAINEL_SENHA) {
      const v = await sha("painel:" + env.PAINEL_SENHA);
      return new Response(null, { status: 302, headers: {
        Location: "/painel", "Set-Cookie": `painel=${v}; Path=/painel; Max-Age=31536000; HttpOnly; Secure; SameSite=Lax` } });
    }
    return new Response(paginaSimples("Senha incorreta."), { status: 401, headers: HTML_HEAD });
  }
  if (!(await autorizado(req, env))) return new Response(paginaSimples("Digite a senha para ver o painel."), { status: 401, headers: HTML_HEAD });
  if (url.pathname === "/painel/dados") return dados(env);
  return new Response(PAINEL_HTML, { headers: HTML_HEAD });
}

async function tentar(env, sql, ...p) {
  try { return (await env.DB.prepare(sql).bind(...p).all()).results; } catch { return []; }
}

async function dados(env) {
  const desde = new Date(Date.now() - 3 * 3600e3 - 59 * 86400e3).toISOString().slice(0, 10);
  const eventos = await tentar(env,
    "SELECT dia, tipo, origem, SUM(n) AS n FROM eventos WHERE dia >= ?1 GROUP BY dia, tipo, origem", desde);
  const vendas = await tentar(env, "SELECT * FROM vendas WHERE dia >= ?1 ORDER BY dia", desde);
  const d30 = new Date(Date.now() - 3 * 3600e3 - 29 * 86400e3).toISOString().slice(0, 10);
  const topCliques = await tentar(env,
    "SELECT item, origem, SUM(n) AS n FROM eventos WHERE tipo='clique' AND dia >= ?1 GROUP BY item, origem ORDER BY n DESC LIMIT 40", d30);
  const topVendas = await tentar(env,
    "SELECT item, nome, nicho, SUM(qtd) AS qtd, SUM(comissao) AS comissao FROM vendas_itens WHERE dia >= ?1 GROUP BY item ORDER BY comissao DESC LIMIT 15", d30);
  const paginas = await tentar(env,
    "SELECT item, SUM(n) AS n FROM eventos WHERE tipo='visita' AND dia >= ?1 GROUP BY item ORDER BY n DESC LIMIT 10", d30);
  let nomes = {};
  try {
    const cat = await (await fetch(`${env.SITE_URL}/api/catalogo.json?v=${Math.floor(Date.now() / 900000)}`)).json();
    for (const p of cat.produtos) nomes[p.id] = { nome: p.nome, slug: p.slug };
  } catch {}
  return new Response(JSON.stringify({ gerado_em: new Date().toISOString(), eventos, vendas, topCliques, topVendas, paginas, nomes }),
    { headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" } });
}

const PAINEL_HTML = `<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>Painel · Compra Mais Barato</title>
<style>
:root{--cor:#ff5a1f;--tx:#1d1d1f;--mut:#6b6b72;--bd:#ececf0;--bg:#f6f6f8;--card:#fff;--ok:#0a8a4a;
 --s1:#ff5a1f;--s2:#2f6fde;--s3:#0a8a4a;--s4:#9b59b6;--s5:#8a8a93}
@media (prefers-color-scheme:dark){:root{--tx:#f2f2f4;--mut:#a0a0a8;--bd:#2c2c31;--bg:#141416;--card:#1c1c1f;--s5:#6b6b72}}
*{box-sizing:border-box}body{margin:0;font:15px/1.45 system-ui,-apple-system,Segoe UI,sans-serif;background:var(--bg);color:var(--tx)}
main{max-width:1100px;margin:0 auto;padding:20px}
h1{font-size:22px;margin:4px 0 2px}.sub{color:var(--mut);font-size:13px;margin-bottom:18px}
.per{display:flex;gap:6px;margin:0 0 16px}.per button{font:inherit;font-size:13px;padding:6px 12px;border:1px solid var(--bd);background:var(--card);color:var(--tx);border-radius:20px;cursor:pointer}
.per button.on{background:var(--tx);color:var(--bg);border-color:var(--tx)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:16px}
.k{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:12px 14px}
.k .r{font-size:12px;color:var(--mut)}.k .v{font-size:24px;font-weight:650;margin-top:2px;font-variant-numeric:tabular-nums}
.k .d{font-size:12px;color:var(--mut);margin-top:2px}
.g{display:grid;grid-template-columns:1fr 1fr;gap:12px}@media(max-width:800px){.g{grid-template-columns:1fr}}
.c{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:14px 16px;margin-bottom:12px}
.c h2{font-size:15px;margin:0 0 10px}
.leg{display:flex;flex-wrap:wrap;gap:12px;font-size:12px;color:var(--mut);margin-bottom:6px}.leg i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:-1px}
svg{display:block;width:100%;height:auto}
table{width:100%;border-collapse:collapse;font-size:13px}td,th{padding:6px 4px;border-bottom:1px solid var(--bd);text-align:left;vertical-align:top}
th{color:var(--mut);font-weight:500}td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
a{color:inherit}.vazio{color:var(--mut);font-size:13px;padding:8px 0}
.funil{display:flex;gap:6px;align-items:stretch;flex-wrap:wrap}.funil div{flex:1;min-width:110px;background:var(--bg);border-radius:10px;padding:10px}
.funil b{display:block;font-size:20px}.funil span{font-size:12px;color:var(--mut)}
</style></head><body><main>
<h1>Painel Compra Mais Barato</h1><div class="sub" id="sub">Carregando…</div>
<div class="per" id="per"><button data-d="1">Hoje</button><button data-d="7" class="on">7 dias</button><button data-d="30">30 dias</button><button data-d="60">60 dias</button></div>
<div class="kpis" id="kpis"></div>
<div class="c"><h2>Funil do período</h2><div class="funil" id="funil"></div></div>
<div class="g">
 <div class="c"><h2>Visitas por dia</h2><div class="leg" id="lv"></div><div id="gv"></div></div>
 <div class="c"><h2>Cliques para a Shopee por dia</h2><div class="leg" id="lc"></div><div id="gc"></div></div>
 <div class="c"><h2>ChatGPT: vezes que o app foi usado</h2><div id="gm"></div></div>
 <div class="c"><h2>Comissão por dia (R$)</h2><div id="gr"></div></div>
</div>
<div class="g">
 <div class="c"><h2>Produtos mais clicados (30 dias)</h2><div id="tc"></div></div>
 <div class="c"><h2>Produtos que mais renderam (30 dias)</h2><div id="tv"></div></div>
</div>
<div class="c"><h2>De onde vêm as visitas (período)</h2><div id="ov"></div></div>
<div class="sub">Cliques de robôs ficam de fora. Vendas e comissão vêm do relatório de afiliados da Shopee (estimado, atualizado a cada 3 horas). Visitas contam só quem abre o site num navegador.</div>
</main>
<script>
const ORIG={site:"Site",chatgpt:"ChatGPT",google:"Google",bing:"Bing",telegram:"Telegram",direto:"Direto",outro:"Outros",whatsapp:"WhatsApp"};
const COR={chatgpt:"var(--s3)",site:"var(--s1)",google:"var(--s2)",bing:"var(--s4)",telegram:"var(--s2)",direto:"var(--s5)",outro:"var(--s5)",whatsapp:"var(--s3)"};
const brl=v=>"R$ "+(v||0).toLocaleString("pt-BR",{minimumFractionDigits:2,maximumFractionDigits:2});
const num=v=>(v||0).toLocaleString("pt-BR");
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
let D=null,dias=7;
function diasLista(n){const out=[];const base=new Date(Date.now()-3*3600e3);for(let i=n-1;i>=0;i--){out.push(new Date(base-i*86400e3).toISOString().slice(0,10))}return out}
function soma(tipo,lista,origem){return D.eventos.filter(e=>e.tipo===tipo&&lista.includes(e.dia)&&(!origem||e.origem===origem)).reduce((a,e)=>a+e.n,0)}
function serie(tipo,lista){const por={};for(const e of D.eventos){if(e.tipo!==tipo||!lista.includes(e.dia))continue;(por[e.origem]??={})[e.dia]=(por[e.origem][e.dia]||0)+e.n}return por}
function barras(el,lista,series,fmt){
 const W=520,H=170,pl=34,pb=20,pt=8;const ks=Object.keys(series);
 const tot=lista.map(d=>ks.reduce((a,k)=>a+(series[k][d]||0),0));const mx=Math.max(1,...tot);
 const bw=(W-pl)/lista.length;let s='<svg viewBox="0 0 '+W+' '+H+'" role="img">';
 for(let i=0;i<=3;i++){const v=mx*i/3,y=H-pb-(H-pb-pt)*i/3;s+='<line x1="'+pl+'" x2="'+W+'" y1="'+y+'" y2="'+y+'" stroke="var(--bd)"/><text x="'+(pl-4)+'" y="'+(y+4)+'" font-size="10" text-anchor="end" fill="var(--mut)">'+(fmt?fmt(v):Math.round(v))+'</text>'}
 lista.forEach((d,i)=>{let y=H-pb;for(const k of ks){const v=series[k][d]||0;if(!v)continue;const h=(H-pb-pt)*v/mx;y-=h;
  s+='<rect x="'+(pl+i*bw+bw*.15)+'" y="'+y+'" width="'+Math.max(1,bw*.7)+'" height="'+h+'" fill="'+(COR[k]||"var(--s1)")+'" rx="1.5"><title>'+d.slice(8)+'/'+d.slice(5,7)+' · '+(ORIG[k]||k)+': '+(fmt?fmt(v):num(v))+'</title></rect>'}
  if(lista.length<=10||i%Math.ceil(lista.length/8)===0)s+='<text x="'+(pl+i*bw+bw/2)+'" y="'+(H-5)+'" font-size="10" text-anchor="middle" fill="var(--mut)">'+d.slice(8)+'/'+d.slice(5,7)+'</text>'});
 el.innerHTML=s+'</svg>';
}
function legenda(el,ks){el.innerHTML=ks.map(k=>'<span><i style="background:'+(COR[k]||"var(--s1)")+'"></i>'+(ORIG[k]||k)+'</span>').join("")}
function render(){
 const L=diasLista(dias),Lant=diasLista(dias*2).slice(0,dias);
 const vend=D.vendas.filter(v=>L.includes(v.dia)),vendA=D.vendas.filter(v=>Lant.includes(v.dia));
 const com=vend.reduce((a,v)=>a+v.comissao,0),comA=vendA.reduce((a,v)=>a+v.comissao,0);
 const ped=vend.reduce((a,v)=>a+v.pedidos,0);
 const vis=soma("visita",L),cli=soma("clique",L),men=soma("mencao",L),res=soma("resultado",L);
 const cliA=soma("clique",Lant),visA=soma("visita",Lant);
 const var_=(a,b)=>b?((a-b)/b*100).toFixed(0)+"% vs período anterior":"";
 document.getElementById("kpis").innerHTML=[
  ["Comissão",brl(com),var_(com,comA)],["Pedidos",num(ped),ped&&cli?(ped/cli*100).toFixed(1)+"% dos cliques":""],
  ["Cliques p/ Shopee",num(cli),var_(cli,cliA)],["Visitas",num(vis),var_(vis,visA)],
  ["Usos no ChatGPT",num(men),num(res)+" produtos mostrados"],["Cliques vindos do ChatGPT",num(soma("clique",L,"chatgpt")),""]
 ].map(([r,v,d])=>'<div class="k"><div class="r">'+r+'</div><div class="v">'+v+'</div><div class="d">'+d+'</div></div>').join("");
 document.getElementById("funil").innerHTML=[["Visitas + usos no ChatGPT",vis+men],["Cliques p/ Shopee",cli],["Pedidos",ped],["Comissão",brl(com)]]
  .map(([t,v])=>'<div><b>'+(typeof v==="number"?num(v):v)+'</b><span>'+t+'</span></div>').join("");
 const sv=serie("visita",L);legenda(document.getElementById("lv"),Object.keys(sv));barras(document.getElementById("gv"),L,sv);
 const sc=serie("clique",L);legenda(document.getElementById("lc"),Object.keys(sc));barras(document.getElementById("gc"),L,sc);
 barras(document.getElementById("gm"),L,{chatgpt:Object.fromEntries(L.map(d=>[d,soma("mencao",[d])]))});
 barras(document.getElementById("gr"),L,{site:Object.fromEntries(D.vendas.map(v=>[v.dia,v.comissao]))},v=>Math.round(v));
 const ag={};for(const t of D.topCliques){(ag[t.item]??={item:t.item,n:0,o:{}});ag[t.item].n+=t.n;ag[t.item].o[t.origem]=(ag[t.item].o[t.origem]||0)+t.n}
 const tc=Object.values(ag).sort((a,b)=>b.n-a.n).slice(0,12);
 document.getElementById("tc").innerHTML=tc.length?'<table><tr><th>Produto</th><th>Origem</th><th class="n">Cliques</th></tr>'+tc.map(t=>{const p=D.nomes[t.item];
  return '<tr><td>'+(p?'<a href="https://www.compramaisbarato.com.br/p/'+esc(p.slug)+'/" target="_blank">'+esc(p.nome.slice(0,60))+'</a>':esc(t.item))+'</td><td>'+Object.entries(t.o).map(([k,v])=>(ORIG[k]||k)+' '+v).join(", ")+'</td><td class="n">'+num(t.n)+'</td></tr>'}).join("")+'</table>':'<div class="vazio">Ainda sem cliques.</div>';
 document.getElementById("tv").innerHTML=D.topVendas.length?'<table><tr><th>Produto</th><th class="n">Qtd</th><th class="n">Comissão</th></tr>'+D.topVendas.map(t=>'<tr><td>'+esc(t.nome.slice(0,60))+'<br><span style="color:var(--mut);font-size:12px">'+esc(t.nicho)+'</span></td><td class="n">'+num(t.qtd)+'</td><td class="n">'+brl(t.comissao)+'</td></tr>').join("")+'</table>':'<div class="vazio">Ainda sem vendas registradas.</div>';
 const ov=Object.entries(sv).map(([k,o])=>[k,Object.values(o).reduce((a,b)=>a+b,0)]).sort((a,b)=>b[1]-a[1]);
 document.getElementById("ov").innerHTML=ov.length?'<table>'+ov.map(([k,n])=>'<tr><td><i style="display:inline-block;width:10px;height:10px;border-radius:2px;background:'+(COR[k]||"var(--s1)")+';margin-right:6px"></i>'+(ORIG[k]||k)+'</td><td class="n">'+num(n)+'</td><td class="n">'+(vis?(n/vis*100).toFixed(0):0)+'%</td></tr>').join("")+'</table>':'<div class="vazio">Ainda sem visitas registradas.</div>';
}
document.getElementById("per").onclick=e=>{const b=e.target.closest("button");if(!b)return;dias=+b.dataset.d;for(const x of document.querySelectorAll("#per button"))x.classList.toggle("on",x===b);render()};
fetch("/painel/dados",{credentials:"same-origin"}).then(r=>r.json()).then(j=>{D=j;
 const u=D.vendas.length?D.vendas[D.vendas.length-1].atualizado:"";
 document.getElementById("sub").textContent="Atualizado "+new Date(D.gerado_em).toLocaleString("pt-BR")+(u?" · vendas até "+u.replace("T"," "):"");render()})
 .catch(()=>{document.getElementById("sub").textContent="Não consegui carregar os dados."});
</script></body></html>`;
