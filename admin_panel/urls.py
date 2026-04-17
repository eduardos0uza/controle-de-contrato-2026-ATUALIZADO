from django.urls import path
from . import views

app_name = 'admin_panel'

urlpatterns = [
    path('', views.admin_dashboard, name='dashboard'),
    path('verify-2fa/', views.verify_2fa, name='verify_2fa'),
    path('usuarios/', views.user_list, name='user_list'),
    path('usuarios/novo/', views.user_create, name='user_create'),
    path('usuarios/<int:pk>/editar/', views.user_update, name='user_update'),
    path('usuarios/<int:pk>/deletar/', views.user_delete, name='user_delete'),
    path('usuarios/<int:pk>/status/', views.user_toggle_status, name='user_toggle_status'),
    path('audit-logs/', views.audit_log_list, name='audit_log_list'),
    path('audit-logs/<int:pk>/detalhes/', views.audit_log_detail, name='audit_log_detail'),
    path('contratos/', views.admin_contratos_list, name='contratos_list'),
    path('configuracoes/', views.system_settings, name='system_settings'),
    path('configuracoes/<int:setting_id>/deletar/', views.delete_system_setting, name='delete_system_setting'),
    path('backup/', views.backup_restore, name='backup_restore'),
    path('debug/', views.debug_info, name='debug_info'),
    
    # CMS
    path('posts/', views.post_list, name='post_list'),
    path('posts/novo/', views.post_create, name='post_create'),
    path('posts/<int:pk>/editar/', views.post_update, name='post_update'),
    path('posts/<int:pk>/deletar/', views.post_delete, name='post_delete'),
    
    path('paginas/', views.page_list, name='page_list'),
    path('paginas/novo/', views.page_create, name='page_create'),
    path('paginas/<int:pk>/editar/', views.page_update, name='page_update'),
    path('paginas/<int:pk>/deletar/', views.page_delete, name='page_delete'),
    
    path('midias/', views.media_list, name='media_list'),
    path('midias/<int:pk>/deletar/', views.media_delete, name='media_delete'),
]
