# Colocar o CDM Desmontes online no Render

Esta versão V4 foi preparada para rodar localmente e também em produção.

## Arquitetura recomendada para o primeiro teste

- 1 Web Service no Render, servindo FastAPI + frontend React no mesmo domínio HTTPS.
- 1 PostgreSQL no Render para empresas, usuários, estoque, vendas, assinaturas e integrações.
- Depois, domínio próprio pode ser conectado sem alterar o sistema.

## Antes de começar

Você precisa de uma conta no GitHub e uma conta no Render.

## 1. Enviar o projeto para o GitHub

Crie um repositório privado, por exemplo `cdm-desmontes-saas`, e envie todo o conteúdo desta pasta. Não envie `backend/.env`, `venv`, `.venv` ou `node_modules`.

## 2. Criar no Render por Blueprint

No Render: New > Blueprint > conecte o repositório. O arquivo `render.yaml` cria:

- `cdm-desmontes-saas`: web service HTTPS
- `cdm-desmontes-db`: PostgreSQL

Quando o deploy terminar, abra a URL `https://...onrender.com/api/health` e confirme `status: ok`.

## 3. Descobrir a URL pública

O serviço recebe uma URL HTTPS do tipo:

`https://cdm-desmontes-saas-xxxx.onrender.com`

O CDM usa a variável automática `RENDER_EXTERNAL_URL`, portanto o frontend e os callbacks OAuth funcionam no mesmo domínio.

## 4. URLs de callback dos marketplaces

Substitua `SEU_DOMINIO` pela URL pública do Render:

- Mercado Livre: `https://SEU_DOMINIO/api/marketplaces/oauth/mercadolivre/callback`
- Shopee: `https://SEU_DOMINIO/api/marketplaces/oauth/shopee/callback`
- OLX: `https://SEU_DOMINIO/api/marketplaces/oauth/olx/callback`

Cadastre essas URLs nas plataformas oficiais.

## 5. Adicionar credenciais no Render

Render > serviço CDM > Environment. Adicione somente as credenciais obtidas nos portais oficiais:

- `ML_CLIENT_ID`
- `ML_CLIENT_SECRET`
- `SHOPEE_PARTNER_ID`
- `SHOPEE_PARTNER_KEY`
- `OLX_CLIENT_ID`
- `OLX_CLIENT_SECRET`

Não coloque tokens dos clientes. Cada empresa autoriza a própria conta pelo painel do CDM.

## 6. Testar

Cadastre uma conta no CDM, abra Integrações e clique em Conectar. Após autorização, a conta deve aparecer como conectada.

## Produção comercial

O plano gratuito de banco do Render é adequado apenas para testes e atualmente expira após 30 dias. Antes de vender assinaturas, use um banco persistente pago, configure backups e adicione migrações de banco (Alembic).
