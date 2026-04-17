from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

User = get_user_model()


class Secretaria(models.Model):
    nome = models.CharField(max_length=100, unique=True, verbose_name="Nome da Secretaria")
    slug = models.SlugField(unique=True)
    icone = models.CharField(max_length=50, default="bi-building", verbose_name="Ícone Bootstrap")
    cor = models.CharField(max_length=20, default="#0d6efd", verbose_name="Cor de Identificação")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Secretaria"
        verbose_name_plural = "Secretarias"
        ordering = ['nome']

    def __str__(self):
        return self.nome

class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('CREATE', 'Criar'),
        ('UPDATE', 'Atualizar'),
        ('DELETE', 'Deletar'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('OTHER', 'Outro'),
    ]

    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Usuário")
    acao = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name="Ação")
    tabela = models.CharField(max_length=100, verbose_name="Tabela")
    objeto_id = models.CharField(max_length=50, blank=True, null=True, verbose_name="ID do Objeto")
    descricao = models.TextField(verbose_name="Descrição")
    dados_anteriores = models.JSONField(null=True, blank=True, verbose_name="Dados Anteriores")
    dados_novos = models.JSONField(null=True, blank=True, verbose_name="Dados Novos")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="Endereço IP")
    user_agent = models.TextField(null=True, blank=True, verbose_name="User Agent")
    data_hora = models.DateTimeField(auto_now_add=True, verbose_name="Data/Hora")

    class Meta:
        ordering = ['-data_hora']
        verbose_name = "Log de Auditoria"
        verbose_name_plural = "Logs de Auditoria"

    def __str__(self):
        return f"{self.usuario} - {self.acao} em {self.tabela} ({self.data_hora:%d/%m/%Y %H:%M})"


class SystemSetting(models.Model):
    SETTING_TYPE_CHOICES = [
        ('GENERAL', 'Geral'),
        ('SECURITY', 'Segurança'),
        ('EMAIL', 'E-mail'),
        ('INTEGRATION', 'Integração'),
        ('UI', 'Interface'),
    ]

    chave = models.CharField(max_length=100, unique=True, verbose_name="Chave")
    valor = models.TextField(verbose_name="Valor")
    descricao = models.TextField(blank=True, null=True, verbose_name="Descrição")
    tipo = models.CharField(max_length=20, choices=SETTING_TYPE_CHOICES, default='GENERAL', verbose_name="Tipo")
    field_type = models.CharField(max_length=20, choices=[
        ('TEXT', 'Texto Curto'),
        ('TEXTAREA', 'Texto Longo'),
        ('NUMBER', 'Número'),
        ('BOOLEAN', 'Sim/Não'),
        ('EMAIL', 'E-mail'),
        ('URL', 'Link (URL)'),
        ('DATE', 'Data'),
    ], default='TEXT', verbose_name="Tipo de Campo")
    ultima_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuração do Sistema"
        verbose_name_plural = "Configurações do Sistema"

    def __str__(self):
        return self.chave

    @property
    def label(self):
        return self.chave.replace('_', ' ').title()


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    secretaria = models.ForeignKey(Secretaria, on_delete=models.SET_NULL, null=True, blank=True, related_name='usuarios')
    telefone = models.CharField(max_length=20, blank=True, null=True)
    cargo = models.CharField(max_length=100, blank=True, null=True)
    departamento = models.CharField(max_length=100, blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    two_factor_enabled = models.BooleanField(default=False, verbose_name="Autenticação de Dois Fatores")
    two_factor_secret = models.CharField(max_length=32, blank=True, null=True)
    notificacoes_email = models.BooleanField(default=True)

    def __str__(self):
        return self.user.username

class Post(models.Model):
    titulo = models.CharField(max_length=200, verbose_name="Título")
    slug = models.SlugField(unique=True)
    conteudo = models.TextField(verbose_name="Conteúdo")
    autor = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Autor")
    data_criacao = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    data_atualizacao = models.DateTimeField(auto_now=True, verbose_name="Última Atualização")
    publicado = models.BooleanField(default=False, verbose_name="Publicado")

    class Meta:
        verbose_name = "Post"
        verbose_name_plural = "Posts"
        ordering = ['-data_criacao']

    def __str__(self):
        return self.titulo

class Page(models.Model):
    titulo = models.CharField(max_length=200, verbose_name="Título")
    slug = models.SlugField(unique=True)
    conteudo = models.TextField(verbose_name="Conteúdo")
    data_atualizacao = models.DateTimeField(auto_now=True, verbose_name="Última Atualização")
    ativa = models.BooleanField(default=True, verbose_name="Ativa")

    class Meta:
        verbose_name = "Página"
        verbose_name_plural = "Páginas"

    def __str__(self):
        return self.titulo

class Media(models.Model):
    titulo = models.CharField(max_length=200, verbose_name="Título", blank=True)
    arquivo = models.FileField(upload_to='media_cms/', verbose_name="Arquivo")
    data_upload = models.DateTimeField(auto_now_add=True, verbose_name="Data de Upload")

    class Meta:
        verbose_name = "Mídia"
        verbose_name_plural = "Mídias"

    def __str__(self):
        return self.titulo or self.arquivo.name
