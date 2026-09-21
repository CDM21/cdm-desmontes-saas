# CDM Desmontes V14.3 — Conectar e Pronto

## Experiência do cliente
- Central de marketplaces simplificada: conectar, autorizar e pronto.
- Informações técnicas de API ficam fora da experiência normal do cliente.
- Botão “Voltar ao Portal do Dono” reduzido a um atalho discreto.
- Tela fiscal mais limpa, sem o cabeçalho grande que podia ficar atrás da barra superior.

## Fiscal / NF-e
- NCM limitado a 8 dígitos no frontend e validado no backend.
- Valores legados inválidos de NCM (inclusive autofill de e-mail) são limpos.
- CFOP validado com 4 dígitos antes da emissão.
- Mensagem do emissor fiscal reescrita para não parecer erro do cliente.

## Cobrança automática
- Mantida a regra dos 10 primeiros clientes fundadores com implantação grátis.
- A partir do 11º cliente: implantação de R$ 1.500,00 uma única vez.
- Depois da implantação: assinatura recorrente de R$ 350,00/mês.
- Implantação usa Checkout Pro do Mercado Pago e a mensalidade usa assinatura recorrente.
- Webhook e sincronização consultam o Mercado Pago novamente antes de marcar pagamento como confirmado.
- A tela do cliente mostra somente o próximo passo necessário.

## Segurança do fluxo
- A implantação só é marcada como paga quando o Mercado Pago informa pagamento aprovado.
- A reconciliação também ocorre pela consulta de pagamentos, reduzindo dependência exclusiva do webhook.
