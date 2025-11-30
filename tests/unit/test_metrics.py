"""Testes para o sistema de métricas."""

from unittest.mock import MagicMock, patch

import pytest

from dapr_state_cache.metrics import (
    CacheStats,
    InMemoryMetrics,
    KeyStats,
    NoOpMetrics,
    OpenTelemetryMetrics,
)


class TestNoOpMetrics:
    """Testes para NoOpMetrics."""

    def test_record_hit_does_nothing(self) -> None:
        """Deve aceitar record_hit sem fazer nada."""
        metrics = NoOpMetrics()
        metrics.record_hit("key", 0.001)  # Não deve lançar erro

    def test_record_miss_does_nothing(self) -> None:
        """Deve aceitar record_miss sem fazer nada."""
        metrics = NoOpMetrics()
        metrics.record_miss("key", 0.001)

    def test_record_write_does_nothing(self) -> None:
        """Deve aceitar record_write sem fazer nada."""
        metrics = NoOpMetrics()
        metrics.record_write("key", 1024)

    def test_record_error_does_nothing(self) -> None:
        """Deve aceitar record_error sem fazer nada."""
        metrics = NoOpMetrics()
        metrics.record_error("key", Exception("test"))


class TestCacheStats:
    """Testes para CacheStats."""

    def test_total_operations(self) -> None:
        """Deve calcular total de operações."""
        stats = CacheStats(hits=10, misses=5)
        assert stats.total_operations == 15

    def test_hit_ratio_with_operations(self) -> None:
        """Deve calcular hit ratio."""
        stats = CacheStats(hits=75, misses=25)
        assert stats.hit_ratio == 0.75

    def test_hit_ratio_no_operations(self) -> None:
        """Deve retornar 0 quando não há operações."""
        stats = CacheStats()
        assert stats.hit_ratio == 0.0

    def test_avg_hit_latency(self) -> None:
        """Deve calcular latência média de hits."""
        stats = CacheStats(hit_latencies=[0.001, 0.002, 0.003])
        assert stats.avg_hit_latency_ms == pytest.approx(2.0)

    def test_avg_hit_latency_empty(self) -> None:
        """Deve retornar 0 sem latências."""
        stats = CacheStats()
        assert stats.avg_hit_latency_ms == 0.0


class TestKeyStats:
    """Testes para KeyStats."""

    def test_total_operations(self) -> None:
        """Deve calcular total de operações."""
        stats = KeyStats(hits=5, misses=3)
        assert stats.total_operations == 8

    def test_hit_ratio(self) -> None:
        """Deve calcular hit ratio."""
        stats = KeyStats(hits=8, misses=2)
        assert stats.hit_ratio == 0.8

    def test_avg_hit_latency(self) -> None:
        """Deve calcular latência média."""
        stats = KeyStats(hits=2, total_latency_hits=0.004)
        assert stats.avg_hit_latency_ms == pytest.approx(2.0)


class TestInMemoryMetrics:
    """Testes para InMemoryMetrics."""

    def test_record_hit(self) -> None:
        """Deve registrar hit."""
        metrics = InMemoryMetrics()
        metrics.record_hit("key1", 0.001)

        stats = metrics.get_stats()
        assert stats.hits == 1
        assert stats.misses == 0

    def test_record_miss(self) -> None:
        """Deve registrar miss."""
        metrics = InMemoryMetrics()
        metrics.record_miss("key1", 0.002)

        stats = metrics.get_stats()
        assert stats.misses == 1
        assert stats.hits == 0

    def test_record_write(self) -> None:
        """Deve registrar write."""
        metrics = InMemoryMetrics()
        metrics.record_write("key1", 1024)

        stats = metrics.get_stats()
        assert stats.writes == 1
        assert 1024 in stats.write_sizes

    def test_record_error(self) -> None:
        """Deve registrar error."""
        metrics = InMemoryMetrics()
        metrics.record_error("key1", Exception("test"))

        stats = metrics.get_stats()
        assert stats.errors == 1

    def test_per_key_stats(self) -> None:
        """Deve manter estatísticas por chave."""
        metrics = InMemoryMetrics()
        metrics.record_hit("key1", 0.001)
        metrics.record_hit("key1", 0.001)
        metrics.record_miss("key2", 0.002)

        key1_stats = metrics.get_key_stats("key1")
        key2_stats = metrics.get_key_stats("key2")

        assert key1_stats is not None
        assert key1_stats.hits == 2
        assert key2_stats is not None
        assert key2_stats.misses == 1

    def test_get_key_stats_nonexistent(self) -> None:
        """Deve retornar None para chave inexistente."""
        metrics = InMemoryMetrics()
        assert metrics.get_key_stats("nonexistent") is None

    def test_get_all_key_stats(self) -> None:
        """Deve retornar todas as estatísticas por chave."""
        metrics = InMemoryMetrics()
        metrics.record_hit("key1", 0.001)
        metrics.record_hit("key2", 0.001)

        all_stats = metrics.get_all_key_stats()
        assert "key1" in all_stats
        assert "key2" in all_stats

    def test_get_top_keys_by_hits(self) -> None:
        """Deve retornar top keys por hits."""
        metrics = InMemoryMetrics()
        metrics.record_hit("popular", 0.001)
        metrics.record_hit("popular", 0.001)
        metrics.record_hit("popular", 0.001)
        metrics.record_hit("regular", 0.001)

        top = metrics.get_top_keys(by="hits", limit=2)
        assert len(top) == 2
        assert top[0][0] == "popular"
        assert top[0][1] == 3

    def test_reset(self) -> None:
        """Deve resetar estatísticas."""
        metrics = InMemoryMetrics()
        metrics.record_hit("key1", 0.001)
        metrics.reset()

        stats = metrics.get_stats()
        assert stats.hits == 0
        assert metrics.get_key_stats("key1") is None

    def test_max_samples_limit(self) -> None:
        """Deve limitar número de samples."""
        metrics = InMemoryMetrics(max_samples=5)

        for i in range(10):
            metrics.record_hit("key", 0.001 * i)

        stats = metrics.get_stats()
        assert len(stats.hit_latencies) == 5

    def test_thread_safety(self) -> None:
        """Deve ser thread-safe."""
        import threading

        metrics = InMemoryMetrics()
        errors = []

        def record_hits() -> None:
            try:
                for _ in range(100):
                    metrics.record_hit("key", 0.001)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_hits) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        stats = metrics.get_stats()
        assert stats.hits == 1000


