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
# Vercel Deployment Force Update: 2026-04-16T13:00:00

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
    
    # Executa migracoes somente quando explicitamente solicitado.
    # Rodar migrate em todo cold start da Vercel deixa o painel lento.
    if os.environ.get('VERCEL') and os.environ.get('AUTO_MIGRATE', 'false').lower() == 'true':
        try:
            from django.core.management import call_command
            print("Verificando migrações na Vercel...")
            call_command('migrate', '--noinput')
            
            # Cria secretarias padrão se não existirem
            from admin_panel.models import Secretaria
            if not Secretaria.objects.exists():
                from django.utils.text import slugify
                print("Criando secretarias padrão...")
                secretarias_padrao = [
                    {"nome": "Gabinete do Prefeito", "icone": "bi-person-badge", "cor": "#003B70"},
                    {"nome": "Secretaria de Saúde", "icone": "bi-heart-pulse", "cor": "#dc3545"},
                    {"nome": "Secretaria de Educação", "icone": "bi-book", "cor": "#0d6efd"},
                    {"nome": "Secretaria de Fazenda", "icone": "bi-cash-coin", "cor": "#198754"},
                    {"nome": "Secretaria de Obras", "icone": "bi-cone-striped", "cor": "#fd7e14"},
                    {"nome": "Secretaria de Assistência Social", "icone": "bi-people", "cor": "#6f42c1"},
                    {"nome": "Secretaria de Administração", "icone": "bi-briefcase", "cor": "#6c757d"},
                    {"nome": "Procuradoria Geral", "icone": "bi-shield-check", "cor": "#212529"},
                ]
                for sec_data in secretarias_padrao:
                    Secretaria.objects.get_or_create(
                        nome=sec_data["nome"],
                        defaults={
                            "slug": slugify(sec_data["nome"]),
                            "icone": sec_data["icone"],
                            "cor": sec_data["cor"]
                        }
                    )
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
