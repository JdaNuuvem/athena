"""Testes de resolucao de vinculo fisica x virtual em core/estoque.py.

Task 5: listar()/movimentacoes() sao os dois pontos de LEITURA de
core/estoque.py que consultam estoque_lojas/estoque_movimentacoes
diretamente (fora do choke point de core/estoque_saldos.py, ja' coberto
pelas Tasks 3-4 em test_estoque_saldos.py) — por isso precisam do proprio
guard de resolucao de loja (virtual com vinculo ativo -> nome da fisica
vinculada) antes de montar o WHERE.

Fail-open (mesmo padrao de core/estoque_saldos.py::saldo()/_saldo_async(),
ver docstrings la' para o raciocinio completo): o resolver real
(core.lojas._loja_efetiva_async) abre sua PROPRIA conexao via get_db(),
independente do `db` fakeado por estes testes (core.estoque.get_db). Um
resolver que EXPLODE (DB indisponivel) OU que devolve um valor invalido sem
excecao precisa ser tratado como no-op — listar()/movimentacoes() continuam
usando o nome de loja ORIGINAL — em vez de deixar o try/except externo de
_go() (que vira {"erro": ...}/[]) engolir a listagem/historico inteiro por
causa so' de um resolver que falhou.

Importante (mesmo cuidado de patch-target documentado em
test_estoque_saldos.py::TestVinculoEstoqueEscrita/TestVinculoEstoqueLeitura,
e reconfirmado manualmente aqui): o alvo do patch e'
`core.estoque._loja_efetiva_async` / `core.estoque._log_erro` (os NOMES
importados dentro deste modulo via `from core.lojas import
_loja_efetiva_async, _log_erro`), NAO `core.lojas._loja_efetiva_async` /
`core.lojas._log_erro` — com `from ... import ...`, o modulo que consome
fica com sua propria referencia ao objeto funcao; patchar so' o modulo de
origem nao intercepta a chamada feita a partir de core/estoque.py (confirmado
empiricamente: com o patch mirando core.lojas.*, o resolver real roda,
tenta abrir uma conexao de verdade via core.lojas.get_db() e falha - o
fail-open entao mantem corretamente o nome original, mas o teste nunca
chegaria a validar a resolucao bem-sucedida do vinculo)."""
import sys, os, unittest
from unittest.mock import patch, AsyncMock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.estoque as estoque


