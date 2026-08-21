"""_upsert_nota_fiscal identificava a nota existente SO' por bling_id.

NF-e, NFC-e e NFS-e sao recursos distintos na API Bling (/nfe/{id},
/nfce/{id}, /nfse/{id}) com sequencias de id INDEPENDENTES — id 1234 existe
nos tres. Sem tipo_documento na chave, o sync de NFC-e encontrava a NF-e de
mesmo bling_id, caia no ramo UPDATE e sobrescrevia numero, chave de acesso e
todos os valores de imposto, remarcando a nota como tipo_documento='nfce'.
O DELETE FROM fiscal_nfe_itens na sequencia apagava os itens da nota
original. Perda silenciosa de dado fiscal.

Mesmo defeito na dimensao ambiente (fase 5): sincronizar em homologacao
sobrescrevia o registro de producao e o remarcava como 'homologacao',
sumindo das telas que filtram ambiente='producao'.
"""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock

async def _mp(*a, **kw):
    m = AsyncMock()
    m.acquire.return_value = AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(
        fetch=AsyncMock(return_value=[]), fetchrow=AsyncMock(return_value=None),
        fetchval=AsyncMock(return_value=0), execute=AsyncMock(return_value="OK"))),
        __aexit__=AsyncMock(return_value=None))
    return m

_patcher = patch("asyncpg.create_pool", side_effect=_mp)
_patcher.start()

import core.fiscal as core_fiscal
from core import run_async


class _FakeDBNotasIndexadas:
    """Fake que simula o comportamento REAL do Postgres: o SELECT so' filtra
    pelas colunas que a query menciona. Com a query antiga (so' bling_id) ele
    devolve a nota de outro tipo/ambiente — reproduzindo a colisao."""

    def __init__(self, registros):
        # registros: dicts com bling_id, tipo_documento, ambiente, id
        self.registros = registros
        self.executed = []
        self.fetchvals = []

    async def fetchval(self, q, *a):
        self.fetchvals.append((q, a))
        if "SELECT id FROM fiscal_notas_fiscais" in q:
            for reg in self.registros:
                if reg["bling_id"] != a[0]:
                    continue
                if "tipo_documento" in q and reg["tipo_documento"] != a[1]:
                    continue
                if "ambiente" in q and reg["ambiente"] != a[2]:
                    continue
                return reg["id"]
            return None
        if "INSERT INTO fiscal_notas_fiscais" in q:
            return 99
        return 1

    async def fetchrow(self, q, *a):
        return None

    async def fetch(self, q, *a):
        return []

    async def execute(self, q, *a):
        self.executed.append((q, a))

    def houve_update(self):
        return any("UPDATE fiscal_notas_fiscais" in q for q, _ in self.executed)

    def houve_insert(self):
        return any("INSERT INTO fiscal_notas_fiscais" in q for q, _ in self.fetchvals)


_DETALHE = {
    "numero": "5001", "chaveAcesso": "CHAVE-NFCE", "dataEmissao": "2026-08-21",
    "contato": {}, "naturezaOperacao": {}, "tributos": {}, "itens": [],
}


class TestColisaoEntreTiposDeDocumento(unittest.TestCase):
    def test_nfce_com_mesmo_bling_id_de_nfe_nao_sobrescreve_a_nfe(self):
        db = _FakeDBNotasIndexadas([
            {"bling_id": 1234, "tipo_documento": "nfe", "ambiente": "producao", "id": 55},
        ])
        run_async(core_fiscal._upsert_nota_fiscal(
            db, 1234, _DETALHE, tipo_documento="nfce", ambiente="producao"))
        self.assertFalse(db.houve_update(), "NFC-e sobrescreveu a NF-e de mesmo bling_id")
        self.assertTrue(db.houve_insert(), "NFC-e deveria ter sido inserida como nota nova")

    def test_nfse_com_mesmo_bling_id_de_nfce_nao_sobrescreve(self):
        db = _FakeDBNotasIndexadas([
            {"bling_id": 777, "tipo_documento": "nfce", "ambiente": "producao", "id": 60},
        ])
        run_async(core_fiscal._upsert_nota_fiscal(
            db, 777, _DETALHE, tipo_documento="nfse", ambiente="producao"))
        self.assertFalse(db.houve_update())
        self.assertTrue(db.houve_insert())


class TestColisaoEntreAmbientes(unittest.TestCase):
    def test_homologacao_nao_sobrescreve_nota_de_producao(self):
        db = _FakeDBNotasIndexadas([
            {"bling_id": 900, "tipo_documento": "nfe", "ambiente": "producao", "id": 70},
        ])
        run_async(core_fiscal._upsert_nota_fiscal(
            db, 900, _DETALHE, tipo_documento="nfe", ambiente="homologacao"))
        self.assertFalse(db.houve_update(), "sync de homologacao sobrescreveu dado de producao")
        self.assertTrue(db.houve_insert())


class TestUpsertLegitimoContinuaAtualizando(unittest.TestCase):
    """A correcao nao pode transformar todo upsert em insert — quando
    bling_id, tipo_documento e ambiente batem, tem que atualizar a propria
    nota (e mirar a linha certa no UPDATE)."""

    def test_mesma_nota_e_atualizada_no_lugar(self):
        db = _FakeDBNotasIndexadas([
            {"bling_id": 1234, "tipo_documento": "nfce", "ambiente": "producao", "id": 55},
        ])
        run_async(core_fiscal._upsert_nota_fiscal(
            db, 1234, _DETALHE, tipo_documento="nfce", ambiente="producao"))
        self.assertTrue(db.houve_update(), "nota existente do mesmo tipo/ambiente nao foi atualizada")
        self.assertFalse(db.houve_insert())

    def test_update_mira_a_linha_exata_e_nao_todas_com_o_mesmo_bling_id(self):
        """WHERE bling_id=$N atingiria TODAS as linhas com aquele bling_id —
        inclusive as de outro tipo/ambiente. Tem que mirar o id da linha."""
        db = _FakeDBNotasIndexadas([
            {"bling_id": 1234, "tipo_documento": "nfce", "ambiente": "producao", "id": 55},
        ])
        run_async(core_fiscal._upsert_nota_fiscal(
            db, 1234, _DETALHE, tipo_documento="nfce", ambiente="producao"))
        q, args = next((q, a) for q, a in db.executed if "UPDATE fiscal_notas_fiscais" in q)
        self.assertIn("WHERE id=", " ".join(q.split()))
        self.assertEqual(args[-1], 55, "UPDATE deveria mirar o id da linha encontrada")


if __name__ == "__main__":
    unittest.main(verbosity=2)
