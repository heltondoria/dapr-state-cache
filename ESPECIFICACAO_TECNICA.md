# Especificação Técnica - dapr-state-cache v0.4.0

## 1. Visão Geral e Objetivos

### 1.1 Propósito da Biblioteca

A biblioteca `dapr-state-cache` é uma solução de cache transparente baseada em Dapr State Store, projetada para simplicidade, alta performance e facilidade de uso. A biblioteca implementa um sistema de cache que funciona com funções síncronas e assíncronas, métodos de instância e funções standalone.

### 1.2 Princípios de Design

- **Simplicidade**: API mínima e intuitiva
- **Transparência**: Decorator não modifica comportamento da função
- **Performance**: Comunicação HTTP direta com sidecar Dapr
- **Flexibilidade**: Suporte nativo a sync e async sem ThreadPool
- **Observabilidade**: Integração com OpenTelemetry

### 1.3 Casos de Uso Principais

- **Cache de APIs**: Cache de respostas de APIs externas com TTL configurável
- **Cache de Dados Computacionais**: Cache de resultados de operações custosas
- **Cache de Configurações**: Cache de configurações de aplicação
- **Cache de Métodos de Serviço**: Cache de métodos de classes de serviço

## 2. Arquitetura do Sistema

### 2.1 Estrutura de Arquivos

```text
dapr_state_cache/
├── __init__.py           # Exports públicos
├── decorator.py          # @cacheable decorator
├── backend.py            # DaprStateBackend (HTTP direto)
├── serializer.py         # MsgPackSerializer
├── key_builder.py        # DefaultKeyBuilder
├── deduplication.py      # DeduplicationManager
├── metrics.py            # OpenTelemetry metrics
├── protocols.py          # Protocols para extensibilidade
└── exceptions.py         # Exceções
```

### 2.2 Fluxo de Dados

1. **Geração de Chave**: `prefix:module.function:hash(args)`
2. **Cache Lookup**: Busca via HTTP no Dapr State Store
3. **Cache Hit**: Retorna dados deserializados (MsgPack)
4. **Cache Miss**: Deduplica chamadas concorrentes → Executa função → Serializa → Armazena
5. **Cache Write**: Armazena com TTL via metadata `ttlInSeconds`

### 2.3 Comunicação com Dapr

