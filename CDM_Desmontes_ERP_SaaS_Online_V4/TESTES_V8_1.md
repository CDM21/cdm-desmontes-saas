# Testes CDM Desmontes V8.1

Depois de instalar e iniciar localmente, confira:

1. Criar/entrar em uma empresa com teste ou assinatura ativa.
2. Abrir Inteligência CDM > Assistente CDM e perguntar "Quanto vendi hoje?".
3. Abrir Painel do Dono e conferir os indicadores.
4. Abrir Radar de Oportunidades.
5. Selecionar uma sucata no Desmonte Inteligente.
6. Selecionar uma peça no Preço Inteligente.
7. Em Proteção de Venda, conferir um SKU de uma venda.
8. Salvar prova de envio com observação/fotos.
9. Gerar QR de garantia para uma peça vendida.
10. Abrir o Catálogo público pelo Painel do Dono e testar a busca/WhatsApp.

Validação feita antes do empacotamento:
- Python: todos os arquivos do backend passam em compilação de sintaxe.
- JSX: frontend passa na análise de sintaxe.
- Nenhuma dependência npm nova foi adicionada.

Observação: IA externa só funciona com OPENAI_API_KEY e OPENAI_MODEL configurados. Sem essas variáveis, o Assistente CDM usa o modo local.
