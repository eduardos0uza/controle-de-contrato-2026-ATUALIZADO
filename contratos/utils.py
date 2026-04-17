from datetime import date
import calendar


def calcular_dias_restantes(data_vencimento: date, referencia: date) -> int:
    return (data_vencimento - referencia).days


def calcular_alerta(dias_restantes: int) -> str:
    if dias_restantes < 0:
        return 'vencido'
    if dias_restantes <= 7:
        return 'vermelho'
    if dias_restantes <= 30:
        return 'laranja'
    if dias_restantes <= 90:
        return 'amarelo'
    return 'normal'


def calcular_data_vencimento(data_inicio: date, meses: int) -> date:
    month = data_inicio.month - 1 + meses
    year = data_inicio.year + month // 12
    month = month % 12 + 1
    day = min(data_inicio.day, calendar.monthrange(year, month)[1])
    return data_inicio.replace(year=year, month=month, day=day)
