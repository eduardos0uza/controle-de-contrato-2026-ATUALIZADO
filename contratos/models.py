from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

from .utils import calcular_alerta, calcular_dias_restantes, calcular_data_vencimento

User = get_user_model()


from admin_panel.models import Secretaria

class ContractStatus(models.TextChoices):
    ATIVO = 'ativo', 'Ativo'
    SUSPENSO = 'suspenso', 'Suspenso'
    ENCERRADO = 'encerrado', 'Encerrado'


class AlertStatus(models.TextChoices):
    NORMAL = 'normal', 'Normal'
    AMARELO = 'amarelo', 'Amarelo'
    LARANJA = 'laranja', 'Laranja'
    VERMELHO = 'vermelho', 'Vermelho'
    VENCIDO = 'vencido', 'Vencido'


class Contract(models.Model):
    numero_contrato = models.CharField(max_length=50, unique=True, verbose_name="Número do Contrato")
    secretaria = models.ForeignKey(Secretaria, on_delete=models.SET_NULL, null=True, blank=True, related_name='contratos', verbose_name="Secretaria Responsável")
    
    # Dados do Processo
    numero_protocolo = models.CharField(max_length=50, blank=True, null=True, verbose_name="Número do Protocolo")
    processo_administrativo = models.CharField(max_length=50, blank=True, null=True, verbose_name="Processo Administrativo")
    numero_pregao = models.CharField(max_length=50, blank=True, null=True, verbose_name="Número do Pregão")
    secretario = models.CharField(max_length=100, blank=True, null=True, verbose_name="Secretário(a)")
    numero_nota_empenho = models.CharField(max_length=50, blank=True, null=True, verbose_name="Número da Nota de Empenho")
    numero_ficha = models.CharField(max_length=50, blank=True, null=True, verbose_name="Número da Ficha")

    # Novos campos
    empresa = models.CharField(max_length=255, blank=True, null=True, verbose_name="Empresa")
    objeto = models.TextField(blank=True, null=True, verbose_name="Objeto do Contrato")
    
    # Campos de controle
    data_inicio = models.DateField(verbose_name="Data de Início")
    vigencia = models.IntegerField(default=12, verbose_name="Vigência (meses)")
    data_vencimento = models.DateField(verbose_name="Data de Vencimento", blank=True)
    status = models.CharField(max_length=20, choices=ContractStatus.choices, default=ContractStatus.ATIVO)
    responsavel = models.CharField(max_length=255, verbose_name="Responsável")
    arquivo = models.FileField(upload_to='contratos/', blank=True, null=True, verbose_name="Arquivo do Contrato")
    dias_restantes = models.IntegerField(default=0)
    alerta = models.CharField(max_length=20, choices=AlertStatus.choices, default=AlertStatus.NORMAL)
    criado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='contratos_criados', verbose_name="Criado por")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    @property
    def valor(self):
        annotated_total = getattr(self, 'valor_total_calculado', None)
        if annotated_total is not None:
            return annotated_total

        prefetched_itens = getattr(self, '_prefetched_objects_cache', {}).get('itens')
        if prefetched_itens is not None:
            return sum((item.valor_total or 0) for item in prefetched_itens)

        # Calcula valor total somando os itens
        total = self.itens.aggregate(total=models.Sum('valor_total'))['total']
        return total or 0

    def atualizar_alerta(self):
        dias_restantes = calcular_dias_restantes(self.data_vencimento, timezone.localdate())
        alerta = calcular_alerta(dias_restantes)
        self.dias_restantes = dias_restantes
        self.alerta = alerta

    @property
    def dias_vencido(self):
        if self.dias_restantes < 0:
            return abs(self.dias_restantes)
        return 0

    def save(self, *args, **kwargs):
        from admin_panel.utils import log_audit
        
        is_new = self.pk is None
        if not self.data_vencimento and self.data_inicio and self.vigencia:
            # Se não tiver data de vencimento, calcula baseada na vigência
            self.data_vencimento = calcular_data_vencimento(self.data_inicio, self.vigencia)
            
        self.atualizar_alerta()
        super().save(*args, **kwargs)
        
        # Log de Auditoria
        if is_new:
            log_audit(
                request=None, 
                acao='CREATE', 
                tabela='Contract', 
                objeto_id=self.pk, 
                descricao=f"Contrato {self.numero_contrato} criado por {self.criado_por} da secretaria {self.secretaria}",
                user=self.criado_por
            )
        else:
            # Para updates, tentamos pegar o usuário atual via middleware se disponível
            from .middleware import get_current_user
            current_user = get_current_user()
            log_audit(
                request=None,
                acao='UPDATE',
                tabela='Contract',
                objeto_id=self.pk,
                descricao=f"Contrato {self.numero_contrato} atualizado",
                user=current_user
            )

    @property
    def alerta_info(self):
        """Retorna informações amigáveis sobre o status do alerta."""
        mapping = {
            'vencido': {
                'label': 'Prazo Expirado',
                'color': '#000000',
                'icon': 'bi-exclamation-octagon-fill',
                'description': 'O contrato já venceu.'
            },
            'vermelho': {
                'label': 'Crítico (até 7 dias)',
                'color': 'var(--hiden-danger)',
                'icon': 'bi-exclamation-triangle-fill',
                'description': 'Vencimento em menos de uma semana.'
            },
            'laranja': {
                'label': 'Urgente (até 30 dias)',
                'color': 'var(--hiden-warning)',
                'icon': 'bi-clock-fill',
                'description': 'Vencimento em menos de um mês.'
            },
            'amarelo': {
                'label': 'Atenção (até 90 dias)',
                'color': '#ffc107', # Yellow mais visível
                'icon': 'bi-info-circle-fill',
                'description': 'Vencimento em menos de 3 meses.'
            },
            'normal': {
                'label': 'Regular (> 90 dias)',
                'color': 'var(--hiden-success)',
                'icon': 'bi-check-circle-fill',
                'description': 'Prazo de vigência seguro.'
            }
        }
        return mapping.get(self.alerta, mapping['normal'])

    def __str__(self):
        return self.numero_contrato


