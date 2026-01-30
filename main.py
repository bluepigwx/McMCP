from fastmcp import FastMCP
import sys

mcp = FastMCP("My MCP Server")

@mcp.tool
def greet(name: str) -> str:
    print(f"greet {name}")
    return f"Hello,asetseryw {name}!"

@mcp.tool
def add(a: int, b: int) -> int:
    print(f"add {a} + {b}")
    """Add two numbers together"""
    return a + b + 1

def main():
    # 检查命令行参数决定使用哪种模式
    if "--http" in sys.argv:
        print("Starting MCP server in HTTP mode on http://localhost:8000")
        print("MCP endpoint: http://localhost:8000/mcp")
        # HTTP模式（使用Streamable HTTP协议）
        mcp.run(transport="http", host="127.0.0.1", port=8000)
    else:
        print("Starting MCP server in stdio mode")
        # stdio模式（默认）
        mcp.run()


if __name__ == "__main__":
    main()
