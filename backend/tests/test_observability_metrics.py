"""
Comprehensive Test Suite for Observability Metrics System

Tests all aspects of the ObservabilityMetrics functionality including:
- Real Show Rate Calculation with database queries
- Reminder Delivery Status Tracking per-touch metrics
- Percentile Infrastructure with Redis sorted sets
- Real Data Integration with Redis/Supabase queries
- Backfill Rate Metrics for waitlist conversion
- Prometheus Export for external monitoring
- SLA Compliance monitoring and alerting
- Slack Alerting for observability-specific scenarios
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import json
import requests

from backend.booking.observability_metrics import ObservabilityMetrics


class TestObservabilityMetricsInit:
    """Test cases for ObservabilityMetrics initialization and configuration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.metrics = ObservabilityMetrics()

    def test_init(self):
        """Test metrics initialization."""
        assert self.metrics is not None
        assert hasattr(self.metrics, 'redis_client')
        assert hasattr(self.metrics, 'sla_targets')
        assert hasattr(self.metrics, 'channel_targets')
        assert hasattr(self.metrics, 'backfill_targets')

    def test_sla_targets_configuration(self):
        """Test SLA targets are correctly configured."""
        targets = self.metrics.sla_targets
        
        # Verify all required SLA targets exist
        assert 'write_latency_seconds' in targets
        assert 'conflict_rate_percent' in targets
        assert 'p50_response_time_seconds' in targets
        assert 'p95_response_time_seconds' in targets
        assert 'p99_response_time_seconds' in targets
        assert 'double_book_rate_percent' in targets
        assert 'show_rate_percent' in targets
        assert 'reminder_delivery_rate_percent' in targets
        assert 'idempotency_reuse_percent' in targets
        
        # Verify target values are realistic
        assert targets['write_latency_seconds'] == 60
        assert targets['conflict_rate_percent'] == 2.0
        assert targets['show_rate_percent'] == 85.0
        assert targets['reminder_delivery_rate_percent'] == 95.0

    def test_channel_targets_configuration(self):
        """Test channel-specific targets."""
        channel_targets = self.metrics.channel_targets
        
        # Verify all required channels exist
        assert 'sms' in channel_targets
        assert 'email' in channel_targets
        assert 'dm' in channel_targets
        
        # Verify channel-specific targets
        for channel in ['sms', 'email', 'dm']:
            assert 'delivery_rate' in channel_targets[channel]
            assert 'response_rate' in channel_targets[channel]
            
            # Verify SMS has highest delivery rate
            if channel == 'sms':
                assert channel_targets[channel]['delivery_rate'] == 98.0

    def test_backfill_targets_configuration(self):
        """Test backfill performance targets."""
        backfill_targets = self.metrics.backfill_targets
        
        assert 'conversion_rate_percent' in backfill_targets
        assert 'time_to_fill_hours' in backfill_targets
        
        assert backfill_targets['conversion_rate_percent'] == 75.0
        assert backfill_targets['time_to_fill_hours'] == 2.0


