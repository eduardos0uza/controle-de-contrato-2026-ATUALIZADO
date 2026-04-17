from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from .models import Contract


def ensure_roles(sender, **kwargs):
    content_type = ContentType.objects.get_for_model(Contract)
    permissoes = Permission.objects.filter(content_type=content_type)
    admin_group, _ = Group.objects.get_or_create(name='administrador')
    gestor_group, _ = Group.objects.get_or_create(name='gestor')
    visualizador_group, _ = Group.objects.get_or_create(name='visualizador')

    admin_group.permissions.set(permissoes)
    gestor_group.permissions.set(
        permissoes.filter(codename__in=['add_contract', 'change_contract', 'view_contract'])
    )
    visualizador_group.permissions.set(
        permissoes.filter(codename__in=['view_contract'])
    )
