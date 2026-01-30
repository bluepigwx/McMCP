from .server import mcp


def main():
    mcp.run(transport="http", host="127.0.0.1", port=8000)
    

if __name__ == "__main__":
    main()