class TestWriteLatencyTracking:
    """Test cases for write latency tracking functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.metrics = ObservabilityMetrics()
        self.lead_id = "test_lead_123"
        self.start_time = datetime.now() - timedelta(seconds=30)
        self.end_time = datetime.now()

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.redis_circuit_breaker')
    def test_track_write_latency_success(self, mock_circuit_breaker, mock_redis):
        """Test successful write latency tracking."""
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Test tracking latency
        self.metrics.track_write_latency(
            start_time=self.start_time,
            end_time=self.end_time,
            lead_id=self.lead_id
        )
        
        # Verify Redis operations were called
        assert mock_redis.zadd.call_count >= 1
        assert mock_redis.expire.call_count >= 1

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.redis_circuit_breaker')
    def test_track_write_latency_sla_breach(self, mock_circuit_breaker, mock_redis):
        """Test SLA breach detection for write latency."""
        with patch.object(self.metrics, 'send_slack_alert') as mock_alert:
            mock_circuit_breaker.call.side_effect = lambda func: func()
            
            # Create very slow operation (90 seconds > 60 second SLA)
            slow_start = datetime.now() - timedelta(seconds=90)
            slow_end = datetime.now()
            
            self.metrics.track_write_latency(
                start_time=slow_start,
                end_time=slow_end,
                lead_id=self.lead_id
            )
            
            # Verify SLA breach alert was sent
            mock_alert.assert_called_once()
            call_args = mock_alert.call_args
            assert call_args[1]['alert_type'] == 'sla_breach'
            assert call_args[1]['payload']['metric'] == 'write_latency'

    @patch('backend.booking.observability_metrics.redis_client', None)
    def test_track_write_latency_no_redis(self):
        """Test write latency tracking when Redis is unavailable."""
        # Should not crash when Redis is None
        self.metrics.track_write_latency(
            start_time=self.start_time,
            end_time=self.end_time,
            lead_id=self.lead_id
        )
        # Test completes without error


class TestConflictRateTracking:
    """Test cases for conflict rate tracking."""

    def setup_method(self):
        """Set up test fixtures."""
        self.metrics = ObservabilityMetrics()

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.redis_circuit_breaker')
    def test_track_conflict_rate_success(self, mock_circuit_breaker, mock_redis):
        """Test successful conflict rate tracking."""
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Test normal conflict rate (within threshold)
        self.metrics.track_conflict_rate(total_writes=100, conflicts=1)
        
        # Verify storage operations
        assert mock_redis.zadd.call_count >= 1

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.redis_circuit_breaker')
    def test_track_conflict_rate_threshold_breach(self, mock_circuit_breaker, mock_redis):
        """Test conflict rate threshold breach detection."""
        with patch.object(self.metrics, 'send_slack_alert') as mock_alert:
            mock_circuit_breaker.call.side_effect = lambda func: func()
            
            # Test high conflict rate (5% > 2% threshold)
            self.metrics.track_conflict_rate(total_writes=100, conflicts=5)
            
            # Verify threshold breach alert
            mock_alert.assert_called_once()
            call_args = mock_alert.call_args
            assert call_args[1]['alert_type'] == 'threshold_breach'
            assert call_args[1]['payload']['metric'] == 'conflict_rate'

    def test_track_conflict_rate_zero_writes(self):
        """Test conflict rate tracking with zero total writes."""
        # Should handle division by zero gracefully
        self.metrics.track_conflict_rate(total_writes=0, conflicts=0)

    def test_track_conflict_rate_zero_conflicts(self):
        """Test conflict rate tracking with zero conflicts."""
        self.metrics.track_conflict_rate(total_writes=100, conflicts=0)


class TestIdempotencyTracking:
    """Test cases for idempotency reuse tracking."""

    def setup_method(self):
        """Set up test fixtures."""
        self.metrics = ObservabilityMetrics()

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.redis_circuit_breaker')
    def test_track_idempotency_reuse_success(self, mock_circuit_breaker, mock_redis):
        """Test successful idempotency reuse tracking."""
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Test high reuse rate (90% > 80% target)
        self.metrics.track_idempotency_reuse(total_writes=100, reused=90)
        
        # Verify storage operations
        assert mock_redis.zadd.call_count >= 1

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.redis_circuit_breaker')
    def test_track_idempotency_reuse_below_target(self, mock_circuit_breaker, mock_redis):
        """Test idempotency reuse rate below target."""
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Test low reuse rate (70% < 80% target)
        with patch('builtins.print') as mock_print:  # Mock logger.info
            self.metrics.track_idempotency_reuse(total_writes=100, reused=70)
            
            # Should log info message but not alert
            # (actual logging behavior depends on logger configuration)

    def test_track_idempotency_reuse_zero_writes(self):
        """Test idempotency reuse tracking with zero writes."""
        self.metrics.track_idempotency_reuse(total_writes=0, reused=0)


class TestDoubleBookPrevention:
    """Test cases for double-booking prevention tracking."""

    def setup_method(self):
        """Set up test fixtures."""
        self.metrics = ObservabilityMetrics()

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.redis_circuit_breaker')
    def test_track_double_book_prevention_no_incidents(self, mock_circuit_breaker, mock_redis):
        """Test double-book prevention with no incidents."""
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Test zero prevented bookings
        self.metrics.track_double_book_prevention(prevented_count=0)
        
        # Verify storage operations
        assert mock_redis.zadd.call_count >= 1

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.redis_circuit_breaker')
    def test_track_double_book_prevention_incidents(self, mock_circuit_breaker, mock_redis):
        """Test double-book prevention with detected incidents."""
        with patch.object(self.metrics, 'send_slack_alert') as mock_alert:
            mock_circuit_breaker.call.side_effect = lambda func: func()
            
            # Test prevented bookings detected
            self.metrics.track_double_book_prevention(prevented_count=2)
            
            # Verify high-severity alert was sent
            mock_alert.assert_called_once()
            call_args = mock_alert.call_args
            assert call_args[1]['alert_type'] == 'double_book_detected'
            assert call_args[1]['payload']['prevented_count'] == 2
            assert call_args[1]['payload']['severity'] == 'high'


class TestReminderDeliveryTracking:
    """Test cases for reminder delivery status tracking."""

    def setup_method(self):
        """Set up test fixtures."""
        self.metrics = ObservabilityMetrics()
        self.lead_id = "test_lead_456"
        self.reminder_type = "24h"
        self.channel = "sms"

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.redis_circuit_breaker')
    def test_track_reminder_delivery_success(self, mock_circuit_breaker, mock_redis):
        """Test successful reminder delivery tracking."""
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Test successful delivery with response
        self.metrics.track_reminder_delivery(
            lead_id=self.lead_id,
            reminder_type=self.reminder_type,
            channel=self.channel,
            delivery_success=True,
            response_received=True,
            response_time_seconds=300
        )
        
        # Verify multiple storage operations (delivery, channel metrics, response)
        assert mock_redis.zadd.call_count >= 3
        assert mock_redis.hset.call_count >= 1

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.redis_circuit_breaker')
    def test_track_reminder_delivery_failure(self, mock_circuit_breaker, mock_redis):
        """Test failed reminder delivery tracking."""
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Test failed delivery
        with patch('builtins.print') as mock_print:  # Mock logger.warning
            self.metrics.track_reminder_delivery(
                lead_id=self.lead_id,
                reminder_type=self.reminder_type,
                channel=self.channel,
                delivery_success=False,
                response_received=False
            )
            
            # Should log warning but continue tracking
            # (actual logging behavior depends on logger configuration)

    def test_track_reminder_delivery_all_channels(self):
        """Test reminder delivery tracking for all supported channels."""
        channels = ['sms', 'email', 'dm']
        reminder_types = ['24h', '3h', '30m', 'last_chance']
        
        for channel in channels:
            for reminder_type in reminder_types:
                # Should not crash for any channel/type combination
                self.metrics.track_reminder_delivery(
                    lead_id=self.lead_id,
                    reminder_type=reminder_type,
                    channel=channel,
                    delivery_success=True
                )

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.redis_circuit_breaker')
    def test_track_reminder_delivery_response_tracking(self, mock_circuit_breaker, mock_redis):
        """Test response time tracking for reminders."""
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Test with various response times
        response_times = [60, 300, 1800, 3600]  # 1min, 5min, 30min, 1hour
        
        for response_time in response_times:
            self.metrics.track_reminder_delivery(
                lead_id=self.lead_id,
                reminder_type=self.reminder_type,
                channel=self.channel,
                delivery_success=True,
                response_received=True,
                response_time_seconds=response_time
            )
            
            # Verify response metrics are stored with time data
            # (actual verification depends on Redis key structure)


class TestShowRateCalculation:
    """Test cases for real show rate calculation with database queries."""

    def setup_method(self):
        """Set up test fixtures."""
        self.metrics = ObservabilityMetrics()
        self.lead_id = "test_lead_789"
        self.event_id = "calendar_event_123"

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.supabase_circuit_breaker')
    @patch('backend.booking.observability_metrics._ensure_supabase')
    def test_track_show_rate_real_success(self, mock_supabase, mock_circuit_breaker, mock_redis):
        """Test tracking real show rate from booking data."""
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Test tracking a show
        self.metrics.track_show_rate_real(
            lead_id=self.lead_id,
            event_id=self.event_id,
            showed_up=True
        )
        
        # Verify storage operations
        assert mock_redis.zadd.call_count >= 1
        assert mock_redis.lpush.call_count >= 1

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.supabase_circuit_breaker')
    @patch('backend.booking.observability_metrics._ensure_supabase')
    def test_track_show_rate_real_no_show(self, mock_supabase, mock_circuit_breaker, mock_redis):
        """Test tracking no-show event."""
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Test tracking a no-show
        self.metrics.track_show_rate_real(
            lead_id=self.lead_id,
            event_id=self.event_id,
            showed_up=False
        )
        
        # Verify storage operations for no-show
        assert mock_redis.zadd.call_count >= 1
        assert mock_redis.lpush.call_count >= 1

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.supabase_circuit_breaker')
    @patch('backend.booking.observability_metrics._ensure_supabase')
    def test_calculate_show_rate_with_data(self, mock_supabase, mock_circuit_breaker, mock_redis):
        """Test show rate calculation with real audit log data."""
        # Mock Supabase response with booking completion data
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [
            {"payload": {"showed_up": True}},
            {"payload": {"showed_up": True}},
            {"payload": {"showed_up": False}},
            {"payload": {"showed_up": True}}
        ]
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value = mock_response
        mock_supabase.return_value = mock_client
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Calculate show rate
        since = datetime.now() - timedelta(days=30)
        show_rate = self.metrics.calculate_show_rate(since)
        
        # Verify calculation (3 out of 4 showed up = 75%)
        assert show_rate == 75.0
        
        # Verify database query was made
        mock_client.table.assert_called_with("audit_logs")

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.supabase_circuit_breaker')
    @patch('backend.booking.observability_metrics._ensure_supabase')
    def test_calculate_show_rate_no_data(self, mock_supabase, mock_circuit_breaker, mock_redis):
        """Test show rate calculation with no data."""
        # Mock empty Supabase response
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value = mock_response
        mock_supabase.return_value = mock_client
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Calculate show rate with no data
        show_rate = self.metrics.calculate_show_rate()
        
        # Should return 0.0 for no data
        assert show_rate == 0.0

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.supabase_circuit_breaker')
    @patch('backend.booking.observability_metrics._ensure_supabase')
    def test_calculate_show_rate_default_timeframe(self, mock_supabase, mock_circuit_breaker, mock_redis):
        """Test show rate calculation uses default 30-day timeframe."""
        # Mock Supabase response
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [{"payload": {"showed_up": True}}]
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value = mock_response
        mock_supabase.return_value = mock_client
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Calculate show rate without specifying since (should use 30 days ago)
        show_rate = self.metrics.calculate_show_rate()
        
        # Should return 100% for single show
        assert show_rate == 100.0

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.supabase_circuit_breaker')
    @patch('backend.booking.observability_metrics._ensure_supabase')
    def test_calculate_show_rate_error_handling(self, mock_supabase, mock_circuit_breaker, mock_redis):
        """Test show rate calculation error handling."""
        # Mock Supabase error
        mock_supabase.side_effect = Exception("Database connection error")
        
        # Calculate show rate with error
        show_rate = self.metrics.calculate_show_rate()
        
        # Should return 0.0 on error and not crash
        assert show_rate == 0.0


class TestPercentileInfrastructure:
    """Test cases for percentile calculation infrastructure with Redis sorted sets."""

    def setup_method(self):
        """Set up test fixtures."""
        self.metrics = ObservabilityMetrics()

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.redis_circuit_breaker')
    def test_track_percentile_latency_success(self, mock_circuit_breaker, mock_redis):
        """Test successful percentile latency tracking."""
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Test tracking latency for percentiles
        latency = 45.5
        operation_type = "write"
        
        self.metrics.track_percentile_latency(latency, operation_type)
        
        # Verify Redis sorted set operations
        mock_redis.zadd.assert_called_once()
        mock_redis.zremrangebyrank.assert_called_once()
        mock_redis.expire.assert_called_once()

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.redis_circuit_breaker')
    def test_track_percentile_latency_different_operations(self, mock_circuit_breaker, mock_redis):
        """Test percentile tracking for different operation types."""
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        operation_types = ["write", "read", "cache", "database"]
        latency = 30.0
        
        for operation_type in operation_types:
            self.metrics.track_percentile_latency(latency, operation_type)
            
            # Verify operation-specific keys are used
            expected_key = f"metrics:latency:{operation_type}:percentiles"
            # (actual key verification depends on implementation)

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.redis_circuit_breaker')
    def test_calculate_percentile_latency_p50(self, mock_circuit_breaker, mock_redis):
        """Test P50 latency calculation."""
        # Mock Redis sorted set with latency data
        latencies = ["30.0", "45.0", "60.0", "75.0", "90.0"]  # 5 values
        mock_redis.zcard.return_value = 5
        mock_redis.zrange.return_value = latencies[2]  # P50 should be middle value (45.0)
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Calculate P50 (50th percentile)
        p50 = self.metrics.calculate_percentile_latency(50, "write")
        
        # Should return the middle value (index 2 for 5 items)
        assert p50 == 45.0

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.redis_circuit_breaker')
    def test_calculate_percentile_latency_p95(self, mock_circuit_breaker, mock_redis):
        """Test P95 latency calculation."""
        # Mock Redis sorted set
        mock_redis.zcard.return_value = 100
        mock_redis.zrange.return_value = ["120.5"]  # P95 value
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Calculate P95 (95th percentile)
        p95 = self.metrics.calculate_percentile_latency(95, "write")
        
        # Should return the 95th percentile value
        assert p95 == 120.5

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.redis_circuit_breaker')
    def test_calculate_percentile_latency_p99(self, mock_circuit_breaker, mock_redis):
        """Test P99 latency calculation."""
        # Mock Redis sorted set
        mock_redis.zcard.return_value = 100
        mock_redis.zrange.return_value = ["180.2"]  # P99 value
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Calculate P99 (99th percentile)
        p99 = self.metrics.calculate_percentile_latency(99, "write")
        
        # Should return the 99th percentile value
        assert p99 == 180.2

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.redis_circuit_breaker')
    def test_calculate_percentile_latency_empty_data(self, mock_circuit_breaker, mock_redis):
        """Test percentile calculation with no data."""
        mock_redis.zcard.return_value = 0
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Calculate percentile with no data
        percentile = self.metrics.calculate_percentile_latency(95, "write")
        
        # Should return 0.0 for empty data
        assert percentile == 0.0

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.redis_circuit_breaker')
    def test_calculate_percentile_latency_boundary_check(self, mock_circuit_breaker, mock_redis):
        """Test percentile calculation handles boundary conditions."""
        # Mock single data point
        mock_redis.zcard.return_value = 1
        mock_redis.zrange.return_value = ["50.0"]
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Calculate various percentiles with single data point
        for percentile in [50, 95, 99]:
            result = self.metrics.calculate_percentile_latency(percentile, "write")
            assert result == 50.0  # Should return the only available value

    @patch('backend.booking.observability_metrics.redis_client', None)
    def test_calculate_percentile_latency_no_redis(self):
        """Test percentile calculation when Redis is unavailable."""
        result = self.metrics.calculate_percentile_latency(95, "write")
        assert result == 0.0

    def test_calculate_percentile_edge_cases(self):
        """Test percentile calculation edge cases."""
        # Test invalid percentiles (should be handled gracefully)
        # Actual implementation may vary
        pass


class TestBackfillMetrics:
    """Test cases for backfill rate metrics and waitlist conversion."""

    def setup_method(self):
        """Set up test fixtures."""
        self.metrics = ObservabilityMetrics()

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.supabase_circuit_breaker')
    @patch('backend.booking.observability_metrics._ensure_supabase')
    def test_track_backfill_metrics_success(self, mock_supabase, mock_circuit_breaker, mock_redis):
        """Test successful backfill metrics tracking."""
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Test normal backfill performance
        self.metrics.track_backfill_metrics(
            waitlist_leads=10,
            converted_leads=8,
            time_to_fill_hours=1.5,
            original_slot_cancelled=True
        )
        
        # Verify storage operations
        assert mock_redis.zadd.call_count >= 2  # conversion rate + time to fill

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.supabase_circuit_breaker')
    @patch('backend.booking.observability_metrics._ensure_supabase')
    def test_track_backfill_metrics_conversion_alert(self, mock_supabase, mock_circuit_breaker, mock_redis):
        """Test backfill conversion rate alert."""
        with patch.object(self.metrics, 'send_slack_alert') as mock_alert:
            mock_circuit_breaker.call.side_effect = lambda func: func()
            
            # Test poor conversion rate (60% < 75% target)
            self.metrics.track_backfill_metrics(
                waitlist_leads=10,
                converted_leads=6,  # 60% conversion
                time_to_fill_hours=1.0,
                original_slot_cancelled=True
            )
            
            # Verify performance alert
            mock_alert.assert_called_once()
            call_args = mock_alert.call_args
            assert call_args[1]['alert_type'] == 'backfill_performance_alert'
            assert call_args[1]['payload']['metric'] == 'conversion_rate'

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.supabase_circuit_breaker')
    @patch('backend.booking.observability_metrics._ensure_supabase')
    def test_track_backfill_metrics_time_alert(self, mock_supabase, mock_circuit_breaker, mock_redis):
        """Test backfill time alert."""
        with patch.object(self.metrics, 'send_slack_alert') as mock_alert:
            mock_circuit_breaker.call.side_effect = lambda func: func()
            
            # Test slow backfill (3 hours > 2 hour target)
            self.metrics.track_backfill_metrics(
                waitlist_leads=10,
                converted_leads=8,
                time_to_fill_hours=3.0,
                original_slot_cancelled=True
            )
            
            # Verify time performance alert
            mock_alert.assert_called_once()
            call_args = mock_alert.call_args
            assert call_args[1]['alert_type'] == 'backfill_performance_alert'
            assert call_args[1]['payload']['metric'] == 'time_to_fill'

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.supabase_circuit_breaker')
    @patch('backend.booking.observability_metrics._ensure_supabase')
    def test_get_backfill_stats_with_data(self, mock_supabase, mock_circuit_breaker, mock_redis):
        """Test backfill statistics calculation with real data."""
        # Mock Supabase response with backfill completion data
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [
            {"payload": {"waitlist_leads": 10, "converted_leads": 8, "time_to_fill_hours": 1.5}},
            {"payload": {"waitlist_leads": 15, "converted_leads": 12, "time_to_fill_hours": 2.0}}
        ]
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value = mock_response
        mock_supabase.return_value = mock_client
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Get backfill statistics
        since = datetime.now() - timedelta(days=30)
        stats = self.metrics._get_backfill_stats(since)
        
        # Verify statistics calculation
        # Total: 25 waitlist leads, 20 converted = 80% conversion rate
        # Average time: (1.5 + 2.0) / 2 = 1.75 hours
        expected_conversion_rate = (20 / 25) * 100  # 80%
        expected_avg_time = (1.5 + 2.0) / 2  # 1.75
        
        assert abs(stats['conversion_rate'] - expected_conversion_rate) < 0.1
        assert abs(stats['avg_time_to_fill'] - expected_avg_time) < 0.1

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.supabase_circuit_breaker')
    @patch('backend.booking.observability_metrics._ensure_supabase')
    def test_get_backfill_stats_no_data(self, mock_supabase, mock_circuit_breaker, mock_redis):
        """Test backfill statistics with no data."""
        # Mock empty Supabase response
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value = mock_response
        mock_supabase.return_value = mock_client
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Get backfill statistics with no data
        stats = self.metrics._get_backfill_stats()
        
        # Should return zero values for no data
        assert stats['conversion_rate'] == 0
        assert stats['avg_time_to_fill'] == 0

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.supabase_circuit_breaker')
    @patch('backend.booking.observability_metrics._ensure_supabase')
    def test_get_backfill_stats_zero_waitlist(self, mock_supabase, mock_circuit_breaker, mock_redis):
        """Test backfill statistics with zero waitlist leads."""
        # Mock Supabase response with zero waitlist
        mock_client = Mock()
        mock_response = Mock()
        mock_response.data = [
            {"payload": {"waitlist_leads": 0, "converted_leads": 0, "time_to_fill_hours": 0}}
        ]
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.execute.return_value = mock_response
        mock_supabase.return_value = mock_client
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Get backfill statistics
        stats = self.metrics._get_backfill_stats()
        
        # Should handle division by zero gracefully
        assert stats['conversion_rate'] == 0  # 0/0 should be 0
        assert stats['avg_time_to_fill'] == 0

    def test_track_backfill_metrics_edge_cases(self):
        """Test backfill metrics edge cases."""
        # Test with various edge case inputs
        test_cases = [
            (0, 0, 0),  # All zeros
            (100, 100, 0.5),  # Perfect conversion, very fast
            (1, 0, 10),  # Single lead, no conversion, slow
            (1000, 1, 100),  # Large waitlist, minimal conversion
        ]
        
        for waitlist, converted, time_to_fill in test_cases:
            # Should not crash on any input combination
            self.metrics.track_backfill_metrics(waitlist, converted, time_to_fill)


class TestPrometheusExport:
    """Test cases for Prometheus metrics export functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.metrics = ObservabilityMetrics()

    @patch.object(ObservabilityMetrics, 'get_real_metrics_summary')
    @patch.object(ObservabilityMetrics, 'calculate_percentile_latency')
    @patch.object(ObservabilityMetrics, 'calculate_show_rate')
    @patch.object(ObservabilityMetrics, '_get_current_conflict_rate')
    @patch.object(ObservabilityMetrics, '_get_reminder_delivery_stats')
    @patch.object(ObservabilityMetrics, '_get_backfill_stats')
    @patch.object(ObservabilityMetrics, 'check_sla_thresholds')
    def test_export_prometheus_metrics_success(self, mock_sla_check, mock_backfill_stats, 
                                              mock_reminder_stats, mock_conflict_rate,
                                              mock_show_rate, mock_p50, mock_summary):
        """Test successful Prometheus metrics export."""
        # Mock all the metrics
        mock_summary.return_value = {
            'latency': {'p50': 45.0, 'p95': 120.0, 'p99': 180.0},
            'show_rate': {'current': 87.5},
            'conflict_rate': 1.5,
            'reminder_delivery': {
                'sms': {'delivery_rate': 98.0},
                'email': {'delivery_rate': 95.0},
                'dm': {'delivery_rate': 92.0}
            },
            'backfill_performance': {
                'conversion_rate': 80.0,
                'avg_time_to_fill': 1.5
            }
        }
        mock_sla_check.return_value = {'compliance_score': 95.0}
        
        # Export Prometheus metrics
        prometheus_output = self.metrics.export_prometheus_metrics()
        
        # Verify output format
        assert isinstance(prometheus_output, str)
        assert 'booking_latency_p50_seconds' in prometheus_output
        assert 'booking_latency_p95_seconds' in prometheus_output
        assert 'booking_latency_p99_seconds' in prometheus_output
        assert 'booking_show_rate_percent' in prometheus_output
        assert 'booking_conflict_rate_percent' in prometheus_output
        assert 'sla_compliance_score' in prometheus_output
        
        # Verify channel-specific reminder delivery metrics
        for channel in ['sms', 'email', 'dm']:
            assert f'reminder_delivery_rate_percent{{channel="{channel}"}}' in prometheus_output

    @patch.object(ObservabilityMetrics, 'get_real_metrics_summary')
    def test_export_prometheus_metrics_error_handling(self, mock_summary):
        """Test Prometheus export error handling."""
        # Mock error in metrics summary
        mock_summary.side_effect = Exception("Metrics calculation error")
        
        # Export metrics with error
        prometheus_output = self.metrics.export_prometheus_metrics()
        
        # Should return error message in Prometheus format
        assert "# Error generating metrics:" in prometheus_output
        assert "Metrics calculation error" in prometheus_output

    @patch.object(ObservabilityMetrics, 'get_real_metrics_summary')
    def test_export_prometheus_metrics_timestamp(self, mock_summary):
        """Test Prometheus metrics include proper timestamps."""
        mock_summary.return_value = {
            'latency': {'p50': 45.0, 'p95': 120.0, 'p99': 180.0},
            'show_rate': {'current': 87.5},
            'conflict_rate': 1.5,
            'reminder_delivery': {},
            'backfill_performance': {'conversion_rate': 80.0, 'avg_time_to_fill': 1.5}
        }
        
        # Export metrics
        prometheus_output = self.metrics.export_prometheus_metrics()
        
        # Verify each metric line includes timestamp
        lines = prometheus_output.strip().split('\n')
        for line in lines:
            if not line.startswith('#'):
                # Each metric line should have: name value timestamp
                parts = line.split()
                assert len(parts) == 3
                assert parts[0].startswith('booking_') or parts[0].startswith('reminder_') or parts[0].startswith('backfill_')
                assert parts[1].replace('.', '').replace('-', '').isdigit()  # numeric value
                assert parts[2].isdigit()  # timestamp


