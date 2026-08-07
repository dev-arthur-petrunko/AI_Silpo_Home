"""Друкує компактні JSON-схеми обраних інструментів із docs/mcp-notes.md."""
import json
import sys

text = open("docs/mcp-notes.md", encoding="utf-8").read()
start = text.index("### tools/list")
blob = text[start:]
decoder = json.JSONDecoder()
obj, _ = decoder.raw_decode(blob[blob.index("{"):])

all_tools = {t["name"]: t for t in obj.get("result", {}).get("tools", [])}
wanted = sys.argv[1:] if len(sys.argv) > 1 else list(all_tools)
for name in wanted:
    t = all_tools.get(name)
    if not t:
        print(f"--- {name}: NOT FOUND ---")
        continue
    print(f"--- {name} ---")
    print("title:", t.get("title"))
    print("desc:", (t.get("description") or "")[:300])
    print("inputSchema:", json.dumps(t.get("inputSchema", {}), ensure_ascii=False))
    print("outputSchema:", json.dumps(t.get("outputSchema", {}), ensure_ascii=False)[:1500])
    print()
