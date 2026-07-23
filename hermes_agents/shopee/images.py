"""
Shopee Images — media upload.
"""
import sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import requests
from core import log
from .auth import configurado, _sign, _base_url, AGENT


def upload_image(image_bytes: bytes, filename: str, loja_id: int = None) -> dict:
    """Envia uma imagem para a Shopee (media_space/upload_image). Retorna image_id,
    que e' usado em add_item/update_item — a Shopee nao aceita URL externa direto."""
    if not configurado(loja_id):
        return {"error": "Shopee não configurado"}
    path = "/api/v2/media_space/upload_image"
    sig = _sign(path, loja_id)
    url = f"{_base_url()}/media_space/upload_image"
    params = {
        "partner_id": sig["partner_id"], "timestamp": sig["timestamp"],
        "access_token": sig["access_token"], "shop_id": sig["shop_id"], "sign": sig["sign"],
    }
    try:
        r = requests.post(url, params=params, files={"image": (filename, image_bytes)}, timeout=60)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log(AGENT, f"Erro upload_image: {e}")
        return {"error": str(e)}
