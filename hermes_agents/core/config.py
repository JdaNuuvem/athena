"""
Configurações unificadas para APIs (Telegram, Bling, Shopee)
Tudo configurável via frontend - não usa .env
"""
from typing import Optional
from pathlib import Path
import json

CONFIG_PATH = Path(__file__).parent.parent / "config" / "api_config.json"

# Inicializar configurações
_config = {
    "telegram": {
        "token": "",
        "webhook_url": "https://177.7.45.242:8000/telegram/webhook"
    },
    "bling": {
        "api_key": "",
        "api_url": "https://bling.com.br/Api/v3"
    },
    "shopee": {
        "partner_id": "",
        "shop_id": "",
        "api_key": "",
        "access_token": ""
    },
    "whatsapp": {
        "api_url": "http://localhost:8080",
        "api_key": "",
        "instance_name": "hermes"
    }
}

def _load_config():
    """Carrega configurações do arquivo se existir."""
    global _config
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, 'r') as f:
                loaded = json.load(f)
                _config.update(loaded)
        except Exception:
            pass

def _save_config():
    """Salva configurações no arquivo."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, 'w') as f:
        json.dump(_config, f, indent=2)

def get_config(sistema: str, chave: str) -> Optional[str]:
    """Obtém configuração específica."""
    return _config.get(sistema, {}).get(chave, "")

def set_config(sistema: str, chave: str, valor: str):
    """Define configuração específica."""
    if sistema not in _config:
        _config[sistema] = {}
    _config[sistema][chave] = valor
    _save_config()

def get_all_config() -> dict:
    """Retorna todas as configurações."""
    return _config

def set_config_bulk(sistema: str, configs: dict):
    """Define múltiplas configurações de um sistema."""
    if sistema not in _config:
        _config[sistema] = {}
    _config[sistema].update(configs)
    _save_config()

# Carregar ao iniciar
_load_config()