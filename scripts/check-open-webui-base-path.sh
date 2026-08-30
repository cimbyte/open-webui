#!/bin/sh
set -eu
repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
node "$repo_dir/scripts/check-open-webui-base-path.mjs"
check_dir=$(mktemp -d)
trap 'rm -rf "$check_dir"' EXIT
mkdir -p "$check_dir/bin"
printf '%s\n' '#!/bin/sh' 'for argument do echo "$argument"; done > "$OPEN_WEBUI_ARGUMENT_CAPTURE"' > "$check_dir/bin/python3"
chmod +x "$check_dir/bin/python3"
OPEN_WEBUI_ARGUMENT_CAPTURE="$check_dir/args" PATH="$check_dir/bin:$PATH" WEBUI_SECRET_KEY=test-secret OPEN_WEBUI_BASE_PATH=/web HOST=127.0.0.1 PORT=18781 "$repo_dir/backend/start.sh"
grep -Fx -- '--root-path' "$check_dir/args" >/dev/null
grep -Fx -- '/web' "$check_dir/args" >/dev/null
grep -Fx -- '127.0.0.1' "$check_dir/args" >/dev/null
grep -Fx -- '18781' "$check_dir/args" >/dev/null
if OPEN_WEBUI_ARGUMENT_CAPTURE="$check_dir/invalid" PATH="$check_dir/bin:$PATH" WEBUI_SECRET_KEY=test OPEN_WEBUI_BASE_PATH=web "$repo_dir/backend/start.sh" 2>/dev/null; then
	echo 'invalid relative base path was accepted' >&2
	exit 1
fi
