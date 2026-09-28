#!/usr/bin/env python3
"""Codex start-image handoff for the Claude Code port.

Claude Code has no built-in image generator, so every approved still is
requested from the Codex app, which keeps the original built-in OpenAI
`image_gen` route. This helper only writes request files, validates what Codex
returns, and produces the provenance fields that `streaming_cut_pipeline.py
accept-start` requires. It never calls an image provider itself.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

ROUTE = "codex_handoff"
PROVIDER = "openai"
SCHEMA = "codex-image-handoff/v1"
RATIOS = {"1:1": 1.0, "9:16": 9 / 16, "16:9": 16 / 9}
RATIO_TOLERANCE = 0.03
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")


def now():
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, data) -> None:
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def handoff_dir(run: Path) -> Path:
    return run / "codex-handoff"


def load_manifest(run: Path) -> dict:
    path = handoff_dir(run) / "handoff.json"
    if not path.is_file():
        raise ValueError("run prepare first; handoff.json is missing")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA:
        raise ValueError("unsupported handoff manifest")
    return data


def render_request(request: dict) -> str:
    refs = "\n".join(f"- {path}" for path in request["reference_images"]) or "- 없음"
    return (
        f"# {request['id']}\n\n"
        f"- request_sha256: `{request['request_sha256']}` (영수증에 그대로 적는다)\n"
        f"- 종류: {request['kind']}\n"
        f"- 비율: {request['ratio']}\n"
        f"- 품질: {request['quality']}\n"
        f"- 결과 이미지: results/{request['id']}.png\n"
        f"- 영수증: results/{request['id']}.json\n\n"
        f"## 조건 이미지 (편집·참조 입력, 있으면 반드시 사용)\n{refs}\n\n"
        f"## prompt\n\n```text\n{request['prompt']}\n```\n"
    )


def request_hash(request: dict) -> str:
    fields = {key: request[key] for key in ("id", "kind", "ratio", "quality", "prompt", "reference_images")}
    return sha256_bytes(json.dumps(fields, ensure_ascii=False, sort_keys=True).encode())


INSTRUCTIONS = """# Codex 이미지 생성 요청 (Claude Code 영상 생성 핸드오프)

이 폴더(`{folder}`)는 Claude Code의 `영상 생성` 작업이 만든 시작 이미지 요청이다. Codex는 **이미지 생성과 저장만** 한다.
아래의 `handoff.json`, `requests/`, `results/`는 모두 이 폴더 기준 경로다. 이 폴더에 쓰기 권한 확인이 뜨면 사용자에게 허용을 요청한다.
영상 생성, Higgsfield, TTS, CapCut 편집, 대본 수정은 하지 않는다.

## 규칙

1. `handoff.json`의 `requests` 중 `results/<id>.png`와 `results/<id>.json`이 아직 없는 요청만 처리한다. `priority`가 낮은 숫자부터 시작한다.
2. 요청마다 `requests/<id>.md`를 끝까지 읽고, 내장 `image_gen` 도구(시스템 `imagegen` 스킬의 기본 내장 모드)로 **요청 1개당 이미지 1장**만 만든다.
   - 서로 다른 요청을 한 번의 다중 출력 호출로 묶지 않는다. 독립 요청은 동시에 최대 {concurrency}개까지 병렬로 호출해도 된다.
   - `조건 이미지`가 있으면 편집/참조 입력으로 반드시 사용한다. 정확한 제품 포장·라벨·색·형태를 바꾸지 않는다.
   - 프롬프트 문구를 임의로 바꾸거나 보강하지 않는다. 비율과 품질은 요청 값을 따른다.
   - Higgsfield 이미지, 직접 Images API, ImageGen CLI, 다른 이미지 서비스로 대체하지 않는다. 내장 `image_gen`을 쓸 수 없으면 해당 요청을 건너뛰고 `results/<id>.json`에 `"status": "unavailable"`과 이유를 적는다.
