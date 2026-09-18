# Execucao da Revisao do Backend — 2026-09-16

Diario operacional para executar, validar e decidir os pontos registrados em `revisao-backend-2026-09-16-pontos-pendentes.md`.

Este arquivo registra o que foi executado, o resultado observado, a decisao tomada e o proximo checkpoint. A revisao deve avancar uma etapa por vez, com validacao tecnica e, quando necessario, acompanhamento visual nos frontends.

## Regras de execucao

- Nao alterar comportamento enquanto a etapa nao tiver uma hipotese, um teste/check discriminante e uma decisao registrada.
- Antes de qualquer mudanca estrutural, preservar compatibilidade com migrations, `AUTH_USER_MODEL`, rotas e contratos consumidos pelos frontends.
- Nao remover codigo legado apenas por parecer antigo; confirmar uso em codigo, testes, scripts, deploy e documentacao.
- Separar achado tecnico de decisao de negocio. A escolha de tenant, escopo de Telegram, permissao e campos comerciais exige decisao explicita.
- Quando uma etapa afetar Clinic e Bakery de forma diferente, validar os dois ecossistemas separadamente.
- Quando a verificacao exigir navegador, iniciar o backend/frontend correspondente e registrar URL, tenant usado, usuario de teste e resultado visual sem registrar segredos.
- Cada etapa deve terminar em uma destas situacoes: concluida, bloqueada por decisao, ou devolvida para investigacao adicional.

## Estados usados

- `[ ]` nao iniciada
- `[>]` em execucao
- `[x]` concluida
- `[!]` bloqueada ou com decisao pendente
- `[-]` descartada com justificativa

## Ordem geral proposta

### Etapa 0 — Baseline e ambiente

Status: `[x]`

Objetivo: confirmar que o estado local usado na revisao e reproduzivel antes de editar codigo.

Checks:

- executar `./.venv/bin/python manage.py check`;
- executar a suite focada de autenticacao, sessoes e Bakery;
- registrar falhas separando regressao, expectativa de teste e problema de ambiente;
- confirmar que `backend/.env` nao sera exposto em registros ou commits.

Saida esperada: baseline tecnico registrado e lista de bloqueios conhecida.

Checkpoint humano: concluido. `nickname` e identificador de negocio por tenant, inclusive durante o status `pending`, e nao pode ser alterado depois da aprovacao.

Resultado atual: `manage.py check` passou. A falha do teste Bakery foi resolvida alinhando o teste a regra de negocio. O serializer retorna HTTP 400 com erro no campo `nickname`, e a constraint `uq_bakery_customer_tenant_nickname_ci` garante unicidade por tenant usando `Lower(Trim(nickname))`, inclusive para cadastros `pending`.

O frontend Bakery ja usa `nickname` para login, busca administrativa, filtros de pedidos e identificacao visual. Nao foi necessaria alteracao no frontend nesta etapa; a resposta de validacao por campo pode ser exibida pelo fluxo existente.

### Etapa 1 — Contrato de autenticacao e tenancy

Status: `[x]`

Objetivo: comparar o comportamento efetivo de Clinic e Bakery antes de modularizar `apps/authentication`.

Verificar:

- login Clinic com professional de Podologia e de Odontologia;
- login Bakery com administrador e, quando aplicavel, cliente aprovado;
- tenant, ecosystem, role e capabilities retornados;
- selecao de tenant quando houver mais de uma membership;
- DeviceSession nos dois fluxos;
- permissao por role e capability;
- rotas e payloads consumidos por `frontend-clinic` e `frontend-bakery`.

Saida esperada: matriz de contrato por ecossistema e lista de rotas que nao podem ser movidas/removidas ainda.

Checkpoint visual: usar um professional Clinic de cada especialidade e um administrador Bakery, com dados de teste autorizados pelo usuario.

Achado inicial: o Bakery resolve `tenant_slug` a partir do hostname/subdominio ou de `VITE_BAKERY_TENANT_SLUG` e envia esse valor no login. O Clinic nao envia slug no login; o backend escolhe a primeira membership Clinic ativa e retorna as capabilities usadas para compor telas e dados. Portanto, a padronizacao de slug nao deve ser tratada agora como simples renomeacao de campo: a selecao de tenant Clinic e uma decisao de produto para o caso de multiplas memberships.

Decisao de escopo: a diferenca nao bloqueou a Etapa 1. O login ambiguo foi definido como rejeitado; um seletor de tenant e uma evolucao futura, antes de habilitar uma experiencia de troca de tenant no Clinic.

Validacao automatizada de 2026-09-17:

- backend: `manage.py check` passou;
- backend: 45 testes passaram, cobrindo autenticacao, sessoes, identidade/login Bakery, isolamento Clinic, capabilities e anamneses por especialidade;
- `frontend-clinic`: 119 testes passaram e 4 foram ignorados;
- `frontend-bakery`: testes passaram; houve apenas aviso de ambiente de teste sobre `window.alert()` nao implementado.

Conclusao: os contratos codificados estao consistentes nos fluxos exercitados. As diretrizes de slug, hostname desconhecido, tenant por especialidade e rejeicao de login ambiguo foram decididas, implementadas e conferidas visualmente.

### Etapa 2 — Modulos de core/settings

Status: `[x]`

Objetivo: tornar o contrato de settings explicito sem alterar valores.

Verificar:

