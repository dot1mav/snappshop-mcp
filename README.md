# 🛒 SnappShop MCP Server

A high-performance Model Context Protocol (MCP) server for [SnappShop](https://snappshop.ir). This project allows LLMs (like Claude) to search for products, fetch detailed specifications, and browse categories from SnappShop in real-time.

## 🌟 Key Features

- **Dual-Runtime Architecture**:
  - **Python Server**: For local development and power users.
  - **ArvanCloud Edge**: A serverless, Iranian-edge implementation for global users and zero-latency access.
- **API-Driven**: Replaced unreliable HTML scraping with a direct integration of the `apix.snappshop.ir` JSON API.
- **Strict Normalization**: Ensures identical data shapes between Python and JavaScript runtimes.
- **Currency Safety**: Explicitly handles the Toman/Rial (1:10) conversion to prevent pricing errors.

## 🚀 Quick Test (Live Demo)
You can test the MCP protocol implementation directly via the ArvanCloud Edge deployment:
👉 **Live Endpoint**: `https://snappshop.dr98mav-hhdrz.arvanedge.ir`

**Test it in your browser:**
- List Tools: `https://snappshop.dr98mav-hhdrz.arvanedge.ir/tools`
- *Note: The `/call` endpoint requires a JSON POST request to execute tools.*

## 📖 What is MCP?
The **Model Context Protocol (MCP)** is an open standard that allows AI models to connect to external tools and data sources. Instead of the AI just "guessing" or using old training data, an MCP server gives the AI **real-time capabilities**.

**How it works with SnappShop:**
1. **Claude** realizes you want to find a product on SnappShop.
2. **Claude** sends a request to the MCP server: `"Call search_products with query='Samsung Galaxy'"`.
3. **The Server** fetches live data from the API, normalizes it, and sends it back.
4. **Claude** reads the live data and gives you an accurate answer with real prices and links.

## 🛠️ Deployment & Configuration

### 1. Local Python Server
Best for users with a local Python environment.
```bash
pip install -r requirements.txt
python server.py
```

### 2. ArvanCloud Edge (Production)
Deploy `worker/src/arvan_edge_mcp.js` to ArvanCloud Edge. This is the recommended way for global users as it handles the Iranian network egress automatically.

## ⚙️ Claude Desktop Configuration

Add the following to your `claude_desktop_config.json` (usually located at `%APPDATA%\Claude\claude_desktop_config.json` on Windows).

### Option A: Using Local Python (Direct)
```json
{
  "mcpServers": {
    "snappshop-local": {
      "command": "python",
      "args": ["C:/path/to/snappshop-mcp/server.py"]
    }
  }
}
```

### Option B: Using the ArvanCloud Edge (via Inspector Bridge)
Since Claude Desktop expects a local process, we use the MCP Inspector to tunnel the remote Edge server into Claude.
```json
{
  "mcpServers": {
    "snappshop-edge": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/inspector",
        "https://snappshop.dr98mav-hhdrz.arvanedge.ir"
      ]
    }
  }
}
```

## 📁 Project Structure
- `snappshop/`: Python core logic.
- `worker/`: ArvanCloud Edge implementation.
- `fixtures/`: Live API samples for testing.
- `contract.md`: The shared data specification.

---
Developed for the MCP ecosystem. 🚀
