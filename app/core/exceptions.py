"""Custom exception classes for the WhatsApp bot."""


class WhatsAppBotError(Exception):
    """Base exception for all WhatsApp bot errors."""
    pass


class WhatsAppAPIError(WhatsAppBotError):
    """Error when communicating with WhatsApp API."""
    pass


class RateLimitExceeded(WhatsAppBotError):
    """User has exceeded their rate limit."""
    pass


class MediaProcessingError(WhatsAppBotError):
    """Error processing media (download, upload, validation)."""
    pass


class AIGenerationError(WhatsAppBotError):
    """Error generating AI response."""
    pass


class ParseError(WhatsAppBotError):
    """Error parsing webhook payload."""
    pass


class ConversationError(WhatsAppBotError):
    """Error managing conversation state."""
    pass