- nomes publicados por `core.settings`;
- duplicacoes entre `security.py` e `production.py`;
- variaveis documentadas mas nao carregadas, como `SLOW_REQUEST_THRESHOLD_MS`;
- inicializacao com `core.settings` e `core.settings.production`;
- legado de variaveis Render antes de qualquer limpeza.

Saida esperada: lista de settings publicos, duplicados, obrigatorios e candidatos a limpeza.

Achados iniciais: `core.settings.production` carrega com as variaveis obrigatorias ficticias e reforca `DEBUG=False`, HTTPS, HSTS, hosts, CSRF e CORS. `security.py` e `production.py` repetem os flags HTTPS; a sobreposicao foi mantida porque producao deve permanecer explicita e estrita. `SLOW_REQUEST_THRESHOLD_MS` era consumido pelo `QueryTimingMiddleware`, mas nao era publicado pelos settings e fazia o middleware cair silenciosamente no default de 500 ms.

Correcao aplicada: `SLOW_REQUEST_THRESHOLD_MS` foi adicionado a `core/settings/base.py`, com default atual de 500 ms e leitura por ambiente, sem alterar o comportamento padrao.

Validacao: `manage.py check` passou; `core.settings` carregou com threshold configuravel; `core.settings.production` carregou com variaveis ficticias sem conectar ao banco e confirmou `DEBUG=False`, `SECURE_SSL_REDIRECT=True`, HSTS de 31536000 segundos e `SLOW_REQUEST_THRESHOLD_MS=750` quando configurado. `git diff --check` passou.

Conclusao: a Etapa 2 foi concluida sem alterar valores de seguranca ou a ordem dos modulos. A duplicacao dos flags HTTPS entre `security.py` e `production.py` permanece como sobreposicao explicita de producao e nao sera limpa nesta revisao.

### Etapa 3 — Entrypoints, middleware e health checks

Status: `[x]`

Objetivo: validar o bootstrap do processo e os comportamentos transversais.

Verificar:

- ASGI e WSGI em local e no comando de producao;
- `X-App-Version`;
- medicao de requisicoes lentas;
- bloqueio de mutacoes em Clinic e Bakery;
- `/health`, `/health/` e `/health/full`;
- significado de HTTP 200 com `status=degraded`.

Saida esperada: comportamento documentado e decisoes sobre prefixos protegidos e readiness.

Validacao executada em 2026-09-17:

- `tests/test_health_endpoints.py` e `tests/test_version_header.py`: 7 testes passaram;
- `core.asgi` e `core.wsgi` importaram corretamente;
- `/health`, `/health/` e `/health/full` retornaram HTTP 200 com JSON valido e `X-App-Version`;
- `/health/full` retorna `status=degraded` e `database=error` quando `connection.ensure_connection()` falha, mantendo HTTP 200 por ser endpoint de readiness/diagnostico;
- Gunicorn confirmou a configuracao `core.wsgi:application` com `DJANGO_SETTINGS_MODULE=core.settings.production` e variaveis ficticias, sem conectar ao banco;
- `manage.py check` passou;
- `git diff --check` passou.

Correcao aplicada: `OnlineMutationLockMiddleware` agora protege tambem o prefixo `/api/v1/bakery/`. O login `/api/v1/auth/bakery/login/` permanece fora do lock, pois nao e uma mutacao de dados. O teste confirma os dois comportamentos.

Decisoes: manter `/health/full` com HTTP 200 em estado degradado para permitir que o monitoramento leia o diagnostico; o consumidor deve avaliar o campo `status`, nao somente o codigo HTTP. O processo de producao deve definir explicitamente `DJANGO_SETTINGS_MODULE=core.settings.production`; ASGI/WSGI mantem `core.settings` como fallback local.

### Etapa 4 — Modularizacao de authentication

Status: `[x]`

Objetivo: separar nucleo global, Clinic e Bakery com mudancas incrementais.

Ordem sugerida:

1. adicionar ou ajustar testes de contrato;
2. retirar rotas Clinic do agregador de authentication, preservando aliases durante a transicao;
3. separar serializers de login Clinic e Bakery;
4. mover comandos que manipulam dados Clinic para `apps/clinic`;
5. separar regras Bakery do admin global;
6. somente depois avaliar `ProfessionalSettings`, Telegram e dados comerciais por tenant.

Restricoes: nao alterar app labels, migrations ou `AUTH_USER_MODEL` sem plano de compatibilidade e validacao de dados.

Primeira fatia executada em 2026-09-17:

- criados os namespaces Python `apps/authentication/serializers/clinic/` e `apps/authentication/serializers/bakery/`;
- serializers de login Clinic e Bakery passaram a ter implementacao canonica nesses namespaces;
- `serializers_auth.py` e `bakery_auth.py` permanecem como wrappers de compatibilidade;
- os imports internos de `services/authentication.py` e `views/views_bakery_auth.py` usam os novos caminhos;
- nenhum model, app label, migration, rota publica ou contrato de payload foi alterado.

Validacao:

- 10 testes focados de authentication/tenant passaram;
- `manage.py check` passou;
- imports novos e legados resolveram as mesmas classes;
- `git diff --check` passou.

Decisao: manter os serializers legados durante a transicao. A proxima fatia deve separar views especificas somente depois de adicionar ou confirmar testes de contrato para as rotas publicas.

Segunda fatia executada em 2026-09-17:

- extraidas as acoes Clinic de settings e Telegram para `views/clinic_professional.py`;
- `ProfessionalViewSet` continua compartilhando CRUD, perfil `me` e listagem basica, herdando o mixin Clinic;
- helpers e a constante de token Telegram continuam reexportados por `professional_views.py` para compatibilidade;
- rotas publicas e registro do router permaneceram inalterados.

