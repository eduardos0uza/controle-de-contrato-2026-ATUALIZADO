import json
import os
import subprocess
import time
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.db.models import Count, Sum, Q
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.core.cache import cache
from django.conf import settings
from django.core.mail import send_mail
from django.contrib.auth.views import LoginView
from django.core.exceptions import ObjectDoesNotExist
from .models import AuditLog, SystemSetting, UserProfile, Post, Page, Media, Secretaria
from .forms import UserForm, UserProfileForm, SystemSettingForm, PostForm, PageForm, MediaForm
from .utils import log_audit
from contratos.models import Contract, ContractStatus, AlertStatus, ContractItem
from contratos.views import get_user_contracts

User = get_user_model()

def get_user_queryset(user):
    """Retorna o queryset de usuários que o usuário logado pode gerenciar."""
    if user.is_superuser:
        return User.objects.all()
    try:
        profile = user.profile
        if profile and profile.secretaria:
            return User.objects.filter(profile__secretaria=profile.secretaria)
    except (ObjectDoesNotExist, AttributeError):
        pass
    return User.objects.none()

def get_audit_log_queryset(user):
    """Retorna o queryset de logs de auditoria que o usuário logado pode ver."""
    if user.is_superuser:
        return AuditLog.objects.all()
    try:
        profile = user.profile
        if profile and profile.secretaria:
            # Logs de usuários da mesma secretaria
            return AuditLog.objects.filter(usuario__profile__secretaria=profile.secretaria)
    except (ObjectDoesNotExist, AttributeError):
        pass
    return AuditLog.objects.none()

# Decorator para permissão de administrador
def admin_only(view_func):
    def wrapper(request, *args, **kwargs):
        try:
            if not request.user.is_superuser and not request.user.groups.filter(name='administrador').exists():
                messages.error(request, "Acesso negado. Você precisa ser um administrador.")
                return redirect('contratos:dashboard')
        except Exception as e:
            print(f"ERRO DECORATOR admin_only: {e}")
            # Em caso de erro na checagem, por segurança redireciona para o dashboard comum
            return redirect('contratos:dashboard')
        return view_func(request, *args, **kwargs)
    return login_required(wrapper)

import random
from .security import rate_limit

def send_2fa_code(user, code):
    """Envia o código 2FA via e-mail ou loga no console se não configurado."""
    subject = f"Seu código de verificação Hiden Systems: {code}"
    message = f"Olá {user.username},\n\nSeu código de verificação para acesso ao painel administrativo é: {code}\n\nEste código expira ao fechar a sessão."
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user.email]
    
    try:
        # Tenta enviar e-mail se configurado (mesmo que seja Console Backend)
        send_mail(subject, message, from_email, recipient_list, fail_silently=False)
        return True
    except Exception as e:
        # Fallback para log no console se falhar ou não estiver configurado
        print(f"DEBUG: Falha ao enviar e-mail. Código 2FA para {user.username}: {code} (Erro: {str(e)})")
        return False

class CustomLoginView(LoginView):
    template_name = 'registration/login.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['secretarias'] = Secretaria.objects.all().order_by('nome')
        return context

    def form_valid(self, form):
        selected_secretaria = self.request.POST.get('secretaria')
        user = form.get_user()
        
        # Validação para Administrador Geral
        if selected_secretaria == 'admin':
            if not user.is_superuser and not user.groups.filter(name='administrador').exists():
                messages.error(self.request, "Acesso negado: Este usuário não tem privilégios de Administrador Geral.")
                return self.form_invalid(form)
            return super().form_valid(form)
            
        # Validação para Secretaria específica
        try:
            if not selected_secretaria:
                messages.error(self.request, "Por favor, selecione uma secretaria.")
                return self.form_invalid(form)

            secretaria = Secretaria.objects.get(id=selected_secretaria)
            user_profile = getattr(user, 'profile', None)
            if not user_profile or user_profile.secretaria != secretaria:
                # Mesmo que seja superuser, se selecionou uma secretaria específica, 
                # deve estar vinculado a ela ou usar o login de Administrador Geral
                if not user.is_superuser:
                    messages.error(self.request, f"Acesso negado: Este usuário não está vinculado à {secretaria.nome}.")
                    return self.form_invalid(form)
        except (Secretaria.DoesNotExist, ValueError, TypeError, UserProfile.DoesNotExist):
            messages.error(self.request, "Selecione uma secretaria válida.")
            return self.form_invalid(form)

        return super().form_valid(form)

@rate_limit('admin_login', limit=5, period=300)
@login_required
def verify_2fa(request):
    if not hasattr(request.user, 'profile') or not request.user.profile.two_factor_enabled:
        return redirect('admin_panel:dashboard')
        
    if request.method == 'POST':
        # Se for uma solicitação de reenvio
        if request.POST.get('action') == 'resend':
            code = str(random.randint(100000, 999999))
            request.session['two_factor_code'] = code
            request.session['two_factor_code_expires'] = time.time() + 300  # 5 minutos
            send_2fa_code(request.user, code)
            messages.info(request, "Novo código enviado.")
            return redirect('admin_panel:verify_2fa')

        # Verificação do código
        code = request.POST.get('code')
        expires = request.session.get('two_factor_code_expires', 0)
        
        if time.time() > expires:
            messages.error(request, "O código expirou. Solicite um novo.")
            if 'two_factor_code' in request.session:
                del request.session['two_factor_code']
        elif code == request.session.get('two_factor_code'):
            request.session['two_factor_verified'] = True
            del request.session['two_factor_code']
            del request.session['two_factor_code_expires']
            messages.success(request, "Autenticação concluída.")
            return redirect('admin_panel:dashboard')
        else:
            messages.error(request, "Código inválido.")
            
    # Gerar código se não existir ou se expirou
    expires = request.session.get('two_factor_code_expires', 0)
    if 'two_factor_code' not in request.session or time.time() > expires:
        code = str(random.randint(100000, 999999))
        request.session['two_factor_code'] = code
        request.session['two_factor_code_expires'] = time.time() + 300  # 5 minutos
        send_2fa_code(request.user, code)
        
    context = {
        'expires_in': int(max(0, request.session.get('two_factor_code_expires', 0) - time.time()))
    }
    return render(request, 'admin_panel/verify_2fa.html', context)

