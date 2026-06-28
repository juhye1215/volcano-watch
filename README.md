# 킬라우에아 자동 감시 서버 — 설치 안내

닫혀 있어도 **매일 자동으로 USGS 데이터를 확인하고 이메일을 보내주는** 무료 서버입니다.
내 컴퓨터를 켜둘 필요가 없습니다. GitHub의 무료 클라우드에서 알아서 돕니다.

- 비용: **0원** (GitHub Actions 무료 + Gmail 무료)
- 준비물: GitHub 계정, Gmail 계정
- 소요 시간: 약 10분

---

## 들어 있는 파일

| 파일 | 역할 |
|---|---|
| `monitor.py` | USGS 데이터를 가져와 다음 분출일을 계산하고 이메일을 보내는 본체 |
| `watch.yml` | "매일 한 번 실행해라"는 시간표 (GitHub Actions 워크플로) |
| `state.json` | 매일의 경사계 값이 자동으로 쌓이는 저장소 (없으면 자동 생성됨) |

---

## 설치 순서

### 1. GitHub 저장소(repository) 만들기
- github.com 로그인 → 오른쪽 위 `+` → **New repository**
- 이름은 `kilauea-watch` 정도로, **Public** 선택 (Public이면 실행시간 완전 무제한·무료)
- **Create repository**

### 2. 파일 두 개 올리기
- 만든 저장소에서 **Add file → Upload files**
- `monitor.py` 를 그대로 올립니다.
- `watch.yml` 은 폴더 안에 들어가야 합니다. 업로드 화면에서 파일 이름 칸에
  `.github/workflows/watch.yml` 이라고 적으면 폴더가 자동으로 만들어집니다.
- **Commit changes**

### 3. Gmail 앱 비밀번호 만들기 (이메일 발송용)
- Gmail은 보안상 일반 비밀번호로 메일을 못 보냅니다. "앱 비밀번호"라는 16자리 전용 비밀번호가 필요합니다.
- 구글 계정 → **보안** → **2단계 인증**을 먼저 켜기
- 그다음 **앱 비밀번호** 검색 → 새로 생성 → 나오는 16자리를 복사 (예: `abcd efgh ijkl mnop`)

### 4. 비밀값 3개 등록하기
- 저장소 → **Settings → Secrets and variables → Actions → New repository secret**
- 아래 3개를 하나씩 추가합니다.

| 이름(Name) | 값(Value) |
|---|---|
| `SMTP_USER` | 내 Gmail 주소 (예: `me@gmail.com`) |
| `SMTP_PASS` | 위에서 만든 16자리 앱 비밀번호 (띄어쓰기 빼고 입력) |
| `MAIL_TO` | 알림을 받을 이메일 주소 |

### 5. 한번 테스트 실행
- 저장소 → **Actions** 탭 → 왼쪽 **Kīlauea watch** → 오른쪽 **Run workflow**
- 1~2분 뒤 `MAIL_TO` 주소로 메일이 오면 성공입니다.

### 6. 끝
- 이제 매일 오전 10시(하와이 시간)쯤 자동으로 확인하고 메일을 보냅니다.
- 컴퓨터를 꺼도 GitHub 클라우드에서 계속 돕니다.

---

## 받는 메일 예시

```
제목: ⚠️ Kīlauea Episode 51 likely ~Jul 10 (88% charged)

Predicted onset:  Friday, July 10, 2026
Recharge:         [█████████████████░░░] 88%
Tilt recovered:   13.6 µrad
Threshold:        15.5 µrad
Days remaining:   2
```

분출이 가까워지면 제목에 ⚠️, 실제로 분출이 시작되면 🌋 가 붙습니다.

---

## 바꾸고 싶을 때

- **시간 바꾸기**: `watch.yml`의 `cron: '0 20 * * *'`에서 `20`이 UTC 기준 시(時)입니다.
  하와이 시간 = UTC − 10. 예) 오전 7시 하와이 = `0 17 * * *`.
- **하루 두 번 받기**: 줄을 하나 더 추가하면 됩니다. 예) `- cron: '0 8 * * *'`
- **변화가 있을 때만 받기**: 원하시면 "충전율이 오르거나 분출이 임박할 때만 발송"하도록
  바꿔 드릴 수 있습니다.

문제가 생기면 Actions 탭의 빨간 ✗ 로그를 캡처해 주시면 바로 고쳐 드리겠습니다.
