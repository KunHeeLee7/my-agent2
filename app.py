import os
from pathlib import Path

import openai
import requests
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel


load_dotenv(Path(__file__).parent / ".env")


class ExchangeQuestion(BaseModel):
    base: str | None
    quote: str | None
    amount: float | None
    clarification: str | None


st.title("💱 실시간 환율 챗봇")
st.caption("Frankfurter의 최신 일별 기준 환율을 조회합니다. 실시간 시장 체결가는 아닙니다.")
st.info("예: 100달러는 원화로 얼마야? / 1유로는 엔화로 얼마야?")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("환율이나 환산할 금액을 질문해 보세요."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        if not os.getenv("OPENAI_API_KEY"):
            answer = "`.env` 파일에 OPENAI_API_KEY를 설정해 주세요."
        else:
            try:
                with st.spinner("환율을 조회하고 있습니다..."):
                    client = OpenAI()
                    response = client.responses.parse(
                        model="gpt-5.4-mini",
                        input=[
                            {"role": "system", "content": (
                                "사용자의 환율 질문에서 기준 통화, 대상 통화와 금액을 추출하세요. "
                                "통화는 ISO 4217 세 글자 코드로 변환하세요. 환율만 묻고 금액이 없으면 1을 사용하세요. "
                                "명확하지 않거나 환율과 무관한 질문은 추측하지 말고 clarification에 한국어로 되물으세요. "
                                "필요한 값이 없으면 해당 필드를 null로 설정하세요. 환율을 직접 추측하지 마세요."
                            )},
                            {"role": "user", "content": prompt},
                        ],
                        text_format=ExchangeQuestion,
                    )
                    question = response.output_parsed
                    if question is None:
                        answer = "질문을 이해하지 못했어요. 통화와 금액을 다시 알려 주세요."
                    elif question.clarification:
                        answer = question.clarification
                    elif not question.base or not question.quote or question.amount is None or question.amount < 0:
                        answer = "기준 통화, 대상 통화와 0 이상의 금액을 알려 주세요."
                    elif not (question.base.isascii() and question.base.isalpha() and len(question.base) == 3 and question.quote.isascii() and question.quote.isalpha() and len(question.quote) == 3):
                        answer = "통화를 확인하지 못했어요. USD, KRW처럼 통화 코드를 알려 주세요."
                    elif question.base.upper() == question.quote.upper():
                        answer = "같은 통화끼리는 환율 조회가 필요 없습니다."
                    else:
                        base, quote = question.base.upper(), question.quote.upper()
                        result = requests.get(
                            f"https://api.frankfurter.dev/v2/rate/{base}/{quote}", timeout=10
                        )
                        result.raise_for_status()
                        data = result.json()
                        rate = data["rate"]
                        answer = (
                            f"**{question.amount:,.2f} {data['base']} = "
                            f"{question.amount * rate:,.2f} {data['quote']}**\n\n"
                            f"- 기준 통화: {data['base']}\n"
                            f"- 대상 통화: {data['quote']}\n"
                            f"- 1 {data['base']} 환율: {rate:,.4f} {data['quote']}\n"
                            f"- 환율 기준일: {data['date']}\n\n"
                            "Frankfurter의 최신 일별 기준 환율이며 실시간 체결가는 아닙니다."
                        )
            except openai.AuthenticationError:
                answer = "OpenAI API 키를 확인해 주세요."
            except openai.RateLimitError:
                answer = "OpenAI API 사용 한도 또는 요청 제한을 확인해 주세요."
            except openai.APIError:
                answer = "OpenAI API에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요."
            except (requests.RequestException, ValueError, KeyError, TypeError):
                answer = "환율을 조회하지 못했습니다. 통화 코드와 네트워크 연결을 확인해 주세요."

        st.markdown(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})
