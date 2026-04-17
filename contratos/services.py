from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core import management
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from .models import Contract
from .utils import calcular_alerta, calcular_dias_restantes


def enviar_alerta_email(contrato: Contract, alerta_anterior: str | None):
    # Removido envio de email pois responsavel agora é string
    pass
    # if not contrato.responsavel.email:
    #     return
    # if alerta_anterior == contrato.alerta:
    #     return
    # assunto = f'Alerta de contrato {contrato.numero_contrato}'
    # mensagem = (
    #     f'O contrato {contrato.numero_contrato} mudou para alerta {contrato.alerta}. '
    #     f'Data de vencimento: {contrato.data_vencimento:%d/%m/%Y}. '
    #     f'Dias restantes: {contrato.dias_restantes}.'
    # )
    # mail.send_mail(
    #     subject=assunto,
    #     message=mensagem,
    #     from_email=settings.DEFAULT_FROM_EMAIL,
    #     recipient_list=[contrato.responsavel.email],
    #     fail_silently=True,
    # )


def atualizar_alertas_diarios() -> int:
    hoje = timezone.localdate()
    cache_key = f'contratos.alertas.{hoje.isoformat()}'
    if cache.get(cache_key):
        return 0
    atualizados = []
    atualizado_em = timezone.now()
    # Usar iterator() para eficiência de memória se houver muitos contratos
    for contrato in Contract.objects.only('id', 'data_vencimento', 'dias_restantes', 'alerta').iterator(chunk_size=1000):
        dias_restantes = calcular_dias_restantes(contrato.data_vencimento, hoje)
        alerta = calcular_alerta(dias_restantes)
        if contrato.dias_restantes != dias_restantes or contrato.alerta != alerta:
            contrato.dias_restantes = dias_restantes
            contrato.alerta = alerta
            contrato.atualizado_em = atualizado_em
            atualizados.append(contrato)
    if atualizados:
        Contract.objects.bulk_update(atualizados, ['dias_restantes', 'alerta', 'atualizado_em'])
    cache.set(cache_key, True, 60 * 60 * 24)
    return len(atualizados)


def executar_backup() -> str:
    base_dir = Path(settings.BASE_DIR)
    destino = base_dir / 'backups'
    destino.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    arquivo = destino / f'backup_{timestamp}.json'
    with transaction.atomic():
        management.call_command('dumpdata', output=str(arquivo))
    return str(arquivo)
