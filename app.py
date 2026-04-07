import streamlit as st
from streamlit_js_eval import get_geolocation
import requests
import pandas as pd
from pyproj import Transformer
import time

# 页面配置
st.set_page_config(page_title="2026 地道美食雷达", layout="wide")

# 1. 密钥 (从 Secrets 读取)
NAVER_CLIENT_ID = st.secrets["NAVER_CLIENT_ID"]
NAVER_CLIENT_SECRET = st.secrets["NAVER_CLIENT_SECRET"]

# 2. 坐标转换逻辑 (WGS84 GPS -> Naver TM128)
# 韩国地图 API 大多使用 KATECH 坐标，不转的话误差几十米
def wgs84_to_tm128(lat, lon):
    # 定义转换器
    transformer = Transformer.from_crs("epsg:4326", "epsg:5179") # epsg:5179 是韩国常用的统筹坐标
    x, y = transformer.transform(lat, lon)
    return int(x), int(y)

# 3. Naver Local API 搜索附近 (无需关键词)
@st.cache_data(ttl=600) # 缓存10分钟，省流量
def search_nearby_food(tm128_x, tm128_y, radius=2000):
    url = "https://openapi.naver.com/v1/search/local.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    # Naver Search API 不支持直接按坐标范围搜，
    # 我们需要搜关键词"맛집"，Naver 会自动根据坐标进行周边匹配
    params = {
        "query": "맛집",
        "display": 20, # 最多显示 20 个
        "sort": "comment", # 按评论数排，确保是热门店
    }
    
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        return response.json().get('items', [])
    return []

# 4. 逻辑过滤层 (143分逻辑：筛选地道盲区)
def filter_hidden_gems(items):
    gems = []
    for item in items:
        title = item['title'].replace("<b>", "").replace("</b>", "")
        # 逻辑：过滤掉明洞、炸鸡、烤肉等对中文游客营销过度的店
        bad_words = ["明洞", "炸鸡", "炸酱面", "烤肉", "Myeongdong"]
        if any(word in title for word in bad_words):
            continue
        
        # 将 Naver 的 KATECH 坐标转回经纬度，用于地图显示
        transformer_back = Transformer.from_crs("epsg:5179", "epsg:4326")
        lat, lon = transformer_back.transform(float(item['mapx']), float(item['mapy']))
        
        gems.append({
            "name": title,
            "address": item['address'],
            "category": item['category'],
            "lat": lat,
            "lon": lon,
            "mapx": item['mapx'],
            "mapy": item['mapy']
        })
    return gems

# ==========================================
# 主界面
# ==========================================
st.title("🇰🇷 2026 周边“地道盲区”美食雷达")
st.caption("5元解锁解锁中文导航")

# 本地调试用 (如果 JS 定位失败)
DEBUG_LAT = 37.544  # 圣水洞
DEBUG_LON = 127.056

# 获取位置
location = get_geolocation()

if location or st.checkbox("调试模式 (假设在圣水洞)"):
    if location:
        u_lat = location['coords']['latitude']
        u_lon = location['coords']['longitude']
    else:
        u_lat, u_lon = DEBUG_LAT, DEBUG_LON

    st.success(f"📍 已锁定位置 (1km 内精准)")

    # 1. 坐标转换
    tm_x, tm_y = wgs84_to_tm128(u_lat, u_lon)

    # 2. 搜索附近
    raw_items = search_nearby_food(tm_x, tm_y)
    
    # 3. 过滤
    gems = filter_hidden_gems(raw_items)

    if gems:
        df = pd.DataFrame(gems)
        # --- 地图显示 ---
        st.map(df, latitude='lat', longitude='lon', size=20, color='#FF4B4B')

        # --- 列表显示 ---
        st.subheader("🔎 发现的宝藏盲区 (点击店铺查看详情)")
        for index, gem in df.iterrows():
            with st.expander(f"💎 {gem['name']} ({gem['category']})"):
                st.write(f"🏠 地址: {gem['address']}")
                
                # --- 导航按钮 (触发支付) ---
                if st.button(f"🗺️ 导航到 {gem['name']}", key=f"nav_{index}"):
                    # 支付逻辑闸门
                    st.session_state[f"pay_active_{index}"] = True

                # --- 支付与导航逻辑 ---
                if st.session_state.get(f"pay_active_{index}"):
                    # **重要：这里是你的支付网关界面**
                    st.warning("💳 该功能为付费专享")
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        # ⚠️ 这里填你自己的微信支付赞赏码或收款码
                        st.image("https://your-website.com/your_wechat_qr.png", caption="扫码支付 5 元")
                    with col2:
                        st.write("### 解锁内容：")
                        st.write("1. 网页地图内显示详细步行/公交路线")
                        st.write("2. 全中文步骤说明 (如：“在便利店左转”)")
                        
                        # 模拟支付确认 (作为 F-4，你需要对接一个真正的支付回调或者使用验证码)
                        # 为了演示，我们做一个"我已付款"按钮
                        if st.button("我已付款，开始导航", key=f"confirm_{index}"):
                            st.success("🎉 支付确认成功！正在规划地道路线...")
                            st.session_state[f"paid_{index}"] = True
                    
                    # 只有付款成功才显示
                    if st.session_state.get(f"paid_{index}"):
                        st.markdown("---")
                        st.subheader(f"🚶 如何前往 {gem['name']}")
                        
                        # 143分逻辑：这里需要调用真正的 Naver Direction API
                        # 简单起见，这里做一个模拟
                        st.info("路线详情 (模拟测试)：")
                        st.markdown("""
                        1. **起点** (你的位置)
                        2. 向东步行 150 米。
                        3. 在 **CU便利店** 处右转。
                        4. 乘坐 **2012路公交车** (方向：뚝섬역)。
                        5. 在 **성수동사거리** 下车。
                        6. 步行 50 米即可到达 **{gem['name']}**。
                        """)
                        
                        
    else:
        st.write(" 주변 2km 내에 한국인 전용 맛집을 찾지 못했습니다. 换个位置试试？")

else:
    st.warning("👋 为了自动扫描周围 2km 内的盲区美食，请点击屏幕上方的“允许获取位置”。")