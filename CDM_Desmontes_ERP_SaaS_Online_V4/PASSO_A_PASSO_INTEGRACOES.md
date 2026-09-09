# Passo a passo — integrações self-service

## 1. Copie o arquivo de configuração

Na pasta `backend`:

```powershell
copy .env.example .env
```

## 2. Configure a aplicação Mercado Livre

Preencha no `.env`:

```env
ML_CLIENT_ID=
ML_CLIENT_SECRET=
ML_REDIRECT_URI=http://localhost:8000/api/marketplaces/oauth/mercadolivre/callback
```

Cadastre a mesma redirect URI na aplicação do Mercado Livre.

## 3. Configure a aplicação Shopee

```env
SHOPEE_PARTNER_ID=
SHOPEE_PARTNER_KEY=
SHOPEE_REDIRECT_URI=http://localhost:8000/api/marketplaces/oauth/shopee/callback
```

## 4. Configure o integrador OLX

```env
OLX_CLIENT_ID=
OLX_CLIENT_SECRET=
OLX_REDIRECT_URI=http://localhost:8000/api/marketplaces/oauth/olx/callback
```

A aplicação precisa estar homologada para o escopo de autoupload.

## 5. Reinicie o backend

```powershell
uvicorn app.main:app --reload
```

## 6. Cliente final

O cliente:

1. Cria/recebe a conta CDM da própria empresa.
2. Acessa **Integrações → Central de integrações**.
3. Clica em **Conectar Mercado Livre**, **Conectar Shopee** ou **Conectar OLX**.
4. Faz login diretamente no marketplace.
5. Autoriza o CDM.
6. Volta ao painel com a conta marcada como conectada.
7. Cadastra a peça e marca **Publicar automaticamente**.

Você não precisa pedir a senha do marketplace do cliente.
