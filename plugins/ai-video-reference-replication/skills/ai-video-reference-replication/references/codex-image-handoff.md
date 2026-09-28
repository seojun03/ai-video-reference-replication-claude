# Codex 이미지 핸드오프 (Claude Code 이식판의 유일한 스틸 경로)

Claude Code에는 내장 이미지 생성 도구가 없다. 원본(Codex)의 “내장 OpenAI `image_gen`만 사용” 규칙은 그대로 유지하되, 그 도구를 **사용자의 Codex 앱**에서 실행한다. Claude는 요청서 작성·결과 검증·QC·Kling 제출·편집을 맡고, Codex는 요청서대로 이미지를 만들어 폴더에 넣기만 한다.

- 계획 값: `image_generation_mode: "openai_only"`, `image_generation_route: "codex_handoff"`, `image_candidates_per_cut: 1`, `higgsfield_image_jobs: 0`, `image_api_jobs: 0`, `image_cli_jobs: 0`.
- 문서의 다른 곳에 남은 “built-in `image_gen`”, “`imagegen` 스킬”, “ImageGen”, “내장 이미지 도구”는 모두 **이 핸드오프를 통해 Codex에서 실행되는 같은 도구**를 뜻한다. Claude가 직접 이미지를 만들거나, Higgsfield 이미지·직접 Images API·다른 서비스로 대체하지 않는다.
- 기존 클린본 편집(`existing_clean_edit`)에서는 핸드오프를 만들지 않는다.

## 1. 요청서 만들기 (Gate 1 승인·계획 lint 통과 뒤)

```bash
python3 "${PLUGIN_ROOT}/skills/ai-video-reference-replication/scripts/codex_image_handoff.py" \
  --run "<run>" prepare --plan "<run>/cut-plan.json"
```

- 각 컷의 `image_prompt`, `image_quality`, 선택 항목 `image_reference_paths`(승인된 제품 마스터·캐릭터 기준 등 조건 이미지 절대경로)로 `<run>/codex-handoff/requests/cut-NN.md`와 `handoff.json`, `CODEX-INSTRUCTIONS.md`를 만든다. 고위험·제품 필수 컷이 먼저 요청된다.
- 계획이 바뀐 뒤에는 기존 핸드오프를 덮어쓰지 않는다. 별도 승인된 재시도·제품 마스터는 `add`로 새 요청을 추가한다:

```bash
python3 "<scripts>/codex_image_handoff.py" --run "<run>" add --id product-master --kind product_master \
  --prompt-file "<prompt.txt>" --quality high --ref "<official-source.png>"
python3 "<scripts>/codex_image_handoff.py" --run "<run>" add --id cut-03-a2 --kind cut_start --cut 3 --attempt 2 \
  --prompt-file "<prompt.txt>" --quality high
```

## 2. 사용자에게 Codex 실행 안내

`prepare`/`add` 결과의 `codex_prompt` 한 줄을 그대로 보여주고, **Codex 앱의 새 작업에 붙여넣어 달라**고 짧게 요청한다. 예:

> Codex에 아래 한 줄을 붙여넣어 주세요. 이미지가 한 장씩 완성되는 대로 제가 바로 검수하고 영상으로 넘깁니다.
> `…/codex-handoff/CODEX-INSTRUCTIONS.md 파일을 끝까지 읽고 그대로 이미지만 생성해줘.`

Codex 쪽 규칙(요청 1개당 1장, 프롬프트 변경 금지, 완성 즉시 저장, 영수증 작성, 대체 서비스 금지)은 `CODEX-INSTRUCTIONS.md`에 들어 있다. 사용자가 Codex를 쓸 수 없다고 하면 해당 컷을 `unavailable`로 기록하고 멈춘다. 다른 이미지 경로로 바꾸지 않는다.

## 3. 도착하는 대로 컷별 스트리밍 (per-cut-streaming.md와 결합)

```bash
python3 "<scripts>/codex_image_handoff.py" --run "<run>" wait --timeout 540
```

- `wait`는 새 결과가 생기거나, 대기 요청이 없거나, 제한 시간이 지나면 돌아온다. `new_ready_ids`가 있으면 곧바로 처리하고, 없으면 진행 중 Kling 작업의 상태 확인·다운로드·QC를 한 뒤 다시 `wait`한다. 모든 이미지를 기다렸다가 영상을 시작하지 않는다.
- `invalid`(비율 불일치, 영수증·요청 해시 불일치, 파일 손상)는 사용하지 않고 원인을 사용자에게 알린다. Codex에 같은 요청을 다시 만들게 하려면 승인된 재시도로 `add`한다.
- 새 결과마다:
  1. `intake --id cut-NN` → 이미지 경로와 `review_stub`(해시·경로·영수증 출처)을 받는다.
  2. Read 도구로 **이미지를 직접 보고** 기존 기준(동작 직전 상태, 인물/제품 식별, 구도·의미, 텍스트·가짜 UI 없음)으로 검수한다. 누적 연락시트로 이미 선택된 컷들과 비교한다.
  3. `review_stub`에 `composition_pass`, `action_ready`, `scene_variety_pass`, (제품 필수 컷) `product_identity_pass`, `compared_with_selected_cut_ids`를 더해 review JSON으로 저장한다. 실제로 보지 않은 항목을 `true`로 쓰지 않는다.
  4. `streaming_cut_pipeline.py accept-start` → `ready` → `claim-video` → Higgsfield 업로드·Kling 제출 → `record-video` 순서는 `per-cut-streaming.md` 그대로다.
- 제품 마스터(`kind: product_master`)는 컷 요청보다 먼저 처리한다. 마스터 QC 실패는 시스템 오류로 보고 컷 생성을 멈춘다.

## 4. 기록

선택·탈락 후보 모두 `provider: openai`, `route: codex_handoff`, Codex `tool_result_path`, 요청/영수증 SHA-256, 품질, 모델(알 수 있으면), QC 상태를 원장과 매니페스트에 남긴다. `intake.json`에 등록된 뒤 결과 파일이 바뀌면 거부된다. Codex가 이미 전달한 이미지를 덮어쓰게 하지 않는다.