Validacao:

- 13 testes focados de authentication/tenant/version passaram;
- `manage.py check` passou;
- as quatro rotas Clinic (`settings`, `telegram/link-start`, `telegram/link-verify` e `telegram/test-send`) continuam registradas;
- `git diff --check` passou.

Decisao: manter `ProfessionalViewSet` como fachada durante a transicao. A proxima fatia pode separar comandos operacionais Clinic, que hoje sao o maior acoplamento restante dentro de `apps/authentication`.

Terceira fatia executada em 2026-09-17:

- implementacoes canonicas dos comandos `export_clients_csv`, `import_clients_csv`, `seed_local` e `seed_demo_professional` foram movidas para `apps/clinic/management/commands`;
- os mesmos modulos em `apps/authentication/management/commands` agora sao wrappers de compatibilidade;
- nomes, argumentos CLI e comportamento de isolamento por tenant foram preservados;
- comandos compartilhados de identidade e tenancy permaneceram em `apps/authentication`.

Validacao:

- `manage.py check` passou;
- os quatro comandos continuaram descobertos pelo Django;
- imports antigos e novos resolveram as mesmas classes;
- 15 testes de authentication, identidade Bakery e anamnese Clinic passaram;
- argumentos de `seed_local` e `import_clients_csv` foram conferidos;
- `git diff --check` passou.

Decisao: manter os wrappers antigos enquanto scripts e procedimentos operacionais puderem referenciar os caminhos históricos. A próxima fatia deve revisar a validação Bakery atualmente embutida no admin global.

Quarta fatia executada em 2026-09-17:

- a regra de nomes duplicados de owners Bakery foi centralizada em `apps/bakery/validators.py`;
- o admin global e o comando `create_tenant_admin` passaram a consumir o validador específico do Bakery;
- o helper histórico do comando foi preservado como adaptador de assinatura;
- nenhum model, migration, rota ou regra de identidade compartilhada foi alterado.

Validacao:

- 7 testes Bakery de validação e notificações passaram;
- `manage.py check` passou;
- imports do admin, comando e validador centralizado passaram;
- foram cobertos owner duplicado no Bakery e mesmo nome permitido em Clinic;
- `git diff --check` passou.

Decisao: manter a política de unicidade por nome para owners Bakery neste ponto; a regra agora tem uma única implementação e pode evoluir para uma política mais precisa sem duplicação.

Quinta fatia executada em 2026-09-17:

- `ProfessionalSettingsSerializer` foi movido para `apps/authentication/serializers/clinic/settings.py`;
- `serializers.py` continua como fachada para os serializers compartilhados e reexporta o serializer Clinic legado;
- `clinic_professional.py` passou a importar diretamente do namespace Clinic;
- `ProfessionalSettings` permaneceu no app `authentication`, sem alteração de model, migration ou `AUTH_USER_MODEL`;
- exports do pacote `serializers.clinic` foram ampliados para incluir autenticação e settings.

Validacao:

- 12 testes de settings Clinic e autenticação passaram;
- `manage.py check` passou;
- exports novos e legados resolveram as mesmas classes;
- regras de intervalo, término à meia-noite e slots inválidos foram cobertas;
- `git diff --check` passou.

Decisao: manter o model compartilhado até existir uma decisão explícita sobre settings por tenant. A organização de código não implica ainda uma separação de dados.

Sexta fatia executada em 2026-09-17:

- serviços de membership e capability foram confirmados como núcleo compartilhado entre Clinic e Bakery;
- `apps/authentication/services/__init__.py` passou a expor `get_active_tenant_membership`, `user_has_tenant_capability` e `HasTenantCapability`;
- adicionados testes diretos para filtro por ecossistema, membership inativa, capabilities do tenant e bypass de superusuário;
- nenhum serviço foi duplicado em `clinic/` ou `bakery/`, e nenhum model, migration ou contrato HTTP foi alterado.

Validacao:

- 11 testes de permissões e autenticação passaram;
- `manage.py check` passou;
- imports da API pública compartilhada passaram sem ciclo;
- `git diff --check` passou.

Decisao: manter permissões de tenancy, capability e autenticação de dispositivo no núcleo compartilhado. A separação por ecossistema deve ocorrer apenas em regras que realmente dependam de Clinic ou Bakery.

Resultado da etapa: a modularizacao planejada foi concluida em seis fatias pequenas, sem alterar models, migrations, `AUTH_USER_MODEL`, rotas publicas ou contratos de payload. Permanecem conscientemente adiados a remocao dos wrappers legados e qualquer separacao de dados compartilhados.

Commits da etapa:

- `c30de20` — `refactor: modularize authentication by ecosystem`;
- `2c521a6` — `refactor: move clinic management commands`;
- `889dc51` — `refactor: centralize bakery owner validation`;
- `fd996ac` — `refactor: isolate clinic professional settings serializer`;
- `7bbf5eb` — `refactor: expose shared tenant permission services`.

### Etapa 5 — Revisao dirigida de apps/clinic

Status: `[x]`

Objetivo: validar a variacao por especialidade e capability.

Verificar:

- tenants independentes de Podologia e Odontologia;
- capabilities e isolamento por `tenant_id`;
- campos e telas condicionais;
- `AnamneseBase` e extensoes `OneToOne` por especialidade;
- tratamento, agenda, clientes e permissao por tenant;
- comportamento visual em cada especialidade.

