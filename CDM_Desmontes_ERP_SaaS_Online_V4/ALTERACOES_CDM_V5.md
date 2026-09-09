# CDM Desmontes ERP SaaS — V5

## O que mudou

### Mercado Livre
- Mantido OAuth por empresa: cada assinante conecta a própria conta, sem fornecer senha ao administrador do CDM.
- O callback agora registra o erro real da tentativa de autorização (sem gravar Client Secret/tokens em texto).
- Nova rota de diagnóstico por marketplace.
- A tela de Integrações mostra o último erro e o Redirect URI efetivamente usado pelo servidor.
- Renovação automática do access token do Mercado Livre continua usando o refresh token armazenado criptografado.

### Cadastro de veículos/sucatas
- Novo catálogo automotivo interno com dezenas de marcas e centenas de modelos usados no Brasil.
- Fluxo Marca -> Modelo.
- Exemplo: Toyota -> Corolla, Corolla Cross, RAV4, Hilux, SW4 etc.
- Permite modelo personalizado caso não esteja na lista.
- Cadastro ganhou combustível, câmbio e outros custos.

### Cadastro de peças
- Peça pode ser vinculada ao veículo/sucata de origem.
- Ao escolher o veículo, marca, modelo e ano são preenchidos no cadastro da peça.
- Marca -> Modelo também funciona para peça avulsa/compatibilidade.
- Campos de lado, posição, OEM, preço, custo, estoque, imagens, dimensões e dados específicos dos marketplaces permanecem.
- Publicação automática continua separada por empresa.

### Assinatura de R$ 350/mês
- Nova tela “Assinatura” no menu lateral.
- Preço padrão: R$ 350/mês (`CDM_MONTHLY_PRICE=350`).
- Checkout recorrente preparado para Mercado Pago via API de Assinaturas.
- Cada assinatura usa `external_reference=cdm_company_ID`, permitindo ativar a empresa correta.
- Webhook consulta o status diretamente na API do Mercado Pago antes de alterar o plano local.
- Botão “Atualizar status” para sincronização manual.

## Variáveis novas no Render

Adicione no Web Service `cdm-desmontes-saas` (ou em um Environment Group vinculado a ele):

- `MP_ACCESS_TOKEN` = Access Token da sua aplicação/conta Mercado Pago
- `CDM_MONTHLY_PRICE` = `350`

Não publique `MP_ACCESS_TOKEN` no GitHub.

## Webhook Mercado Pago

Configure as notificações de Assinaturas para:

`https://cdm-desmontes-saas.onrender.com/api/billing/mercadopago/webhook`

## Mercado Livre — Redirect URI

Deve continuar exatamente:

`https://cdm-desmontes-saas.onrender.com/api/marketplaces/oauth/mercadolivre/callback`

No CDM, em Integrações > Mercado Livre, use “Verificar configuração” para confirmar a URI real usada pelo servidor e visualizar o último erro OAuth.

### Segurança antes de vender
- Login não tenta mais criar automaticamente o usuário padrão `admin123`.
- `/api/auth/bootstrap` fica bloqueado em produção, a menos que `ALLOW_BOOTSTRAP=true` seja definido explicitamente.
- Novos clientes entram por “Criar conta”, com empresa e assinatura separadas.
- Módulos operacionais exigem assinatura ativa/trial válida também no backend (HTTP 402 quando vencida).
