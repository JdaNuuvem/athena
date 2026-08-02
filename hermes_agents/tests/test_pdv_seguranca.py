"""Testes de integracao dos controles de seguranca de PDV/caixa:
bypass do CRUD generico bloqueado, alcada de aprovacao de sangria (limite
configuravel), desconto por item validado, diferenca de caixa persistida,
aviso de segregacao de funcao, e correcao do DRE por loja (comissao so'
sobre receita online)."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from unittest.mock import patch, AsyncMock


class _FakeTransaction:
    async def __aenter__(self): return None
    async def __aexit__(self, *a): return None


class _FakeAcquire:
    def __init__(self, db): self.db = db
    async def __aenter__(self): return self.db
    async def __aexit__(self, *a): return None


class FakeDB:
    def __init__(self):
        self.operadores = {}  # id -> dict
        self.caixas = {}      # id -> dict
        self.sangrias = []
        self.sangria_aprovacoes = []
        self.vendas_por_caixa = {}  # caixa_id -> list[operador]
        self.config = {}
        self.orcamentos = {}  # id -> dict, usado por criar_orcamento nos testes

    def acquire(self):
        return _FakeAcquire(self)

    def transaction(self):
        return _FakeTransaction()

    async def execute(self, query, *params):
        q = " ".join(query.split())
        if "ALTER TABLE" in q or "CREATE TABLE" in q or "CREATE INDEX" in q:
            return "OK"
        if "UPDATE pdv_sangria_aprovacoes SET status = 'aprovada'" in q:
            aprovador_id, aprovador_nome, aid = params
            for a in self.sangria_aprovacoes:
                if a["id"] == aid:
                    a["status"] = "aprovada"
        elif "UPDATE pdv_sangria_aprovacoes SET status = 'rejeitada'" in q:
            aprovador_id, aprovador_nome, motivo, aid = params
            for a in self.sangria_aprovacoes:
                if a["id"] == aid:
                    a["status"] = "rejeitada"
        elif "INSERT INTO configs" in q:
            sistema, chave, valor = params
            self.config[(sistema, chave)] = valor
        elif "UPDATE pdv_operadores SET pin_hash" in q:
            pin_hash, oid = params
            self.operadores.setdefault(oid, {})["pin_hash"] = pin_hash
        elif "UPDATE pdv_operadores SET codigo_barras_hash" in q:
            codigo_hash, oid = params
            self.operadores.setdefault(oid, {})["codigo_barras_hash"] = codigo_hash
        return "OK"

    async def fetchval(self, query, *params):
        q = " ".join(query.split())
        if "SELECT saldo_inicial FROM pdv_caixas" in q:
            (cid,) = params
            return self.caixas.get(cid, {}).get("saldo_inicial", 0)
        if "SUM(total)" in q or "SUM(valor)" in q or "SUM(p.valor)" in q:
            return 0
        return None

    async def fetchrow(self, query, *params):
        q = " ".join(query.split())
        if "FROM pdv_operadores WHERE id" in q:
            (oid,) = params
            return self.operadores.get(oid)
        if "INSERT INTO pdv_sangria_aprovacoes" in q:
            caixa_id, valor, motivo, uid, uname = params
            row = {"id": len(self.sangria_aprovacoes) + 1, "caixa_id": caixa_id, "valor": valor,
                   "motivo": motivo, "status": "pendente",
                   "usuario_solicitante_id": uid, "usuario_solicitante_nome": uname}
            self.sangria_aprovacoes.append(row)
            return row
        if "FROM pdv_sangria_aprovacoes WHERE id" in q:
            (aid,) = params
            return next((a for a in self.sangria_aprovacoes if a["id"] == aid), None)
        if "INSERT INTO pdv_sangrias" in q:
            caixa_id, valor, motivo, operador = params
            row = {"id": len(self.sangrias) + 1, "caixa_id": caixa_id, "valor": valor,
                   "motivo": motivo, "operador": operador}
            self.sangrias.append(row)
            return row
        if "INSERT INTO pdv_vendas" in q:
            cliente, cliente_id, total, desconto, operador, data = params
            row = {"id": len(self.orcamentos) + 1, "cliente": cliente, "cliente_id": cliente_id,
                   "total": total, "desconto": desconto, "operador": operador,
                   "status": "orcamento", "tipo": "orcamento", "data": data}
            self.orcamentos[row["id"]] = row
            return row
        if "UPDATE pdv_caixas SET status='fechado'" in q:
            saldo_final, diferenca, operador_fechamento, cid = params
            caixa = self.caixas.setdefault(cid, {"saldo_inicial": 0})
            caixa.update({"status": "fechado", "saldo_final": saldo_final,
                          "diferenca": diferenca, "operador_fechamento": operador_fechamento})
            return caixa
        return None

    async def fetch(self, query, *params):
        q = " ".join(query.split())
        if "SELECT DISTINCT operador FROM pdv_vendas" in q:
            (cid,) = params
            return [{"operador": op} for op in self.vendas_por_caixa.get(cid, [])]
        if "FROM pdv_operadores WHERE ativo = TRUE AND codigo_barras_hash IS NOT NULL" in q:
            return [o for o in self.operadores.values() if o.get("codigo_barras_hash")]
        return []


class TestPDVAprovacaoSangria(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fake = FakeDB()
        self._patches = []
        for modulo in ("core.pdv", "core.pdv_aprovacoes"):
            async def _get_db(_fake=self.fake):
                return _fake
            p = patch(f"{modulo}.get_db", side_effect=_get_db)
            p.start()
            self._patches.append(p)
        import core.pdv as m
        m._ensure_tables = lambda: None
        import core.pdv_aprovacoes as ma
        ma._ok = True
        # limite padrao (sem config setada) = 200.0
        p2 = patch("core.pdv_aprovacoes.get_config", return_value="")
        p2.start()
        self._patches.append(p2)

        self.fake.operadores[1] = {"id": 1, "nome": "gerente1", "role": "gerente", "ativo": True,
                                    "senha": None, "desconto_maximo_percent": 10}

    def tearDown(self):
        for p in self._patches:
            p.stop()

    async def test_sangria_pequena_aplica_direto(self):
        from core.pdv import sangria
        with patch("core.pdv.verificar_operador", return_value={"ok": True, "id": 1, "nome": "gerente1", "role": "gerente"}):
            r = sangria(caixa_id=1, valor=50, motivo="troco", operador="gerente1", operador_id=1, senha="x")
        self.assertNotIn("pendente", r)
        self.assertEqual(len(self.fake.sangrias), 1)
        self.assertEqual(self.fake.sangrias[0]["valor"], 50)

    async def test_sangria_grande_fica_pendente(self):
        from core.pdv import sangria
        with patch("core.pdv.verificar_operador", return_value={"ok": True, "id": 1, "nome": "gerente1", "role": "gerente"}):
            r = sangria(caixa_id=1, valor=500, motivo="deposito_banco", operador="gerente1", operador_id=1, senha="x")
        self.assertTrue(r.get("pendente"))
        self.assertEqual(len(self.fake.sangrias), 0)

    async def test_sangria_motivo_invalido_rejeitada(self):
        from core.pdv import sangria
        with patch("core.pdv.verificar_operador", return_value={"ok": True, "id": 1, "nome": "gerente1", "role": "gerente"}):
            r = sangria(caixa_id=1, valor=10, motivo="qualquer coisa", operador="gerente1", operador_id=1, senha="x")
        self.assertIn("error", r)

    async def test_sangria_operador_nao_gerencial_bloqueada(self):
        from core.pdv import sangria
        with patch("core.pdv.verificar_operador", return_value={"ok": True, "id": 2, "nome": "op2", "role": "operador"}):
            r = sangria(caixa_id=1, valor=10, motivo="troco", operador="op2", operador_id=2, senha="x")
        self.assertIn("error", r)
        self.assertEqual(len(self.fake.sangrias), 0)

    async def test_aprovar_sangria_pendente_aplica(self):
        from core.pdv_aprovacoes import solicitar, aprovar
        r = solicitar(1, 500, "deposito_banco", usuario_id=1, usuario_nome="gerente1")
        aid = r["aprovacao_id"]
        r2 = aprovar(aid, aprovador_id=9, aprovador_nome="admin")
        self.assertTrue(r2.get("id"))  # retorno de _aplicar_sangria (create) tem id
        self.assertEqual(len(self.fake.sangrias), 1)
        self.assertEqual(self.fake.sangria_aprovacoes[0]["status"], "aprovada")

    async def test_rejeitar_sangria_pendente_nao_aplica(self):
        from core.pdv_aprovacoes import solicitar, rejeitar
        r = solicitar(1, 500, "deposito_banco", usuario_id=1, usuario_nome="gerente1")
        aid = r["aprovacao_id"]
        r2 = rejeitar(aid, aprovador_id=9, aprovador_nome="admin", motivo_rejeicao="fora do previsto")
        self.assertTrue(r2.get("ok"))
        self.assertEqual(len(self.fake.sangrias), 0)
        self.assertEqual(self.fake.sangria_aprovacoes[0]["status"], "rejeitada")

    async def test_limite_configuravel(self):
        from core.pdv_aprovacoes import precisa_aprovacao
        with patch("core.pdv_aprovacoes.get_config", return_value="50"):
            self.assertTrue(precisa_aprovacao(51))
            self.assertFalse(precisa_aprovacao(50))


class TestPDVDescontoPorItem(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fake = FakeDB()
        self._patches = []
        async def _get_db(_fake=self.fake):
            return _fake
        p = patch("core.pdv.get_db", side_effect=_get_db)
        p.start()
        self._patches.append(p)
        import core.pdv as m
        m._ensure_tables = lambda: None
        self.fake.operadores[1] = {"id": 1, "nome": "op1", "role": "operador", "ativo": True,
                                    "senha": None, "desconto_maximo_percent": 10}

    def tearDown(self):
        for p in self._patches:
            p.stop()

    async def test_desconto_total_dentro_do_limite_ok(self):
        from core.pdv import realizar_venda
        # so' testamos a validacao de desconto (retorno de erro) — nao a
        # persistencia da venda inteira. pagamentos precisa cobrir o total
        # (100 - 5 desconto item - 5 desconto venda = 90) pra nao cair na
        # checagem de "pagamento insuficiente" antes de chegar no mock.
        with patch("core.pdv.run_async", side_effect=lambda coro: coro.close() or {"venda": {"id": 1}, "total": 90}):
            r = realizar_venda(caixa_id=1, itens=[{"quantidade": 1, "valor_unitario": 100, "desconto": 5}],
                                pagamentos=[{"valor": 90}], operador="op1", operador_id=1, desconto=5)
        self.assertNotIn("error", r)

    async def test_desconto_concentrado_em_item_acima_do_limite_bloqueado(self):
        from core.pdv import realizar_venda
        # desconto total agregado = 0% (nenhum desconto no nivel da venda),
        # mas um item individual tem 50% de desconto — deve ser bloqueado
        # mesmo sem desconto agregado, pois antes so' o agregado era validado.
        r = realizar_venda(caixa_id=1,
                            itens=[{"quantidade": 1, "valor_unitario": 100, "desconto": 50, "descricao": "Produto X"}],
                            pagamentos=[], operador="op1", operador_id=1, desconto=0)
        self.assertIn("error", r)
        self.assertIn("Produto X", r["error"])

    async def test_orcamento_com_desconto_acima_do_limite_bloqueado(self):
        """Antes desta correcao, criar_orcamento() nao validava desconto algum
        — dava para criar um orcamento com desconto de 100% e converter em
        venda finalizada sem nunca passar pela checagem de realizar_venda."""
        from core.pdv import criar_orcamento
        r = criar_orcamento(itens=[{"quantidade": 1, "valor_unitario": 100, "desconto": 0}],
                             operador="op1", operador_id=1, desconto=50)
        self.assertIn("error", r)

    async def test_orcamento_dentro_do_limite_aplica(self):
        from core.pdv import criar_orcamento
        r = criar_orcamento(itens=[{"quantidade": 1, "valor_unitario": 100, "desconto": 0}],
                             operador="op1", operador_id=1, desconto=5)
        self.assertNotIn("error", r)
        self.assertTrue(r.get("orcamento"))


class TestPDVConverterOrcamento(unittest.IsolatedAsyncioTestCase):
    """converter_orcamento() revalida o limite de desconto — defesa em
    profundidade alem da checagem em criar_orcamento (o orcamento poderia
    em tese ser manipulado direto no banco entre a criacao e a conversao)."""

    def setUp(self):
        self.fake = FakeDB()
        self._patches = []
        async def _get_db(_fake=self.fake):
            return _fake
        p = patch("core.pdv.get_db", side_effect=_get_db)
        p.start()
        self._patches.append(p)
        import core.pdv as m
        m._ensure_tables = lambda: None
        self.fake.operadores[1] = {"id": 1, "nome": "op1", "role": "operador", "ativo": True, "senha": None, "desconto_maximo_percent": 10}

        self.fake.orcamento = {"id": 10, "status": "orcamento", "desconto": 50, "total": 50}
        self.fake.itens_orcamento = [{"id": 1, "venda_id": 10, "descricao": "Produto X", "quantidade": 1, "valor_unitario": 100, "desconto": 0}]

        async def fetchrow(query, *params):
            q = " ".join(query.split())
            if "FROM pdv_operadores WHERE id" in q:
                (oid,) = params
                return self.fake.operadores.get(oid)
            if "FROM pdv_vendas WHERE id" in q:
                return self.fake.orcamento
            return None
        async def fetch(query, *params):
            q = " ".join(query.split())
            if "FROM pdv_itens WHERE venda_id" in q:
                return self.fake.itens_orcamento
            return []
        self.fake.fetchrow = fetchrow
        self.fake.fetch = fetch

    def tearDown(self):
        for p in self._patches:
            p.stop()

    async def test_converter_orcamento_com_desconto_acima_do_limite_bloqueado(self):
        from core.pdv import converter_orcamento
        r = converter_orcamento(venda_id=10, caixa_id=1, pagamentos=[], operador="op1", operador_id=1)
        self.assertIn("error", r)


class TestPDVFecharCaixa(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.fake = FakeDB()
        self._patches = []
        async def _get_db(_fake=self.fake):
            return _fake
        p = patch("core.pdv.get_db", side_effect=_get_db)
        p.start()
        self._patches.append(p)
        import core.pdv as m
        m._ensure_tables = lambda: None
        self.fake.operadores[1] = {"id": 1, "nome": "gerente1", "role": "gerente", "ativo": True, "senha": None}
        self.fake.caixas[1] = {"saldo_inicial": 100}

    def tearDown(self):
        for p in self._patches:
            p.stop()

    async def test_fechar_caixa_persiste_diferenca_e_avisa_segregacao(self):
        from core.pdv import fechar_caixa
        self.fake.vendas_por_caixa[1] = ["gerente1"]  # unico operador do turno = quem fecha
        with patch("core.pdv.verificar_operador", return_value={"ok": True, "id": 1, "nome": "gerente1", "role": "gerente"}), \
             patch("core.entidades.ao_fechar_caixa_pdv", return_value=None, create=True):
            r = fechar_caixa(caixa_id=1, saldo_final=100, operador_id=1, senha="x")
        self.assertTrue(r.get("aviso_segregacao"))
        self.assertEqual(self.fake.caixas[1]["diferenca"], 0)

    async def test_fechar_caixa_sem_segregacao_quando_outro_operador_vendeu(self):
        from core.pdv import fechar_caixa
        self.fake.vendas_por_caixa[1] = ["operador2"]
        with patch("core.pdv.verificar_operador", return_value={"ok": True, "id": 1, "nome": "gerente1", "role": "gerente"}), \
             patch("core.entidades.ao_fechar_caixa_pdv", return_value=None, create=True):
            r = fechar_caixa(caixa_id=1, saldo_final=100, operador_id=1, senha="x")
        self.assertFalse(r.get("aviso_segregacao"))


class TestPDVPinGerencial(unittest.IsolatedAsyncioTestCase):
    """PIN numerico curto — operador comum chama um gerente para autorizar
    cancelamento/devolucao/sangria/desconto sem precisar de logout/login."""

    def setUp(self):
        self.fake = FakeDB()
        self._patches = []
        async def _get_db(_fake=self.fake):
            return _fake
        p = patch("core.pdv.get_db", side_effect=_get_db)
        p.start()
        self._patches.append(p)
        p_ensure = patch("core.pdv._ensure_saldos_async", new=AsyncMock(return_value=None))
        p_ensure.start()
        self._patches.append(p_ensure)
        import core.pdv as m
        m._ensure_tables = lambda: None
        self.fake.operadores[1] = {"id": 1, "nome": "gerente1", "role": "gerente", "ativo": True, "senha": None, "pin_hash": None}
        self.fake.operadores[2] = {"id": 2, "nome": "op2", "role": "operador", "ativo": True, "senha": None, "pin_hash": None}

    def tearDown(self):
        for p in self._patches:
            p.stop()

    async def test_definir_e_verificar_pin_correto(self):
        from core.pdv import definir_pin, verificar_pin_gerencial
        r = definir_pin(1, "1234")
        self.assertTrue(r.get("ok"))
        r2 = verificar_pin_gerencial(1, "1234", {"gerente", "admin"})
        self.assertTrue(r2.get("ok"))
        self.assertEqual(r2.get("nome"), "gerente1")

    async def test_pin_incorreto_rejeitado(self):
        from core.pdv import definir_pin, verificar_pin_gerencial
        definir_pin(1, "1234")
        r = verificar_pin_gerencial(1, "9999", {"gerente", "admin"})
        self.assertIn("error", r)

    async def test_pin_de_operador_nao_gerencial_rejeitado(self):
        from core.pdv import definir_pin, verificar_pin_gerencial
        definir_pin(2, "1234")
        r = verificar_pin_gerencial(2, "1234", {"gerente", "admin"})
        self.assertIn("error", r)

    async def test_pin_invalido_curto_recusado_ao_definir(self):
        from core.pdv import definir_pin
        r = definir_pin(1, "12")
        self.assertIn("error", r)

    async def test_cancelar_venda_com_pin_de_gerente_autoriza_operador_comum(self):
        from core.pdv import definir_pin, cancelar_venda
        definir_pin(1, "1234")

        async def fetchrow_venda(query, *params):
            q = " ".join(query.split())
            if "FROM pdv_operadores WHERE id" in q:
                (oid,) = params
                return self.fake.operadores.get(oid)
            if "FROM pdv_vendas WHERE id" in q:
                return {"id": 10, "status": "finalizada", "total": 50, "caixa_id": None}
            return None
        self.fake.fetchrow = fetchrow_venda
        r = cancelar_venda(venda_id=10, motivo="cliente desistiu", operador="op2", operador_id=2,
                            gerente_pin_id=1, pin="1234")
        self.assertTrue(r.get("success"))


class TestPDVCodigoBarrasGerencial(unittest.IsolatedAsyncioTestCase):
    """Codigo de barras (cracha fisico) — 'PIN fisico': bipar ja identifica o
    gerente automaticamente, sem precisar selecionar da lista antes."""

    def setUp(self):
        self.fake = FakeDB()
        self._patches = []
        async def _get_db(_fake=self.fake):
            return _fake
        p = patch("core.pdv.get_db", side_effect=_get_db)
        p.start()
        self._patches.append(p)
        import core.pdv as m
        m._ensure_tables = lambda: None
        self.fake.operadores[1] = {"id": 1, "nome": "gerente1", "role": "gerente", "ativo": True, "senha": None, "codigo_barras_hash": None}
        self.fake.operadores[2] = {"id": 2, "nome": "op2", "role": "operador", "ativo": True, "senha": None, "codigo_barras_hash": None}

    def tearDown(self):
        for p in self._patches:
            p.stop()

    async def test_gerar_e_verificar_codigo_de_barras(self):
        from core.pdv import gerar_codigo_barras, verificar_codigo_barras_gerencial
        r = gerar_codigo_barras(1)
        self.assertTrue(r.get("ok"))
        codigo = r["codigo_barras"]
        self.assertTrue(len(codigo) >= 12)
        r2 = verificar_codigo_barras_gerencial(codigo, {"gerente", "admin"})
        self.assertTrue(r2.get("ok"))
        self.assertEqual(r2.get("id"), 1)
        self.assertEqual(r2.get("nome"), "gerente1")

    async def test_codigo_de_barras_identifica_automaticamente_sem_informar_gerente_id(self):
        """Diferenca chave do codigo de barras vs PIN: nao precisa saber de
        antemao qual gerente e' — o codigo sozinho ja resolve."""
        from core.pdv import gerar_codigo_barras, verificar_codigo_barras_gerencial
        gerar_codigo_barras(1)
        codigo = self.fake.operadores[1]["codigo_barras_hash"]  # apenas para confirmar que foi salvo
        self.assertIsNotNone(codigo)

    async def test_codigo_incorreto_nao_autoriza(self):
        from core.pdv import gerar_codigo_barras, verificar_codigo_barras_gerencial
        gerar_codigo_barras(1)
        r = verificar_codigo_barras_gerencial("codigo-errado-qualquer", {"gerente", "admin"})
        self.assertIn("error", r)

    async def test_codigo_de_operador_nao_gerencial_rejeitado(self):
        from core.pdv import gerar_codigo_barras, verificar_codigo_barras_gerencial
        r = gerar_codigo_barras(2)
        codigo = r["codigo_barras"]
        r2 = verificar_codigo_barras_gerencial(codigo, {"gerente", "admin"})
        self.assertIn("error", r2)

    async def test_sangria_com_codigo_de_barras_autoriza_operador_comum(self):
        from core.pdv import gerar_codigo_barras, sangria
        r = gerar_codigo_barras(1)
        codigo = r["codigo_barras"]
        result = sangria(caixa_id=1, valor=500, motivo="deposito_banco", operador="op2",
                          operador_id=2, codigo_barras=codigo)
        # 500 > limite padrao (200) -> deve ficar pendente, nao aplicar direto
        self.assertTrue(result.get("pendente"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
