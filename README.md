# las-update-installer (multiplatform)

Port Python multiplataforma do **LAS Update Installer** — equivalente a `br.com.mv.mvupdate.App` (Java).

Este serviço local gerencia o ciclo de vida de módulos LAS (instalar, iniciar, parar, desinstalar), registra instâncias em um servidor de discovery, garante execução em instância única e trata conexões via esquema de URI `mvupdate://`. Os módulos em si são empacotados com **install4j** e executados como aplicações **Java**.

## Visão geral do fluxo

```
Navegador (LAS web + Flash)
        │
        │  clique em link mvupdate://connect?{base64}
        ▼
las-update-installer (Python)  ──►  servidor HTTP local (Flask/Waitress)
        │
        │  install / start / stop / uninstall
        ▼
Executáveis install4j (.exe / .sh)  ──►  aplicações Java (módulos LAS)
```

1. O portal LAS no navegador dispara um link `mvupdate://` com credenciais codificadas em Base64.
2. O sistema operacional abre o `las-update-installer` (registrado como handler do protocolo no Windows).
3. O instalador Python sobe (ou reutiliza) um servidor HTTP em `127.0.0.1` na faixa de portas `32768–32818`.
4. Via API REST, recebe pacotes de módulos, executa instaladores install4j e inicia os binários Java com propriedades JVM (`-J-Ddiscovery.server.url`, `-J-Ddiscovery.server.token`).

## Plataformas suportadas

| Plataforma | Status | Observações |
|------------|--------|-------------|
| Windows    | Suportado | Registro automático do protocolo `mvupdate://` no registry |
| Linux      | Suportado | File lock via `fcntl`; instaladores `.sh` |
| macOS      | Suportado | Testado; paths em `~/.config` e `~/.local/share` |

---

## Requisitos do ambiente

O `las-update-installer` em Python é apenas o **orquestrador local**. Para o ecossistema LAS funcionar de ponta a ponta, a máquina precisa dos componentes abaixo.

### 1. Python (obrigatório — este projeto)

| Item | Requisito |
|------|-----------|
| Python | **3.10+** |
| pip | Para instalar dependências |

```bash
pip install -r requirements.txt
```

Dependências Python (`requirements.txt`):

| Pacote | Uso |
|--------|-----|
| `flask` | Servidor HTTP e roteamento da API |
| `waitress` | Servidor WSGI de produção (substitui o embedded do Java) |
| `requests` | Cliente HTTP (discovery, connect entre instâncias) |

### 2. Java Runtime (obrigatório — módulos install4j)

Os módulos LAS são distribuídos e executados via **install4j**. O código invoca instaladores e executáveis nativos gerados pelo install4j e repassa argumentos JVM com o prefixo `-J-`:

```python
# utils/install4j_utils.py — ao iniciar um módulo
args.append(f"-J-Ddiscovery.server.url={server_config.url}")
args.append(f"-J-Ddiscovery.server.token={server_config.token}")
```

Isso indica que os binários empacotados são **launchers install4j para aplicações Java**. Em teoria (e na prática do ecossistema LAS):

- O **install4j** embute ou exige um **JRE/JDK** compatível com a versão usada na build do módulo.
- Se o launcher não trouxer JRE bundled, é necessário ter **Java instalado e acessível** no sistema (`JAVA_HOME` / `PATH`).
- Versão recomendada: alinhar com a versão Java usada na build dos módulos LAS da sua release (consulte a documentação interna da MV / release notes do módulo).

> **Resumo:** Python roda o instalador; **Java roda os módulos** instalados via install4j.

### 3. Navegador com suporte a Flash (obrigatório — portal LAS)

O gatilho inicial do fluxo parte do **navegador**, que abre links `mvupdate://`. O portal web LAS ainda depende de **Adobe Flash** para componentes legados da aplicação.

É necessário um navegador **compatível com Flash** em uma das famílias abaixo:

| Família | Exemplos | Observação |
|---------|----------|------------|
| **Chromium** | Google Chrome, Microsoft Edge (legado), Chromium, browsers corporativos baseados em Chromium | Versões antigas ou builds corporativos que ainda permitam NPAPI/PPAPI Flash, conforme política interna |
| **Firefox** | Mozilla Firefox, builds baseados em Gecko | Versões ESR ou builds legados com Flash habilitado, conforme política interna |

