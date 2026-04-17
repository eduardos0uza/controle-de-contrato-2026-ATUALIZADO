from django.contrib import admin

from .models import Contract, ContractHistory


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ('numero_contrato', 'data_vencimento', 'status', 'alerta', 'responsavel')
    list_filter = ('status', 'alerta', 'responsavel')
    search_fields = ('numero_contrato',)


@admin.register(ContractHistory)
class ContractHistoryAdmin(admin.ModelAdmin):
    list_display = ('contrato', 'alterado_em', 'alterado_por')
    list_filter = ('alterado_em',)
