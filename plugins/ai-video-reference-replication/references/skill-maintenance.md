# 스킬 수정은 공개 배포까지 (Claude Code 이식판)

소유자의 2026-09-08 명시 지시: “스킬 수정하면 무조건 배포본에 반영 되도록 해줘”. 이 플러그인과 포함된 지원 스킬의 소유자 유지보수 요청에만 적용한다. 영상 제작 요청, 읽기 전용 진단, 다른 플러그인, 수신자 개인 수정에는 배포를 시작하지 않는다. 최신 사용자가 로컬 시험만 요청하거나 배포를 금지하면 해당 제한이 우선한다.

Claude Code 이식판의 원본은 GitHub 저장소 `seojun03/ai-video-reference-replication-claude`의 `main` 브랜치다. 설치 캐시(`~/.claude/plugins/...`)는 사본이므로 직접 고치지 않는다. Codex 배포본(`ai-video-reference-replication-mac`)과는 별개이며, Codex 쪽 변경을 이쪽에 옮길 때는 이식판 규칙(Codex 이미지 핸드오프, 형제 스킬 표기, 상태 경로)을 유지한다.

1. 저장소의 로컬 클론(없으면 새로 clone)에서 요청한 변경만 수정한다. 유지보수 중 제작 인터뷰·유료 영상 생성·CapCut 종료를 시작하지 않는다.
2. 변경과 관련된 테스트를 실행한다. 기본 검사:
   ```bash
   python3 -m pytest -q plugins/ai-video-reference-replication
   claude plugin validate .
   ```
   macOS 전용 폰트·CapCut 경로가 필요한 테스트는 Mac에서 확인한다.
3. `python3 plugins/ai-video-reference-replication/scripts/bump_version.py`로 버전을 올린다. 내용이 실제로 바뀐 경우에만 올라가고, 같은 내용 재실행은 버전을 유지한다.
4. 변경을 커밋하고 `main`에 푸시한다. 푸시 후 GitHub에서 해당 파일이 반영됐는지 확인한다. 푸시 실패·테스트 실패를 로컬 성공으로 바꾸지 않고 실패 단계와 남은 조치를 보고한다.
5. 사용자 측 반영: Claude Code에서 `/plugin marketplace update incore-video` 후 새 세션을 시작한다(마켓플레이스 자동 업데이트가 켜져 있으면 다음 시작 때 반영). 실제 수신자 PC 업데이트는 별도 확인 전까지 완료했다고 말하지 않는다.

이 절차는 에이전트가 수정 요청을 처리할 때의 완료 조건이다. 별도 감시기나 예약 작업을 만들지 않는다. 키·토큰·제품 자료·CapCut 프로젝트는 저장소에 포함하지 않는다.
