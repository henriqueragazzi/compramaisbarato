// Vitrine exibida dentro do ChatGPT. Lê os produtos de window.openai.toolOutput (structuredContent
// da ferramenta buscar_produtos) e também aceita o padrão MCP Apps (mensagem ui/notifications/tool-result).
export const WIDGET_HTML = `<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--tx:#1d1d1f;--mut:#6b6b72;--bd:#e7e7ec;--bg:#fff;--cor:#ff5a1f}
.dark{--tx:#f2f2f3;--mut:#a3a3ab;--bd:#34343a;--bg:#1f1f23}
*{box-sizing:border-box}body{margin:0;font:14px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--tx);background:transparent}
.lista{display:flex;gap:12px;overflow-x:auto;padding:4px 2px 10px;scroll-snap-type:x mandatory}
.card{flex:0 0 200px;scroll-snap-align:start;background:var(--bg);border:1px solid var(--bd);border-radius:14px;overflow:hidden;display:flex;flex-direction:column}
.card img{width:100%;aspect-ratio:1;object-fit:cover;background:#f2f2f2}
.in{padding:10px;display:flex;flex-direction:column;gap:4px;flex:1}
.nm{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:40px}
.preco{font-weight:800;font-size:16px}.meta{font-size:12px;color:var(--mut)}
button{margin-top:auto;border:0;border-radius:10px;background:var(--cor);color:#fff;font-weight:700;padding:9px;cursor:pointer}
.rodape{font-size:11px;color:var(--mut);padding:0 2px}
.vazio{padding:12px;color:var(--mut)}
</style></head><body>
<div id="app"><div class="vazio">Carregando…</div></div>
<script>
(function(){
  var dados=null;
  function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
  function abrir(href){
    try{ if(window.openai&&window.openai.openExternal){window.openai.openExternal({href:href});return;} }catch(e){}
    try{ window.parent.postMessage({jsonrpc:'2.0',id:Date.now(),method:'ui/open-link',params:{url:href}},'*'); }catch(e){}
    window.open(href,'_blank','noopener');
  }
  function render(){
    if(window.openai&&window.openai.theme==='dark')document.documentElement.className='dark';
    var out=dados||(window.openai&&window.openai.toolOutput)||null;
    var app=document.getElementById('app');
    if(!out||!out.produtos){app.innerHTML='<div class="vazio">Carregando…</div>';return;}
    if(!out.produtos.length){app.innerHTML='<div class="vazio">Nenhum produto encontrado para essa busca.</div>';return;}
    app.innerHTML='<div class="lista">'+out.produtos.map(function(p,i){
      return '<div class="card"><img src="'+esc(p.imagem)+'" alt="'+esc(p.nome)+'" loading="lazy">'+
        '<div class="in"><div class="nm">'+esc(p.nome)+'</div><div class="preco">'+esc(p.preco_texto)+'</div>'+
        '<div class="meta">⭐ '+esc(p.nota)+' · '+Number(p.vendas).toLocaleString('pt-BR')+' vendidos</div>'+
        '<button data-i="'+i+'">Ver na Shopee</button></div></div>';
    }).join('')+'</div><div class="rodape">Preços aproximados, conferidos várias vezes ao dia. O valor final é o da Shopee. Links de afiliado · Compra Mais Barato</div>';
    Array.prototype.forEach.call(app.querySelectorAll('button'),function(b){
      b.onclick=function(){abrir(out.produtos[+b.getAttribute('data-i')].url_compra)};
    });
  }
  // Handshake do padrão MCP Apps (outros hosts); no ChatGPT, window.openai já entrega os dados.
  try{
    window.parent.postMessage({jsonrpc:'2.0',id:1,method:'ui/initialize',params:{protocolVersion:'2025-11-21',appInfo:{name:'compra-mais-barato',version:'1.0.0'},appCapabilities:{}}},'*');
  }catch(e){}
  window.addEventListener('openai:set_globals',render);
  window.addEventListener('message',function(ev){
    var m=ev.data;
    if(m&&m.id===1&&m.result){try{window.parent.postMessage({jsonrpc:'2.0',method:'ui/notifications/initialized',params:{}},'*')}catch(e){}}
    if(m&&m.method==='ui/notifications/tool-result'&&m.params&&m.params.structuredContent){dados=m.params.structuredContent;render();}
  });
  render();
})();
</script></body></html>`;
