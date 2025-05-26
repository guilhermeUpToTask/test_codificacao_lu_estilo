# API Comercial – Projeto de Teste de Codificação

Este repositório contém a **API RESTful** desenvolvida como parte de um **teste de codificação** para uma empresa fictícia chamada **Lu Estilo**. O objetivo é demonstrar habilidades em backend, incluindo autenticação, CRUD completo e deploy em Docker.

## 🔥 Funcionalidades

* **Autenticação e Autorização**

  * Registro, login e refresh token (JWT)
  * Controle de acesso por níveis (admin e usuário)

* **Gestão de Clientes**

  * CRUD completo
  * Filtros por nome e email
  * Validação de CPF e email únicos

* **Gestão de Produtos**

  * CRUD completo
  * Filtros por categoria, preço e disponibilidade
  * Upload de imagens e controle de estoque

* **Gestão de Pedidos**

  * CRUD completo
  * Filtros por período, status, seção, ID e cliente
  * Validação de estoque ao criar pedidos


## 🛠️ Tecnologias e Ferramentas

* **Backend:** FastAPI, SQLAlchemy
* **Banco de Dados:** PostgreSQL
* **Autenticação:** JWT
* **Testes:** Pytest
* **Containerização:** Docker e Docker Compose
* **Documentação:** Swagger (automático via FastAPI)

## 🚀 Como Executar Localmente

### Pré-requisitos

* Docker e Docker Compose
* Git

### Clonar o repositório

```bash
git clone https://github.com/seu-usuario/nome-do-repositorio.git
cd nome-do-repositorio
```

### Configurar variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto, por exemplo:

```env
PROJECT_NAME=

#FastApi Configuration
SECRET_KEY = 
# Algorithm used for encoding the JWT token.
ALGORITHM = HS256
ACCESS_TOKEN_EXPIRE_MINUTES =
ADMIN_USER=
ADMIN_PASSWORD=

# Database Configuration
DATABASE_USERNAME=
DATABASE_PASSWORD=
DATABASE_HOST=
DATABASE_NAME=
DATABASE_PORT=

```

### Subir o ambiente

```bash
docker-compose up --build
```

A API estará disponível em `http://localhost:8000`.

#### Documentação

* Swagger: `http://localhost:8000/docs`
* Redoc: `http://localhost:8000/redoc`

## 🗄️ Migrations

```bash
docker-compose exec api alembic revision --autogenerate -m "Mensagem da migration"
docker-compose exec api alembic upgrade head
```

## ✅ Testes

```bash
docker-compose exec api pytest
```

## 🏗️ Estrutura do Projeto

```plaintext
.
├── app/
│   ├── api/           # Rotas
│   ├── core/          # Configurações e segurança
│   ├── models/        # Modelos ORM
│   ├── schemas/       # Schemas Pydantic
│   ├── services/      # Lógica de negócio e integração WhatsApp
│   ├── tests/         # Testes unitários e de integração
│   ├── main.py        # Entrada da aplicação
├── alembic/           # Migrations
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── README.md
```




> **Observação:** Este projeto foi criado exclusivamente como um **exemplo demonstrativo** para o teste de codificação da empresa fictícia **Lu Estilo**.