Requisitos práticos:

- O navegador deve conseguir **abrir o protocolo customizado** `mvupdate://` (handler registrado no SO).
- O plugin Flash deve estar **habilitado** para o domínio/origem do portal LAS.
- Flash foi descontinuado pela Adobe em 2020; em ambientes atuais isso normalmente implica **versões específicas de browser + plugin** mantidas pelo time de infraestrutura, ou ambientes virtualizados/VDI com essa stack congelada.

> **Resumo:** sem navegador Flash-compatível, o usuário não acessa o portal LAS nem dispara os links `mvupdate://` que acionam este instalador.

### 4. Permissões e SO (recomendado)

| SO | Permissão / configuração |
|----|--------------------------|
| Windows | Admin para registro de `mvupdate://` em `HKEY_CLASSES_ROOT` (primeira execução) |
| Linux / macOS | Permissão de execução nos instaladores `.sh`; file lock em `~/.config/mv/las/temp` |
| Todos | Portas locais `32768–32818` disponíveis; acesso de gravação nos diretórios de dados (ver abaixo) |

---

## Instalação

```bash
git clone https://github.com/lucaslamdev/las-update-installer_multiplatform.git
cd las-update-installer_multiplatform
pip install -r requirements.txt
```

Certifique-se de que **Java** e o **navegador Flash-compatível** já estejam configurados conforme a seção de requisitos antes de usar o fluxo completo LAS.

---

## Execução

```bash
python app.py
```

### Modo debug

Ative o rastreamento detalhado para inspecionar módulos instalados, tráfego HTTP e operações install4j:

```bash
python app.py --debug
```

Outras formas de ativar:

| Método | Exemplo |
|--------|---------|
| Variável de ambiente | `LAS_DEBUG=1 python app.py` |
| `application.properties` | `las.debug=true` |
| Diretório customizado | `LAS_DEBUG_DIR=C:/temp/las-debug python app.py --debug` |

Com debug ativo, cada request **recebido** e **enviado** é exibido no terminal em tempo real (além dos arquivos JSONL). Payloads Base64 — como o parâmetro de `mvupdate:connect?{base64}` — são decodificados automaticamente na tela para facilitar a leitura.

Com debug ativo, os artefatos também são gravados em:

| Caminho (padrão) | Conteúdo |
|------------------|----------|
| `{temp}/debug/http_inbound.jsonl` | Requests/responses recebidos pelo servidor local |
| `{temp}/debug/http_outbound.jsonl` | Requests/responses enviados (discovery, `/connect`) |
| `{temp}/debug/events.jsonl` | Eventos de módulos, install4j e startup |
| `{temp}/debug/requests/` | Snapshot JSON individual por request |
| `{temp}/debug/modules/{release}/{timestamp}/` | Cópia dos instaladores recebidos + `metadata.json` |

`{temp}` corresponde a `%LOCALAPPDATA%/mv/las/temp` (Windows) ou `~/.config/mv/las/temp` (Linux/macOS), salvo se `LAS_DEBUG_DIR` for definido.

Tokens de autenticação são mascarados nos logs (`TOKEN***xxxx`). Uploads de módulos são arquivados integralmente para análise posterior.

### Comportamento na inicialização

1. Carrega logging de `logging.properties`.
2. **Windows:** tenta registrar `mvupdate://` no registry (`utils/protocol_registry.py`).
3. Se recebeu URI na linha de comando (`mvupdate:connect?...`), decodifica a chave de autenticação.
4. Verifica **instância única** via file lock (`managers/single_instance_manager.py`).
   - Se já houver instância: envia POST `/connect` para a instância existente.
   - Se for a primeira: escolhe porta livre, persiste `serverConfig.properties` e sobe o servidor.
5. Se `discovery.server.url` e `discovery.server.token` estiverem configurados, inicia o **DiscoveryClient** (registro + heartbeat).

### Disparo via navegador

Formato da URI:

```
mvupdate:connect?{json_base64}
```

O JSON decodificado contém a chave `MvupdateKey` usada na autenticação das rotas protegidas da API.

---

## Diretórios de dados

