"""
Strategy: Estoque Alto — aplica se o SKU tem estoque parado ha N dias.
"""
from datetime import date
from typing import Optional, Dict, Any
from .base import RegraPrecoStrategy

class EstoqueAltoStrategy(RegraPrecoStrategy):
    async def aplicar(self, sku: str, loja_id: Optional[int], db) -> Optional[Dict[str, Any]]:
        dias = self.regra.get("condicao_estoque_dias")
        if not dias or not sku:
            return None
        qtd = await db.fetchval("SELECT SUM(quantidade) FROM estoque_lojas WHERE sku = $1", sku)
        if not qtd or float(qtd) <= 0:
            return None
        ult_mov = await db.fetchval("SELECT MAX(data) FROM estoque_movimentacoes WHERE sku = $1", sku)
        if ult_mov and (date.today() - ult_mov).days >= dias:
            return self._desconto() or self._markup()
        return None
