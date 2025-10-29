import math

import pytest

from rt4d_codeplug.constants import SPI_REGIONS
from rt4d_uart import RT4DUART


class FakeSerial:
    def __init__(self, read_bytes=b""):
        self.read_buffer = bytearray(read_bytes)
        self.writes = []
        self.write_count = 0
        self.is_open = True
        self.timeout = None
        self.write_timeout = None

    def write(self, data):
        self.write_count += 1
        if len(self.writes) < 5:
            self.writes.append(bytes(data))
        return len(data)

    def flush(self):
        return None

    def read(self, size):
        if not self.read_buffer:
            return b""
        chunk = self.read_buffer[:size]
        del self.read_buffer[:size]
        return bytes(chunk)

    @property
    def in_waiting(self):
        return len(self.read_buffer)

    def close(self):
        self.is_open = False


def make_spi_frame(payload, header=b"\x00\x00\x00"):
    frame = bytearray(header)
    frame.extend(payload)
    frame.append(sum(frame) & 0xFF)
    return bytes(frame)


def test_command_notify_success():
    uart = RT4DUART()
    fake = FakeSerial(read_bytes=b"\x06")
    uart.port = fake

    assert uart.command_notify() is True
    assert fake.writes[0] == bytes([0x34, 0x00, 0x00, 0x10, 0x44])


def test_command_notify_timeout():
    uart = RT4DUART()
    uart.port = FakeSerial()

    assert uart.command_notify() is False


def test_command_close_writes_termination():
    uart = RT4DUART()
    fake = FakeSerial()
    uart.port = fake

    assert uart.command_close() is True
    assert fake.writes[0] == bytes([0x34, 0x52, 0x05, 0xEE, 0x79])


def test_command_read_spi_returns_payload():
    payload = bytes(range(256)) * 4  # 1024 bytes
    frame = make_spi_frame(payload, header=b"\x10\x20\x30")

    uart = RT4DUART()
    fake = FakeSerial(read_bytes=frame)
    uart.port = fake

    result = uart.command_read_spi(0x4020)
    assert result == payload
    expected_cmd = bytes([0x52, 0x40, 0x20, (0x52 + 0x40 + 0x20) & 0xFF])
    assert fake.writes[0] == expected_cmd


def test_command_read_spi_invalid_checksum_returns_none():
    payload = bytes(range(256)) * 4
    frame = bytearray(make_spi_frame(payload))
    frame[-1] ^= 0xFF  # corrupt checksum

    uart = RT4DUART()
    fake = FakeSerial(read_bytes=bytes(frame))
    uart.port = fake

    assert uart.command_read_spi(0x0001) is None


def test_command_write_spi_writes_full_blocks():
    data = bytes(range(256)) * 8  # 2048 bytes
    ack_bytes = b"\x06" * 2

    uart = RT4DUART()
    fake = FakeSerial(read_bytes=ack_bytes)
    uart.port = fake

    assert uart.command_write_spi(data, region=0x91, start=0, size=len(data)) is True
    assert fake.write_count == 2
    first = fake.writes[0]
    second = fake.writes[1]
    assert first[0] == 0x91 and first[1:3] == b"\x00\x00"
    assert second[0] == 0x91 and second[1:3] == b"\x00\x01"
    assert first[3:3 + 1024] == data[:1024]
    assert second[3:3 + 1024] == data[1024:2048]


def test_command_write_spi_nacks_fail():
    data = bytes(range(256)) * 4
    uart = RT4DUART()
    fake = FakeSerial(read_bytes=b"\x00")
    uart.port = fake

    assert uart.command_write_spi(data, region=0x91, start=0, size=len(data)) is False


def test_write_spi_region_validates_size():
    uart = RT4DUART()
    region = SPI_REGIONS["channels"]
    fake = FakeSerial(read_bytes=b"\x06" * math.ceil(region["size"] / 1024))
    uart.port = fake
    good = bytes([0xAA]) * region["size"]
    assert uart.write_spi_region(good, "channels") is True

    assert uart.write_spi_region(good + b"\x00", "channels") is False


def test_addressbook_writer_frames_blocks_and_reports_progress():
    data = bytes(range(200)) * 8  # 1600 bytes
    total_len = len(data) + 4
    blocks = math.ceil(total_len / 1024)
    fake = FakeSerial(read_bytes=b"\x06" * blocks)
    uart = RT4DUART()
    uart.port = fake

    progress = []

    def progress_cb(current, total):
        progress.append((current, total))

    assert uart.command_write_addressbook(data, progress_cb) is True
    assert fake.write_count == blocks
    assert progress == [(1, blocks), (2, blocks)]

    first_packet = fake.writes[0]
    assert first_packet[0] == 0xA4 and first_packet[1:3] == b"\x00\x00"
    first_payload = first_packet[3:3 + 1024]
    length = int.from_bytes(first_payload[:4], "big")
    assert length == total_len
    assert first_payload[4:4 + 1020] == data[:1020]

    second_packet = fake.writes[1]
    assert second_packet[1:3] == b"\x00\x01"
    second_payload = second_packet[3:3 + 1024]
    remainder = data[1020:]
    assert second_payload[: len(remainder)] == remainder
    assert all(byte == 0xFF for byte in second_payload[len(remainder):])


def test_addressbook_writer_enforces_max_size():
    max_size = 29360124
    data = b"A" * (max_size + 100)
    total_len = max_size + 4
    blocks = math.ceil(total_len / 1024)
    fake = FakeSerial(read_bytes=b"\x06" * blocks)

    uart = RT4DUART()
    uart.port = fake

    progress = {"count": 0, "last": None}

    def progress_cb(current, total):
        progress["count"] += 1
        progress["last"] = (current, total)

    assert uart.command_write_addressbook(data, progress_cb) is True
    assert progress["count"] == blocks
    assert progress["last"] == (blocks, blocks)
    first_packet = fake.writes[0]
    length = int.from_bytes(first_packet[3:7], "big")
    assert length == max_size + 4
    assert fake.write_count == blocks
