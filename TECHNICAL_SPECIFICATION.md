# Technical Specification - dapr-state-cache v0.4.0

## 1. Overview and Objectives

### 1.1 Library Purpose

The `dapr-state-cache` library is a transparent caching solution based on Dapr State Store, designed for simplicity, high performance, and ease of use. The library implements a caching system that works with synchronous and asynchronous functions, instance methods, and standalone functions.

### 1.2 Design Principles

- **Simplicity**: Minimal and intuitive API
- **Transparency**: Decorator does not modify function behavior
- **Performance**: Direct HTTP communication with Dapr sidecar
- **Flexibility**: Native sync and async support without ThreadPool
- **Observability**: OpenTelemetry integration

### 1.3 Main Use Cases

- **API Caching**: Cache external API responses with configurable TTL
- **Computational Data Caching**: Cache results of expensive operations
- **Configuration Caching**: Cache application configurations
- **Service Method Caching**: Cache service class methods

## 2. System Architecture

### 2.1 File Structure

```text
dapr_state_cache/
├── __init__.py           # Public exports
├── decorator.py          # @cacheable decorator
├── backend.py            # DaprStateBackend (direct HTTP)
├── serializer.py         # MsgPackSerializer
├── key_builder.py        # DefaultKeyBuilder
├── deduplication.py      # DeduplicationManager
├── metrics.py            # OpenTelemetry metrics
├── protocols.py          # Protocols for extensibility
└── exceptions.py         # Exceptions
```

### 2.2 Data Flow

1. **Key Generation**: `prefix:module.function:hash(args)`
2. **Cache Lookup**: HTTP lookup in Dapr State Store
3. **Cache Hit**: Returns deserialized data (MsgPack)
4. **Cache Miss**: Deduplicates concurrent calls → Executes function → Serializes → Stores
5. **Cache Write**: Stores with TTL via `ttlInSeconds` metadata

### 2.3 Dapr Communication

