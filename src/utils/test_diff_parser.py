from .diff_parser import format_changes, parse_diff

sample = """diff --git a/src/generate.py b/src/generate.py
index 03a33fb..7e6d33a 100644
--- a/src/generate.py
+++ b/src/generate.py
@@ -12,3 +12,3 @@
-GENERATION_MODEL = "gemma3:1b"
+GENERATION_MODEL = "gemma4"
 DEFAULT_TOP_K = 5
"""

parsed = parse_diff(sample)
print(format_changes(parsed))

# OUTPUT:
# python -m utils.test_diff_parser
# FILE: b/src/generate.py
# STATUS: modified
# BINARY: False

# HUNK 1: @@ -12,3 +12,3 @@

# REMOVED (-):
# - GENERATION_MODEL = "gemma3:1b"

# ADDED (+):
# + GENERATION_MODEL = "gemma4"

# CONTEXT (unchanged):
#   DEFAULT_TOP_K = 5

# DIFF STATS:
# Files changed: 1
# Insertions: 1
# Deletions: 1
