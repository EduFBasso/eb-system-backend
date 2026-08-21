# Arquitetura do Projeto

## 📐 Diretrizes Gerais
- Limite máximo de **700 linhas por arquivo**.  
- Se ultrapassar, aplicar **modularização** para manter leveza e facilitar edição.  
- Seguir princípios **SOLID** e **DDD** sempre que possível.  
- Separar responsabilidades entre backend, frontend e testes.  
- Documentar decisões arquiteturais neste arquivo para referência futura.

---

## ⚙️ Backend (Django)
- Estrutura modularizada em apps (`clinic/`, `bakery/`, `juridico/` etc.).  
- Configurações divididas em arquivos específicos dentro de `settings/`:  
  - `database.py` → conexões e ORM.  
  - `auth.py` → autenticação e permissões.  
  - `tenants.py` → multi-tenant e capacities.  
- **Capacities**:  
  - Usar flags booleanas (`odonto: true`) para especialidades.  
  - Evoluir para JSON declarativo se necessário (ex.: permissões, regras específicas).  
- Migrations sempre acompanhadas de atualização de testes.  

---

## 🎨 Frontend (React/Next)
- Estrutura em `src/components/` com **PascalCase**:  
  - `NomeComponente.tsx` → export direto (`export function NomeComponente() {}`).
  - `NomeComponente.module.css` → escopo local, sem `default`.  
- Estrutura em `pages/` pode usar **camelCase** para fluxos diferentes, mas sempre com CSS escopado local.  
- UX refinado com foco em acessibilidade e consistência visual.  

---

## 🧪 Testes
- Cobertura mínima obrigatória para cada módulo.  
- Testes devem ser atualizados junto com migrations e refatorações.  
- Revisão periódica com agente de testes (Claude Sonnet 5.0).  

---

## 🤖 Perfis de IA
- **Copilot principal** → Arquitetura, backend, chamadas de API, migrations, testes.  
- **Luna 5.6** → Refinamento de UX, acessibilidade, copywriting e consistência visual.  
- **Claude Sonnet 5.0** → Revisão de código e testes, garantindo legibilidade e cobertura.  

---

## 📂 Organização do Workspace
- Frontend e backend como **irmãos** dentro da mesma pasta.  
- Ecosistemas não utilizados devem permanecer **comentados** no workspace para evitar ruído.  
- Cada agente só enxerga o que está ativo no momento.  

---

## 📌 Fluxo de Trabalho
1. **Planejamento** → definir arquitetura e atualizar `ARCHITECTURE.md`.  
2. **Execução** → Copilot gera backend modularizado.  
3. **Refinamento** → Luna melhora UX e interface.  
4. **Validação** → Sonnet revisa testes e consistência.  