A biblioteca usa a [API HTTP do Dapr State](https://docs.dapr.io/reference/api/state_api/) diretamente:

- `GET /v1.0/state/{storename}/{key}` - Buscar valor
- `POST /v1.0/state/{storename}` - Salvar valor com TTL
- `DELETE /v1.0/state/{storename}/{key}` - Deletar valor

**Benefícios desta abordagem**:

- Sem dependência do SDK Dapr Python
- Controle total sobre sync/async via httpx
- Compatível com qualquer objeto async (conexões de BD, sessions HTTP)

## 3. API do Decorator @cacheable

### 3.1 Parâmetros

```python
@cacheable(
    store_name: str = "cache",           # Nome do state store Dapr
    ttl_seconds: int = 3600,             # TTL em segundos
    key_prefix: str = "cache",           # Prefixo das chaves
    key_builder: KeyBuilder | None = None,  # Construtor de chaves customizado
    serializer: Serializer | None = None,   # Serializer customizado
    metrics: CacheMetrics | None = None,    # Coletor de métricas
)
```

### 3.2 Exemplos de Uso

```python
from dapr_state_cache import cacheable, InMemoryMetrics

# Uso simples
@cacheable
def get_user(user_id: int) -> dict:
    return db.query(user_id)

# Com configuração
@cacheable(store_name="users", ttl_seconds=300)
async def get_user_async(user_id: int) -> dict:
    return await db.query(user_id)

# Com métricas
metrics = InMemoryMetrics()

@cacheable(store_name="cache", metrics=metrics)
def compute_expensive(x: int) -> int:
    return x ** 2

# Invalidação
get_user.invalidate(user_id=123)
await get_user_async.invalidate_async(user_id=456)
```

### 3.3 Comportamento Automático

- **Detecção Sync/Async**: O decorator detecta automaticamente se a função é síncrona ou assíncrona
- **Funções Sync**: Usa `httpx.Client` para operações de cache
- **Funções Async**: Usa `httpx.AsyncClient` para operações de cache
- **Sem ThreadPool**: Não há conversão entre contextos - cada modo usa seu próprio cliente HTTP

## 4. Serialização

### 4.1 MsgPackSerializer (Padrão)

A biblioteca usa MsgPack como formato de serialização padrão por ser:

- **Eficiente**: Formato binário compacto
- **Rápido**: Serialização/deserialização otimizadas
- **Compatível**: Suporta tipos Python nativos

### 4.2 Tipos Suportados

| Tipo Python | Suporte |
|-------------|---------|
| `None` | ✅ |
| `bool` | ✅ |
| `int` | ✅ |
| `float` | ✅ |
| `str` | ✅ |
| `bytes` | ✅ |
| `list` | ✅ |
| `dict` | ✅ |

### 4.3 Extensibilidade

Implemente o Protocol `Serializer` para usar outros formatos:

```python
from dapr_state_cache import Serializer

class JsonSerializer:
    def serialize(self, data: Any) -> bytes:
        return json.dumps(data).encode()

    def deserialize(self, data: bytes) -> Any:
        return json.loads(data.decode())

@cacheable(serializer=JsonSerializer())
def my_function():
    pass
```

## 5. Geração de Chaves

### 5.1 Formato da Chave

```text
{prefix}:{module}.{qualname}:{hash}
```

Exemplo: `cache:myapp.services.get_user:a1b2c3d4e5f6g7h8`

### 5.2 Algoritmo

1. Obtém caminho completo da função (`module.qualname`)
2. Filtra `self`/`cls` de métodos (cache compartilhado entre instâncias)
3. Serializa argumentos para JSON
4. Calcula SHA256 truncado para 16 caracteres

### 5.3 Key Builder Customizado

```python
from dapr_state_cache import KeyBuilder

class TenantKeyBuilder:
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id

    def build_key(self, func, args, kwargs) -> str:
        return f"{self.tenant_id}:{func.__name__}:{hash(args)}"

@cacheable(key_builder=TenantKeyBuilder("tenant-123"))
def get_data():
    pass
```

## 6. Deduplicação (Thundering Herd Protection)

### 6.1 Comportamento

Quando múltiplas chamadas concorrentes tentam computar o mesmo valor (cache miss):

1. Apenas a primeira computação é executada
2. Demais chamadas aguardam o resultado
3. Resultado é compartilhado com todas as chamadas

### 6.2 Benefícios

- Evita computações redundantes
- Reduz carga no sistema em picos de tráfego
- Proteção automática sem configuração

## 7. Observabilidade com OpenTelemetry

### 7.1 Métricas Disponíveis

| Métrica | Tipo | Descrição |
|---------|------|-----------|
| `cache.hits` | Counter | Número de cache hits |
| `cache.misses` | Counter | Número de cache misses |
| `cache.writes` | Counter | Número de escritas |
| `cache.errors` | Counter | Número de erros |
| `cache.latency` | Histogram | Latência das operações |
| `cache.size` | Histogram | Tamanho dos dados |

### 7.2 Uso com OpenTelemetry

```python
from dapr_state_cache import cacheable, OpenTelemetryMetrics
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider

# Configura OpenTelemetry
metrics.set_meter_provider(MeterProvider())

# Usa métricas
otel_metrics = OpenTelemetryMetrics()

@cacheable(metrics=otel_metrics)
def my_function():
    pass
```

### 7.3 Métricas em Memória (Desenvolvimento)

```python
from dapr_state_cache import cacheable, InMemoryMetrics

metrics = InMemoryMetrics()

@cacheable(metrics=metrics)
def my_function():
    pass

# Análise
stats = metrics.get_stats()
print(f"Hit ratio: {stats.hit_ratio:.2%}")
print(f"Avg latency: {stats.avg_hit_latency_ms:.1f}ms")

# Top keys
top = metrics.get_top_keys(by="hits", limit=10)
```

## 8. Tratamento de Erros

### 8.1 Política Best-Effort

Erros de cache não quebram o fluxo da aplicação:

- **Falha de Conexão**: Log + executa função sem cache
- **Falha de Serialização**: Log + executa função sem cache
- **Timeout**: Log + executa função sem cache

### 8.2 Exceções

| Exceção | Descrição |
|---------|-----------|
| `CacheError` | Erro base |
| `CacheConnectionError` | Falha ao conectar com sidecar |
| `CacheSerializationError` | Falha de serialização |
| `CacheKeyError` | Chave inválida ou vazia |

## 9. Backend HTTP

### 9.1 Configuração

```python
from dapr_state_cache import DaprStateBackend

# Configuração padrão (localhost:3500)
backend = DaprStateBackend("my-store")

# Configuração customizada
backend = DaprStateBackend(
    store_name="my-store",
    timeout=10.0,
    dapr_url="http://dapr-sidecar:3500"
)
```

### 9.2 Variáveis de Ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `DAPR_HTTP_HOST` | `127.0.0.1` | Host do sidecar |
| `DAPR_HTTP_PORT` | `3500` | Porta do sidecar |

## 10. Dependências

```toml
[project]
dependencies = [
    "httpx>=0.27.0",
    "msgpack>=1.1.1",
    "opentelemetry-api>=1.20.0",
]
```

## 11. Compatibilidade

| Componente | Versão Mínima |
|------------|---------------|
| Python | 3.12+ |
| Dapr | 1.10+ |

### 11.1 State Stores Compatíveis

Qualquer state store Dapr com suporte a TTL:

- Redis (recomendado)
- MongoDB
- PostgreSQL
- Azure Cosmos DB
- Memory (apenas desenvolvimento)

## 12. Migração da v0.3.x

### 12.1 Mudanças Breaking

- Removido suporte a `JsonSerializer` e `PickleSerializer`
- Removido `SyncAsyncBridge` e `ThreadPoolExecutor`
- Removido suporte a criptografia Dapr (será readicionado em versão futura)
- Removida invalidação por prefixo

### 12.2 Novas Features

- Backend HTTP direto (sem SDK Dapr)
- Métricas OpenTelemetry nativas
- API simplificada

### 12.3 Guia de Migração

```python
# Antes (v0.3.x)
from dapr_state_cache import cacheable, JsonSerializer

@cacheable(
    store_name="cache",
    serializer=JsonSerializer(),
    use_dapr_crypto=True,
)
def my_func():
    pass

# Depois (v0.4.0)
from dapr_state_cache import cacheable

@cacheable(store_name="cache")
def my_func():
    pass
# MsgPackSerializer é o padrão
# Criptografia será readicionada em versão futura
```
