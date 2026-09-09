# CDM Desmontes ERP — SaaS / Multiempresa

Versão atualizada do CDM Desmontes com visual de ERP profissional, cadastro multiempresa, assinatura e integração self-service com Mercado Livre, Shopee e OLX.

## O que mudou

- Menu lateral completo no estilo ERP de desmanche/autopeças.
- Barra superior vermelha com busca, atalhos e menu do usuário.
- Tema claro/escuro.
- Tela **Informações da Empresa** com CNPJ, IE, regime tributário, responsável, endereço, telefone e demais dados.
- Cadastros de sucatas, peças, grupos, clientes, localizações, transportadoras, vendedores, fornecedores e configuração tributária.
- Estoque em cards com dados/compatibilidade, imagens, busca, filtros, exportação CSV e impressão/PDF pelo navegador.
- Vendas, financeiro, fluxo de caixa, etiquetas, relatórios, expedição e área fiscal.
- Multiempresa: cada assinante possui dados, estoque, vendas e integrações separados.
- Cadastro de nova empresa pelo próprio usuário.
- Status de assinatura por empresa.
- Marketplace self-service: cada cliente autoriza a **própria** conta sem passar senha/token para você.

## Como abrir no Windows / VS Code

### 1. Backend

Abra um terminal na pasta principal e execute:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

Backend: http://localhost:8000
Documentação: http://localhost:8000/docs

### 2. Frontend

Abra outro terminal na pasta principal:

```powershell
cd frontend
npm install
npm run dev
```

Frontend: http://localhost:5173

### Usuário local inicial

- E-mail: `admin@autodesmonte.local`
- Senha: `admin123`

> Troque a senha/chaves antes de produção.

## Integrações: como funciona no SaaS

Você configura **uma vez** no servidor as credenciais da aplicação CDM:

- Mercado Livre: `ML_CLIENT_ID`, `ML_CLIENT_SECRET`, `ML_REDIRECT_URI`
- Shopee: `SHOPEE_PARTNER_ID`, `SHOPEE_PARTNER_KEY`, `SHOPEE_REDIRECT_URI`
- OLX: `OLX_CLIENT_ID`, `OLX_CLIENT_SECRET`, `OLX_REDIRECT_URI`

Depois disso, cada cliente assinante entra em **Integrações → Central de integrações** e clica em **Conectar**. O marketplace abre sua tela oficial de autorização e o backend salva o token criptografado vinculado somente à empresa daquele cliente.

### Mercado Livre

O cliente autoriza a conta via OAuth. No cadastro da peça, ele informa os dados obrigatórios de publicação, como categoria do Mercado Livre, preço, estoque e imagens quando aplicável.

### Shopee

O cliente autoriza a loja. No cadastro da peça, ele pode informar categoria, logística e IDs de imagem da Shopee, além de peso/dimensões.

### OLX

O cliente autoriza a conta via OAuth. O sistema envia os anúncios pela API de importação. Para publicação real, a aplicação CDM precisa estar homologada como integrador OLX e a conta do anunciante precisa ter plano compatível com integração.

## Assinatura mensal

A estrutura multiempresa já possui `Subscription` por empresa e bloqueia integrações/automações quando a assinatura não está ativa.

Foi incluído um webhook genérico:

`POST /api/billing/webhook`

Ele permite que o gateway de cobrança escolhido altere a assinatura para `active`, `past_due`, `canceled` etc. O segredo fica em `BILLING_WEBHOOK_SECRET`.

A etapa que ainda depende da sua escolha comercial é **qual gateway de pagamento** vai vender/renovar o acesso mensal (Mercado Pago, Pagar.me, Stripe, Asaas etc.). Depois de escolhido, o checkout/webhook específico pode ser ligado nesse ponto sem mudar a arquitetura do sistema.

## Banco de dados

Por padrão usa SQLite:

`backend/cdm_desmontes.db`

Para produção, recomenda-se migrar para PostgreSQL e usar HTTPS.

## Segurança

- Tokens de marketplaces são armazenados criptografados.
- Cada endpoint operacional filtra por `company_id`.
- O cliente final não precisa informar credenciais de aplicativo; apenas autoriza a própria conta no marketplace.
- Defina `SECRET_KEY` forte e `APP_ENCRYPTION_KEY` em produção.

