# CDM Desmontes — V7.0.0

Atualização focada em uso comercial e clientes SaaS.

## Interface
- Fontes maiores em todo o sistema.
- Campos e botões maiores para uso diário.
- Fotos de produtos centralizadas com `object-fit: contain`: a peça aparece inteira, sem corte nem deformação.
- Mantida a opção de fundo branco da V6.

## Produtos e marketplaces
- Mantém edição de produto, etiquetas individuais/em lote e chaves por canal da V6.
- Mercado Livre: criação/atualização de anúncio, descrição, preço/estoque e atributos obrigatórios por categoria.
- Mercado Livre: webhook de pedidos para registrar venda e baixar estoque local de forma idempotente.
- Shopee: fluxo real preparado para criar/atualizar produto, preço, estoque e enviar imagens quando a conta Open Platform tiver acesso.
- OLX: fluxo real via AutoUpload para inserir/editar e consultar publicados quando o integrador tiver credenciais/homologação.
- Erros dos canais ficam registrados na listagem sem derrubar a venda local.

## Vendas / estoque
- PDV com carrinho de vários itens.
- Cliente opcional.
- Baixa de estoque em transação.
- Registro de itens da venda.
- Registro automático de movimentação de estoque.
- Entrada financeira automática da venda.
- Sincronização de estoque com canais conectados após a venda.

## Assinatura
- Plano padrão: R$ 350/mês.
- Checkout recorrente via Mercado Pago (`/preapproval`).
- Webhook de cobrança e atualização do status da assinatura.
- Cancelamento de assinatura pelo sistema.
- Validação HMAC do webhook quando `MP_WEBHOOK_SECRET` estiver configurado.

## Administração SaaS
- Nova área "Clientes SaaS" para administradores da plataforma.
- Lista empresas, usuários, produtos, vendas e integrações.
- Permite ativar/bloquear empresa.
- Permite ajustar status de assinatura.
- Backup lógico completo em JSON gzip, com tokens de marketplace permanecendo criptografados.

## Segurança
- Limite simples de tentativas de login/cadastro por IP.
- Senha mínima de 8 caracteres para novos cadastros.
- Headers de segurança HTTP.
- Área administrativa protegida por `PLATFORM_ADMIN_EMAILS`.
- Auditoria de ações administrativas e vendas.

## Importante
Ativação real de cobrança e marketplaces depende das credenciais oficiais de cada provedor no Render. Shopee/OLX também dependem da aprovação/permissões concedidas à aplicação do integrador. Não há como o CDM contornar essa aprovação.
