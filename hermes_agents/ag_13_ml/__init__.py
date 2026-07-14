"""
AG-13: Machine Learning - Previsão de Defeitos
Modelo simples RandomForest para prever probabilidade de defeitos.
Ponytail: modelo mínimo, sem over-engineering.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import get_db, run_async, log

AGENT = "AG-13 | Machine Learning"

try:
    import pandas as pd
    from sklearn.ensemble import RandomForestClassifier
    import pickle
    HAS_ML = True
except ImportError:
    HAS_ML = False
    log(AGENT, "⚠️ scikit-learn não instalado. Use: pip install scikit-learn")

def treinar_modelo_previsao_defeitos() -> dict:
    """Treina modelo simples de previsão de defeitos."""
    if not HAS_ML:
        return {"error": "scikit-learn não instalado"}
    
    async def _go():
        db = await get_db()
        
        # Buscar dados históricos de produção
        rows = await db.fetch("""
            SELECT 
                pl.sku,
                pl.quantidade_planejada,
                pl.quantidade_defeituosa,
                pl.tempo_ciclo_segundos,
                pl.oee_calculado,
                m.tipo as molde_tipo,
                m.material as molde_material,
                pl.maquina_id
            FROM producao_lotes pl
            LEFT JOIN moldes m ON m.id = pl.molde_id
            WHERE pl.status = 'concluido'
              AND pl.quantidade_planejada > 0
            ORDER BY pl.data_inicio DESC
            LIMIT 500
        """)
        
        if len(rows) < 10:
            return {"error": "Dados insuficientes para treino (mínimo 10 lotes)"}
        
        df = pd.DataFrame([dict(r) for r in rows])
        
        # Features numéricas
        features = ['quantidade_planejada', 'tempo_ciclo_segundos', 'oee_calculado']
        df_features = df[features].fillna(0)
        
        # Target: taxa de defeitos > 5%
        df['taxa_defeitos'] = (df['quantidade_defeituosa'] / df['quantidade_planejada']).fillna(0)
        df['tem_defeito'] = (df['taxa_defeitos'] > 0.05).astype(int)
        
        X = df_features.values
        y = df['tem_defeito'].values
        
        # Modelo simples (n_estimators=10, max_depth=3 = minimal)
        modelo = RandomForestClassifier(
            n_estimators=10,
            max_depth=3,
            random_state=42,
            n_jobs=1  # Evita warnings
        )
        
        modelo.fit(X, y)
        
        accuracy = modelo.score(X, y)
        
        # Importância das features
        importancia = dict(zip(features, modelo.feature_importances_))
        importancia = {k: round(v * 100, 1) for k, v in importancia.items()}
        
        # Salvar modelo
        modelo_path = Path(__file__).parent / "model_defeitos.pkl"
        with open(modelo_path, 'wb') as f:
            pickle.dump({
                'modelo': modelo,
                'features': features,
                'acuracia': accuracy,
                'importancia': importancia,
                'data_treino': hoje()
            }, f)
        
        log(AGENT, f"✅ Modelo treinado - Accuracy: {accuracy:.1%}")
        
        return {
            "success": True,
            "accuracy": round(accuracy * 100, 1),
            "importancia": importancia,
            "data_treino": hoje(),
            "amostras": len(df)
        }
    return run_async(_go())

def prever_defeitos_lote(lote_data: dict) -> dict:
    """Prevê se lote terá defeitos."""
    if not HAS_ML:
        return {"error": "scikit-learn não instalado"}
    
    try:
        modelo_path = Path(__file__).parent / "model_defeitos.pkl"
        
        if not modelo_path.exists():
            return {"error": "Modelo não treinado. Treine primeiro com treinar_modelo_previsao_defeitos()"}
        
        with open(modelo_path, 'rb') as f:
            modelo_data = pickle.load(f)
        
        modelo = modelo_data['modelo']
        features = modelo_data['features']
        
        # Criar DataFrame com os dados do lote
        import numpy as np
        X = np.array([[
            lote_data.get('quantidade_planejada', 0),
            lote_data.get('tempo_ciclo_segundos', 0),
            lote_data.get('oee_calculado', 0)
        ]])
        
        # Prever probabilidade de defeito
        prob = modelo.predict_proba(X)[0][1]
        risco = "alto" if prob > 0.3 else "normal"
        
        return {
            "sku": lote_data.get('sku', 'DESCONHECIDO'),
            "probabilidade_defeito": round(prob * 100, 1),
            "risco": risco,
            "recomendacao": _gerar_recomendacao(risco, prob),
            "modelo_acuracia": modelo_data['acuracia']
        }
    except Exception as e:
        return {"error": f"Erro ao prever: {str(e)}"}

def _gerar_recomendacao(risco: str, prob: float) -> str:
    """Gera recomendação baseada no risco."""
    if risco == "alto":
        if prob > 0.5:
            return "ALERTA: Reduzir velocidade, aumentar inspeção"
        elif prob > 0.3:
            return "ATENÇÃO: Monitorar qualidade de perto"
        else:
            return "Considerar ajuste de parâmetros"
    else:
        return "Normal: Proceder com produção padrão"

if __name__ == "__main__":
    log(AGENT, "Auto-teste")
    
    if HAS_ML:
        # Treinar modelo (se houver dados)
        resultado = treinar_modelo_previsao_defeitos()
        print("Treinamento:", resultado)
        
        # Testar previsão
        if resultado.get("success"):
            teste = prever_defeitos_lote({
                "sku": "TEST-SKU",
                "quantidade_planejada": 500,
                "tempo_ciclo_segundos": 30,
                "oee_calculado": 85.0
            })
            print("Previsão teste:", teste)
    else:
        print("⚠️ Instale scikit-learn para usar ML")