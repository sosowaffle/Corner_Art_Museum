# 코너의 미술관 — 채널 연결 완료 버전

아래 여섯 채널의 ID를 `channels.json`에 **미리 입력**했습니다. GitHub Secrets에는 **`DISCORD_BOT_TOKEN` 하나만 등록**하면 됩니다. `DISCORD_CHANNELS` Secret은 필요하지 않습니다(있을 경우 해당 설정이 우선됨).

| 전시관 | 채널 ID | 유형 |
|---|---|---|
| 코너의_미술관 | `1535642301907345448` | 일반 텍스트 채널 |
| 코너의_전쟁기념관 | `1535642966243409920` | 게시판(포럼)으로 보임. 게시글의 이미지 수집 지원 |
| 코너의_으흐흐관 | `1535725889361420348` | 일반 텍스트 채널 |
| to-소소와플 | `1535645389041049630` | 자동 유형 확인 |
| to-심심한코너 | `1535645421614006353` | 자동 유형 확인 |
| to-강시 | `1535645447769686106` | 자동 유형 확인 |

*디스코드에 실제로 접속하지 않았으므로 채널 유형은 화면 아이콘에서 추정했습니다. 스크립트는 실행 시 Discord API에서 채널 유형을 직접 확인합니다.*

**주의:** 디스코드 봇이 여섯 채널과 게시판 스레드를 볼 수 있어야 하며 `View Channel`/`Read Message History` 권한과 `Message Content Intent`가 필요합니다. 게시판은 활성 게시글과 최근 공개 보관 게시글(최대 500개)을 탐색합니다. 매우 오래된 보관 게시글은 수집되지 않을 수 있습니다. 이미 가져온 게시글의 새 댓글 이미지도 다음 실행에서 수집합니다. 개인정보·저작권·작품 공개 동의를 확인해 주세요.

## 간단한 실행 순서

1. 이 ZIP **압축을 풀고 내부 파일 전체**를 GitHub 리포지토리에 업로드합니다. `.github/workflows/sync-discord.yml`, `channels.json`도 반드시 포함하세요.
2. Discord Developer Portal에서 봇 생성 후 여섯 채널에 접근 권한을 부여합니다.
3. GitHub 리포지토리 `Settings → Secrets and variables → Actions`에서 `DISCORD_BOT_TOKEN`을 Secret으로 만듭니다.
4. GitHub `Actions → Sync Discord Artworks → Run workflow`로 첫 동기화를 실행합니다.
5. `Settings → Pages → Deploy from a branch → main / (root)`로 홈페이지를 공개합니다.

---

# ATELIER / 디스코드 자동 전시 미술관

디스코드 지정 채널에 타인이 올린 **이미지 및 동영상 첨부파일**을 GitHub Pages 온라인 미술관에 전시합니다. 사이트는 `index.html` 하나로 작동하지만, **자동 연동에는** 나머지 파일과 `.github/workflows/sync-discord.yml`이 반드시 필요합니다.

## 1. GitHub에 업로드

1. GitHub에서 새 **공개(Public) 리포지토리**를 만드세요. 예: `art-museum`.
2. 이 ZIP 파일을 풀고 **폴더 안의 내용 전체를 리포지토리 최상단**에 올리세요. `.github` 폴더도 포함되어야 합니다. (GitHub 웹 업로드에서 숨김 폴더 누락 주의.)
3. `Settings → Pages → Build and deployment → Deploy from a branch`를 선택하고 브랜치 `main`, 폴더 `/(root)`를 저장하세요.
4. 주소 예시: `https://사용자이름.github.io/art-museum/`. 첫 배포에는 시간이 걸릴 수 있습니다.
5. 첫 화면의 이미지는 실제 작가 작품이 아닌 **데모용 추상 일러스트**입니다. 연동 후 자동으로 교체됩니다.

## 2. Discord 앱 / 봇 등록

