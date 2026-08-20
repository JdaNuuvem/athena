"""Testes unitarios — Financeiro + Bling (contas pagar/receber, fluxo caixa, DRE)."""
import sys,os,unittest
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch,MagicMock,AsyncMock
async def _mp(*a,**kw):m=AsyncMock();m.acquire.return_value=AsyncMock(__aenter__=AsyncMock(return_value=AsyncMock(fetch=AsyncMock(return_value=[]),fetchrow=AsyncMock(return_value=None),fetchval=AsyncMock(return_value=0),execute=AsyncMock(return_value="OK"))),__aexit__=AsyncMock(return_value=None));return m
patcher=patch("asyncpg.create_pool",side_effect=_mp)
patcher.start()
import core.financeiro as fin

class TestFinanceiro(unittest.TestCase):
    def test_list_fluxo(self):r=fin.list("fluxo_caixa");self.assertIsInstance(r,list)
    def test_list_contas(self):r=fin.list("contas_receber");self.assertIsInstance(r,list)
    def test_fluxo_resumo(self):r=fin.fluxo_caixa_resumo();self.assertIn("resumo",r)
    def test_dre_resumo(self):r=fin.dre_resumo();self.assertIn("resultado",r)

class TestBlingFinanceiro(unittest.TestCase):
    @patch("bling_erp.get_access_token",return_value="token")
    @patch("bling_erp.requests.request")
    def test_listar_contas_pagar(self,mr,mt):
        mr.return_value.status_code=200;mr.return_value.json.return_value={"data":[]}
        import bling_erp as b
        r=b.listar_contas_pagar()
        self.assertIn("data",r)

    def test_sincronizar_plano_contas_bling_faz_upsert_por_bling_id(self):
        # coluna bling_id + indice unico parcial agora sao garantidos no boot
        # por _ensure_tables() (ver test_financeiro_ensure_tables_cria_coluna_
        # bling_id_e_indice_plano_contas abaixo) — sincronizar_plano_contas_bling
        # so' faz o upsert em si, entao so' precisa mockar o SELECT de "existing".
        fake_db = AsyncMock()
        fake_db.fetchval.side_effect = [None]  # checa conta existente
        with patch("bling_erp.get_access_token", return_value="tok"), \
             patch("core.financeiro.get_db", new=AsyncMock(return_value=fake_db)), \
             patch("bling_erp.listar_contas_contabeis", return_value={"data": [
                 {"id": 999, "descricao": "Receita de Vendas Online", "tipo": "R"},
             ]}):
            resultado = fin.sincronizar_plano_contas_bling()
        self.assertEqual(resultado["sync"], 1)
        sqls_executados = [c.args[0] for c in fake_db.execute.call_args_list]
        self.assertTrue(any("INSERT INTO fin_plano_contas" in s for s in sqls_executados))
        # migracao de coluna nunca pode apagar/truncar o seed de 11 linhas ja
        # existente em fin_plano_contas — ADD COLUMN IF NOT EXISTS e' a unica
        # operacao de schema permitida contra essa tabela no sync.
        self.assertFalse(any("DROP" in s.upper() or "TRUNCATE" in s.upper() or "DELETE FROM fin_plano_contas" in s.upper() for s in sqls_executados))

    def test_ensure_tables_cria_coluna_bling_id_e_indice_plano_contas(self):
        # Achado #1 da revisao final: GET /api/bling/plano-contas selecionava
        # a coluna bling_id sem ela nunca ter sido garantida no boot (so' era
        # criada dentro de sincronizar_plano_contas_bling(), sob demanda) —
        # em qualquer banco que ja tinha fin_plano_contas, o primeiro GET
        # antes do primeiro sync manual explodia com UndefinedColumn -> 500.
        fake_db = AsyncMock()
        fake_db.fetchval.return_value = 0
        with patch("core.financeiro.get_db", new=AsyncMock(return_value=fake_db)):
            fin._ensure_tables()
        sqls_executados = [c.args[0] for c in fake_db.execute.call_args_list]
        self.assertTrue(any(
            "ALTER TABLE fin_plano_contas ADD COLUMN IF NOT EXISTS bling_id" in s
            for s in sqls_executados))
        self.assertTrue(any(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_fin_plano_contas_bling_id" in s
            and "fin_plano_contas(bling_id) WHERE bling_id IS NOT NULL" in s
            for s in sqls_executados))

if __name__=="__main__":unittest.main(verbosity=2)
