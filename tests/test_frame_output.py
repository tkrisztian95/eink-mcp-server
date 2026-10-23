import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from display import EinkDisplay  # noqa: E402


def _test_image(display: EinkDisplay) -> Image.Image:
    image = Image.new("L", (display.width, display.height), 255)
    draw = ImageDraw.Draw(image)
    draw.rectangle([10, 10, 200, 100], fill=0)
    draw.line([(0, display.height - 1), (display.width - 1, 0)], fill=0, width=3)
    return image


def test_file_mode_is_available_without_hardware(tmp_path):
    display = EinkDisplay(output="file", frame_dir=str(tmp_path))
    assert display.is_available
    assert not display._available


def test_send_writes_raw_frame_that_round_trips(tmp_path):
    display = EinkDisplay(output="file", frame_dir=str(tmp_path))
    image = _test_image(display)
    display.send(image)

    data = (tmp_path / "frame.bin").read_bytes()
    assert len(data) == display.width * display.height // 8

    decoded = Image.frombytes("1", (display.width, display.height), data)
    assert decoded.tobytes() == image.convert("1").tobytes()
    # Bit meaning: 1 = white, MSB = leftmost pixel. Top-left pixel is white, (10, 10) black.
    assert data[0] & 0x80
    assert decoded.getpixel((10, 10)) == 0

    with Image.open(tmp_path / "frame.png") as png:
        assert png.tobytes() == decoded.tobytes()
    assert not list(tmp_path.glob("*.tmp"))


def test_clear_publishes_all_white_frame(tmp_path):
    display = EinkDisplay(output="file", frame_dir=str(tmp_path))
    display.clear()
    data = (tmp_path / "frame.bin").read_bytes()
    assert data == b"\xff" * (display.width * display.height // 8)


def test_render_publishes_rotated_frame(tmp_path):
    display = EinkDisplay(output="file", frame_dir=str(tmp_path))
    display.render([{"type": "rect", "x0": 0, "y0": 0, "x1": 9, "y1": 9, "fill": 0}], rotation=180)
    decoded = Image.frombytes(
        "1", (display.width, display.height), (tmp_path / "frame.bin").read_bytes()
    )
    # A black square at the top-left ends up bottom-right after a 180° rotation.
    assert decoded.getpixel((display.width - 1, display.height - 1)) == 0
    assert decoded.getpixel((0, 0)) == 255


def test_wrong_size_frame_is_skipped(tmp_path):
    display = EinkDisplay(output="file", frame_dir=str(tmp_path))
    display.send(Image.new("L", (100, 100), 255))
    assert not (tmp_path / "frame.bin").exists()
