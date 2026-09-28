# 공유받은 환경에서 실행하기 (Claude Code)

`PLUGIN_ROOT`는 현재 읽고 있는 플러그인 안의 `.claude-plugin/plugin.json`이 있는 폴더다(보통 `~/.claude/plugins/` 아래 설치 캐시). 설치 캐시 버전이나 작성자의 사용자 이름을 고정하지 않는다. 쉘 명령에는 확인한 절대 경로를 인용하여 사용한다.

## Claude Code 이식판 공통 규칙

이 플러그인은 Codex 플러그인 v1.11을 Claude Code로 옮긴 것이다. 모든 지원 스킬에 아래 규칙이 원문보다 우선한다.

- **시작 이미지·제품 마스터:** Claude Code에는 내장 이미지 생성 도구가 없다. 모든 스틸은 `skills/ai-video-reference-replication/references/codex-image-handoff.md`의 Codex 핸드오프로 사용자의 Codex 앱에서 만든다(`image_generation_route: "codex_handoff"`). 문서의 “built-in `image_gen`”, “`imagegen` 스킬”, “ImageGen”, “내장 이미지 도구”는 이 경로로 실행되는 같은 도구를 뜻한다. Claude가 Higgsfield 이미지·직접 Images API·다른 서비스로 대체하지 않는다.
- **형제 스킬:** 문서에서 백틱으로 적힌 형제 스킬 이름(원본의 `$스킬명`)은 Skill 도구로 `ai-video-reference-replication:<스킬명>`을 호출하거나 `skills/<스킬명>/SKILL.md`를 끝까지 읽고 따른다.
- **이미지 보기:** 원본의 `view_image`는 Read 도구로 이미지 파일을 직접 여는 것으로 대신한다.
- **질문 표시:** 채팅 번호 목록 규칙(`workflow-01-question-display.md`)을 그대로 따른다. `AskUserQuestion` 카드로 바꾸지 않는다.
- **상태 경로:** `~/.codex/state/<이름>/`이 이미 있으면 Codex와 공유해 그대로 쓰고, 없으면 `~/.claude/state/<이름>/`을 쓴다.
- **긴 작업:** 한 번의 셸 명령은 10분을 넘기지 않는다. 대기는 짧은 상태 조회를 반복한다.

## 준비

제품 자료 기본 경로는 수신자의 `~/Documents/인코어`다. 다른 폴더를 쓰면 해당 실행의 `VIDEO_PRODUCT_LIBRARY_ROOT` 환경변수와 `--root` 지원 인자에 동일한 절대 경로를 전달한다. 업체와 제품은 사용자가 지정해야 하며, 폴더가 없다고 다른 업체 자료를 가져오지 않는다. 제품 자료와 API 키, 음성 복제 ID, 과거 작업물은 공유 패키지에 포함하지 않는다.

Python 패키지는 `python3 "$PLUGIN_ROOT/scripts/setup_runtime.py"`로 수신자 전용 가상환경에 설치한다. 이후 실행에는 `~/.local/share/ai-video-reference-replication/venv/bin/python`을 사용한다(Codex 판과 같은 가상환경을 공유한다).

먼저 `python3 "$PLUGIN_ROOT/scripts/doctor.py"`로 로컬 도구를 읽기 전용 확인한다. 이 검사는 서비스 로그인이나 실제 유료 생성 성공을 증명하지 않는다. 선택한 제작 단계에 필요한 조건만 확인한다.

- 이미지: 사용자의 Codex 앱(내장 `image_gen` 사용 가능)이 필요하다. Claude는 요청서를 만들고 결과를 검증만 한다. 다른 이미지 API로 대체하지 않는다.
- AI 영상: 수신자 자신의 Higgsfield 연결과 Kling v3.0 이용 권한이 필요하다. 플러그인의 `higgsfield` MCP 서버(처음 사용 시 `/mcp`에서 로그인) 또는 사용자가 연결한 Higgsfield 커넥터를 사용한다. 인증값은 복사하지 않는다. 사용 가능한 도구와 반환 모델을 제작 시 확인한다.
- TTS: 수신자 자신의 ElevenLabs 계정과 지원 스킬의 인증 경로를 사용한다. 환경변수의 값이나 인증 파일 내용을 채팅에 출력하지 않는다. 과거 소유자의 음성·설정을 추정하지 않는다.
- 기본 9:16 의미별 편집: 포함된 `capcut-semantic-cut-edit`의 실행 코드와 수신자의 기존 CapCut 프로젝트를 사용한다. 현재 구현은 macOS 기준이며 Claude Code도 같은 Mac에서 실행해야 한다(클라우드 세션에서는 CapCut 편집을 완료할 수 없다). 원본 프로젝트를 보존하고 새 타임라인을 검증해야 한다.
- 별도 스타일·엄격한 복제·범용 편집: `CAPCUT_AUTOMATION_ROOT`로 지정한 별도 CapCut 자동화 실행 엔진이 필요하다. 이 패키지에 소유자의 실행 프로젝트나 학습 데이터는 들어 있지 않다. 엔진이 없으면 해당 단계가 미구성임을 알리고 완료로 표시하지 않는다.
- Windows: 플러그인 문서 설치와 제작 기획은 가능하지만 `fcntl`, macOS CapCut 경로·앱 제어에 의존하는 실행은 Windows 이식·검증 전까지 지원한다고 표시하지 않는다.

지원 스킬을 읽을 때 같은 플러그인의 `skills/<이름>/SKILL.md`를 우선한다. `ai-video-reference-tts-workflow`는 별도 통합 워크플로에 대한 선택적 안내다. 본 플러그인의 직접 TTS 경로에는 필요 없으며 없을 때 그 별도 경로를 시작하지 않는다. `product-page-reference-video`는 상위 계약이 허용한 제품 분석 단계까지만 사용한다. OpenAI 이미지 전용(Codex 핸드오프)·Kling v3.0 고정·기존 클린본 모드 생성 금지는 모든 하위 안내보다 우선한다.

받는 사람의 설정·제품 파일은 설치 폴더 밖에 둔다. 새 버전 설치가 사용자 자료를 덮어쓰면 안 된다. 실제 미설치 도구나 필수 입력이 없는 경우에만 해당 항목을 짧게 안내한다.