1. [Discord Developer Portal](https://discord.com/developers/applications)에서 **New Application**을 만드세요.
2. `Bot` 메뉴에서 봇 토큰을 발급받으세요. **토큰은 절대로 index.html, public repo, 채팅에 올리지 마세요.**
3. `Bot → Privileged Gateway Intents → Message Content Intent`를 **켜세요**. API에서 타인이 올린 첨부파일과 메시지 설명을 읽기 위해 필요합니다. 인증된 대규모 앱은 별도 승인이 요구될 수 있습니다.
4. `OAuth2 → URL Generator`에서 `bot` 스코프를 선택하고 `View Channels`와 `Read Message History` 권한을 주어 해당 서버로 초대하세요. 봇이 읽을 채널의 **채널별 권한 덮어쓰기**도 확인하세요.
5. 디스코드 `사용자 설정 → 고급 → 개발자 모드`를 켜고 채널에서 우클릭 → **채널 ID 복사**를 누르세요.
6. 그림을 올리는 모든 참여자에게 **홈페이지 공개 전시 동의**, 이름 노출, 작품 철회·삭제 요청 절차를 공지하세요. 공개 채널이나 등록 규칙에 게시하는 편이 좋습니다.

## 3. GitHub Secrets 설정 (이 프로젝트는 하나만 필수)

리포지토리 `Settings → Secrets and variables → Actions → New repository secret`에서 설정합니다.

**`DISCORD_BOT_TOKEN`**: 디스코드 개발자 포털에서 발급한 봇 토큰 (앞에 `Bot `을 붙이지 마세요)

**`DISCORD_CHANNELS`**: 선택 사항입니다. 기본 채널은 `channels.json`에 이미 설정되어 있으므로 입력하지 않아도 됩니다. 아래는 추가 사용자 설정 예시입니다.

```json
{
  "123456789012345678": {"name": "일러스트", "category": "illustration"},
  "234567890123456789": {"name": "팬아트", "category": "fanart"},
  "345678901234567890": {"name": "오리지널", "category": "original"},
  "456789012345678901": {"name": "스케치", "category": "sketch"}
}
```

카테고리는 `illustration`, `fanart`, `original`, `sketch`, `photo`, `other` 등을 사용할 수 있습니다. 여러 채널을 하나의 카테고리로 묶어도 됩니다.

## 4. 자동 연동 시작

1. GitHub `Settings → Actions → General → Workflow permissions`에서 **Read and write permissions**를 선택하세요. 조직 정책이 이를 막으면 설정을 바꿀 관리자 권한이 필요합니다.
2. `Actions` 탭 → **Sync Discord Artworks** → **Run workflow**를 실행해 최초 등록을 확인하세요.
3. 이후 `7,17,27,37,47,57분(UTC)`에 정기 체크합니다. **약 10분 간격이며 GitHub 실행 지연 및 Pages 배포 시간에 따라 더 늦을 수 있습니다.**
4. 작업은 그림을 `assets/artworks/`에 복사하고 `gallery.json`을 갱신하며 GitHub Actions 봇 계정으로 커밋합니다. 그 커밋으로 GitHub Pages가 다시 배포됩니다.
5. 이 방식은 **새 메시지를 증분 수집**하며, 게시물 수정·삭제나 디스코드 닉네임 변경을 기존 전시에 자동 반영하지 않습니다. 작품 삭제 요청이 오면 리포지토리의 `gallery.json` 항목과 해당 이미지 파일을 삭제하세요. 필요 시 `sync-state.json`의 커서를 확인하세요.

## 5. 작품 올리는 형식

디스코드 지정 채널에 이미지 또는 동영상 **파일을 첨부**하고 다음처럼 메시지를 남기면 됩니다.

```text
제목: 푸른 새벽
설명: 빛이 들어오기 직전의 조용한 거리.
```

- 한 메시지에 여러 이미지를 올리면 각각 **별도의 작품 카드**로 등록되며 같은 제목/설명이 사용됩니다.
- 캡션이 없으면 파일명을 제목으로 사용합니다.
- 이미지: PNG, JPEG, WebP, GIF (최대 **8 MiB**). 동영상: MP4, WebM (최대 **40 MiB**). 그보다 큰 파일은 건너뜁니다.
- **MOV, YouTube 링크, 외부 동영상 링크, Discord 링크 미리보기는 미지원**입니다. MOV는 MP4(H.264/AAC)로 변환하여 파일로 첨부하세요.
- 동영상은 브라우저에서 클릭 시 컨트롤로 재생되며 목록에는 미리보기 프레임이 표시됩니다. 브라우저에서 재생 가능한 코덱으로 인코딩해야 합니다.
- GitHub 저장소에 동영상을 직접 커밋하므로 작품이 많아지면 용량 제한에 빠르게 도달할 수 있습니다. 대용량 동영상은 별도 스토리지 연동이 필요합니다.
- 첫 동기화에서 새 채널마다 최근 메시지 최대 2,000개를 탐색합니다. 이후 마지막 동기화 커서를 기준으로 새 메시지를 읽습니다. 메시지가 매우 많은 채널은 짧은 동기화 주기를 유지하세요.
- 봇이 쓴 메시지는 수집하지 않습니다.

## 6. 전시 기능

- 첫 화면 최신 작품 **가로 슬라이드**
- 전체 작품 **카테고리 필터와 검색**
- 작가별 전시실 (Discord 사용자 ID 기준)
- 작품 **전체 확대**, 좌우 키보드 이동, 모바일 좌우 스와이프
- 작품명 · 작가명 · 설명 · 업로드 날짜 · 원본 디스코드 게시글 링크
- 반응형 모바일/PC 레이아웃

## 운영 시 알아둘 점

- **공개 GitHub 리포지토리**에 원본 작품 이미지가 업로드됩니다. 작품을 외부에 공개할 권한과 동의를 확보하세요. 자동 전시는 유해 콘텐츠가 바로 공개될 수 있으므로 규칙과 신고/삭제 절차를 마련하세요.
- GitHub 저장소 크기와 대역폭, GitHub Actions 사용 한도가 커질 수 있습니다. 큰 규모의 갤러리는 전용 이미지 스토리지(R2/S3 등)로 이전하는 편이 좋습니다.
- 디스코드 이미지 URL은 만료될 수 있으므로 이 프로젝트는 이미지와 동영상 파일을 내려받아 사이트 자체 파일로 보존합니다.
- 공개 저장소와 GitHub Pages는 비공개 디스코드 채널의 이미지도 누구나 볼 수 있게 하므로 **비공개 채널을 연결하지 마세요**.
- GitHub Actions가 오류를 내면 `Actions` 로그를 보고 봇 권한, 채널 ID, 토큰, GitHub write permissions를 확인하세요.
- GitHub Actions 정기 실행은 정확한 시각을 보장하지 않으며 비활성 공개 리포지토리에서는 자동으로 비활성화될 수 있습니다.

## 로컬 미리보기

`index.html`을 직접 더블클릭하는 대신, 이 폴더에서 명령 프롬프트를 열고 다음을 실행하세요.

```bash
python -m http.server 8000
```

그 뒤 브라우저에서 `http://localhost:8000`으로 접속하세요. 정적 파일 `fetch`를 사용하기 때문에 로컬 서버 실행이 권장됩니다.

## 기존 GitHub 프로젝트에 업데이트하기

ZIP 압축을 풀어 **기존 리포지토리의 같은 경로에 덮어쓰기**하세요. 이미 실제 작품을 수집했다면 GitHub의 `gallery.json`, `sync-state.json`, `assets/artworks/`를 **삭제하거나 초기화하지 마세요**. 이번 ZIP에는 초기 데모 파일만 들어 있으므로, 기존 작품을 운영 중인 리포지토리에서는 **`index.html`, `channels.json`, `scripts/sync_discord.py`, `README.md`만 교체**하는 것이 가장 안전합니다. 기존 `DISCORD_CHANNELS` Secret이 있다면 `channels.json`보다 우선되므로 삭제하거나 6개 채널 모두 포함하도록 변경하세요.
