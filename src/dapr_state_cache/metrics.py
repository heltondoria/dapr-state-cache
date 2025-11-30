"""Métricas de cache usando OpenTelemetry."""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Protocol

from opentelemetry import metrics as otel_metrics

logger = logging.getLogger(__name__)


class CacheMetrics(Protocol):
    """Protocol para coletores de métricas."""

    def record_hit(self, key: str, latency: float) -> None:
        """Registra cache hit."""
        ...

    def record_miss(self, key: str, latency: float) -> None:
        """Registra cache miss."""
        ...

    def record_write(self, key: str, size: int) -> None:
        """Registra escrita no cache."""
        ...

    def record_error(self, key: str, error: Exception) -> None:
        """Registra erro de cache."""
        ...


class NoOpMetrics:
    """Coletor de métricas que não faz nada (default)."""

    def record_hit(self, key: str, latency: float) -> None:
        pass

    def record_miss(self, key: str, latency: float) -> None:
        pass

    def record_write(self, key: str, size: int) -> None:
        pass

    def record_error(self, key: str, error: Exception) -> None:
        pass


@dataclass
class KeyStats:
    """Estatísticas para uma chave específica."""

    hits: int = 0
    misses: int = 0
    writes: int = 0
    errors: int = 0
    total_latency_hits: float = 0.0
    total_latency_misses: float = 0.0
    total_bytes_written: int = 0

    @property
    def total_operations(self) -> int:
        return self.hits + self.misses

    @property
    def hit_ratio(self) -> float:
        total = self.total_operations
        return self.hits / total if total > 0 else 0.0

    @property
    def avg_hit_latency_ms(self) -> float:
        return (self.total_latency_hits / self.hits * 1000) if self.hits > 0 else 0.0

    @property
    def avg_miss_latency_ms(self) -> float:
        return (self.total_latency_misses / self.misses * 1000) if self.misses > 0 else 0.0


@dataclass
class CacheStats:
    """Estatísticas agregadas do cache."""

    hits: int = 0
    misses: int = 0
    writes: int = 0
    errors: int = 0
    hit_latencies: list[float] = field(default_factory=list)
    miss_latencies: list[float] = field(default_factory=list)
    write_sizes: list[int] = field(default_factory=list)

    @property
    def total_operations(self) -> int:
        return self.hits + self.misses

    @property
    def hit_ratio(self) -> float:
        total = self.total_operations
        return self.hits / total if total > 0 else 0.0

    @property
    def avg_hit_latency_ms(self) -> float:
        if not self.hit_latencies:
            return 0.0
        return sum(self.hit_latencies) / len(self.hit_latencies) * 1000

    @property
    def avg_miss_latency_ms(self) -> float:
        if not self.miss_latencies:
            return 0.0
        return sum(self.miss_latencies) / len(self.miss_latencies) * 1000


class OpenTelemetryMetrics:
    """Coletor de métricas usando OpenTelemetry.

    Exporta métricas para qualquer backend suportado pelo OpenTelemetry:
    - Prometheus
    - Jaeger
    - Zipkin
    - OTLP (OpenTelemetry Protocol)

    Métricas exportadas:
    - cache.hits (counter): Número de cache hits
    - cache.misses (counter): Número de cache misses
    - cache.writes (counter): Número de escritas
    - cache.errors (counter): Número de erros
    - cache.latency (histogram): Latência das operações em segundos
    - cache.size (histogram): Tamanho dos dados escritos em bytes

    Example:
        ```python
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry import metrics

        # Configura exportador (exemplo: console)
        metrics.set_meter_provider(MeterProvider())

        # Usa com @cacheable
        otel_metrics = OpenTelemetryMetrics()

        @cacheable(metrics=otel_metrics)
        def my_function():
            pass
        ```
    """

    def __init__(self, meter_name: str = "dapr_state_cache") -> None:
        """Inicializa métricas OpenTelemetry.

        Args:
            meter_name: Nome do meter para agrupar métricas
        """
        meter = otel_metrics.get_meter(meter_name)

        # Counters
        self._hits_counter = meter.create_counter(
            "cache.hits",
            description="Número de cache hits",
            unit="1",
        )
        self._misses_counter = meter.create_counter(
            "cache.misses",
            description="Número de cache misses",
            unit="1",
        )
        self._writes_counter = meter.create_counter(
            "cache.writes",
            description="Número de escritas no cache",
            unit="1",
        )
        self._errors_counter = meter.create_counter(
            "cache.errors",
            description="Número de erros de cache",
            unit="1",
        )

        # Histograms
        self._latency_histogram = meter.create_histogram(
            "cache.latency",
            description="Latência das operações de cache",
            unit="s",
        )
        self._size_histogram = meter.create_histogram(
            "cache.size",
            description="Tamanho dos dados escritos no cache",
            unit="By",
        )

    def record_hit(self, key: str, latency: float) -> None:
        """Registra cache hit."""
        self._hits_counter.add(1, {"key": key})
        self._latency_histogram.record(latency, {"operation": "hit", "key": key})

    def record_miss(self, key: str, latency: float) -> None:
        """Registra cache miss."""
        self._misses_counter.add(1, {"key": key})
        self._latency_histogram.record(latency, {"operation": "miss", "key": key})

    def record_write(self, key: str, size: int) -> None:
        """Registra escrita no cache."""
        self._writes_counter.add(1, {"key": key})
        self._size_histogram.record(size, {"key": key})

    def record_error(self, key: str, error: Exception) -> None:
        """Registra erro de cache."""
        self._errors_counter.add(1, {"key": key, "error_type": type(error).__name__})