| Finalidade | Windows | Linux / macOS |
|------------|---------|---------------|
| Lock, config do servidor | `%LOCALAPPDATA%/mv/las/temp` | `~/.config/mv/las/temp` |
| Módulos install4j (upload/install) | `%LOCALAPPDATA%/mv/las/{release}/` | `~/.local/share/mv/las/{release}/` |

Arquivos relevantes por módulo:

- `{release}` — instalador enviado via API (upload)
- `{release}-install.properties` — gerado pelo install4j após instalação
- `{release}-install.exe` / `{release}-install.sh` — wrapper install4j
- Binário Java do módulo — paths em `installation.dir`, `execute.file`, `uninstall.file` no `.properties`

---

## Configuração

Prioridade de propriedades (`environment.py`):

1. Propriedades de runtime (`ApplicationEnvPropertySource`)
2. Variáveis de ambiente do SO
3. Arquivo `application.properties`

Propriedades principais:

| Propriedade | Descrição |
|-------------|-----------|
| `discovery.server.url` | URL base do servidor de discovery remoto |
| `discovery.server.token` | Token de autenticação do discovery |
| `uriSchema` | URI `mvupdate://` (normalmente passada pelo browser na linha de comando) |
| `las.debug` | `true` para ativar modo debug (ver seção Execução) |
| `info.build.name` / `info.build.version` | Metadados de build (em `application.properties`) |

Constantes em `config.py`:

| Constante | Valor | Descrição |
|-----------|-------|-----------|
| `PORT_MIN` / `PORT_MAX` | 32768 – 32818 | Faixa de portas do servidor local |
| `HEARTBEAT_INTERVAL` | 10 s | Intervalo de heartbeat com discovery |
| `MVUPDATE_KEY_TTL` | 8 h | TTL das chaves mvupdate |
| `MODULE_POLL_TIMEOUT` | 30 s | Timeout ao aguardar start/stop de módulo |

---

## API HTTP (resumo)

Servidor local em `http://127.0.0.1:{porta}`. Autenticação via header `Authentication: TOKEN{token}`.

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/` | Info do servidor (release, SO, hostname, links) |
| GET | `/modules` | Lista módulos instalados |
| GET | `/modules/{release}` | Status de um módulo |
| POST | `/modules/{release}` | Upload e instalação de módulo (multipart) |
| DELETE | `/modules/{release}` | Desinstala e remove módulo |
| POST | `/modules/{release}/start` | Inicia módulo (install4j + JVM args) |
| POST | `/modules/{release}/stop` | Para módulo |
| POST | `/discovery/{release}` | Registra instância no discovery local |
| PUT | `/discovery/{release}` | Heartbeat |
| DELETE | `/discovery/{release}/{instance_id}` | Remove instância |
| POST | `/connect` | Conecta instância secundária à principal |
| POST | `/shutdown` | Encerra o servidor |

---

## Estrutura do projeto

```
app.py                  # Ponto de entrada
config.py               # Constantes da aplicação
environment.py          # Resolução hierárquica de propriedades
application.properties  # Propriedades default
logging.properties      # Configuração de log (estilo Java)
managers/               # Instância única, módulos, discovery
models/                 # DTOs e entidades
repositories/           # Persistência (config, chaves, módulos)
server/                 # Servidor HTTP (Flask + Waitress)
discovery/              # Cliente de discovery remoto
utils/                  # install4j, protocolo mvupdate, hostname, portas
```

---

## Troubleshooting

| Sintoma | Possível causa | Ação |
|---------|----------------|------|
| Link `mvupdate://` não abre o instalador | Protocolo não registrado (Windows) ou handler ausente | Executar como admin no Windows; verificar registro em `utils/protocol_registry.py` |
| Instalação do módulo falha | Java ausente ou incompatível | Instalar JRE/JDK da versão exigida pelo módulo; verificar logs do install4j |
| Portal LAS não carrega | Flash desabilitado ou browser incompatível | Usar Chrome/Firefox compatível com Flash conforme política interna |
| "Another instance running" | Instância anterior ativa | Encerrar processo Python existente ou remover lock em `mv/las/temp` |
| Módulo não inicia | Executável install4j ausente | Verificar `{release}-install.properties` e paths em `ModuleConfig` |
| Discovery não registra | URL/token não configurados | Definir `discovery.server.url` e `discovery.server.token` |

---

## Versão

**2.2.6** — ver `config.py` e `application.properties`.
