"""
Gemini AI Code Review Script
PR의 변경사항을 분석하고 코드 리뷰를 자동으로 작성합니다.
"""

import os
import requests
from google import genai


def get_pr_diff() -> str:
    """PR diff 파일 읽기"""
    with open("pr_diff.txt", "r", encoding="utf-8") as f:
        return f.read()


def truncate_diff(diff: str, max_chars: int = 30000) -> str:
    """diff가 너무 길면 자르기"""
    if len(diff) > max_chars:
        return diff[:max_chars] + "\n\n... (truncated)"
    return diff


def review_with_gemini(diff: str) -> str:
    """Gemini API로 코드 리뷰 수행"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found")

    client = genai.Client(api_key=api_key)

    prompt = f"""당신은 시니어 소프트웨어 엔지니어입니다. 아래 코드 변경사항(diff)을 리뷰해주세요.

## 리뷰 기준
1. **버그/오류**: 잠재적 버그나 런타임 오류
2. **보안**: 보안 취약점 (하드코딩된 비밀, SQL 인젝션 등)
3. **성능**: 비효율적인 코드, 불필요한 연산
4. **코드 품질**: 가독성, 네이밍, 중복 코드
5. **베스트 프랙티스**: Python/프레임워크 권장 사항

## 응답 형식
한국어로 작성하고, 마크다운 형식을 사용하세요:

### 요약
(1-2문장으로 변경사항 요약)

### 발견된 이슈
(이슈가 있으면 파일명:라인 형식으로)
- **[심각도]** 설명

### 개선 제안
(선택적 개선 사항)

### 전체 평가
⭐ 점수 (1-5) + 한줄평

---

## 코드 변경사항 (diff)
```diff
{diff}
```
"""

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )
    return response.text


def post_comment(review: str) -> None:
    """GitHub PR에 코멘트 작성"""
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("REPO")
    pr_number = os.environ.get("PR_NUMBER")

    if not all([token, repo, pr_number]):
        raise ValueError("Missing GitHub environment variables")

    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    body = f"""## 🤖 Gemini AI Code Review

{review}

---
<sub>Powered by Gemini 2.0 Flash | [Report Issue](https://github.com/{repo}/issues)</sub>
"""

    response = requests.post(url, headers=headers, json={"body": body}, timeout=30)
    response.raise_for_status()
    print(f"Comment posted successfully: {response.json()['html_url']}")


def main() -> None:
    """메인 실행"""
    print("Reading PR diff...")
    diff = get_pr_diff()

    if not diff.strip():
        print("No diff found, skipping review")
        return

    print(f"Diff size: {len(diff)} characters")
    diff = truncate_diff(diff)

    print("Requesting Gemini review...")
    review = review_with_gemini(diff)

    print("Posting comment to PR...")
    post_comment(review)

    print("AI Review completed!")


if __name__ == "__main__":
    main()
