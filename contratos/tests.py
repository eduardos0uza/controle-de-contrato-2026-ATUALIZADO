from datetime import date
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.utils import timezone
from django.urls import reverse

from .services import atualizar_alertas_diarios
from .models import Contract
from .utils import calcular_alerta, calcular_dias_restantes
from .views import _salvar_contrato_com_itens


class AlertasTestCase(TestCase):
    def test_calcular_dias_restantes(self):
        referencia = date(2026, 2, 1)
        vencimento = date(2026, 3, 1)
        self.assertEqual(calcular_dias_restantes(vencimento, referencia), 28)

    def test_alerta_vermelho(self):
        self.assertEqual(calcular_alerta(7), 'vermelho')
        self.assertEqual(calcular_alerta(0), 'vermelho')

    def test_alerta_laranja(self):
        self.assertEqual(calcular_alerta(30), 'laranja')
        self.assertEqual(calcular_alerta(15), 'laranja')

    def test_alerta_amarelo(self):
        self.assertEqual(calcular_alerta(90), 'amarelo')
        self.assertEqual(calcular_alerta(60), 'amarelo')

    def test_alerta_normal(self):
        self.assertEqual(calcular_alerta(120), 'normal')

    def test_alerta_vencido(self):
        self.assertEqual(calcular_alerta(-1), 'vencido')


class AtualizacaoAlertasTestCase(TestCase):
    def test_atualizar_alertas_diarios_usa_cache(self):
        contrato = Contract.objects.create(
            numero_contrato='CACHE-001',
            data_inicio=date(2026, 1, 1),
            data_vencimento=date(2026, 1, 10),
            vigencia=12,
            responsavel='Admin',
        )
        Contract.objects.filter(pk=contrato.pk).update(dias_restantes=999, alerta='normal')

        atualizados = atualizar_alertas_diarios()
        contrato.refresh_from_db()

        self.assertEqual(atualizados, 1)
        self.assertEqual(contrato.dias_restantes, (contrato.data_vencimento - timezone.localdate()).days)
        self.assertEqual(atualizar_alertas_diarios(), 0)


class CriacaoContratoTestCase(TestCase):
    def test_salvamento_reprocessa_apos_reset_de_sequence(self):
        form = Mock()
        form.instance = Mock(pk=None, id=None)
        contrato = Mock()
        form.save.side_effect = [
            IntegrityError('duplicate key value violates unique constraint "contratos_contract_pkey"'),
            contrato,
        ]
        formset = Mock()

        with patch('contratos.views.reset_contract_sequences') as reset_sequences:
            resultado = _salvar_contrato_com_itens(form, formset)

        self.assertIs(resultado, contrato)
        self.assertEqual(form.save.call_count, 2)
        reset_sequences.assert_called_once()
        self.assertIs(formset.instance, contrato)
        formset.save.assert_called_once()


class LogoutTemplateTestCase(TestCase):
    def test_base_renderiza_logout_com_post(self):
        user = get_user_model().objects.create_user(username='admin_teste', password='senha123')
        request = RequestFactory().get('/', secure=True)
        request.user = user

        html = render_to_string('base.html', request=request)

        self.assertIn('method="post"', html)
        self.assertIn(f'action="{reverse("logout")}"', html)
        self.assertIn('Sair do sistema', html)