class TestListarResolveVinculo(unittest.TestCase):
    def test_listar_com_loja_nome_resolve_para_fisica(self):
        db = AsyncMock()
        db.fetchval.return_value = 0
        db.fetch.return_value = []
        with patch("core.estoque.get_db", AsyncMock(return_value=db)), \
             patch("core.estoque._loja_efetiva_async",
                   AsyncMock(return_value="Loja Fisica Central")) as mock_resolver:
            estoque.listar(loja="Loja Virtual A")
        mock_resolver.assert_called_once_with("Loja Virtual A")
        args = db.fetchval.call_args[0]
        self.assertIn("Loja Fisica Central", args)

    def test_listar_loja_sem_vinculo_passa_pelo_resolver_e_usa_o_proprio_nome(self):
        """Regression: loja fisica (ou virtual sem vinculo) precisa continuar
        filtrando pelo proprio nome — o resolver so' troca quando ha' vinculo
        ativo; aqui o fake devolve o mesmo nome recebido, como o resolver
        real faz pra esse caso (ver core/lojas.py::_loja_efetiva_async)."""
        db = AsyncMock()
        db.fetchval.return_value = 0
        db.fetch.return_value = []
        with patch("core.estoque.get_db", AsyncMock(return_value=db)), \
             patch("core.estoque._loja_efetiva_async",
                   AsyncMock(side_effect=lambda loja: loja)) as mock_resolver:
            estoque.listar(loja="Loja A")
        mock_resolver.assert_called_once_with("Loja A")
        args = db.fetchval.call_args[0]
        self.assertIn("Loja A", args)

    def test_listar_resolver_indisponivel_nao_derruba_a_listagem_usa_loja_original(self):
        """O resolver real abre sua PROPRIA conexao (core.lojas.get_db()),
        independente do `db` fakeado aqui (core.estoque.get_db) — uma
        excecao (DB indisponivel) precisa ser tratada como no-op (listar()
        continua usando 'loja' original), nunca propagar e derrubar a
        listagem inteira via o try/except externo de _go() (que devolveria
        {"erro": ...}). A falha tambem precisa chegar em _log_erro
        (persistido em system_logs), nao so' sumir."""
        db = AsyncMock()
        db.fetchval.return_value = 3
        db.fetch.return_value = []
        erro_original = RuntimeError("DB indisponivel")
        with patch("core.estoque.get_db", AsyncMock(return_value=db)), \
             patch("core.estoque._loja_efetiva_async",
                   AsyncMock(side_effect=erro_original)) as mock_resolver, \
             patch("core.estoque._log_erro") as mock_log_erro:
            resultado = estoque.listar(loja="Loja Virtual A")
        mock_resolver.assert_called_once_with("Loja Virtual A")
        self.assertNotIn("erro", resultado)
        self.assertEqual(resultado["total"], 3)
        args = db.fetchval.call_args[0]
        self.assertIn("Loja Virtual A", args)
        mock_log_erro.assert_called_once()
        onde, exc = mock_log_erro.call_args[0]
        self.assertIn("resolver_loja_efetiva", onde)
        self.assertIs(exc, erro_original)

    def test_listar_resolver_devolve_valor_nao_string_e_ignorado_usa_loja_original(self):
        """Outra face da regression acima: resolver que NAO levanta excecao
        mas devolve algo que nao e' um nome de loja valido (ex.: None)
        precisa ser ignorado (usa 'loja' original) e logado via _log_erro —
        nunca filtrar estoque por uma chave corrompida silenciosamente."""
        db = AsyncMock()
        db.fetchval.return_value = 3
        db.fetch.return_value = []
        with patch("core.estoque.get_db", AsyncMock(return_value=db)), \
             patch("core.estoque._loja_efetiva_async",
                   AsyncMock(return_value=None)) as mock_resolver, \
             patch("core.estoque._log_erro") as mock_log_erro:
            resultado = estoque.listar(loja="Loja Virtual A")
        mock_resolver.assert_called_once_with("Loja Virtual A")
        self.assertNotIn("erro", resultado)
        self.assertEqual(resultado["total"], 3)
        args = db.fetchval.call_args[0]
        self.assertIn("Loja Virtual A", args)
        mock_log_erro.assert_called_once()
        onde, exc = mock_log_erro.call_args[0]
        self.assertIn("resolver_loja_efetiva", onde)
        self.assertIsInstance(exc, Exception)


