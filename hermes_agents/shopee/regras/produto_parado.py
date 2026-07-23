"""
Strategy: Produto Parado — aplica se o SKU nao tem venda nos ultimos N dias.
"""
from datetime import date
from typing import Optional, Dict, Any
from .base import RegraPrecoStrategy

class ProdutoParadoStrategy(RegraPrecoStrategy):
    async def aplicar(self, sku: str, loja_id: Optional[int], db) -> Optional[Dict[str, Any]]:
        dias = self.regra.get("condicao_estoque_dias")
        if not dias or not sku:
            return None
        ultima = await db.fetchval("""
            SELECT MAX(v.data) FROM vendas_pedidos v
            JOIN vendas_itens i ON i.pedido_id = v.id
            WHERE i.sku = $1 AND v.status != 'cancelado'
        """, sku)
        if ultima:
            parado_desde = ultima
        else:
            # Nunca vendeu — considera parado desde o cadastro no catalogo (o caso mais
            # "parado" possivel; antes esse produto nunca era pego por essa regra).
            parado_desde = await db.fetchval(
                "SELECT created_at::date FROM catalogo_produtos WHERE sku = $1", sku)
        if parado_desde and (date.today() - parado_desde).days >= dias:
            return self._desconto() or self._markup()
        return None
