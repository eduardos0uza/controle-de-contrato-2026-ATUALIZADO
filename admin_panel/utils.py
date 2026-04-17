from .models import AuditLog

def log_audit(request, acao, tabela, objeto_id=None, descricao="", dados_anteriores=None, dados_novos=None, user=None):
    """Gera um log de auditoria no sistema."""
    try:
        AuditLog.objects.create(
            usuario=user or (request.user if request and request.user.is_authenticated else None),
            acao=acao,
            tabela=tabela,
            objeto_id=str(objeto_id) if objeto_id else None,
            descricao=descricao,
            dados_anteriores=dados_anteriores,
            dados_novos=dados_novos,
            ip_address=request.META.get('REMOTE_ADDR') if request else None,
            user_agent=request.META.get('HTTP_USER_AGENT') if request else None
        )
    except Exception as e:
        print(f"ERRO AO GERAR LOG DE AUDITORIA: {e}")
