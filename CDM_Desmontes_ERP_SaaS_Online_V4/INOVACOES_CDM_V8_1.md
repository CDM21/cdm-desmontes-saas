# CDM Desmontes V8.1 — Inovações adicionadas

## Liberadas automaticamente pela assinatura
- Assistente CDM por empresa
- Painel do Dono
- Radar de Oportunidades
- Desmonte Inteligente
- Preço Inteligente
- Proteção de Venda
- Qualidade da peça
- Garantia por QR Code
- Catálogo público de peças
- Botão de atendimento por WhatsApp no catálogo

## Assistente CDM
Cada empresa usa o mesmo mecanismo do SaaS, porém com contexto isolado por `company_id`.
Não há criação manual de um bot para cada empresa.

Novos cadastros têm acesso durante o período de teste. Depois, o acesso depende do status da assinatura.
O webhook do Mercado Pago atualiza a assinatura; quando ela fica ativa, o assistente é liberado automaticamente.

## Controle de custo
O limite padrão é de 1000 mensagens mensais por empresa e pode ser ajustado por variável de ambiente.
O sistema possui modo local quando a integração de IA externa não estiver configurada.

## Inteligência operacional
As recomendações de preço, radar e desmonte usam o histórico da própria empresa. Elas não fingem consultar preço de mercado externo quando esse dado não existe.

## Dependências externas ainda necessárias
Automação total de conversas pelo WhatsApp exige API oficial do WhatsApp Business/Meta.
IA externa exige credencial de API configurada no servidor.
As funções continuam separadas dos dados de outras empresas.
