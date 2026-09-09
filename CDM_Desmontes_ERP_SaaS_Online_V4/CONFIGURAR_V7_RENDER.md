# Configurar CDM V7 no Render

A V7 usa a mesma pasta interna e o mesmo Blueprint da V6.

## Variáveis de ambiente necessárias

### Administração do SaaS
`PLATFORM_ADMIN_EMAILS=seu-email-de-login-no-cdm`

Não envie esse e-mail junto com senhas em chats. Defina diretamente no painel do Render.

### Mercado Livre
- `ML_CLIENT_ID`
- `ML_CLIENT_SECRET`
- `ML_REDIRECT_URI=https://cdm-desmontes-saas.onrender.com/api/marketplaces/oauth/mercadolivre/callback`

URL para notificações de pedidos:
`https://cdm-desmontes-saas.onrender.com/api/marketplaces/webhooks/mercadolivre`

### Mercado Pago — R$ 350/mês
- `MP_ACCESS_TOKEN`
- `CDM_MONTHLY_PRICE=350`
- `MP_WEBHOOK_SECRET` (recomendado)

Webhook:
`https://cdm-desmontes-saas.onrender.com/api/billing/mercadopago/webhook`

### Shopee
- `SHOPEE_PARTNER_ID`
- `SHOPEE_PARTNER_KEY`
- `SHOPEE_REDIRECT_URI`

A publicação real só fica disponível se a aplicação Open Platform estiver aprovada e tiver as permissões/endpoints de produto, imagem, preço e estoque.

### OLX
- `OLX_CLIENT_ID`
- `OLX_CLIENT_SECRET`
- `OLX_REDIRECT_URI`

A publicação real usa a integração AutoUpload e depende de credenciais/homologação da OLX.

## Depois de salvar variáveis
Faça `Manual Deploy -> Deploy latest commit` no Render se o serviço não redeployar sozinho.

## Backup
Entre em `Clientes SaaS` com uma conta cujo e-mail esteja em `PLATFORM_ADMIN_EMAILS` e use `Baixar backup agora`.
Guarde o arquivo fora do Render.
