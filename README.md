# 영상 생성 자동화 — Claude Code 마켓플레이스

인코어 영상 생성 자동화 플러그인(Codex판 v1.11)의 Claude Code 이식판입니다. 컷별 시작 이미지는 Codex 앱에서 만들고, 기획·영상화(Higgsfield Kling v3.0)·TTS·CapCut 편집은 Claude Code가 진행합니다.

## 설치 (Mac의 Claude Code)

```text
/plugin marketplace add seojun03/ai-video-reference-replication-claude
/plugin install ai-video-reference-replication@incore-video
```

설치 후 새 세션을 시작하고, 처음 한 번 Claude에게 "영상 생성 런타임 설치해줘"라고 하면 플러그인의 `scripts/setup_runtime.py`로 Python 전용 가상환경을 준비합니다(Codex판을 쓰던 Mac이면 같은 가상환경을 그대로 씁니다).

Higgsfield는 처음 사용할 때 `/mcp`에서 `higgsfield` 서버에 로그인합니다(이미 Higgsfield 커넥터가 연결돼 있으면 그대로 사용됩니다).

## 사용

- `/ai-video-reference-replication:영상생성` — 제작 방식부터 묻고 시작합니다.
- 또는 그냥 "영상 생성 시작해줘"라고 말해도 스킬이 호출됩니다.

## 업데이트

```text
/plugin marketplace update incore-video
```

플러그인 원본과 상세 설명: [`plugins/ai-video-reference-replication/README.md`](plugins/ai-video-reference-replication/README.md)

Codex판(`ai-video-reference-replication-mac`)과는 별도 저장소이며 서로 덮어쓰지 않습니다.
