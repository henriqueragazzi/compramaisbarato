"""Cliente da API oficial de afiliados da Shopee Brasil (GraphQL).

Credenciais: painel affiliate.shopee.com.br > Open API > App ID e Secret.
Defina as variáveis de ambiente SHOPEE_APP_ID e SHOPEE_SECRET.
"""
import hashlib
import json
import os
import time

import requests

ENDPOINT = "https://open-api.affiliate.shopee.com.br/graphql"

# sortType: 1=relevância, 2=mais vendidos, 3=maior preço, 4=menor preço, 5=maior comissão
CAMPOS_PRODUTO = """
  itemId productName shopName shopId
  price priceMin priceMax priceDiscountRate
  sales ratingStar commissionRate commission
  imageUrl productLink offerLink
"""


class ShopeeAPIError(RuntimeError):
    pass


class Shopee:
    def __init__(self, app_id=None, secret=None):
        import re
        bruto_id = app_id or os.environ.get("SHOPEE_APP_ID", "")
        bruto_secret = secret or os.environ.get("SHOPEE_SECRET", "")
        # tolera espaços/rótulos colados junto ("AppID: 123")
        achado = re.search(r"\d{6,}", bruto_id)
        self.app_id = achado.group(0) if achado else bruto_id.strip()
        partes = re.findall(r"[A-Za-z0-9]{16,}", bruto_secret)
        self.secret = max(partes, key=len) if partes else bruto_secret.strip()
        if not self.app_id or not self.secret:
            raise ShopeeAPIError("Defina SHOPEE_APP_ID e SHOPEE_SECRET (painel de afiliados > Open API).")

    def _post(self, query, variables=None, tentativas=3):
        corpo = json.dumps({"query": query, "variables": variables or {}}, separators=(",", ":"), ensure_ascii=False)
        for i in range(tentativas):
            ts = int(time.time())
            # Assinatura = SHA256(AppId + Timestamp + Payload + Secret) — o payload assinado
            # tem que ser byte a byte igual ao enviado, por isso serializamos uma vez só.
            assinatura = hashlib.sha256(f"{self.app_id}{ts}{corpo}{self.secret}".encode("utf-8")).hexdigest()
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"SHA256 Credential={self.app_id}, Timestamp={ts}, Signature={assinatura}",
            }
            r = requests.post(ENDPOINT, data=corpo.encode("utf-8"), headers=headers, timeout=30)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(2 ** i * 3)
                continue
            dados = r.json()
            if dados.get("errors"):
                msg = json.dumps(dados["errors"], ensure_ascii=False)
                if "rate" in msg.lower() and i < tentativas - 1:
                    time.sleep(2 ** i * 5)
                    continue
                raise ShopeeAPIError(msg)
            return dados["data"]
        raise ShopeeAPIError(f"Falhou após {tentativas} tentativas (HTTP {r.status_code})")

    def buscar_produtos(self, palavra, ordem=2, pagina=1, limite=50):
        q = f"""query($kw:String,$sort:Int,$page:Int,$limit:Int){{
          productOfferV2(keyword:$kw, sortType:$sort, page:$page, limit:$limit){{
            nodes {{ {CAMPOS_PRODUTO} }}
            pageInfo {{ page limit hasNextPage }}
          }}
        }}"""
        d = self._post(q, {"kw": palavra, "sort": ordem, "page": pagina, "limit": limite})
        return d["productOfferV2"]["nodes"], d["productOfferV2"]["pageInfo"]["hasNextPage"]

    def produto_por_id(self, item_id, shop_id):
        q = f"""query($item:Int64,$shop:Int64){{
          productOfferV2(itemId:$item, shopId:$shop){{ nodes {{ {CAMPOS_PRODUTO} }} }}
        }}"""
        nodes = self._post(q, {"item": int(item_id), "shop": int(shop_id)})["productOfferV2"]["nodes"]
        return nodes[0] if nodes else None

    def link_curto(self, url, sub_ids=None):
        q = """mutation($url:String!,$subs:[String]){
          generateShortLink(input:{originUrl:$url, subIds:$subs}){ shortLink }
        }"""
        return self._post(q, {"url": url, "subs": sub_ids or ["site"]})["generateShortLink"]["shortLink"]

    def relatorio_conversoes(self, inicio_ts, fim_ts, scroll_id=""):
        q = """query($s:Int64,$e:Int64,$scroll:String){
          conversionReport(purchaseTimeStart:$s, purchaseTimeEnd:$e, scrollId:$scroll, limit:500){
            nodes { purchaseTime checkoutId estimatedTotalCommission
                    orders { items { itemId itemName itemPrice qty itemTotalCommission } } }
            pageInfo { scrollId hasNextPage }
          }
        }"""
        return self._post(q, {"s": int(inicio_ts), "e": int(fim_ts), "scroll": scroll_id})["conversionReport"]
