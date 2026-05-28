"""
URL configuration for controle_contratos project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from admin_panel.views import CustomLoginView
import os
from datetime import datetime

def debug_secretarias_view(request):
    from admin_panel.models import Secretaria
    from django.db import connection
    
    # Run forced normalization if requested via query param
    force_run = request.GET.get('force') == 'true'
    logs = []
    
    if force_run:
        try:
            from django.core.management import call_command
            call_command('migrate', 'admin_panel', '0006_normalize_secretarias', '--noinput')
            logs.append("Migração 0006_normalize_secretarias executada.")
            
            import seed_secretarias
            seed_secretarias.seed_secretarias()
            logs.append("Seed de secretarias executado.")
        except Exception as e:
            logs.append(f"Erro ao forçar correção: {str(e)}")

    secretarias = list(Secretaria.objects.all().values('id', 'nome', 'slug'))
    
    db_engine = settings.DATABASES['default']['ENGINE']
    db_name = settings.DATABASES['default'].get('NAME', 'unknown')
    if isinstance(db_name, str) and 'supabase' in db_name:
        db_name = '[CENSORED_SUPABASE_URL]'
    elif isinstance(db_name, str) and db_name.startswith('postgres://'):
        db_name = '[CENSORED_POSTGRES_URL]'
        
    db_url_env = os.environ.get('DATABASE_URL')
    has_db_url = bool(db_url_env)
        
    return JsonResponse({
        'timestamp': datetime.now().isoformat(),
        'environment': {
            'vercel': os.environ.get('VERCEL') == '1',
            'debug': settings.DEBUG,
        },
        'database': {
            'engine': db_engine,
            'name_type': str(db_name),
            'has_database_url_env': has_db_url,
            'vendor': connection.vendor,
        },
        'actions': logs,
        'secretarias': {
            'total': len(secretarias),
            'items': secretarias
        }
    })

urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/login/', CustomLoginView.as_view(), name='login'),
    path('auth/', include('django.contrib.auth.urls')),
    path('admin-panel/', include('admin_panel.urls')),
    path('api/debug-secretarias/', debug_secretarias_view, name="debug_secretarias"),
    path('', include('contratos.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