class ContractItem(models.Model):
    TIPO_COBRANCA_CHOICES = [
        ('UNIDADE', 'Unidade'),
        ('MENSAL', 'Mensal'),
    ]
    TIPO_ITEM_CHOICES = [
        ('SERVICO', 'Serviço/Produto'),
        ('PASSAGEM', 'Passagem Aérea'),
        ('ALUGUEL', 'Aluguel'),
    ]
    contrato = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='itens')
    tipo_item = models.CharField(max_length=10, choices=TIPO_ITEM_CHOICES, default='SERVICO', verbose_name="Tipo de Item")
    descricao = models.TextField(verbose_name="Descrição do Item")
    unidade = models.CharField(max_length=20, blank=True, null=True, verbose_name="Unidade")
    # Campos de Aluguel
    proprietario = models.CharField(max_length=255, blank=True, null=True, verbose_name="Nome do Proprietário")
    cpf = models.CharField(max_length=14, blank=True, null=True, verbose_name="CPF")
    localidade = models.CharField(max_length=255, blank=True, null=True, verbose_name="Localidade")
    
    tipo_cobranca = models.CharField(max_length=10, choices=TIPO_COBRANCA_CHOICES, default='UNIDADE', verbose_name="Tipo de Cobrança")
    quantidade = models.IntegerField(default=1, verbose_name="Quantidade")
    quantidade_meses = models.IntegerField(default=12, blank=True, null=True, verbose_name="Meses")
    valor_unitario = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Valor Unitário")
    data_viagem = models.DateField(blank=True, null=True, verbose_name="Data da Viagem")
    taxa_servico = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Taxa de Serviço (%)")
    desconto = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Desconto (%)")
    caixa_atual = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, verbose_name="Caixa Atual")
    valor_total = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Valor Total")

    def save(self, *args, **kwargs):
        # Recalcula valor total do item se não fornecido ou se mudou unitario/qtd
        if not self.valor_total and self.quantidade and self.valor_unitario:
             total = self.quantidade * self.valor_unitario
             try:
                if self.tipo_cobranca == 'MENSAL':
                    if self.quantidade_meses:
                         total = total * self.quantidade_meses
                    elif self.contrato.vigencia:
                         total = total * self.contrato.vigencia
             except Exception:
                pass
             
             # Taxa e Desconto agora são porcentagens
             valor_taxa = total * ((self.taxa_servico or 0) / 100)
             valor_desconto = total * ((self.desconto or 0) / 100)
             
             total = total + valor_taxa - valor_desconto
             self.valor_total = total
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.descricao} ({self.contrato.numero_contrato})"


class ContractHistory(models.Model):
    ACAO_CHOICES = [
        ('CREATE', 'Criação'),
        ('UPDATE', 'Atualização'),
        ('DELETE', 'Exclusão'),
        ('STATUS', 'Mudança de Status'),
        ('ALERTA', 'Mudança de Alerta'),
    ]
    contrato = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='historico')
    alterado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    alterado_em = models.DateTimeField(auto_now_add=True)
    acao = models.CharField(max_length=20, choices=ACAO_CHOICES, default='UPDATE')
    descricao = models.TextField(blank=True, null=True)
    alteracoes = models.JSONField(default=dict)

    def __str__(self):
        return f'{self.contrato.numero_contrato} - {self.get_acao_display()} - {self.alterado_em:%Y-%m-%d %H:%M}'
