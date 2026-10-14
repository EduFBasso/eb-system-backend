# Validação da branch `normatize_auth_history` na Render

Roteiro para executar depois que a branch for revisada, aprovada, publicada e
o novo deploy estiver ativo na Render.

Este roteiro não substitui os testes locais. A suíte completa deve ser
executada localmente ou em CI/staging. No ambiente online, execute apenas
verificações operacionais, o `dry-run` e o backfill aprovado.

## 1. Pré-condições

Antes de abrir o Shell da Render:

- confirmar que o deploy foi concluído com sucesso;
- confirmar que o commit publicado pertence à branch
  `normatize_auth_history`;
- confirmar que o backup do banco foi realizado;
- confirmar que existe uma janela para validação;
- não executar comandos de teste que criem ou alterem dados reais;
- manter este relatório aberto para registrar as saídas.

O backup deve ser confirmado pelo mecanismo de backup configurado para o banco
da Render. Não armazenar senhas, tokens ou dados pessoais no relatório.

## 2. Confirmar o diretório e o código em execução

No Shell da Render, confirmar a localização do projeto:

```bash
pwd
ls
```

Se `manage.py` não estiver no diretório atual, localizar o backend:

```bash
find . -maxdepth 3 -name manage.py -print
```

Entrar no diretório que contém `manage.py`, por exemplo:

```bash
cd backend
```

Confirmar que o arquivo de gerenciamento está disponível:

```bash
test -f manage.py && echo "manage.py encontrado"
```

## 3. Confirmar versão publicada

Executar:

```bash
git rev-parse --short HEAD
git status --short
```

Comparar o commit exibido com o commit aprovado para o deploy.

Se o commit não for o esperado, interromper o procedimento e não executar o
backfill.

## 4. Verificações do Django

Executar:

```bash
python manage.py check
```

Resultado esperado:

```text
System check identified no issues
```

Confirmar o estado das migrations:

```bash
python manage.py showmigrations
```

Verificar que não existem migrations pendentes:

```bash
python manage.py migrate --plan
```

Se o comando listar migrations para aplicar, interromper o procedimento,
avaliar as migrations e aplicar somente após aprovação explícita.

## 5. Executar o backfill em modo seguro

Primeiro executar obrigatoriamente o `dry-run`:

```bash
python manage.py backfill_existing_tenants --dry-run
```

O comando não deve alterar dados. Ele deve apresentar um resumo semelhante a:

```text
Backfill de tenants (dry-run):
  clinic.Appointment: 0
  clinic.Encounter: 0
  clinic.ClinicalRecord: 0
  clinic.Charge: 0
  clinic.AnamneseBase: 0
  clinic.ReminderDelivery: 0
  clinic.TreatmentPlan: 0
  clinic.ChargeItem: 0
  clinic.PodologyProcedureContext: 0
```

Os nomes e os totais podem variar conforme os dados online.

### Interpretação do resultado

Se todos os totais forem `0`:

- não há registros candidatos no banco online;
- não é necessário executar o backfill real;
- registrar o resultado e seguir para os smoke tests.

Se houver totais maiores que `0`:

- não executar imediatamente o comando real;
- salvar o resumo;
- confirmar que os registros pertencem a um único tenant inequívoco;
- confirmar que não há conflito de memberships;
- revisar o resultado com o responsável pela operação.

O backfill ignora profissionais associados a múltiplos tenants para evitar
atribuição incorreta.

## 6. Aplicar o backfill aprovado

Executar somente depois da revisão do `dry-run`:

```bash
python manage.py backfill_existing_tenants
```

Registrar a saída completa do comando.

Depois, executar novamente em modo de simulação:

```bash
python manage.py backfill_existing_tenants --dry-run
```

O segundo `dry-run` deve retornar `0` para todos os registros que foram
processados. Se ainda houver candidatos, interromper e investigar antes de
prosseguir.

## 7. Smoke tests de saúde

Validar os endpoints públicos de saúde usando a URL real do backend:

```bash
curl -fsS https://SEU_BACKEND/health/
curl -fsS https://SEU_BACKEND/health/full
```

Substituir `https://SEU_BACKEND` pela URL real antes de executar.

Resultado esperado:

- resposta HTTP bem-sucedida;
- payload indicando que o serviço está disponível;
- nenhuma falha de conexão com o banco.

## 8. Smoke tests funcionais

Executar a partir do frontend ou de um cliente HTTP controlado:

- login Clinic com usuário autorizado;
- login Bakery com usuário autorizado;
- login por e-mail;
- login por `login_alias`, quando aplicável;
- acesso a um tenant Clinic;
- acesso a um tenant Bakery;
- usuário com múltiplos tenants utilizando o tenant escolhido no token;
- rejeição de token sem contexto de tenant;
- rejeição de acesso a tenant diferente do token;
- leitura de um recurso Clinic;
- leitura de um recurso Bakery;
- uma gravação controlada, somente se autorizada na janela operacional.

Não utilizar contas ou dados pessoais reais em comandos salvos em arquivos,
histórico compartilhado ou relatórios.

## 9. Verificar logs na Render

Após os smoke tests, revisar os logs do serviço e procurar por:

- `500`;
- `FieldError`;
- `IntegrityError`;
- `PermissionDenied` inesperado;
- falhas de autenticação;
- erros relacionados a `tenant_id`;
- erros de conexão com o banco;
- aumento anormal de latência.

Também confirmar que o deploy não iniciou um loop de reinício.

## 10. Critérios de sucesso

Considerar a atualização validada somente se:

- o commit em execução for o aprovado;
- `manage.py check` passar;
- as migrations estiverem no estado esperado;
- o `dry-run` for revisado;
- o backfill real, quando executado, terminar sem erro;
- o segundo `dry-run` não encontrar novos candidatos;
- `/health/` e `/health/full` responderem corretamente;
- os logins Clinic e Bakery funcionarem;
- o isolamento por tenant estiver correto;
- não houver erro anormal nos logs.

## 11. Procedimento de interrupção

Interromper e não continuar o roteiro se ocorrer qualquer uma destas
situações:

- commit incorreto em execução;
- migration pendente não aprovada;
- `dry-run` com registros ambíguos;
- `FieldError` ou `IntegrityError`;
- falha no health check;
- login emitindo token com tenant incorreto;
- acesso cruzado entre tenants;
- erro persistente nos logs.

Não executar `migrate zero`, não apagar dados manualmente e não tentar
corrigir registros diretamente no banco sem um procedimento aprovado.

## 12. Registro da execução

Preencher após a validação:

```text
Data/hora:
Serviço:
Commit:
Deploy concluído:
Backup confirmado:
manage.py check:
Migrations:
Dry-run inicial:
Backfill real executado:
Dry-run final:
Health checks:
Smoke tests:
Logs revisados:
Resultado:
Responsável:
Observações:
```

