"""Parser coverage for every WhatsApp inbound type."""
from app.services.whatsapp.parser import MessageType, parse_webhook_payload


def _wrap(message: dict) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "PHONE_NUMBER_ID",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "1", "phone_number_id": "1"},
                    "messages": [message],
                },
                "field": "messages",
            }],
        }],
    }


def _msg(message_type: str, **payload) -> dict:
    base = {
        "from": "15551234567",
        "id": "wamid.TEST",
        "timestamp": "1700000000",
        "type": message_type,
    }
    base.update(payload)
    return base


def test_text_message():
    parsed = parse_webhook_payload(_wrap(_msg("text", text={"body": "hello"})))
    assert parsed.message_type == MessageType.TEXT
    assert parsed.content.text == "hello"


def test_image_message():
    parsed = parse_webhook_payload(_wrap(_msg(
        "image",
        image={"id": "MEDIA_ID", "mime_type": "image/jpeg", "caption": "cat"},
    )))
    assert parsed.message_type == MessageType.IMAGE
    assert parsed.content.media_id == "MEDIA_ID"
    assert parsed.content.caption == "cat"


def test_voice_message_marked_as_voice():
    parsed = parse_webhook_payload(_wrap(_msg(
        "voice",
        voice={"id": "MEDIA_ID", "mime_type": "audio/ogg"},
    )))
    assert parsed.message_type == MessageType.VOICE
    assert parsed.content.voice is True


def test_document_message():
    parsed = parse_webhook_payload(_wrap(_msg(
        "document",
        document={"id": "MEDIA", "mime_type": "application/pdf", "filename": "report.pdf"},
    )))
    assert parsed.message_type == MessageType.DOCUMENT
    assert parsed.content.filename == "report.pdf"


def test_location_message():
    parsed = parse_webhook_payload(_wrap(_msg(
        "location",
        location={"latitude": 40.7128, "longitude": -74.006, "name": "NYC"},
    )))
    assert parsed.message_type == MessageType.LOCATION
    assert parsed.content.latitude == 40.7128
    assert parsed.content.longitude == -74.006
    assert parsed.content.location_name == "NYC"


def test_contacts_message():
    parsed = parse_webhook_payload(_wrap(_msg(
        "contacts",
        contacts=[{"name": {"formatted_name": "Alice"}, "phones": [{"phone": "1"}]}],
    )))
    assert parsed.message_type == MessageType.CONTACTS
    assert parsed.content.contacts and parsed.content.contacts[0]["name"]["formatted_name"] == "Alice"


def test_sticker_message():
    parsed = parse_webhook_payload(_wrap(_msg(
        "sticker",
        sticker={"id": "MEDIA", "mime_type": "image/webp", "animated": True},
    )))
    assert parsed.message_type == MessageType.STICKER
    assert parsed.content.animated is True


def test_interactive_button_reply():
    parsed = parse_webhook_payload(_wrap(_msg(
        "interactive",
        interactive={
            "type": "button_reply",
            "button_reply": {"id": "yes", "title": "Yes"},
        },
    )))
    assert parsed.message_type == MessageType.INTERACTIVE
    assert parsed.content.button_id == "yes"
    assert parsed.content.button_title == "Yes"
    assert parsed.content.text == "Yes"


def test_interactive_list_reply():
    parsed = parse_webhook_payload(_wrap(_msg(
        "interactive",
        interactive={
            "type": "list_reply",
            "list_reply": {"id": "x", "title": "Pick X"},
        },
    )))
    assert parsed.message_type == MessageType.INTERACTIVE
    assert parsed.content.list_id == "x"
    assert parsed.content.list_title == "Pick X"


def test_reaction_message():
    parsed = parse_webhook_payload(_wrap(_msg(
        "reaction",
        reaction={"message_id": "wamid.OTHER", "emoji": "👍"},
    )))
    assert parsed.message_type == MessageType.REACTION
    assert parsed.content.reaction_emoji == "👍"
    assert parsed.content.reaction_target_id == "wamid.OTHER"


def test_status_update_returns_none():
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "1",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {},
                    "statuses": [{"id": "x", "status": "read"}],
                },
                "field": "messages",
            }],
        }],
    }
    assert parse_webhook_payload(payload) is None
