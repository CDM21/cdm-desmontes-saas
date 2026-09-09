# Documentação oficial usada nas integrações

## Mercado Livre

- Developers: https://developers.mercadolivre.com.br/
- Autenticação e autorização: https://developers.mercadolivre.com.br/autenticacao-e-autorizacao
- Publicação de produtos: https://developers.mercadolivre.com.br/pt_br/publicacao-de-produtos

Observação: para novos desenvolvimentos, a documentação atual orienta considerar o fluxo de **User Products**. O código desta versão mantém uma publicação compatível via `/items` e deixa os erros de validação do marketplace visíveis no painel, para evolução conforme a conta/categoria.

## OLX

- OAuth: https://developers.olx.com.br/anuncio/api/oauth.html
- Importação de anúncios: https://developers.olx.com.br/anuncio/api/import.html
- Status da importação: https://developers.olx.com.br/anuncio/api/publishing_status.html

A aplicação CDM precisa ser cadastrada/homologada como integrador e o anunciante precisa ter plano compatível com integração.

## Shopee

- Open Platform: https://open.shopee.com/

A aplicação precisa possuir Partner ID/Partner Key válidos. Cada loja autoriza o acesso e recebe tokens próprios. A publicação usa o fluxo `v2.product.add_item` e exige categoria, logística e imagens da Shopee.