class TestMovimentacoesResolveVinculo(unittest.TestCase):
    def test_movimentacoes_com_loja_resolve_para_fisica(self):
        db = AsyncMock()
        db.fetch.return_value = []
        with patch("core.estoque.get_db", AsyncMock(return_value=db)), \
             patch("core.estoque._loja_efetiva_async",
                   AsyncMock(return_value="Loja Fisica Central")) as mock_resolver:
            estoque.movimentacoes(loja="Loja Virtual A")
        mock_resolver.assert_called_once_with("Loja Virtual A")
        args = db.fetch.call_args[0]
        self.assertIn("Loja Fisica Central", args)

    def test_movimentacoes_loja_sem_vinculo_passa_pelo_resolver_e_usa_o_proprio_nome(self):
        """Regression: mesma logica do TestListarResolveVinculo homologo."""
        db = AsyncMock()
        db.fetch.return_value = []
        with patch("core.estoque.get_db", AsyncMock(return_value=db)), \
             patch("core.estoque._loja_efetiva_async",
                   AsyncMock(side_effect=lambda loja: loja)) as mock_resolver:
            estoque.movimentacoes(loja="Loja A")
        mock_resolver.assert_called_once_with("Loja A")
        args = db.fetch.call_args[0]
        self.assertIn("Loja A", args)

    def test_movimentacoes_resolver_indisponivel_nao_derruba_o_historico_usa_loja_original(self):
        """Mesma regression do TestListarResolveVinculo homologo. Usa uma
        linha fake NAO-vazia pra provar que o retorno veio da query real —
        o fallback de erro de movimentacoes() tambem e' [] (lista vazia),
        entao so' checar 'resultado == []' seria ambiguo entre "leitura real
        sem resultados" e "excecao engolida pelo try/except externo"."""
        db = AsyncMock()
        db.fetch.return_value = [{"sku": "SKU1", "loja": "Loja Virtual A"}]
        erro_original = RuntimeError("DB indisponivel")
        with patch("core.estoque.get_db", AsyncMock(return_value=db)), \
             patch("core.estoque._loja_efetiva_async",
                   AsyncMock(side_effect=erro_original)) as mock_resolver, \
             patch("core.estoque._log_erro") as mock_log_erro:
            resultado = estoque.movimentacoes(loja="Loja Virtual A")
        mock_resolver.assert_called_once_with("Loja Virtual A")
        self.assertEqual(resultado, [{"sku": "SKU1", "loja": "Loja Virtual A"}])
        args = db.fetch.call_args[0]
        self.assertIn("Loja Virtual A", args)
        mock_log_erro.assert_called_once()
        onde, exc = mock_log_erro.call_args[0]
        self.assertIn("resolver_loja_efetiva", onde)
        self.assertIs(exc, erro_original)

    def test_movimentacoes_resolver_devolve_valor_nao_string_e_ignorado_usa_loja_original(self):
        """Outra face da regression acima: resolver que devolve valor
        invalido sem excecao."""
        db = AsyncMock()
        db.fetch.return_value = [{"sku": "SKU1", "loja": "Loja Virtual A"}]
        with patch("core.estoque.get_db", AsyncMock(return_value=db)), \
             patch("core.estoque._loja_efetiva_async",
                   AsyncMock(return_value=None)) as mock_resolver, \
             patch("core.estoque._log_erro") as mock_log_erro:
            resultado = estoque.movimentacoes(loja="Loja Virtual A")
        mock_resolver.assert_called_once_with("Loja Virtual A")
        self.assertEqual(resultado, [{"sku": "SKU1", "loja": "Loja Virtual A"}])
        args = db.fetch.call_args[0]
        self.assertIn("Loja Virtual A", args)
        mock_log_erro.assert_called_once()
        onde, exc = mock_log_erro.call_args[0]
        self.assertIn("resolver_loja_efetiva", onde)
        self.assertIsInstance(exc, Exception)


