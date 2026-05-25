# las-update-installer (multiplatform)

Port Python multiplataforma do **LAS Update Installer** (equivalente a `br.com.mv.mvupdate.App` em Java).

Gerencia instalação, atualização, inicialização e remoção de módulos LAS via install4j, com descoberta de instâncias, instância única e suporte ao esquema de URI `mvupdate://`.

## Plataformas suportadas

| Plataforma | Status |
|------------|--------|
| Windows    | Suportado (registro de protocolo `mvupdate://` via registry) |
| Linux      | Suportado |
| macOS      | Suportado (testado) |

## Requisitos

- Python 3.10+
- Dependências em `requirements.txt`

```bash
pip install -r requirements.txt
```

## Execução

```bash
python app.py
```

Ao iniciar, o servidor escolhe uma porta disponível entre `32768` e `32818`, persiste a configuração em disco e registra handlers REST para gerenciamento de módulos.

No Windows, o protocolo `mvupdate://` é registrado automaticamente no registry (requer permissões de administrador para registro em `HKEY_CLASSES_ROOT`).

## Estrutura

```
app.py                  # Ponto de entrada
config.py               # Constantes da aplicação
environment.py          # Resolução hierárquica de propriedades
managers/               # Instância única, módulos, discovery
models/                 # DTOs e entidades
repositories/           # Persistência (config, chaves, módulos)
server/                 # Servidor HTTP (Flask + Waitress)
discovery/              # Cliente de discovery
utils/                  # Utilitários OS-specific e install4j
```

## Configuração

Propriedades em `application.properties` (menor prioridade). Variáveis de ambiente e propriedades de runtime têm precedência (ver `environment.py`).

Diretórios de dados por SO:

- **Windows:** `%LOCALAPPDATA%/mv/las/temp`
- **Linux / macOS:** `~/.config/mv/las/temp`

## Versão

`2.2.6` (ver `config.py`)
