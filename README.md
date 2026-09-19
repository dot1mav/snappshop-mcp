# 🛒 SnappShop MCP Server

A high-performance Model Context Protocol (MCP) server for [SnappShop](https://snappshop.ir). This project allows LLMs (like Claude) to search for products, fetch detailed specifications, and browse categories from SnappShop in real-time.

## 🌟 Key Features

- **Dual-Runtime Architecture**:
  - **Python Server**: For local development and power users.
  - **ArvanCloud Edge**: A serverless, Iranian-edge implementation for global users and zero-latency access.
- **API-Driven**: Replaced unreliable HTML scraping with a direct integration of the `apix.snappshop.ir` JSON API.
- **Strict Normalization**: Ensures identical data shapes between Python and JavaScript runtimes.
- **Currency Safety**: Explicitly handles the Toman/Rial (1:10) conversion to prevent pricing errors.

## 🛠️ Architecture

### 🧬 Normalization Contract
To ensure the LLM receives consistent data regardless of the transport layer, both runtimes follow a shared contract:
- **ProductCard**: Standardized search result containing price, slug, and rating.
- **ProductDetail**: Comprehensive detail including attributes, images, and vendor offers.

### 🌐 Deployment Options

### 1. Local Python Server
Run as a local process for Claude Desktop.
```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python server.py
```

### 2. ArvanCloud Edge (Recommended for Production)
Deploy the unified JavaScript worker to ArvanCloud Edge for direct access to the Iranian API.
- **File**: `worker/src/arvan_edge_mcp.js`
- **Benefits**: No VPN required, ultra-low latency, serverless scaling.

## ⚙️ Claude Desktop Configuration

Add the following to your `claude_desktop_config.json`:

### Using Local Python:
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

### Using ArvanCloud Edge:
```json
{
  "mcpServers": {
    "snappshop-edge": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/inspector",
        "https://your-edge-function.arvancloud.ir"
      ]
    }
  }
}
```

## 📁 Project Structure

- `snappshop/`: Python core logic (Normalization, API, Units).
- `worker/`: ArvanCloud Edge implementation.
- `fixtures/`: Live API samples for regression testing.
- `contract.md`: Definition of the shared data shapes.

---
Developed for the MCP ecosystem. 🚀