The library uses the [Dapr State HTTP API](https://docs.dapr.io/reference/api/state_api/) directly:

- `GET /v1.0/state/{storename}/{key}` - Get value
- `POST /v1.0/state/{storename}` - Save value with TTL
- `DELETE /v1.0/state/{storename}/{key}` - Delete value

**Benefits of this approach**:

- No dependency on Dapr Python SDK
- Full control over sync/async via httpx
- Compatible with any async object (DB connections, HTTP sessions)

## 3. @cacheable Decorator API

### 3.1 Parameters

```python
@cacheable(
    store_name: str = "cache",           # Dapr state store name
    ttl_seconds: int = 3600,             # TTL in seconds
    key_prefix: str = "cache",           # Key prefix
    key_builder: KeyBuilder | None = None,  # Custom key builder
    serializer: Serializer | None = None,   # Custom serializer
    metrics: CacheMetrics | None = None,    # Metrics collector
)
```

### 3.2 Usage Examples

```python
from dapr_state_cache import cacheable, InMemoryMetrics

# Simple usage
@cacheable
def get_user(user_id: int) -> dict:
    return db.query(user_id)

# With configuration
@cacheable(store_name="users", ttl_seconds=300)
async def get_user_async(user_id: int) -> dict:
    return await db.query(user_id)

# With metrics
metrics = InMemoryMetrics()

@cacheable(store_name="cache", metrics=metrics)
def compute_expensive(x: int) -> int:
    return x ** 2

# Invalidation
get_user.invalidate(user_id=123)
await get_user_async.invalidate_async(user_id=456)
```

### 3.3 Automatic Behavior

- **Sync/Async Detection**: The decorator automatically detects if the function is synchronous or asynchronous
- **Sync Functions**: Uses `httpx.Client` for cache operations
- **Async Functions**: Uses `httpx.AsyncClient` for cache operations
- **No ThreadPool**: No context conversion - each mode uses its own HTTP client

## 4. Serialization

### 4.1 MsgPackSerializer (Default)

The library uses MsgPack as the default serialization format because it is:

- **Efficient**: Compact binary format
- **Fast**: Optimized serialization/deserialization
- **Compatible**: Supports native Python types

### 4.2 Supported Types

| Python Type | Support |
|-------------|---------|
| `None` | Yes |
| `bool` | Yes |
| `int` | Yes |
| `float` | Yes |
| `str` | Yes |
| `bytes` | Yes |
| `list` | Yes |
| `dict` | Yes |

### 4.3 Extensibility

Implement the `Serializer` Protocol to use other formats:

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

## 5. Key Generation

### 5.1 Key Format

```text
{prefix}:{module}.{qualname}:{hash}
```

Example: `cache:myapp.services.get_user:a1b2c3d4e5f6g7h8`

### 5.2 Algorithm

1. Gets full function path (`module.qualname`)
2. Filters `self`/`cls` from methods (cache shared between instances)
3. Serializes arguments to JSON
4. Calculates truncated SHA256 (16 characters)

### 5.3 Custom Key Builder

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

## 6. Deduplication (Thundering Herd Protection)

### 6.1 Behavior

When multiple concurrent calls try to compute the same value (cache miss):

1. Only the first computation is executed
2. Other calls wait for the result
3. Result is shared with all calls

### 6.2 Benefits

- Avoids redundant computations
- Reduces system load during traffic spikes
- Automatic protection without configuration

## 7. Observability with OpenTelemetry

### 7.1 Available Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `cache.hits` | Counter | Number of cache hits |
| `cache.misses` | Counter | Number of cache misses |
| `cache.writes` | Counter | Number of writes |
| `cache.errors` | Counter | Number of errors |
| `cache.latency` | Histogram | Operation latency |
| `cache.size` | Histogram | Data size |

### 7.2 Using with OpenTelemetry

```python
from dapr_state_cache import cacheable, OpenTelemetryMetrics
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider

# Configure OpenTelemetry
metrics.set_meter_provider(MeterProvider())

# Use metrics
otel_metrics = OpenTelemetryMetrics()

@cacheable(metrics=otel_metrics)
def my_function():
    pass
```

### 7.3 In-Memory Metrics (Development)

```python
from dapr_state_cache import cacheable, InMemoryMetrics

metrics = InMemoryMetrics()

@cacheable(metrics=metrics)
def my_function():
    pass

# Analysis
stats = metrics.get_stats()
print(f"Hit ratio: {stats.hit_ratio:.2%}")
print(f"Avg latency: {stats.avg_hit_latency_ms:.1f}ms")

# Top keys
top = metrics.get_top_keys(by="hits", limit=10)
```

## 8. Error Handling

### 8.1 Best-Effort Policy

Cache errors do not break the application flow:

- **Connection Failure**: Log + execute function without cache
- **Serialization Failure**: Log + execute function without cache
- **Timeout**: Log + execute function without cache

### 8.2 Exceptions

| Exception | Description |
|-----------|-------------|
| `CacheError` | Base error |
| `CacheConnectionError` | Failed to connect to sidecar |
| `CacheSerializationError` | Serialization failure |
| `CacheKeyError` | Invalid or empty key |

## 9. HTTP Backend

### 9.1 Configuration

```python
from dapr_state_cache import DaprStateBackend

# Default configuration (localhost:3500)
backend = DaprStateBackend("my-store")

# Custom configuration
backend = DaprStateBackend(
    store_name="my-store",
    timeout=10.0,
    dapr_url="http://dapr-sidecar:3500"
)
```

### 9.2 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DAPR_HTTP_HOST` | `127.0.0.1` | Sidecar host |
| `DAPR_HTTP_PORT` | `3500` | Sidecar port |

## 10. Dependencies

```toml
[project]
dependencies = [
    "httpx>=0.27.0",
    "msgpack>=1.1.1",
    "opentelemetry-api>=1.20.0",
]
```

## 11. Compatibility

| Component | Minimum Version |
|-----------|-----------------|
| Python | 3.12+ |
| Dapr | 1.10+ |

### 11.1 Compatible State Stores

Any Dapr state store with TTL support:

- Redis (recommended)
- MongoDB
- PostgreSQL
- Azure Cosmos DB
- Memory (development only)

## 12. Migration from v0.3.x

### 12.1 Breaking Changes

- Removed support for `JsonSerializer` and `PickleSerializer`
- Removed `SyncAsyncBridge` and `ThreadPoolExecutor`
- Removed Dapr encryption support (will be re-added in future version)
- Removed prefix invalidation

### 12.2 New Features

- Direct HTTP backend (no Dapr SDK)
- Native OpenTelemetry metrics
- Simplified API

### 12.3 Migration Guide

```python
# Before (v0.3.x)
from dapr_state_cache import cacheable, JsonSerializer

@cacheable(
    store_name="cache",
    serializer=JsonSerializer(),
    use_dapr_crypto=True,
)
def my_func():
    pass

# After (v0.4.0)
from dapr_state_cache import cacheable

@cacheable(store_name="cache")
def my_func():
    pass
# MsgPackSerializer is the default
# Encryption will be re-added in future version
```

