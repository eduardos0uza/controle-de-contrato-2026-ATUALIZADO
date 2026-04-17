from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from .models import AuditLog
from contratos.middleware import get_current_user # Assumindo que este middleware existe ou criando um similar

@receiver(post_save)
def audit_post_save(sender, instance, created, **kwargs):
    # Evitar recursão infinita se estivermos salvando um AuditLog
    if sender == AuditLog:
        return
    
    # Lista de modelos para ignorar (opcional)
    if sender.__name__ in ['Session', 'Permission', 'ContentType', 'LogEntry']:
        return

    user = get_current_user() # Helper para pegar o usuário logado do thread local
    
    action = 'CREATE' if created else 'UPDATE'
    
    AuditLog.objects.create(
        usuario=user if user and user.is_authenticated else None,
        acao=action,
        tabela=sender.__name__,
        objeto_id=str(instance.pk),
        descricao=f"{action} em {sender.__name__}: {str(instance)[:100]}",
        dados_novos=None, # Aqui poderíamos serializar o objeto
    )

@receiver(post_delete)
def audit_post_delete(sender, instance, **kwargs):
    if sender == AuditLog:
        return
        
    if sender.__name__ in ['Session', 'Permission', 'ContentType', 'LogEntry']:
        return

    user = get_current_user()
    
    AuditLog.objects.create(
        usuario=user if user and user.is_authenticated else None,
        acao='DELETE',
        tabela=sender.__name__,
        objeto_id=str(instance.pk),
        descricao=f"DELETE em {sender.__name__}: {str(instance)[:100]}",
    )
