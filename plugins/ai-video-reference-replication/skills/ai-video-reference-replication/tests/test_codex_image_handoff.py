from __future__ import annotations

import importlib.util
import json
import random
import shutil
import sys
from pathlib import Path

import pytest
from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def module(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


handoff = module("codex_image_handoff")
pipeline = module("streaming_cut_pipeline")


def make_plan(tmp_path, count=2, ratio="9:16", route="codex_handoff"):
    plan = {"video_source_mode": "ai_generation", "image_generation_route": route, "output_ratio": ratio, "cuts": []}
    for number in range(1, count + 1):
        plan["cuts"].append({"cut": number, "duration_seconds": 4, "motion_prompt": "손을 움직인다",
                             "image_prompt": f"scene {number}, no text", "image_quality": "low",
                             "risk_level": "high" if number == count else "low",
                             "product_presence": "forbidden", "cost": {"mode": "pro"},
                             "scene_design": {"setting": f"room-{number}", "subject_action": f"action-{number}",
                                              "shot_scale": "medium", "camera_angle": "side"}})
    path = tmp_path / "cut-plan.json"
    path.write_text(json.dumps(plan))
    return path


def codex_delivers(run, request_id, size=(72, 128), seed=1, request_sha=None):
    """Simulate Codex: save the image_gen output and write the receipt."""
    manifest = json.loads((run / "codex-handoff/handoff.json").read_text())
    request = next(r for r in manifest["requests"] if r["id"] == request_id)
    rng = random.Random(seed)
    original = run / "codex-generated" / f"{request_id}-original.png"
    original.parent.mkdir(exist_ok=True)
    Image.frombytes("RGB", size, bytes(rng.randrange(256) for _ in range(size[0] * size[1] * 3))).save(original)
    results = run / "codex-handoff/results"
    shutil.copyfile(original, results / f"{request_id}.png")
    (results / f"{request_id}.json").write_text(json.dumps({
        "id": request_id, "request_sha256": request_sha or request["request_sha256"], "status": "generated",
        "image_file": f"{request_id}.png", "tool_result_path": str(original), "quality": "low",
        "model": None, "created_at": "2026-09-28T00:00:00Z"}))


def test_prepare_writes_requests_and_codex_instructions(tmp_path):
    plan = make_plan(tmp_path, count=3)
    manifest = handoff.prepare(plan, tmp_path)
    ids = [r["id"] for r in manifest["requests"]]
    assert ids[0] == "cut-03"  # high-risk cut is requested first
    assert sorted(ids) == ["cut-01", "cut-02", "cut-03"]
    base = tmp_path / "codex-handoff"
    assert (base / "CODEX-INSTRUCTIONS.md").read_text().count("image_gen") >= 2
    request_md = (base / "requests/cut-01.md").read_text()
    assert manifest["requests"][1]["request_sha256"] in request_md or manifest["requests"][2]["request_sha256"] in request_md
    assert handoff.status(tmp_path)["counts"] == {"pending": 3}


def test_prepare_rejects_other_routes_and_clean_edit(tmp_path):
    with pytest.raises(ValueError, match="codex_handoff"):
        handoff.prepare(make_plan(tmp_path, route="built_in_image_gen"), tmp_path)
    clean = tmp_path / "clean.json"
    clean.write_text(json.dumps({"video_source_mode": "existing_clean_edit", "cuts": []}))
    with pytest.raises(ValueError, match="never generates"):
        handoff.prepare(clean, tmp_path)


def test_prepare_is_immutable_once_plan_changes(tmp_path):
    plan = make_plan(tmp_path)
    handoff.prepare(plan, tmp_path)
    data = json.loads(plan.read_text())
    data["cuts"][0]["image_prompt"] = "changed"
    plan.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="immutable"):
        handoff.prepare(plan, tmp_path)


