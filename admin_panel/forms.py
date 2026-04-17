from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from .models import UserProfile, SystemSetting, Post, Page, Media, Secretaria

User = get_user_model()

class UserForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, required=False, label="Senha")
    confirm_password = forms.CharField(widget=forms.PasswordInput, required=False, label="Confirmar Senha")
    secretaria = forms.ModelChoiceField(
        queryset=Secretaria.objects.all(),
        required=False,
        label="Secretaria/Departamento",
        empty_label="Selecione seu departamento"
    )
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Níveis de Acesso"
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'is_active', 'groups']
        labels = {
            'username': 'Nome de Usuário',
            'email': 'E-mail',
            'first_name': 'Nome',
            'last_name': 'Sobrenome',
            'is_active': 'Ativo',
        }

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop('request_user', None)
        super().__init__(*args, **kwargs)
        
        # Pre-popula secretaria se existir perfil
        if self.instance and self.instance.pk:
            try:
                profile = self.instance.profile
                self.fields['secretaria'].initial = profile.secretaria
            except UserProfile.DoesNotExist:
                pass
        
        # Se não for superuser, restringe a escolha da secretaria
        if self.request_user and not self.request_user.is_superuser:
            try:
                user_secretaria = self.request_user.profile.secretaria
                if user_secretaria:
                    # Trava na secretaria do usuário logado
                    self.fields['secretaria'].queryset = Secretaria.objects.filter(id=user_secretaria.id)
                    self.fields['secretaria'].initial = user_secretaria
                    self.fields['secretaria'].widget.attrs['readonly'] = True
                    # Opcional: Desabilitar o campo para evitar mudanças via inspecionar elemento
                    # Mas se desabilitar, o Django não envia o dado no POST se não for handled.
                    # Melhor apenas filtrar o queryset para que ele só possa escolher a dele.
            except UserProfile.DoesNotExist:
                self.fields['secretaria'].queryset = Secretaria.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("As senhas não coincidem.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get("password")
        if password:
            user.set_password(password)
        if commit:
            user.save()
            self.save_m2m()
            
            # Salva a secretaria no perfil
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.secretaria = self.cleaned_data.get('secretaria')
            profile.save()
        return user


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['telefone', 'cargo', 'notificacoes_email', 'avatar']
        labels = {
            'telefone': 'Telefone',
            'cargo': 'Cargo',
            'notificacoes_email': 'Receber Notificações por E-mail',
            'avatar': 'Foto de Perfil',
        }


class SystemSettingForm(forms.ModelForm):
    class Meta:
        model = SystemSetting
        fields = ['chave', 'valor', 'descricao', 'tipo', 'field_type']
        widgets = {
            'chave': forms.TextInput(attrs={'class': 'form-control rounded-3', 'placeholder': 'Ex: NOME_SISTEMA'}),
            'tipo': forms.Select(attrs={'class': 'form-select rounded-3'}),
            'field_type': forms.Select(attrs={'class': 'form-select rounded-3'}),
            'valor': forms.Textarea(attrs={'rows': 2, 'class': 'form-control rounded-3', 'placeholder': 'O que você quer definir aqui?'}),
            'descricao': forms.Textarea(attrs={'rows': 2, 'class': 'form-control rounded-3', 'placeholder': 'Ex: Nome que aparece no topo do site...'}),
        }
        labels = {
            'chave': 'Código da Configuração (Use MAIÚSCULAS e sem espaços)',
            'tipo': 'Onde esta configuração se encaixa?',
            'field_type': 'Qual o formato desta informação?',
            'valor': 'O que você quer salvar nela?',
            'descricao': 'Para que serve isso? (Explicado para humanos)',
        }

class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['titulo', 'slug', 'conteudo', 'publicado']
        widgets = {
            'conteudo': forms.Textarea(attrs={'rows': 10, 'class': 'form-control'}),
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'publicado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class PageForm(forms.ModelForm):
    class Meta:
        model = Page
        fields = ['titulo', 'slug', 'conteudo', 'ativa']
        widgets = {
            'conteudo': forms.Textarea(attrs={'rows': 10, 'class': 'form-control'}),
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'ativa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class MediaForm(forms.ModelForm):
    class Meta:
        model = Media
        fields = ['titulo', 'arquivo']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'arquivo': forms.FileInput(attrs={'class': 'form-control'}),
        }
