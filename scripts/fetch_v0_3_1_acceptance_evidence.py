#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import json
import os
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, cast

from v0_3_1_stage_acceptance import (
    StageAcceptanceError,
    load_manifest,
    load_policy,
    validate_evidence,
    validate_manifest,
    validate_prerequisite,
)

MAX_ARCHIVE_BYTES = 5 * 1024 * 1024
EVIDENCE_FILENAME = "acceptance-evidence.json"
UrlReader = Callable[[str, str], bytes]


class SafeGitHubRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        request: urllib.request.Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Mapping[str, str],
        new_url: str,
    ) -> urllib.request.Request | None:
        redirected = super().redirect_request(
            request,
            file_pointer,
            code,
            message,
            headers,
            new_url,
        )
        if redirected is None:
            return None
        old_host = urllib.parse.urlsplit(request.full_url).hostname
        new_target = urllib.parse.urlsplit(new_url)
        if new_target.scheme != "https":
            raise StageAcceptanceError("acceptance artifact redirect must use HTTPS")
        if new_target.hostname != old_host:
            redirected.remove_header("Authorization")
            redirected.remove_header("X-GitHub-Api-Version")
        return redirected


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve the previous stage acceptance evidence.")
    parser.add_argument("--stage-id", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def read_url(url: str, token: str) -> bytes:
    if not url.startswith("https://api.github.com/"):
        raise StageAcceptanceError("GitHub API request URL is not trusted")
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "trd-bot-v031-stage-acceptance",
        },
    )
    opener = urllib.request.build_opener(SafeGitHubRedirectHandler())
    with opener.open(request, timeout=30) as response:
        content_length = response.headers.get("Content-Length")
        if content_length is not None and int(content_length) > MAX_ARCHIVE_BYTES:
            raise StageAcceptanceError("acceptance artifact exceeds the size limit")
        payload = response.read(MAX_ARCHIVE_BYTES + 1)
    if len(payload) > MAX_ARCHIVE_BYTES:
        raise StageAcceptanceError("acceptance artifact exceeds the size limit")
    return payload


def select_artifact(
    payload: Mapping[str, Any],
    *,
    artifact_name: str,
    commit_sha: str,
) -> dict[str, Any]:
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list):
        raise StageAcceptanceError("GitHub artifact response is invalid")
    matches: list[dict[str, Any]] = []
    for item in artifacts:
        if not isinstance(item, dict):
            continue
        workflow_run = item.get("workflow_run")
        if (
            item.get("name") == artifact_name
            and item.get("expired") is False
            and isinstance(workflow_run, dict)
            and workflow_run.get("head_sha") == commit_sha
        ):
            matches.append(cast(dict[str, Any], item))
    if len(matches) != 1:
        raise StageAcceptanceError(
            f"expected one unexpired acceptance artifact, found {len(matches)}"
        )
    return matches[0]


def extract_evidence(archive: bytes) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            names = [
                name
                for name in bundle.namelist()
                if not name.endswith("/") and Path(name).name == EVIDENCE_FILENAME
            ]
            if names != [EVIDENCE_FILENAME]:
                raise StageAcceptanceError("acceptance archive must contain one root evidence file")
            info = bundle.getinfo(EVIDENCE_FILENAME)
            if info.file_size > MAX_ARCHIVE_BYTES:
                raise StageAcceptanceError("acceptance evidence exceeds the size limit")
            payload = json.loads(bundle.read(info))
    except (zipfile.BadZipFile, json.JSONDecodeError, KeyError) as error:
        raise StageAcceptanceError("acceptance artifact is not a valid evidence archive") from error
    if not isinstance(payload, dict):
        raise StageAcceptanceError("acceptance evidence must contain a JSON object")
    return cast(dict[str, Any], payload)


def resolve_previous_evidence(
    stage_id: str,
    repository: str,
    token: str,
    *,
    reader: UrlReader = read_url,
) -> dict[str, Any] | None:
    policy = load_policy()
    manifest = load_manifest(stage_id)
    validate_manifest(policy, manifest, require_candidate=True)
    prerequisite = cast(dict[str, Any], manifest["prerequisite"])
    if prerequisite["mode"] == "legacy_freeze":
        validate_prerequisite(policy, manifest)
        return None

    previous_stage = cast(str, prerequisite["stage_id"])
    commit_sha = cast(str, prerequisite["accepted_commit_sha"])
    artifact_name = f"{previous_stage}-acceptance-{commit_sha}"
    query = urllib.parse.urlencode({"name": artifact_name, "per_page": 100})
    api_url = f"https://api.github.com/repos/{repository}/actions/artifacts?{query}"
    listing = json.loads(reader(api_url, token))
    if not isinstance(listing, dict):
        raise StageAcceptanceError("GitHub artifact listing must be an object")
    artifact = select_artifact(listing, artifact_name=artifact_name, commit_sha=commit_sha)
    download_url = artifact.get("archive_download_url")
    if not isinstance(download_url, str) or not download_url.startswith(
        f"https://api.github.com/repos/{repository}/actions/artifacts/"
    ):
        raise StageAcceptanceError("untrusted acceptance artifact download URL")
    evidence = extract_evidence(reader(download_url, token))
    validate_evidence(
        policy,
        evidence,
        expected_stage_id=previous_stage,
        expected_commit_sha=commit_sha,
        expected_next_stage=stage_id,
    )
    return evidence


def main() -> int:
    args = parse_args()
    token = os.environ.get(args.token_env, "")
    manifest = load_manifest(args.stage_id)
    prerequisite = cast(dict[str, Any], manifest["prerequisite"])
    if prerequisite.get("mode") == "ci_artifact" and not token:
        raise StageAcceptanceError(f"{args.token_env} is required for CI artifact lookup")
    evidence = resolve_previous_evidence(args.stage_id, args.repository, token)
    if evidence is None:
        print("PREREQUISITE_EVIDENCE=LEGACY_FREEZE_PASS")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("PREREQUISITE_EVIDENCE=CI_ACCEPTANCE_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