# ── Task 7 (vinculo fisica x virtual): estoque_aprovacoes.solicitar() e
# estoque_contagem.sugestoes()/registrar() resolvem `loja` (nome/id de uma
# loja virtual com vinculo ativo) pro nome da fisica vinculada ANTES de
# checar saldo / montar o WHERE / gravar — mesmo padrao ja' estabelecido em
# core/estoque_saldos.py (Tasks 3-4), core/estoque.py (Task 5, acima neste
# mesmo arquivo) e core/estoque_analise.py (Task 6, test_estoque_analise.py).
#
# solicitar()/sugestoes() sao closures async (`async def _go()`) — resolvem
# via `_loja_efetiva_async` com o mesmo guard fail-open manual (try/except +
# validacao isinstance(str) do valor de retorno) das Tasks 5-6.
#
# registrar() e' DIFERENTE: e' uma funcao SINCRONA que chama run_async() tres
# vezes em sequencia (nao um unico `_go()`), entao resolve via a versao
# SINCRONA `loja_efetiva()` (wrapper sobre run_async, ja' fail-open com seu
# proprio _log_erro interno — core/lojas.py:133-142), UMA VEZ no topo da
# funcao — chamar a async diretamente dali (fora de um `async def`) nao e'
# possivel, e reimplementar isso com run_async(_loja_efetiva_async(...))
# manualmente correria o mesmo risco de vazar pool ja' documentado em
# core/lojas.py::loja_efetiva().
#
# Patch-target (mesmo cuidado das Tasks 3-6): os alvos sao
# `core.estoque_aprovacoes._loja_efetiva_async`/`_log_erro` e
# `core.estoque_contagem._loja_efetiva_async`/`_log_erro`/`loja_efetiva` (os
# NOMES importados dentro DE CADA modulo consumidor via `from core.lojas
# import ...`), NUNCA `core.lojas.*` diretamente — com `from ... import
# ...`, cada modulo consumidor fica com sua PROPRIA referencia ao objeto
# funcao; patchar so' o modulo de origem nao intercepta a chamada.
#
# Assercoes de "qual loja foi usada" sempre rodam DEPOIS do bloco `with`
# (via db.fetchval.call_args/db.fetch.call_args/db.execute.call_args), nunca
# dentro de um side_effect — um assertion failure ali seria engolido pelo
# `except Exception: return {"erro": ...}`/`except Exception: return []`
# externo de cada funcao (issue real, ja' batida nesta mesma plan).
class TestAprovacoesResolveVinculo(unittest.TestCase):
    def test_solicitar_resolve_loja_antes_de_checar_saldo(self):
        db = AsyncMock()
        db.fetchval.return_value = 5
        db.fetchrow.return_value = {"id": 1}
        with patch("core.estoque_aprovacoes.get_db", AsyncMock(return_value=db)), \
             patch("core.estoque_aprovacoes._loja_efetiva_async",
                   AsyncMock(return_value="Loja Fisica Central")) as mock_resolver:
            import core.estoque_aprovacoes as aprov
            aprov._ok = True  # pula _ensure() (CREATE TABLE) no teste
            resultado = aprov.solicitar("SKU-1", "Loja Virtual A", 3, "quebra")
        mock_resolver.assert_called_once_with("Loja Virtual A")
        self.assertNotIn("erro", resultado)
        self.assertEqual(resultado["loja"], "Loja Fisica Central")
        fetchval_args = db.fetchval.call_args[0]
        self.assertIn("Loja Fisica Central", fetchval_args)
        fetchrow_args = db.fetchrow.call_args[0]
        self.assertIn("Loja Fisica Central", fetchrow_args)

    def test_solicitar_resolver_indisponivel_usa_loja_original_retorna_dado_real(self):
        """Fail-open: o resolver real (core.lojas._loja_efetiva_async) abre
        sua PROPRIA conexao via get_db(), independente do `db` fakeado
        aqui — uma excecao (DB indisponivel) precisa ser tratada como
        no-op (solicitar() continua usando 'loja' ORIGINAL), nunca propagar
        e fazer o try/except externo de _go() devolver {"erro": ...}
        silenciosamente por causa so' de um resolver que falhou."""
        db = AsyncMock()
        db.fetchval.return_value = 5
        db.fetchrow.return_value = {"id": 1}
        erro_original = RuntimeError("DB indisponivel")
        with patch("core.estoque_aprovacoes.get_db", AsyncMock(return_value=db)), \
             patch("core.estoque_aprovacoes._loja_efetiva_async",
                   AsyncMock(side_effect=erro_original)) as mock_resolver, \
             patch("core.estoque_aprovacoes._log_erro") as mock_log_erro:
            import core.estoque_aprovacoes as aprov
            aprov._ok = True
            resultado = aprov.solicitar("SKU-1", "Loja Virtual A", 3, "quebra")
        mock_resolver.assert_called_once_with("Loja Virtual A")
        self.assertNotIn("erro", resultado)
        self.assertEqual(resultado["loja"], "Loja Virtual A")
        fetchval_args = db.fetchval.call_args[0]
        self.assertIn("Loja Virtual A", fetchval_args)
        mock_log_erro.assert_called_once()
        onde, exc = mock_log_erro.call_args[0]
        self.assertIn("resolver_loja_efetiva", onde)
        self.assertIs(exc, erro_original)

    def test_solicitar_resolver_devolve_valor_invalido_usa_loja_original_retorna_dado_real(self):
        """Outra face da regression acima: resolver que NAO levanta excecao
        mas devolve algo que nao e' um nome de loja valido (None) precisa
        ser ignorado (usa 'loja' original) e logado via _log_erro — nunca
        checar saldo/gravar pendencia usando uma chave corrompida
        silenciosamente."""
        db = AsyncMock()
        db.fetchval.return_value = 5
        db.fetchrow.return_value = {"id": 1}
        with patch("core.estoque_aprovacoes.get_db", AsyncMock(return_value=db)), \
             patch("core.estoque_aprovacoes._loja_efetiva_async",
                   AsyncMock(return_value=None)) as mock_resolver, \
             patch("core.estoque_aprovacoes._log_erro") as mock_log_erro:
            import core.estoque_aprovacoes as aprov
            aprov._ok = True
            resultado = aprov.solicitar("SKU-1", "Loja Virtual A", 3, "quebra")
        mock_resolver.assert_called_once_with("Loja Virtual A")
        self.assertNotIn("erro", resultado)
        self.assertEqual(resultado["loja"], "Loja Virtual A")
        fetchval_args = db.fetchval.call_args[0]
        self.assertIn("Loja Virtual A", fetchval_args)
        mock_log_erro.assert_called_once()
        onde, exc = mock_log_erro.call_args[0]
        self.assertIn("resolver_loja_efetiva", onde)
        self.assertIsInstance(exc, Exception)


