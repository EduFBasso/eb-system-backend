# Roteiro de teste integrado — Clinic e Bakery

Roteiro operacional para repetir durante refatoracoes de isolamento, estabilidade e fluxos de negocio. O roteiro deve ser executado em ambiente local, nunca primeiro no ambiente remoto.

## Regras de execucao

- Usar somente dados ficticios ou autorizados.
- Nao registrar senhas, tokens, links privados ou valores de `.env`.
- Manter cada tenant em uma aba/janela separada.
- Anotar tenant, rota, usuario sem senha, horario, resultado esperado e evidencia.
- Depois de qualquer alteracao de codigo: reproduzir, corrigir, executar teste automatizado, validar manualmente e repetir o caso.
- Ao encontrar vazamento entre tenants, interromper o cenario e corrigir antes de continuar.
- Nao apagar os registros criados sem registrar o que foi removido e por qual motivo.

## Preparacao comum

1. Confirmar branch de trabalho e registrar o commit inicial.
2. Confirmar banco local, migrations e `manage.py check`.
3. Executar a suite backend antes da rodada manual.
4. Executar testes e build do frontend correspondente.
5. Confirmar os quatro tenants:
   - Clinic Odontologia;
   - Clinic Podologia;
   - Bakery Boa Esperanca;
   - Bakery Central.
6. Abrir uma aba por tenant e conferir que a identidade visual e a especialidade/ecossistema estao corretos.
7. Preparar uma planilha ou registro com os identificadores dos dados criados, sem incluir credenciais.

## Evidencias obrigatorias

Para cada cenario, registrar uma das situacoes:

- `APROVADO`: resultado persistiu e a tela mostrou o estado esperado.
- `FALHOU`: comportamento divergente, com passos para reproduzir.
- `PENDENTE`: depende de uma decisao ou ambiente externo.
- `NAO APLICAVEL`: justificar.

Evidencias uteis:

- texto visivel da tela;
- screenshot sem credenciais;
- rota e tenant;
- resposta visual apos salvar;
- recarga da pagina confirmando persistencia;
- resultado de teste automatizado;
- consulta administrativa apenas quando necessaria para confirmar persistencia.

# Parte A — Bakery

## A1. Cliente, aprovacao e credito

1. Abrir o registro publico do tenant Bakery.
2. Cadastrar cliente ficticio com nome, telefone e endereco de teste.
3. Confirmar que o cliente aparece como pendente no admin do mesmo tenant.
4. Aprovar o cliente com senha do dono, sem registrar a senha.
5. Definir limite de credito e confirmar a mensagem de sucesso uma unica vez.
6. Confirmar que o cliente aprovado consegue autenticar.
7. Confirmar que outro tenant nao exibe esse cliente.

## A2. Catalogo e pedido

1. Criar um produto no tenant A.
2. Recarregar o catalogo e confirmar persistencia.
3. Abrir o tenant B e confirmar que o produto nao aparece.
4. No cliente aprovado do tenant A, adicionar o produto ao carrinho.
5. Criar pedido dentro do limite de credito.
6. Confirmar total, quantidade, saldo utilizado e saldo disponivel.
7. No admin, localizar o pedido pelo cliente e conferir itens e valor.
8. Marcar como pago com confirmacao do dono.
9. Filtrar pagamentos confirmados e conferir o estado final `PAGO`.
10. Reabrir o pedido e confirmar que os detalhes pertencem ao cliente e tenant corretos.

## A3. Estado executado em 2026-09-18

- Tenant: Bakery Boa Esperanca.
- Cliente: `fluxoteste`.
- Produto: `Cesta Fluxo Boa`.
- Pedido: `#1`, duas unidades, total de R$ 19,80.
- Limite: R$ 100,00; utilizado R$ 19,80; disponivel R$ 80,20.
- Resultado: aprovado, pedido criado e pagamento confirmado.
- Achado corrigido: feedback de aprovacao aparecia duas vezes porque pai e filho renderizavam a mesma mensagem.

# Parte B — Clinic: cadastro e catalogos

Executar nos tenants Odontologia e Podologia, adaptando os campos especificos da especialidade.

## B1. Cliente e isolamento

1. Cadastrar cliente ficticio no tenant A.
2. Buscar por nome, telefone e identificador; confirmar listagem e detalhe.
3. Editar dados basicos e recarregar a pagina.
4. Confirmar que o cliente e seus registros nao aparecem no tenant B.
5. Tentar acessar diretamente uma rota/identificador do tenant A estando no tenant B; esperar bloqueio, ausencia ou resposta de nao encontrado.
6. Repetir o cadastro no tenant B com outro cliente e confirmar separacao.

## B2. Catalogo de produtos