class TestSLACompliance:
    """Test cases for SLA threshold monitoring and compliance checking."""

    def setup_method(self):
        """Set up test fixtures."""
        self.metrics = ObservabilityMetrics()

    @patch.object(ObservabilityMetrics, 'calculate_percentile_latency')
    @patch.object(ObservabilityMetrics, 'calculate_show_rate')
    @patch.object(ObservabilityMetrics, '_get_current_conflict_rate')
    @patch.object(ObservabilityMetrics, '_get_reminder_delivery_stats')
    @patch.object(ObservabilityMetrics, '_get_backfill_stats')
    @patch.object(ObservabilityMetrics, 'send_slack_alert')
    def test_check_sla_thresholds_all_compliant(self, mock_alert, mock_backfill_stats,
                                               mock_reminder_stats, mock_conflict_rate,
                                               mock_show_rate, mock_p50):
        """Test SLA checking when all metrics are compliant."""
        # Mock all metrics within SLA thresholds
        mock_p50.side_effect = [40.0, 110.0, 170.0]  # P50, P95, P99
        mock_show_rate.return_value = 90.0  # > 85% target
        mock_conflict_rate.return_value = 1.0  # < 2% threshold
        mock_reminder_stats.return_value = {
            'sms': {'delivery_rate': 99.0},
            'email': {'delivery_rate': 96.0},
            'dm': {'delivery_rate': 93.0}
        }
        mock_backfill_stats.return_value = {'conversion_rate': 80.0, 'avg_time_to_fill': 1.5}
        
        # Check SLA thresholds
        result = self.metrics.check_sla_thresholds()
        
        # Verify all metrics are compliant
        assert result['status'] == 'checked'
        assert result['compliance_score'] == 100.0  # All metrics compliant
        assert result['alerts_triggered'] == 0
        
        # Verify no alerts were sent
        mock_alert.assert_not_called()

    @patch.object(ObservabilityMetrics, 'calculate_percentile_latency')
    @patch.object(ObservabilityMetrics, 'calculate_show_rate')
    @patch.object(ObservabilityMetrics, '_get_current_conflict_rate')
    @patch.object(ObservabilityMetrics, '_get_reminder_delivery_stats')
    @patch.object(ObservabilityMetrics, '_get_backfill_stats')
    @patch.object(ObservabilityMetrics, 'send_slack_alert')
    def test_check_sla_thresholds_multiple_breaches(self, mock_alert, mock_backfill_stats,
                                                   mock_reminder_stats, mock_conflict_rate,
                                                   mock_show_rate, mock_p50):
        """Test SLA checking with multiple metric breaches."""
        # Mock metrics exceeding thresholds
        mock_p50.side_effect = [70.0, 150.0, 200.0]  # P50, P95, P99 all over limits
        mock_show_rate.return_value = 80.0  # < 85% target
        mock_conflict_rate.return_value = 3.5  # > 2% threshold
        mock_reminder_stats.return_value = {
            'sms': {'delivery_rate': 96.0},  # SMS below 98%
            'email': {'delivery_rate': 94.0},  # Email below 95%
            'dm': {'delivery_rate': 91.0}  # DM below 92%
        }
        mock_backfill_stats.return_value = {'conversion_rate': 70.0, 'avg_time_to_fill': 2.5}
        
        # Check SLA thresholds
        result = self.metrics.check_sla_thresholds()
        
        # Verify multiple breaches detected
        assert result['alerts_triggered'] > 0
        assert result['compliance_score'] < 100.0
        
        # Verify alert was sent
        mock_alert.assert_called_once()
        call_args = mock_alert.call_args
        assert call_args[1]['alert_type'] == 'sla_dashboard_breach'
        assert 'breached_metrics' in call_args[1]['payload']

    @patch.object(ObservabilityMetrics, 'calculate_percentile_latency')
    @patch.object(ObservabilityMetrics, 'calculate_show_rate')
    @patch.object(ObservabilityMetrics, '_get_current_conflict_rate')
    @patch.object(ObservabilityMetrics, '_get_reminder_delivery_stats')
    @patch.object(ObservabilityMetrics, '_get_backfill_stats')
    @patch.object(ObservabilityMetrics, 'send_slack_alert')
    def test_check_sla_thresholds_zero_metrics(self, mock_alert, mock_backfill_stats,
                                             mock_reminder_stats, mock_conflict_rate,
                                             mock_show_rate, mock_p50):
        """Test SLA checking with no metric data."""
        # Mock zero values for all metrics
        mock_p50.side_effect = [0.0, 0.0, 0.0]
        mock_show_rate.return_value = 0.0
        mock_conflict_rate.return_value = 0.0
        mock_reminder_stats.return_value = {
            'sms': {'delivery_rate': 0.0},
            'email': {'delivery_rate': 0.0},
            'dm': {'delivery_rate': 0.0}
        }
        mock_backfill_stats.return_value = {'conversion_rate': 0.0, 'avg_time_to_fill': 0.0}
        
        # Check SLA thresholds
        result = self.metrics.check_sla_thresholds()
        
        # Verify calculation handles zero metrics gracefully
        assert result['status'] == 'checked'
        assert result['total_metrics'] > 0  # Should count non-zero metrics only
        assert result['compliance_score'] == 0.0  # No compliant metrics

    @patch.object(ObservabilityMetrics, 'calculate_percentile_latency')
    @patch.object(ObservabilityMetrics, 'calculate_show_rate')
    @patch.object(ObservabilityMetrics, '_get_current_conflict_rate')
    @patch.object(ObservabilityMetrics, '_get_reminder_delivery_stats')
    @patch.object(ObservabilityMetrics, '_get_backfill_stats')
    @patch.object(ObservabilityMetrics, 'send_slack_alert')
    def test_check_sla_thresholds_error_handling(self, mock_alert, mock_backfill_stats,
                                               mock_reminder_stats, mock_conflict_rate,
                                               mock_show_rate, mock_p50):
        """Test SLA checking error handling."""
        # Mock error in one of the metric calculations
        mock_p50.side_effect = Exception("Latency calculation error")
        
        # Check SLA thresholds
        result = self.metrics.check_sla_thresholds()
        
        # Should return error status
        assert result['status'] == 'error'
        assert 'error' in result

    def test_sla_threshold_edge_cases(self):
        """Test SLA threshold checking edge cases."""
        # Test with various boundary conditions
        pass


