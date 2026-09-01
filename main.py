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
    종목 코드를 입력하면 주가 흐름을 그래프로 보여드려요. 두 종목을 나란히 비교할 수도 있어요.  
    예시) 삼성전자 → `005930.KS`, 애플 → `AAPL`, 카카오 → `035720.KS`
    """
)

st.divider()

# ---------------------------------------------------
# 기간 선택 (버튼 4개)
# ---------------------------------------------------
# 버튼 이름 : (yfinance에 넘길 기간 문자열, 화면에 보여줄 이름)
PERIOD_OPTIONS = {
    "1개월": "1mo",
    "6개월": "6mo",
    "1년": "1y",
    "5년": "5y",
}

# 처음 화면을 열었을 때 기본값은 "1년"으로 설정
if "selected_period_label" not in st.session_state:
    st.session_state.selected_period_label = "1년"

st.markdown("**📅 조회 기간을 선택하세요**")
period_cols = st.columns(len(PERIOD_OPTIONS))

for col, label in zip(period_cols, PERIOD_OPTIONS.keys()):
    with col:
        # 현재 선택된 기간 버튼은 강조(primary) 스타일로 보여줌
        is_selected = st.session_state.selected_period_label == label
        if st.button(
            label,
            use_container_width=True,
            type="primary" if is_selected else "secondary",
            key=f"period_{label}",
        ):
            st.session_state.selected_period_label = label
            st.rerun()

selected_label = st.session_state.selected_period_label
selected_period = PERIOD_OPTIONS[selected_label]

st.divider()

# ---------------------------------------------------
# 종목 코드 입력창 2개 (나란히 배치)
# ---------------------------------------------------
st.markdown("**🔎 비교할 종목을 입력하세요 (두 번째는 선택 사항이에요)**")
input_col1, input_col2 = st.columns(2)

with input_col1:
    ticker_input_1 = st.text_input(
        "종목 1",
        value="005930.KS",
        help="한국 주식은 종목코드 뒤에 .KS(코스피) 또는 .KQ(코스닥)를 붙여주세요. 미국 주식은 티커만 입력하면 돼요.",
    )

with input_col2:
    ticker_input_2 = st.text_input(
        "종목 2 (선택)",
        value="",
        placeholder="예: AAPL",
        help="비워두면 종목 1만 조회해요.",
    )

# 앞뒤 공백 제거 + 대문자로 변환 (티커는 보통 대문자로 씀)
ticker_1 = ticker_input_1.strip().upper()
ticker_2 = ticker_input_2.strip().upper()

# 실제로 조회할 종목 코드 목록 (중복 입력은 한 번만 처리)
tickers_to_load = []
for t in [ticker_1, ticker_2]:
    if t and t not in tickers_to_load:
        tickers_to_load.append(t)

# 그래프에 사용할 색상 (첫 번째, 두 번째 종목 구분용)
LINE_COLORS = ["#F4A825", "#5B8C5A"]  # 따뜻한 노란색, 차분한 초록색

# ---------------------------------------------------
# 주가 데이터 불러오기 함수
# ---------------------------------------------------
@st.cache_data(ttl=3600)  # 한 시간 동안은 같은 종목/기간이면 다시 안 불러오고 캐시 사용
def load_stock_data(ticker_code: str, period: str) -> pd.DataFrame:
    """yfinance로 선택한 기간의 일별 주가를 가져오는 함수"""
    data = yf.download(
        ticker_code,
        period=period,
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


def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    """yfinance가 컬럼을 다중 레벨로 줄 때가 있어 한 단계로 정리해주는 함수"""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


# ---------------------------------------------------
# 메인 로직: 입력된 종목마다 데이터를 불러와 처리
# ---------------------------------------------------
if not tickers_to_load:
    st.info("👆 위 입력창에 종목 코드를 입력하면 그래프가 나타나요.")
else:
    stock_results = []  # 정상적으로 불러온 종목들의 정보를 담아둘 리스트

    for ticker in tickers_to_load:
        with st.spinner(f"'{ticker}' 데이터를 불러오는 중이에요..."):
            df = load_stock_data(ticker, selected_period)

        # 데이터가 비어있으면 잘못된 종목 코드일 가능성이 높음
        if df.empty:
            st.error(f"❗ '{ticker}' 데이터를 찾을 수 없어요. 종목 코드를 다시 확인해 주세요.")
            continue

        df = clean_columns(df)
        company_name = load_company_name(ticker)

        stock_results.append({
            "ticker": ticker,
            "name": company_name,
            "df": df,
        })

    # -------------------------------------------
    # 종목별 지표 카드 (현재가 · 등락률 · 최고가 · 최저가 · 평균가)
    # -------------------------------------------
    for idx, stock in enumerate(stock_results):
        df = stock["df"]

        first_price = float(df["Close"].iloc[0])   # 기간 시작 시점 종가
        last_price = float(df["Close"].iloc[-1])    # 가장 최근 종가
        change_amount = last_price - first_price
        change_percent = (change_amount / first_price) * 100

        highest_price = float(df["Close"].max())     # 기간 내 최고가
        lowest_price = float(df["Close"].min())       # 기간 내 최저가
        average_price = float(df["Close"].mean())     # 기간 내 평균가

        st.subheader(f"{stock['name']} ({stock['ticker']})")

        # 첫 번째 줄: 현재가, 등락률
        row1_col1, row1_col2 = st.columns(2)
        with row1_col1:
            st.metric(label="현재가", value=f"{last_price:,.2f}")
        with row1_col2:
            st.metric(
                label=f"{selected_label} 등락률",
                value=f"{change_percent:+.2f}%",
                delta=f"{change_amount:+,.2f}",
            )

        # 두 번째 줄: 최고가, 최저가, 평균가
        row2_col1, row2_col2, row2_col3 = st.columns(3)
        with row2_col1:
            st.metric(label="최고가", value=f"{highest_price:,.2f}")
        with row2_col2:
            st.metric(label="최저가", value=f"{lowest_price:,.2f}")
        with row2_col3:
            st.metric(label="평균가", value=f"{average_price:,.2f}")

        st.write("")  # 종목 카드 사이 여백

    if stock_results:
        st.divider()

        # -------------------------------------------
        # Plotly로 꺾은선 그래프 그리기 (종목이 2개면 한 그래프에 같이 표시)
        # -------------------------------------------
        fig = go.Figure()

        for idx, stock in enumerate(stock_results):
            df = stock["df"]
            color = LINE_COLORS[idx % len(LINE_COLORS)]

            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=df["Close"],
                    mode="lines",
                    name=f"{stock['name']} ({stock['ticker']})",
                    line=dict(color=color, width=2),
                )
            )

        fig.update_layout(
            title=f"최근 {selected_label} 주가 흐름",
            xaxis_title="날짜",
            yaxis_title="종가",
            template="plotly_white",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=20, r=20, t=60, b=20),
        )

        st.plotly_chart(fig, use_container_width=True)

        # -------------------------------------------
        # 원본 데이터 표로도 확인하고 싶은 사람을 위한 접이식 섹션
        # -------------------------------------------
        for stock in stock_results:
            with st.expander(f"📋 {stock['name']} ({stock['ticker']}) 원본 데이터 표로 보기"):
                st.dataframe(stock["df"].sort_index(ascending=False))

st.divider()
st.caption("데이터 출처: Yahoo Finance (yfinance) · 투자 판단의 참고용이며, 실제 투자 결정에 대한 책임은 본인에게 있어요.")