Primeira fatia executada em 2026-09-17:

- confirmado o contrato de capability Clinic no formato direto e no formato aninhado em `Tenant.capabilities.modules`;
- adicionado teste de regressao para gravacao de anamnese odontologica quando `modules.odonto` esta ativo;
- preservados o isolamento por `tenant_id`, a membership Clinic ativa e a rejeicao de cliente pertencente a outro tenant;
- nenhuma alteracao em model, migration, endpoint ou regra de producao foi necessaria.

Validacao:

- 24 testes Clinic de clientes, isolamento, anamnese, tokens e permissoes passaram;
- `manage.py check` passou;
- `git diff --check` passou.

Hipotese confirmada: o endpoint odontologico autoriza a gravacao somente para o tenant Clinic ativo com capability `odonto`, aceitando tanto a forma direta quanto a forma aninhada, sem permitir cliente de outro tenant.

Segunda fatia executada em 2026-09-17:

- adicionado teste inverso de especialidade no fluxo de clientes;
- tenant exclusivamente Odonto rejeita `anamnese_podologia` e nao cria cliente nem extensao de anamnese;
- a protecao cruzada agora esta coberta nos dois sentidos: Podologia rejeita Odonto e Odonto rejeita Podologia.

Validacao adicional: 5 testes do contrato de clientes Clinic passaram.

Proximo foco: revisar a simetria de `AnamneseBase` e extensoes Odontologia/Podologia, incluindo os testes de isolamento e capability da Podologia.

Terceira fatia executada em 2026-09-17:

- identificada uma assimetria real no fluxo nested de clientes: `anamnese_podologia` sem `anamnese_base` era aceito, mas descartado silenciosamente;
- `_save_nested_anamneses` passou a criar a `AnamneseBase` automaticamente antes de persistir a extensao de Podologia, seguindo o comportamento ja existente no fluxo Odonto;
- adicionado teste de regressao confirmando a criacao da base e da extensao com `tenant` e `professional` corretos;
- a correcao nao altera models, migrations ou endpoints, apenas evita perda silenciosa de dados enviados pelo cliente.

Validacao adicional: 25 testes Clinic de clientes, isolamento, anamnese, tokens e permissoes passaram; `manage.py check` e `git diff --check` passaram.

Nota arquitetural: a coexistencia de fluxos nested, endpoints dedicados e estruturas herdadas de iteracoes anteriores e tratada como compatibilidade a ser verificada por comportamento. Nesta fatia foi corrigida somente a perda de dados comprovada por teste.

Adendo estrutural registrado em 2026-09-17:

- o formulario de dados profissionais ainda permite salvar identidade comercial e endereco (`city`, `state`, `address`, `number`, `neighborhood`, `zip_code` e `cnpj`) diretamente em `Professional`;
- essa estrutura pertence ao desenho historico, centrado em um profissional atendendo muitos clientes, enquanto o desenho atual identifica a empresa pelo `Tenant`;
- o profissional continua usando esses dados para montar informacoes exibidas em planos/orcamentos, portanto nao e seguro simplesmente remover ou ignorar os campos atuais;
- a migracao para dados empresariais do tenant fica adiada para um plano de refino separado, antes do merge para `main/deploy`.

Plano minimo para essa revisao futura:

1. inventariar todos os consumidores backend, frontend, admin, serializers, comandos e relatorios;
2. definir a fonte oficial por tenant e o comportamento para profissionais vinculados a mais de um tenant;
3. preparar backfill e compatibilidade de leitura/escrita, sem apagar os campos antigos no primeiro passo;
4. criar testes reais de migracao, isolamento por tenant, planos/orcamentos e regressao de dados existentes;
5. executar validacao controlada antes de qualquer remocao de campos ou migration destrutiva.

Decisao: nao alterar essa estrutura durante a Etapa 5. A existencia de codigo historico misturado e reconhecida, mas somente inconsistencias comprovadas por comportamento serao corrigidas nesta etapa.

Revisao de alto risco — pos-revisao atual:

- esta revisao somente sera iniciada depois da conclusao das etapas correntes e de seus commits;
- o escopo devera incluir backend e frontend, acompanhando o fluxo completo desde a tela ate a persistencia;
- a auditoria devera separar codigo efetivamente usado pelo usuario de funcoes teoricamente disponiveis, legadas ou nunca exercitadas;
- cada candidato a remocao devera ter consumidores, testes, dados existentes, impacto de usabilidade e plano de rollback avaliados;
- a revisao devera priorizar o fluxo humano real, reduzindo operacoes, telas e estados que aumentem complexidade sem beneficio comprovado;
- nenhuma funcao sera removida apenas por parecer poluicao: sera necessario confirmar que nao e usada, que nao sustenta compatibilidade e que sua retirada melhora ou preserva a experiencia.
- ao final da revisao de alto risco, sera viavel executar manualmente o fluxo completo do Clinic, cobrindo cadastro, clientes, agenda, filtros, anamneses, tratamento e demais operacoes usadas no atendimento;
- no mesmo momento final, sera executado o fluxo manual completo do Bakery, cobrindo cadastro de clientes, produtos, servicos, pedidos, agenda, filtros e demais operacoes efetivamente disponiveis;
- essas validacoes manuais ficarao para o fim porque dependem da auditoria tecnica e devem confirmar o comportamento real integrado, sem antecipar conclusoes enquanto ainda houver alteracoes estruturais em andamento.