class TestContagemResolveVinculo(unittest.TestCase):
    def test_sugestoes_resolve_loja(self):
        db = AsyncMock()
        db.fetch.return_value = []
        with patch("core.estoque_contagem.get_db", AsyncMock(return_value=db)), \
             patch("core.estoque_contagem._loja_efetiva_async",
                   AsyncMock(return_value="Loja Fisica Central")) as mock_resolver:
            import core.estoque_contagem as contagem
            contagem._ok = True
            resultado = contagem.sugestoes(loja="Loja Virtual A")
        mock_resolver.assert_called_once_with("Loja Virtual A")
        self.assertEqual(resultado, [])
        args = db.fetch.call_args[0]
        self.assertIn("Loja Fisica Central", args)

    def test_sugestoes_resolver_indisponivel_usa_loja_original_retorna_dado_real(self):
        """Fail-open (mesmo raciocinio do homologo em
        TestAprovacoesResolveVinculo). Usa uma linha fake NAO-vazia pra
        provar que o retorno veio da query real com a loja ORIGINAL, nao de
        um except externo engolindo tudo."""
        db = AsyncMock()
        db.fetch.return_value = [{"sku": "SKU1", "loja": "Loja Virtual A"}]
        erro_original = RuntimeError("DB indisponivel")
        with patch("core.estoque_contagem.get_db", AsyncMock(return_value=db)), \
             patch("core.estoque_contagem._loja_efetiva_async",
                   AsyncMock(side_effect=erro_original)) as mock_resolver, \
             patch("core.estoque_contagem._log_erro") as mock_log_erro:
            import core.estoque_contagem as contagem
            contagem._ok = True
            resultado = contagem.sugestoes(loja="Loja Virtual A")
        mock_resolver.assert_called_once_with("Loja Virtual A")
        self.assertEqual(resultado, [{"sku": "SKU1", "loja": "Loja Virtual A"}])
        args = db.fetch.call_args[0]
        self.assertIn("Loja Virtual A", args)
        mock_log_erro.assert_called_once()
        onde, exc = mock_log_erro.call_args[0]
        self.assertIn("resolver_loja_efetiva", onde)
        self.assertIs(exc, erro_original)

    def test_sugestoes_resolver_devolve_valor_invalido_usa_loja_original_retorna_dado_real(self):
        """Outra face da regression acima: resolver que devolve valor
        invalido sem excecao (None)."""
        db = AsyncMock()
        db.fetch.return_value = [{"sku": "SKU1", "loja": "Loja Virtual A"}]
        with patch("core.estoque_contagem.get_db", AsyncMock(return_value=db)), \
             patch("core.estoque_contagem._loja_efetiva_async",
                   AsyncMock(return_value=None)) as mock_resolver, \
             patch("core.estoque_contagem._log_erro") as mock_log_erro:
            import core.estoque_contagem as contagem
            contagem._ok = True
            resultado = contagem.sugestoes(loja="Loja Virtual A")
        mock_resolver.assert_called_once_with("Loja Virtual A")
        self.assertEqual(resultado, [{"sku": "SKU1", "loja": "Loja Virtual A"}])
        args = db.fetch.call_args[0]
        self.assertIn("Loja Virtual A", args)
        mock_log_erro.assert_called_once()
        onde, exc = mock_log_erro.call_args[0]
        self.assertIn("resolver_loja_efetiva", onde)
        self.assertIsInstance(exc, Exception)


