"""Midia da loja (logo/banner/fotos/galeria/video) — wrapper fino sobre
core/documentos.py, que ja resolve armazenamento fisico real (disco +
tabela "documentos"). Nao existe tabela nova aqui: "tipo" e' guardado na
coluna "tags" ja existente em documentos, filtrando por
entidade_tipo="loja" + entidade_id=loja_id."""
from core import documentos

TIPOS_VALIDOS = ("logo", "banner", "foto_fachada", "foto_interna", "galeria", "video")


def vincular(loja_id: int, tipo: str, file_data: bytes, nome_original: str,
             mime_type: str = "application/octet-stream", criado_por: str = "") -> dict:
    if tipo not in TIPOS_VALIDOS:
        return {"error": f"tipo invalido. Use um de: {', '.join(TIPOS_VALIDOS)}"}
    return documentos.upload(
        file_data, nome_original, entidade_tipo="loja", entidade_id=loja_id,
        criado_por=criado_por, mime_type=mime_type, tags=tipo,
    )


def listar(loja_id: int, tipo: str = None) -> list:
    itens = documentos.listar(entidade_tipo="loja", entidade_id=loja_id)
    if tipo:
        itens = [i for i in itens if i.get("tags") == tipo]
    return itens


def remover(documento_id: int, loja_id: int = None) -> dict:
    """loja_id (quando informado) valida que a midia pertence de fato a essa
    loja antes de apagar — sem isso, quem tem configuracoes.editar consegue
    apagar midia de QUALQUER loja so' trocando o <id> na URL, ja que
    documentos.deletar() so' olha o documento_id (IDOR)."""
    if loja_id is not None:
        pertence = any(item.get("id") == documento_id for item in listar(loja_id))
        if not pertence:
            return {"error": "Midia nao encontrada para esta loja"}
    return documentos.deletar(documento_id)
