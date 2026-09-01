import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta

# ---------------------------------------------------
# 페이지 기본 설정
# ---------------------------------------------------
st.set_page_config(
    page_title="주가 조회 앱",
    page_icon="📈",
    layout="centered",
)

# ---------------------------------------------------
# 제목과 간단한 설명
# ---------------------------------------------------
st.title("📈 내 주식 한눈에 보기")
st.markdown(
    """
    종목 코드를 입력하면 최근 1년간의 주가 흐름을 그래프로 보여드려요.  
    예시) 삼성전자 → `005930.KS`, 애플 → `AAPL`, 카카오 → `035720.KS`
    """
)

st.divider()

# ---------------------------------------------------
# 종목 코드 입력창
# ---------------------------------------------------
ticker_input = st.text_input(
    "🔎 종목 코드를 입력해 주세요",
    value="005930.KS",
    help="한국 주식은 종목코드 뒤에 .KS(코스피) 또는 .KQ(코스닥)를 붙여주세요. 미국 주식은 티커만 입력하면 돼요.",
)

# 앞뒤 공백 제거 + 대문자로 변환 (티커는 보통 대문자로 씀)
ticker = ticker_input.strip().upper()

# ---------------------------------------------------
# 주가 데이터 불러오기 함수
# ---------------------------------------------------
@st.cache_data(ttl=3600)  # 한 시간 동안은 같은 종목이면 다시 안 불러오고 캐시 사용
def load_stock_data(ticker_code: str) -> pd.DataFrame:
    """yfinance로 최근 1년치 일별 주가를 가져오는 함수"""
    end_date = datetime.today()
    start_date = end_date - timedelta(days=365)

    data = yf.download(
        ticker_code,
        start=start_date,
        end=end_date,
        progress=False,
    )
    return data


@st.cache_data(ttl=3600)
def load_company_name(ticker_code: str) -> str:
    """종목의 회사 이름을 가져오는 함수 (실패하면 종목 코드 그대로 반환)"""
    try:
        info = yf.Ticker(ticker_code).info
        return info.get("longName") or info.get("shortName") or ticker_code
    except Exception:
        return ticker_code


# ---------------------------------------------------
# 메인 로직: 종목 코드가 입력되었을 때만 실행
# ---------------------------------------------------
if ticker:
    with st.spinner(f"'{ticker}' 데이터를 불러오는 중이에요..."):
        df = load_stock_data(ticker)

    # 데이터가 비어있으면 잘못된 종목 코드일 가능성이 높음
    if df.empty:
        st.error("❗ 데이터를 찾을 수 없어요. 종목 코드를 다시 확인해 주세요.")
    else:
        # yfinance가 여러 종목을 조회할 때처럼 컬럼이 다중 레벨로 나올 때가 있어 정리해줌
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        company_name = load_company_name(ticker)

        # -------------------------------------------
        # 현재가 & 1년 등락률 계산
        # -------------------------------------------
        first_price = float(df["Close"].iloc[0])   # 1년 전 종가
        last_price = float(df["Close"].iloc[-1])    # 가장 최근 종가
        change_amount = last_price - first_price
        change_percent = (change_amount / first_price) * 100

        st.subheader(f"{company_name} ({ticker})")

        # 지표 카드 2개를 나란히 표시
        col1, col2 = st.columns(2)
        with col1:
            st.metric(
                label="현재가",
                value=f"{last_price:,.2f}",
            )
        with col2:
            st.metric(
                label="1년 등락률",
                value=f"{change_percent:+.2f}%",
                delta=f"{change_amount:+,.2f}",
            )

        st.divider()

        # -------------------------------------------
        # Plotly로 꺾은선 그래프 그리기
        # -------------------------------------------
        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["Close"],
                mode="lines",
                name="종가",
                line=dict(color="#F4A825", width=2),  # 따뜻한 노란빛 라인
                fill="tozeroy",
                fillcolor="rgba(244, 168, 37, 0.12)",
            )
        )

        fig.update_layout(
            title="최근 1년 주가 흐름",
            xaxis_title="날짜",
            yaxis_title="종가",
            template="plotly_white",
            hovermode="x unified",
            margin=dict(l=20, r=20, t=50, b=20),
        )

        st.plotly_chart(fig, use_container_width=True)

        # -------------------------------------------
        # 원본 데이터 표로도 확인하고 싶은 사람을 위한 접이식 섹션
        # -------------------------------------------
        with st.expander("📋 원본 데이터 표로 보기"):
            st.dataframe(df.sort_index(ascending=False))

else:
    st.info("👆 위 입력창에 종목 코드를 입력하면 그래프가 나타나요.")

st.divider()
st.caption("데이터 출처: Yahoo Finance (yfinance) · 투자 판단의 참고용이며, 실제 투자 결정에 대한 책임은 본인에게 있어요.")
