# Adicionar um novo tenant Bakery

Este guia descreve o cadastro de uma nova panificadora usando um subdomínio
próprio, por exemplo:

```text
https://mister-pao.ebsis.com.br
```

O procedimento mantém o tenant de teste separado e configura o acesso no
Django Admin, no backend Render, na Vercel e no Registro.br.

## 1. Definir os dados

Escolha um slug único, em minúsculas, sem espaços e preferencialmente usando
hífens:

```text
Nome: Mister Pão
Nome fantasia: Mister Pão
Slug: mister-pao
Domínio: mister-pao.ebsis.com.br
Ecossistema: Unidade Padaria (Alimentação/Varejo)
Capacidades: {"bakery": true}
```

O slug é usado como `tenant_slug` no login e deve corresponder ao primeiro
subdomínio:

```text
mister-pao.ebsis.com.br -> tenant_slug=mister-pao
```

Não reutilize o slug de outro tenant. Para uma empresa real, não renomeie o
tenant de teste; crie um novo registro.

## 2. Criar o Tenant no Django Admin

No Django Admin do backend, abra **Authentication > Empresas (Tenants) >
Adicionar** e preencha:

- **Nome da Empresa / Unidade**: razão social ou identificação interna;
- **Nome Fantasia**: nome público da empresa;
- **CEP**;
- **Rua / Avenida**;
- **Número**;
- **Bairro**;
- **Cidade**;
- **Estado**: sigla com duas letras;
- **Complemento**, se houver;
- **Identificador na URL (Slug)**: o novo slug;
- **Ecossistema / Tipo de Negócio**: Unidade Padaria;
- **Capacidades / Funcionalidades Ativas**:
  ```json
  {"bakery": true}
  ```
- **Cadastro Ativo**: marcado.

Os dados de endereço pertencem ao Tenant, não ao usuário proprietário.

Depois de salvar, confirme na listagem:

```text
slug: mister-pao
ecosystem: bakery
is_active: sim
```

## 3. Criar o usuário proprietário

Em **Authentication > Usuários do Sistema**, crie uma conta individual para o
proprietário:

- e-mail real e controlado pelo proprietário;
- nome e sobrenome reais;
- telefone celular correto;
- senha inicial segura;
- usuário ativo;
- `is_superuser`: desmarcado, salvo necessidade administrativa explícita.

Não use e-mail fictício que não possa ser recuperado. O e-mail identifica a
conta e poderá ser necessário para recuperação de acesso.

## 4. Criar o membership `owner`

Em **Authentication > Vínculos de Acessos (Memberships)**, crie:

```text
Tenant: Mister Pão (mister-pao)
Professional: usuário proprietário
Role: Dono da Empresa (owner)
Login alias: opcional
Vínculo habilitado: marcado
```

Se houver gerente ou secretário, crie outra conta individual e outro
membership no mesmo tenant:

```text
Role: Administrador da Unidade (admin)
```

Não compartilhe a mesma credencial entre owner e admin.

## 5. Adicionar o domínio na Vercel

No projeto `bakery-system`, abra:

```text
Settings > Domains > Add Existing
```

Informe o domínio completo:

```text
mister-pao.ebsis.com.br
```

Escolha:

```text
Connect to an environment
Environment: Production
```

Não escolha **Redirect to Another Domain**. O subdomínio deve servir o
frontend Bakery diretamente e identificar o tenant pelo hostname.

A Vercel exibirá o registro DNS necessário. Use o valor exibido pela Vercel,
pois ele pode ser específico para o domínio. Não substitua automaticamente
por outro destino.

## 6. Criar o registro no Registro.br

No DNS do domínio `ebsis.com.br`, adicione o registro solicitado pela Vercel.
Normalmente será:

```text
Tipo: CNAME
Nome: mister-pao
Destino: <valor exibido pela Vercel>
```

O Registro.br pode exibir o nome completo como:

```text
mister-pao.ebsis.com.br
```

Não crie outro registro se já existir um `A`, `AAAA` ou `CNAME` com o mesmo
nome. Verifique o conflito antes de substituir qualquer entrada.

Volte à Vercel e use **Refresh**. Prossiga somente quando aparecer:

