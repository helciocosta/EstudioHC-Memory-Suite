import re, io, sys

repo = sys.argv[1]
brief = io.open(repo + r"\.superpowers\sdd\briefs\opcaoB-task-3-brief.md", encoding="utf-8").read()
file = io.open(repo + r"\apps\mcp-memory\src\memory_server.py", encoding="utf-8").read()
file = file.replace("\r\n", "\n").replace("\r", "\n")
brief = brief.replace("\r\n", "\n")

blocks = re.findall(r"```python\n(.*?)```", brief, re.S)
print("Total verbatim blocks in brief:", len(blocks))
for i, b in enumerate(blocks):
    trim = b.rstrip("\n")
    ok = trim in file
    print("Block %d: EXACT-match=%s len=%d" % (i + 1, ok, len(trim)))
    if not ok:
        for j, line in enumerate(trim.split("\n")):
            if line not in file:
                print("   first missing line %d: %r" % (j + 1, line))
                break

# check required schema fields present
for tool in ["doc_add", "doc_search", "doc_list", "doc_delete"]:
    print("tool %s in handle_list_tools: %s" % (tool, ('name="%s"' % tool) in file))
    print("branch for %s: %s" % (tool, ('name == "%s"' % tool) in file))

print("CR bytes in committed-blob-normalized file:", file.count("\r"))
print("import line present:", "import chroma_client as chroma" in file)
