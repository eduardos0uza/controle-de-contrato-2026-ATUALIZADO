# Documentação do Painel Administrativo - Hiden Systems

Este documento descreve as funcionalidades, segurança e estrutura do painel administrativo personalizado.

## 🛡️ Segurança

O painel administrativo conta com múltiplas camadas de proteção:

1.  **Role-Based Access Control (RBAC):** Apenas usuários no grupo `administrador` ou `superusuários` podem acessar o painel.
2.  **Autenticação de Dois Fatores (2FA):** 
    - Pode ser ativado/desativado no perfil do usuário.
    - Utiliza códigos numéricos de 6 dígitos enviados por e-mail.
    - Fallback para log no console em ambiente de desenvolvimento.
    - Protegido pelo decorator `@two_factor_required`.
3.  **Rate Limiting:**
    - Limita o número de requisições por IP para evitar ataques de força bruta ou DoS.
    - Implementado via decorator `@rate_limit(key_prefix, limit, period)`.
    - Retorna status `429 Too Many Requests`.
4.  **Logs de Auditoria:**
    - Todas as ações críticas (Criação, Edição, Deleção) são registradas.
    - Captura: Usuário, Ação, Tabela, ID do objeto, Descrição, IP e User Agent.

## 📊 Dashboard

O Dashboard oferece uma visão consolidada do sistema:
- **Métricas de Usuários:** Total, Ativos e Novos no mês.
- **Métricas de Contratos:** Total, Valor Global e Vencidos.
- **Métricas de CMS:** Total de Posts, Páginas e Mídias.
- **Atividade Recente:** Tabela com os últimos logs de auditoria.

## 📝 Funcionalidades (CMS)

O painel inclui um sistema de gerenciamento de conteúdo simplificado:
- **Posts:** Criação e edição de notícias/artigos com suporte a slugs automáticos.
- **Páginas:** Gerenciamento de páginas institucionais estáticas.
- **Mídias:** Galeria para upload e exclusão de imagens e arquivos.

## ⚙️ Sistema

- **Configurações:** Interface para gerenciar variáveis dinâmicas do sistema (SystemSettings).
- **Backup & Restauração:** 
    - Geração de backups em formato JSON via `dumpdata`.
    - Interface para visualização e download de arquivos de backup.
    - Instruções para restauração manual via CLI.

## 🛠️ Estrutura Técnica

- **Views:** Localizadas em `admin_panel/views.py`, protegidas por múltiplos decorators.
- **Segurança:** Lógica de rate limit em `admin_panel/security.py`.
- **Modelos:** `UserProfile`, `AuditLog`, `SystemSetting`, `Post`, `Page`, `Media`.
- **Templates:** Utilizam Bootstrap 5 com design responsivo e componentes reutilizáveis (ex: `sidebar.html`).

---
*Hiden Systems AI - 2026*
