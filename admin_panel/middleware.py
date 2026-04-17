import json
from django.utils.deprecation import MiddlewareMixin
from .models import AuditLog
from django.contrib.contenttypes.models import ContentType

class AuditMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        try:
            if request.method in ['POST', 'DELETE'] and request.user.is_authenticated:
                # Ignorar visualizações que podem ser barulhentas ou sensíveis
                if any(path in request.path for path in ['login', 'logout', 'verify-2fa']):
                    return None
                
                # O log real é feito via sinais ou explicitamente nas views
                # Este middleware pode ser usado para capturar metadados se necessário
                pass
        except Exception as e:
            print(f"ERRO AuditMiddleware: {e}")
        return None

    def process_response(self, request, response):
        return response
