"""
Shopee Regras de Preco — Strategy Pattern registry.
SOLID: OCP — para adicionar novo tipo de regra, registre aqui.
"""
from typing import Dict, Type
from .base import RegraPrecoStrategy
from .manual import ManualStrategy
from .sazonal import SazonalStrategy
from .loja_nova import LojaNovaStrategy
from .produto_parado import ProdutoParadoStrategy
from .estoque_alto import EstoqueAltoStrategy

# ═══ Registry ═══
# Mapeia tipo da regra → classe Strategy
REGISTRO: Dict[str, Type[RegraPrecoStrategy]] = {
    "manual": ManualStrategy,
    "sazonal": SazonalStrategy,
    "loja_nova": LojaNovaStrategy,
    "produto_parado": ProdutoParadoStrategy,
    "estoque_alto": EstoqueAltoStrategy,
}


def criar_estrategia(tipo: str, regra: dict) -> RegraPrecoStrategy:
    """Factory: instancia a Strategy correta para o tipo de regra."""
    cls = REGISTRO.get(tipo, ManualStrategy)
    return cls(regra)


def registrar(tipo: str, cls: Type[RegraPrecoStrategy]):
    """Permite plugins registrarem novas estrategias em runtime."""
    REGISTRO[tipo] = cls
