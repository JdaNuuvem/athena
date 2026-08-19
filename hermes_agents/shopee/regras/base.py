"""
Strategy Pattern — interface para regras de preco.
SOLID: OCP — nova regra = nova classe, sem modificar codigo existente.
"""
from abc import ABC, abstractmethod
from datetime import date
from typing import Optional, Dict, Any


class RegraPrecoStrategy(ABC):
    """Estrategia que avalia se uma regra se aplica a um produto e calcula o ajuste."""

    def __init__(self, regra: Dict[str, Any]):
        self.regra = regra
        self.nome = regra.get("nome", "")
        self.prioridade = regra.get("prioridade", 0)

    @abstractmethod
    async def aplicar(self, sku: str, loja_id: Optional[int], db) -> Optional[Dict[str, Any]]:
        """Retorna {'tipo': 'desconto'|'markup', 'ajuste_pct': float, 'nome': str} ou None se nao se aplica.

        async porque core/automacoes.py::aplicar_regras_preco() sempre faz
        `await strategy.aplicar(...)` — uma implementacao sincrona (`def`)
        estoura TypeError na hora do await, engolido pelo except generico da
        chamadora (achado real: manual.py e sazonal.py tinham `def` e as
        regras Manual/Sazonal nunca aplicavam nada, silenciosamente)."""

    def _desconto(self) -> Optional[Dict[str, Any]]:
        pct = self.regra.get("desconto_pct", 0)
        if pct:
            return {"tipo": "desconto", "ajuste_pct": -float(pct), "nome": self.nome}
        return None

    def _markup(self) -> Optional[Dict[str, Any]]:
        pct = self.regra.get("markup_ajuste_pct", 0)
        if pct:
            return {"tipo": "markup", "ajuste_pct": float(pct), "nome": self.nome}
        return None
