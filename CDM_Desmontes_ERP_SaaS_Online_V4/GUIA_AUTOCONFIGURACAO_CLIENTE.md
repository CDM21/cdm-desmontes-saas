# CDM Desmontes — configuração sem depender do suporte

## Objetivo
O cliente cria a conta e o próprio CDM mostra o que falta para começar a operar. Chaves técnicas de Mercado Livre, Shopee, OLX e Focus NFe ficam somente no servidor do CDM. O cliente nunca precisa copiar `client_secret`, callback, token técnico ou editar código.

## 1. Dados da empresa
1. Abra **Informações da Empresa**.
2. Digite o CNPJ e clique em **Buscar dados pelo CNPJ**.
3. Confira razão social, nome fantasia, endereço, CEP e contatos.
4. Confirme principalmente **Inscrição Estadual** e **Regime de Tributação**.
5. Salve.

> O preenchimento automático ajuda, mas dados tributários devem ser conferidos pela empresa/contador.

## 2. Nota fiscal
1. Abra **Notas Fiscais → NF-e**.
2. O painel “Configuração guiada” mostra 3 etapas.
3. Envie o certificado digital A1 no formato `.pfx` ou `.p12` e informe a senha.
4. Clique em **Testar conexão**.
5. Use **Homologação** para testes.
6. Quando a empresa estiver pronta, selecione **Produção**.

Depois disso o CDM envia a NF-e, acompanha o processamento da SEFAZ sozinho e libera XML/DANFE no histórico quando disponíveis. Também há cancelamento, importação de XML e inutilização de numeração.

## 3. Marketplaces
Abra **Integrações** e escolha o canal. Quando a integração do CDM estiver ativa, o cliente usa apenas **Conectar Mercado Livre**, **Conectar Shopee** ou **Conectar OLX**, entra na própria conta do canal e autoriza. A senha do marketplace não é armazenada pelo CDM.

### OLX
Após publicar, o CDM acompanha automaticamente o token de importação até o anúncio ficar publicado, recusado ou removido. Se houver recusa, a pendência aparece na Central de Anúncios.

## 4. Checklist inicial
O painel mostra a porcentagem da implantação e abre diretamente a tela que falta:
- dados da empresa;
- emissão fiscal;
- conexão de marketplace;
- primeira sucata;
- primeira peça;
- primeira venda.

## Configuração única do dono do CDM
No Render, o administrador da plataforma precisa cadastrar uma única vez as credenciais das aplicações dos marketplaces e o `FOCUS_NFE_MASTER_TOKEN`. Essas informações não são solicitadas aos clientes.
