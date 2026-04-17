from decimal import Decimal
from django import forms
from django.contrib.auth import get_user_model
from django.forms import inlineformset_factory
from .models import Contract, ContractItem
from admin_panel.models import Secretaria, UserProfile


class ContractItemForm(forms.ModelForm):
    valor_unitario = forms.CharField(
        label="Valor Unitário (R$)",
        widget=forms.TextInput(attrs={'class': 'money-mask form-control item-valor-unitario', 'placeholder': '0,00'}),
        required=False
    )
    valor_total = forms.CharField(
        label="Valor Total (R$)",
        widget=forms.TextInput(attrs={'class': 'money-mask form-control item-valor-total', 'placeholder': '0,00', 'readonly': 'readonly'}),
        required=False
    )
    taxa_servico = forms.CharField(
        label="Taxa de Serviço (%)",
        widget=forms.TextInput(attrs={'class': 'percentage-mask form-control item-taxa-servico', 'placeholder': '0,00'}),
        required=False
    )
    desconto = forms.CharField(
        label="Desconto (%)",
        widget=forms.TextInput(attrs={'class': 'percentage-mask form-control item-desconto', 'placeholder': '0,00'}),
        required=False
    )

    caixa_atual = forms.CharField(
        label="Caixa Atual (R$)",
        widget=forms.TextInput(attrs={'class': 'money-mask form-control item-caixa-atual', 'placeholder': '0,00'}),
        required=False
    )

    class Meta:
        model = ContractItem
        fields = ['descricao', 'tipo_item', 'tipo_cobranca', 'quantidade_meses', 'quantidade', 'unidade', 'valor_unitario', 'taxa_servico', 'desconto', 'caixa_atual', 'valor_total', 'data_viagem', 'proprietario', 'cpf', 'localidade']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'tipo_item': forms.Select(attrs={'class': 'form-select item-tipo-item'}),
            'tipo_cobranca': forms.Select(attrs={'class': 'form-select item-tipo-cobranca'}),
            'quantidade_meses': forms.NumberInput(attrs={'class': 'form-control item-quantidade-meses', 'min': '1', 'placeholder': 'Meses'}),
            'quantidade': forms.NumberInput(attrs={'class': 'form-control item-quantidade', 'min': '1'}),
            'unidade': forms.TextInput(attrs={'class': 'form-control item-unidade', 'placeholder': 'UNID'}),
            'data_viagem': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control item-data-viagem'}),
            'proprietario': forms.TextInput(attrs={'class': 'form-control item-proprietario'}),
            'cpf': forms.TextInput(attrs={'class': 'form-control item-cpf', 'placeholder': '000.000.000-00'}),
            'localidade': forms.TextInput(attrs={'class': 'form-control item-localidade'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Helper function to format currency
        def format_br(val):
            if val is None:
                return ""
            return f"{val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

        # Format initial values from instance (DB)
        if self.instance.pk:
            if self.instance.valor_unitario is not None:
                self.fields['valor_unitario'].initial = format_br(self.instance.valor_unitario)
            if self.instance.valor_total is not None:
                self.fields['valor_total'].initial = format_br(self.instance.valor_total)
            if self.instance.taxa_servico is not None:
                self.fields['taxa_servico'].initial = format_br(self.instance.taxa_servico)
            if self.instance.desconto is not None:
                self.fields['desconto'].initial = format_br(self.instance.desconto)
            if self.instance.caixa_atual is not None:
                self.fields['caixa_atual'].initial = format_br(self.instance.caixa_atual)
        
        # Format initial values from initial dict (e.g. duplication or pre-filled forms)
        elif self.initial:
            for field in ['valor_unitario', 'valor_total', 'taxa_servico', 'desconto', 'caixa_atual']:
                if field in self.initial:
                    val = self.initial.get(field)
                    if isinstance(val, (int, float, Decimal)):
                        self.fields[field].initial = format_br(val)

    def clean_valor_unitario(self):
        data = self.fields['valor_unitario'].widget.value_from_datadict(self.data, self.files, self.add_prefix('valor_unitario'))
        if not data:
            return 0
        return str(data).replace('.', '').replace(',', '.')

    def clean_taxa_servico(self):
        data = self.fields['taxa_servico'].widget.value_from_datadict(self.data, self.files, self.add_prefix('taxa_servico'))
        if not data:
            return 0
        return str(data).replace('.', '').replace(',', '.')

    def clean_desconto(self):
        data = self.fields['desconto'].widget.value_from_datadict(self.data, self.files, self.add_prefix('desconto'))
        if not data:
            return 0
        return str(data).replace('.', '').replace(',', '.')

    def clean_caixa_atual(self):
        data = self.fields['caixa_atual'].widget.value_from_datadict(self.data, self.files, self.add_prefix('caixa_atual'))
        if not data:
            return None
        return str(data).replace('.', '').replace(',', '.')

    def clean_valor_total(self):
        data = self.fields['valor_total'].widget.value_from_datadict(self.data, self.files, self.add_prefix('valor_total'))
        if not data:
            return 0
        return str(data).replace('.', '').replace(',', '.')


ContractItemFormSet = inlineformset_factory(
    Contract, ContractItem, form=ContractItemForm,
    extra=0, can_delete=True
)


class ContractForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop('request_user', None)
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-control'})
        
        # Estilização específica para secretaria se presente
        if 'secretaria' in self.fields:
            self.fields['secretaria'].widget.attrs.update({'class': 'form-select'})
            
        # Restrição de secretaria para não-superusers
        if self.request_user and not self.request_user.is_superuser:
            try:
                user_secretaria = self.request_user.profile.secretaria
                if user_secretaria:
                    self.fields['secretaria'].queryset = Secretaria.objects.filter(id=user_secretaria.id)
                    self.fields['secretaria'].initial = user_secretaria
                    # Opcional: Ocultar o campo se ele só tem uma opção
                    # self.fields['secretaria'].widget = forms.HiddenInput()
            except UserProfile.DoesNotExist:
                self.fields['secretaria'].queryset = Secretaria.objects.none()

    class Meta:
        model = Contract
        fields = [
            'numero_contrato',
            'secretaria',
            'empresa',
            'objeto',
            # Dados do Processo
            'numero_protocolo',
            'processo_administrativo',
            'numero_pregao',
            'secretario',
            'numero_nota_empenho',
            'numero_ficha',
            # Campos de item removidos daqui
            # Outros
            'data_inicio',
            'vigencia',
            'data_vencimento',
            'status',
            'responsavel',
            'arquivo',
        ]
        widgets = {
            'objeto': forms.Textarea(attrs={'rows': 3}),
            'data_inicio': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'vigencia': forms.NumberInput(attrs={'min': '1', 'placeholder': '12'}),
            'data_vencimento': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'secretaria': forms.Select(attrs={'class': 'form-select'}),
        }
