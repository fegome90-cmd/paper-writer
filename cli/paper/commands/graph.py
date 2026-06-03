"""Graph/tracing subcommand handlers for paper CLI."""

import argparse
import json
import sys


def _cmd_trace(args: argparse.Namespace) -> None:
    """Trace a symbol's callers, callees, or call path using Trifecta.

    Useful for code review, understanding impact, and verifying reachability.
    """
    from clients.trifecta import get_trifecta_client

    client = get_trifecta_client()
    if client is None:
        print(
            "Trifecta not enabled. Set MCP_TRIFECTA_MODE=real to use code tracing.",
            file=sys.stderr,
        )
        sys.exit(1)

    action = args.action
    symbol = args.symbol

    if action == "callers":
        result = client.find_callers(symbol, depth=args.depth)
        if not result.success:
            print(f"Error: {result.error}", file=sys.stderr)
            sys.exit(1)
        if args.output == "json":
            print(json.dumps(result.data, indent=2, ensure_ascii=False))
        else:
            if not result.data:
                print(f"No callers found for: {symbol}")
            else:
                print(f"Callers of {symbol} (depth={args.depth}):")
                for caller in result.data:
                    name = caller.get("symbol_name", caller.get("qualified_name", "?"))
                    file_rel = caller.get("file_rel", "?")
                    print(f"  {file_rel}::{name}")

    elif action == "callees":
        result = client.find_callees(symbol)
        if not result.success:
            print(f"Error: {result.error}", file=sys.stderr)
            sys.exit(1)
        if args.output == "json":
            print(json.dumps(result.data, indent=2, ensure_ascii=False))
        else:
            if not result.data:
                print(f"No callees found for: {symbol}")
            else:
                print(f"Callees of {symbol}:")
                for callee in result.data:
                    name = callee.get("symbol_name", callee.get("qualified_name", "?"))
                    file_rel = callee.get("file_rel", "?")
                    print(f"  {file_rel}::{name}")

    elif action == "path":
        if not args.to_symbol:
            print("Error: --to SYMBOL required for path action", file=sys.stderr)
            sys.exit(1)
        result = client.find_path(symbol, args.to_symbol)
        if not result.success:
            print(f"Error: {result.error}", file=sys.stderr)
            sys.exit(1)
        if args.output == "json":
            print(json.dumps(result.data, indent=2, ensure_ascii=False))
        else:
            data = result.data
            if data.get("path_exists") or data.get("path"):
                print(f"Path from {symbol} to {args.to_symbol}:")
                for hop in data.get("path", []):
                    print(f"  → {hop}")
            else:
                print(f"No path found from {symbol} to {args.to_symbol}")


def _cmd_graph_overview(args: argparse.Namespace) -> None:
    """Show graph overview: nodes, edges, cycles, orphans, top hubs."""

    from clients.trifecta import get_trifecta_client

    client = get_trifecta_client()
    if client is None:
        print(
            "Trifecta not enabled. Set MCP_TRIFECTA_MODE=real to use graph overview.",
            file=sys.stderr,
        )
        sys.exit(1)

    result = client.find_overview()
    if not result.success:
        print(f"Error: {result.error}", file=sys.stderr)
        sys.exit(1)

    data = result.data
    if args.output == "json":
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print("Graph Overview")
        print(f"  Nodes: {data.get('node_count', '?')}")
        print(f"  Edges: {data.get('edge_count', '?')}")
        print(f"  Cycles (calls): {data.get('calls_cycles', '?')}")
        print(f"  Cycles (imports): {data.get('imports_cycles', '?')}")
        print(f"  Cycles (inherits): {data.get('inherits_cycles', '?')}")
        print(f"  Orphans: {data.get('orphan_count', '?')}")
        top_hubs = data.get("top_hubs", [])
        if top_hubs:
            print("  Top Hubs:")
            for hub in top_hubs[:5]:
                name = hub.get("symbol_name", hub.get("qualified_name", "?"))
                in_deg = hub.get("in_degree", "?")
                print(f"    {name} (in_degree={in_deg})")
