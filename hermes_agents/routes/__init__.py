from flask import Flask


def register_blueprints(app: Flask):
    from .auth import auth_bp
    from .health import health_bp
    from .agents_core import agents_core_bp
    from .agents_ops import agents_ops_bp
    from .config_routes import config_bp
    from .integrations import integrations_bp
    from .business import business_bp
    from .hermes import hermes_bp
    from .shopee_ads import shopee_ads_bp
    from .catalog import catalog_bp
    from .webhooks import webhooks_bp, webhook_bp
    from .integrations import bling_bp
    from .estoque import estoque_bp, workflows_bp
    from .agent_executor import hermes_bp as agent_hermes_bp, memory_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(agents_core_bp)
    app.register_blueprint(agents_ops_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(integrations_bp)
    app.register_blueprint(business_bp)
    app.register_blueprint(hermes_bp)
    app.register_blueprint(shopee_ads_bp)
    app.register_blueprint(catalog_bp)
    app.register_blueprint(webhooks_bp)
    app.register_blueprint(webhook_bp)
    app.register_blueprint(bling_bp)
    app.register_blueprint(estoque_bp)
    app.register_blueprint(workflows_bp)
    app.register_blueprint(agent_hermes_bp)
    app.register_blueprint(memory_bp)
