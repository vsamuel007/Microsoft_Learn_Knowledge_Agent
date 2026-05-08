import argparse


def _normalize_host(host: str, public_base_url: str | None) -> str:
    if public_base_url:
        return public_base_url.rstrip("/")

    if host in {"0.0.0.0", "::"}:
        # Bind-all addresses are not routable for clients; use localhost for local testing.
        host = "127.0.0.1"

    return f"http://{host}"


def _endpoint_suffix(transport: str) -> str:
    if transport == "sse":
        return "/sse"
    if transport == "streamable-http":
        return "/mcp"
    raise ValueError("stdio transport has no remote MCP URL")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print the exact SKILL_GAP_MCP_SERVER_URL value for the current server mode."
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        required=True,
        help="Server transport mode.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Server host (ignored when --public-base-url is set).")
    parser.add_argument("--port", type=int, default=8000, help="Server port (ignored when --public-base-url is set).")
    parser.add_argument(
        "--public-base-url",
        default="",
        help="Public base URL, e.g. https://abc123.ngrok-free.app",
    )

    args = parser.parse_args()

    if args.transport == "stdio":
        print("SKILL_GAP_MCP_SERVER_URL is not applicable for stdio mode.")
        print("Use this only for portal/remote mode (sse or streamable-http).")
        return

    base = _normalize_host(args.host, args.public_base_url or None)
    if not args.public_base_url:
        base = f"{base}:{args.port}"

    url = f"{base}{_endpoint_suffix(args.transport)}"

    print(url)
    print(f"SKILL_GAP_MCP_SERVER_URL={url}")


if __name__ == "__main__":
    main()
