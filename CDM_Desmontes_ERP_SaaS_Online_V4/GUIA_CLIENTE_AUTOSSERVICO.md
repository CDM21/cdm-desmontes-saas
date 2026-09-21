# Comece sozinho no CDM Desmontes

O CDM foi preparado para você configurar a própria empresa sem depender de suporte técnico.

## Dados da empresa

Abra **Empresa**. Digite seu CNPJ e clique em **Buscar dados pelo CNPJ**. O CDM tenta preencher automaticamente razão social, nome fantasia, endereço e contato público. Confira os dados, informe Inscrição Estadual/regime quando necessário e salve.

## Nota fiscal

Abra **Fiscal > Configuração Tributária** e informe os padrões tributários recomendados pelo seu contador. Depois abra **Fiscal > Emitir NF-e**.

O assistente mostra quatro etapas: dados da empresa, tributação, certificado digital A1 e teste final. Envie seu certificado `.pfx` ou `.p12`, informe a senha e valide. Comece em **Homologação**, que serve para testes e não gera documento com valor fiscal. Quando estiver tudo conferido, altere para **Produção**.

## Mercado Livre, Shopee e OLX

Abra **Integrações** e escolha o canal. Clique em **Conectar**. Você será levado para a página oficial do marketplace, entra na sua própria conta e autoriza o CDM. Sua senha do marketplace não é entregue ao CDM.

Se um canal aparecer como **Disponível em breve**, significa que a integração global daquele canal ainda aguarda liberação da própria plataforma; não há chave técnica para você preencher.

## Depois de conectar

Cadastre suas peças normalmente e escolha em quais canais cada peça será publicada. O CDM acompanha o processamento dos anúncios. Na OLX, por exemplo, o sistema consulta automaticamente a importação até saber se o anúncio foi aceito ou recusado.

## NF-e emitida

Em **Fiscal > Notas emitidas e rascunhos**, você pode consultar a situação, abrir XML/DANFE quando disponíveis e solicitar cancelamento de uma NF-e autorizada dentro das regras fiscais aplicáveis.
