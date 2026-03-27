# eink-mcp

An MCP server that lets AI agents draw on or clear a Waveshare 7.5" V2 e-ink display (800×480).

## Tools

| Tool | Description |
|------|-------------|
| `get_display_info` | Returns display width and height in pixels |
| `clear_display` | Clears the display to white |
| `draw` | Renders a list of drawing elements onto the display |

### Drawing elements

All elements are passed as a list to `draw`. Each must have a `type` field.

**text**
```json
{ "type": "text", "text": "Hello", "x": 10, "y": 10, "size": 24, "fill": 0, "font": null }
```
- `font` — optional path to a `.ttf` file; defaults to DejaVuSansMono

**rect**
```json
{ "type": "rect", "x0": 10, "y0": 10, "x1": 200, "y1": 80, "outline": 0, "fill": null }
```

**line**
```json
{ "type": "line", "x0": 0, "y0": 0, "x1": 800, "y1": 480, "fill": 0, "width": 2 }
```

**ellipse**
```json
{ "type": "ellipse", "x0": 100, "y0": 100, "x1": 300, "y1": 300, "outline": 0, "fill": null }
```

Colour values: `0` = black, `255` = white, any integer 0–255 for greyscale.

## Hardware

- Raspberry Pi (any model with GPIO)
- [Waveshare 7.5inch e-Paper HAT V2](https://www.waveshare.com/7.5inch-e-paper-hat.htm) (800×480)

## Setup

**1. System packages**

```bash
sudo apt install python3-full python3-venv fonts-dejavu
```

**2. Virtual environment**

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

**3. Waveshare e-Paper library** (not on PyPI — clone it inside the project directory)

```bash
git clone https://github.com/waveshare/e-Paper
venv/bin/pip install ./e-Paper/RaspberryPi_JetsonNano/python/
```

After setup the directory should look like this:

```
eink-mcp/
├── server.py
├── display.py
├── requirements.txt
├── venv/          <- created by you, not in git
└── e-Paper/       <- cloned by you, not in git
```

## Running the server

```bash
venv/bin/python server.py
```

The server uses stdio transport (default for MCP).

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "eink-display": {
      "command": "/path/to/eink-mcp/venv/bin/python",
      "args": ["/path/to/eink-mcp/server.py"]
    }
  }
}
```

### Claude Code

```bash
claude mcp add eink-display /path/to/eink-mcp/venv/bin/python -- /path/to/eink-mcp/server.py
```

## Testing

Once added, ask Claude directly in the chat:

**Check the server is connected and get display dimensions:**
```
What is the eink display size?
```

**Draw something:**
```
Draw "Hello from Claude" in large text centered on the eink display
```

**Clear the display:**
```
Clear the eink display
```

Claude will pick up the `get_display_info`, `draw`, and `clear_display` tools automatically. On a Mac without Pi hardware, tool calls still succeed — a `WARNING Hardware not available` line appears in the server's stderr log instead of writing to the display.

## Configuration

| Environment variable | Default | Description |
|----------------------|---------|-------------|
| `EINK_FONT_PATH` | `/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf` | Default font for text elements |

## Development

Install dev dependencies:

```bash
venv/bin/pip install -r requirements-dev.txt
```

**Lint and format:**

```bash
ruff check .
ruff check --fix .
ruff format .
```

If the Waveshare hardware is unavailable (e.g. on a Mac), `draw` and `clear_display` log a dry-run message instead of crashing, so you can develop and test tool schemas without a Pi.

## Troubleshooting

**`No module named 'waveshare_epd'`**
```bash
venv/bin/pip install ./e-Paper/RaspberryPi_JetsonNano/python/
```

**`No module named 'spidev'` / `No module named 'lgpio'`**
```bash
venv/bin/pip install -r requirements.txt
```

**SPI not enabled**
```bash
sudo raspi-config nonint do_spi 0
sudo reboot
```
