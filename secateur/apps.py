from django.apps import AppConfig


class SecateurConfig(AppConfig):
    name = "secateur"

    def ready(self) -> None:
        import secateur.signals

        return super().ready()
