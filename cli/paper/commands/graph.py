"""Graph/tracing subcommand handlers for paper CLI."""

import argparse

from cli.paper.errors import ExternalServiceError, UserInputError
from cli.paper.output import emit_json, emit_result, should_emit_json


def _cmd_trace(args: argparse.Namespace) -> None:
    """Trace a symbol's callers, callees, or call path using Trifecta.

    Useful for code review, understanding impact, and verifying reachability.
    """
    from clients.trifecta import get_trifecta_client

    client = get_trifecta_client()
    if client is None:
        raise ExternalServiceError(
            "Trifecta not enabled. Set MCP_TRIFECTA_MODE=real to use code tracing."
        )

    action = args.action
    symbol = args.symbol

    if action == "callers":
        result = client.find_callers(symbol, depth=args.depth)
        if not result.success:
            raise ExternalServiceError(str(result.error))
        if should_emit_json(args):
            emit_json(result.data)
        else:
            if not result.data:
                emit_result(f"No callers found for: {symbol}")
            else:
                emit_result(f"Callers of {symbol} (depth={args.depth}):")
                for caller in result.data:
                    name = caller.get("symbol_name", caller.get("qualified_name", "?"))
                    file_rel = caller.get("file_rel", "?")
                    emit_result(f"  {file_rel}::{name}")

    elif action == "callees":
        result = client.find_callees(symbol)
        if not result.success:
            raise ExternalServiceError(str(result.error))
        if should_emit_json(args):
            emit_json(result.data)
        else:
            if not result.data:
                emit_result(f"No callees found for: {symbol}")
            else:
                emit_result(f"Callees of {symbol}:")
                for callee in result.data:
                    name = callee.get("symbol_name", callee.get("qualified_name", "?"))
                    file_rel = callee.get("file_rel", "?")
                    emit_result(f"  {file_rel}::{name}")

    elif action == "path":
        if not args.to_symbol:
            raise UserInputError("--to SYMBOL required for path action")
        result = client.find_path(symbol, args.to_symbol)
        if not result.success:
            raise ExternalServiceError(str(result.error))
        if should_emit_json(args):
            emit_json(result.data)
        else:
            data = result.data
            if data.get("path_exists") or data.get("path"):
                emit_result(f"Path from {symbol} to {args.to_symbol}:")
                for hop in data.get("path") or []:
                    emit_result(f"  → {hop}")
            else:
                emit_result(f"No path found from {symbol} to {args.to_symbol}")


def _cmd_graph_overview(args: argparse.Namespace) -> None:
    """Show graph overview: nodes, edges, cycles, orphans, top hubs."""

    from clients.trifecta import get_trifecta_client

    client = get_trifecta_client()
    if client is None:
        raise ExternalServiceError(
            "Trifecta not enabled. Set MCP_TRIFECTA_MODE=real to use graph overview."
        )

    result = client.find_overview()
    if not result.success:
        raise ExternalServiceError(str(result.error))

    data = result.data
    if should_emit_json(args):
        emit_json(data)
    else:
        emit_result("Graph Overview")
        emit_result(f"  Nodes: {data.get('node_count', '?')}")
        emit_result(f"  Edges: {data.get('edge_count', '?')}")
        emit_result(f"  Cycles (calls): {data.get('calls_cycles', '?')}")
        emit_result(f"  Cycles (imports): {data.get('imports_cycles', '?')}")
        emit_result(f"  Cycles (inherits): {data.get('inherits_cycles', '?')}")
        emit_result(f"  Orphans: {data.get('orphan_count', '?')}")
        top_hubs = data.get("top_hubs") or []
        if top_hubs:
            emit_result("  Top Hubs:")
            for hub in top_hubs[:5]:
                name = hub.get("symbol_name", hub.get("qualified_name", "?"))
                in_deg = hub.get("in_degree", "?")
                emit_result(f"    {name} (in_degree={in_deg})")
