import os
import sys
from pathlib import Path
from django.core.wsgi import get_wsgi_application  # type: ignore

# Caminho raiz do projeto
BASE_DIR = Path(__file__).resolve().parent.parent

# Garante que o projeto está no PYTHONPATH
sys.path.append(str(BASE_DIR))

# Define o settings do Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "controle_contratos.settings")

# Inicializa a aplicação WSGI (IMPORTANTE: nome 'app' para Vercel)
# Vercel Deployment Force Update: 2026-04-16T13:30:00

# Vercel's static analyzer needs these at the top level
app = None
application = None
handler = None

try:
    # Garante que o Django está pronto antes de qualquer comando
    import django
    django.setup()
    
    # Obtém a aplicação WSGI
    app = get_wsgi_application()
    application = app
    handler = app
    
    # Verificação rápida de secretarias na Vercel (Roda mesmo sem AUTO_MIGRATE para garantir a correção)
    if os.environ.get('VERCEL'):
        try:
            from admin_panel.models import Secretaria
            if not Secretaria.objects.exists() or Secretaria.objects.filter(nome="Secretaria de Administração").exists():
                print("Inconsistência nas secretarias detectada. Corrigindo...")
                from django.core.management import call_command
                call_command('migrate', 'admin_panel', '0006_normalize_secretarias', '--noinput')
                
                import seed_secretarias
                seed_secretarias.seed_secretarias()
        except Exception as e:
            print(f"Erro ao verificar/corrigir secretarias: {e}")

    # Executa migracoes somente quando explicitamente solicitado.
    # Rodar migrate em todo cold start da Vercel deixa o painel lento.
    if os.environ.get('VERCEL') and os.environ.get('AUTO_MIGRATE', 'false').lower() == 'true':
        try:
            from django.core.management import call_command
            print("Verificando migrações na Vercel...")
            call_command('migrate', '--noinput')
            print("Processo de inicialização concluído!")
        except Exception as e_mig:
            print(f"Erro na inicialização (migrações): {e_mig}")

except Exception as e:
    print(f"Erro crítico ao carregar aplicação WSGI: {e}")
    def error_app(environ, start_response):
        status = '500 Internal Server Error'
        output = f'Erro de Inicialização Django: {str(e)}'.encode('utf-8')
        response_headers = [('Content-type', 'text/plain'), ('Content-Length', str(len(output)))]
        start_response(status, response_headers)
        return [output]
    app = error_app
    application = app
    handler = app
