from django.contrib import admin

from .models import Contract, ContractHistory, ControleMensal


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ('numero_contrato', 'data_vencimento', 'status', 'alerta', 'responsavel')
    list_filter = ('status', 'alerta', 'responsavel')
    search_fields = ('numero_contrato',)


@admin.register(ContractHistory)
class ContractHistoryAdmin(admin.ModelAdmin):
    list_display = ('contrato', 'alterado_em', 'alterado_por')
    list_filter = ('alterado_em',)


@admin.register(ControleMensal)
class ControleMensalAdmin(admin.ModelAdmin):
    list_display = (
        'contrato', 'referencia_mes', 'referencia_ano',
        'valor_previsto', 'valor_utilizado', 'saldo', 'status',
    )
    list_filter  = ('status', 'referencia_ano', 'referencia_mes', 'secretaria')
    search_fields = ('contrato__numero_contrato', 'contrato__empresa')
    readonly_fields = ('saldo', 'percentual_executado', 'criado_em', 'atualizado_em')
    ordering = ('-referencia_ano', '-referencia_mes')

