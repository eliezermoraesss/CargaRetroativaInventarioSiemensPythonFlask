# Carga Retroativa de Inventário Siemens — Point of Sales API

Sistema automatizado com dashboard Web interativo para realização de carga retroativa e contínua de **Inventário/Estoque** para a API Siemens Point of Sales (`/qua/inventory/create_record`).

## 📌 Funcionalidades

- **Envio em Batches de no máximo 1.000 registros**: Otimizado para alta performance e estabilidade da API Siemens.
- **Filtro por Período (`AD_DHINC`)**: Seleção dinâmica de intervalo de datas (início e fim) no frontend.
- **Modo Dry Run**: Simula a busca no Oracle e loteamento sem realizar disparos HTTP reais.
- **Dashboard em Tempo Real (SSE)**: Acompanhamento de progresso, barra visual animada, métricas de envio e log de eventos streaming.
- **Controle de Interrupção**: Botão para cancelar graciosamente o envio entre lotes.
- **Retry Automático**: Re-tentativa automática com backoff exponencial em caso de instabilidade na API.

## 🛠️ Arquitetura do Projeto

```
CargaRetroativaInventarioSiemens/
├── app.py                # Servidor Flask principal (Worker em background, SSE, API REST)
├── config.py             # Configurações centralizadas (.env)
├── db_oracle.py          # Conexão e queries Oracle (Query A: Filial / Query B: Produtos)
├── siemens_api.py        # Módulo de envio HTTP POST para /qua/inventory/create_record
├── wsgi.py               # Entrypoint WSGI para produção
├── setup.bat             # Script de instalação e execução automatizada em Windows
├── requirements.txt      # Dependências Python (Flask, oracledb, requests, python-dotenv)
├── templates/
│   └── index.html        # Interface do Dashboard (HTML5 semântico)
└── static/
    ├── style.css         # CSS Design System (Tema Escuro, Glassmorphism, Paleta Siemens)
    └── app.js            # Lógica Client-Side (SSE, controles, métricas)
```

## 🚀 Como Executar

### Pré-requisitos
- Python 3.10 ou superior
- Acesso à rede/VPN para conexão ao banco Oracle `CLOUD.MULTFER.COM.BR:21159/PROD`

### 1. Via `setup.bat` (Windows - Recomendado)
Basta dar dois cliques no arquivo `setup.bat` na raiz do projeto. Ele irá:
1. Criar o ambiente virtual `.venv` se não existir.
2. Instalar todas as dependências do `requirements.txt`.
3. Iniciar a aplicação na porta `5001`.
4. Abra o navegador em: `http://localhost:5001`.

### 2. Manualmente via Terminal

```bash
# Entrar no diretório do projeto
cd CargaRetroativaInventarioSiemens

# Criar e ativar o ambiente virtual
python -m venv .venv
.venv\Scripts\activate

# Instalar dependências
pip install -r requirements.txt

# Executar a aplicação
python app.py
```

Acesse o dashboard no seu navegador em: `http://localhost:5001`.

## ⚙️ Variáveis de Ambiente (`.env`)

| Variável | Valor Padrão | Descrição |
| --- | --- | --- |
| `ORA_USER` | `SANKHYA` | Usuário da base Oracle |
| `ORA_PASS` | `laranja` | Senha da base Oracle |
| `ORA_DSN` | `CLOUD.MULTFER.COM.BR:21159/PROD` | DSN da conexão Oracle |
| `SIEMENS_API_URL` | `https://api.pos.siemens.com/qua/inventory/create_record` | Endpoint de Inventário Siemens |
| `SIEMENS_API_TOKEN` | `4rwtKHdH44oa1K5Zs9kXa20NLEco8FQ95AtbJngh` | Header `x-api-key` |
| `SIEMENS_DISTRIBUTOR_SENDER_ID` | `40212903` | Header `distributor_sender_id` |
| `BATCH_SIZE` | `1000` | Limite de registros por batch |
| `FLASK_PORT` | `5001` | Porta do servidor Web |
