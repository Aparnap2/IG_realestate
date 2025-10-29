"""
Multi-Channel Communication System for Progressive Nurture

Intelligent multi-channel communication for lead nurturing with:
- Support for SMS, Email, In-App, Push Notifications, and WhatsApp
- Intelligent channel selection based on user preferences and engagement patterns
- Message formatting and delivery optimization per channel
- Integration with nurture sequences and engagement tracker
- Compliance checking for industry-specific regulations
"""

from .multi_channel_manager import MultiChannelManager, multi_channel_manager

__all__ = [
    'MultiChannelManager',
    'multi_channel_manager'
]