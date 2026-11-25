-- Contadores agregados por dia. Não guarda nada que identifique pessoas.
CREATE TABLE IF NOT EXISTS eventos (
  dia TEXT NOT NULL,        -- AAAA-MM-DD (UTC)
  tipo TEXT NOT NULL,       -- mencao (o ChatGPT usou o app) | resultado (produto mostrado) | clique (foi pra loja)
  origem TEXT NOT NULL,     -- chatgpt | site | telegram | outro
  item TEXT NOT NULL,       -- id do produto, nicho ou ferramenta
  n INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (dia, tipo, origem, item)
);

-- Vendas da Shopee por dia (gravado pelo robô, agents/vendas.py)
CREATE TABLE IF NOT EXISTS vendas (dia TEXT PRIMARY KEY, pedidos INTEGER, itens INTEGER, comissao REAL, valor REAL, atualizado TEXT);
CREATE TABLE IF NOT EXISTS vendas_itens (dia TEXT, item TEXT, nome TEXT, nicho TEXT, qtd INTEGER, comissao REAL, PRIMARY KEY (dia, item));