Contexto da decisao: a evolucao do sistema gerou conhecimento pratico sobre como identificar e limpar codigo em etapas com apoio de IA. Esse aprendizado deve ser usado como criterio de produto e usabilidade, nao apenas como criterio de completude tecnica. Sistemas grandes tambem podem acumular funcoes que parecem completas no desenho, mas nao fazem parte do trabalho cotidiano do usuario; a revisao futura deve tornar essa diferenca explicita.

Quarta fatia executada em 2026-09-17:

- identificada uma falha de isolamento no `POST /clinic/treatment/plans/`: o tenant do plano era definido pelo profissional, mas o cliente podia pertencer a outro tenant;
- a criacao agora rejeita o plano antes do `save` quando `client.tenant_id` nao corresponde ao tenant Clinic ativo;
- adicionado teste de regressao garantindo resposta `400` e ausencia de plano cruzado;
- nenhum model, migration ou contrato de leitura foi alterado.

Validacao: 18 testes de rotas de especialidade, acesso a planos, preferencia de impressao e contexto de Podologia passaram; `manage.py check` e `git diff --check` passaram.

Proximo foco: revisar os fluxos de agenda e clientes que ainda nao foram cobertos pela matriz de isolamento da Etapa 5.

Quinta fatia executada em 2026-09-17:

- identificada uma lacuna nos serializers de `Encounter` e `ClinicalRecord`: o queryset protegia leituras por tenant, mas a criacao aceitava cliente de outro tenant quando nao havia `appointment` ou `encounter` cruzado para acionar a validacao do model;
- criada validacao compartilhada para confirmar que o cliente pertence ao tenant ativo do profissional antes de persistir atendimento ou registro clinico;
- adicionados testes de regressao para rejeitar criacao cross-tenant em `/agenda/encounters/` e `/agenda/clinical-records/`;
- a agenda de `Appointment` continua coberta pela validacao existente e nao teve mudanca de contrato;
- `Charge` permanece legado e fora da ampliacao funcional desta etapa: nao sera tratado como fluxo financeiro digital sem evidencia de uso real e decisao especifica na revisao futura.

Validacao adicional: 34 testes de agenda, incluindo isolamento, regras de appointment, encontros e registros clinicos, passaram; os arquivos alterados nao apresentaram erros de diagnostico.

Proximo foco: revisar as regras comportamentais de `Encounter` e `ClinicalRecord` e confirmar se a matriz de isolamento da agenda esta completa, sem ampliar o escopo financeiro legado.

Sexta fatia executada em 2026-09-17:

- revisadas as regras comportamentais de `Encounter`: criacao independente, apenas uma sessao aberta por cliente/profissional, encerramento, cancelamento e bloqueio de exclusao;
- revisado o fluxo de `ClinicalRecord`: exigencia de vinculo coerente com o atendimento, preservacao do historico e remocao em cascata quando o cliente e excluido pelo fluxo permitido;
- nenhuma inconsistência adicional foi comprovada nessa fatia, portanto nao houve alteracao de regra de producao;
- a protecao de tenant permanece aplicada tanto no queryset dos viewsets quanto na validacao de criacao registrada na fatia anterior.

Validacao adicional: 15 testes comportamentais de agenda e exclusao relacionada passaram.

Proximo foco: fechar a matriz de isolamento da agenda com cenarios de leitura e mutacao cross-tenant e, depois, avaliar a conclusao da Etapa 5.

Setima fatia executada em 2026-09-17:

- adicionados cenarios de API para confirmar que `Encounter` e `ClinicalRecord` de outro tenant nao aparecem em listagens;
- leitura por detalhe e mutacao cross-tenant retornam `404`, preservando o comportamento de queryset restrito e evitando revelar a existencia dos registros;
- a matriz de isolamento da agenda e do prontuario fica coberta para criacao, listagem, leitura e atualizacao;
- nenhuma alteracao adicional de producao foi necessaria.

Validacao adicional: 3 testes de isolamento clinico passaram, totalizando 37 testes na rodada consolidada de agenda.

Proximo foco: executar a validacao consolidada da Etapa 5 e revisar o diario antes de marcar a etapa como concluida.

Conclusao da Etapa 5 em 2026-09-17:

- a variacao por especialidade e capability, o isolamento por tenant, os fluxos de clientes, anamneses, tratamento, agenda, encontros e registros clinicos foram revisados por comportamento e testes;
- a matriz de isolamento foi coberta para criacao, listagem, leitura e atualizacao nos recursos clinicos relevantes;
- a validacao consolidada da suite `apps/clinic/tests` e do teste de exclusao relacionada passou com 89 testes, sem falhas ou erros;
- `manage.py check` e `git diff --check` passaram, e o working tree ficou limpo apos os commits da etapa;
- permanecem adiados, sem bloquear esta conclusao, a migracao de dados comerciais de `Professional` para `Tenant`, a decisao sobre `DeviceSession` no Bakery, a definicao de escopo tenant-specific de settings/Telegram, o fluxo financeiro legado `Charge` e a revisao manual full-stack de alto risco;
- nenhuma migration destrutiva, remocao de wrapper legado ou alteracao de `AUTH_USER_MODEL` foi introduzida.

Resultado: Etapa 5 concluida. Proximo passo: iniciar a etapa seguinte conforme o diario, preservando os itens de alto risco para a revisao especifica ja registrada.

### Etapa 6 — Revisao dirigida de apps/bakery

Status: `[ ]`

