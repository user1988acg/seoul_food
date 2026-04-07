import streamlit as st
from streamlit_js_eval import get_geolocation
import requests
import pandas as pd
from pyproj import Transformer
import folium
from streamlit_folium import st_folium
import time

# 页面配置
st.set_page_config(page_title="2026 地道美食雷达", layout="wide")

# 1. 密钥管理 (请确保 Secrets 中有这四个键)
# Naver Search API (用于找店)
# 搜索 API
S_ID = st.secrets["SEARCH_ID"]
S_SECRET = st.secrets["SEARCH_SECRET"]

# 路径/地图 API
NCP_ID = st.secrets["MAP_ID"]
NCP_SECRET = st.secrets["MAP_SECRET"]
# 2. 坐标转换工具
to_naver = Transformer.from_crs("epsg:4326", "epsg:5179", always_xy=True)
to_wgs84 = Transformer.from_crs("epsg:5179", "epsg:4326", always_xy=True)

# 3. 搜索附近美食
@st.cache_data(ttl=600)
def search_nearby_food(lat, lon):
    # 第一步：逆地理编码，把经纬度转成“街道名”，搜索才准
    # 这里简化处理：直接搜索关键词，Naver 搜索 API 会优先匹配相关度
    url = "https://openapi.naver.com/v1/search/local.json"
    headers = {"X-Naver-Client-Id": S_ID, "X-Naver-Client-Secret": S_SECRET}
    
    # 模拟“地道搜索”：搜一些韩国人爱用但游客少用的词
    params = {
        "query": "현지인 맛집", # “当地人美食店”
        "display": 15,
        "sort": "comment"
    }
    
    res = requests.get(url, headers=headers, params=params)
    if res.status_code == 200:
        return res.json().get('items', [])
    return []

# 4. 获取路径规划数据
def get_route_data(start_lon, start_lat, goal_lon, goal_lat):
    url = "https://naveropenapi.apigw.ntruss.com/map-direction/v1/driving"
    headers = {"X-NCP-APIGW-API-KEY-ID": NCP_ID, "X-NCP-APIGW-API-KEY": NCP_SECRET}
    params = {
        "start": f"{start_lon},{start_lat}",
        "goal": f"{goal_lon},{goal_lat}",
        "option": "trafast"
    }
    res = requests.get(url, headers=headers, params=params)
    return res.json()

# 5. 渲染 Folium 网页内地图
def render_route_map(route_json):
    path = route_json['route']['trafast'][0]['path']
    path_points = [[p[1], p[0]] for p in path] # 转为 lat, lon
    
    m = folium.Map(location=path_points[len(path_points)//2], zoom_start=15)
    folium.PolyLine(path_points, color="red", weight=5, opacity=0.7).add_to(m)
    folium.Marker(path_points[0], popup="起点").add_to(m)
    folium.Marker(path_points[-1], popup="终点").add_to(m)
    return m

# ==========================================
# 主界面逻辑
# ==========================================
st.title("🇰🇷 2026 周边“地道盲区”美食雷达")

# 初始化 session_state
if 'paid_list' not in st.session_state:
    st.session_state.paid_list = []

location = get_geolocation()
if location or st.checkbox("调试模式 (圣水洞)"):
    u_lat, u_lon = (location['coords']['latitude'], location['coords']['longitude']) if location else (37.544, 127.056)
    
    st.success(f"📍 当前定位：经度 {u_lon:.4f}, 纬度 {u_lat:.4f}")

    # 搜索
    items = search_nearby_food(u_lat, u_lon)
    
    processed_gems = []
    for item in items:
        # 坐标转换：Naver Search 返回的是 TM128 格式，必须转回 WGS84 才能在地图显示
        # 修正：Naver 的 mapx/mapy 需要除以 1e7 或者使用特定的 Transformer
        try:
            # 这是一个常见的 Naver 坐标转换 trick
            lon_wgs, lat_wgs = to_wgs84.transform(float(item['mapx']), float(item['mapy']))
            processed_gems.append({
                "name": item['title'].replace("<b>","").replace("</b>",""),
                "address": item['address'],
                "category": item['category'],
                "lat": lat_wgs,
                "lon": lon_wgs
            })
        except: continue

    if processed_gems:
        df = pd.DataFrame(processed_gems)
        st.map(df) # 先显示一个总览大图

        st.subheader("🔎 发现的宝藏点")
        for i, gem in enumerate(processed_gems):
            with st.expander(f"💎 {gem['name']} ({gem['category']})"):
                st.write(f"🏠 地址: {gem['address']}")
                
                # 状态判断
                is_paid = f"paid_{i}" in st.session_state.paid_list
                
                if not is_paid:
                    if st.button(f"解锁中文导航 (¥5)", key=f"pay_{i}"):
                        st.warning("请扫码支付")
                        st.image("https://your-website.com/qr.png", width=200)
                        if st.button("我已完成支付", key=f"confirm_{i}"):
                            st.session_state.paid_list.append(f"paid_{i}")
                            st.rerun()
                else:
                    # --- 支付成功：直接在网页内显示地图和路径 ---
                    st.success("✅ 支付成功，已解锁实时路径")
                    
                    route_data = get_route_data(u_lon, u_lat, gem['lon'], gem['lat'])
                    if route_data.get('code') == 0:
                        c1, c2 = st.columns([2, 1])
                        with c1:
                            m = render_route_map(route_data)
                            st_folium(m, width=600, height=400, key=f"map_{i}")
                        with c2:
                            st.write("### 🚶 中文步骤")
                            summary = route_data['route']['trafast'][0]['summary']
                            st.write(f"全程: {summary['distance']/1000:.1f}km")
                            
                            guides = route_data['route']['trafast'][0]['guide']
                            for g in guides[:5]: # 显示前5步
                                msg = g['instructions'].replace("우회전","右转").replace("좌회전","左转").replace("직진","直行")
                                st.write(f"- {msg}")
                    else:
                        st.error("路径计算失败，请检查 API 权限")
else:
    st.info("请允许位置权限以扫描周边。")