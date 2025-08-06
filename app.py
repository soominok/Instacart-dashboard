import streamlit as st
import pandas as pd
import re
import plotly.express as px
import plotly.graph_objects as go

# --- 페이지 설정 ---
st.set_page_config(
    page_title="고객 세그먼트별 추천 성과 대시보드",
    page_icon="📊",
    layout="wide",
)

# --- 커스텀 CSS 스타일 ---
st.markdown("""
<style>
    /* 카드 기본 스타일 */
    .stats-card {
        background-color: #FFFFFF;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        border: 1px solid #EAEAEA;
        margin-bottom: 20px;
        height: 280px; /* 카드의 높이를 고정하여 정렬을 맞춤 */
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .stats-card h5 {
        margin-top: 0;
        margin-bottom: 20px;
        font-weight: 600;
        color: #333333;
    }
    /* 통계 행 스타일 (평균, 최소, 최대) */
    .stats-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 10px 0;
        border-bottom: 1px solid #F0F0F0;
    }
    .stats-row:last-of-type {
        border-bottom: none;
    }
    .stats-label {
        color: #666666;
        font-size: 15px;
    }
    .stats-value {
        font-size: 18px;
        font-weight: 700;
    }
    .value-blue { color: #5B8DEF; }
    .value-green { color: #3CD68A; }
    .value-orange { color: #FF9A4D; }

    /* 범위 바 스타일 */
    .range-bar-container {
        margin-top: 15px;
    }
    .range-bar {
        height: 8px;
        border-radius: 4px;
        background-color: #EAEAEA;
    }
    .range-bar-fill-purple {
        height: 100%;
        background: linear-gradient(to right, #8A6FF2, #5B8DEF);
        border-radius: 4px;
    }
    .range-bar-fill-green {
        height: 100%;
        background: linear-gradient(to right, #3CD68A, #6DEB9B);
        border-radius: 4px;
    }
    .range-labels {
        display: flex;
        justify-content: space-between;
        font-size: 12px;
        color: #888888;
        margin-top: 5px;
    }

    /* 데이터 인사이트 카드 스타일 */
    .insight-card {
        background-color: #F8F9FA;
        padding: 20px;
        border-radius: 15px;
        border-left: 5px solid #6c757d;
        margin-top: 10px;
    }
    .insight-card p {
        margin-bottom: 5px;
    }
    
    /* KPI 카드 스타일 */
    /* [수정] 핵심 지표(KPI) 카드 스타일 */
    .kpi-card {
        background-color: #FFFFFF; /* 흰색 배경 */
        padding: 25px 20px; /* 패딩 조정 */
        border-radius: 15px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        border: 1px solid #EAEAEA;
        text-align: center;
        height: 130px; /* 높이 조정 */
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .kpi-value {
        font-size: 2.2em;
        font-weight: 700;
        color: #2E3B4E; /* 어두운 색으로 변경 */
        line-height: 1.2;
    }
    .kpi-label {
        font-size: 0.9em;
        color: #6c757d;
        margin-top: 8px;
    }
</style>
""", unsafe_allow_html=True)


# --- 데이터 로딩 및 파싱 함수들 ---
@st.cache_data
def load_data(filepath):
    try:
        df = pd.read_csv(filepath, encoding='utf-8-sig')
    except FileNotFoundError:
        st.error(f"오류: '{filepath}' 파일을 찾을 수 없습니다. app.py와 같은 폴더에 있는지 확인해주세요.")
        return None
    # 데이터 타입 변환
    if 'reorder_ratio' in df.columns and df['reorder_ratio'].dtype == 'object':
        df['reorder_ratio'] = df['reorder_ratio'].str.replace('%', '', regex=False).astype(float)
    if 'total_orders' in df.columns and df['total_orders'].dtype == 'object':
        df['total_orders'] = pd.to_numeric(df['total_orders'], errors='coerce').fillna(0).astype(int)
    if 'rec_taste_score' in df.columns and df['rec_taste_score'].dtype == 'object':
        df['rec_taste_score'] = df['rec_taste_score'].str.replace('점', '', regex=False).astype(float)
    return df

