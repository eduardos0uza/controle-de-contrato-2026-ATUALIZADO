from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from contratos.models import Contract

def ensure_admin_roles(sender, **kwargs):
    """Garante a existência dos grupos e permissões necessários."""
    try:
        # Definir roles solicitadas pelo usuário
        roles = {
            'administrador': {
                'description': 'Acesso total ao sistema',
                'permissions': 'all'
            },
            'gestor': {
                'description': 'Gestão completa de contratos e relatórios',
                'permissions': ['add_contract', 'change_contract', 'delete_contract', 'view_contract', 'view_auditlog']
            },
            'moderador': {
                'description': 'Gerencia contratos e visualiza logs, mas não altera configurações globais',
                'permissions': ['add_contract', 'change_contract', 'view_contract', 'view_auditlog']
            },
            'editor': {
                'description': 'Cria e edita contratos',
                'permissions': ['add_contract', 'change_contract', 'view_contract']
            },
            'visualizador': {
                'description': 'Apenas visualização de contratos e relatórios',
                'permissions': ['view_contract']
            }
        }

        from django.apps import apps
        try:
            AuditLog = apps.get_model('admin_panel', 'AuditLog')
            contract_ct = ContentType.objects.get_for_model(Contract)
            audit_ct = ContentType.objects.get_for_model(AuditLog)
        except Exception as e_models:
            print(f"Erro ao carregar modelos para roles: {e_models}")
            return

        for role_name, info in roles.items():
            try:
                group, _ = Group.objects.get_or_create(name=role_name)
                
                if info['permissions'] == 'all':
                    # Admin recebe tudo
                    all_perms = Permission.objects.all()
                    group.permissions.set(all_perms)
                else:
                    perms = []
                    # Permissões de contrato
                    contract_perms = Permission.objects.filter(
                        content_type=contract_ct, 
                        codename__in=info['permissions']
                    )
                    perms.extend(list(contract_perms))
                    
                    # Permissões de audit log se necessário
                    if 'view_auditlog' in info['permissions']:
                        audit_perms = Permission.objects.filter(
                            content_type=audit_ct,
                            codename='view_auditlog'
                        )
                        perms.extend(list(audit_perms))
                    
                    group.permissions.set(perms)
            except Exception as e_role:
                print(f"Erro ao criar role {role_name}: {e_role}")
    except Exception as e_global:
        print(f"Erro crítico em ensure_admin_roles: {e_global}")
