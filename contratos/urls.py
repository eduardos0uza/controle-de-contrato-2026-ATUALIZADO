from django.urls import path
from contratos import views

app_name = 'contratos'

urlpatterns = [
    path('', views.landing_page, name='landing'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('contratos/', views.lista_contratos, name='lista'),
    path('contratos/novo/', views.criar_contrato, name='criar'),
    path('contratos/<int:contrato_id>/', views.detalhe_contrato, name='detalhe'),
    path('contratos/<int:contrato_id>/editar/', views.editar_contrato, name='editar'),
    path('contratos/<int:contrato_id>/duplicar/', views.duplicar_contrato, name='duplicar'),
    path('contratos/<int:contrato_id>/excluir/', views.excluir_contrato, name='excluir'),
    path('relatorios/', views.relatorios, name='relatorios'),
    path('privacidade/', views.privacidade, name='privacidade'),
    path('termos/', views.termos_uso, name='termos'),
]