```text
Valid Configuration
```

## 7. Autorizar a origem no backend

No serviço `eb-system-api` da Render, mantenha as origens existentes e
acrescente o novo domínio completo em `CORS_ALLOWED_ORIGINS`:

```text
https://panificadora.ebsis.com.br,https://mister-pao.ebsis.com.br
```

Se `CSRF_TRUSTED_ORIGINS` estiver configurada, acrescente o domínio também:

```text
https://panificadora.ebsis.com.br,https://mister-pao.ebsis.com.br
```

Cada origem deve incluir `https://`, sem barra final. Não use apenas:

```text
mister-pao.ebsis.com.br
```

Depois de salvar, faça o deploy do backend e aguarde o serviço ficar
saudável. Uma origem inválida pode impedir o Django de iniciar.

## 8. Configurar o frontend Bakery

No projeto `bakery-system` da Vercel, em **Environment Variables**, mantenha
as variáveis existentes e confirme, no ambiente **Production**:

```text
VITE_API_BASE=<configuração atual da API>
VITE_BAKERY_PUBLIC_HOST=<host público legado, se utilizado>
VITE_BAKERY_TENANT_SLUG=panificadora
VITE_BAKERY_ROOT_DOMAIN=ebsis.com.br
```

`VITE_BAKERY_ROOT_DOMAIN` é configurada uma vez para o domínio raiz. Não é
necessário criar uma variável `VITE_*` para cada novo tenant.

O valor correto é:

```text
ebsis.com.br
```

Não inclua `https://`.

Como variáveis `VITE_*` são incorporadas durante o build, faça um novo deploy
do frontend depois de salvar ou alterar essa variável.

## 9. Validar o login e o isolamento

Abra:

```text
https://mister-pao.ebsis.com.br/admin
```

Valide:

1. o certificado HTTPS;
2. a tela de login Bakery;
3. o login do usuário `owner`;
4. o nome e o endereço de Mister Pão no painel;
5. os contadores inicialmente esperados;
6. a ausência de clientes, produtos e pedidos do tenant de teste.

No DevTools do navegador, em **Network**, confira a requisição de login. Ela
deve usar:

```text
tenant_slug=mister-pao
```

Se aparecer `tenant_slug=panificadora`, o frontend ainda está usando o
fallback antigo e precisa de novo deploy com `VITE_BAKERY_ROOT_DOMAIN`.

Teste também o endereço público:

```text
https://mister-pao.ebsis.com.br/
```

## 10. Validar operação e Telegram

Depois de confirmar o login:

1. cadastre um produto de teste;
2. cadastre um cliente de teste;
3. crie um pedido de teste;
4. confirme o status e os dados do pedido;
5. verifique a notificação do responsável no Telegram;
6. confirme que o pedido aparece no histórico do tenant correto.

O token da Bakery deve existir no `eb-system-api`:

```text
BAKERY_TELEGRAM_BOT_TOKEN
BAKERY_TELEGRAM_BOT_API_BASE=https://api.telegram.org
BAKERY_TELEGRAM_BOT_TIMEOUT_SECONDS=10
```

O Bakery envia notificações por evento e não precisa de CronJob para novos
pedidos, cancelamentos ou novos clientes.

## Checklist final

```text
[ ] Tenant criado com slug único
[ ] Ecosystem = bakery
[ ] Capacidade {"bakery": true}
[ ] Tenant ativo
[ ] Endereço comercial preenchido
[ ] Usuário owner criado com e-mail controlado
[ ] Membership owner ativo no tenant correto
[ ] Domínio adicionado à Vercel em Production
[ ] CNAME criado no Registro.br
[ ] Vercel mostra Valid Configuration
[ ] CORS_ALLOWED_ORIGINS atualizado com https:// e sem barra final
[ ] CSRF_TRUSTED_ORIGINS atualizado, se aplicável
[ ] Backend redeployado com sucesso
[ ] VITE_BAKERY_ROOT_DOMAIN=ebsis.com.br em Production
[ ] Frontend redeployado após a variável
[ ] Login envia tenant_slug correto
[ ] Dados do tenant de teste não aparecem
[ ] Pedido de teste criado
[ ] Telegram do responsável validado
```

