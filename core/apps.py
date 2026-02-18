from django.apps import AppConfig

class CoreConfig(AppConfig):
    """
    AppConfig for the 'core' application
    """

    # the type of the automatic PK for new models
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        from . import signals  # we avoid cyclic imports during startup and
                               # make sure that the models and app registry are initialized;
