from django.apps import AppConfig


class SecateurConfig(AppConfig):
    name = "secateur"

    def ready(self):
        import secateur.signals

        return super().ready()
