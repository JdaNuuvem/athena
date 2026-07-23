"""
Repository Pattern — interfaces abstratas para acesso a dados.
SOLID: DIP — modulos de negocio dependem destas interfaces, nao do Postgres diretamente.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


# ═══ Data Classes ═══

@dataclass
class Produto:
    sku: str
    descricao: str = ""
    preco_custo: float = 0.0
    grupo: str = ""
    situacao: str = "A"

@dataclass
class Loja:
    id: int
    nome: str
    ativa: bool = True
    shopee_shop_id: str = ""
    shopee_access_token: str = ""
    shopee_shop_name: str = ""
    shopee_markup_pct: float = 100.0
    grupos_publicacao: str = ""
    shopee_token_expira_em: Optional[datetime] = None

@dataclass
class AnuncioConcorrente:
    sku: str
    marketplace: str
    preco: float

@dataclass
class ParVendas:
    sku_a: str
    sku_b: str
    qtd_juntos: int


# ═══ Abstract Repositories ═══

class ProdutoRepository(ABC):
    """Acesso a dados de produtos do catalogo."""

    @abstractmethod
    async def buscar_custo(self, sku: str) -> float:
        """Retorna o preco_custo do produto. 0 se nao encontrado."""

    @abstractmethod
    async def buscar_grupo(self, sku: str) -> str:
        """Retorna o grupo do produto. Vazio se nao definido."""

    @abstractmethod
    async def buscar_por_sku(self, sku: str) -> Optional[Produto]:
        """Retorna o produto completo ou None."""


class LojaRepository(ABC):
    """Acesso a dados de lojas."""

    @abstractmethod
    async def listar_lojas_shopee(self) -> List[Loja]:
        """Retorna lojas com token Shopee valido e ativas."""

    @abstractmethod
    async def buscar_por_id(self, loja_id: int) -> Optional[Loja]:
        """Retorna loja pelo ID."""

    @abstractmethod
    async def buscar_markup(self, loja_id: int) -> float:
        """Retorna shopee_markup_pct da loja. Default 100."""

    @abstractmethod
    async def buscar_grupos_publicacao(self, loja_id: int) -> set:
        """Retorna set de grupos de publicacao da loja."""


class ConcorrenciaRepository(ABC):
    """Acesso a dados de anuncios concorrentes."""

    @abstractmethod
    async def listar_anuncios(self, sku: str, marketplace: str = "shopee") -> List[AnuncioConcorrente]:
        """Retorna anuncios concorrentes para um SKU."""


class VendasRepository(ABC):
    """Acesso a dados de vendas para analise."""

    @abstractmethod
    async def buscar_pares_comprados_juntos(self, dias: int, min_ocorrencias: int) -> List[ParVendas]:
        """Retorna pares de SKUs comprados no mesmo pedido."""

    @abstractmethod
    async def buscar_nome_produto(self, sku: str) -> str:
        """Retorna descricao do produto ou o proprio SKU."""

    @abstractmethod
    async def contar_vendas_sku(self, sku: str, dias: int) -> int:
        """Conta pedidos que contem o SKU no periodo."""


@dataclass
class EstoqueLoja:
    sku: str
    loja: str
    quantidade: int
    nome_produto: str = ""

class EstoqueRepository(ABC):
    """Acesso a dados de estoque por loja."""

    @abstractmethod
    async def listar_estoque_por_loja(self) -> List[EstoqueLoja]:
        """Retorna todo o estoque agrupado por SKU e loja."""

    @abstractmethod
    async def buscar_quantidade(self, sku: str, loja: str) -> int:
        """Retorna quantidade em estoque para um SKU em uma loja."""

    @abstractmethod
    async def listar_lojas_com_estoque(self) -> List[str]:
        """Retorna nomes unicos de lojas que tem estoque."""


@dataclass
class ReceitaLoja:
    loja_id: int
    loja_nome: str
    receita_online: float = 0.0
    receita_pdv: float = 0.0
    frete: float = 0.0
    custos_producao: float = 0.0
    qtd_vendas: int = 0

class FinanceiroRepository(ABC):
    """Acesso a dados financeiros agregados por loja."""

    @abstractmethod
    async def listar_receita_por_loja(self, dias: int) -> List[ReceitaLoja]:
        """Retorna receita, frete, custos por loja no periodo."""

    @abstractmethod
    async def listar_lojas_ativas(self) -> List[Loja]:
        """Retorna lojas ativas do cadastro."""