class TestOpenTelemetryMetrics:
    """Testes para OpenTelemetryMetrics."""

    def test_init_creates_counters_and_histograms(self) -> None:
        """Deve criar counters e histograms na inicialização."""
        mock_meter = MagicMock()
        mock_otel = MagicMock()
        mock_otel.get_meter.return_value = mock_meter

        with patch("dapr_state_cache.metrics.otel_metrics", mock_otel):
            OpenTelemetryMetrics("test_meter")

            mock_otel.get_meter.assert_called_once_with("test_meter")
            assert mock_meter.create_counter.call_count == 4  # hits, misses, writes, errors
            assert mock_meter.create_histogram.call_count == 2  # latency, size

    def test_init_uses_default_meter_name(self) -> None:
        """Deve usar nome de meter padrão."""
        mock_meter = MagicMock()
        mock_otel = MagicMock()
        mock_otel.get_meter.return_value = mock_meter

        with patch("dapr_state_cache.metrics.otel_metrics", mock_otel):
            OpenTelemetryMetrics()

            mock_otel.get_meter.assert_called_once_with("dapr_state_cache")

    def test_record_hit(self) -> None:
        """Deve registrar cache hit."""
        mock_meter = MagicMock()
        mock_counter = MagicMock()
        mock_histogram = MagicMock()
        mock_meter.create_counter.return_value = mock_counter
        mock_meter.create_histogram.return_value = mock_histogram

        mock_otel = MagicMock()
        mock_otel.get_meter.return_value = mock_meter

        with patch("dapr_state_cache.metrics.otel_metrics", mock_otel):
            metrics = OpenTelemetryMetrics("test_meter")
            metrics.record_hit("test_key", 0.005)

            mock_counter.add.assert_called_with(1, {"key": "test_key"})
            mock_histogram.record.assert_called_with(0.005, {"operation": "hit", "key": "test_key"})

    def test_record_miss(self) -> None:
        """Deve registrar cache miss."""
        mock_meter = MagicMock()
        mock_counter = MagicMock()
        mock_histogram = MagicMock()
        mock_meter.create_counter.return_value = mock_counter
        mock_meter.create_histogram.return_value = mock_histogram

        mock_otel = MagicMock()
        mock_otel.get_meter.return_value = mock_meter

        with patch("dapr_state_cache.metrics.otel_metrics", mock_otel):
            metrics = OpenTelemetryMetrics()
            metrics.record_miss("test_key", 0.003)

            mock_counter.add.assert_called_with(1, {"key": "test_key"})
            mock_histogram.record.assert_called_with(0.003, {"operation": "miss", "key": "test_key"})

    def test_record_write(self) -> None:
        """Deve registrar escrita no cache."""
        mock_meter = MagicMock()
        mock_counter = MagicMock()
        mock_histogram = MagicMock()
        mock_meter.create_counter.return_value = mock_counter
        mock_meter.create_histogram.return_value = mock_histogram

        mock_otel = MagicMock()
        mock_otel.get_meter.return_value = mock_meter

        with patch("dapr_state_cache.metrics.otel_metrics", mock_otel):
            metrics = OpenTelemetryMetrics()
            metrics.record_write("test_key", 2048)

            mock_counter.add.assert_called_with(1, {"key": "test_key"})
            mock_histogram.record.assert_called_with(2048, {"key": "test_key"})

    def test_record_error(self) -> None:
        """Deve registrar erro de cache."""
        mock_meter = MagicMock()
        mock_counter = MagicMock()
        mock_histogram = MagicMock()
        mock_meter.create_counter.return_value = mock_counter
        mock_meter.create_histogram.return_value = mock_histogram

        mock_otel = MagicMock()
        mock_otel.get_meter.return_value = mock_meter

        with patch("dapr_state_cache.metrics.otel_metrics", mock_otel):
            metrics = OpenTelemetryMetrics()
            metrics.record_error("test_key", ValueError("test error"))

            mock_counter.add.assert_called_with(1, {"key": "test_key", "error_type": "ValueError"})