class InMemoryMetrics:
    """Coletor de métricas em memória com estatísticas por chave.

    Útil para desenvolvimento, testes e análise detalhada.
    Mantém estatísticas agregadas e por chave com thread-safety.

    Attributes:
        max_samples: Máximo de amostras de latência mantidas
    """

    def __init__(self, max_samples: int = 1000) -> None:
        """Inicializa coletor de métricas.

        Args:
            max_samples: Máximo de amostras de latência a manter
        """
        self._max_samples = max_samples
        self._lock = Lock()
        self._overall = CacheStats()
        self._by_key: dict[str, KeyStats] = defaultdict(KeyStats)

    def record_hit(self, key: str, latency: float) -> None:
        """Registra cache hit."""
        with self._lock:
            self._overall.hits += 1
            self._overall.hit_latencies.append(latency)
            self._trim_samples(self._overall.hit_latencies)

            self._by_key[key].hits += 1
            self._by_key[key].total_latency_hits += latency

    def record_miss(self, key: str, latency: float) -> None:
        """Registra cache miss."""
        with self._lock:
            self._overall.misses += 1
            self._overall.miss_latencies.append(latency)
            self._trim_samples(self._overall.miss_latencies)

            self._by_key[key].misses += 1
            self._by_key[key].total_latency_misses += latency

    def record_write(self, key: str, size: int) -> None:
        """Registra escrita no cache."""
        with self._lock:
            self._overall.writes += 1
            self._overall.write_sizes.append(size)
            self._trim_samples(self._overall.write_sizes)

            self._by_key[key].writes += 1
            self._by_key[key].total_bytes_written += size

    def record_error(self, key: str, error: Exception) -> None:
        """Registra erro de cache."""
        with self._lock:
            self._overall.errors += 1
            self._by_key[key].errors += 1

    def _trim_samples(self, samples: list[Any]) -> None:
        """Remove amostras antigas se exceder limite."""
        if len(samples) > self._max_samples:
            del samples[: len(samples) - self._max_samples]

    def get_stats(self) -> CacheStats:
        """Retorna estatísticas agregadas."""
        with self._lock:
            return CacheStats(
                hits=self._overall.hits,
                misses=self._overall.misses,
                writes=self._overall.writes,
                errors=self._overall.errors,
                hit_latencies=self._overall.hit_latencies.copy(),
                miss_latencies=self._overall.miss_latencies.copy(),
                write_sizes=self._overall.write_sizes.copy(),
            )

    def get_key_stats(self, key: str) -> KeyStats | None:
        """Retorna estatísticas de uma chave específica."""
        with self._lock:
            if key not in self._by_key:
                return None
            stats = self._by_key[key]
            return KeyStats(
                hits=stats.hits,
                misses=stats.misses,
                writes=stats.writes,
                errors=stats.errors,
                total_latency_hits=stats.total_latency_hits,
                total_latency_misses=stats.total_latency_misses,
                total_bytes_written=stats.total_bytes_written,
            )

    def get_all_key_stats(self) -> dict[str, KeyStats]:
        """Retorna estatísticas de todas as chaves."""
        with self._lock:
            return {
                key: KeyStats(
                    hits=stats.hits,
                    misses=stats.misses,
                    writes=stats.writes,
                    errors=stats.errors,
                    total_latency_hits=stats.total_latency_hits,
                    total_latency_misses=stats.total_latency_misses,
                    total_bytes_written=stats.total_bytes_written,
                )
                for key, stats in self._by_key.items()
            }

    def get_top_keys(self, by: str = "hits", limit: int = 10) -> list[tuple[str, int]]:
        """Retorna as chaves mais acessadas.

        Args:
            by: Critério de ordenação (hits, misses, writes, errors)
            limit: Número máximo de chaves a retornar
        """
        with self._lock:
            items = [(key, getattr(stats, by)) for key, stats in self._by_key.items()]
            items.sort(key=lambda x: x[1], reverse=True)
            return items[:limit]

    def reset(self) -> None:
        """Reseta todas as estatísticas."""
        with self._lock:
            self._overall = CacheStats()
            self._by_key.clear()
