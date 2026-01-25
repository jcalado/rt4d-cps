"""RT-4D Codeplug Library

A Python library and GUI for parsing, editing, and flashing RT-4D radio codeplug files.
"""

__version__ = "0.4.0"

from .models import (
    Channel, Contact, GroupList, Zone, Codeplug, RadioSettings,
    ChannelMode, PowerLevel, ScanMode, ContactType,
    EncryptionKey, EncryptionType,
    Message, MessageStore, MessageType, CallType,
    FMPreset, FMSettings
)
from .parser import CodeplugParser
from .serializer import CodeplugSerializer
from .global_contacts import GlobalContact, GlobalContactDatabase, GlobalContactCSVParser
from .messages import MessageParser, MessageSerializer
from .fm_radio import FMParser, FMSerializer

__all__ = [
    "Channel",
    "Contact",
    "GroupList",
    "Zone",
    "Codeplug",
    "RadioSettings",
    "ChannelMode",
    "PowerLevel",
    "ScanMode",
    "ContactType",
    "EncryptionKey",
    "EncryptionType",
    "Message",
    "MessageStore",
    "MessageType",
    "CallType",
    "FMPreset",
    "FMSettings",
    "CodeplugParser",
    "CodeplugSerializer",
    "MessageParser",
    "MessageSerializer",
    "FMParser",
    "FMSerializer",
    "GlobalContact",
    "GlobalContactDatabase",
    "GlobalContactCSVParser",
]

# Re-export key methods for convenience
GlobalContactCSVParser.export_for_radio = GlobalContactCSVParser.export_for_radio