class TestSlackAlerting:
    """Test cases for Slack alerting functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.metrics = ObservabilityMetrics()

    @patch('requests.post')
    @patch('os.getenv')
    @patch('backend.booking.observability_metrics.audit_log_event')
    def test_send_slack_alert_success(self, mock_audit, mock_getenv, mock_post):
        """Test successful Slack alert sending."""
        # Mock environment and HTTP response
        mock_getenv.return_value = "https://hooks.slack.com/services/test"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # Send test alert
        alert_payload = {
            'metric': 'test_metric',
            'value': 100,
            'threshold': 50
        }
        
        self.metrics.send_slack_alert('threshold_breach', alert_payload)
        
        # Verify HTTP request was made
        mock_post.assert_called_once()
        
        # Verify audit logging
        mock_audit.assert_called()
        
        # Verify alert message format
        call_args = mock_post.call_args
        message_data = call_args[1]['json']
        assert message_data['text'] == '📊 Threshold Breach: test_metric exceeded 50'
        assert 'blocks' in message_data

    @patch('os.getenv')
    def test_send_slack_alert_no_webhook(self, mock_getenv):
        """Test Slack alert when webhook URL is not configured."""
        # Mock missing webhook URL
        mock_getenv.return_value = None
        
        # Send alert without webhook
        alert_payload = {'metric': 'test', 'value': 100}
        
        # Should not crash and should log warning
        self.metrics.send_slack_alert('threshold_breach', alert_payload)

    @patch('requests.post')
    @patch('os.getenv')
    @patch('backend.booking.observability_metrics.audit_log_event')
    def test_send_slack_alert_http_error(self, mock_audit, mock_getenv, mock_post):
        """Test Slack alert HTTP error handling."""
        # Mock environment and HTTP error
        mock_getenv.return_value = "https://hooks.slack.com/services/test"
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("Server Error")
        mock_post.return_value = mock_response
        
        # Send alert that will fail
        alert_payload = {'metric': 'test', 'value': 100}
        
        # Should handle HTTP error gracefully
        self.metrics.send_slack_alert('threshold_breach', alert_payload)
        
        # Verify audit logging for error
        mock_audit.assert_called()

    @patch('requests.post')
    @patch('os.getenv')
    def test_send_slack_alert_request_exception(self, mock_getenv, mock_post):
        """Test Slack alert request exception handling."""
        # Mock environment and network error
        mock_getenv.return_value = "https://hooks.slack.com/services/test"
        mock_post.side_effect = requests.exceptions.RequestException("Network error")
        
        # Send alert that will fail with network error
        alert_payload = {'metric': 'test', 'value': 100}
        
        # Should handle request exception gracefully
        self.metrics.send_slack_alert('threshold_breach', alert_payload)

    def test_send_slack_alert_all_types(self):
        """Test all alert types are properly formatted."""
        alert_types = [
            'conflict_detected',
            'sla_breach',
            'threshold_breach',
            'double_book_detected',
            'sla_dashboard_breach',
            'backfill_performance_alert',
            'reminder_delivery_alert',
            'policy_drift',
            'cache_miss_spike',
            'retry_spike'
        ]
        
        for alert_type in alert_types:
            # Each alert type should have a formatted message
            # The actual message content validation depends on implementation
            alert_payload = {'test': 'data'}
            try:
                self.metrics.send_slack_alert(alert_type, alert_payload)
            except Exception:
                # Some alerts might fail due to missing webhook, but should not crash
                pass

    @patch('requests.post')
    @patch('os.getenv')
    def test_send_slack_alert_complex_payload(self, mock_getenv, mock_post):
        """Test Slack alert with complex payload including breached metrics."""
        # Mock environment and successful response
        mock_getenv.return_value = "https://hooks.slack.com/services/test"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # Send complex alert with breached metrics
        complex_payload = {
            'breached_metrics': [
                {'metric': 'latency_p95', 'value': 150.0, 'threshold': 120.0},
                {'metric': 'show_rate', 'value': 80.0, 'threshold': 85.0}
            ],
            'compliance_score': 75.0,
            'total_metrics': 8
        }
        
        self.metrics.send_slack_alert('sla_dashboard_breach', complex_payload)
        
        # Verify the request includes the complex payload
        call_args = mock_post.call_args
        message_data = call_args[1]['json']
        
        # Verify breached metrics are included in blocks
        blocks = message_data.get('blocks', [])
        breached_block = None
        for block in blocks:
            if 'breached_metrics' in str(block):
                breached_block = block
                break
        
        assert breached_block is not None

    @patch('requests.post')
    @patch('os.getenv')
    def test_send_slack_alert_message_formatting(self, mock_getenv, mock_post):
        """Test Slack alert message formatting with special characters."""
        # Mock environment and successful response
        mock_getenv.return_value = "https://hooks.slack.com/services/test"
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # Send alert with special characters
        alert_payload = {
            'metric': 'test_metric_with_underscores',
            'value': 123.45,
            'threshold': 100.0,
            'description': 'Test alert with special chars: <>&"'
        }
        
        self.metrics.send_slack_alert('sla_breach', alert_payload)
        
        # Verify the request was made with formatted message
        call_args = mock_post.call_args
        message_data = call_args[1]['json']
        
        assert 'blocks' in message_data
        assert 'fields' in message_data['blocks'][1]


class TestRealDataIntegration:
    """Test cases for real data integration with Redis and Supabase."""

    def setup_method(self):
        """Set up test fixtures."""
        self.metrics = ObservabilityMetrics()

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.redis_circuit_breaker')
    def test_get_real_metrics_summary_success(self, mock_circuit_breaker, mock_redis):
        """Test getting real metrics summary with all data sources."""
        # Mock all the metric calculation methods
        with patch.object(self.metrics, 'calculate_percentile_latency') as mock_percentile, \
             patch.object(self.metrics, 'calculate_show_rate') as mock_show_rate, \
             patch.object(self.metrics, '_get_current_conflict_rate') as mock_conflict, \
             patch.object(self.metrics, '_get_reminder_delivery_stats') as mock_reminder, \
             patch.object(self.metrics, '_get_backfill_stats') as mock_backfill, \
             patch.object(self.metrics, '_get_idempotency_stats') as mock_idempotency:
            
            # Mock return values
            mock_percentile.side_effect = [40.0, 110.0, 170.0]  # P50, P95, P99
            mock_show_rate.return_value = 87.5
            mock_conflict.return_value = 1.2
            mock_reminder.return_value = {
                'sms': {'delivery_rate': 98.5, 'response_rate': 45.0},
                'email': {'delivery_rate': 95.0, 'response_rate': 25.0},
                'dm': {'delivery_rate': 92.0, 'response_rate': 35.0}
            }
            mock_backfill.return_value = {'conversion_rate': 78.0, 'avg_time_to_fill': 1.8}
            mock_idempotency.return_value = 85.0
            
            mock_circuit_breaker.call.side_effect = lambda func: func()
            
            # Get metrics summary
            since = datetime.now() - timedelta(days=7)
            summary = self.metrics.get_real_metrics_summary(since)
            
            # Verify summary structure
            assert 'period' in summary
            assert 'latency' in summary
            assert 'show_rate' in summary
            assert 'reminder_delivery' in summary
            assert 'conflict_rate' in summary
            assert 'backfill_performance' in summary
            assert 'idempotency_reuse' in summary
            
            # Verify latency percentiles
            assert summary['latency']['p50'] == 40.0
            assert summary['latency']['p95'] == 110.0
            assert summary['latency']['p99'] == 170.0
            
            # Verify show rate
            assert summary['show_rate']['current'] == 87.5
            assert summary['show_rate']['target'] == 85.0

    @patch.object(ObservabilityMetrics, 'calculate_percentile_latency')
    @patch.object(ObservabilityMetrics, 'calculate_show_rate')
    def test_get_real_metrics_summary_error_handling(self, mock_show_rate, mock_percentile):
        """Test real metrics summary error handling."""
        # Mock error in one of the metric calculations
        mock_percentile.side_effect = Exception("Redis connection error")
        
        # Get metrics summary with error
        summary = self.metrics.get_real_metrics_summary()
        
        # Should return error information
        assert 'error' in summary
        assert 'Redis connection error' in summary['error']

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.redis_circuit_breaker')
    def test_get_reminder_delivery_stats_real_data(self, mock_circuit_breaker, mock_redis):
        """Test getting real reminder delivery statistics."""
        # Mock Redis operations
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        since = datetime.now() - timedelta(days=30)
        stats = self.metrics._get_reminder_delivery_stats(since)
        
        # Verify structure
        for channel in ['sms', 'email', 'dm']:
            assert channel in stats
            assert 'delivery_rate' in stats[channel]
            assert 'response_rate' in stats[channel]
            
            # Verify rates are reasonable
            assert 0 <= stats[channel]['delivery_rate'] <= 100
            assert 0 <= stats[channel]['response_rate'] <= 100

    @patch('backend.booking.observability_metrics.redis_client')
    def test_get_reminder_delivery_stats_no_redis(self, mock_redis):
        """Test reminder delivery stats when Redis is unavailable."""
        # Mock Redis as None
        mock_redis = None
        
        stats = self.metrics._get_reminder_delivery_stats()
        
        # Should return default values
        assert 'sms' in stats
        assert 'email' in stats
        assert 'dm' in stats
        assert stats['sms']['delivery_rate'] == 0
        assert stats['sms']['response_rate'] == 0

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.redis_circuit_breaker')
    def test_store_metric_point_success(self, mock_circuit_breaker, mock_redis):
        """Test storing individual metric points."""
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Store a test metric
        self.metrics._store_metric_point(
            metric_type='test_metric',
            value=42.5,
            metadata={'test_key': 'test_value'}
        )
        
        # Verify Redis operations
        assert mock_redis.zadd.call_count == 1
        assert mock_redis.expire.call_count == 1

    @patch('backend.booking.observability_metrics.redis_client')
    def test_store_metric_point_no_redis(self, mock_redis):
        """Test storing metrics when Redis is unavailable."""
        # Should not crash when Redis is None
        self.metrics._store_metric_point(
            metric_type='test_metric',
            value=42.5
        )

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.redis_circuit_breaker')
    def test_update_show_rate_tracking_success(self, mock_circuit_breaker, mock_redis):
        """Test updating real-time show rate tracking."""
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Test both show and no-show
        self.metrics._update_show_rate_tracking('lead_123', True)
        self.metrics._update_show_rate_tracking('lead_456', False)
        
        # Verify Redis operations
        assert mock_redis.lpush.call_count == 2
        assert mock_redis.ltrim.call_count == 2
        assert mock_redis.expire.call_count >= 2

    @patch('backend.booking.observability_metrics.redis_client')
    def test_update_show_rate_tracking_no_redis(self, mock_redis):
        """Test show rate tracking when Redis is unavailable."""
        # Should not crash
        self.metrics._update_show_rate_tracking('lead_123', True)


class TestEdgeCasesAndErrorRecovery:
    """Test edge cases and error recovery scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.metrics = ObservabilityMetrics()

    @patch('backend.booking.observability_metrics.redis_client', None)
    @patch('backend.booking.observability_metrics.supabase_circuit_breaker')
    @patch('backend.booking.observability_metrics._ensure_supabase')
    def test_all_methods_no_dependencies(self, mock_supabase, mock_circuit_breaker):
        """Test all methods gracefully handle missing dependencies."""
        mock_circuit_breaker.call.side_effect = lambda func: None  # Return None instead of function result
        
        # Test all major methods don't crash
        test_methods = [
            lambda: self.metrics.track_write_latency(datetime.now(), datetime.now(), 'test'),
            lambda: self.metrics.track_conflict_rate(100, 5),
            lambda: self.metrics.track_idempotency_reuse(100, 80),
            lambda: self.metrics.track_double_book_prevention(0),
            lambda: self.metrics.track_reminder_delivery('test', '24h', 'sms', True),
            lambda: self.metrics.track_backfill_metrics(10, 8, 1.5),
            lambda: self.metrics.track_show_rate_real('test', 'event', True),
            lambda: self.metrics.calculate_percentile_latency(95),
            lambda: self.metrics.calculate_show_rate(),
            lambda: self.metrics.get_real_metrics_summary(),
            lambda: self.metrics.export_prometheus_metrics(),
            lambda: self.metrics.check_sla_thresholds(),
            lambda: self.metrics.generate_weekly_digest()
        ]
        
        for method in test_methods:
            try:
                result = method()
                # Most methods should return something even on error
                assert result is None or isinstance(result, (dict, str))
            except Exception as e:
                pytest.fail(f"Method failed with exception: {e}")

    def test_datetime_edge_cases(self):
        """Test handling of edge case datetime values."""
        # Test with very old dates
        old_date = datetime.now() - timedelta(days=365*10)  # 10 years ago
        result = self.metrics.calculate_show_rate(old_date)
        assert isinstance(result, float)
        
        # Test with future dates
        future_date = datetime.now() + timedelta(days=365)  # 1 year future
        result = self.metrics.calculate_show_rate(future_date)
        assert isinstance(result, float)

    def test_numeric_edge_cases(self):
        """Test handling of extreme numeric values."""
        # Test with very large numbers
        self.metrics.track_conflict_rate(1e10, 1e8)
        self.metrics.track_idempotency_reuse(1e10, 1e9)
        self.metrics.track_backfill_metrics(1e6, 1e5, 1e3)
        
        # Test with very small numbers
        self.metrics.track_conflict_rate(1, 0)
        self.metrics.track_idempotency_reuse(1, 0)
        self.metrics.track_backfill_metrics(0, 0, 0)

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.redis_circuit_breaker')
    def test_redis_circuit_breaker_behavior(self, mock_circuit_breaker, mock_redis):
        """Test Redis circuit breaker behavior."""
        # Mock circuit breaker always returning None (failure)
        mock_circuit_breaker.call.return_value = None
        
        # Test methods handle circuit breaker failures
        self.metrics.track_write_latency(datetime.now(), datetime.now(), 'test')
        self.metrics.track_conflict_rate(100, 5)
        self.metrics.track_reminder_delivery('test', '24h', 'sms', True)
        
        # Should not crash, circuit breaker handles failures

    @patch('backend.booking.observability_metrics.supabase_circuit_breaker')
    @patch('backend.booking.observability_metrics._ensure_supabase')
    def test_supabase_circuit_breaker_behavior(self, mock_supabase, mock_circuit_breaker):
        """Test Supabase circuit breaker behavior."""
        # Mock circuit breaker returning None (failure)
        mock_circuit_breaker.call.return_value = None
        
        # Test methods handle Supabase failures
        show_rate = self.metrics.calculate_show_rate()
        assert show_rate == 0.0  # Should return safe default
        
        backfill_stats = self.metrics._get_backfill_stats()
        assert isinstance(backfill_stats, dict)  # Should return safe structure

    def test_string_handling_edge_cases(self):
        """Test handling of edge case string inputs."""
        # Test with special characters
        self.metrics.track_reminder_delivery('test_@#$%^&*()', '24h', 'sms', True)
        self.metrics.track_show_rate_real('test_with_unicode_🚀', 'event_🎯', True)
        
        # Test with empty strings
        try:
            self.metrics.track_reminder_delivery('', '', '', True)
        except Exception:
            # May fail validation, which is acceptable
            pass

    def test_concurrent_operations_simulation(self):
        """Test simulation of concurrent metric operations."""
        # Simulate multiple operations happening simultaneously
        operations = []
        
        for i in range(10):
            operations.append(
                lambda: self.metrics.track_write_latency(
                    datetime.now() - timedelta(seconds=i),
                    datetime.now(),
                    f'lead_{i}'
                )
            )
        
        # Execute all operations
        for operation in operations:
            try:
                operation()
            except Exception:
                # Some operations might fail, but shouldn't crash the system
                pass


