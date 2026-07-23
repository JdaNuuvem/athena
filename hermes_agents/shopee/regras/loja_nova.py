"""
Strategy: Loja Nova — aplica se a loja foi criada ha menos de N dias.
"""
from datetime import date
from typing import Optional, Dict, Any
from .base import RegraPrecoStrategy

class LojaNovaStrategy(RegraPrecoStrategy):
    async def aplicar(self, sku: str, loja_id: Optional[int], db) -> Optional[Dict[str, Any]]:
        dias_ativo = self.regra.get("dias_ativo")
        if not dias_ativo or not loja_id:
            return None
        loja_criada = await db.fetchval("SELECT created_at FROM lojas WHERE id = $1", loja_id)
        if loja_criada and (date.today() - loja_criada.date()).days <= dias_ativo:
            return self._desconto() or self._markup()
        return None
