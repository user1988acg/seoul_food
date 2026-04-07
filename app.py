import streamlit as st
from streamlit_js_eval import get_geolocation
import requests
import folium
from streamlit_folium import st_folium

# ==========================================
# 密钥加载
# ==========================================
S_ID = st.secrets["SEARCH_ID"]
S_SECRET = st.secrets["SEARCH_SECRET"]
MAP_ID = st.secrets["MAP_ID"]         
MAP_SECRET = st.secrets["MAP_SECRET"] 

# ==========================================
# 核心函数
# ==========================================

def search_food_suwon():
    """搜索水原市的美食店"""
    url = "https://openapi.naver.com/v1/search/local.json"
    headers = {
        "X-Naver-Client-Id": S_ID,
        "X-Naver-Client-Secret": S_SECRET
    }
    params = {"query": "수원시 맛집", "display": 15, "sort": "comment"}
    res = requests.get(url, headers=headers, params=params)
    return res.json().get('items', [])


def get_ncp_route(s_lon, s_lat, g_lon, g_lat):
    """
    使用 NCP Directions5 API 进行路径规划
    文档：https://api.ncloud-docs.com/docs/ai-naver-mapsdirections-driving
    """
    url = "https://naveropenapi.apigw.ntruss.com/map-direction/v1/driving"
    headers = {
        "X-NCP-APIGW-API-KEY-ID": MAP_ID,
        "X-NCP-APIGW-API-KEY": MAP_SECRET
    }
    params = {
        "start": f"{s_lon},{s_lat}",
        "goal": f"{g_lon},{g_lat}",
        "option": "trafast"  # 실시간 빠른 길
    }
    try:
        res = requests.get(url, headers=headers, params=params, timeout=10)
        return res
    except requests.exceptions.RequestException as e:
        return None


# ==========================================
# 主界面
# ==========================================
st.set_page_config(page_title="水原美食雷达", layout="wide")
st.title("🇰🇷 2026 韩国地道美食雷达（水原版）")

if 'nav_list' not in st.session_state:
    st.session_state.nav_list = []

# ==========================================
# 定位（默认水原站）
# ==========================================
u_lat, u_lon = 37.266, 127.000
loc = get_geolocation()
if loc and 'coords' in loc:
    u_lat = loc['coords']['latitude']
    u_lon = loc['coords']['longitude']

st.info(f"📍 当前定位：{u_lat:.4f}, {u_lon:.4f}（水原市范围）")

# ==========================================
# 1. 获取并处理餐厅数据
# ==========================================
with st.spinner("正在加载美食信息，请稍候..."):
    raw_items = search_food_suwon()

processed = []
for item in raw_items:
    try:
        lon_w = float(item['mapx']) / 10000000
        lat_w = float(item['mapy']) / 10000000
        processed.append({
            "name": item['title'].replace("<b>", "").replace("</b>", ""),
            "lat": lat_w,
            "lon": lon_w,
            "addr": item.get('address', '暂无地址信息'),
            "category": item.get('category', ''),
            "telephone": item.get('telephone', ''),
            "link": item.get('link', '')
        })
    except Exception:
        continue

# ==========================================
# 2. 主地图
# ==========================================
if processed:
    st.subheader("🗺️ 水原地道餐厅分布图")

    m = folium.Map(location=[u_lat, u_lon], zoom_start=13)
    folium.Marker(
        [u_lat, u_lon],
        popup="📍 我的位置",
        tooltip="我的位置",
        icon=folium.Icon(color='blue', icon='user', prefix='fa')
    ).add_to(m)

    for p in processed:
        folium.Marker(
            [p['lat'], p['lon']],
            popup=folium.Popup(f"<b>{p['name']}</b><br>{p['addr']}", max_width=200),
            tooltip=p['name'],
            icon=folium.Icon(color='red', icon='cutlery', prefix='fa')
        ).add_to(m)

    st_folium(m, width=1100, height=500, key="main_map")

    # ==========================================
    # 3. 餐厅详情列表 + NCP Directions 导航
    # ==========================================
    st.markdown("---")
    st.subheader("🔎 发现的宝藏餐厅")

    for i, p in enumerate(processed):
        with st.expander(f"🍽️ {p['name']}"):
            col1, col2 = st.columns(2)

            with col1:
                st.write(f"🏠 **地址：** {p['addr']}")
                if p['category']:
                    st.write(f"🏷️ **类别：** {p['category']}")
                if p['telephone']:
                    st.write(f"📞 **电话：** {p['telephone']}")
                if p['link']:
                    st.markdown(f"🔗 [Naver详情页]({p['link']})")

            with col2:
                nav_key = f"nav_{i}"

                if nav_key not in st.session_state.nav_list:
                    if st.button("🗺️ 点击导航（NCP路线规划）", key=f"btn_{i}"):
                        st.session_state.nav_list.append(nav_key)
                        st.rerun()
                else:
                    with st.spinner("正在计算路线，请稍候..."):
                        res = get_ncp_route(u_lon, u_lat, p['lon'], p['lat'])

                    if res is None:
                        st.error("❌ 网络请求失败，请检查网络连接后重试。")

                    elif res.status_code == 200:
                        data = res.json()
                        code = data.get('code', -1)

                        if code == 0 and data.get('route'):
                            # NCP 返回结构：route > trafast > [0] > summary / path
                            route_data = data['route'].get('trafast', [])
                            if not route_data:
                                st.warning("⚠️ 未找到可用路线。")
                            else:
                                r = route_data[0]
                                summary = r['summary']
                                distance_km = summary['distance'] / 1000
                                duration_min = summary['duration'] / 1000 / 60  # ms → min
                                path_pts = [[pt[1], pt[0]] for pt in r['path']]

                                st.success(
                                    f"✅ 路线计算完成 ｜ "
                                    f"距离：{distance_km:.1f} km ｜ "
                                    f"预计行驶时间：{duration_min:.0f} 分钟"
                                )

                                rm = folium.Map(location=path_pts[0], zoom_start=14)
                                folium.Marker(
                                    path_pts[0],
                                    popup="📍 出发点",
                                    tooltip="出发点",
                                    icon=folium.Icon(color='blue', icon='play', prefix='fa')
                                ).add_to(rm)
                                folium.Marker(
                                    path_pts[-1],
                                    popup=f"🍽️ {p['name']}",
                                    tooltip=p['name'],
                                    icon=folium.Icon(color='red', icon='flag', prefix='fa')
                                ).add_to(rm)
                                folium.PolyLine(
                                    path_pts,
                                    color="#0066FF",
                                    weight=5,
                                    opacity=0.8
                                ).add_to(rm)

                                st_folium(rm, width=500, height=350, key=f"route_{i}")

                        else:
                            # NCP 错误码说明
                            err_map = {
                                1: "출발지/도착지 오류 (좌표 확인 필요)",
                                2: "경유지 오류",
                                3: "출발지와 도착지 동일",
                                4: "경로 탐색 불가",
                            }
                            msg = err_map.get(code, f"알 수 없는 오류 (code={code})")
                            st.warning(f"⚠️ 路线规划失败：{msg}")

                    else:
                        st.error(f"❌ NCP API 异常（HTTP {res.status_code}）")
                        st.write(res.text)

else:
    st.error("❌ 未能获取美食数据，请检查 API 配置。")