Objetivo: validar o fluxo uniforme entre administradores e tenants Bakery.

Verificar:

- cadastro e login do administrador;
- cliente pendente, aprovado e bloqueado;
- catalogo, pedido, credito e notificacoes;
- isolamento entre unidades Bakery;
- campos governados pelo administrador versus campos editaveis pelo cliente;
- comportamento visual do mesmo fluxo para administradores diferentes.

### Etapa 7 — Decisoes de migracao e limpeza

Status: `[ ]`

Objetivo: executar somente limpezas justificadas por evidencias.

Candidatos ja registrados:

- `services/backfill.py` e `backfill_tenants.py`;
- `services/signals.py` vazio;
- aliases de rotas e imports historicos;
- campos comerciais de `Professional` apos migracao para `Tenant`;
- variaveis legadas da Render.

Nenhum candidato deve ser removido antes de confirmar consumidores, deploy, dados existentes e rollback.

## Registro de etapas

### Etapa 0

Data: 2026-09-17

- `./.venv/bin/python manage.py check`
- `./.venv/bin/python -m pytest -q apps/authentication/tests/test_password_auth.py tests/test_sessions.py tests/test_bakery_lookup_cep.py tests/test_bakery_order_lifecycle.py`

Resultado: check passou; a suite inicial tinha 27 testes aprovados e 1 falha. Apos o alinhamento, os testes de identidade e ciclo Bakery passaram: 11 testes aprovados e 0 falhas.

Decisao: `nickname` e identificador case-insensitive, com espacos externos normalizados, unico por tenant e imutavel apos aprovacao. HTTP 400 foi mantido, pois o corpo identifica o campo invalido; nao e necessario criar um novo status HTTP.

Proximo passo: iniciar a Etapa 1, mapeando o contrato de autenticacao e tenancy com os dois frontends.

### Etapa 2

Data: 2026-09-17

Resultado: settings base, producao e threshold de requisicoes lentas validados. Foi corrigida a ausencia de `SLOW_REQUEST_THRESHOLD_MS` em `core/settings/base.py`.

Decisao: manter a sobreposicao explicita dos flags HTTPS em `production.py`; nao fazer limpeza estrutural de settings nesta etapa.

Proximo passo: iniciar a Etapa 3, validando ASGI/WSGI, middleware, health checks, cabecalho de versao e bloqueio de mutacoes.

### Etapa 3

Data: 2026-09-17

Resultado: entrypoints, middleware, health checks, cabecalho de versao e lock online validados. O lock Bakery foi corrigido e coberto por teste.

Decisao: readiness degradado continua respondendo HTTP 200 com `status=degraded`; o deploy deve configurar explicitamente o modulo de settings de producao.

Proximo passo: iniciar a Etapa 4, modularizacao incremental de `apps.authentication`, preservando rotas e contratos publicos.

### Etapa 4 — Primeira fatia

Data: 2026-09-17

Resultado: serializers de autenticacao foram organizados nos namespaces Python de Clinic e Bakery. Os modulos antigos continuam reexportando as classes, preservando imports existentes; os modelos compartilhados, migrations e rotas nao foram movidos.

Validacao: 10 testes focados passaram; `manage.py check`, compatibilidade de imports e `git diff --check` passaram.

Proximo passo: mapear e separar as views especificas de cada ecossistema, mantendo wrappers de compatibilidade e os contratos atuais.

### Etapa 4 — Segunda fatia

Data: 2026-09-17

Resultado: settings de profissional e integracao Telegram foram movidos para `apps/authentication/views/clinic_professional.py` como mixin. A view compartilhada preserva o mesmo router e continua exportando os helpers legados.

Validacao: 13 testes focados passaram; `manage.py check`, verificacao do router e `git diff --check` passaram.

Proximo passo: separar os comandos de gerenciamento que importam diretamente modelos Clinic, sem alterar nomes de comandos durante a transicao.

### Etapa 4 — Terceira fatia

Data: 2026-09-17

Resultado: os comandos Clinic `export_clients_csv`, `import_clients_csv`, `seed_local` e `seed_demo_professional` passaram a ter implementacoes canonicas em `apps/clinic`, mantendo wrappers nos caminhos antigos.

Validacao: `manage.py check`, descoberta dos quatro comandos, compatibilidade de imports, argumentos CLI e 15 testes focados passaram.

Proximo passo: centralizar a validacao especifica de owners Bakery.

### Etapa 4 — Quarta fatia

Data: 2026-09-17

Resultado: a validacao de nomes duplicados de owners Bakery foi centralizada em `apps/bakery/validators.py`; admin e comando de criacao passaram a consumir a mesma regra.

Validacao: 7 testes Bakery, `manage.py check`, imports e `git diff --check` passaram.

Proximo passo: isolar o serializer de settings especifico do Clinic.

### Etapa 4 — Quinta fatia

Data: 2026-09-17

Resultado: `ProfessionalSettingsSerializer` passou para `apps/authentication/serializers/clinic/settings.py`; o model, migrations e `AUTH_USER_MODEL` permaneceram compartilhados.

Validacao: 12 testes de settings Clinic e autenticacao, `manage.py check`, exports novos/legados e `git diff --check` passaram.

Proximo passo: confirmar a API publica dos servicos compartilhados de tenancy.

### Etapa 4 — Sexta fatia

Data: 2026-09-17

Resultado: os servicos compartilhados de membership e capability foram exportados por `apps/authentication/services/__init__.py`, com testes diretos para ecossistema, membership inativa, capability e superusuario.

