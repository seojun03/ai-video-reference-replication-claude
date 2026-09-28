# 영상 생성 자동화 — Claude Code 플러그인

Codex 플러그인 `ai-video-reference-replication` v1.11을 Claude Code로 옮긴 판입니다. 레퍼런스 제작 주 스킬 `영상 생성`과 지원 스킬 8개를 포함합니다. 영상 모델(Kling v3.0 고정)·품질·인터뷰·대본 확정 기준은 원본과 같고, 업체 자료·계정·API 키·CapCut 프로젝트는 포함하지 않습니다.

## 원본과 달라진 점

| 항목 | Codex 원본 | Claude Code 이식판 |
|---|---|---|
| 컷별 시작 이미지·제품 마스터 | Codex 내장 `image_gen` 직접 호출 | Claude가 요청서를 쓰고 **Codex 앱이 같은 `image_gen`으로 생성**하는 핸드오프 (`image_generation_route: codex_handoff`) |
| 설치·업데이트 | `INSTALL-MAC.command` + 6시간 자동 업데이트 | Claude Code 플러그인 마켓플레이스 (`/plugin`) |
| Higgsfield 연결 | `agents/openai.yaml` 의존성 | 플러그인 `.mcp.json` 또는 기존 Higgsfield 커넥터 |
| 하위 스킬 호출 | `$스킬명` | Skill 도구 `ai-video-reference-replication:<스킬명>` |
| 상태 폴더 | `~/.codex/state/...` | 기존 Codex 폴더가 있으면 공유, 없으면 `~/.claude/state/...` |

## 이미지 핸드오프 흐름

1. Claude가 대본 확정·컷 기획(Gate 1)까지 진행하고 `codex-handoff/` 폴더에 컷별 요청서를 씁니다.
2. Claude가 알려주는 한 줄을 Codex 앱에 붙여넣으면 Codex가 이미지를 한 장씩 `results/`에 저장합니다.
3. Claude가 도착하는 대로 검수·중복 검사 후 바로 Kling 영상으로 보내고, TTS·CapCut 편집까지 이어갑니다.

자세한 규칙: `skills/ai-video-reference-replication/references/codex-image-handoff.md`

## 실행 조건

`references/recipient-runtime.md`를 참고합니다. Mac에서 Claude Code(데스크톱 앱 또는 CLI)로 실행해야 로컬 CapCut·FFmpeg·업체 폴더를 다룰 수 있습니다. Python 패키지는 `python3 "<플러그인 경로>/scripts/setup_runtime.py"`로 전용 가상환경에 설치합니다.

## 수정과 배포

`references/skill-maintenance.md`: 수정 → 테스트 → `scripts/bump_version.py` → `main`에 푸시. 사용자는 `/plugin marketplace update incore-video`로 받습니다.