def two_factor_required(view_func):
    def wrapper(request, *args, **kwargs):
        try:
            if hasattr(request.user, 'profile') and request.user.profile.two_factor_enabled:
                if not request.session.get('two_factor_verified'):
                    return redirect('admin_panel:verify_2fa')
        except Exception as e:
            print(f"ERRO DECORATOR two_factor_required: {e}")
            # Em caso de erro, por segurança redireciona para verificação
            return redirect('admin_panel:verify_2fa')
        return view_func(request, *args, **kwargs)
    return wrapper

# Dashboard Administrativo
@rate_limit('admin_dashboard', limit=100, period=60)
@admin_only
@two_factor_required
def admin_dashboard(request):
    try:
        # Usuários
        usuarios_queryset = get_user_queryset(request.user)
        primeiro_dia_mes = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        try:
            scope = 'all' if request.user.is_superuser else f"secretaria:{request.user.profile.secretaria_id}"
        except (ObjectDoesNotExist, AttributeError):
            scope = f"user:{request.user.id}"
        
        try:
            user_metrics_key = f'admin_dashboard:user_metrics:{scope}:{primeiro_dia_mes:%Y%m%d}'
            metrics_usuarios = cache.get(user_metrics_key)
            if metrics_usuarios is None:
                metrics_usuarios = usuarios_queryset.aggregate(
                    total=Count('id'),
                    ativos=Count('id', filter=Q(is_active=True)),
                    novos_mes=Count('id', filter=Q(date_joined__gte=primeiro_dia_mes))
                )
                cache.set(user_metrics_key, metrics_usuarios, 60)
            total_usuarios = metrics_usuarios.get('total', 0)
            usuarios_ativos = metrics_usuarios.get('ativos', 0)
            novos_usuarios_mes = metrics_usuarios.get('novos_mes', 0)
        except Exception as e_user_metrics:
            print(f"Erro ao calcular métricas de usuários: {e_user_metrics}")
            total_usuarios = usuarios_ativos = novos_usuarios_mes = 0
        
        # Contratos
        try:
            contratos_queryset = get_user_contracts(request.user).select_related('secretaria', 'criado_por')
            contract_metrics_key = f'admin_dashboard:contract_metrics:{scope}'
            metrics_contratos = cache.get(contract_metrics_key)
            if metrics_contratos is None:
                metrics_contratos = contratos_queryset.aggregate(
                    total=Count('id', distinct=True),
                    vencidos=Count('id', filter=Q(alerta='vencido'), distinct=True),
                    valor_total=Sum('itens__valor_total'),
                )
                cache.set(contract_metrics_key, metrics_contratos, 60)
            total_contratos = metrics_contratos.get('total', 0)
            vencidos = metrics_contratos.get('vencidos', 0)
            valor_total = metrics_contratos.get('valor_total') or 0
        except Exception as e_contract_metrics:
            print(f"Erro ao calcular métricas de contratos: {e_contract_metrics}")
            contratos_queryset = Contract.objects.none()
            total_contratos = vencidos = 0
            valor_total = 0
        
        # Distribuição por status
        try:
            status_labels = dict(ContractStatus.choices)
            status_key = f'admin_dashboard:status:{scope}'
            status_rows = cache.get(status_key)
            if status_rows is None:
                status_rows = list(contratos_queryset.values('status').annotate(total=Count('status')).order_by('status'))
                cache.set(status_key, status_rows, 60)
            status_distribuicao = [
                {
                    'status': row['status'],
                    'label': status_labels.get(row['status'], row['status'] or 'Sem status'),
                    'total': row['total'],
                    'percent': round((row['total'] / total_contratos) * 100) if total_contratos else 0,
                }
                for row in status_rows
            ]
        except Exception as e_status:
            print(f"Erro ao calcular distribuição de status: {e_status}")
            status_distribuicao = []
        
        # CMS stats
        try:
            cms_counts = cache.get('admin_dashboard:cms_counts')
            if cms_counts is None:
                cms_counts = {
                    'total_posts': Post.objects.count(),
                    'total_paginas': Page.objects.count(),
                    'total_midias': Media.objects.count(),
                }
                cache.set('admin_dashboard:cms_counts', cms_counts, 120)
            total_posts = cms_counts.get('total_posts', 0)
            total_paginas = cms_counts.get('total_paginas', 0)
            total_midias = cms_counts.get('total_midias', 0)
        except Exception as e_cms:
            print(f"Erro ao carregar estatísticas CMS: {e_cms}")
            total_posts = total_paginas = total_midias = 0
        
        # Logs e Alertas
        try:
            logs_key = f'admin_dashboard:logs:{scope}'
            logs_recentes = cache.get(logs_key)
            if logs_recentes is None:
                logs_recentes = list(
                    get_audit_log_queryset(request.user)
                    .select_related('usuario')
                    .only('id', 'usuario__username', 'usuario__first_name', 'usuario__last_name', 'acao', 'tabela', 'descricao', 'data_hora')
                    .all()[:6]
                )
                cache.set(logs_key, logs_recentes, 30)
        except Exception as e_logs:
            print(f"Erro ao carregar logs: {e_logs}")
            logs_recentes = []
        
        # Alertas críticos
        try:
            alertas_key = f'admin_dashboard:alertas:{scope}'
            contratos_alertas = cache.get(alertas_key)
            if contratos_alertas is None:
                contratos_alertas = list(
                    contratos_queryset.filter(alerta__in=['vencido', 'vermelho'])
                    .only('id', 'numero_contrato', 'empresa', 'objeto', 'data_vencimento', 'dias_restantes', 'alerta', 'secretaria', 'criado_por')
                    .order_by('data_vencimento')[:5]
                )
                cache.set(alertas_key, contratos_alertas, 45)
        except Exception as e_alerts:
            print(f"Erro ao carregar alertas críticos: {e_alerts}")
            contratos_alertas = []
        
        # Próximos vencimentos
        try:
            vencimentos_key = f'admin_dashboard:vencimentos:{scope}'
            proximos_vencimentos = cache.get(vencimentos_key)
            if proximos_vencimentos is None:
                proximos_vencimentos = list(
                    contratos_queryset.filter(alerta='laranja')
                    .only('id', 'numero_contrato', 'empresa', 'objeto', 'data_vencimento', 'dias_restantes', 'alerta', 'secretaria', 'criado_por')
                    .order_by('data_vencimento')[:5]
                )
                cache.set(vencimentos_key, proximos_vencimentos, 45)
        except Exception as e_prox:
            print(f"Erro ao carregar próximos vencimentos: {e_prox}")
            proximos_vencimentos = []
        
        context = {
            'total_usuarios': total_usuarios,
            'usuarios_ativos': usuarios_ativos,
            'novos_usuarios_mes': novos_usuarios_mes,
            'total_contratos': total_contratos,
            'valor_total': valor_total,
            'vencidos': vencidos,
            'status_distribuicao': status_distribuicao,
            'total_posts': total_posts,
            'total_paginas': total_paginas,
            'total_midias': total_midias,
            'logs_recentes': logs_recentes,
            'contratos_alertas': contratos_alertas,
            'proximos_vencimentos': proximos_vencimentos,
            'active_menu': 'dashboard'
        }
        return render(request, 'admin_panel/dashboard.html', context)
    except Exception as e:
        import traceback
        error_msg = f"Erro no Dashboard Administrativo: {str(e)}\n{traceback.format_exc()}"
        print(f"CRITICAL ERROR: {error_msg}")
        
        if settings.DEBUG:
            return HttpResponse(f"<pre>{error_msg}</pre>", status=500)
        
        # Em produção, usa o template 500.html se disponível
        try:
            return render(request, '500.html', {'error': str(e)}, status=500)
        except:
            # Fallback se o template 500.html falhar
            messages.error(request, "Ocorreu um erro ao carregar o dashboard administrativo. Por favor, tente novamente mais tarde.")
            return redirect('contratos:dashboard')

