"""
Memory Core — AG-09 Extended
Fluxo: Pergunta → Agente → Memória → Histórico → Aprendizado → Resposta

Gerencia o ciclo completo de memória conversacional:
  store()   — salva interação (pergunta, resposta, agente, categoria, sucesso)
  recall()  — busca interações similares por keyword matching + recentidade
  history() — histórico recente por agente/categoria
  learn()   — identifica padrões de sucesso para melhorar respostas futuras
  context() — gera contexto de memória para injetar em novas perguntas
"""
import re
import json
from datetime import datetime, date
from core import get_db, run_async, log, hoje

AGENT = "AG-09 | Memory Core"

# ── Auto-migration ──

def _ensure_table():
    """Cria a tabela de memória se não existir."""
    async def _go():
        db = await get_db()
        await db.execute("""
            CREATE TABLE IF NOT EXISTS memoria_interacoes (
                id SERIAL PRIMARY KEY,
                query TEXT NOT NULL,
                response TEXT,
                agent_id VARCHAR(20) NOT NULL,
                category VARCHAR(50) DEFAULT 'geral',
                success BOOLEAN DEFAULT NULL,
                metadata JSONB DEFAULT '{}',
                embedding FLOAT[] DEFAULT '{}',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_memoria_agent ON memoria_interacoes(agent_id)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_memoria_category ON memoria_interacoes(category)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_memoria_created ON memoria_interacoes(created_at DESC)
        """)
    run_async(_go())


_ensure_table()


# ── Tokenização simples ──

STOPWORDS = {"de", "da", "do", "em", "no", "na", "e", "que", "o", "a", "os", "as",
             "um", "uma", "para", "com", "por", "se", "não", "é", "foi", "está",
             "the", "is", "a", "an", "and", "or", "in", "to", "of", "for"}

def _tokenize(text: str) -> list[str]:
    words = re.findall(r'[a-záàâãéêíóôõúç]{3,}', text.lower())
    return [w for w in words if w not in STOPWORDS]


def _keyword_score(query_tokens: list[str], doc_tokens: list[str]) -> float:
    if not query_tokens:
        return 0.0
    matches = sum(1 for t in query_tokens if t in doc_tokens)
    return matches / len(query_tokens)


# ── API principal ──

def store(query: str, response: str | None, agent_id: str,
          category: str = "geral", success: bool | None = None,
          metadata: dict | None = None) -> int | None:
    """Salva uma interação na memória. Retorna o ID."""
    async def _go():
        db = await get_db()
        row = await db.fetchrow("""
            INSERT INTO memoria_interacoes (query, response, agent_id, category, success, metadata)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb)
            RETURNING id
        """, query, response, agent_id, category, success,
            json.dumps(metadata or {}, ensure_ascii=False))
        return row["id"] if row else None
    return run_async(_go(), default=None)


def recall(query: str, agent_id: str | None = None,
           category: str | None = None, limit: int = 5) -> list[dict]:
    """
    Busca interações similares na memória.
    Usa keyword matching + recentidade para ranking.
    """
    query_tokens = _tokenize(query)
    if not query_tokens:
        return _recent(agent_id, category, limit)

    async def _go():
        db = await get_db()
        where = []
        params: list = []
        p_idx = 0

        if agent_id:
            p_idx += 1
            where.append(f"agent_id = ${p_idx}")
            params.append(agent_id)
        if category:
            p_idx += 1
            where.append(f"category = ${p_idx}")
            params.append(category)

        where_clause = " AND ".join(where) if where else "1=1"

        # Busca candidatos por qualquer token (filtro largo)
        token_filters = []
        for t in query_tokens[:5]:
            p_idx += 1
            token_filters.append(f"query ILIKE ${p_idx}")
            params.append(f"%{t}%")

        token_clause = " OR ".join(token_filters) if token_filters else "1=1"
        full_where = f"({where_clause}) AND ({token_clause})"

        rows = await db.fetch(f"""
            SELECT id, query, response, agent_id, category, success, metadata, created_at
            FROM memoria_interacoes
            WHERE {full_where}
            ORDER BY created_at DESC
            LIMIT {limit * 3}
        """, *params)

        # Re-ranking por keyword overlap
        scored = []
        for r in rows:
            doc_tokens = _tokenize(r["query"])
            score = _keyword_score(query_tokens, doc_tokens)
            # Boost para interações bem-sucedidas
            if r["success"]:
                score *= 1.2
            scored.append((score, dict(r)))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [s[1] for s in scored[:limit]]

    return run_async(_go())