1. Criar produto no menu de catalogo do tenant A.
2. Recarregar a lista e confirmar nome, preco, status e persistencia.
3. Abrir a criacao de um plano de tratamento para o cliente de teste.
4. Adicionar ao plano um produto existente no catalogo.
5. Salvar o plano e reabrir; confirmar item, quantidade, preco e total.
6. Dentro do plano, adicionar um produto novo que ainda nao existe no catalogo geral.
7. Salvar e voltar ao catalogo.
8. Confirmar se o produto novo foi criado no catalogo geral conforme a regra atual.
9. Confirmar que os produtos dos dois tenants permanecem isolados.
10. Repetir com alteracao de preco/status e verificar se o plano preserva o valor historico esperado.

## B3. Catalogo de servicos e tratamentos

1. Criar um servico/tratamento no catalogo do tenant A.
2. Confirmar persistencia na listagem e no detalhe.
3. Criar ou abrir um plano de tratamento do cliente de teste.
4. Adicionar o servico existente pelo seletor do plano.
5. Adicionar um servico/tratamento novo diretamente pelo fluxo do plano.
6. Salvar, reabrir o plano e confirmar nome, escopo, valor e observacoes.
7. Voltar ao catalogo e verificar se o novo servico foi exibido conforme a regra do dominio.
8. Repetir o teste no tenant da outra especialidade e confirmar que tipos e campos indevidos nao vazam para a tela.

# Parte C — Clinic: plano de tratamento e impressao

## C1. Criacao e edicao

1. Criar um plano com queixa principal e objetivo do tratamento.
2. Adicionar pelo menos um produto e um servico.
3. Editar quantidade, valor, observacoes e ordem dos itens.
4. Salvar, fechar, recarregar e reabrir o plano.
5. Confirmar que os totais e itens persistem sem duplicacao.
6. Confirmar feedback de sucesso sem modal duplicado ou bloqueio indevido.

## C2. Impressao e bloqueio

1. Abrir a visualizacao de impressao do plano.
2. Conferir paciente, itens, quantidades, valores, totais e data.
3. Acionar `Imprimir`.
4. Confirmar o dialogo de bloqueio e escolher a acao de impressao.
5. Verificar que o plano fica identificado como impresso/travado.
6. Tentar editar data, itens, quantidade, valor e observacoes.
7. Esperar bloqueio de alteracoes conforme a regra do plano.
8. Reabrir e recarregar o plano para confirmar que o bloqueio persistiu.
9. Verificar se nova impressao e permitida ou explicitamente impedida pela regra atual.
10. Registrar qualquer divergencia entre bloqueio visual, bloqueio no frontend e bloqueio persistido no backend.

# Parte D — Clinic: agenda e compromissos

## D1. Criacao e persistencia

1. Criar um compromisso pelo ClientCard/fluxo rapido.
2. Confirmar data, horario, duracao, tipo de visita e observacoes.
3. Recarregar e confirmar persistencia no ClientCard.
4. Editar o compromisso e confirmar evento de atualizacao nas listas.
5. Criar um segundo compromisso com conflito de horario.
6. Confirmar alerta e fluxo de substituicao, sem criar duplicacao silenciosa.
7. Cancelar um compromisso e confirmar que ele permanece com estado correto.

## D2. Visoes diaria, semanal e mensal

1. Abrir a agenda diaria e localizar os compromissos por horario.
2. Abrir a visao semanal e confirmar o mesmo compromisso no dia correto.
3. Abrir a visao mensal e confirmar o indicador no dia correto.
4. Alternar entre as visoes e recarregar a pagina.
5. Confirmar que nenhum compromisso muda de data, horario, cliente ou estado.
6. Abrir o ClientCard e confirmar que os compromissos associados aparecem com status, horario e acoes corretos.
7. Abrir os detalhes do compromisso pelo ClientCard e pela agenda; comparar os dados.

## D3. Transicoes e encerramento

1. Testar compromisso `scheduled` em horario futuro.
2. Testar a entrada na janela operacional sem assumir que `ongoing` e um estado persistido.
3. Encerrar o atendimento e confirmar passagem para `pending` quando aplicavel.
4. Resolver `pending` como concluido e confirmar `done`.
5. Testar cancelamento e confirmar `canceled`.
6. Tentar editar data/hora de compromisso `pending`, `done` e `canceled`; esperar bloqueio conforme a regra.
7. Confirmar que compromissos de um tenant nao aparecem na agenda do outro.

# Parte E — Link de cadastro e WhatsApp

1. No ClientCard, acionar o envio do link de cadastro/anamnese.
2. Confirmar que a URL gerada pertence ao tenant e cliente corretos.
3. Em vez de enviar para um numero real, copiar/abrir o link em uma aba anonima ou segundo navegador local.
4. Preencher o formulario do cliente.
5. Confirmar que o profissional recebe os dados no cliente correto.
6. Recarregar o ClientCard e confirmar persistencia.
7. Testar o acionamento do WhatsApp apenas como abertura de URL local/de teste.
8. Registrar `PENDENTE` se a validacao depender de WhatsApp real, dispositivo externo ou permissao de popup.
9. Testar popup bloqueado e confirmar mensagem compreensivel sem perda do link.