@admin_only
def debug_info(request):
    """View para diagnosticar problemas no ambiente Vercel."""
    if not request.user.is_superuser:
        return HttpResponse("Acesso negado.", status=403)
        
    info = {
        "user": request.user.username,
        "is_superuser": request.user.is_superuser,
        "debug_mode": settings.DEBUG,
        "database": settings.DATABASES['default']['ENGINE'],
        "vercel_env": os.environ.get('VERCEL'),
        "timezone": timezone.get_current_timezone_name(),
        "now": str(timezone.now()),
        "hoje": str(timezone.localdate()),
    }
    
    try:
        from .models import Secretaria
        info["secretarias_count"] = Secretaria.objects.count()
        from contratos.models import Contract
        info["contratos_count"] = Contract.objects.count()
    except Exception as e:
        info["db_error"] = str(e)
        
    return JsonResponse(info)

# Gerenciamento de Usuários
@admin_only
@two_factor_required
@rate_limit('admin_users', limit=50, period=60)
def user_list(request):
    try:
        q = request.GET.get('q', '')
        users = get_user_queryset(request.user).select_related('profile').prefetch_related('groups').filter(
            Q(username__icontains=q) | 
            Q(email__icontains=q) | 
            Q(first_name__icontains=q) | 
            Q(last_name__icontains=q)
        ).order_by('-date_joined')
        
        paginator = Paginator(users, 10)
        page = request.GET.get('page')
        users_list = paginator.get_page(page)
        
        context = {
            'users': users_list,
            'q': q,
            'active_menu': 'usuarios'
        }
        return render(request, 'admin_panel/user_list.html', context)
    except Exception as e:
        import traceback
        error_msg = f"Erro na Listagem de Usuários: {str(e)}\n{traceback.format_exc()}"
        print(f"CRITICAL ERROR: {error_msg}")
        if settings.DEBUG:
            return HttpResponse(f"<pre>{error_msg}</pre>", status=500)
        try:
            return render(request, '500.html', {'error': str(e)}, status=500)
        except:
            messages.error(request, "Ocorreu um erro ao carregar a listagem de usuários.")
            return redirect('admin_panel:dashboard')

@admin_only
@two_factor_required
@rate_limit('admin_users_edit', limit=20, period=60)
def user_create(request):
    try:
        if request.method == 'POST':
            form = UserForm(request.POST, request_user=request.user)
            profile_form = UserProfileForm(request.POST, request.FILES)
            if form.is_valid() and profile_form.is_valid():
                user = form.save()
                # O perfil já é criado e salvo dentro do método save() do UserForm
                # Então buscamos o perfil que já existe
                profile, _ = UserProfile.objects.get_or_create(user=user)
                
                # Atualiza campos do profile_form no perfil existente
                # Usamos o profile_form apenas para popular os campos extras (cargo, telefone, etc)
                for field in profile_form.fields:
                    if field in request.POST or field in request.FILES:
                        setattr(profile, field, profile_form.cleaned_data.get(field))
                
                # Auto-atribuir secretaria do criador se não for superuser
                if not request.user.is_superuser:
                    try:
                        if hasattr(request.user, 'profile') and request.user.profile.secretaria:
                            profile.secretaria = request.user.profile.secretaria
                    except Exception:
                        pass
                        
                profile.save()
                log_audit(request, 'CREATE', 'User', user.id, f"Criou usuário {user.username}")
                messages.success(request, f"Usuário {user.username} criado com sucesso.")
                return redirect('admin_panel:user_list')
        else:
            form = UserForm(request_user=request.user)
            profile_form = UserProfileForm()
        
        return render(request, 'admin_panel/user_form.html', {'form': form, 'profile_form': profile_form, 'title': 'Novo Usuário'})
    except Exception as e:
        import traceback
        error_msg = f"Erro ao Criar Usuário: {str(e)}\n{traceback.format_exc()}"
        print(f"CRITICAL ERROR: {error_msg}")
        if settings.DEBUG:
            return HttpResponse(f"<pre>{error_msg}</pre>", status=500)
        try:
            return render(request, '500.html', {'error': str(e)}, status=500)
        except:
            messages.error(request, "Ocorreu um erro ao processar a criação de usuário.")
            return redirect('admin_panel:user_list')

