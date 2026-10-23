"""
로컬 LLM 댓글 라벨링 스모크 테스트
준비: pip install ollama pydantic
실행: python smoke_test.py qwen3:8b
"""
import sys
import time
from typing import Literal

import ollama
from pydantic import BaseModel

MODEL = sys.argv[1] if len(sys.argv) > 1 else "qwen3:8b"

POLICY = "정부가 수도권 주택담보대출 한도를 6억 원으로 제한하는 대출 규제를 발표했다."

COMMENTS = [
    "이제야 정신 차렸네. 빚내서 집 사는 거 막아야 함",
    "서민은 평생 집 사지 말라는 거지? 현금부자만 신났다",
    "와 대단하다 대단해~ 이번엔 진짜 집값 잡겠네ㅋㅋㅋ",
    "효과는 몇 달 지나봐야 알 듯",
    "앵커 목소리 좋다",
]


class Label(BaseModel):
    id: int
    relevant: bool  # 정책과 관련된 댓글인가
    sarcasm: bool   # stance보다 먼저 판단하게 순서를 앞으로
    stance: Literal["support", "oppose", "neutral"]  # 비꼼이면 실제 의도 기준
    target: Literal["government", "policy", "market", "other"]


class LabelBatch(BaseModel):
    labels: list[Label]


SYSTEM = (
    "너는 한국어 유튜브 뉴스 댓글을 분류하는 연구 보조원이다. "
    "각 댓글이 주어진 정책에 대해 어떤 입장인지 판단한다. "
    "비꼬는 말투(반어법)는 실제 의도로 해석하고 sarcasm=true로 표시한다. "
    "정책과 무관한 댓글은 relevant=false, stance=neutral, target=other로 둔다."
)


def label_batch(comments: list[str]) -> LabelBatch:
    numbered = "\n".join(f"{i}: {c}" for i, c in enumerate(comments))
    resp = ollama.chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"정책: {POLICY}\n\n댓글:\n{numbered}"},
        ],
        format=LabelBatch.model_json_schema(),
        options={"temperature": 0},
        think=False,  # Qwen3 생각 모드 끄기 (지원 안 하는 모델은 무시됨)
    )
    return LabelBatch.model_validate_json(resp.message.content)


if __name__ == "__main__":
    start = time.time()
    result = label_batch(COMMENTS)
    elapsed = time.time() - start

    for lab in result.labels:
        print(f"[{lab.stance:>7} | {lab.target:<10} | 관련={lab.relevant!s:<5} | 비꼼={lab.sarcasm!s:<5}] {COMMENTS[lab.id]}")
    print(f"\n모델: {MODEL} | 댓글 {len(COMMENTS)}개 | {elapsed:.1f}초")
