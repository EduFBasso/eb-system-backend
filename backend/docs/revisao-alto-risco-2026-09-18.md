# Revisao de Alto Risco — 2026-09-18

Guia operacional para a revisao final antes da proxima entrega do backend e, se necessario, dos frontends.

O historico executado permanece em `execution-revisao-backend-2026-09-16.md`. Este documento concentra somente o trabalho ainda a executar.

## Premissas confirmadas

- A branch de trabalho e isolada; a revisao nao sera executada na `main`.
- O banco do deploy sera recriado e populado com dados novos.
- O historico antigo de migrations nao e uma dependencia deste deploy: ele foi removido em ciclos destrutivos anteriores durante a passagem de mono-tenant para multi-tenant e a inclusao do ecossistema Bakery.
- Existe backup local dos dados da Podologia para contingencia.
- Antes de importar dados antigos, verificar se existe uma fonte online mais recente e autorizada.
- Nenhum segredo, senha ou token deve ser registrado neste guia.

## Objetivo

Confirmar que os fluxos humanos reais funcionam nos quatro contextos abaixo, com isolamento entre tenants e sem regressao de dados:

- Clinic Odontologia;
- Clinic Podologia;
- Bakery Panificadora Boa Esperanca;
- Bakery Panificadora Central.

A validacao sera feita no Chrome com os quatro contextos abertos simultaneamente, usando usuarios e dados ficticios ou autorizados.

## Ordem de execucao

1. Confirmar branch, commit inicial, banco alvo e backup/ponto de retorno.
2. Recriar o banco e aplicar somente a estrutura atual do projeto.
3. Criar ou confirmar os quatro tenants e os usuarios de teste.
4. Executar a baseline automatizada antes de qualquer alteracao.
5. Testar Clinic e Bakery manualmente em abas/janelas separadas.
6. Registrar cada falha com tenant, usuario, tela, rota, acao e resultado esperado.
7. Corrigir uma fatia por vez.
8. Para cada fatia: reproduzir, editar, commitar, testar automaticamente, validar manualmente, corrigir se necessario e testar novamente.
9. Executar a rodada consolidada e decidir se o backend e os frontends estao prontos para a entrega.

## Matriz Clinic

### Odontologia e Podologia

- login no tenant correto;
- capability e telas correspondentes a especialidade;
- cadastro, busca, listagem, detalhe e edicao de cliente;
- anamnese aplicavel a especialidade;
- agenda, filtros, cancelamento e conclusao;
- atendimento, registro clinico e historico;
- plano de tratamento, itens, valores e impressao;
- tentativa de acessar cliente ou registro do outro tenant;
- recarregar a pagina e confirmar persistencia;
- expirar sessao e observar o comportamento da mensagem.

## Matriz Bakery

### Panificadoras A e B

- login administrativo no tenant correto;
- identidade e perfil da panificadora;
- cadastro, aprovacao e bloqueio de cliente;
- produtos ativos e inativos;
- cadastro e consulta de pedidos;
- filtros por status, cliente, apelido, periodo e pedidos em aberto;
- limite de credito e historico de lancamentos;
- notificacoes quando aplicavel;
- tentativa de acessar produto, cliente ou pedido da outra panificadora;
- recarregar a pagina e confirmar persistencia;
- expirar sessao e observar o comportamento da mensagem.

## Sessao, modal e toast

- A mensagem de sessao expirada observada no Clinic e um modal bloqueante.
- Modal de sessao expirada e toast possuem funcoes diferentes e nao devem ser misturados.
- O modal deve aparecer uma unica vez por contexto de sessao, mesmo que varias requisicoes falhem simultaneamente.
- Toast fica reservado para sucesso, aviso e erro nao bloqueante.
- A padronizacao visual de toasts do Clinic sera tratada na revisao de frontend, depois que o comportamento funcional estiver confirmado.

## Criterios de seguranca

- Nao testar primeiro no ambiente produtivo.
- Nao importar backup sem confirmar a origem e a compatibilidade dos dados.
- Nao usar a `main` para experimentos.
- Nao remover migrations, aliases ou campos apenas durante um teste manual.
- Nao apagar dados de teste sem registrar o que foi criado e em qual tenant.
- Ao encontrar falha cross-tenant, interromper o fluxo daquele cenario e corrigir antes de prosseguir.

## Registro de cada achado

Para cada problema, registrar:

- identificador do achado;
- ecossistema e tenant;
- usuario de teste, sem senha;
- tela e rota;
- passos para reproduzir;
- resultado atual;
- resultado esperado;
- impacto humano e tecnico;
- commit da correcao;
- testes automatizados executados;
- resultado da repeticao manual.

## Encerramento

A revisao somente sera concluida quando:

- os quatro contextos forem testados;
- os fluxos principais persistirem corretamente;
- as tentativas de isolamento indevido forem rejeitadas;
- as falhas encontradas tiverem correcao e regressao;
- a sessao expirada estiver documentada e sem duplicacao incoerente;
- a suite automatizada e `manage.py check` passarem;
- o working tree estiver limpo;
- qualquer pendencia de frontend estiver separada da aprovacao do backend.