@admin_only
@two_factor_required
@rate_limit('admin_users_edit', limit=20, period=60)
def user_update(request, pk):
    try:
        users_permitidos = get_user_queryset(request.user)
        user = get_object_or_404(users_permitidos, pk=pk)
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        if request.method == 'POST':
            form = UserForm(request.POST, instance=user, request_user=request.user)
            profile_form = UserProfileForm(request.POST, request.FILES, instance=profile)
            if form.is_valid() and profile_form.is_valid():
                # Impedir que um gestor de secretaria mude a secretaria de um usuário para outra que não a dele
                if not request.user.is_superuser:
                    try:
                        profile_form.instance.secretaria = request.user.profile.secretaria
                    except Exception:
                        pass
                
                form.save()
                profile_form.save()
                log_audit(request, 'UPDATE', 'User', user.id, f"Atualizou usuário {user.username}")
                messages.success(request, f"Usuário {user.username} atualizado.")
                return redirect('admin_panel:user_list')
        else:
            form = UserForm(instance=user, request_user=request.user)
            profile_form = UserProfileForm(instance=profile)
        
        return render(request, 'admin_panel/user_form.html', {'form': form, 'profile_form': profile_form, 'title': 'Editar Usuário'})
    except Exception as e:
        import traceback
        error_msg = f"Erro ao Atualizar Usuário: {str(e)}\n{traceback.format_exc()}"
        print(f"CRITICAL ERROR: {error_msg}")
        if settings.DEBUG:
            return HttpResponse(f"<pre>{error_msg}</pre>", status=500)
        try:
            return render(request, '500.html', {'error': str(e)}, status=500)
        except:
            messages.error(request, "Ocorreu um erro ao processar a atualização de usuário.")
            return redirect('admin_panel:user_list')

@admin_only
@two_factor_required
@rate_limit('admin_users_edit', limit=10, period=60)
def user_delete(request, pk):
    try:
        users_permitidos = get_user_queryset(request.user)
        user = get_object_or_404(users_permitidos, pk=pk)
        if user == request.user:
            messages.error(request, "Você não pode deletar sua própria conta.")
        else:
            username = user.username
            user.delete()
            log_audit(request, 'DELETE', 'User', pk, f"Deletou usuário {username}")
            messages.success(request, f"Usuário {username} deletado.")
        return redirect('admin_panel:user_list')
    except Exception as e:
        import traceback
        error_msg = f"Erro ao Deletar Usuário: {str(e)}\n{traceback.format_exc()}"
        print(f"CRITICAL ERROR: {error_msg}")
        if settings.DEBUG:
            return HttpResponse(f"<pre>{error_msg}</pre>", status=500)
        try:
            return render(request, '500.html', {'error': str(e)}, status=500)
        except:
            messages.error(request, "Ocorreu um erro ao deletar o usuário.")
            return redirect('admin_panel:user_list')

