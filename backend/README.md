# 🧠 ENGINE — Backend (Django)

Este repositório contém o backend principal utilizado por todos os sistemas (Clinic, Bakery, Jurídico, Previdenciário).  
A arquitetura é **multi-servidor**, permitindo isolamento e personalização por cliente.

## 🚀 Tecnologias
- Django + Django REST Framework  
- PostgreSQL  
- JWT para autenticação  
- Deploy na Render  

## 📂 Estrutura
- `apps/` → módulos independentes (agenda, clients, tenancy, etc.)
- `scripts/` → utilitários e automações
- `docs/` → documentação interna
- `core/` → configurações principais do projeto

## ▶️ Como rodar localmente
```bash
python manage.py migrate
python manage.py runserver
