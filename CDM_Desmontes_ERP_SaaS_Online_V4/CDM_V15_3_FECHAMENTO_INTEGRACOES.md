# CDM Desmontes V15.3

Fechamento de codigo para NF-e, OLX e recuperacao de senha.

## NF-e
- aceita FOCUS_NFE_MASTER_TOKEN e FOCUS_MASTER_TOKEN;
- elimina divergencia entre documentacao/Render e backend;
- mantem homologacao e producao separadas;
- continua exigindo credencial Focus e configuracao fiscal real antes de emitir.

## OLX
- fluxo OAuth + AutoUpload preservado;
- diagnostico informa credenciais ausentes e callback;
- valida que o OAuth realmente retornou access_token;
- credenciais e homologacao continuam sendo dependencias da OLX.

## E-mail
- diagnostico SMTP sem mostrar segredos;
- SMTP_USER pode ser usado como remetente quando SMTP_FROM nao estiver definido;
- recuperacao de senha deixa de registrar falso sucesso quando o SMTP nao esta disponivel.

## Portal do Dono
- V15.3;
- remove texto antigo de OTX;
- diferencia codigo pronto de dependencia externa.
