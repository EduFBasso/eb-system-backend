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
- dados de panificadora ficam isolados do domínio clínico

## Módulo backend

Domínio no app:

- apps.bakery

Base compartilhada com o restante da plataforma:

- autenticação em apps.authentication
- infraestrutura em core

## Frontend correspondente

O frontend separado deste domínio fica em:

- ../frontend-bakery

Deploy recomendado:

- projeto dedicado na Vercel, separado do frontend-clinic
- variáveis de ambiente e domínio próprios por ambiente

## Validação local

```bash
./.venv/bin/python manage.py check
./.venv/bin/python -m pytest -q
```
