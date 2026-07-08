"""
AG-05: Gerente Industrial
Monitora CNC, moldes, produção, tempos de ciclo, estoque de matéria-prima
e consumo de ferramentas. Identifica gargalos antes que virem prejuízo.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import get_db, run_async, log, hoje
from .cnc_interface import CNCInterface

AGENT = "AG-05 | Gerente Industrial"

def status_maquinas() -> list:
    """Status em tempo real de todas as máquinas."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("SELECT * FROM status_maquinas ORDER BY nome")
        return [dict(r) for r in rows]
    return run_async(_go())

def verificar_moldes() -> list:
    """Moldes com ciclos restantes abaixo do limite."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT codigo, produto, ciclos_previstos, ciclos_atuais,
                   ROUND(ciclos_atuais::numeric / ciclos_previstos * 100, 1) AS utilizacao_pct,
                   ciclos_previstos - ciclos_atuais AS ciclos_restantes,
                   CASE WHEN ciclos_atuais >= ciclos_previstos * 0.8 THEN 'critico'
                        WHEN ciclos_atuais >= ciclos_previstos * 0.6 THEN 'alerta'
                        ELSE 'ok' END AS status
            FROM moldes WHERE status = 'ativo' AND ciclos_previstos > 0
            ORDER BY utilizacao_pct DESC
        """)
        return [dict(r) for r in rows]
    return run_async(_go())

def verificar_ferramentas() -> list:
    """Ferramentas com consumo anômalo ou próximas da troca."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT * FROM ferramentas_cnc
            WHERE status IN ('anomalo', 'troca_proxima', 'critico')
            ORDER BY 
                CASE status 
                    WHEN 'critico' THEN 1 
                    WHEN 'anomalo' THEN 2 
                    WHEN 'troca_proxima' THEN 3 
                END
        """)
        return [dict(r) for r in rows]
    return run_async(_go())

async def calcular_oee(maquina_id: str) -> dict:
    """Overall Equipment Effectiveness em tempo real."""
    cnc = CNCInterface()
    status = await cnc.get_machine_status(maquina_id)
    
    if "error" in status:
        return {"error": status["error"], "maquina_id": maquina_id}
    
    oee = status['oee']
    
    if oee < 70:
        status_ = 'critico'
    elif oee < 80:
        status_ = 'atencao'
    else:
        status_ = 'normal'
    
    return {
        "maquina_id": maquina_id,
        "nome": status.get('nome', maquina_id),
        "oee": round(oee, 1),
        "status": status_,
        "meta": 85.0,
        "gap": round(85.0 - oee, 1),
        "disponibilidade": status.get('disponibilidade', 0),
        "performance": status.get('performance', 0),
        "qualidade": status.get('qualidade', 0),
    }

async def verificar_alertas() -> list:
    """Verifica todos os alertas industriais."""
    alertas = []
    
    # Moldes críticos
    moldes_criticos = await verificar_moldes()
    for molde in moldes_criticos:
        if molde['status'] == 'critico':
            alertas.append({
                "tipo": "molde_critico",
                "molde": molde['codigo'],
                "gravidade": "alta",
                "mensagem": f"Molde {molde['codigo']} com {molde.get('ciclos_restantes', 0)} ciclos restantes (<20%)"
            })
    
    # OEE abaixo da meta
    cnc = CNCInterface()
    maquinas_status = await cnc.get_all_machines_status()
    
    for status in maquinas_status:
        if "error" not in status:
            oee_alert = await calcular_oee(status['machine_id'])
            if oee_alert['status'] in ['critico', 'atencao']:
                alertas.append({
                    "tipo": "oee_baixo",
                    "maquina": oee_alert['maquina_id'],
                    "gravidade": "alta" if oee_alert['status'] == 'critico' else "media",
                    "mensagem": f"OEE {oee_alert['oee']}% abaixo da meta ({oee_alert['meta']}%) - gap: {oee_alert['gap']}%"
                })
    
    # Ferramentas anômalas
    ferramentas = await verificar_ferramentas()
    for ferramenta in ferramentas:
        alertas.append({
            "tipo": "ferramenta_anomala",
            "ferramenta": ferramenta['nome'],
            "gravidade": "alta" if ferramenta['status'] == 'critico' else "media",
            "mensagem": f"Ferramenta {ferramenta['nome']} com status {ferramenta['status']}"
        })
    
    # Matéria-prima baixa
    materia_baixa = await alerta_materia_prima()
    for material in materia_baixa:
        alertas.append({
            "tipo": "materia_prima_baixa",
            "material": material['nome'],
            "gravidade": "media",
            "mensagem": f"{material['nome']} com estoque crítico: {material['estoque_atual_kg']}kg (mínimo: {material['estoque_minimo_kg']}kg)"
        })
    
    return alertas

def analisar_gargalos() -> list:
    """Identifica gargalos na produção."""
    log(AGENT, "Analisando gargalos...")
    gargalos = []
    maquinas = [
        {"nome": "Injetora 1", "tempo_ciclo_padrao": 30, "tempo_ciclo_atual": 42, "status": "lento"},
        {"nome": "Injetora 2", "tempo_ciclo_padrao": 25, "tempo_ciclo_atual": 26, "status": "normal"},
        {"nome": "CNC Router", "tempo_ciclo_padrao": 120, "tempo_ciclo_atual": 135, "status": "atencao"},
    ]
    for m in maquinas:
        desvio = m["tempo_ciclo_atual"] - m["tempo_ciclo_padrao"]
        desvio_pct = round(desvio / m["tempo_ciclo_padrao"] * 100, 1) if m["tempo_ciclo_padrao"] else 0
        gargalos.append({**m, "desvio_pct": desvio_pct})

    return sorted(gargalos, key=lambda x: x["desvio_pct"], reverse=True)

def alerta_materia_prima() -> list:
    """Matérias-primas com estoque crítico."""
    async def _go():
        db = await get_db()
        rows = await db.fetch("""
            SELECT nome, estoque_atual_kg, estoque_minimo_kg, fornecedor_id
            FROM materias_primas
            WHERE estoque_atual_kg <= estoque_minimo_kg * 1.2
        """)
        return [dict(r) for r in rows]
    return run_async(_go())

def relatorio_industrial() -> dict:
    """Relatório consolidado industrial."""
    log(AGENT, "Gerando relatório industrial...")
    moldes = verificar_moldes()
    criticos = [m for m in moldes if m["status"] == "critico"]
    gargalos = analisar_gargalos()
    return {
        "data": hoje(),
        "moldes_total": len(moldes),
        "moldes_criticos": len(criticos),
        "moldes_80porcento": [m["codigo"] for m in criticos],
        "gargalos": gargalos,
        "materia_prima_baixa": alerta_materia_prima(),
        "ferramentas_anomalas": [f for f in verificar_ferramentas() if f["status"] != "normal"],
    }

if __name__ == "__main__":
    log(AGENT, "Auto-teste")
    print("Gargalos:", analisar_gargalos())
    print("Relatório:", relatorio_industrial()["moldes_criticos"])
