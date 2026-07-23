"""
Strategy: Sazonal — aplica se data atual esta entre data_inicio e data_fim.
"""
from datetime import date
from typing import Optional, Dict, Any
from .base import RegraPrecoStrategy

class SazonalStrategy(RegraPrecoStrategy):
    def aplicar(self, sku: str, loja_id: Optional[int], db) -> Optional[Dict[str, Any]]:
        hoje = date.today()
        ini = self.regra.get("data_inicio")
        fim = self.regra.get("data_fim")
        if ini and fim and ini <= hoje <= fim:
            return self._desconto() or self._markup()
        return None