3. 이미지가 하나 완성될 때마다 **즉시** 저장한다. 전체가 끝날 때까지 기다리지 않는다(Claude가 완성된 컷부터 바로 영상으로 보낸다).
   - 도구가 반환한 원본 파일을 재인코딩 없이 `results/<id>.png`로 복사한다(원본이 jpg/webp면 확장자를 유지해도 된다).
   - 그다음 `results/<id>.json` 영수증을 쓴다:

```json
{{
  "id": "<요청 id>",
  "request_sha256": "<handoff.json에 적힌 이 요청의 request_sha256>",
  "status": "generated",
  "image_file": "<id>.png",
  "tool_result_path": "<image_gen이 반환한 원본 파일 절대경로>",
  "quality": "<사용한 품질>",
  "model": "<도구가 알려준 모델명, 모르면 null>",
  "created_at": "<ISO 8601 시각>"
}}
```

4. 결과를 스스로 고르거나 재시도하지 않는다. 같은 요청에 두 번째 이미지를 만들지 않는다. 품질 판정과 재시도 결정은 Claude와 사용자가 한다.
5. 모든 요청을 처리하면 처리한 id 목록과 실패 id만 짧게 보고한다.
"""


def prepare(plan_path: Path, run: Path, concurrency: int = 5) -> dict:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if plan.get("video_source_mode") == "existing_clean_edit":
        raise ValueError("existing_clean_edit never generates images")
    if plan.get("image_generation_route") != ROUTE:
        raise ValueError(f"plan image_generation_route must be {ROUTE}")
    ratio = plan.get("output_ratio")
    if ratio not in RATIOS:
        raise ValueError("plan output_ratio must be 1:1, 9:16 or 16:9")
    if not 1 <= concurrency <= 8:
        raise ValueError("concurrency must be 1..8")
    base = handoff_dir(run)
    if (base / "handoff.json").exists():
        existing = load_manifest(run)
        if existing["plan_sha256"] != sha256_file(plan_path):
            raise ValueError("plan changed; existing handoff is immutable — add a separately approved request instead")
        return existing
    requests = []
    for index, cut in enumerate(sorted(plan["cuts"], key=lambda c: (0 if c.get("risk_level") == "high" or c.get("product_presence") == "required" else 1, c["cut"]))):
        prompt = str(cut.get("image_prompt", "")).strip()
        if not prompt:
            raise ValueError(f"cut {cut['cut']} has no image_prompt")
        request = {
            "id": f"cut-{int(cut['cut']):02d}",
            "cut": cut["cut"],
            "attempt": 1,
            "kind": "cut_start",
            "priority": index,
            "ratio": ratio,
            "quality": cut.get("image_quality", "high"),
            "prompt": prompt,
            "reference_images": [str(Path(p).expanduser().resolve()) for p in cut.get("image_reference_paths", [])],
        }
        requests.append(request)
    return _write_manifest(run, plan_path, ratio, concurrency, requests)


def _write_manifest(run: Path, plan_path: Path, ratio: str, concurrency: int, requests: list[dict]) -> dict:
    base = handoff_dir(run)
    (base / "requests").mkdir(parents=True, exist_ok=True)
    (base / "results").mkdir(parents=True, exist_ok=True)
    for request in requests:
        request["request_sha256"] = request_hash(request)
        (base / "requests" / f"{request['id']}.md").write_text(render_request(request), encoding="utf-8")
    manifest = {"schema": SCHEMA, "route": ROUTE, "provider": PROVIDER,
                "plan_path": str(plan_path.resolve()), "plan_sha256": sha256_file(plan_path),
                "output_ratio": ratio, "concurrency": concurrency, "requests": requests,
                "created_at": now()}
    write_json(base / "handoff.json", manifest)
    (base / "CODEX-INSTRUCTIONS.md").write_text(INSTRUCTIONS.format(concurrency=concurrency, folder=base.resolve()), encoding="utf-8")
    return manifest


def add_request(run: Path, request_id: str, kind: str, prompt: str, quality: str,
                references: list[str], cut=None, attempt: int = 1, ratio=None) -> dict:
    manifest = load_manifest(run)
    if any(r["id"] == request_id for r in manifest["requests"]):
        raise ValueError("request id already exists; requests are immutable")
    if kind not in {"cut_start", "product_master"}:
        raise ValueError("kind must be cut_start or product_master")
    if kind == "cut_start" and (cut is None or attempt < 2):
        raise ValueError("an added cut_start is a separately approved retry: pass --cut and --attempt >= 2")
    request = {"id": request_id, "cut": cut, "attempt": attempt, "kind": kind,
               "priority": -1 if kind == "product_master" else len(manifest["requests"]),
               "ratio": ratio or manifest["output_ratio"], "quality": quality, "prompt": prompt.strip(),
               "reference_images": [str(Path(p).expanduser().resolve()) for p in references]}
    if not request["prompt"]:
        raise ValueError("prompt is empty")
    if request["ratio"] not in RATIOS:
        raise ValueError("unsupported ratio")
    manifest["requests"].append(request)
    base = handoff_dir(run)
    request["request_sha256"] = request_hash(request)
    (base / "requests" / f"{request_id}.md").write_text(render_request(request), encoding="utf-8")
    write_json(base / "handoff.json", manifest)
    return request


def _result_image(results: Path, request_id: str, receipt: dict):
    named = receipt.get("image_file")
    if named:
        candidate = (results / named).resolve()
        if candidate.parent != results.resolve():
            raise ValueError(f"{request_id}: image_file must stay inside results/")
        return candidate if candidate.is_file() else None
    for suffix in IMAGE_SUFFIXES:
        candidate = results / f"{request_id}{suffix}"
        if candidate.is_file():
            return candidate
    return None


def inspect_result(run: Path, request: dict) -> dict:
    results = handoff_dir(run) / "results"
    receipt_path = results / f"{request['id']}.json"
    if not receipt_path.is_file():
        return {"id": request["id"], "state": "pending"}
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"id": request["id"], "state": "pending", "note": "receipt still being written"}
    if receipt.get("status") == "unavailable":
        return {"id": request["id"], "state": "unavailable", "reason": receipt.get("reason")}
    problems = []
    if receipt.get("id") != request["id"]:
        problems.append("receipt id mismatch")
    if receipt.get("request_sha256") != request["request_sha256"]:
        problems.append("receipt request_sha256 does not match the current request")
    if not receipt.get("tool_result_path"):
        problems.append("receipt has no tool_result_path")
    image = _result_image(results, request["id"], receipt)
    if image is None:
        problems.append("result image missing")
    else:
        try:
            with Image.open(image) as opened:
                opened.verify()
            with Image.open(image) as opened:
                width, height = opened.size
            expected = RATIOS[request["ratio"]]
            if abs(width / height - expected) / expected > RATIO_TOLERANCE:
                problems.append(f"aspect {width}x{height} does not match {request['ratio']}")
        except Exception as exc:  # unreadable or truncated image
            problems.append(f"image unreadable: {exc}")
    if problems:
        return {"id": request["id"], "state": "invalid", "problems": problems}
    return {"id": request["id"], "state": "ready", "cut": request.get("cut"), "kind": request["kind"],
            "attempt": request.get("attempt", 1), "image": str(image.resolve()),
            "image_sha256": sha256_file(image), "receipt_path": str(receipt_path.resolve()),
            "receipt_sha256": sha256_file(receipt_path)}


def status(run: Path) -> dict:
    manifest = load_manifest(run)
    rows = [inspect_result(run, request) for request in manifest["requests"]]
    intake = _intake_log(run)
    for row in rows:
        row["intaken"] = row["id"] in intake
    counts = {}
    for row in rows:
        counts[row["state"]] = counts.get(row["state"], 0) + 1
    return {"counts": counts, "requests": rows,
            "new_ready_ids": [r["id"] for r in rows if r["state"] == "ready" and not r["intaken"]]}


def _intake_log(run: Path) -> dict:
    path = handoff_dir(run) / "intake.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def intake(run: Path, request_id: str) -> dict:
    manifest = load_manifest(run)
    request = next((r for r in manifest["requests"] if r["id"] == request_id), None)
    if request is None:
        raise ValueError("unknown request id")
    row = inspect_result(run, request)
    if row["state"] != "ready":
        raise ValueError(f"{request_id} is not ready: {row}")
    log = _intake_log(run)
    prior = log.get(request_id)
    if prior and prior["image_sha256"] != row["image_sha256"]:
        raise ValueError("result changed after intake; Codex must not overwrite a delivered image")
    log[request_id] = {"image": row["image"], "image_sha256": row["image_sha256"],
                       "receipt_path": row["receipt_path"], "receipt_sha256": row["receipt_sha256"],
                       "intaken_at": prior["intaken_at"] if prior else now()}
    write_json(handoff_dir(run) / "intake.json", log)
    receipt = json.loads(Path(row["receipt_path"]).read_text(encoding="utf-8"))
    # Provenance part of the accept-start review. Claude adds the visual QC flags
    # and compared_with_selected_cut_ids only after actually viewing the image.
    review_stub = {"image_sha256": row["image_sha256"], "provider": PROVIDER, "route": ROUTE,
                   "tool_result_path": receipt["tool_result_path"],
                   "handoff_request_id": request_id,
                   "handoff_request_sha256": request["request_sha256"],
                   "handoff_receipt_path": row["receipt_path"],
                   "handoff_receipt_sha256": row["receipt_sha256"],
                   "model": receipt.get("model"), "quality": receipt.get("quality")}
    return {"status": "intaken", "id": request_id, "cut": request.get("cut"), "kind": request["kind"],
            "image": row["image"], "review_stub": review_stub}


def wait(run: Path, timeout: float, interval: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    while True:
        result = status(run)
        pending = result["counts"].get("pending", 0)
        if result["new_ready_ids"] or pending == 0 or time.monotonic() >= deadline:
            result["timed_out"] = not result["new_ready_ids"] and pending > 0
            return result
        time.sleep(interval)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True, help="run folder that holds codex-handoff/")
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--plan", type=Path, required=True)
    prep.add_argument("--concurrency", type=int, default=5)
    add = sub.add_parser("add")
    add.add_argument("--id", required=True)
    add.add_argument("--kind", required=True, choices=["cut_start", "product_master"])
    add.add_argument("--prompt-file", type=Path, required=True)
    add.add_argument("--quality", default="high")
    add.add_argument("--ref", action="append", default=[])
    add.add_argument("--cut", type=int)
    add.add_argument("--attempt", type=int, default=1)
    add.add_argument("--ratio")
    sub.add_parser("status")
    take = sub.add_parser("intake")
    take.add_argument("--id", required=True)
    wt = sub.add_parser("wait")
    wt.add_argument("--timeout", type=float, default=540)
    wt.add_argument("--interval", type=float, default=5)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            manifest = prepare(args.plan, args.run, args.concurrency)
            instructions = (handoff_dir(args.run) / "CODEX-INSTRUCTIONS.md").resolve()
            result = {"status": "prepared", "requests": [r["id"] for r in manifest["requests"]],
                      "codex_prompt": f"{instructions} 파일을 끝까지 읽고 그대로 이미지만 생성해줘."}
        elif args.command == "add":
            request = add_request(args.run, args.id, args.kind, args.prompt_file.read_text(encoding="utf-8"),
                                  args.quality, args.ref, args.cut, args.attempt, args.ratio)
            instructions = (handoff_dir(args.run) / "CODEX-INSTRUCTIONS.md").resolve()
            result = {"status": "added", "id": request["id"],
                      "codex_prompt": f"{instructions} 파일을 다시 읽고 아직 결과가 없는 요청만 이미지로 생성해줘."}
        elif args.command == "status":
            result = status(args.run)
        elif args.command == "intake":
            result = intake(args.run, args.id)
        else:
            result = wait(args.run, args.timeout, args.interval)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
