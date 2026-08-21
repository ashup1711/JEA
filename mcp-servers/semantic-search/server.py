"""Lightweight code search MCP server - no heavy dependencies."""
import json
import re
from collections import Counter
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("semantic-search")

_index: dict[str, str] = {}
_file_paths: list[str] = []
_indexed = False


def _tokenize(text: str) -> list[str]:
    """Simple tokenizer: lowercase, split on non-alphanumeric."""
    return re.findall(r"[a-z_][a-z0-9_]*", text.lower())


def _score_document(query_tokens: list[str], doc_tokens: list[str]) -> float:
    """Score document relevance using token overlap."""
    if not query_tokens or not doc_tokens:
        return 0.0
    query_set = set(query_tokens)
    doc_counter = Counter(doc_tokens)
    score = 0.0
    for token in query_set:
        if token in doc_counter:
            score += doc_counter[token]
    return score / (len(query_tokens) * max(len(doc_tokens), 1))


def _index_directory(directory: str, extensions: list[str] | None = None) -> int:
    """Index all files in a directory."""
    global _index, _file_paths, _indexed

    if extensions is None:
        extensions = [".py", ".ts", ".js", ".tsx", ".jsx", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini", ".sh", ".go", ".rs", ".java", ".rb"]

    _index.clear()
    _file_paths.clear()
    root = Path(directory).resolve()

    for ext in extensions:
        for filepath in root.rglob(f"*{ext}"):
            parts = filepath.parts
            if any(p in parts for p in ["node_modules", ".git", "__pycache__", ".venv", "venv", ".chroma", ".mypy_cache", ".ruff_cache"]):
                continue
            try:
                content = filepath.read_text(encoding="utf-8", errors="ignore")
                rel_path = str(filepath.relative_to(root))
                _index[rel_path] = content
            except Exception:
                continue

    _file_paths = list(_index.keys())
    _indexed = True
    return len(_index)


def _search(query: str, top_k: int = 5) -> list[dict]:
    """Search indexed files using token-based relevance scoring."""
    if not _indexed:
        return []

    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    results = []
    for filepath, content in _index.items():
        doc_tokens = _tokenize(content)
        score = _score_document(query_tokens, doc_tokens)
        if score > 0:
            results.append({
                "file": filepath,
                "score": round(score, 4),
                "content": content[:3000],
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def _grep_search(pattern: str, top_k: int = 10) -> list[dict]:
    """Regex search across indexed files."""
    if not _indexed:
        return []

    regex = re.compile(pattern, re.IGNORECASE)
    results = []

    for filepath, content in _index.items():
        lines = content.split("\n")
        matches = []
        for i, line in enumerate(lines, 1):
            if regex.search(line):
                matches.append({"line": i, "text": line.strip()})

        if matches:
            results.append({
                "file": filepath,
                "matches": matches[:10],
                "total_matches": len(matches),
            })

    return results[:top_k]


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="index_directory",
            description="Index all source files in a directory for search",
            inputSchema={
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Directory path to index"},
                    "extensions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "File extensions to index (default: common source files)",
                    },
                },
                "required": ["directory"],
            },
        ),
        Tool(
            name="semantic_search",
            description="Search indexed codebase using relevance scoring. Returns files ranked by relevance to the query.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (natural language or keywords)"},
                    "top_k": {"type": "integer", "description": "Number of results (default: 5)"},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="grep_search",
            description="Search indexed files using regex pattern matching",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern to search for"},
                    "top_k": {"type": "integer", "description": "Max files to return (default: 10)"},
                },
                "required": ["pattern"],
            },
        ),
        Tool(
            name="get_index_stats",
            description="Get statistics about the current index",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "index_directory":
        directory = arguments["directory"]
        extensions = arguments.get("extensions")
        count = _index_directory(directory, extensions)
        return [TextContent(type="text", text=json.dumps({"indexed_files": count, "directory": directory}))]

    elif name == "semantic_search":
        query = arguments["query"]
        top_k = arguments.get("top_k", 5)
        results = _search(query, top_k)
        return [TextContent(type="text", text=json.dumps({"results": results, "query": query, "count": len(results)}))]

    elif name == "grep_search":
        pattern = arguments["pattern"]
        top_k = arguments.get("top_k", 10)
        results = _grep_search(pattern, top_k)
        return [TextContent(type="text", text=json.dumps({"results": results, "pattern": pattern, "count": len(results)}))]

    elif name == "get_index_stats":
        return [TextContent(type="text", text=json.dumps({
            "indexed_files": len(_index),
            "has_index": _indexed,
            "files": _file_paths[:50],
        }))]

    return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