def _recent(agent_id: str | None = None,
            category: str | None = None, limit: int = 5) -> list[dict]:
    """Fallback: retorna interações mais recentes."""
    async def _go():
        db = await get_db()
        where = []
        params = []
        p = 0
        if agent_id:
            p += 1
            where.append(f"agent_id = ${p}")
            params.append(agent_id)
        if category:
            p += 1
            where.append(f"category = ${p}")
            params.append(category)
        clause = " AND ".join(where) if where else "1=1"
        rows = await db.fetch(f"""
            SELECT id, query, response, agent_id, category, success, metadata, created_at
            FROM memoria_interacoes
            WHERE {clause}
            ORDER BY created_at DESC
            LIMIT $${p+1}
        """, *params, limit)
        return [dict(r) for r in rows]
    return run_async(_go())


def history(agent_id: str | None = None, category: str | None = None,
            limit: int = 20, days: int = 90) -> list[dict]:
    """Histórico recente de interações."""
    async def _go():
        db = await get_db()
        where = [f"created_at >= CURRENT_DATE - {days}"]
        params = []
        p = 0
        if agent_id:
            p += 1
            where.append(f"agent_id = ${p}")
            params.append(agent_id)
        if category:
            p += 1
            where.append(f"category = ${p}")
            params.append(category)
        clause = " AND ".join(where)
        rows = await db.fetch(f"""
            SELECT id, query, response, agent_id, category, success, created_at
            FROM memoria_interacoes
            WHERE {clause}
            ORDER BY created_at DESC
            LIMIT $${p+1}
        """, *params, limit)
        return [dict(r) for r in rows]
    return run_async(_go())


def learn(agent_id: str | None = None, category: str | None = None,
          min_occurrences: int = 2) -> list[dict]:
    """
    Identifica padrões de sucesso — queries similares que geraram respostas boas.
    Retorna padrões aprendidos para melhorar respostas futuras.
    """
    async def _go():
        db = await get_db()
        where = ["success = TRUE"]
        params = []
        p = 0
        if agent_id:
            p += 1
            where.append(f"agent_id = ${p}")
            params.append(agent_id)
        if category:
            p += 1
            where.append(f"category = ${p}")
            params.append(category)
        clause = " AND ".join(where)

        rows = await db.fetch(f"""
            SELECT query, response, agent_id, category, COUNT(*) as cnt
            FROM memoria_interacoes
            WHERE {clause}
            GROUP BY query, response, agent_id, category
            HAVING COUNT(*) >= ${p+1}
            ORDER BY cnt DESC
            LIMIT 10
        """, *params, min_occurrences)
        return [dict(r) for r in rows]
    return run_async(_go())


def context(query: str, agent_id: str | None = None,
            category: str | None = None) -> str:
    """
    Gera um bloco de contexto de memória para injetar no prompt do agente.
    Inclui: interações similares + padrões aprendidos.
    """
    recalled = recall(query, agent_id, category, limit=3)
    patterns = learn(agent_id, category, min_occurrences=2)

    parts = []

    if patterns:
        parts.append("📚 **Padrões aprendidos (interações bem-sucedidas):**")
        for p in patterns[:3]:
            parts.append(f"  → Q: {p['query'][:120]}")
            resp_short = (p.get('response') or '')[:150]
            parts.append(f"    R: {resp_short}")

    if recalled:
        parts.append("🧠 **Memória recente (interações similares):**")
        for r in recalled:
            parts.append(f"  → [{r['agent_id']}] {r['query'][:120]}")
            resp_short = (r.get('response') or '')[:150]
            parts.append(f"    R: {resp_short}")

    return "\n".join(parts) if parts else ""


def stats() -> dict:
    """Estatísticas da memória."""
    async def _go():
        db = await get_db()
        total = await db.fetchval("SELECT COUNT(*) FROM memoria_interacoes")
        success_count = await db.fetchval(
            "SELECT COUNT(*) FROM memoria_interacoes WHERE success = TRUE")
        by_agent_rows = await db.fetch("""
            SELECT agent_id, COUNT(*) as cnt
            FROM memoria_interacoes
            GROUP BY agent_id
            ORDER BY cnt DESC
        """)
        return {
            "total_interactions": total or 0,
            "success_rate": round(success_count / max(total, 1) * 100, 1),
            "by_agent": [dict(r) for r in (by_agent_rows or [])],
        }
    return run_async(_go())


if __name__ == "__main__":
    log(AGENT, "Auto-teste Memory Core")
    mid = store("Qual produto devo lançar?", "Sugiro o SKU XT-300 baseado em tendências",
                agent_id="ag_01", category="produto", success=True)
    log(AGENT, f"Stored: id={mid}")

    found = recall("produto lançar", agent_id="ag_01")
    log(AGENT, f"Recall: {len(found)} resultados")

    h = history(category="produto")
    log(AGENT, f"History: {len(h)} entradas")

    learned = learn(category="produto")
    log(AGENT, f"Learned patterns: {len(learned)}")

    ctx = context("Qual produto devo lançar?", agent_id="ag_01")
    log(AGENT, f"Context:\n{ctx[:300]}")

    s = stats()
    log(AGENT, f"Stats: {s}")
