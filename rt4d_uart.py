"""RT-4D UART Communication Protocol

Ported from the C# RT_4D_UART class
"""

import serial
import time
from typing import Optional


class RT4DUART:
    """Communication with RT-4D radio via UART/Serial"""

    def __init__(self):
        self.port: Optional[serial.Serial] = None
        self.read_timeout = 10.0  # seconds
        self.write_timeout = 2.0  # seconds

    def open(self, port_name: str, baudrate: int = 115200):
        """Open serial port connection"""
        self.port = serial.Serial(
            port=port_name,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=self.read_timeout,
            write_timeout=self.write_timeout
        )
        if not self.port.is_open:
            raise IOError(f"Failed to open port {port_name}")

    def close(self):
        """Close serial port"""
        if self.port and self.port.is_open:
            self.port.close()

    def _checksum(self, command: bytearray) -> int:
        """Calculate checksum for command"""
        total = sum(command[:-1])
        return total & 0xFF

    def _verify(self, command: bytes) -> bool:
        """Verify checksum of received data"""
        if len(command) == 0:
            return False
        total = sum(command[:-1])
        return (total & 0xFF) == command[-1]

    def command_notify(self) -> bool:
        """Send notify command to radio"""
        command = bytearray([0x34, 0x00, 0x00, 0x10, 0x00])
        command[-1] = self._checksum(command)

        self.port.write(command)
        self.port.flush()

        try:
            response = self.port.read(1)
            if len(response) == 0:
                print("Timeout waiting for notify response")
                return False
            if response[0] != 0x06:
                print(f"Unexpected notify response: 0x{response[0]:02X}")
                return False
            return True
        except Exception as e:
            print(f"Error in command_notify: {e}")
            return False

    def command_close(self) -> bool:
        """Send close command to radio"""
        command = bytes([0x34, 0x52, 0x05, 0xEE, 0x79])

        try:
            self.port.write(command)
            self.port.flush()
            return True
        except Exception as e:
            print(f"Error closing connection: {e}")
            return False

    def command_read_spi(self, offset: int) -> Optional[bytes]:
        """Read 1KB block from SPI flash at given offset (in KB)"""
        command = bytearray([0x52, 0x00, 0x00, 0x00])
        command[1] = (offset >> 8) & 0xFF
        command[2] = (offset >> 0) & 0xFF
        command[3] = self._checksum(command)

        self.port.write(command)
        self.port.flush()

        # Read 1024 + 4 bytes (data + header + checksum)
        block = bytearray()
        while len(block) < 1028:
            chunk = self.port.read(1028 - len(block))
            if len(chunk) == 0:
                print(f"Timeout reading SPI block at offset 0x{offset:04X}")
                return None
            block.extend(chunk)

        # Check for error response
        if block[0] == 0xFF:
            return None

        # Verify checksum
        if not self._verify(block):
            print(f"Checksum error reading SPI block at 0x{offset:04X}")
            return None

        # Return data only (skip 3-byte header and checksum)
        return bytes(block[3:1027])

    def command_write_spi(self, data: bytes, region: int, start: int, size: int) -> bool:
        """Write data to SPI flash region"""
        command = bytearray(1028)  # 1024 data + 4 header

        for i in range(0, size, 1024):
            command[0] = region
            command[1] = ((i // 1024) >> 8) & 0xFF
            command[2] = ((i // 1024) >> 0) & 0xFF

            # Copy 1KB of data
            chunk_size = min(1024, size - i)
            command[3:3 + chunk_size] = data[start + i:start + i + chunk_size]

            # Calculate checksum
            command[1027] = self._checksum(command)

            # Send command
            self.port.write(command)
            self.port.flush()

            # Wait for ACK
            try:
                response = self.port.read(1)
                if len(response) == 0:
                    print(f"Timeout waiting for write ACK at offset {i}")
                    return False
                if response[0] != 0x06:
                    print(f"Unexpected write response: 0x{response[0]:02X}")
                    return False
            except Exception as e:
                print(f"Error writing SPI: {e}")
                return False

        return True

    def is_bootloader_mode(self) -> bool:
        """Check if radio is in bootloader mode"""
        data = self.command_read_spi(0)

        if data is not None:
            return False  # Normal mode

        # Clear any pending data
        for _ in range(8):
            if self.port.in_waiting == 0:
                break
            self.port.read(1)

        return True  # Bootloader mode

    def read_spi_dump(self, output_file: str) -> bool:
        """Read complete SPI flash to file (4MB)"""
        print("Reading SPI flash...")

        with open(output_file, 'wb') as f:
            for i in range(4096):  # 4096 KB = 4 MB
                percentage = (i / 4096) * 100
                print(f"\rReading SPI flash: {percentage:.1f}%", end='', flush=True)

                data = self.command_read_spi(i)
                if data is None:
                    print(f"\nFailed to read SPI flash at 0x{i:04X}")
                    return False

                f.write(data)

        print("\rReading complete" + " " * 30)
        return True

    def read_spi_region(self, address: int, size: int) -> Optional[bytes]:
        """Read a specific region from SPI flash"""
        data = bytearray()
        kb_offset = address // 1024  # Convert byte address to KB offset
        num_blocks = (size + 1023) // 1024  # Round up to nearest KB

        for i in range(num_blocks):
            block_data = self.command_read_spi(kb_offset + i)
            if block_data is None:
                print(f"\nFailed to read SPI block at 0x{kb_offset + i:04X}")
                return None
            data.extend(block_data)

        # Return only the requested size
        return bytes(data[:size])

    def write_spi_region(self, data: bytes, region_name: str) -> bool:
        """Write data to a specific SPI region"""
        from rt4d_codeplug.constants import SPI_REGIONS

        if region_name not in SPI_REGIONS:
            print(f"Unknown region: {region_name}")
            return False

        region_info = SPI_REGIONS[region_name]
        region_id = region_info["region_id"]
        address = region_info["address"]
        size = region_info["size"]

        if len(data) > size:
            print(f"Data too large for region {region_name}: {len(data)} > {size}")
            return False

        print(f"Writing {len(data)} bytes to {region_name}...")
        return self.command_write_spi(data, region_id, 0, len(data))

    def command_write_addressbook(self, data: bytes, progress_callback=None) -> bool:
        """Write global contacts (address book) to radio

        Args:
            data: GBK-encoded CSV data (first 6 columns, no header)
            progress_callback: Optional callback(current_block, total_blocks) for progress

        Returns:
            True if successful, False otherwise
        """
        # Prepare data with header
        MAX_SIZE = 29360124  # 28MB max
        data_len = min(len(data), MAX_SIZE)

        # Build payload: 4-byte length header + data
        total_len = data_len + 4
        payload = bytearray(total_len)

        # Write length as 32-bit big-endian
        payload[0] = (total_len >> 24) & 0xFF
        payload[1] = (total_len >> 16) & 0xFF
        payload[2] = (total_len >> 8) & 0xFF
        payload[3] = (total_len) & 0xFF

        # Copy data
        payload[4:4 + data_len] = data[:data_len]

        # Calculate number of 1KB blocks
        num_blocks = (total_len + 1023) // 1024

        print(f"Writing {len(data):,} bytes ({num_blocks} blocks) to address book...")

        # Send blocks
        for block_num in range(num_blocks):
            # Prepare 1028-byte packet
            packet = bytearray(1028)

            # Command and block number
            packet[0] = 0xA4  # Address book write command
            packet[1] = (block_num >> 8) & 0xFF
            packet[2] = (block_num) & 0xFF

            # Copy 1KB of data
            start_offset = block_num * 1024
            end_offset = min(start_offset + 1024, total_len)
            chunk_size = end_offset - start_offset

            # Fill data bytes
            for i in range(1024):
                if start_offset + i < total_len:
                    packet[3 + i] = payload[start_offset + i]
                else:
                    packet[3 + i] = 0xFF  # Pad with 0xFF

            # Calculate checksum
            packet[1027] = self._checksum(packet)

            # Send packet
            try:
                self.port.write(packet)
                self.port.flush()
            except Exception as e:
                print(f"\nError writing block {block_num}: {e}")
                return False

            # Wait for response
            try:
                response = self.port.read(1)
                if len(response) == 0:
                    print(f"\nTimeout waiting for ACK at block {block_num}")
                    return False

                if response[0] == 0x06:
                    # Success - continue
                    if progress_callback:
                        progress_callback(block_num + 1, num_blocks)
                elif response[0] == 0xA4:
                    print(f"\nFlash IC capacity mismatch!")
                    return False
                elif response[0] == 0x4A:
                    print(f"\nFlash IC capacity limit reached!")
                    return False
                else:
                    print(f"\nUnexpected response: 0x{response[0]:02X}")
                    return False

            except Exception as e:
                print(f"\nError reading response at block {block_num}: {e}")
                return False

        print("\nAddress book write complete!")
        return True
