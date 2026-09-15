# 문서 생성기 시작 안내

## 먼저 구분하기

| 찾는 내용 | 시작 위치 |
| --- | --- |
| 프로젝트 사용법 | [README](README.md) |
| 우리가 정한 문서 작성 규칙 | [5종 작성 가이드](rules/INDEX.md) |
| 폴더·본문·팀 운영 정책 | [정책 문서](docs/policies/INDEX.md) |
| 실제 회사·제품 등록 | [운영 설정](config/INDEX.md) |
| 테스트용 가상 회사·제품 | [데모 전용 안내](examples/demo/INDEX.md) |
| 캡처·AI 실행 방법 | [사용 가이드](docs/guides/INDEX.md) |
| 요청 반영 여부·테스트 결과 | [개발 기록](docs/development/INDEX.md) |

## 설정을 바꿀 때

| 변경할 항목 | 위치 |
| --- | --- |
| 문서 분류·필수 항목 | [산출물 정책](policies/INDEX.md) |
| 단계 순서·검사 기준 | [작업 흐름](workflows/INDEX.md) |
| 역할별 담당자 | [역할](roles/INDEX.md) |
| 문서 유형별 필수 절 | [문서 계약](templates/INDEX.md) |
| 공통 글꼴·표·페이지 서식 | [기본 테마](themes/INDEX.md), 실제 회사는 config/companies의 theme.json |
| 브라우저·언어·해상도 | [캡처 프로필](profiles/capture/INDEX.md) |
| 회사·제품 설정의 실제 위치 | [설정 목록](config/catalog.json) |

## 개발할 때

[수집 모듈](collector/INDEX.md) · [보조 도구](tools/INDEX.md) · [테스트](tests/INDEX.md)

실행 시 만들어지는 workspaces/에는 조사·본문·리뷰가 분류되고 자체 INDEX가 생성됩니다. output/은 캡처·조회·출력물입니다. 이 두 폴더와 .local/은 Git에 포함하지 않습니다.
