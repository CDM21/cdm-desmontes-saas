# CDM Desmontes — V6

Atualização focada em operação de estoque, etiquetas, fotos e controle individual de marketplaces.

## Produtos
- Botão **Editar** em cada card e na visualização em lista.
- Edição reutiliza o mesmo cadastro e não cria um novo produto.
- Opções **Salvar alterações** e **Salvar e sincronizar canais ativos**.
- Exclusão em lote arquiva os itens selecionados.
- Visualização em **Card** ou **Lista**.
- Seleção de itens com destaque visual.

## Marketplaces por produto
Cada peça agora possui chaves independentes:
- Mercado Livre: ativar/desativar
- Shopee: ativar/desativar
- OLX: ativar/desativar

O comando "Publicar / sincronizar" processa somente os canais ativados para aquela peça.

### Mercado Livre
A tela de configuração da peça inclui:
- condição: novo, usado ou recondicionado (recondicionado é tratado como usado na publicação quando necessário);
- garantia;
- tipo de listagem;
- opção de deixar o frete automático, Mercado Envios ou a combinar;
- frete grátis;
- retirada pessoalmente;
- categoria sugerida pela API.

## Fotos
- Upload de imagens direto do computador.
- Redimensionamento para até 1200 px.
- Compressão JPEG antes de salvar.
- Opção **Remover fundo e deixar branco** durante o upload.
- Botão **Fundo branco** em cada imagem já adicionada.
- Remoção individual de fotos.
- Imagens processadas ficam armazenadas no banco como data URL e são expostas pelo backend em uma URL pública para os marketplaces conseguirem buscá-las.

Observação: a remoção de fundo desta versão é automática por similaridade de cor do fundo. Funciona melhor em fotos feitas contra fundo uniforme; não é segmentação por IA.

## Etiquetas
- Seleção de produtos no estoque.
- Botão **Gerar Etiquetas** no topo.
- Botão **Etiqueta** em cada produto.
- Impressão individual ou em lote.
- Modelo padrão 100 x 50 mm inspirado na referência enviada:
  - nome da empresa;
  - QR Code;
  - código grande da peça;
  - descrição;
  - marca/modelo/ano e OEM;
  - SKU e condição.

## Banco de dados
A V6 inclui migração leve automática no startup para acrescentar os novos campos ao banco PostgreSQL/SQLite de instalações V4/V5 existentes.

## Versão
API: 6.0.0
Mensalidade padrão: R$ 350,00 (mantida da V5)
