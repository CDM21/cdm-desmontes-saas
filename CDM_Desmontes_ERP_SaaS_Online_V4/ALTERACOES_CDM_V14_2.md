# CDM Desmontes V14.2 — Cliente Independente

Atualização focada em deixar o cliente configurar e operar o sistema com o mínimo de suporte manual.

## Fiscal / NF-e
- Configuração fiscal refeita em uma única tela guiada.
- Progresso visual com empresa, tributação, certificado A1 e conexão fiscal.
- Busca de dados públicos pelo CNPJ dentro da própria configuração fiscal.
- Tentativa de preenchimento automático da inscrição estadual e regime tributário quando disponíveis na consulta pública.
- Edição e salvamento dos dados essenciais da empresa sem sair da tela fiscal.
- Configuração tributária básica sem obrigar o cliente a navegar por outro menu.
- NCM padrão passa a ser opcional; cada peça pode informar o NCM correto na emissão.
- Upload e substituição do certificado A1 com feedback visual mais claro.
- Mensagens técnicas do provedor foram trocadas por mensagens compreensíveis para o cliente.
- O certificado não é marcado como configurado se o serviço fiscal global do SaaS ainda não estiver disponível.
- Checklist do teste final coerente com os requisitos reais de emissão.
- Depois de configurado, o cliente pode voltar à configuração fiscal por um botão direto na tela de emissão.

## Marketplaces
- A área de conexão ficou menos técnica.
- “Diagnóstico” foi substituído por “Ver situação”.
- Informações de callback/redirect deixaram de ser exibidas ao cliente final.
- Textos explicam a ação necessária sem pedir chaves técnicas.

## Interface
- O botão de retorno do Portal do Dono fica fixo no canto inferior e não pode cobrir o cabeçalho ou formulários.
- Rodapé atualizado para V14.2.
- Nova organização visual do assistente fiscal, com menos texto e ações mais diretas.
- Melhorias de responsividade para celular e telas menores.

## Validações realizadas
- Backend validado com `python -m compileall backend/app -q`.
- JSX validado por parser TypeScript sem erros de sintaxe.
- O build Vite completo deve ser executado no computador/repositório antes do push para confirmar as dependências do ambiente local.
