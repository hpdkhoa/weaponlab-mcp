"""Drives the labs as another session would: each MCP server over stdio, its tools called by name."""
import asyncio, json, os, sys, time
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

E = os.path.dirname(os.path.abspath(__file__))
VENV = os.path.join(E, "venv", "Scripts")
ENV = dict(os.environ, WEAPONLAB_PROJECT=os.path.join(E, "project"), WEAPONLAB_DIGITIZE=os.path.join(E, "digitize"))


async def server(exe, calls):
    p = StdioServerParameters(command=os.path.join(VENV, exe), args=[], env=ENV)
    out = {}
    async with stdio_client(p) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = (await s.list_tools()).tools
            out["tools"] = len(tools)
            for name, args in calls:
                t = time.time()
                try:
                    res = await s.call_tool(name, args)
                    txt = " ".join(getattr(c, "text", "") for c in res.content)
                    out[name] = {"error": getattr(res, "is_error", getattr(res, "isError", None)), "secs": round(time.time() - t, 1), "text": txt[:600]}
                except Exception as e:
                    out[name] = {"error": True, "text": repr(e)[:600]}
                print(name, json.dumps(out[name])[:700], flush=True)
    return out


which = sys.argv[1]
arg = sys.argv[2] if len(sys.argv) > 2 else "[]"
calls = json.load(open(arg[1:], encoding="utf-8")) if arg.startswith("@") else json.loads(arg)
res = asyncio.run(server(which, calls))
print("SERVER", which, "tools", res["tools"])