@admin_only
@two_factor_required
@rate_limit('admin_users_edit', limit=30, period=60)
def user_toggle_status(request, pk):
    try:
        users_permitidos = get_user_queryset(request.user)
        user = get_object_or_404(users_permitidos, pk=pk)
        if user == request.user:
            return JsonResponse({'status': 'error', 'message': 'Não pode alterar seu próprio status.'})
        
        user.is_active = not user.is_active
        user.save()
        status_str = "ativado" if user.is_active else "desativado"
        log_audit(request, 'UPDATE', 'User', user.id, f"Usuário {user.username} foi {status_str}")
        return JsonResponse({'status': 'success', 'is_active': user.is_active})
    except Exception as e:
        print(f"ERRO user_toggle_status: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

# Logs de Auditoria
@admin_only
@two_factor_required
@rate_limit('admin_audit', limit=100, period=60)
def audit_log_list(request):
    try:
        logs = get_audit_log_queryset(request.user).order_by('-data_hora')
        
        # Filtros
        usuario_id = request.GET.get('usuario')
        acao = request.GET.get('acao')
        tabela = request.GET.get('tabela')
        data_inicio = request.GET.get('data_inicio')
        data_fim = request.GET.get('data_fim')
        busca = request.GET.get('q')
        
        if usuario_id:
            logs = logs.filter(usuario_id=usuario_id)
        if acao:
            logs = logs.filter(acao=acao)
        if tabela:
            logs = logs.filter(tabela=tabela)
        if data_inicio:
            logs = logs.filter(data_hora__date__gte=data_inicio)
        if data_fim:
            logs = logs.filter(data_hora__date__lte=data_fim)
        if busca:
            logs = logs.filter(Q(descricao__icontains=busca) | Q(tabela__icontains=busca))

        # Exportação CSV
        if request.GET.get('export') == 'csv':
            try:
                import csv
                from django.http import HttpResponse
                response = HttpResponse(content_type='text/csv')
                response['Content-Disposition'] = 'attachment; filename="logs_auditoria.csv"'
                writer = csv.writer(response)
                writer.writerow(['Data/Hora', 'Usuário', 'Ação', 'Tabela', 'Descrição', 'IP', 'Dados Antigos', 'Dados Novos'])
                for log in logs:
                    writer.writerow([
                        log.data_hora.strftime('%d/%m/%Y %H:%M:%S'),
                        log.usuario.username if log.usuario else 'Sistema',
                        log.get_acao_display(),
                        log.tabela,
                        log.descricao,
                        log.ip_address,
                        log.dados_anteriores,
                        log.dados_novos
                    ])
                return response
            except Exception as e_csv:
                print(f"Erro ao exportar CSV de logs: {e_csv}")
                messages.error(request, "Erro ao gerar arquivo CSV.")

        # Estatísticas Rápidas
        try:
            hoje = timezone.now().date()
            stats = logs.aggregate(
                total_hoje=Count('id', filter=Q(data_hora__date=hoje)),
                criacoes=Count('id', filter=Q(acao='CREATE')),
                edicoes=Count('id', filter=Q(acao='UPDATE')),
                exclusoes=Count('id', filter=Q(acao='DELETE')),
            )
        except Exception as e_stats:
            print(f"Erro ao calcular estatísticas de logs: {e_stats}")
            stats = {'total_hoje': 0, 'criacoes': 0, 'edicoes': 0, 'exclusoes': 0}

        # Opções para os filtros
        try:
            usuarios = cache.get('admin_audit:staff_users')
            if usuarios is None:
                usuarios = list(User.objects.filter(is_staff=True).values('id', 'username').order_by('username'))
                cache.set('admin_audit:staff_users', usuarios, 120)
            acoes = AuditLog.ACTION_CHOICES
        except Exception as e_filters:
            print(f"Erro ao carregar opções de filtro: {e_filters}")
            usuarios = User.objects.none()
            acoes = []

        logs = logs.select_related('usuario', 'usuario__profile', 'usuario__profile__secretaria').only(
            'id', 'usuario__id', 'usuario__username', 'usuario__first_name', 'usuario__last_name',
            'usuario__profile__secretaria__nome', 'acao', 'tabela', 'descricao', 'ip_address',
            'data_hora'
        )

        paginator = Paginator(logs, 20)
        page = request.GET.get('page')
        logs_list = paginator.get_page(page)
        query_params = request.GET.copy()
        query_params.pop('page', None)
        querystring_without_page = query_params.urlencode()
        
        context = {
            'logs': logs_list, 
            'active_menu': 'audit',
            'usuarios': usuarios,
            'acoes': acoes,
            'stats': stats,
            'filtros': request.GET,
            'pagination_range': logs_list.paginator.get_elided_page_range(
                logs_list.number,
                on_each_side=1,
                on_ends=1,
            ),
            'querystring_without_page': querystring_without_page,
        }
        
        return render(request, 'admin_panel/audit_log_list.html', context)
    except Exception as e:
        import traceback
        error_msg = f"Erro na Listagem de Logs: {str(e)}\n{traceback.format_exc()}"
        print(f"CRITICAL ERROR: {error_msg}")
        if settings.DEBUG:
            return HttpResponse(f"<pre>{error_msg}</pre>", status=500)
        try:
            return render(request, '500.html', {'error': str(e)}, status=500)
        except:
            messages.error(request, "Ocorreu um erro ao carregar os logs de auditoria.")
            return redirect('admin_panel:dashboard')

@admin_only
@two_factor_required
@rate_limit('admin_audit_detail', limit=120, period=60)
def audit_log_detail(request, pk):
    log = get_object_or_404(
        get_audit_log_queryset(request.user)
        .select_related('usuario', 'usuario__profile', 'usuario__profile__secretaria')
        .only(
            'id', 'usuario__id', 'usuario__username', 'usuario__first_name', 'usuario__last_name',
            'usuario__profile__secretaria__nome', 'acao', 'tabela', 'descricao', 'ip_address',
            'user_agent', 'data_hora', 'dados_anteriores', 'dados_novos'
        ),
        pk=pk,
    )

    usuario_nome = 'Sistema'
    secretaria_nome = ''
    if log.usuario:
        usuario_nome = log.usuario.get_full_name() or log.usuario.username
        try:
            secretaria_nome = log.usuario.profile.secretaria.nome if log.usuario.profile.secretaria else ''
        except (ObjectDoesNotExist, AttributeError):
            secretaria_nome = ''

    return JsonResponse({
        'id': log.id,
        'usuario': usuario_nome,
        'secretaria': secretaria_nome,
        'acao': log.get_acao_display(),
        'acao_codigo': log.acao,
        'tabela': log.tabela or '-',
        'descricao': log.descricao or '-',
        'ip': log.ip_address or '-',
        'user_agent': log.user_agent or 'Informacoes nao capturadas',
        'data_hora': timezone.localtime(log.data_hora).strftime('%d/%m/%Y %H:%M:%S'),
        'dados_anteriores': log.dados_anteriores or {},
        'dados_novos': log.dados_novos or {},
    }, json_dumps_params={'ensure_ascii': False})

@admin_only
@two_factor_required
@rate_limit('admin_contratos', limit=100, period=60)
def admin_contratos_list(request):
    """Listagem administrativa de todos os contratos com dados de auditoria."""
    try:
        query = request.GET.get('q')
        secretaria_id = request.GET.get('secretaria')
        usuario_id = request.GET.get('usuario')
        status = request.GET.get('status')
        
        # Base QuerySet - Administradores veem tudo (restringido pelo decorator admin_only)
        contratos = Contract.objects.all()

        # Filtros
        if query:
            contratos = contratos.filter(
                Q(numero_contrato__icontains=query) |
                Q(objeto__icontains=query) |
                Q(empresa__icontains=query)
            )
        
        if secretaria_id:
            contratos = contratos.filter(secretaria_id=secretaria_id)
        
        if usuario_id:
            contratos = contratos.filter(criado_por_id=usuario_id)
            
        if status:
            contratos = contratos.filter(status=status)

        # Exportação CSV para Auditoria Completa
        if request.GET.get('export') == 'csv':
            try:
                import csv
                from django.http import HttpResponse
                response = HttpResponse(content_type='text/csv')
                response['Content-Disposition'] = f'attachment; filename="auditoria_contratos_{timezone.now():%Y%m%d}.csv"'
                
                writer = csv.writer(response, delimiter=';', quoting=csv.QUOTE_MINIMAL)
                writer.writerow([
                    'Número', 'Empresa', 'Objeto', 'Secretaria', 'Status', 'Valor', 
                    'Criado Por', 'Criado Em', 'Última Modificação', 'Total de Mods'
                ])
                
                for c in contratos.select_related('criado_por', 'secretaria').prefetch_related('historico'):
                    writer.writerow([
                        c.numero_contrato,
                        c.empresa,
                        c.objeto,
                        c.secretaria.nome if c.secretaria else 'Não definida',
                        c.get_status_display(),
                        f"{c.valor:.2f}".replace('.', ','),
                        c.criado_por.username if c.criado_por else 'Sistema',
                        c.criado_em.strftime('%d/%m/%Y %H:%M'),
                        c.atualizado_em.strftime('%d/%m/%Y %H:%M'),
                        c.historico.count()
                    ])
                return response
            except Exception as e_csv:
                print(f"Erro ao exportar CSV de contratos: {e_csv}")
                messages.error(request, "Erro ao gerar arquivo CSV.")

        contratos_filtrados = contratos
        contratos = (
            contratos_filtrados
            .select_related('criado_por', 'secretaria')
            .annotate(valor_total_calculado=Sum('itens__valor_total'))
            .order_by('-criado_em')
        )
        
        # Paginação
        paginator = Paginator(contratos, 15)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        # Estatísticas Rápidas (Baseadas no QuerySet filtrado)
        try:
            stats_agregadas = contratos_filtrados.aggregate(
                total=Count('id', distinct=True),
                ativos=Count('id', filter=Q(status='ativo'), distinct=True),
                vencendo_30=Count('id', filter=Q(status='ativo', dias_restantes__gt=0, dias_restantes__lte=30), distinct=True),
                vencidos=Count('id', filter=Q(dias_restantes__lt=0), distinct=True),
                valor_total=Sum('itens__valor_total'),
                alerta_normal=Count('id', filter=Q(alerta='normal'), distinct=True),
                alerta_amarelo=Count('id', filter=Q(alerta='amarelo'), distinct=True),
                alerta_laranja=Count('id', filter=Q(alerta='laranja'), distinct=True),
                alerta_vermelho=Count('id', filter=Q(alerta='vermelho'), distinct=True),
                alerta_vencido=Count('id', filter=Q(alerta='vencido'), distinct=True),
            )
            total_count = stats_agregadas.get('total', 0)
            vencidos_count = stats_agregadas.get('vencidos', 0)
            
            stats = {
                'total': total_count,
                'ativos': stats_agregadas.get('ativos', 0),
                'vencendo_30': stats_agregadas.get('vencendo_30', 0),
                'vencidos': vencidos_count,
                'taxa_vencimento': (vencidos_count / total_count * 100) if total_count > 0 else 0,
                'valor_total': stats_agregadas.get('valor_total') or 0,
                'alertas': {
                    'normal': stats_agregadas.get('alerta_normal', 0),
                    'amarelo': stats_agregadas.get('alerta_amarelo', 0),
                    'laranja': stats_agregadas.get('alerta_laranja', 0),
                    'vermelho': stats_agregadas.get('alerta_vermelho', 0),
                    'vencido': stats_agregadas.get('alerta_vencido', 0),
                }
            }
        except Exception as e_stats:
            print(f"Erro ao calcular estatísticas de contratos: {e_stats}")
            stats = {
                'total': 0, 'ativos': 0, 'vencendo_30': 0, 'vencidos': 0, 'taxa_vencimento': 0, 
                'valor_total': 0, 'alertas': {'normal': 0, 'amarelo': 0, 'laranja': 0, 'vermelho': 0, 'vencido': 0}
            }

        context = {
            'contratos': page_obj,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'secretarias': Secretaria.objects.all().order_by('nome'),
            'usuarios': User.objects.only('id', 'username').order_by('username'),
            'query': query,
            'selected_secretaria': secretaria_id,
            'selected_usuario': usuario_id,
            'selected_status': status,
            'stats': stats,
            'active_menu': 'contratos_criados'
        }
        
        return render(request, 'admin_panel/contratos_list.html', context)
    except Exception as e:
        import traceback
        error_msg = f"Erro na Listagem de Contratos: {str(e)}\n{traceback.format_exc()}"
        print(f"CRITICAL ERROR: {error_msg}")
        if settings.DEBUG:
            return HttpResponse(f"<pre>{error_msg}</pre>", status=500)
        try:
            return render(request, '500.html', {'error': str(e)}, status=500)
        except:
            messages.error(request, "Ocorreu um erro ao carregar a listagem de contratos.")
            return redirect('admin_panel:dashboard')

# Configurações do Sistema
@admin_only
@two_factor_required
@rate_limit('admin_settings', limit=50, period=60)
def system_settings(request):
    try:
        settings_queryset = SystemSetting.objects.all()
        
        if request.method == 'POST':
            # Se for uma atualização em massa via AJAX ou Form comum
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'bulk_update' in request.POST:
                for key, value in request.POST.items():
                    if key.startswith('setting_'):
                        setting_id_str = key.replace('setting_', '')
                        if not setting_id_str.isdigit():
                            continue
                        
                        try:
                            setting = SystemSetting.objects.get(id=int(setting_id_str))
                            if setting.valor != value:
                                old_value = setting.valor
                                setting.valor = value
                                setting.save()
                                log_audit(request, 'UPDATE', 'SystemSetting', setting.id, f"Alterou {setting.chave}", old_value, value)
                        except SystemSetting.DoesNotExist:
                            continue
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'status': 'success', 'message': 'Configurações atualizadas.'})
                
                messages.success(request, "Configurações atualizadas.")
                return redirect('admin_panel:system_settings')
                
            # Fallback para criação de nova configuração via Modal
            form = SystemSettingForm(request.POST)
            if form.is_valid():
                form.save()
                log_audit(request, 'CREATE', 'SystemSetting', None, f"Nova configuração: {form.cleaned_data['chave']}")
                messages.success(request, "Nova configuração criada.")
                return redirect('admin_panel:system_settings')
        else:
            form = SystemSettingForm()
        
        # Agrupar por tipo para a interface
        grouped_settings = {}
        for choice_key, choice_label in SystemSetting.SETTING_TYPE_CHOICES:
            grouped_settings[choice_label] = settings_queryset.filter(tipo=choice_key)
        
        return render(request, 'admin_panel/settings.html', {
            'grouped_settings': grouped_settings, 
            'all_settings': settings_queryset,
            'form': form, 
            'active_menu': 'config'
        })
    except Exception as e:
        import traceback
        error_msg = f"Erro nas Configurações: {str(e)}\n{traceback.format_exc()}"
        print(f"CRITICAL ERROR: {error_msg}")
        if settings.DEBUG:
            return HttpResponse(f"<pre>{error_msg}</pre>", status=500)
        try:
            return render(request, '500.html', {'error': str(e)}, status=500)
        except:
            messages.error(request, "Ocorreu um erro ao carregar as configurações do sistema.")
            return redirect('admin_panel:dashboard')

