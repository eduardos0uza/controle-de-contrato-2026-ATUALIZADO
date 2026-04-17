from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User, Group
from django.core import mail, cache
from .models import AuditLog, SystemSetting, UserProfile, Post, Page, Media
import time

@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
class AdminPanelTest(TestCase):
    def setUp(self):
        # Limpar cache antes de cada teste
        cache.cache.clear()
        
        # Criar grupos
        Group.objects.get_or_create(name='administrador')
        Group.objects.get_or_create(name='moderador')
        Group.objects.get_or_create(name='editor')

        # Criar usuário administrador
        self.admin_user = User.objects.create_superuser(
            username='admin_test',
            email='admin@test.com',
            password='password123'
        )
        self.admin_user.groups.add(Group.objects.get(name='administrador'))
        # Garantir que o perfil existe
        self.admin_profile, _ = UserProfile.objects.get_or_create(user=self.admin_user)
        
        # Criar usuário comum
        self.regular_user = User.objects.create_user(
            username='user_test',
            email='user@test.com',
            password='password123'
        )
        
        self.client = Client()

    def test_admin_dashboard_access(self):
        """Teste de acesso ao dashboard administrativo"""
        # Tentar acessar sem login
        response = self.client.get(reverse('admin_panel:dashboard'))
        self.assertEqual(response.status_code, 302) # Redireciona para login

        # Tentar acessar como usuário comum
        self.client.login(username='user_test', password='password123')
        response = self.client.get(reverse('admin_panel:dashboard'))
        self.assertEqual(response.status_code, 302) # Redireciona (Acesso Negado)

        # Acessar como administrador
        self.client.login(username='admin_test', password='password123')
        response = self.client.get(reverse('admin_panel:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Painel Administrativo")

    def test_user_2fa_flow(self):
        """Teste do fluxo de autenticação de dois fatores"""
        # Ativar 2FA para o admin
        self.admin_profile.two_factor_enabled = True
        self.admin_profile.save()
        
        self.client.login(username='admin_test', password='password123')
        
        # Tentar acessar dashboard - deve redirecionar para verificação 2FA
        response = self.client.get(reverse('admin_panel:dashboard'))
        self.assertRedirects(response, reverse('admin_panel:verify_2fa'))
        
        # Verificar se o e-mail foi "enviado"
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Seu código de verificação", mail.outbox[0].subject)
        
        # Pegar o código da sessão
        session = self.client.session
        code = session.get('two_factor_code')
        self.assertIsNotNone(code)
        
        # Enviar código correto
        response = self.client.post(reverse('admin_panel:verify_2fa'), {'code': code})
        self.assertRedirects(response, reverse('admin_panel:dashboard'))
        
        # Agora deve acessar o dashboard
        response = self.client.get(reverse('admin_panel:dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_2fa_expiration_and_resend(self):
        """Teste de expiração e reenvio de código 2FA"""
        self.admin_profile.two_factor_enabled = True
        self.admin_profile.save()
        
        self.client.login(username='admin_test', password='password123')
        self.client.get(reverse('admin_panel:verify_2fa'))
        
        # Simular expiração do código alterando o tempo no session
        session = self.client.session
        session['two_factor_code_expires'] = time.time() - 10
        session.save()
        
        # Tentar enviar código expirado
        response = self.client.post(reverse('admin_panel:verify_2fa'), {'code': '000000'})
        self.assertContains(response, "O código expirou")
        
        # Testar reenvio
        mail.outbox = [] # Limpar emails anteriores
        response = self.client.post(reverse('admin_panel:verify_2fa'), {'action': 'resend'})
        self.assertRedirects(response, reverse('admin_panel:verify_2fa'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Seu código de verificação", mail.outbox[0].subject)
        
        # Verificar se o novo código é válido
        session = self.client.session
        new_code = session.get('two_factor_code')
        self.assertIsNotNone(new_code)
        self.assertGreater(session.get('two_factor_code_expires'), time.time())
        
        # Enviar novo código
        response = self.client.post(reverse('admin_panel:verify_2fa'), {'code': new_code})
        self.assertRedirects(response, reverse('admin_panel:dashboard'))

    def test_rate_limiting(self):
        """Teste de restrição de taxa (Rate Limiting)"""
        # Ativar 2FA para evitar o redirect na view verify_2fa
        self.admin_profile.two_factor_enabled = True
        self.admin_profile.save()
        
        self.client.login(username='admin_test', password='password123')
        
        # Fazer várias requisições rápidas para uma view com limite baixo
        # A view verify_2fa tem limite 5 em 300s
        for i in range(5):
            response = self.client.get(reverse('admin_panel:verify_2fa'))
            self.assertEqual(response.status_code, 200)
            
        # A 6ª requisição deve ser bloqueada
        response = self.client.get(reverse('admin_panel:verify_2fa'))
        self.assertEqual(response.status_code, 429)
        self.assertIn("Muitas requisições", response.content.decode('utf-8'))
        self.assertIn("Calma lá!", response.content.decode('utf-8')) # Verifica se o novo template foi usado

    def test_cms_crud_operations(self):
        """Teste de operações CRUD no CMS"""
        self.client.login(username='admin_test', password='password123')
        
        # Teste Post
        response = self.client.post(reverse('admin_panel:post_create'), {
            'titulo': 'Post de Teste',
            'slug': 'post-de-teste',
            'conteudo': 'Conteúdo do post',
            'status': 'PUBLISHED'
        })
        self.assertRedirects(response, reverse('admin_panel:post_list'))
        self.assertTrue(Post.objects.filter(titulo='Post de Teste').exists())
        
        # Teste Page
        response = self.client.post(reverse('admin_panel:page_create'), {
            'titulo': 'Página de Teste',
            'slug': 'pagina-de-teste',
            'conteudo': 'Conteúdo da página',
            'is_active': True
        })
        self.assertRedirects(response, reverse('admin_panel:page_list'))
        self.assertTrue(Page.objects.filter(titulo='Página de Teste').exists())

    def test_user_crud_access(self):
        """Teste de acesso ao CRUD de usuários"""
        self.client.login(username='admin_test', password='password123')
        
        # Listagem
        response = self.client.get(reverse('admin_panel:user_list'))
        self.assertEqual(response.status_code, 200)
        
        # Criação
        response = self.client.get(reverse('admin_panel:user_create'))
        self.assertEqual(response.status_code, 200)

    def test_audit_log_creation(self):
        """Teste de criação de logs de auditoria"""
        self.client.login(username='admin_test', password='password123')
        
        # Criar uma configuração para gerar log
        self.client.post(reverse('admin_panel:system_settings'), {
            'chave': 'TEST_SETTING',
            'valor': 'test_value',
            'tipo': 'GENERAL',
            'descricao': 'Test description'
        })
        
        # Verificar se o log foi criado
        log_exists = AuditLog.objects.filter(tabela='SystemSetting', acao='CREATE').exists()
        self.assertTrue(log_exists)

    def test_backup_generation(self):
        """Teste de geração de backup"""
        self.client.login(username='admin_test', password='password123')
        response = self.client.get(reverse('admin_panel:backup_restore'), {'action': 'create'})
        self.assertEqual(response.status_code, 302) # Redireciona após criar