def parse_key_value_string(data_string):
    if pd.isna(data_string): return pd.DataFrame(columns=['항목', '빈도'])
    try:
        items = [item.split(':') for item in data_string.split(';')]
        df_parsed = pd.DataFrame({'항목': [item[0].strip() for item in items], '빈도': [int(re.sub(r'[^0-9]', '', item[1])) for item in items]})
        return df_parsed
    except (IndexError, ValueError): return pd.DataFrame(columns=['항목', '빈도'])

def parse_stats_string(stats_string):
    if pd.isna(stats_string): return {'평균': 0, '최소': 0, '최대': 0, '단위': ''}
    avg = re.search(r"평균 ([\d\.]+)", stats_string)
    min_val = re.search(r"최소 ([\d\.]+)", stats_string)
    max_val = re.search(r"최대 ([\d\.]+)", stats_string)
    unit = re.search(r"([\S]+)\s*$", stats_string)
    return {'평균': float(avg.group(1)) if avg else 0, '최소': int(min_val.group(1)) if min_val else 0, '최대': int(max_val.group(1)) if max_val else 0, '단위': unit.group(1).strip(',') if unit else ''}

# --- 데이터 파싱 및 시각화 함수 ---
def parse_and_plot(data_string, title, chart_type='bar', orientation='h', color_scale='Blues'):
    """ 
    'Key:Value;...' 형태의 문자열을 파싱하여 지정된 타입의 차트를 그립니다.
    orientation: 'h'(가로) 또는 'v'(세로) 막대그래프
    """
    if pd.isna(data_string):
        st.info(f"{title} 데이터가 없습니다.")
        return

    try:
        items = [item.split(':') for item in data_string.split(';')]
        df_plot = pd.DataFrame({
            '항목': [item[0].strip() for item in items],
            '빈도': [int(re.sub(r'[^0-9]', '', item[1])) for item in items]
        }).sort_values('빈도', ascending=False).head(10)

        fig = None # fig 변수를 먼저 초기화

        if chart_type == 'bar':
            if orientation == 'v': # 세로 막대그래프
                # 요일 순서 정렬 로직 추가
                if '요일' in title:
                    dow_order = ['월', '화', '수', '목', '금', '토', '일']
                    df_plot['항목'] = pd.Categorical(df_plot['항목'], categories=dow_order, ordered=True)
                    df_plot = df_plot.sort_values('항목')
                fig = px.bar(df_plot, x='항목', y='빈도', title=title,
                             color='빈도', color_continuous_scale=color_scale)
            else: # 가로 막대그래프 (기본값)
                df_plot = df_plot.sort_values('빈도', ascending=True)
                fig = px.bar(df_plot, x='빈도', y='항목', title=title,
                             orientation='h', color='빈도', color_continuous_scale=color_scale)
            fig.update_layout(yaxis_title='', xaxis_title='빈도수')

        elif chart_type == 'pie':
            # 그라데이션 색상을 수동으로 생성하여 버전 호환성 높임
            colors = px.colors.get_colorscale(color_scale)
            num_colors = len(df_plot)
            pie_colors = [colors[int(i * (len(colors)-1) / (num_colors-1)) if num_colors > 1 else 0][1] for i in range(num_colors)]

            fig = px.pie(df_plot, 
                         names='항목', 
                         values='빈도', 
                         title=title,
                         color_discrete_sequence=pie_colors) # 생성된 색상 리스트를 사용
            fig.update_traces(textposition='inside', textinfo='percent+label', textfont_size=14,
                              marker=dict(line=dict(color='#000000', width=1))) # 조각 테두리 추가
            fig.update_layout(showlegend=False)

        if fig:
            st.plotly_chart(fig, use_container_width=True)
        
    except (IndexError, ValueError) as e:
        st.warning(f"'{title}' 데이터 형식에 문제가 있어 차트를 그릴 수 없습니다: {data_string}")
    except Exception as e:
        st.error(f"{title} 차트 생성 중 오류 발생: {e}")

