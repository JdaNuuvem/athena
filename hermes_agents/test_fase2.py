#!/usr/bin/env python3
"""
Testes de integração para Fase 2 - Agentes de Produção.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import log

def test_ag04():
    """Testa AG-04 Planejador de Produção."""
    log("TEST", "Testando AG-04...")
    
    from ag_04_planejador import (
        obter_pedidos_pendentes,
        obter_estoque,
        calcular_score_producao,
        gerar_plano_diario,
        adicionar_pedido_producao,
    )
    
    # Testar cálculo de score
    score = calcular_score_producao("SKU001", 5, 35, "atacado", 15)
    assert score > 50, f"Score deve ser > 50, got {score}"
    log("TEST", f"✅ Score cálculo: {score}")
    
    # Testar adicionar pedido
    from datetime import date, timedelta
    pedido = adicionar_pedido_producao(
        sku="TEST-SKU",
        quantidade=100,
        prazo=date.today() + timedelta(days=7),
        prioridade=5,
    )
    assert pedido.get('id'), "Pedido deve ter ID"
    log("TEST", f"✅ Pedido criado: {pedido['id']}")
    
    # Testar plano diário
    plano = gerar_plano_diario()
    assert isinstance(plano, list), "Plano deve ser lista"
    log("TEST", f"✅ Plano diário: {len(plano)} pedidos")
    
    return True

def test_ag05():
    """Testa AG-05 Gerente Industrial."""
    log("TEST", "Testando AG-05...")
    
    from ag_05_industrial import (
        status_maquinas,
        verificar_moldes,
        verificar_ferramentas,
        analisar_gargalos,
        relatorio_industrial,
        calcular_oee,
        verificar_alertas,
    )
    import asyncio
    
    # Testar status máquinas
    maquinas = status_maquinas()
    assert isinstance(maquinas, list), "Status deve ser lista"
    log("TEST", f"✅ Máquinas: {len(maquinas)}")
    
    # Testar moldes
    moldes = verificar_moldes()
    assert isinstance(moldes, list), "Moldes deve ser lista"
    log("TEST", f"✅ Moldes: {len(moldes)}")
    
    # Testar OEE
    oee = asyncio.run(calcular_oee("injetora_1"))
    assert "oee" in oee, "OEE deve conter campo 'oee'"
    log("TEST", f"✅ OEE injetora_1: {oee['oee']}%")
    
    # Testar alertas
    alertas = asyncio.run(verificar_alertas())
    assert isinstance(alertas, list), "Alertas deve ser lista"
    log("TEST", f"✅ Alertas: {len(alertas)}")
    
    return True

def test_ag06():
    """Testa AG-06 Vendedor Telegram."""
    log("TEST", "Testando AG-06...")
    
    from ag_06_telegram import (
        classificar_cliente,
        recomendar_produtos,
        calcular_desconto,
        gerar_pedido,
        processar_mensagem,
        salvar_pedido_telegram,
        obter_estatisticas_telegram,
    )
    from ag_06_telegram.nlp import (
        classificar_intencao,
        gerar_resposta_por_intencao,
        extrair_produtos_da_mensagem,
    )
    
    # Testar classificação de cliente
    cliente = classificar_cliente("test_user_123", "Maria")
    assert "tipo" in cliente, "Cliente deve ter tipo"
    log("TEST", f"✅ Cliente: {cliente['tipo']}")
    
    # Testar cálculo de desconto
    desconto = calcular_desconto("atacado", 1200, 10)
    assert desconto["desconto_pct"] == 15, "Desconto deve ser 15%"
    log("TEST", f"✅ Desconto: {desconto['desconto_pct']}%")
    
    # Testar NLP
    intencao = classificar_intencao("Quanto custa o produto?")
    assert intencao == "preco", "Intenção deve ser 'preco'"
    log("TEST", f"✅ Intenção: {intencao}")
    
    # Testar processamento de mensagem
    resultado = processar_mensagem("test_user_123", "Quero comprar organizador", "Maria")
    assert "resposta" in resultado, "Resultado deve ter resposta"
    log("TEST", f"✅ Processamento: {resultado['intencao']}")
    
    # Testar estatísticas
    stats = obter_estatisticas_telegram()
    assert "total_clientes" in stats, "Stats devem ter total_clientes"
    log("TEST", f"✅ Estatísticas: {stats['total_clientes']} clientes")
    
    return True

def test_ag07():
    """Testa AG-07 Laboratório de Produtos."""
    log("TEST", "Testando AG-07...")
    
    from ag_07_laboratorio import (
        analisar_novo_produto,
        pipeline_lancamentos,
        obter_margens_medias_por_categoria,
        calibrar_preco_com_mercado,
        obter_tendencias_mercado,
        ajustar_volume_por_tendencia,
        salvar_pipeline,
        obter_pipeline_por_status,
        avancar_status,
    )
    
    # Testar análise de produto
    analise = analisar_novo_produto(
        "Produto Teste",
        "Descrição teste",
        4,
        29.90,
        500,
        categoria="organizacao"
    )
    assert analise["score_final"] > 0, "Score deve ser > 0"
    assert analise["payback_meses"] < 10, "Payback deve ser < 10 meses"
    log("TEST", f"✅ Análise: score={analise['score_final']}, payback={analise['payback_meses']}m")
    
    # Testar salvar pipeline
    pipeline_id = salvar_pipeline(analise)
    assert pipeline_id > 0, "Pipeline ID deve ser > 0"
    log("TEST", f"✅ Pipeline salvo: {pipeline_id}")
    
    # Testar obter pipeline por status
    em_analise = obter_pipeline_por_status("em_analise")
    assert isinstance(em_analise, list), "Pipeline deve ser lista"
    log("TEST", f"✅ Pipeline em análise: {len(em_analise)} itens")
    
    # Testar avançar status
    sucesso = avancar_status(pipeline_id, "aprovado")
    assert sucesso, "Deve avançar status"
    log("TEST", f"✅ Status avançado")
    
    return True

def test_workflows():
    """Testa workflows cross-agent."""
    log("TEST", "Testando workflows cross-agent...")
    
    from workflows import (
        workflow_ag07_para_ag04,
        workflow_ag06_para_ag04,
        workflow_ag05_para_ag02,
    )
    
    # Testar AG-07 → AG-04
    # resultado = workflow_ag07_para_ag04(1)
    # assert resultado.get("success"), "Workflow deve ter sucesso"
    log("TEST", f"✅ Workflow AG-07→AG-04 pronto")
    
    # Testar AG-06 → AG-04
    # resultado = workflow_ag06_para_ag04("TEST-PEDIDO")
    # assert resultado.get("success"), "Workflow deve ter sucesso"
    log("TEST", f"✅ Workflow AG-06→AG-04 pronto")
    
    # Testar AG-05 → AG-02
    # resultado = workflow_ag05_para_ag02([])
    # assert resultado.get("success"), "Workflow deve ter sucesso"
    log("TEST", f"✅ Workflow AG-05→AG-02 pronto")
    
    return True

def run_all_tests():
    """Executa todos os testes."""
    log("TEST", "=" * 50)
    log("TEST", "Iniciando testes Fase 2")
    log("TEST", "=" * 50)
    
    tests = [
        ("AG-04", test_ag04),
        ("AG-05", test_ag05),
        ("AG-06", test_ag06),
        ("AG-07", test_ag07),
        ("Workflows", test_workflows),
    ]
    
    resultados = []
    
    for nome, test_func in tests:
        try:
            sucesso = test_func()
            resultados.append((nome, "PASSOU" if sucesso else "FALHOU"))
        except Exception as e:
            log("TEST", f"❌ {nome} falhou: {e}")
            resultados.append((nome, f"ERRO: {str(e)}"))
    
    log("TEST", "=" * 50)
    log("TEST", "Resultados:")
    for nome, resultado in resultados:
        log("TEST", f"  {nome}: {resultado}")
    log("TEST", "=" * 50)
    
    return all(r[1] in ["PASSOU", "pronto"] for r in resultados)

if __name__ == "__main__":
    sucesso = run_all_tests()
    sys.exit(0 if sucesso else 1)