def test_delivered_image_streams_into_accept_start(tmp_path):
    plan = make_plan(tmp_path)
    handoff.prepare(plan, tmp_path)
    state = tmp_path / "qc/streaming-pipeline.json"
    pipeline.initialize(state, plan, tmp_path / "qc/ledger.json", 3)
    codex_delivers(tmp_path, "cut-01")
    waited = handoff.wait(tmp_path, timeout=1, interval=0.1)
    assert waited["new_ready_ids"] == ["cut-01"] and not waited["timed_out"]
    taken = handoff.intake(tmp_path, "cut-01")
    review = {**taken["review_stub"], "composition_pass": True, "action_ready": True,
              "scene_variety_pass": True, "compared_with_selected_cut_ids": []}
    assert pipeline.accept_start(state, 1, Path(taken["image"]), review)["status"] == "image_ready"
    assert pipeline.ready(json.loads(state.read_text()))["ready_cut_ids"] == ["1"]
    assert handoff.status(tmp_path)["new_ready_ids"] == []


def test_wrong_ratio_and_stale_request_hash_are_invalid(tmp_path):
    handoff.prepare(make_plan(tmp_path), tmp_path)
    codex_delivers(tmp_path, "cut-01", size=(128, 128))
    codex_delivers(tmp_path, "cut-02", request_sha="stale")
    rows = {r["id"]: r for r in handoff.status(tmp_path)["requests"]}
    assert rows["cut-01"]["state"] == "invalid" and "aspect" in rows["cut-01"]["problems"][0]
    assert rows["cut-02"]["state"] == "invalid" and "request_sha256" in rows["cut-02"]["problems"][0]
    with pytest.raises(ValueError, match="not ready"):
        handoff.intake(tmp_path, "cut-01")


def test_overwritten_result_after_intake_is_rejected(tmp_path):
    handoff.prepare(make_plan(tmp_path), tmp_path)
    codex_delivers(tmp_path, "cut-01", seed=1)
    handoff.intake(tmp_path, "cut-01")
    codex_delivers(tmp_path, "cut-01", seed=2)
    with pytest.raises(ValueError, match="overwrite"):
        handoff.intake(tmp_path, "cut-01")


def test_accept_start_rejects_review_without_matching_receipt(tmp_path):
    plan = make_plan(tmp_path)
    handoff.prepare(plan, tmp_path)
    state = tmp_path / "qc/streaming-pipeline.json"
    pipeline.initialize(state, plan, tmp_path / "qc/ledger.json", 3)
    codex_delivers(tmp_path, "cut-01")
    taken = handoff.intake(tmp_path, "cut-01")
    review = {**taken["review_stub"], "composition_pass": True, "action_ready": True,
              "scene_variety_pass": True, "compared_with_selected_cut_ids": []}
    forged = {**review, "tool_result_path": "/elsewhere.png"}
    with pytest.raises(ValueError, match="receipt"):
        pipeline.accept_start(state, 1, Path(taken["image"]), forged)
    Path(taken["review_stub"]["handoff_receipt_path"]).write_text("{}")
    with pytest.raises(ValueError, match="receipt"):
        pipeline.accept_start(state, 1, Path(taken["image"]), review)


def test_retry_and_product_master_requests_are_added_not_overwritten(tmp_path):
    handoff.prepare(make_plan(tmp_path), tmp_path)
    with pytest.raises(ValueError, match="retry"):
        handoff.add_request(tmp_path, "cut-01-a1", "cut_start", "again", "high", [], cut=1, attempt=1)
    master = handoff.add_request(tmp_path, "product-master", "product_master", "exact package", "high", [])
    assert master["priority"] == -1
    retry = handoff.add_request(tmp_path, "cut-01-a2", "cut_start", "again", "high", [], cut=1, attempt=2)
    assert retry["request_sha256"]
    with pytest.raises(ValueError, match="immutable"):
        handoff.add_request(tmp_path, "cut-01-a2", "cut_start", "x", "high", [], cut=1, attempt=2)
    unavailable = tmp_path / "codex-handoff/results/cut-02.json"
    unavailable.write_text(json.dumps({"id": "cut-02", "status": "unavailable", "reason": "image_gen off"}))
    rows = {r["id"]: r for r in handoff.status(tmp_path)["requests"]}
    assert rows["cut-02"]["state"] == "unavailable"