class TestRegistrarResolveVinculo(unittest.TestCase):
    """registrar() nao e' um closure async unico como as demais funcoes
    deste arquivo — e' SINCRONA e chama run_async() tres vezes em
    sequencia, entao resolve via a versao SINCRONA loja_efetiva() (nao
    _loja_efetiva_async), UMA VEZ no topo, encadeando o resultado pra todas
    as chamadas downstream (_go() do saldo, _entrada()/_saida()/
    _solicitar_aprovacao(), e o INSERT de _salvar()). Ver comentario acima
    desta classe pro raciocinio completo e o cuidado de patch-target (NOME
    diferente do usado por sugestoes()/solicitar() acima, embora venha do
    mesmo core/lojas.py).

    Nao re-testa o fail-open do proprio loja_efetiva() aqui — ja' coberto
    pelos testes dele (Task 1); so' verifica que registrar() chama e
    encadeia o nome resolvido corretamente."""

    def test_registrar_entrada_usa_loja_resolvida_em_entrada_e_salvar(self):
        db = AsyncMock()
        db.fetchval.side_effect = [3, 1]  # 1: saldo atual (_go); 2: loja_id (_salvar)
        with patch("core.estoque_contagem.get_db", AsyncMock(return_value=db)), \
             patch("core.estoque_contagem.loja_efetiva",
                   return_value="Loja Fisica Central") as mock_loja_efetiva, \
             patch("core.estoque_contagem._entrada",
                   return_value={"ok": True}) as mock_entrada:
            import core.estoque_contagem as contagem
            contagem._ok = True
            resultado = contagem.registrar("SKU-1", "Loja Virtual A", 10,
                                            usuario_id=1, usuario_nome="Fulano")
        mock_loja_efetiva.assert_called_once_with("Loja Virtual A")
        mock_entrada.assert_called_once_with(
            "SKU-1", "Loja Fisica Central", 7, "ajuste_inventario", 1, "Fulano")
        salvar_args = db.execute.call_args[0]
        self.assertIn("Loja Fisica Central", salvar_args)
        self.assertNotIn("Loja Virtual A", salvar_args)
        self.assertEqual(resultado["loja"], "Loja Fisica Central")
        self.assertEqual(resultado["ajuste_status"], "aplicado")


if __name__ == "__main__":
    unittest.main(verbosity=2)
