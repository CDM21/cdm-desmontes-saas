# Alterações — CDM Desmontes ERP V3

## Interface

- Sidebar inspirada no fluxo de ERPs profissionais de desmanche.
- Barra superior vermelha com busca e atalhos.
- Menu de usuário com informações da empresa, tema e logout.
- Tema claro e escuro.
- Estoque em cards com abas visuais Dados / Compatibilidade.
- Ações de exportação e filtros.

## Cadastros

- Cadastro de Sucatas
- Cadastro de Peças
- Grupo de Peças
- Clientes
- Localizações
- Transportadoras
- Vendedores
- Fornecedores
- Configuração Tributária
- Informações da Empresa

## SaaS / Assinatura

- Company: separação por empresa.
- Subscription: plano/status/vencimento por empresa.
- Registro self-service de nova empresa/usuário.
- Isolamento de veículos, peças, vendas, financeiro e cadastros por empresa.
- Webhook genérico para ativação de assinatura pelo gateway de pagamento.

## Marketplaces

- Conexões por empresa.
- Tokens criptografados.
- Botões de autorização self-service.
- Mercado Livre OAuth + publicação + descrição.
- Shopee autorização + token/refresh + add_item.
- OLX OAuth + autoupload/import + status de processamento.
- Cadastro da peça possui campos específicos para cada canal.
- Opção de publicar automaticamente ao cadastrar a peça.

## Importante para produção

As credenciais de aplicação e homologações não podem ser inventadas pelo sistema. Elas devem ser obtidas oficialmente nas plataformas. Depois de configuradas uma vez no backend, os seus clientes conectam as contas deles sozinhos pelo painel.
