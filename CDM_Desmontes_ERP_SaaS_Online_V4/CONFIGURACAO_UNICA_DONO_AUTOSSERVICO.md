# CDM Desmontes — configuração única do dono do SaaS

Esta versão foi preparada para que o cliente final configure a própria empresa sem depender do dono do CDM.

## 1. Variáveis globais (você configura uma única vez no Render)

Marketplaces:
- `ML_CLIENT_ID`, `ML_CLIENT_SECRET`, `ML_REDIRECT_URI`
- `SHOPEE_PARTNER_ID`, `SHOPEE_PARTNER_KEY`, `SHOPEE_REDIRECT_URI`
- `OLX_CLIENT_ID`, `OLX_CLIENT_SECRET`, `OLX_REDIRECT_URI`

Fiscal:
- `FOCUS_MASTER_TOKEN`: token da conta integradora Focus NFe usado pelo CDM para cadastrar/atualizar empresas e enviar certificado A1 sem expor credenciais técnicas ao cliente.
- `APP_ENCRYPTION_KEY`: chave Fernet usada para criptografar tokens por empresa.

Sincronização:
- `INTEGRATION_SYNC_SECONDS=180` (opcional; padrão 3 minutos).

Depois que essas variáveis globais estiverem configuradas, cada cliente faz a própria autorização pela interface do CDM.

## 2. Fluxo do cliente

1. Cadastra a conta e entra no CDM.
2. Abre **Empresa**, digita o CNPJ e usa **Buscar dados pelo CNPJ**.
3. Confere os dados e informa Inscrição Estadual/regime quando necessário.
4. Abre **Fiscal > Configuração Tributária** e define os padrões fiscais com o contador.
5. Abre **Fiscal > Emitir NF-e**, envia o certificado A1 e faz o teste em homologação.
6. Abre **Integrações**, clica em Mercado Livre/Shopee/OLX e autoriza a própria conta na página oficial do canal.
7. Cadastra peças e começa a publicar.

## 3. Segurança implementada

- Senhas dos marketplaces nunca passam pelo CDM: autorização via OAuth quando a plataforma oferece esse fluxo.
- Tokens por empresa ficam criptografados no banco.
- O arquivo/senha do certificado A1 não são persistidos pelo CDM; o arquivo é enviado ao provedor fiscal durante a configuração.
- Dados são isolados por `company_id`.
- Produção e homologação fiscal ficam separados.

## 4. Automação

O `integration_scheduler.py` acompanha automaticamente:
- lotes OLX em `pending/queued/processing` até aceitação ou recusa;
- NF-e em processamento até autorização/rejeição;
- atualização dos links de XML e DANFE quando retornados pelo provedor.

O cliente ainda pode usar os botões de consulta manual no histórico, mas não depende deles para o fluxo normal.
