"""
Strategy: Manual — sempre ativa se datas batem.
"""
from typing import Optional, Dict, Any
from .base import RegraPrecoStrategy

class ManualStrategy(RegraPrecoStrategy):
    def aplicar(self, sku: str, loja_id: Optional[int], db) -> Optional[Dict[str, Any]]:
        return self._desconto() or self._markup()
