import threading
from datetime import timedelta

from django.utils import timezone

from .services import atualizar_alertas_diarios, executar_backup

_scheduler_started = False


def _executar_tarefas():
    atualizar_alertas_diarios()
    executar_backup()
    _agendar_proxima_execucao()


def _agendar_proxima_execucao():
    agora = timezone.localtime()
    proxima = (agora + timedelta(days=1)).replace(hour=2, minute=0, second=0, microsecond=0)
    atraso = (proxima - agora).total_seconds()
    timer = threading.Timer(atraso, _executar_tarefas)
    timer.daemon = True
    timer.start()


def start_scheduler():
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True
    _agendar_proxima_execucao()
