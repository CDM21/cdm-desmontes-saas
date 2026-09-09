# Atualizar a versão online para V5

1. Faça backup da pasta atual do projeto.
2. Copie os arquivos desta V5 para a pasta do repositório `cdm-desmontes-saas`, substituindo os arquivos antigos.
3. No terminal, na raiz do repositório:

```powershell
git add .
git commit -m "CDM V5 cadastro automotivo marketplaces e assinatura"
git push
```

4. O Render deverá iniciar um novo deploy automaticamente.
5. Espere o serviço voltar para `Live`.
6. Abra o CDM e pressione `Ctrl + F5`.

## Depois do deploy

- Teste Cadastro de Sucatas: Toyota -> Corolla/RAV4/SW4.
- Teste Cadastro de Peças e selecione o veículo de origem.
- Em Integrações -> Mercado Livre, clique em `Verificar configuração`.
- Para cobrança, configure `MP_ACCESS_TOKEN` e `CDM_MONTHLY_PRICE=350` no Render.
