# Validação técnica — CDM Desmontes V8

Data da revisão: 10/09/2026.

## Verificações executadas no pacote

- Compilação sintática de todos os módulos Python do backend: aprovada.
- Validação sintática do `frontend/src/main.jsx` em JSX/ES2022: aprovada, zero diagnósticos.
- Inicialização da API V8 com banco SQLite isolado: aprovada.
- Cadastro de nova empresa/usuário: aprovado.
- Cadastro de localização com sigla automática: aprovado.
- Cadastro de fornecedor com os novos campos: aprovado.
- Atualização da configuração tributária V8: aprovada.
- Cadastro de peça com estoque 3: aprovado.
- Venda de 1 unidade: aprovada; estoque resultante 2.
- Registro financeiro associado à venda: preservado pelo fluxo de vendas.
- Notificação persistente da venda: aprovada.
- Contador de não lidas e marcar todas como lidas: aprovados.
- Criação de rascunho de NF-e: aprovada.
- Proteção contra falsa emissão fiscal: aprovada; sem provedor configurado, a API recusa a emissão real com mensagem clara.

## Validações que exigem serviço externo

Mercado Livre, Shopee, OLX, Mercado Pago e autorização fiscal real precisam de credenciais/contas autorizadas e resposta dos próprios provedores. O pacote não contém segredos de produção.

O build Vite final deve ser executado após `npm install` na máquina/contêiner de destino. O código JSX foi validado separadamente; `node_modules` não é distribuído no ZIP para evitar arquivos nativos de outra plataforma.
