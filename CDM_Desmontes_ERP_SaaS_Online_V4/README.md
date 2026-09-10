# CDM Desmontes — V8.1.0

ERP SaaS para desmanches e autopeças, com estoque, sucatas, vendas, financeiro, etiquetas, cadastros, área fiscal, assinatura e integração com canais de venda.

## Começar no Windows / VS Code

1. Extraia o ZIP completo.
2. Abra no VS Code a pasta `CDM_Desmontes_ERP_SaaS_Online_V4`.
3. Abra **Terminal > New Terminal**.
4. Execute `./INSTALAR_CDM.bat` (no PowerShell, também pode usar `.\INSTALAR_CDM.bat`).
5. Depois execute `./INICIAR_CDM.bat`.
6. O sistema abre em `http://localhost:5173`.

> Não cole no terminal o texto `PS C:\...>` nem mensagens de erro; cole somente os comandos.

## V8

A V8 preserva a base funcional da V7 e adiciona interface revisada em português, cartões de estoque aprimorados, tratamento de fotos com fundo branco/centralização, visualizador com zoom, Localizações, Fornecedores, Configuração Tributária ampliada, NF-e estruturada, central de notificações persistentes e melhorias nos canais Mercado Livre, Shopee e OLX.

Consulte `ALTERACOES_CDM_V8.md` para a lista completa.

## Notificações de venda

As vendas registradas no CDM recebem notificação persistente. Venda local e pedido recebido pelo webhook do Mercado Livre criam a notificação junto com a venda. O painel também garante uma notificação para vendas existentes/importadas que já estejam salvas no banco, mantendo canal, valor, situação e pedido externo quando disponível.

## Fotos de produtos

O cadastro permite enviar imagens, manter a peça inteira sem deformação e gerar uma versão quadrada com fundo branco e margem. A remoção de fundo incluída é local, sem serviço pago, e funciona melhor quando o fundo original é relativamente uniforme. Fundos complexos podem exigir tratamento manual posterior.

## NF-e

A tela fiscal possui Identificação, Itens, Transporte, Financeiro e Tributação, além de rascunhos persistentes. A autorização fiscal real não é simulada: para emitir uma NF-e válida é necessário contratar/configurar um provedor fiscal compatível, certificado e credenciais da empresa. As variáveis preparadas são `FISCAL_PROVIDER_URL` e `FISCAL_PROVIDER_TOKEN`.

## Canais de venda

Mercado Livre usa autorização OAuth e possui publicação, atualização, estoque, descrição, atributos e processamento de pedidos recebido pelo webhook. Shopee e OLX possuem a base de autorização/publicação/sincronização, mas o funcionamento real depende de aplicação aprovada, credenciais válidas e, quando exigido, homologação do provedor.

Cada empresa cliente autoriza a própria conta. O operador do CDM não precisa receber a senha da conta do cliente.

## Assinatura

O plano padrão permanece em R$ 350/mês. A integração recorrente com Mercado Pago da V7 foi preservada.

## Produção

Antes de liberar clientes reais, use banco PostgreSQL persistente, serviço de aplicação adequado à produção, backups, domínio/HTTPS, monitoramento e armazenamento persistente para crescimento de imagens. SQLite é apropriado apenas para desenvolvimento e testes simples.

Consulte `CONFIGURAR_V8_PRODUCAO.md` antes de publicar a V8 no ambiente principal.


## Inteligência CDM

A V8.1 adiciona um núcleo de inovação com:

- Assistente CDM por empresa, liberado automaticamente durante o teste e enquanto a assinatura estiver ativa.
- Painel do Dono.
- Radar de Oportunidades.
- Desmonte Inteligente.
- Preço Inteligente.
- Proteção de Venda com conferência de SKU e prova de envio.
- Qualidade da peça e prazo de garantia no cadastro.
- Garantia digital por QR Code.
- Catálogo público de peças com busca e botão de WhatsApp.

### Assistente automático por empresa

Não é necessário criar um assistente manualmente para cada cliente. O sistema identifica a empresa pelo login e usa somente os dados associados ao `company_id` daquela conta.

Fluxo:
1. A empresa cria a conta e recebe o período de teste.
2. O Assistente CDM já fica disponível no teste.
3. Se o teste vencer sem pagamento, o acesso é bloqueado junto com os módulos operacionais.
4. Quando o Mercado Pago confirmar a assinatura, o status vira ativo e o Assistente CDM é liberado novamente automaticamente.
5. Se a assinatura for cancelada/inativada, o acesso volta a ser bloqueado.

O limite mensal padrão é configurável por `ASSISTANT_MONTHLY_MESSAGES` e começa em 1000 mensagens por empresa. Sem `OPENAI_API_KEY`/`OPENAI_MODEL`, o sistema mantém um modo local para consultas operacionais básicas. Com as duas variáveis configuradas, o Assistente CDM pode usar IA externa.

A integração de IA usa uma única credencial no servidor; o cliente não precisa informar senha ou conta de IA.
