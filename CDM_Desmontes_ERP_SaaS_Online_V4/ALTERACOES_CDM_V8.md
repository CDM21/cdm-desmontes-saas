# CDM DESMONTES V8.0.0 — ALTERAÇÕES

Esta versão preserva a base funcional da V7 e adiciona a camada V8 solicitada para uso comercial.

## Entregue na V8

- Interface revisada e textos principais em português.
- Topo profissional com atalhos de documentos, notificações, compras e perfil.
- Central de notificações persistentes, com contador de não lidas, canal, valor, situação e pedido externo quando existir.
- Toda venda registrada no CDM gera/recebe notificação; a venda local e o webhook do Mercado Livre criam a notificação na própria transação.
- Estoque com cartões, lista, seleção, ações em lote, menu de três pontos, histórico, publicação, compartilhamento, etiqueta e exclusão.
- Visualizador grande das fotos, zoom, anterior/próxima e acesso à edição.
- Processamento de imagem no navegador: fundo uniforme é tratado para branco, a peça é centralizada, recebe margem e é redimensionada sem deformar.
- Fotos em base64 são expostas pelo backend por URL pública do próprio produto para envio aos canais em produção.
- Localizações com modal, sigla manual/automática, descrição, quantidade máxima, depósito, corredor, prateleira e posição.
- Fornecedores com CPF/CNPJ, razão social, fantasia, RG/IE, celular, telefone, CEP, cidade, UF, número, logradouro, bairro, complemento, IBGE, e-mail e situação.
- Busca de CEP via ViaCEP no cadastro de fornecedor.
- Configuração Tributária com abas Inicial, ICMS, PIS, COFINS, IPI e IBS/CBS.
- NF-e com Identificação, Itens, Transporte, Financeiro e Tributação; rascunhos persistentes e integração genérica com provedor fiscal real.
- Mercado Livre: OAuth, publicação/edição, descrição, atributos, preço/estoque, User Products/multi-origem e webhook de pedidos.
- Shopee: OAuth/Open Platform, publicação/edição, preço, estoque e imagens quando a aplicação estiver aprovada e credenciada.
- OLX: OAuth/AutoUpload e sincronização conforme credenciais e homologação da conta.
- Assinatura mensal de R$ 350 via Mercado Pago preservada.
- Administração SaaS, auditoria, backup e isolamento por empresa preservados.

## Dependências externas que não podem ser simuladas

A emissão autorizada de NF-e exige provedor fiscal/certificado/credenciais reais. Shopee e OLX podem exigir aprovação/homologação da aplicação. Mercado Livre, Mercado Pago e demais provedores só podem ser validados de ponta a ponta com contas e credenciais autorizadas.

## Infraestrutura de produção

Antes de clientes reais, usar PostgreSQL persistente, serviço Render pago, domínio/HTTPS, política de backup e monitoramento. O ambiente gratuito continua adequado apenas para testes.
