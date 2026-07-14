"""
AG-05 CNC Interface: Mock de integração com máquinas CNC.
Substituir por API real quando disponível.
"""
import random
from datetime import datetime, timedelta

class CNCInterface:
    """Interface para integração CNC - Mock inicial."""
    
    def __init__(self):
        self.maquinas = {
            "injetora_1": {"nome": "Injetora 1", "tipo": "injecao", "tempo_ciclo_padrao": 30},
            "injetora_2": {"nome": "Injetora 2", "tipo": "injecao", "tempo_ciclo_padrao": 25},
            "injetora_3": {"nome": "Injetora 3", "tipo": "injecao", "tempo_ciclo_padrao": 28},
            "cnc_router": {"nome": "CNC Router", "tipo": "usinagem", "tempo_ciclo_padrao": 120},
        }
    
    async def get_machine_status(self, machine_id: str) -> dict:
        """Mock de integração CNC - substituir por API real depois."""
        if machine_id not in self.maquinas:
            return {"error": "Máquina não encontrada"}
        
        maquina = self.maquinas[machine_id]
        
        # Simular variação de performance
        desvio = random.uniform(-5, 15)
        tempo_ciclo_atual = maquina["tempo_ciclo_padrao"] + desvio
        
        # Calcular OEE simulado
        disponibilidade = random.uniform(0.85, 0.98)
        performance = maquina["tempo_ciclo_padrao"] / tempo_ciclo_atual
        qualidade = random.uniform(0.95, 0.99)
        oee = disponibilidade * performance * qualidade * 100
        
        return {
            "machine_id": machine_id,
            "nome": maquina["nome"],
            "tipo": maquina["tipo"],
            "status": "running" if random.random() > 0.1 else "maintenance",
            "tempo_ciclo_padrao": maquina["tempo_ciclo_padrao"],
            "tempo_ciclo_atual": round(tempo_ciclo_atual, 1),
            "oee": round(oee, 1),
            "disponibilidade": round(disponibilidade * 100, 1),
            "performance": round(performance * 100, 1),
            "qualidade": round(qualidade * 100, 1),
            "maintenance_due": oee < 75,
            "ultima_manutencao": (datetime.now() - timedelta(days=random.randint(1, 30))).isoformat(),
        }
    
    async def get_all_machines_status(self) -> list:
        """Status de todas as máquinas."""
        import asyncio
        tasks = [self.get_machine_status(mid) for mid in self.maquinas.keys()]
        return await asyncio.gather(*tasks)
    
    async def update_machine_status(self, machine_id: str, status: str) -> bool:
        """Atualiza status da máquina (mock)."""
        # ponytail: substituir por chamada API real quando disponível
        if machine_id in self.maquinas:
            self.maquinas[machine_id]["status"] = status
            return True
        return False