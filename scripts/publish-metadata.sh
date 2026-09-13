#!/bin/bash
#
# Record a released package in the PCM metadata on main.
#
# The release workflow runs on the *tag*, but the metadata has to land on the
# *current* main. The tag can lag behind main — v0.7.1 was tagged before the
# previous release's metadata commit had been pulled — and pushing the tag's
# tree then either gets rejected, or would drop entries main already has. The
# old step pushed with `|| echo "Nothing to push"`, so that rejection showed
# as a green run while the PCM never listed the release.
#
# So: update a fresh worktree of the latest main, push, and on a rejection
# (main moved while we worked) start over from the new main. Fail loudly if
# it can't be done. Re-running for a version already recorded is a no-op.
#
# Usage:  scripts/publish-metadata.sh <version> <package.zip>
# Env:    PUBLISH_REMOTE       remote to publish to        (default: origin)
#         PUBLISH_BRANCH       branch holding the metadata (default: main)
#         PUBLISH_ATTEMPTS     push attempts               (default: 5)
#         PUBLISH_RETRY_DELAY  seconds × attempt between tries (default: 3)
#
# Commits use the repository's configured git identity.

set -euo pipefail

if [ $# -ne 2 ]; then
    echo "Usage: $0 <version> <package.zip>" >&2
    exit 2
fi

version="$1"
package="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"
remote="${PUBLISH_REMOTE:-origin}"
branch="${PUBLISH_BRANCH:-main}"
attempts="${PUBLISH_ATTEMPTS:-5}"
delay="${PUBLISH_RETRY_DELAY:-3}"

repo="$(git rev-parse --show-toplevel)"
scratch="$(mktemp -d)"
worktree="$scratch/metadata"

cleanup() {
    cd "$repo"
    git worktree remove --force "$worktree" >/dev/null 2>&1 || true
    rm -rf "$scratch"
}
trap cleanup EXIT

for attempt in $(seq 1 "$attempts"); do
    cd "$repo"
    git fetch --quiet "$remote" "+refs/heads/$branch:refs/remotes/$remote/$branch"
    git worktree remove --force "$worktree" >/dev/null 2>&1 || true
    git worktree add --quiet --detach "$worktree" "$remote/$branch"

    cd "$worktree"
    python3 scripts/update-metadata.py "$version" "$package" >/dev/null

    # repository.json always gets a fresh timestamp; only publish when the
    # package lists actually changed.
    if git diff --quiet -- metadata.json packages.json; then
        echo "$branch already lists v$version with this package; nothing to publish."
        exit 0
    fi

    git add metadata.json packages.json repository.json
    git commit --quiet -m "Update metadata for release v$version"
    if git push --quiet "$remote" "HEAD:refs/heads/$branch"; then
        echo "Published v$version metadata to $branch ($(git rev-parse --short HEAD))."
        exit 0
    fi

    echo "Push attempt $attempt/$attempts was rejected ($branch moved?); retrying on the latest $branch." >&2
    sleep $(( attempt * delay ))
done

echo "::error::Could not publish v$version metadata to $branch after $attempts attempts. The release exists, but the PCM won't list it until metadata.json, packages.json and repository.json are updated." >&2
exit 1
