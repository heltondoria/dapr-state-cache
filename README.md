# dapr-state-cache

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-0.5.0-green.svg)](https://github.com/heltondoria/dapr-state-cache)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Coverage](https://img.shields.io/badge/coverage-90%25+-brightgreen.svg)](htmlcov/index.html)

**High-performance transparent cache for Dapr applications**

A modern Python library that adds transparent caching to functions using Dapr State Store, with native support for synchronous and asynchronous operations.

## Features

- **Simple decorator** - Add caching with a single line using `@cacheable`
- **Native Sync and Async** - Automatic function type detection, no ThreadPool
- **Direct HTTP backend** - Direct communication with Dapr sidecar via httpx
- **Efficient serialization** - MsgPack as default for maximum performance
- **OpenTelemetry metrics** - Complete observability out-of-the-box
- **Thundering Herd Protection** - Automatic deduplication of concurrent calls
- **Extensible via Protocols** - Customize serialization, keys, and metrics
- **Type-safe** - Fully typed with mypy and pyright support

## Installation

### With pip

```bash
pip install dapr-state-cache
```

### With uv (recommended)

```bash
uv add dapr-state-cache
```

### Development dependencies

```bash
uv add dapr-state-cache --dev
# or
pip install dapr-state-cache[dev]
```

## Quick Start

### Basic example

```python
from dapr_state_cache import cacheable

# Synchronous function with cache
@cacheable(store_name="cache", ttl_seconds=300)
def get_user(user_id: int) -> dict:
    # Expensive operation - executed only on cache miss
    return database.query(user_id)

# Asynchronous function with cache
@cacheable(store_name="cache", ttl_seconds=300)
async def get_user_async(user_id: int) -> dict:
    return await database.query_async(user_id)

# Usage - cache is transparent
user = get_user(123)  # Cache miss - executes query
user = get_user(123)  # Cache hit - returns from cache

# Manual invalidation
get_user.invalidate(123)
await get_user_async.invalidate_async(456)
```

### Usage without parentheses

```python
@cacheable  # Uses default values: store_name="cache", ttl_seconds=3600
def simple_function(x: int) -> int:
    return x * 2
```

### With metrics

```python
from dapr_state_cache import cacheable, InMemoryMetrics

metrics = InMemoryMetrics()

@cacheable(store_name="cache", metrics=metrics)
def compute_expensive(x: int) -> int:
    return x ** 2

# After some calls
stats = metrics.get_stats()
print(f"Hit ratio: {stats.hit_ratio:.2%}")
print(f"Avg hit latency: {stats.avg_hit_latency_ms:.1f}ms")
```

## Dapr Environment Configuration

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DAPR_HTTP_HOST` | `127.0.0.1` | Dapr sidecar host |
| `DAPR_HTTP_PORT` | `3500` | Dapr sidecar port |

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

### Compatible State Stores

Any Dapr state store with TTL support:

| Store | Recommendation |
|-------|----------------|
| Redis | Production (recommended) |
| MongoDB | Production |
| PostgreSQL | Production |
| Azure Cosmos DB | Production |
| In-Memory | Development only |

## Detailed Documentation

### @cacheable decorator parameters

```python
@cacheable(
    store_name: str = "cache",           # Dapr state store name
    ttl_seconds: int = 3600,             # TTL in seconds (1 hour default)
    key_prefix: str = "cache",           # Cache key prefix
    key_builder: KeyBuilder | None = None,  # Custom key builder
    serializer: Serializer | None = None,   # Custom serializer
    metrics: CacheMetrics | None = None,    # Metrics collector
)
```

### Serialization

The library uses **MsgPack** as the default serialization format because it is:

- **Compact** - Binary format smaller than JSON
- **Fast** - Optimized serialization/deserialization
- **Compatible** - Supports native Python types

#### Supported types

| Python Type | Support |
|-------------|---------|
| `None`, `bool`, `int`, `float`, `str` | Yes |
| `bytes` | Yes |
| `list`, `tuple`, `dict` | Yes |

### Key Generation

The default key format is:

```text
{prefix}:{module}.{qualname}:{hash}
```

Example: `cache:myapp.services.get_user:a1b2c3d4e5f6g7h8`

#### Algorithm

1. Gets full function path (`module.qualname`)
2. Filters `self`/`cls` from methods (cache shared between instances)
3. Serializes arguments to JSON
4. Calculates truncated SHA256 (16 characters)

### Metrics

The library offers three metrics collectors:

#### NoOpMetrics (default)

Does not collect metrics - zero overhead.

```python
@cacheable(store_name="cache")  # Implicit NoOpMetrics
def my_function():
    pass
```

#### InMemoryMetrics

Collects metrics in memory - ideal for development and testing.

```python
from dapr_state_cache import cacheable, InMemoryMetrics

metrics = InMemoryMetrics()

@cacheable(store_name="cache", metrics=metrics)
def my_function():
    pass

# Aggregated statistics
stats = metrics.get_stats()
print(f"Hits: {stats.hits}")
print(f"Misses: {stats.misses}")
print(f"Hit ratio: {stats.hit_ratio:.2%}")

# Top most accessed keys
top_keys = metrics.get_top_keys(by="hits", limit=10)

# Statistics per key
key_stats = metrics.get_key_stats("cache:module.func:abc123")
```

#### OpenTelemetryMetrics

OpenTelemetry integration for production.

```python
from dapr_state_cache import cacheable, OpenTelemetryMetrics
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider

# Configure OpenTelemetry
metrics.set_meter_provider(MeterProvider())

otel_metrics = OpenTelemetryMetrics()

@cacheable(store_name="cache", metrics=otel_metrics)
def my_function():
    pass
```

**Exported metrics:**

| Metric | Type | Description |
|--------|------|-------------|
| `cache.hits` | Counter | Number of cache hits |
| `cache.misses` | Counter | Number of cache misses |
| `cache.writes` | Counter | Number of writes |
| `cache.errors` | Counter | Number of errors |
| `cache.latency` | Histogram | Operation latency (seconds) |
| `cache.size` | Histogram | Data size (bytes) |

### Deduplication (Thundering Herd Protection)

When multiple concurrent calls try to compute the same value (cache miss):

1. Only the **first computation** is executed
2. Other calls **wait** for the result
3. Result is **shared** with all calls

```python
import asyncio
from dapr_state_cache import cacheable

@cacheable(store_name="cache", ttl_seconds=60)
async def expensive_operation(key: str) -> dict:
    await asyncio.sleep(1)  # Simulates slow operation
    return {"result": key}

# 100 concurrent calls - only 1 actual execution
results = await asyncio.gather(*[
    expensive_operation("same-key")
    for _ in range(100)
])
```

### Error Handling

The library follows a **best-effort** policy - cache errors do not break the flow:

| Scenario | Behavior |
|----------|----------|
| Connection failure | Log warning + execute function |
| Serialization failure | Log warning + execute function |
| Timeout | Log warning + execute function |

#### Available exceptions

```python
from dapr_state_cache import (
    CacheError,              # Base error
    CacheConnectionError,    # Failed to connect to sidecar
    CacheSerializationError, # Serialization failure
    CacheKeyError,           # Invalid or empty key
)
```

## Extensibility

The library uses **Protocols** to allow custom implementations.

### Custom Serializer

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

### Custom KeyBuilder

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

### Custom Metrics

```python
from dapr_state_cache import cacheable

class PrometheusMetrics:
    def record_hit(self, key: str, latency: float) -> None:
        # Prometheus integration
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

### Main Classes

| Class | Description |
|-------|-------------|
| `cacheable` | Main decorator to add caching |
| `CacheableWrapper` | Wrapper returned by the decorator |
| `DaprStateBackend` | Dapr communication backend |
| `MsgPackSerializer` | MsgPack serializer (default) |
| `DefaultKeyBuilder` | Key builder (default) |
| `DeduplicationManager` | Deduplication manager |

### Metrics

| Class | Description |
|-------|-------------|
| `NoOpMetrics` | Null collector (default) |
| `InMemoryMetrics` | In-memory collector |
| `OpenTelemetryMetrics` | OpenTelemetry integration |
| `CacheStats` | Aggregated statistics |
| `KeyStats` | Per-key statistics |

### Exceptions

| Exception | Description |
|-----------|-------------|
| `CacheError` | Base error |
| `CacheConnectionError` | Connection failure |
| `CacheSerializationError` | Serialization failure |
| `CacheKeyError` | Invalid key |

### Protocols

| Protocol | Description |
|----------|-------------|
| `SerializerProtocol` | Interface for serializers |
| `KeyBuilder` | Interface for key builders |
| `CacheMetricsProtocol` | Interface for metrics collectors |

## Development

### Environment setup

```bash
# Clone the repository
git clone https://github.com/heltondoria/dapr-state-cache.git
cd dapr-state-cache

# Install development dependencies
uv sync --dev
# or
pip install -e ".[dev]"
```

### Makefile commands

#### Quick development

```bash
make check      # Lint + format + types (< 10s)
make fix        # Auto-fix issues
```

#### Complete validation

```bash
make validate   # Complete analysis + tests (< 60s)
make health     # Full project assessment
```

#### Tests

```bash
make test-quick     # Quick unit tests
make test-coverage  # Tests with coverage (90%+ required)
make test-all       # All tests
```

#### Quality analysis

```bash
make lint       # Linting with ruff
make type-check # Type checking with pyright
make radon      # Complexity analysis
make vulture    # Dead code detection
make security   # Security analysis
make quality    # Complete analysis
```

### Quality standards

The project follows **Clean Code** and **TDD** principles:

| Metric | Requirement |
|--------|-------------|
| Line coverage | 90%+ |
| Branch coverage | 90%+ |
| Cyclomatic complexity | ≤5 per method |
| Method size | ≤20 lines |
| Dead code | 0% |
| Type errors | 0 |
| Lint errors | 0 |

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a branch for your feature (`git checkout -b feature/amazing-feature`)
3. Run `make validate` before committing
4. Commit following [Conventional Commits](https://www.conventionalcommits.org/)
5. Open a Pull Request

### PR requirements

- All tests passing
- Code coverage maintained at 90%+
- Zero lint and type errors
- Documentation updated

## Compatibility

| Component | Minimum version |
|-----------|-----------------|
| Python | 3.12+ |
| Dapr | 1.10+ |

## License

This project is licensed under the [MIT License](LICENSE).

## Author

**Helton Dória** - [helton.doria@gmail.com](mailto:helton.doria@gmail.com)

---

Made with Python and Dapr
