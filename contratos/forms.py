from decimal import Decimal, InvalidOperation
from django.utils import timezone
from django import forms
from django.contrib.auth import get_user_model
from django.forms import inlineformset_factory
from .models import Contract, ContractItem, ContractRenewal, ControleMensal
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
            self.fields['secretaria'].required = True
            
        # Restrição de secretaria para não-superusers
        if self.request_user and not self.request_user.is_superuser:
            try:
                user_secretaria = self.request_user.profile.secretaria
                if user_secretaria:
                    self.fields['secretaria'].queryset = Secretaria.objects.filter(id=user_secretaria.id)
                    self.fields['secretaria'].initial = user_secretaria
                    self.fields['secretaria'].disabled = True  # Native Django field lock!
            except (UserProfile.DoesNotExist, AttributeError):
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


class ContractRenewalForm(forms.ModelForm):
    valor_novo = forms.CharField(
        label="Valor Novo",
        widget=forms.TextInput(attrs={'class': 'money-mask form-control', 'placeholder': '0,00'})
    )

    class Meta:
        model = ContractRenewal
        fields = [
            'vencimento_novo',
            'valor_novo',
            'tipo_renovacao',
            'observacoes',
            'documento',
        ]
        widgets = {
            'vencimento_novo': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': 'form-control'}),
            'valor_novo': forms.TextInput(attrs={'class': 'money-mask form-control', 'placeholder': '0,00'}),
            'tipo_renovacao': forms.Select(attrs={'class': 'form-select'}),
            'observacoes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'documento': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def clean_valor_novo(self):
        data = self.cleaned_data.get('valor_novo')
        if not data:
            raise forms.ValidationError("O valor da renovação é obrigatório.")
        
        try:
            if isinstance(data, str):
                # Limpeza robusta: remove R$, espaços, pontos de milhar e troca vírgula por ponto
                clean_data = data.replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.').strip()
                decimal_value = Decimal(clean_data)
            else:
                decimal_value = Decimal(data)
                
            if decimal_value <= 0:
                raise forms.ValidationError("O valor da renovação deve ser maior que zero.")
            return decimal_value
        except (ValueError, TypeError, InvalidOperation):
            raise forms.ValidationError("Informe um valor numérico válido (ex: 1.500,50).")

    def clean_documento(self):
        doc = self.cleaned_data.get('documento')
        if doc:
            if not doc.name.lower().endswith('.pdf'):
                raise forms.ValidationError("O arquivo comprobatório deve estar no formato PDF.")
            if doc.size > 10 * 1024 * 1024:  # 10MB
                raise forms.ValidationError("O arquivo é muito grande. O limite é 10MB.")
        return doc

    def clean(self):
        cleaned_data = super().clean()
        vencimento_novo = cleaned_data.get('vencimento_novo')
        
        # Log de auditoria para debug profissional
        print(f"[AUDITORIA RENOVACAO] Dados: {cleaned_data}")
        
        if vencimento_novo and vencimento_novo < timezone.localdate():
            self.add_error('vencimento_novo', "A nova vigência deve ser uma data futura. Não é permitido renovar com data retroativa.")
            
        return cleaned_data


# ─────────────────────────────────────────────────────────────────────────────
# FORM — CONTROLE MENSAL
# ─────────────────────────────────────────────────────────────────────────────

class ControleMensalForm(forms.ModelForm):
    """Formulário para criar/editar um registro de controle mensal."""

    valor_previsto = forms.CharField(
        label='Valor Previsto (R$)',
        widget=forms.TextInput(attrs={
            'class': 'money-mask form-control',
            'placeholder': '0,00',
        }),
        required=True,
    )
    valor_utilizado = forms.CharField(
        label='Valor Utilizado (R$)',
        widget=forms.TextInput(attrs={
            'class': 'money-mask form-control',
            'placeholder': '0,00',
        }),
        required=False,
    )

    class Meta:
        model  = ControleMensal
        fields = [
            'valor_previsto',
            'valor_utilizado',
            'status',
            'observacao',
            'data_vencimento',
            'data_pagamento',
            'anexo',
        ]
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'observacao': forms.Textarea(attrs={
                'rows': 3, 'class': 'form-control',
                'placeholder': 'Observações sobre a execução deste mês...',
            }),
            'data_vencimento': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'type': 'date', 'class': 'form-control'},
            ),
            'data_pagamento': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'type': 'date', 'class': 'form-control'},
            ),
            'anexo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    # ── formatação de valores iniciais ────────────────────────────────────

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        def format_br(val):
            if val is None:
                return ''
            try:
                return f'{float(val):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
            except Exception:
                return str(val)

        if self.instance.pk:
            if self.instance.valor_previsto is not None:
                self.fields['valor_previsto'].initial  = format_br(self.instance.valor_previsto)
            if self.instance.valor_utilizado is not None:
                self.fields['valor_utilizado'].initial = format_br(self.instance.valor_utilizado)

    # ── clean helpers ─────────────────────────────────────────────────────

    def _clean_money(self, field_name, required=False):
        from decimal import Decimal, InvalidOperation
        raw = self.data.get(self.add_prefix(field_name), '')
        if not raw:
            if required:
                raise forms.ValidationError('Este campo é obrigatório.')
            return Decimal('0.00')
        try:
            clean = str(raw).replace('.', '').replace(',', '.').strip()
            value = Decimal(clean)
            if required and value <= 0:
                raise forms.ValidationError('O valor deve ser maior que zero.')
            if value < 0:
                raise forms.ValidationError('O valor não pode ser negativo.')
            return value
        except (ValueError, TypeError, InvalidOperation):
            raise forms.ValidationError('Informe um valor numérico válido (ex: 1.500,00).')

    def clean_valor_previsto(self):
        return self._clean_money('valor_previsto', required=True)

    def clean_valor_utilizado(self):
        return self._clean_money('valor_utilizado', required=False)

    def clean_anexo(self):
        anexo = self.cleaned_data.get('anexo')
        if anexo and hasattr(anexo, 'name'):
            allowed_exts = ['.pdf', '.xml', '.jpg', '.jpeg', '.png', '.gif']
            import os
            ext = os.path.splitext(anexo.name)[1].lower()
            if ext not in allowed_exts:
                raise forms.ValidationError(
                    'Tipo de arquivo não permitido. Use: PDF, XML, JPG, PNG.'
                )
            if anexo.size > 15 * 1024 * 1024:  # 15 MB
                raise forms.ValidationError('O arquivo é muito grande. Limite: 15 MB.')
        return anexo

