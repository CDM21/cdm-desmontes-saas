# CDM Desmontes SaaS Online V4

Novidades desta versão:

- frontend deixa de depender de URL fixa `localhost`;
- backend aceita CORS por variável de ambiente;
- suporte a PostgreSQL em produção;
- Dockerfile para servir backend + frontend no mesmo domínio;
- Render Blueprint (`render.yaml`) para subir app + banco;
- callbacks OAuth calculados automaticamente pela URL HTTPS pública do Render;
- mantém execução local com os arquivos BAT existentes.

Para produção, leia `COLOCAR_ONLINE_RENDER.md`.