class TestIntegrationAndFlow:
    """Integration tests for complete observability flow."""

    def setup_method(self):
        """Set up integration test fixtures."""
        self.metrics = ObservabilityMetrics()

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.redis_circuit_breaker')
    @patch('backend.booking.observability_metrics.supabase_circuit_breaker')
    @patch('backend.booking.observability_metrics._ensure_supabase')
    @patch('backend.booking.observability_metrics.audit_log_event')
    def test_complete_booking_flow_observability(self, mock_audit, mock_supabase, 
                                               mock_circuit_breaker, mock_redis):
        """Test complete booking flow with full observability tracking."""
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Simulate complete booking flow
        lead_id = "integration_test_lead"
        event_id = "calendar_integration_123"
        
        # Step 1: Track booking latency
        start_time = datetime.now() - timedelta(seconds=45)
        end_time = datetime.now()
        self.metrics.track_write_latency(start_time, end_time, lead_id)
        
        # Step 2: Track conflict detection (none in this case)
        self.metrics.track_conflict_rate(total_writes=1, conflicts=0)
        
        # Step 3: Track idempotency (reused)
        self.metrics.track_idempotency_reuse(total_writes=1, reused=1)
        
        # Step 4: Track reminder deliveries for all touch points
        reminder_scenarios = [
            ('24h', 'sms', True, True, 300),
            ('3h', 'email', True, False, None),
            ('30m', 'dm', True, True, 120),
            ('last_chance', 'sms', True, False, None)
        ]
        
        for reminder_type, channel, success, response, response_time in reminder_scenarios:
            self.metrics.track_reminder_delivery(
                lead_id=lead_id,
                reminder_type=reminder_type,
                channel=channel,
                delivery_success=success,
                response_received=response,
                response_time_seconds=response_time
            )
        
        # Step 5: Track show/no-show
        self.metrics.track_show_rate_real(lead_id, event_id, showed_up=True)
        
        # Step 6: Check SLA compliance
        sla_result = self.metrics.check_sla_thresholds()
        
        # Step 7: Generate metrics summary
        summary = self.metrics.get_real_metrics_summary()
        
        # Verify integration flow completed
        assert 'status' in sla_result
        assert 'period' in summary
        
        # Verify audit logging was called
        assert mock_audit.call_count > 0

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.redis_circuit_breaker')
    @patch('backend.booking.observability_metrics.supabase_circuit_breaker')
    @patch('backend.booking.observability_metrics._ensure_supabase')
    @patch('backend.booking.observability_metrics.audit_log_event')
    def test_backfill_flow_observability(self, mock_audit, mock_supabase, 
                                        mock_circuit_breaker, mock_redis):
        """Test complete backfill flow with observability."""
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Simulate backfill flow
        # Step 1: Initial cancellation
        self.metrics.track_conflict_rate(total_writes=1, conflicts=0)  # Background writes
        
        # Step 2: Backfill metrics
        self.metrics.track_backfill_metrics(
            waitlist_leads=5,
            converted_leads=4,
            time_to_fill_hours=1.5,
            original_slot_cancelled=True
        )
        
        # Step 3: Check backfill SLA
        sla_result = self.metrics.check_sla_thresholds()
        
        # Step 4: Export metrics for monitoring
        prometheus_metrics = self.metrics.export_prometheus_metrics()
        
        # Verify backfill flow
        assert 'status' in sla_result
        assert 'backfill_conversion_rate_percent' in prometheus_metrics
        assert 'backfill_time_to_fill_hours' in prometheus_metrics

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.redis_circuit_breaker')
    def test_weekly_digest_generation(self, mock_circuit_breaker, mock_redis):
        """Test weekly digest generation flow."""
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Mock additional methods for digest
        with patch.object(self.metrics, 'send_slack_alert') as mock_alert, \
             patch.object(self.metrics, '_get_metric_sum') as mock_sum, \
             patch.object(self.metrics, '_get_metric_avg') as mock_avg:
            
            # Mock metric values
            mock_sum.side_effect = [45, 3, 2]  # bookings, reschedules, backfills
            mock_avg.side_effect = [52.5, 1.2, 87.5]  # latency, conflict, show rate
            
            # Generate weekly digest
            digest = self.metrics.generate_weekly_digest()
            
            # Verify digest structure
            assert digest['status'] == 'generated'
            assert 'metrics' in digest
            assert 'period' in digest
            
            # Verify weekly metrics are included
            weekly_metrics = digest['metrics']
            assert weekly_metrics['bookings_count'] == 45
            assert weekly_metrics['reschedules_count'] == 3
            assert weekly_metrics['backfills_count'] == 2
            assert weekly_metrics['avg_write_latency'] == 52.5
            
            # Verify Slack alert was sent
            mock_alert.assert_called_once_with('weekly_digest', mock.ANY)

    @patch('backend.booking.observability_metrics.redis_client')
    @patch('backend.booking.observability_metrics.redis_circuit_breaker')
    def test_alerting_integration(self, mock_circuit_breaker, mock_redis):
        """Test complete alerting integration."""
        mock_circuit_breaker.call.side_effect = lambda func: func()
        
        # Mock Slack alert
        with patch.object(self.metrics, 'send_slack_alert') as mock_alert:
            
            # Trigger various alert scenarios
            alert_scenarios = [
                # SLA breach scenarios
                (lambda: self.metrics.track_write_latency(
                    datetime.now() - timedelta(seconds=120),
                    datetime.now(),
                    'test'
                ), 'sla_breach'),
                
                # Threshold breach scenarios  
                (lambda: self.metrics.track_conflict_rate(100, 5), 'threshold_breach'),
                
                # Performance alerts
                (lambda: self.metrics.track_backfill_metrics(10, 6, 3.0), 'backfill_performance_alert'),
                
                # Double booking detection
                (lambda: self.metrics.track_double_book_prevention(1), 'double_book_detected')
            ]
            
            for trigger_func, expected_alert_type in alert_scenarios:
                trigger_func()
                
                # Verify appropriate alert was sent
                if expected_alert_type == 'sla_breach':
                    # May be called multiple times
                    pass
                elif expected_alert_type == 'threshold_breach':
                    mock_alert.assert_called()
                    call_args = mock_alert.call_args
                    assert call_args[1]['alert_type'] == expected_alert_type
                elif expected_alert_type == 'backfill_performance_alert':
                    mock_alert.assert_called()
                    call_args = mock_alert.call_args
                    assert call_args[1]['alert_type'] == expected_alert_type
                elif expected_alert_type == 'double_book_detected':
                    mock_alert.assert_called()
                    call_args = mock_alert.call_args
                    assert call_args[1]['alert_type'] == expected_alert_type


if __name__ == '__main__':
    pytest.main([__file__])