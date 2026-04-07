import streamlit as st
from streamlit_js_eval import get_geolocation
import requests
import pandas as pd
import folium
from streamlit_folium import st_folium

# 1. 密钥
S_ID = st.secrets["SEARCH_ID"]
S_SECRET = st.secrets["SEARCH_SECRET"]
NCP_ID = st.secrets["MAP_ID"]
NCP_SECRET = st.secrets["MAP_SECRET"]

test_url = "https://naveropenapi.apigw.ntruss.com/map-reversegeocode/v2/gc"
test_headers = {"X-NCP-APIGW-API-KEY-ID": NCP_ID, "X-NCP-APIGW-API-KEY": NCP_SECRET}
test_res = requests.get(test_url, headers=test_headers, params={"coords": "127.0,37.0", "output": "json"})

if test_res.status_code == 401:
    st.error("🚨 权限诊断结果：您的 NCP Key 仍然没有权限！")
    st.write("请检查：1. 是否点击了 'Maps 服务使用申请'。 2. 是否在 Application 里勾选了权限。 3. 是否等待了 15 分钟。")
elif test_res.status_code == 200:
    st.success("✅ 权限诊断结果：NCP Key 已激活！水原店即将出现。")

# 获取行政区 (如: 水原市)
def get_current_district(lat, lon):
    url = "https://naveropenapi.apigw.ntruss.com/map-reversegeocode/v2/gc"
    headers = {"X-NCP-APIGW-API-KEY-ID": NCP_ID, "X-NCP-APIGW-API-KEY": NCP_SECRET}
    params = {"coords": f"{lon},{lat}", "output": "json", "orders": "admcode"}
    try:
        res = requests.get(url, headers=headers, params=params)
        if res.status_code != 200:
            st.error(f"⚠️ 无法获取行政区 (ErrorCode: {res.status_code})")
            st.write(res.text) # 这里会显示是否欠费或没开权限
            return None
        data = res.json()
        city = data['results'][0]['region']['area2']['name']
        return city
    except:
        return None

# 搜索
def search_nearby_food(lat, lon, district_name):
    url = "https://openapi.naver.com/v1/search/local.json"
    headers = {"X-Naver-Client-Id": S_ID, "X-Naver-Client-Secret": S_SECRET}
    
    # 逻辑加固：如果没拿到地名，绝不去搜全韩国，而是报错提醒
    if not district_name:
        st.warning("⚠️ 由于权限问题没拿到当前城市名，请手动输入城市进行搜索。")
        district_name = st.text_input("请输入您所在的城市(如: 수원시)", "수원시")
    
    query = f"{district_name} 맛집"
    params = {"query": query, "display": 15, "sort": "comment"}
    res = requests.get(url, headers=headers, params=params)
    return res.json().get('items', [])

# 路径
def get_route_data(start_lon, start_lat, goal_lon, goal_lat):
    url = "https://naveropenapi.apigw.ntruss.com/map-direction/v1/driving"
    headers = {"X-NCP-APIGW-API-KEY-ID": NCP_ID, "X-NCP-APIGW-API-KEY": NCP_SECRET}
    params = {"start": f"{start_lon},{start_lat}", "goal": f"{goal_lon},{goal_lat}", "option": "trafast"}
    res = requests.get(url, headers=headers, params=params)
    return res.json()

# ==========================================
# 主界面
# ==========================================
st.title("🇰🇷 2026 韩国地道美食雷达")

if 'paid_list' not in st.session_state: st.session_state.paid_list = []

location = get_geolocation()
debug_mode = st.checkbox("调试模式 (强制定位到水原站)")

if location or debug_mode:
    u_lat, u_lon = (location['coords']['latitude'], location['coords']['longitude']) if not debug_mode else (37.266, 127.000)
    
    # 权限检查与地名获取
    district = get_current_district(u_lat, u_lon)
    
    if district:
        st.success(f"📍 您当前位于：{district}")
    
    items = search_nearby_food(u_lat, u_lon, district)
    processed = []
    for item in items:
        try:
            processed.append({
                "name": item['title'].replace("<b>","").replace("</b>",""),
                "lat": float(item['mapy']) / 10000000,
                "lon": float(item['mapx']) / 10000000,
                "addr": item['address']
            })
        except: continue

    if processed:
        # 主地图
        m = folium.Map(location=[u_lat, u_lon], zoom_start=14)
        folium.Marker([u_lat, u_lon], icon=folium.Icon(color='blue')).add_to(m)
        for p in processed:
            folium.Marker([p['lat'], p['lon']], icon=folium.Icon(color='red')).add_to(m)
        st_folium(m, width="100%", height=400, key="main")

        # 列表
        for i, p in enumerate(processed):
            with st.expander(f"💎 {p['name']}"):
                if f"paid_{i}" not in st.session_state.paid_list:
                    if st.button(f"解锁导航", key=f"p_{i}"):
                        st.session_state.paid_list.append(f"paid_{i}")
                        st.rerun()
                else:
                    # 导航
                    res = get_route_data(u_lon, u_lat, p['lon'], p['lat'])
                    if res.get('code') == 0:
                        path = res['route']['trafast'][0]['path']
                        points = [[pt[1], pt[0]] for pt in path]
                        rm = folium.Map(location=points[0], zoom_start=15)
                        folium.PolyLine(points, color="red").add_to(rm)
                        st_folium(rm, width=600, height=300, key=f"m_{i}")
                    else:
                        st.error(f"导航失败: {res.get('message')}")