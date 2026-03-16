from __future__ import annotations

import textwrap

from code2skill.git_client import parse_unified_diff


def test_parse_unified_diff_supports_common_change_types() -> None:
    raw = textwrap.dedent(
        """\
        diff --git a/src/service.py b/src/service.py
        index 1111111..2222222 100644
        --- a/src/service.py
        +++ b/src/service.py
        @@ -1 +1,2 @@
        -def old():
        +def new():
        +    return 1
        diff --git a/src/old_name.py b/src/new_name.py
        similarity index 90%
        rename from src/old_name.py
        rename to src/new_name.py
        @@ -1 +1 @@
        -print("old")
        +print("new")
        diff --git a/src/deleted.py b/src/deleted.py
        deleted file mode 100644
        --- a/src/deleted.py
        +++ /dev/null
        @@ -1 +0,0 @@
        -print("gone")
        diff --git a/src/added.py b/src/added.py
        new file mode 100644
        --- /dev/null
        +++ b/src/added.py
        @@ -0,0 +1 @@
        +print("added")
        """
    )

    patches = parse_unified_diff(raw)

    assert [(item.path, item.change_type) for item in patches] == [
        ("src/service.py", "modify"),
        ("src/new_name.py", "rename"),
        ("src/deleted.py", "delete"),
        ("src/added.py", "add"),
    ]
    assert patches[1].previous_path == "src/old_name.py"
    assert patches[0].hunks[0].header == "@@ -1 +1,2 @@"
    assert '+print("added")' in patches[3].patch
