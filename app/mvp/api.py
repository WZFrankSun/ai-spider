from app.monitoring.api.routes import MonitoringContainer, create_monitoring_app


def create_app():
    return create_monitoring_app(MonitoringContainer.demo(), legacy_auto_recover=True)