Validacao: 11 testes de permissoes e autenticacao, `manage.py check`, import sem ciclo e `git diff --check` passaram.

Decisao: manter esses servicos no nucleo compartilhado; nao duplicar permissoes em namespaces Clinic ou Bakery.

### Etapa 1 — Atualizacao apos implementacao

Data: 2026-09-17

Checks executados:

- `./.venv/bin/python manage.py check`
- suite backend focada de authentication, Bakery, Clinic, capabilities e anamnese;
- `npm test -- --run` em `frontend-clinic`;
- `npm test -- --run` em `frontend-bakery`.

Resultado: checks automatizados aprovados e checkpoint visual concluido em 2026-09-17.

Decisao atual: manter a selecao Bakery por `tenant_slug` derivado do dominio/configuracao e rejeitar login Clinic ambiguo quando houver multiplas memberships. O backend nao deve escolher silenciosamente a primeira membership nesse caso.

Decisoes confirmadas para a arquitetura Clinic online:

- um unico projeto Vercel pode atender varios subdominios e dominios customizados;
- `frontend-clinic` continua compartilhado entre Odontologia e Podologia;
- o slug identifica o tenant/empresa, nao a especialidade;
- `Tenant.capabilities` identifica a especialidade e habilita telas, dados e regras;
- rotas e componentes condicionais permanecem no frontend compartilhado;
- nao criar `frontend-odonto` e `frontend-podology` nesta fase, evitando duplicacao de autenticacao, componentes, testes e deploys.
- o Navbar temporario deve listar somente profissionais com membership ativa no tenant indicado pelo slug; `ecosystem=clinic` sozinho nao e isolamento suficiente.

Diretrizes ja decididas e implementadas:

- hostname/subdominio e a fonte principal do slug Clinic; `VITE_CLINIC_TENANT_SLUG` fica restrito a localhost/preview controlado;
- o frontend envia `tenant_slug` ao `/token/` e o backend valida tenant ativo e membership;
- login ambiguo e rejeitado; seletor de tenant fica para uma etapa posterior;
- hostname desconhecido e bloqueado, sem fallback para tenant de producao;
- cada tenant Clinic possui uma unica especialidade; capabilities conflitantes sao rejeitadas;
- `tenant_id`, slug, ecosystem, role e capabilities formam o contexto da sessao atual.

Pendencias remanescentes da Fase 1:

1. **Sessao de dispositivo:** decidir se Bakery deve adotar a mesma criacao/limite de `DeviceSession` do Clinic ou se a diferenca e intencional e documentada.
2. **Configuracoes por tenant:** decidir se agenda, `ProfessionalSettings` e Telegram sao globais por profissional ou especificos por tenant antes de permitir o mesmo profissional em duas clinicas.

Itens que podem ficar para a fase seguinte, sem bloquear a arquitetura online: mover pacotes de autenticacao, migrar campos comerciais de `Professional` para `Tenant`, remover aliases de rotas e limpar comandos legados.

Proximo passo: iniciar a Etapa 5, com revisao dirigida de `apps/clinic`.

Evidencia visual registrada pelo usuario:

- `frontend-clinic` exibiu simultaneamente uma dentista no tenant de Odontologia e uma podologa no tenant de Podologia, com profissionais e dados distintos;
- `frontend-bakery` exibiu dois tenants independentes, com slugs distintos, titulos `Panificadora Boa Esperanca` e `Panificadora Central` e dados de clientes correspondentes a cada contexto;
- a evidencia confirma que o frontend compartilhado preserva o contexto do tenant e que o Bakery nao apresenta apenas uma identidade visual fixa entre unidades.

Conclusao da Etapa 1: checkpoint visual aprovado; nenhuma falha visual foi identificada. Permanecem apenas as decisoes futuras sobre `DeviceSession` no Bakery e escopo tenant-specific de `ProfessionalSettings`/Telegram.

Implementacao inicial do contrato Clinic:

- `/token/` aceita `tenant_slug`, valida o tenant Clinic ativo e retorna `tenant_slug` no contexto da sessao;
- sem slug, o login legado continua permitido somente para uma membership Clinic ativa; com mais de uma, retorna erro de ambiguidade;
- tenants com capabilities simultaneamente `odonto` e `podologia` sao rejeitados;
- `professionals-basic` aceita `tenant_slug` e filtra profissionais por memberships ativas daquele tenant;
- o Navbar resolve o slug pelo hostname (`<slug>.clinic.eb.com` ou `<slug>.clinic.eb.localhost`) e bloqueia dominio desconhecido;
- em `localhost`, o teste/desenvolvimento precisa declarar `VITE_CLINIC_TENANT_SLUG`; nao existe fallback de producao.

Nota de modelo: `TenantMembership` atualmente nao possui um campo de especialidade. A especialidade do contexto e definida por `Tenant.capabilities`; `Professional.specialty` permanece um dado legado/descritivo e nao deve substituir o filtro por tenant.

Validacao apos a implementacao:

