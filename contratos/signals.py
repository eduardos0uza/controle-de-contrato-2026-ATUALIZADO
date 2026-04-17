from datetime import date, datetime
from decimal import Decimal

from django.conf import settings
from django.db.models.signals import post_save, pre_save, post_delete, pre_delete

from .middleware import get_current_user
from .models import Contract, ContractHistory, ContractItem
from .services import enviar_alerta_email
from .backup import realizar_backup_contrato


def register_signals():
    # Signals existentes
    pre_save.connect(armazenar_estado_anterior, sender=Contract, dispatch_uid='contratos_pre_save')
    post_save.connect(registrar_historico, sender=Contract, dispatch_uid='contratos_post_save')
    
    # Novos signals de backup
    post_save.connect(backup_contrato_handler, sender=Contract, dispatch_uid='backup_contrato_save')
    pre_delete.connect(backup_contrato_handler, sender=Contract, dispatch_uid='backup_contrato_delete')
    
    # Backup quando itens são alterados
    post_save.connect(backup_item_handler, sender=ContractItem, dispatch_uid='backup_item_save')
    post_delete.connect(backup_item_handler, sender=ContractItem, dispatch_uid='backup_item_delete')


def backup_contrato_handler(sender, instance, **kwargs):
    if not settings.ENABLE_CONTRACT_FILE_BACKUPS:
        return
    try:
        realizar_backup_contrato(instance)
    except Exception as e:
        print(f"Erro no backup do contrato {instance.id}: {e}")


def backup_item_handler(sender, instance, **kwargs):
    if not settings.ENABLE_CONTRACT_FILE_BACKUPS:
        return
    try:
        if instance.contrato:
            realizar_backup_contrato(instance.contrato)
    except Exception as e:
        print(f"Erro no backup do item {instance.id}: {e}")


def armazenar_estado_anterior(sender, instance, **kwargs):
    if instance.pk:
        anterior = Contract.objects.filter(pk=instance.pk).values().first()
        instance._estado_anterior = anterior
    else:
        instance._estado_anterior = None


def registrar_historico(sender, instance, created, **kwargs):
    anterior = getattr(instance, '_estado_anterior', None)
    atual = Contract.objects.filter(pk=instance.pk).values().first()
    if atual is None:
        return
    
    alteracoes = {}
    acao = 'UPDATE'
    descricao = ""
    
    if created:
        acao = 'CREATE'
        descricao = f"Contrato {instance.numero_contrato} criado no sistema."
        alteracoes = {chave: _serializar_valor(valor) for chave, valor in atual.items()}
    else:
        campos_ignorados = ['atualizado_em', '_estado_anterior']
        for chave, valor in atual.items():
            if chave in campos_ignorados:
                continue
            
            val_anterior = anterior.get(chave)
            if val_anterior != valor:
                # Se mudou status ou alerta, registramos a ação específica
                if chave == 'status':
                    acao = 'STATUS'
                elif chave == 'alerta':
                    acao = 'ALERTA'
                
                alteracoes[chave] = {
                    'antes': _serializar_valor(val_anterior),
                    'depois': _serializar_valor(valor),
                }
        
        if alteracoes:
            qtd_alteracoes = len(alteracoes)
            descricao = f"Atualizou {qtd_alteracoes} campo(s): {', '.join(alteracoes.keys())}"

    if alteracoes or created:
        ContractHistory.objects.create(
            contrato=instance,
            alterado_por=get_current_user(),
            acao=acao,
            descricao=descricao,
            alteracoes=alteracoes,
        )
    
    # Alerta por email se mudou o alerta
    alerta_anterior = anterior.get('alerta') if anterior else None
    if alerta_anterior != instance.alerta:
        enviar_alerta_email(instance, alerta_anterior)


def _serializar_valor(valor):
    if isinstance(valor, datetime):
        return valor.isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return str(valor)
    return valor
