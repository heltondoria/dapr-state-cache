# dapr-state-cache

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-0.5.0-green.svg)](https://github.com/heltondoria/dapr-state-cache)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Coverage](https://img.shields.io/badge/coverage-90%25+-brightgreen.svg)](htmlcov/index.html)

**Cache transparente de alta performance para aplicações Dapr**

Uma biblioteca Python moderna que adiciona cache transparente a funções usando Dapr State Store, com suporte nativo a operações síncronas e assíncronas.

## Features

- **Decorator simples** - Adicione cache com uma única linha usando `@cacheable`
- **Sync e Async nativos** - Detecção automática do tipo de função, sem ThreadPool
- **Backend HTTP direto** - Comunicação direta com sidecar Dapr via httpx
- **Serialização eficiente** - MsgPack como padrão para máxima performance
- **Métricas OpenTelemetry** - Observabilidade completa out-of-the-box
- **Thundering Herd Protection** - Deduplicação automática de chamadas concorrentes
- **Extensível via Protocols** - Customize serialização, chaves e métricas
- **Type-safe** - Totalmente tipado com suporte a mypy e pyright

## Instalação

### Com pip

```bash
pip install dapr-state-cache
```

### Com uv (recomendado)

```bash
uv add dapr-state-cache
```

### Dependências de desenvolvimento

```bash
uv add dapr-state-cache --dev
# ou
pip install dapr-state-cache[dev]
```

## Quick Start

### Exemplo básico

```python
from dapr_state_cache import cacheable

# Função síncrona com cache
@cacheable(store_name="cache", ttl_seconds=300)
def get_user(user_id: int) -> dict:
    # Operação custosa - executada apenas no cache miss
    return database.query(user_id)

# Função assíncrona com cache
@cacheable(store_name="cache", ttl_seconds=300)
async def get_user_async(user_id: int) -> dict:
    return await database.query_async(user_id)

# Uso - cache é transparente
user = get_user(123)  # Cache miss - executa query
user = get_user(123)  # Cache hit - retorna do cache

# Invalidação manual
get_user.invalidate(123)
await get_user_async.invalidate_async(456)
```

### Uso sem parênteses

```python
@cacheable  # Usa valores padrão: store_name="cache", ttl_seconds=3600
def simple_function(x: int) -> int:
    return x * 2
```

### Com métricas

```python
from dapr_state_cache import cacheable, InMemoryMetrics

metrics = InMemoryMetrics()

@cacheable(store_name="cache", metrics=metrics)
def compute_expensive(x: int) -> int:
    return x ** 2

# Após algumas chamadas
stats = metrics.get_stats()
print(f"Hit ratio: {stats.hit_ratio:.2%}")
print(f"Avg hit latency: {stats.avg_hit_latency_ms:.1f}ms")
```

## Configuração do Ambiente Dapr

### Variáveis de ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `DAPR_HTTP_HOST` | `127.0.0.1` | Host do sidecar Dapr |
| `DAPR_HTTP_PORT` | `3500` | Porta do sidecar Dapr |

### Component YAML (Redis)

```yaml
apiVersion: dapr.io/v1alpha1
kind: Component
metadata:
  name: cache
spec:
  type: state.redis
  version: v1
  metadata:
    - name: redisHost
      value: localhost:6379
    - name: redisPassword
      value: ""
    - name: actorStateStore
      value: "false"
```

### State Stores compatíveis

Qualquer state store Dapr com suporte a TTL:

| Store | Recomendação |
|-------|--------------|
| Redis | Produção (recomendado) |
| MongoDB | Produção |
| PostgreSQL | Produção |
| Azure Cosmos DB | Produção |
| In-Memory | Apenas desenvolvimento |

## Documentação Detalhada

### Parâmetros do decorator @cacheable

```python
@cacheable(
    store_name: str = "cache",           # Nome do state store Dapr
    ttl_seconds: int = 3600,             # TTL em segundos (1 hora padrão)
    key_prefix: str = "cache",           # Prefixo das chaves de cache
    key_builder: KeyBuilder | None = None,  # Construtor de chaves customizado
    serializer: Serializer | None = None,   # Serializer customizado
    metrics: CacheMetrics | None = None,    # Coletor de métricas
)
```

### Serialização

A biblioteca usa **MsgPack** como formato de serialização padrão por ser:

- **Compacto** - Formato binário menor que JSON
- **Rápido** - Serialização/deserialização otimizadas
- **Compatível** - Suporta tipos Python nativos

#### Tipos suportados

| Tipo Python | Suporte |
|-------------|---------|
| `None`, `bool`, `int`, `float`, `str` | Sim |
| `bytes` | Sim |
| `list`, `tuple`, `dict` | Sim |

### Geração de chaves

O formato padrão das chaves é:

```text
{prefix}:{module}.{qualname}:{hash}
```

Exemplo: `cache:myapp.services.get_user:a1b2c3d4e5f6g7h8`

#### Algoritmo

1. Obtém caminho completo da função (`module.qualname`)
2. Filtra `self`/`cls` de métodos (cache compartilhado entre instâncias)
3. Serializa argumentos para JSON
4. Calcula SHA256 truncado (16 caracteres)

### Métricas

A biblioteca oferece três coletores de métricas:

#### NoOpMetrics (padrão)

Não coleta métricas - zero overhead.

```python
@cacheable(store_name="cache")  # NoOpMetrics implícito
def my_function():
    pass
```

#### InMemoryMetrics

Coleta métricas em memória - ideal para desenvolvimento e testes.

```python
from dapr_state_cache import cacheable, InMemoryMetrics

metrics = InMemoryMetrics()

@cacheable(store_name="cache", metrics=metrics)
def my_function():
    pass

# Estatísticas agregadas
stats = metrics.get_stats()
print(f"Hits: {stats.hits}")
print(f"Misses: {stats.misses}")
print(f"Hit ratio: {stats.hit_ratio:.2%}")

# Top chaves mais acessadas
top_keys = metrics.get_top_keys(by="hits", limit=10)

# Estatísticas por chave
key_stats = metrics.get_key_stats("cache:module.func:abc123")
```

#### OpenTelemetryMetrics

Integração com OpenTelemetry para produção.

```python
from dapr_state_cache import cacheable, OpenTelemetryMetrics
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider

# Configura OpenTelemetry
metrics.set_meter_provider(MeterProvider())

otel_metrics = OpenTelemetryMetrics()

@cacheable(store_name="cache", metrics=otel_metrics)
def my_function():
    pass
```

**Métricas exportadas:**

| Métrica | Tipo | Descrição |
|---------|------|-----------|
| `cache.hits` | Counter | Número de cache hits |
| `cache.misses` | Counter | Número de cache misses |
| `cache.writes` | Counter | Número de escritas |
| `cache.errors` | Counter | Número de erros |
| `cache.latency` | Histogram | Latência das operações (segundos) |
| `cache.size` | Histogram | Tamanho dos dados (bytes) |

### Deduplicação (Thundering Herd Protection)

Quando múltiplas chamadas concorrentes tentam computar o mesmo valor (cache miss):

1. Apenas a **primeira computação** é executada
2. Demais chamadas **aguardam** o resultado
3. Resultado é **compartilhado** com todas as chamadas

```python
import asyncio
from dapr_state_cache import cacheable

@cacheable(store_name="cache", ttl_seconds=60)
async def expensive_operation(key: str) -> dict:
    await asyncio.sleep(1)  # Simula operação lenta
    return {"result": key}

# 100 chamadas concorrentes - apenas 1 execução real
results = await asyncio.gather(*[
    expensive_operation("same-key")
    for _ in range(100)
])
```

### Tratamento de erros

A biblioteca segue uma política **best-effort** - erros de cache não quebram o fluxo:

| Cenário | Comportamento |
|---------|---------------|
| Falha de conexão | Log warning + executa função |
| Falha de serialização | Log warning + executa função |
| Timeout | Log warning + executa função |

#### Exceções disponíveis

```python
from dapr_state_cache import (
    CacheError,              # Erro base
    CacheConnectionError,    # Falha ao conectar com sidecar
    CacheSerializationError, # Falha de serialização
    CacheKeyError,           # Chave inválida ou vazia
)
```

## Extensibilidade

A biblioteca usa **Protocols** para permitir implementações customizadas.

### Serializer customizado

```python
import json
from typing import Any
from dapr_state_cache import cacheable

class JsonSerializer:
    def serialize(self, data: Any) -> bytes:
        return json.dumps(data).encode("utf-8")

    def deserialize(self, data: bytes) -> Any:
        return json.loads(data.decode("utf-8"))

@cacheable(store_name="cache", serializer=JsonSerializer())
def my_function():
    pass
```

### KeyBuilder customizado

```python
from collections.abc import Callable
from typing import Any
from dapr_state_cache import cacheable

class TenantKeyBuilder:
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id

    def build_key(
        self,
        func: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> str:
        return f"{self.tenant_id}:{func.__name__}:{hash(args)}"

@cacheable(store_name="cache", key_builder=TenantKeyBuilder("tenant-123"))
def tenant_function():
    pass
```

### Metrics customizado

```python
from dapr_state_cache import cacheable

class PrometheusMetrics:
    def record_hit(self, key: str, latency: float) -> None:
        # Integração com Prometheus
        cache_hits_total.labels(key=key).inc()

    def record_miss(self, key: str, latency: float) -> None:
        cache_misses_total.labels(key=key).inc()

    def record_write(self, key: str, size: int) -> None:
        cache_writes_total.labels(key=key).inc()

    def record_error(self, key: str, error: Exception) -> None:
        cache_errors_total.labels(key=key, error=type(error).__name__).inc()

@cacheable(store_name="cache", metrics=PrometheusMetrics())
def my_function():
    pass
```

## API Reference

### Classes principais

| Classe | Descrição |
|--------|-----------|
| `cacheable` | Decorator principal para adicionar cache |
| `CacheableWrapper` | Wrapper retornado pelo decorator |
| `DaprStateBackend` | Backend de comunicação com Dapr |
| `MsgPackSerializer` | Serializer MsgPack (padrão) |
| `DefaultKeyBuilder` | Construtor de chaves (padrão) |
| `DeduplicationManager` | Gerenciador de deduplicação |

### Métricas

| Classe | Descrição |
|--------|-----------|
| `NoOpMetrics` | Coletor nulo (padrão) |
| `InMemoryMetrics` | Coletor em memória |
| `OpenTelemetryMetrics` | Integração OpenTelemetry |
| `CacheStats` | Estatísticas agregadas |
| `KeyStats` | Estatísticas por chave |

### Exceções

| Exceção | Descrição |
|---------|-----------|
| `CacheError` | Erro base |
| `CacheConnectionError` | Falha de conexão |
| `CacheSerializationError` | Falha de serialização |
| `CacheKeyError` | Chave inválida |

### Protocols

| Protocol | Descrição |
|----------|-----------|
| `SerializerProtocol` | Interface para serializers |
| `KeyBuilder` | Interface para key builders |
| `CacheMetricsProtocol` | Interface para coletores de métricas |

## Desenvolvimento

### Configuração do ambiente

```bash
# Clone o repositório
git clone https://github.com/heltondoria/dapr-state-cache.git
cd dapr-state-cache

# Instale dependências de desenvolvimento
uv sync --dev
# ou
pip install -e ".[dev]"
```

### Comandos do Makefile

#### Desenvolvimento rápido

```bash
make check      # Lint + format + types (< 10s)
make fix        # Auto-fix de problemas
```

#### Validação completa

```bash
make validate   # Análise completa + testes (< 60s)
make health     # Assessment completo do projeto
```

#### Testes

```bash
make test-quick     # Testes unitários rápidos
make test-coverage  # Testes com cobertura (90%+ requerido)
make test-all       # Todos os testes
```

#### Análise de qualidade

```bash
make lint       # Linting com ruff
make type-check # Verificação de tipos com pyright
make radon      # Análise de complexidade
make vulture    # Detecção de código morto
make security   # Análise de segurança
make quality    # Análise completa
```

### Padrões de qualidade

O projeto segue princípios de **Clean Code** e **TDD**:

| Métrica | Requisito |
|---------|-----------|
| Cobertura de linhas | 90%+ |
| Cobertura de branches | 90%+ |
| Complexidade ciclomática | ≤5 por método |
| Tamanho de método | ≤20 linhas |
| Código morto | 0% |
| Erros de tipo | 0 |
| Erros de lint | 0 |

## Contribuição

Contribuições são bem-vindas! Por favor:

1. Faça fork do repositório
2. Crie uma branch para sua feature (`git checkout -b feature/amazing-feature`)
3. Execute `make validate` antes de commitar
4. Faça commit seguindo [Conventional Commits](https://www.conventionalcommits.org/)
5. Abra um Pull Request

### Requisitos para PR

- Todos os testes passando
- Cobertura de código mantida em 90%+
- Zero erros de lint e tipo
- Documentação atualizada

## Compatibilidade

| Componente | Versão mínima |
|------------|---------------|
| Python | 3.12+ |
| Dapr | 1.10+ |

## Licença

Este projeto está licenciado sob a [MIT License](LICENSE).

## Autor

**Helton Dória** - [helton.doria@gmail.com](mailto:helton.doria@gmail.com)

---

Feito com Python e Dapr
