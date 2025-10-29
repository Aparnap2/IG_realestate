"""
Observability Metrics for Self-Driving Booking Ops 2.0

Implements SLA tracking, conflict rate monitoring, and Slack alerting
for booking system performance and reliability metrics.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from collections import defaultdict

from backend.utils.redis_client import redis_client, redis_circuit_breaker
from backend.utils.audit import audit_log_event

logger = logging.getLogger(__name__)

class ObservabilityMetrics:
    """
    Comprehensive observability for booking operations.
    
    Tracks write latency, conflict rates, idempotency reuse, and SLA compliance
    with automatic Slack alerting for threshold breaches.
    """

    def __init__(self):
        self.redis_client = redis_client

        # SLA targets
        self.sla_targets = {
            'write_latency_seconds': 60,
            'conflict_rate_percent': 2.0,
            'p95_response_time_seconds': 120,
            'double_book_rate_percent': 0.5,
            'idempotency_reuse_percent': 80.0  # Target reuse rate
        }

    def track_write_latency(
        self,
        start_time: datetime,
        end_time: datetime,
        lead_id: str
    ) -> None:
        """
        Track calendar write operation latency.
        
        Args:
            start_time: Operation start time
            end_time: Operation end time
            lead_id: Lead identifier for correlation
        """
        try:
            latency_seconds = (end_time - start_time).total_seconds()

            # Store individual latency
            self._store_metric_point(
                metric_type='write_latency',
                value=latency_seconds,
                metadata={
                    'lead_id': lead_id,
                    'operation': 'calendar_write'
                }
            )

            # Update rolling aggregates
            self._update_latency_aggregates(latency_seconds)

            # Check SLA thresholds
            if latency_seconds > self.sla_targets['write_latency_seconds']:
                self.send_slack_alert(
                    alert_type='sla_breach',
                    payload={
                        'metric': 'write_latency',
                        'value': latency_seconds,
                        'threshold': self.sla_targets['write_latency_seconds'],
                        'lead_id': lead_id
                    }
                )

        except Exception as e:
            logger.error(f"Error tracking write latency: {e}")

    def track_conflict_rate(self, total_writes: int, conflicts: int) -> None:
        """
        Track calendar conflict rate.
        
        Args:
            total_writes: Total write operations
            conflicts: Number of conflicts detected
        """
        try:
            if total_writes == 0:
                return

            conflict_rate = (conflicts / total_writes) * 100

            self._store_metric_point(
                metric_type='conflict_rate',
                value=conflict_rate,
                metadata={
                    'total_writes': total_writes,
                    'conflicts': conflicts
                }
            )

            # Check threshold
            if conflict_rate > self.sla_targets['conflict_rate_percent']:
                self.send_slack_alert(
                    alert_type='threshold_breach',
                    payload={
                        'metric': 'conflict_rate',
                        'value': conflict_rate,
                        'threshold': self.sla_targets['conflict_rate_percent']
                    }
                )

        except Exception as e:
            logger.error(f"Error tracking conflict rate: {e}")

    def track_idempotency_reuse(self, total_writes: int, reused: int) -> None:
        """
        Track idempotency key reuse rate.
        
        Args:
            total_writes: Total write operations
            reused: Number of idempotent operations (cache hits)
        """
        try:
            if total_writes == 0:
                return

            reuse_rate = (reused / total_writes) * 100

            self._store_metric_point(
                metric_type='idempotency_reuse',
                value=reuse_rate,
                metadata={
                    'total_writes': total_writes,
                    'reused': reused
                }
            )

            # Log if below target (not necessarily an alert)
            if reuse_rate < self.sla_targets['idempotency_reuse_percent']:
                logger.info(f"Idempotency reuse rate below target: {reuse_rate:.1f}%")

        except Exception as e:
            logger.error(f"Error tracking idempotency reuse: {e}")

    def track_double_book_prevention(self, prevented_count: int) -> None:
        """
        Track double-bookings prevented by the system.
        
        Args:
            prevented_count: Number of double-bookings prevented
        """
        try:
            self._store_metric_point(
                metric_type='double_book_prevention',
                value=prevented_count,
                metadata={'period': 'daily'}
            )

            # Alert if double-books detected
            if prevented_count > 0:
                self.send_slack_alert(
                    alert_type='double_book_detected',
                    payload={
                        'prevented_count': prevented_count,
                        'severity': 'high'
                    }
                )

        except Exception as e:
            logger.error(f"Error tracking double-book prevention: {e}")

    def check_sla_thresholds(self) -> Dict[str, Any]:
        """
        Check all SLA thresholds and return status.
        
        Returns:
            Dict with SLA compliance status for each metric
        """
        try:
            status = {}
            alerts_triggered = []

            # Check write latency P95
            p95_latency = self._calculate_p95_latency()
            status['write_latency_p95'] = {
                'value': p95_latency,
                'threshold': self.sla_targets['p95_response_time_seconds'],
                'compliant': p95_latency <= self.sla_targets['p95_response_time_seconds']
            }

            # Check conflict rate
            conflict_rate = self._get_current_conflict_rate()
            status['conflict_rate'] = {
                'value': conflict_rate,
                'threshold': self.sla_targets['conflict_rate_percent'],
                'compliant': conflict_rate <= self.sla_targets['conflict_rate_percent']
            }

            # Check double-book rate
            double_book_rate = self._get_current_double_book_rate()
            status['double_book_rate'] = {
                'value': double_book_rate,
                'threshold': self.sla_targets['double_book_rate_percent'],
                'compliant': double_book_rate <= self.sla_targets['double_book_rate_percent']
            }

            # Trigger alerts for non-compliant metrics
            for metric, data in status.items():
                if not data['compliant']:
                    alerts_triggered.append({
                        'metric': metric,
                        'value': data['value'],
                        'threshold': data['threshold']
                    })

            if alerts_triggered:
                self.send_slack_alert(
                    alert_type='sla_dashboard_breach',
                    payload={'breached_metrics': alerts_triggered}
                )

            return {
                'status': 'checked',
                'metrics': status,
                'alerts_triggered': len(alerts_triggered)
            }

        except Exception as e:
            logger.error(f"Error checking SLA thresholds: {e}")
            return {'status': 'error', 'error': str(e)}

    def send_slack_alert(self, alert_type: str, payload: Dict[str, Any]) -> None:
        """
        Send Slack alert for booking system issues.
        
        Args:
            alert_type: Type of alert (conflict_detected, sla_breach, etc.)
            payload: Alert-specific data
        """
        try:
            import requests
            import os

            webhook_url = os.getenv('SLACK_WEBHOOK_URL')
            if not webhook_url:
                logger.warning("SLACK_WEBHOOK_URL not configured - skipping Slack alert")
                return

            # Format alert message
            alert_messages = {
                'conflict_detected': f"🚨 Calendar Conflict Detected: {payload.get('slot_time', 'Unknown time')}",
                'sla_breach': f"⚠️ SLA Breach: {payload.get('metric', 'Unknown')} at {payload.get('value', 'N/A')}",
                'threshold_breach': f"📊 Threshold Breach: {payload.get('metric', 'Unknown')} exceeded {payload.get('threshold', 'N/A')}",
                'double_book_detected': f"🚫 Double-Book Prevention: {payload.get('prevented_count', 0)} incidents prevented",
                'sla_dashboard_breach': f"📈 SLA Dashboard Alert: {len(payload.get('breached_metrics', []))} metrics breached",
                'policy_drift': f"⚙️ Policy Drift Detected: Scheduling policies may need adjustment",
                'cache_miss_spike': f"💾 Cache Performance: High cache miss rate detected",
                'retry_spike': f"🔄 System Load: Rising retry counts detected"
            }

            message_text = alert_messages.get(alert_type, f"🚨 Booking Alert: {alert_type}")

            # Create detailed message
            blocks = [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{message_text}*"
                    }
                },
                {
                    "type": "section",
                    "fields": []
                }
            ]

            # Add payload fields
            fields = []
            for key, value in payload.items():
                if key != 'breached_metrics':  # Handle separately
                    fields.append({
                        "type": "mrkdwn",
                        "text": f"*{key}*: {value}"
                    })

            if fields:
                blocks[1]["fields"] = fields

            # Handle breached metrics specially
            if 'breached_metrics' in payload:
                breached_text = "\\n".join([
                    f"• {m['metric']}: {m['value']:.2f} > {m['threshold']:.2f}"
                    for m in payload['breached_metrics']
                ])
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Breached Metrics:*\\n{breached_text}"
                    }
                })

            message = {
                "text": message_text,
                "blocks": blocks
            }

            response = requests.post(webhook_url, json=message, timeout=10)
            response.raise_for_status()

            audit_log_event("slack_alert_sent", {
                "alert_type": alert_type,
                "payload": payload,
                "response_status": response.status_code
            })

        except Exception as e:
            logger.error(f"Error sending Slack alert: {e}")
            audit_log_event("slack_alert_error", {
                "alert_type": alert_type,
                "error": str(e)
            })

    def generate_weekly_digest(self) -> Dict[str, Any]:
        """
        Generate weekly performance digest.
        
        Returns:
            Dict with weekly metrics summary
        """
        try:
            # Calculate metrics for the past week
            week_start = datetime.now() - timedelta(days=7)

            metrics = {
                'bookings_count': self._get_metric_sum('bookings', week_start),
                'reschedules_count': self._get_metric_sum('reschedules', week_start),
                'backfills_count': self._get_metric_sum('backfills', week_start),
                'avg_write_latency': self._get_metric_avg('write_latency', week_start),
                'conflict_rate': self._get_metric_avg('conflict_rate', week_start),
                'show_rate': self._calculate_show_rate(week_start),
                'idempotency_reuse': self._get_metric_avg('idempotency_reuse', week_start)
            }

            # Send weekly digest to Slack
            self.send_slack_alert(
                alert_type='weekly_digest',
                payload={
                    'period': 'weekly',
                    'metrics': metrics,
                    'generated_at': datetime.now().isoformat()
                }
            )

            audit_log_event("weekly_digest_generated", metrics)

            return {
                'status': 'generated',
                'metrics': metrics,
                'period': f"{week_start.date()} to {datetime.now().date()}"
            }

        except Exception as e:
            logger.error(f"Error generating weekly digest: {e}")
            return {'status': 'error', 'error': str(e)}

    def _store_metric_point(
        self,
        metric_type: str,
        value: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Store individual metric data point."""
        if self.redis_client is None:
            return

        try:
            date_key = datetime.now().strftime('%Y-%m-%d')
            key = f"metrics:{metric_type}:{date_key}"

            def _store_operation():
                # Store as sorted set with timestamp as score
                timestamp = datetime.now().timestamp()
                data = {
                    'value': value,
                    'timestamp': timestamp,
                    'metadata': metadata or {}
                }
                self.redis_client.zadd(key, {json.dumps(data): timestamp})

                # Set expiry (90 days)
                self.redis_client.expire(key, 7776000)
                return True

            redis_circuit_breaker.call(_store_operation)

        except Exception as e:
            logger.warning(f"Error storing metric point: {e}")

    def _update_latency_aggregates(self, latency: float) -> None:
        """Update rolling latency aggregates."""
        if self.redis_client is None:
            return

        try:
            def _update_operation():
                # Store in sorted set for percentile calculations
                key = "metrics:write_latency:rolling"
                timestamp = datetime.now().timestamp()
                self.redis_client.zadd(key, {str(latency): timestamp})

                # Keep only last 1000 measurements
                self.redis_client.zremrangebyrank(key, 0, -1001)

                # Set expiry (7 days)
                self.redis_client.expire(key, 604800)

            redis_circuit_breaker.call(_update_operation)

        except Exception as e:
            logger.warning(f"Error updating latency aggregates: {e}")

    def _calculate_p95_latency(self) -> float:
        """Calculate P95 write latency from recent measurements."""
        if self.redis_client is None:
            return 0.0

        try:
            def _calculate_operation():
                key = "metrics:write_latency:rolling"
                count = self.redis_client.zcard(key)

                if count == 0:
                    return 0.0

                # Get 95th percentile (index = 95% of count)
                p95_index = int(count * 0.95)
                values = self.redis_client.zrange(key, p95_index, p95_index)

                if values:
                    return float(values[0])

                return 0.0

            return redis_circuit_breaker.call(_calculate_operation) or 0.0

        except Exception as e:
            logger.warning(f"Error calculating P95 latency: {e}")
            return 0.0

    def _get_current_conflict_rate(self) -> float:
        """Get current conflict rate from recent data."""
        # Placeholder - would calculate from stored metrics
        return 1.5  # Mock value

    def _get_current_double_book_rate(self) -> float:
        """Get current double-book prevention rate."""
        # Placeholder - would calculate from stored metrics
        return 0.1  # Mock value

    def _get_metric_sum(self, metric_type: str, since: datetime) -> int:
        """Get sum of metric values since date."""
        # Placeholder - would query stored metrics
        return 42  # Mock value

    def _get_metric_avg(self, metric_type: str, since: datetime) -> float:
        """Get average of metric values since date."""
        # Placeholder - would query stored metrics
        return 25.0  # Mock value

    def _calculate_show_rate(self, since: datetime) -> float:
        """Calculate show-up rate from booking data."""
        # Placeholder - would calculate from booking outcomes
        return 85.0  # Mock value (85% show rate)