- 7 testes de autenticacao e tenancy Clinic passaram;
- o teste de login do Navbar passou;
- o typecheck do `frontend-clinic` passou;
- o Navbar agora consulta `professionals-basic` com `tenant_slug`, portanto profissionais de outros tenants nao aparecem na selecao;
- chamadas Clinic legadas a `professionals-basic` sem slug retornam lista vazia, evitando listar profissionais de todos os tenants;
- para o deploy Vercel, cada dominio Clinic deve seguir `<slug>.clinic.eb.com` e apontar para o mesmo projeto; `VITE_CLINIC_TENANT_SLUG` deve ser usado somente em localhost/preview controlado;
- antes do deploy, validar visualmente um subdominio de Podologia e um de Odontologia, confirmando que a lista, o login e as capabilities pertencem ao mesmo tenant.
- o superusuario pode definir senhas temporarias para profissionais de teste, permitindo validar o fluxo completo sem compartilhar credenciais reais;
- o checkpoint visual deve incluir pelo menos um profissional de cada especialidade, a navegacao pelas paginas de clientes e um cliente de teste criado no tenant correto;
- contas e clientes usados somente para validacao devem ser identificados como temporarios, ter dados ficticios e ser removidos ao final, incluindo sessoes e tokens ativos quando aplicavel.

## Decisoes humanas pendentes

- [x] Definir que cliente Bakery aprovado nao pode alterar `nickname`; o teste foi alinhado a regra atual.
- [x] Definir como o login Clinic seleciona tenant com multiplas memberships: login ambiguo e rejeitado; seletor fica para etapa posterior.
- [ ] Definir se `ProfessionalSettings` e Telegram sao globais ou tenant-specific.
- [ ] Definir migracao dos dados comerciais/endereco de `Professional` para identidade empresarial do `Tenant`.
- [ ] Planejar revisao de alto risco full-stack apos esta revisao, incluindo rastreamento de uso real, limpeza de codigo legado e validacao de usabilidade.
- [ ] Definir se Bakery tambem deve criar e limitar `DeviceSession` como Clinic.
- [ ] Aprovar eventual correcao dos dois textos inconsistentes em `docs/reset_database_loc.md`.

## Estado atual

Etapas 0, 1, 2, 3, 4 e 5 concluidas. A Etapa 5 foi encerrada com sete fatias funcionais executadas e validadas. A modularizacao foi encerrada nesta fase sem alterar contratos publicos, models, migrations ou `AUTH_USER_MODEL`. As etapas de Bakery e limpeza continuam conscientemente adiadas.

## Procedimento de checkpoint visual antes do deploy

1. O superusuario cria ou seleciona um tenant Clinic de Podologia e um tenant Clinic de Odontologia, cada um com uma unica capability de especialidade.
2. Para cada tenant, cria ou seleciona um profissional de teste com membership ativa e define uma senha temporaria.
3. Acessa o subdominio correspondente e confirma: listagem do profissional correto no Navbar, login, `tenant_slug`, role, capability e rotas/telas condicionais.
4. Cria um cliente ficticio no tenant testado e percorre as paginas de clientes, formulario, visualizacao, edicao, agenda e anamnese aplicavel a especialidade.
5. Repete o fluxo no segundo tenant e confirma que nenhum profissional, cliente ou dado do primeiro tenant aparece no segundo.
6. Revoga sessoes, remove clientes temporarios e, quando nao forem contas reais, desativa ou remove os profissionais de teste depois da validacao.

Nao registrar senhas, tokens, dados pessoais reais ou payloads sensiveis no diario. O teste deve usar somente dados ficticios ou contas autorizadas explicitamente.


----

# Decisões User:


## Fase 1: Objetivo
Documentar e implementar diretrizes de login multi-tenant para os ecosystems Clinic e Bakery, seguindo tabela de cenários definida.

## Diretrizes principais
1. Slug Clinic: hostname/subdomínio será a fonte principal.
2. Login: frontend deve enviar `tenant_slug` ao endpoint `/token/`.
3. Múltiplas memberships: rejeitar login ambíguo; seletor será criado depois, mas backend já deve retornar erro.
4. Hostname desconhecido: bloquear acesso sem fallback.
5. Tenant com duas especialidades: não permitido; cada especialidade é um tenant distinto.
6. Domínio oficial: raiz `clinic.eb.com`, subdomínios baseados no slug; ambiente local usa `.localhost`.

## Tabela de cenários
| Cenário | URL de login | Slug enviado | Comportamento esperado | Resultado |
|---------|--------------|--------------|------------------------|-----------|
| 1. Login válido – Podologia | https://consultorio-podologia.clinic.eb.com/token/ | consultorio-podologia | Backend valida membership ativa | ✅ Autorizado |
| 2. Login válido – Odontologia | https://consultorio-odontologia.clinic.eb.com/token/ | consultorio-odontologia | Backend valida membership ativa | ✅ Autorizado |
| 3. Login ambíguo | https://clinic.eb.com/token/ | (não enviado) | Backend detecta múltiplas memberships | ❌ Rejeitado |
| 4. Hostname desconhecido | https://clinica-x.clinic.eb.com/token/ | clinica-x | Slug não corresponde a tenant ativo | ❌ Bloqueado |
| 5. Tenant inválido (duas especialidades) | https://consultorio-misto.clinic.eb.com/token/ | consultorio-misto | Capabilities conflitantes | ❌ Rejeitado |
| 6. Ambiente local | https://consultorio-podologia.clinic.eb.localhost/token/ | consultorio-podologia | Usado para desenvolvimento isolado | ✅ Autorizado |

## Resumo de tarefas: 
- Gerar comentários explicativos para cada diretriz (por que foi escolhida).
- Escrever exemplos de código Django/DRF para validação de `tenant_slug` no endpoint `/token/`.
- Incluir tratamento de erro para login ambíguo e hostname desconhecido.
- Documentar no código (docstrings) que cada especialidade deve ser um tenant separado.
