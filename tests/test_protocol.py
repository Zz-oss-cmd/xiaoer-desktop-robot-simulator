import unittest
import random

from robot_sim.protocol import (
    HEADER,
    Command,
    ProtocolFrame,
    StreamParser,
    crc16_modbus,
    encode_frame,
)


class ProtocolTests(unittest.TestCase):
    def test_crc16_modbus_reference_vector(self) -> None:
        self.assertEqual(crc16_modbus(b"123456789"), 0x4B37)

    def test_encode_and_parse_round_trip(self) -> None:
        expected = ProtocolFrame(Command.CONTROL, 7, b"dance")
        self.assertEqual(StreamParser().feed(encode_frame(expected), 0), [expected])

    def test_frame_split_one_byte_at_a_time(self) -> None:
        expected = ProtocolFrame(Command.SENSOR_DATA, 8, bytes(range(8)))
        parser = StreamParser()
        actual = []
        for now_ms, value in enumerate(encode_frame(expected)):
            actual.extend(parser.feed(bytes((value,)), now_ms))
        self.assertEqual(actual, [expected])

    def test_multiple_sticky_frames(self) -> None:
        expected = [
            ProtocolFrame(Command.HEARTBEAT, 1),
            ProtocolFrame(Command.DEVICE_STATUS, 2, b"\x01\x02\x03\x04"),
            ProtocolFrame(Command.CONTROL, 3, b"stop"),
        ]
        stream = b"".join(encode_frame(frame) for frame in expected)
        self.assertEqual(StreamParser().feed(stream, 0), expected)

    def test_noise_and_header_bytes_inside_payload(self) -> None:
        expected = ProtocolFrame(Command.CONTROL, 9, b"x" + HEADER + b"y")
        parser = StreamParser()
        self.assertEqual(parser.feed(b"\x00\xFFnoise" + encode_frame(expected), 0), [expected])
        self.assertEqual(parser.stats.discarded_noise_bytes, 7)

    def test_crc_error_recovers_to_next_frame(self) -> None:
        damaged = bytearray(encode_frame(ProtocolFrame(Command.CONTROL, 1, b"bad")))
        damaged[-1] ^= 0xFF
        expected = ProtocolFrame(Command.HEARTBEAT, 2)
        parser = StreamParser()
        self.assertEqual(parser.feed(bytes(damaged) + encode_frame(expected), 0), [expected])
        self.assertEqual(parser.stats.crc_errors, 1)

    def test_invalid_length_recovers_to_next_frame(self) -> None:
        invalid = HEADER + bytes((1, int(Command.CONTROL), 1)) + (129).to_bytes(2, "little")
        expected = ProtocolFrame(Command.HEARTBEAT, 2)
        parser = StreamParser()
        self.assertEqual(parser.feed(invalid + encode_frame(expected), 0), [expected])
        self.assertEqual(parser.stats.length_errors, 1)

    def test_bad_version_and_unknown_command_are_filtered(self) -> None:
        bad_version = bytearray(encode_frame(ProtocolFrame(Command.HEARTBEAT, 1)))
        bad_version[2] = 2
        bad_version[-2:] = crc16_modbus(bytes(bad_version[2:-2])).to_bytes(2, "little")
        unknown_body = bytes((1, 0x99, 2, 0, 0))
        unknown = HEADER + unknown_body + crc16_modbus(unknown_body).to_bytes(2, "little")
        parser = StreamParser()
        self.assertEqual(parser.feed(bytes(bad_version) + unknown, 0), [])
        self.assertEqual(parser.stats.version_errors, 1)
        self.assertEqual(parser.stats.unknown_commands, 1)

    def test_partial_frame_timeout_resets_parser(self) -> None:
        parser = StreamParser()
        parser.feed(HEADER + b"\x01", 10)
        self.assertFalse(parser.poll_timeout(109))
        self.assertTrue(parser.poll_timeout(110))
        self.assertEqual(parser.buffered_bytes, 0)
        self.assertEqual(parser.stats.partial_timeouts, 1)

    def test_slow_drip_cannot_extend_absolute_frame_timeout(self) -> None:
        frame = encode_frame(ProtocolFrame(Command.CONTROL, 1, b"slow"))
        parser = StreamParser()
        parser.feed(frame[:2], 0)
        parser.feed(frame[2:3], 60)
        parser.feed(frame[3:4], 99)
        self.assertTrue(parser.poll_timeout(100))

    def test_buffer_limit_is_enforced(self) -> None:
        parser = StreamParser(max_buffer=16)
        parser.feed(b"x" * 32, 0)
        self.assertLessEqual(parser.buffered_bytes, 16)
        self.assertEqual(parser.stats.buffer_overflows, 1)

    def test_ten_thousand_frames_with_random_chunking(self) -> None:
        randomizer = random.Random(20260803)
        expected = [
            ProtocolFrame(Command.CONTROL, index & 0xFF, bytes((index & 0xFF,)))
            for index in range(10_000)
        ]
        stream = b"".join(encode_frame(frame) for frame in expected)
        parser = StreamParser()
        actual = []
        offset = 0
        now_ms = 0
        while offset < len(stream):
            chunk_size = randomizer.randint(1, 97)
            actual.extend(parser.feed(stream[offset : offset + chunk_size], now_ms))
            offset += chunk_size
            now_ms += 1
        self.assertEqual(actual, expected)
        self.assertEqual(parser.stats.valid_frames, 10_000)
        self.assertEqual(parser.stats.crc_errors, 0)


if __name__ == "__main__":
    unittest.main()