# --- 데이터 로드 ---
df = load_data('stratified_top10_users_report.csv')
if df is None: st.stop()

# --- 사이드바 ---
st.sidebar.header("📊 필터")
segments = ['전체'] + sorted(df['segment'].unique().tolist())
selected_segment = st.sidebar.selectbox("고객 세그먼트 선택", options=segments)
if selected_segment == '전체': filtered_df = df
else: filtered_df = df[df['segment'] == selected_segment]
user_ids = sorted(filtered_df['user_id'].unique())
selected_user_id = st.sidebar.selectbox("사용자 ID 선택", options=user_ids)

# --- 메인 대시보드 ---
st.title("📊 고객 세그먼트별 추천 성과 대시보드")
st.markdown("---")
user_data = df[df['user_id'] == selected_user_id]

if not user_data.empty:
    user_info = user_data.iloc[0]

    st.header(f"👤 사용자 #{selected_user_id} 분석 리포트")
    
    profile_cols = st.columns(4)
    profile_cols[0].metric("고객 세그먼트", user_info['segment'])
    profile_cols[1].metric("총 주문 횟수", f"{user_info['total_orders']}회")
    profile_cols[2].metric("재주문율", f"{user_info['reorder_ratio']:.1f}%")
    profile_cols[3].metric("추천 정확도 (Precision)", f"{user_info['precision']:.1%}")

    with st.expander("📋 사용자 구매 요약 정보 보기", expanded=True):
        summary_cols = st.columns(2)
        order_stats = parse_stats_string(user_info['days_since_prior_order_stats'])
        basket_stats = parse_stats_string(user_info['basket_size_stats'])

        with summary_cols[0]:
            st.markdown(f"""
                <div class="stats-card">
                    <div>
                        <h5>🗓️ 주문 간격 통계</h5>
                        <div class="stats-row">
                            <span class="stats-label">평균</span>
                            <span class="stats-value value-blue">{order_stats['평균']}일</span>
                        </div>
                        <div class="stats-row">
                            <span class="stats-label">최소</span>
                            <span class="stats-value value-green">{order_stats['최소']}일</span>
                        </div>
                        <div class="stats-row">
                            <span class="stats-label">최대</span>
                            <span class="stats-value value-orange">{order_stats['최대']}일</span>
                        </div>
                    </div>
                    <div class="range-bar-container">
                        <div class="range-bar"><div class="range-bar-fill-purple"></div></div>
                        <div class="range-labels">
                            <span>{order_stats['최소']}일 (최소)</span>
                            <span>{order_stats['최대']}일 (최대)</span>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

        with summary_cols[1]:
            is_constant = "(일정함)" if basket_stats['최소'] == basket_stats['최대'] else "(최대)"
            st.markdown(f"""
                <div class="stats-card">
                    <div>
                        <h5>🛒 장바구니 크기 통계</h5>
                        <div class="stats-row">
                            <span class="stats-label">평균</span>
                            <span class="stats-value value-blue">{basket_stats['평균']}개</span>
                        </div>
                        <div class="stats-row">
                            <span class="stats-label">최소</span>
                            <span class="stats-value value-green">{basket_stats['최소']}개</span>
                        </div>
                        <div class="stats-row">
                            <span class="stats-label">최대</span>
                            <span class="stats-value value-orange">{basket_stats['최대']}개</span>
                        </div>
                    </div>
                    <div class="range-bar-container">
                        <div class="range-bar"><div class="range-bar-fill-green"></div></div>
                        <div class="range-labels">
                            <span>{basket_stats['최소']}개 (최소)</span>
                            <span>{basket_stats['최대']}개 {is_constant}</span>
                        </div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
        
        # 데이터 인사이트 섹션
        insight_text = f"""
            <div class="insight-card">
                <h5>☑️ 데이터 인사이트</h5>
                <p><b>주문 간격:</b> 고객님이 평균 <b>{order_stats['평균']}일</b>마다 재주문하며, 최소 {order_stats['최소']}일에서 최대 {order_stats['최대']}일까지 다양한 주문 패턴을 보입니다.</p>
                <p><b>장바구니 크기:</b> 주로 <b>{basket_stats['평균']}개</b>의 상품을 구매하는 안정적인 패턴을 보입니다.</p>
            </div>
        """
        st.markdown(insight_text, unsafe_allow_html=True)


    # st.markdown("---")
    # st.header("📈 사용자 구매 패턴 시각화")
    # # with st.expander("🛒 사용자 구매 패턴 시각화", expanded=True):
    
    # vis_col1, vis_col2 = st.columns(2)

    # with vis_col1:
    #     parse_and_plot(user_info.get('dow_counts'), "요일별 구매 빈도", orientation='v', color_scale='Cividis')
    #     parse_and_plot(user_info.get('department_counts'), "선호 카테고리 (Department)", chart_type='pie', color_scale='Blues')
    # with vis_col2:
    #     parse_and_plot(user_info.get('hour_counts'), "시간대별 구매 빈도", color_scale='Viridis')
    #     parse_and_plot(user_info.get('aisle_counts'), "선호 통로 (Aisle)", chart_type='pie', color_scale='Greens')


    st.markdown("---")
    
    
    # 1. 시각화를 위한 데이터 준비
    dow_df = parse_key_value_string(user_info.get('dow_counts'))
    hour_df = parse_key_value_string(user_info.get('hour_counts'))
    dept_df = parse_key_value_string(user_info.get('department_counts'))
    aisle_df = parse_key_value_string(user_info.get('aisle_counts'))

    # 2. 메인 타이틀과 서브타이틀
    st.markdown("<h2 style='text-align: center; margin-bottom: 5px;'>🛒 식료품 구매 패턴 분석</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align: center; color: #6c757d;'>요일별 구매 빈도 및 상품 카테고리 분석</p>", unsafe_allow_html=True)
    st.write("") 

    # 3. 차트 영역 (상단 2개)
    chart_row1 = st.columns(2)
    palette = ['#2E3B4E', '#5B8DEF', '#8A6FF2', '#A38CF5', '#BFABF9', '#DBCFFC']
    
    with chart_row1[0]:
        # [수정] .stats-card -> .chart-card 클래스로 변경
        st.markdown('<div class="chart-card">', unsafe_allow_html=True) 
        st.markdown("<h5>🗓️ 요일별 구매 빈도</h5>", unsafe_allow_html=True)
        if not dow_df.empty:
            dow_order = ['월', '화', '수', '목', '금', '토', '일']
            dow_df['항목'] = pd.Categorical(dow_df['항목'], categories=dow_order, ordered=True)
            dow_df = dow_df.sort_values('항목')
            
            fig = px.bar(dow_df, x='항목', y='빈도')
            fig.update_traces(marker_color='#5B8DEF', marker_line_width=0, marker=dict(cornerradius="6"))
            fig.update_layout(plot_bgcolor='white', yaxis_title=None, xaxis_title=None, margin=dict(t=0, l=0, r=0, b=0)) # 마진 최소화
            st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with chart_row1[1]:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.markdown("<h5>⏰ 시간대별 구매 빈도</h5>", unsafe_allow_html=True)
        if not hour_df.empty:
            hour_df['시간'] = hour_df['항목'].str.extract('(\d+)').astype(int)
            hour_df = hour_df.sort_values('시간')
            
            # --- 롤리팝 차트 (Lollipop Chart) 구현 시작 ---
            fig = go.Figure()

            # 1. 막대 (Lollipop stick) 추가
            fig.add_trace(go.Bar(
                x=hour_df['시간'],
                y=hour_df['빈도'],
                width=0.05, # 막대 두께를 매우 얇게 설정
                marker_color='#B0C4DE', # 연한 회색/파란색 계열
                hoverinfo='none' # 막대에는 호버 효과 없음
            ))

            # 2. 점 (Lollipop head) 추가
            fig.add_trace(go.Scatter(
                x=hour_df['시간'],
                y=hour_df['빈도'],
                mode='markers',
                marker=dict(
                    size=12, # 점 크기
                    color='#5B8DEF', # 진한 파란색
                    line=dict(width=2, color='white') # 점 테두리
                ),
                # 호버 텍스트 설정
                hovertemplate='<b>%{x}시</b><br>구매 빈도: %{y}<extra></extra>'
            ))
            # --- 롤리팝 차트 구현 끝 ---

            fig.update_layout(
                plot_bgcolor='white',
                yaxis_title=None,
                xaxis_title=None,
                margin=dict(t=10, l=10, r=10, b=10),
                showlegend=False, # 범례 숨기기
                xaxis=dict(
                    tickmode='array',
                    tickvals=hour_df['시간'],
                    ticktext=[f"{h}시" for h in hour_df['시간']]
                ),
                bargap=0.5 # 막대 사이의 간격
            )
            st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # 4. 차트 영역 (하단 2개) - 가로 막대그래프로 변경
    chart_row2 = st.columns(2)
    with chart_row2[0]:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.markdown("<h5>🏢 선호 카테고리 (Department)</h5>", unsafe_allow_html=True)
        if not dept_df.empty:
            # 빈도수가 높은 순으로 정렬 (내림차순)
            dept_df_sorted = dept_df.head(10).sort_values('빈도', ascending=True)
            
            fig = px.bar(
                dept_df_sorted,
                x='빈도',
                y='항목',
                orientation='h', # 가로 막대그래프
                color='빈도', # 빈도에 따라 그라데이션 색상 적용
                color_continuous_scale='Blues'
            )
            fig.update_layout(
                plot_bgcolor='white',
                xaxis_title=None,
                yaxis_title=None,
                coloraxis_showscale=False, # 컬러바 숨기기
                margin=dict(t=10, l=10, r=10, b=10)
            )
            st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with chart_row2[1]:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        st.markdown("<h5>🌿 선호 통로 (Aisle)</h5>", unsafe_allow_html=True)
        if not aisle_df.empty:
            # 빈도수가 높은 순으로 정렬 (내림차순)
            aisle_df_sorted = aisle_df.head(10).sort_values('빈도', ascending=True)

            fig = px.bar(
                aisle_df_sorted,
                x='빈도',
                y='항목',
                orientation='h', # 가로 막대그래프
                color='빈도', # 빈도에 따라 그라데이션 색상 적용
                color_continuous_scale='Greens'
            )
            fig.update_layout(
                plot_bgcolor='white',
                xaxis_title=None,
                yaxis_title=None,
                coloraxis_showscale=False, # 컬러바 숨기기
                margin=dict(t=10, l=10, r=10, b=10)
            )
            st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # 5. 핵심 지표(KPI) 카드 영역
    st.write("") # 여백
    kpi_cols = st.columns(4)

    # KPI 계산
    max_dow = dow_df.loc[dow_df['빈도'].idxmax()] if not dow_df.empty else {'항목': 'N/A', '빈도': 0}
    max_hour = hour_df.loc[hour_df['빈도'].idxmax()] if not hour_df.empty else {'항목': 'N/A', '빈도': 0}
    
    # 'produce' 카테고리의 비율 계산
    produce_pct = 0
    if not dept_df.empty and 'produce' in dept_df['항목'].values and dept_df['빈도'].sum() > 0:
        produce_pct = dept_df[dept_df['항목'] == 'produce']['빈도'].sum() / dept_df['빈도'].sum() * 100

    # 가장 빈도가 높은 통로(aisle)와 그 비율 계산
    top_aisle = aisle_df.iloc[0] if not aisle_df.empty else {'항목': 'N/A', '빈도': 0}
    top_aisle_pct = (top_aisle['빈도'] / aisle_df['빈도'].sum() * 100) if not aisle_df.empty and aisle_df['빈도'].sum() > 0 else 0

    # [수정] st.markdown을 사용하여 이미지와 동일한 UI로 KPI 카드 렌더링
    kpi_cols[0].markdown(
        f'<div class="kpi-card"><div class="kpi-value">{max_dow["빈도"]}</div><div class="kpi-label">{max_dow["항목"]}요일 최고 구매</div></div>',
        unsafe_allow_html=True
    )
    kpi_cols[1].markdown(
        f'<div class="kpi-card"><div class="kpi-value">{max_hour["빈도"]}</div><div class="kpi-label">{max_hour["항목"]} 최고 구매</div></div>',
        unsafe_allow_html=True
    )
    kpi_cols[2].markdown(
        f'<div class="kpi-card"><div class="kpi-value">{produce_pct:.0f}%</div><div class="kpi-label">신선식품 선호</div></div>',
        unsafe_allow_html=True
    )
    kpi_cols[3].markdown(
        f'<div class="kpi-card"><div class="kpi-value">{top_aisle_pct:.1f}%</div><div class="kpi-label">{top_aisle["항목"]} 최다 구매</div></div>',
        unsafe_allow_html=True
    )


    st.markdown("---")
    st.header("💡 추천 결과 및 이유 분석")

    rec_col1, rec_col2 = st.columns([3, 2]) # 비율 유지

    with rec_col1:
        st.subheader("상품별 취향 점수 및 구매여부")
        actual_purchases_list = set([item.strip() for item in user_info['actual_purchases'].split(';')])
        recommendations = user_data[['rec_rank', 'rec_product_name', 'rec_taste_score', 'rec_reason_tags']].copy()
        
        # [수정] '실제 구매' 컬럼을 이모지로만 깔끔하게 표시
        recommendations['구매'] = recommendations['rec_product_name'].apply(
            lambda x: "✅ 구매함" if x in actual_purchases_list else "❌ 구매안함"
        )
        
        recommendations.rename(columns={
            'rec_rank': '순위', 'rec_product_name': '추천 상품명', 
            'rec_taste_score': '취향 점수', 'rec_reason_tags': '추천 이유'
        }, inplace=True)

        rec_sorted = recommendations.sort_values('취향 점수', ascending=True)
        fig_taste = px.bar(rec_sorted, x='취향 점수', y='추천 상품명', orientation='h', 
                           color='구매', 
                           color_discrete_map={'✅ 구매함':'#1f77b4', '❌ 구매안함': '#d62728'}, 
                           height=400)
        fig_taste.update_layout(yaxis_title='', xaxis_title='취향 점수', 
                                legend_title_text='구매 여부', 
                                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_taste, use_container_width=True)
        
        with st.expander("추천 상세 데이터 테이블 보기", expanded=True):
            # [수정] 컬럼 순서 변경 로직 추가
            # 1. 보여줄 컬럼 순서를 리스트로 정의
            display_columns = ['순위', '추천 상품명', '취향 점수', '구매', '추천 이유']
            
            # 2. 정의된 순서대로 데이터프레임 재정렬
            recommendations_to_display = recommendations[display_columns].set_index('순위')

            # 3. 추천 이유 태그를 보기 좋게 변경
            recommendations_to_display['추천 이유'] = recommendations_to_display['추천 이유'].str.replace('#', '\n#')
            
            # 4. 수정된 데이터프레임 표시
            st.dataframe(recommendations_to_display, use_container_width=True)

    with rec_col2:
        st.subheader("🛒 실제 구매 상품 목록")
        st.dataframe(pd.DataFrame(list(actual_purchases_list), columns=["상품명"]), 
                     hide_index=True, use_container_width=True)

else:
    st.warning("선택된 사용자에 대한 데이터가 없습니다. 필터를 확인해주세요.")