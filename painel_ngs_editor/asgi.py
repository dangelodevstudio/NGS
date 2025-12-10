import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'painel_ngs_editor.settings')

application = get_asgi_application()