@admin_only
@two_factor_required
def delete_system_setting(request, setting_id):
    try:
        if request.method == 'POST':
            try:
                setting = SystemSetting.objects.get(id=setting_id)
                chave = setting.chave
                setting.delete()
                log_audit(request, 'DELETE', 'SystemSetting', setting_id, f"Excluiu a configuração: {chave}")
                return JsonResponse({'status': 'success', 'message': f'Configuração {chave} excluída com sucesso.'})
            except SystemSetting.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': 'Configuração não encontrada.'}, status=404)
        return JsonResponse({'status': 'error', 'message': 'Método não permitido.'}, status=405)
    except Exception as e:
        print(f"ERRO delete_system_setting: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

# Backup e Restauração
@admin_only
@two_factor_required
@rate_limit('admin_backup', limit=5, period=3600)
def backup_restore(request):
    try:
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        if not os.path.exists(backup_dir):
            try:
                os.makedirs(backup_dir)
            except Exception as e_dir:
                print(f"Erro ao criar diretório de backup: {e_dir}")
                # Em ambientes como Vercel, o sistema de arquivos pode ser read-only
                # Mas o /tmp costuma ser gravável. No entanto, backups locais não são ideais na Vercel.
                
        backups = []
        if os.path.exists(backup_dir):
            for f in os.listdir(backup_dir):
                if f.endswith('.json'):
                    path = os.path.join(backup_dir, f)
                    try:
                        backups.append({
                            'name': f,
                            'size': f"{os.path.getsize(path) / 1024:.2f} KB",
                            'date': timezone.datetime.fromtimestamp(os.path.getctime(path))
                        })
                    except Exception:
                        pass
        
        if request.GET.get('action') == 'create':
            filename = f"backup_{timezone.now():%Y%m%d_%H%M%S}.json"
            filepath = os.path.join(backup_dir, filename)
            try:
                with open(filepath, 'w') as f:
                    subprocess.run(['python', 'manage.py', 'dumpdata', '--exclude', 'auth.permission', '--exclude', 'contenttypes'], stdout=f)
                log_audit(request, 'OTHER', 'System', None, f"Backup criado: {filename}")
                messages.success(request, f"Backup {filename} criado com sucesso.")
            except Exception as e:
                messages.error(request, f"Erro ao criar backup (verifique permissões de escrita): {str(e)}")
            return redirect('admin_panel:backup_restore')
            
        return render(request, 'admin_panel/backup.html', {'backups': backups, 'active_menu': 'backup'})
    except Exception as e:
        import traceback
        error_msg = f"Erro no Backup/Restauração: {str(e)}\n{traceback.format_exc()}"
        print(f"CRITICAL ERROR: {error_msg}")
        if settings.DEBUG:
            return HttpResponse(f"<pre>{error_msg}</pre>", status=500)
        try:
            return render(request, '500.html', {'error': str(e)}, status=500)
        except:
            messages.error(request, "Ocorreu um erro ao processar o backup.")
            return redirect('admin_panel:dashboard')

# Gerenciamento de Conteúdo (Posts)
@admin_only
@two_factor_required
@rate_limit('admin_cms', limit=100, period=60)
def post_list(request):
    try:
        posts = Post.objects.select_related('autor').all().order_by('-data_criacao')
        paginator = Paginator(posts, 10)
        page = request.GET.get('page')
        posts_list = paginator.get_page(page)
        return render(request, 'admin_panel/post_list.html', {'posts': posts_list, 'active_menu': 'conteudo'})
    except Exception as e:
        import traceback
        error_msg = f"Erro na Listagem de Posts: {str(e)}\n{traceback.format_exc()}"
        print(f"CRITICAL ERROR: {error_msg}")
        if settings.DEBUG:
            return HttpResponse(f"<pre>{error_msg}</pre>", status=500)
        try:
            return render(request, '500.html', {'error': str(e)}, status=500)
        except:
            messages.error(request, "Ocorreu um erro ao carregar os posts.")
            return redirect('admin_panel:dashboard')

@admin_only
@two_factor_required
@rate_limit('admin_cms_edit', limit=50, period=60)
def post_create(request):
    try:
        if request.method == 'POST':
            form = PostForm(request.POST)
            if form.is_valid():
                post = form.save(commit=False)
                post.autor = request.user
                post.save()
                log_audit(request, 'CREATE', 'Post', post.id, f"Criou post {post.titulo}")
                messages.success(request, f"Post {post.titulo} criado.")
                return redirect('admin_panel:post_list')
        else:
            form = PostForm()
        return render(request, 'admin_panel/post_form.html', {'form': form, 'title': 'Novo Post', 'active_menu': 'conteudo'})
    except Exception as e:
        import traceback
        error_msg = f"Erro ao Criar Post: {str(e)}\n{traceback.format_exc()}"
        print(f"CRITICAL ERROR: {error_msg}")
        if settings.DEBUG:
            return HttpResponse(f"<pre>{error_msg}</pre>", status=500)
        try:
            return render(request, '500.html', {'error': str(e)}, status=500)
        except:
            messages.error(request, "Ocorreu um erro ao criar o post.")
            return redirect('admin_panel:post_list')

@admin_only
@two_factor_required
@rate_limit('admin_cms_edit', limit=50, period=60)
def post_update(request, pk):
    try:
        post = get_object_or_404(Post, pk=pk)
        if request.method == 'POST':
            form = PostForm(request.POST, instance=post)
            if form.is_valid():
                form.save()
                log_audit(request, 'UPDATE', 'Post', post.id, f"Atualizou post {post.titulo}")
                messages.success(request, f"Post {post.titulo} atualizado.")
                return redirect('admin_panel:post_list')
        else:
            form = PostForm(instance=post)
        return render(request, 'admin_panel/post_form.html', {'form': form, 'title': 'Editar Post', 'active_menu': 'conteudo'})
    except Exception as e:
        import traceback
        error_msg = f"Erro ao Atualizar Post: {str(e)}\n{traceback.format_exc()}"
        print(f"CRITICAL ERROR: {error_msg}")
        if settings.DEBUG:
            return HttpResponse(f"<pre>{error_msg}</pre>", status=500)
        try:
            return render(request, '500.html', {'error': str(e)}, status=500)
        except:
            messages.error(request, "Ocorreu um erro ao atualizar o post.")
            return redirect('admin_panel:post_list')

@admin_only
@two_factor_required
@rate_limit('admin_cms_edit', limit=20, period=60)
def post_delete(request, pk):
    try:
        post = get_object_or_404(Post, pk=pk)
        titulo = post.titulo
        post.delete()
        log_audit(request, 'DELETE', 'Post', pk, f"Deletou post {titulo}")
        messages.success(request, f"Post {titulo} deletado.")
        return redirect('admin_panel:post_list')
    except Exception as e:
        import traceback
        error_msg = f"Erro ao Deletar Post: {str(e)}\n{traceback.format_exc()}"
        print(f"CRITICAL ERROR: {error_msg}")
        if settings.DEBUG:
            return HttpResponse(f"<pre>{error_msg}</pre>", status=500)
        try:
            return render(request, '500.html', {'error': str(e)}, status=500)
        except:
            messages.error(request, "Ocorreu um erro ao deletar o post.")
            return redirect('admin_panel:post_list')

# Gerenciamento de Conteúdo (Páginas)
@admin_only
@two_factor_required
@rate_limit('admin_cms', limit=100, period=60)
def page_list(request):
    try:
        pages = Page.objects.all().order_by('titulo')
        return render(request, 'admin_panel/page_list.html', {'pages': pages, 'active_menu': 'conteudo'})
    except Exception as e:
        import traceback
        error_msg = f"Erro na Listagem de Páginas: {str(e)}\n{traceback.format_exc()}"
        print(f"CRITICAL ERROR: {error_msg}")
        if settings.DEBUG:
            return HttpResponse(f"<pre>{error_msg}</pre>", status=500)
        try:
            return render(request, '500.html', {'error': str(e)}, status=500)
        except:
            messages.error(request, "Ocorreu um erro ao carregar as páginas.")
            return redirect('admin_panel:dashboard')

@admin_only
@two_factor_required
@rate_limit('admin_cms_edit', limit=50, period=60)
def page_create(request):
    try:
        if request.method == 'POST':
            form = PageForm(request.POST)
            if form.is_valid():
                page = form.save()
                log_audit(request, 'CREATE', 'Page', page.id, f"Criou página {page.titulo}")
                messages.success(request, f"Página {page.titulo} criada.")
                return redirect('admin_panel:page_list')
        else:
            form = PageForm()
        return render(request, 'admin_panel/page_form.html', {'form': form, 'title': 'Nova Página', 'active_menu': 'conteudo'})
    except Exception as e:
        import traceback
        error_msg = f"Erro ao Criar Página: {str(e)}\n{traceback.format_exc()}"
        print(f"CRITICAL ERROR: {error_msg}")
        if settings.DEBUG:
            return HttpResponse(f"<pre>{error_msg}</pre>", status=500)
        try:
            return render(request, '500.html', {'error': str(e)}, status=500)
        except:
            messages.error(request, "Ocorreu um erro ao criar a página.")
            return redirect('admin_panel:page_list')

@admin_only
@two_factor_required
@rate_limit('admin_cms_edit', limit=50, period=60)
def page_update(request, pk):
    try:
        page = get_object_or_404(Page, pk=pk)
        if request.method == 'POST':
            form = PageForm(request.POST, instance=page)
            if form.is_valid():
                form.save()
                log_audit(request, 'UPDATE', 'Page', page.id, f"Atualizou página {page.titulo}")
                messages.success(request, f"Página {page.titulo} atualizada.")
                return redirect('admin_panel:page_list')
        else:
            form = PageForm(instance=page)
        return render(request, 'admin_panel/page_form.html', {'form': form, 'title': 'Editar Página', 'active_menu': 'conteudo'})
    except Exception as e:
        import traceback
        error_msg = f"Erro ao Atualizar Página: {str(e)}\n{traceback.format_exc()}"
        print(f"CRITICAL ERROR: {error_msg}")
        if settings.DEBUG:
            return HttpResponse(f"<pre>{error_msg}</pre>", status=500)
        try:
            return render(request, '500.html', {'error': str(e)}, status=500)
        except:
            messages.error(request, "Ocorreu um erro ao atualizar a página.")
            return redirect('admin_panel:page_list')

@admin_only
@two_factor_required
@rate_limit('admin_cms_edit', limit=20, period=60)
def page_delete(request, pk):
    try:
        page = get_object_or_404(Page, pk=pk)
        titulo = page.titulo
        page.delete()
        log_audit(request, 'DELETE', 'Page', pk, f"Deletou página {titulo}")
        messages.success(request, f"Página {titulo} deletada.")
        return redirect('admin_panel:page_list')
    except Exception as e:
        import traceback
        error_msg = f"Erro ao Deletar Página: {str(e)}\n{traceback.format_exc()}"
        print(f"CRITICAL ERROR: {error_msg}")
        if settings.DEBUG:
            return HttpResponse(f"<pre>{error_msg}</pre>", status=500)
        try:
            return render(request, '500.html', {'error': str(e)}, status=500)
        except:
            messages.error(request, "Ocorreu um erro ao deletar a página.")
            return redirect('admin_panel:page_list')

# Gerenciamento de Mídias
@admin_only
@two_factor_required
@rate_limit('admin_cms', limit=100, period=60)
def media_list(request):
    try:
        medias = Media.objects.all().order_by('-data_upload')
        if request.method == 'POST':
            form = MediaForm(request.POST, request.FILES)
            if form.is_valid():
                media = form.save()
                log_audit(request, 'CREATE', 'Media', media.id, f"Upload de mídia: {media.arquivo.name}")
                messages.success(request, "Mídia enviada com sucesso.")
                return redirect('admin_panel:media_list')
        else:
            form = MediaForm()
        return render(request, 'admin_panel/media_list.html', {'medias': medias, 'form': form, 'active_menu': 'conteudo'})
    except Exception as e:
        import traceback
        error_msg = f"Erro na Listagem de Mídias: {str(e)}\n{traceback.format_exc()}"
        print(f"CRITICAL ERROR: {error_msg}")
        if settings.DEBUG:
            return HttpResponse(f"<pre>{error_msg}</pre>", status=500)
        try:
            return render(request, '500.html', {'error': str(e)}, status=500)
        except:
            messages.error(request, "Ocorreu um erro ao carregar as mídias.")
            return redirect('admin_panel:dashboard')

@admin_only
@two_factor_required
@rate_limit('admin_cms_edit', limit=20, period=60)
def media_delete(request, pk):
    try:
        media = get_object_or_404(Media, pk=pk)
        filename = media.arquivo.name
        media.delete()
        log_audit(request, 'DELETE', 'Media', pk, f"Deletou mídia {filename}")
        messages.success(request, "Mídia excluída.")
        return redirect('admin_panel:media_list')
    except Exception as e:
        import traceback
        error_msg = f"Erro ao Deletar Mídia: {str(e)}\n{traceback.format_exc()}"
        print(f"CRITICAL ERROR: {error_msg}")
        if settings.DEBUG:
            return HttpResponse(f"<pre>{error_msg}</pre>", status=500)
        try:
            return render(request, '500.html', {'error': str(e)}, status=500)
        except:
            messages.error(request, "Ocorreu um erro ao deletar a mídia.")
            return redirect('admin_panel:media_list')