# Parte F — Sessao, isolamento e regressao

## F1. Sessao

1. Abrir um fluxo Clinic e deixar a sessao expirar ou remover o token somente no ambiente local.
2. Confirmar modal unico de sessao expirada.
3. Confirmar que o modal bloqueia acoes ate novo login.
4. Confirmar que requisicoes concorrentes nao geram varias mensagens.
5. Reautenticar e confirmar retorno para a tela esperada.

## F2. Isolamento

1. Usar IDs de cliente, plano, produto, servico e compromisso de outro tenant em rotas diretas.
2. Esperar rejeicao, ausencia ou `404/403` conforme o contrato.
3. Confirmar que nenhuma resposta inclui nome, telefone, preco, plano ou compromisso do tenant indevido.
4. Repetir a verificacao pela UI, nao apenas pela API.

## F3. Fechamento automatizado

Executar ao final de cada rodada:

- `backend/.venv/bin/python manage.py check`;
- `backend/.venv/bin/python -m pytest -q`;
- no Clinic: `npm test -- --run`, `npm run typecheck`, `npm run build`;
- no Bakery: `npm test -- --run`, `npm run build`;
- `git diff --check`;
- registrar commits, pendencias e dados de teste mantidos.

## Registro de rodada

- Data:
- Branch/commit inicial:
- Banco/ambiente:
- Tenants executados:
- Resultado Bakery:
- Resultado Clinic Odontologia:
- Resultado Clinic Podologia:
- Resultado isolamento:
- Resultado sessao:
- Testes automatizados:
- Achados novos:
- Correcoes e commits:
- Pendencias autorizadas:

## Rodada executada — Clinic Odontologia — 2026-09-18

- Tenant: `consultorio-odontologia.clinic.eb.localhost`.
- Cliente criado: `Paciente Fluxo Odonto Teste Local`, codigo local `1`.
- Cadastro, anamnese odontologica basica, retorno a Home e persistencia: `APROVADO`.
- Produto criado no catalogo: `Produto Fluxo Odonto`, R$ 37,50: `APROVADO`.
- Produto existente selecionado pelo autocomplete no plano: `APROVADO`.
- Produto novo criado diretamente no plano com `Adicionar ao catalogo geral`: `APROVADO`; apareceu no catalogo como `Produto Direto do Plano`, R$ 12,00.
- Servico criado no catalogo: `Servico Fluxo Odonto`, tipo `Outros`, R$ 85,00: `APROVADO`.
- Servico existente selecionado no plano: `APROVADO`.
- Servico novo criado diretamente no plano com inclusao no catalogo geral: `APROVADO`; apareceu como `Servico Direto do Plano`, R$ 55,00.
- Plano reaberto com quatro itens e total persistido de R$ 189,50: `APROVADO`.
- Impressao exibiu paciente, profissional, itens, forma de pagamento e total: `APROVADO`.
- Apos confirmar `Imprimir e bloquear`, o plano passou a aparecer como `Impresso` e reabriu somente na visualizacao impressa: `APROVADO`.
- ClientCard exibiu o compromisso criado com cliente, tipo `Consulta`, horario e acao de edicao: `APROVADO`.
- Agenda diaria: na primeira abertura houve atraso de atualizacao e apareceu vazio; ao fechar e reabrir, exibiu o compromisso `09:59–10:59` como `Ativo`. Registrar como `APROVADO COM OBSERVACAO`, mantendo este caso para regressao de refresh.
- Agenda mensal e agenda desktop: exibiram o compromisso no dia 18 com cliente e horario corretos: `APROVADO`.
- Visao semanal: cobertura funcional parcial nesta sessao; em viewport desktop o componente semanal renderiza a grade mensal por regra responsiva. Repetir em viewport mobile real ou device emulado.
- WhatsApp: o ClientCard gerou o link para o telefone correto; envio real permanece `PENDENTE` por nao usar dispositivo externo.

## Rodada parcial — Clinic Podologia — 2026-09-18

- Tenant: `consultorio-podologia.clinic.eb.localhost`.
- Login com `Podologa Teste • Podologia`: `APROVADO`.
- Tela de cadastro exibiu a anamnese especifica de Podologia, incluindo calcados, meias, sensibilidade e alteracoes ungueais: `APROVADO`.
- Cliente criado: `Paciente Fluxo Podo Teste Local`, telefone final `7777`: `APROVADO`.
- ClientCard exibiu o atalho `Abrir plano de tratamento`, sem o atalho odontologico de prontuario: `APROVADO`.
- Plano criado: `Plano Fluxo Podo`; workspace exibiu `Mapa dos Membros (Maos e Pes)` e secao `Procedimentos`: `APROVADO`.
- Itens de catalogo/procedimentos, impressao/bloqueio, agenda diaria/semanal/mensal e isolamento cross-tenant: `PENDENTE` nesta rodada.
