from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from functools import wraps
import time

def rate_limit(key_prefix, limit=5, period=60):
    """
    Simples rate limiting usando o cache do Django.
    limit: número de requisições permitidas
    period: período em segundos
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            try:
                # Usar IP do usuário como chave
                ip = request.META.get('REMOTE_ADDR')
                key = f"rate_limit_{key_prefix}_{ip}"
                
                # Obter histórico de requisições
                try:
                    requests = cache.get(key, [])
                    if requests is None:
                        requests = []
                except:
                    requests = []
                    
                now = time.time()
                
                # Filtrar requisições fora do período
                requests = [r for r in requests if now - r < period]
                
                if len(requests) >= limit:
                    msg = "Muitas requisições. Tente novamente mais tarde."
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.path.endswith('.json'):
                        return JsonResponse({'status': 'error', 'error': msg}, status=429)
                    
                    # Renderiza template amigável se possível
                    from django.shortcuts import render
                    try:
                        return render(request, 'admin_panel/error_429.html', {'message': msg}, status=429)
                    except:
                        return HttpResponse(msg, status=429)
                
                # Adicionar nova requisição e atualizar cache
                requests.append(now)
                cache.set(key, requests, period)
            except Exception as e:
                # Se o cache falhar, loga o erro mas permite a execução da view
                # para não derrubar o sistema por causa do rate limit
                print(f"ERRO RATE LIMIT (Cache): {e}")
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
