# Bakery System Backend

Este documento descreve regras e operação do domínio de panificadora.

## Escopo funcional

- cadastro de clientes
- cadastro de produtos
- criação e acompanhamento de pedidos
- registros financeiros/lançamentos relacionados ao ciclo de pedidos

Foco principal: controle de pedidos de produtos para panificadora.

## Regras de negócio principais

- pedido deve manter rastreabilidade por status ao longo do fluxo
- histórico de lançamentos deve preservar trilha de cobrança
- dados de panificadora ficam isolados do domínio clínico e do tenant Bakery
- clientes pendentes ou bloqueados não recebem sessão de cliente
- cliente autenticado acessa somente seus próprios pedidos, lançamentos e perfil
- owner/admin acessa os dados administrativos do tenant mediante autorização

## Contratos de autenticação

O login Bakery possui endpoints separados:

- `POST /api/v1/auth/bakery/login/admin/`: owner/admin;
- `POST /api/v1/auth/bakery/login/customer/`: cliente `member` aprovado.

Ambos recebem `login`, `password` e `tenant_slug`, e retornam o contexto do
tenant junto aos tokens JWT. O endpoint único legado `/api/v1/auth/bakery/login/`
não deve ser usado.

As APIs do domínio ficam sob `/api/v1/bakery/`. O cliente só pode consultar
recursos pertencentes ao próprio tenant e à própria identidade.

## Módulo backend

Domínio no app:

- apps.bakery

Base compartilhada com o restante da plataforma:

- autenticação em apps.authentication
- infraestrutura em core

## Frontend correspondente

O frontend separado deste domínio fica em:

- ../frontend-bakery

Em desenvolvimento local, use o hostname do tenant para manter o contexto,
por exemplo `http://admin-panificadora.localhost:5174`.

Deploy recomendado:

- projeto dedicado na Vercel, separado do frontend-clinic
- variáveis de ambiente e domínio próprios por ambiente

## Validação local

```bash
./.venv/bin/python manage.py check
./.venv/bin/python -m pytest -q

cd ../frontend-bakery
npm test -- --run
npm run build
```
