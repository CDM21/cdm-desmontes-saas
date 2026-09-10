# CDM Desmontes V8 — checklist de produção

## Antes de trocar a versão principal

1. Suba a V8 primeiro no serviço de teste usando a branch V8.
2. Faça login com conta de teste e confira painel, cadastro de peça, fotos, localização, fornecedor, tributação, venda, baixa de estoque, financeiro, etiquetas, notificações e rascunho fiscal.
3. Teste Mercado Livre com uma conta autorizada antes de liberar clientes.
4. Valide Shopee/OLX somente quando as aplicações estiverem aprovadas/homologadas pelos provedores.
5. Não coloque tokens nem senhas em arquivos do Git.

## Infraestrutura recomendada para clientes reais

- PostgreSQL persistente.
- Serviço web de produção sem armazenamento efêmero para dados críticos.
- `SECRET_KEY` e `APP_ENCRYPTION_KEY` fortes em variáveis de ambiente.
- Backup periódico.
- Domínio próprio e HTTPS.
- Monitoramento de erros e disponibilidade.
- Planejamento de armazenamento de imagens para volume maior.

## Variáveis principais

Consulte `backend/.env.example`. Em produção, configure os valores somente no painel seguro do provedor de hospedagem.

A emissão real de NF-e exige `FISCAL_PROVIDER_URL` e `FISCAL_PROVIDER_TOKEN`, além da configuração/certificado exigidos pelo provedor fiscal escolhido.

## Publicação

O `render.yaml` foi mantido compatível com a estrutura atual do repositório, em que o projeto fica dentro da pasta `CDM_Desmontes_ERP_SaaS_Online_V4`.


## Assistente CDM

Para ativar respostas com IA externa, configure no servidor:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `ASSISTANT_MONTHLY_MESSAGES=1000`

Sem essas variáveis, o Assistente CDM continua disponível em modo de inteligência local para perguntas básicas sobre vendas, estoque e financeiro.

A empresa não recebe nem vê a chave do servidor. Cada consulta é filtrada pelo `company_id` do usuário autenticado para evitar mistura de dados entre assinantes.
