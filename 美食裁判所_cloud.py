import json
import random
import hashlib
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# =====================================================
# Google Sheets 連線
# =====================================================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

@st.cache_resource
def get_sheets():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(st.secrets["sheets"]["spreadsheet_id"])
    return {
        "users": spreadsheet.worksheet("users"),
        "restaurants": spreadsheet.worksheet("restaurants"),
        "verdict_history": spreadsheet.worksheet("verdict_history"),
    }

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# =====================================================
# 資料存取工具
# =====================================================

def get_all_records(sheet_name):
    sheets = get_sheets()
    return sheets[sheet_name].get_all_records()

def append_row(sheet_name, row):
    sheets = get_sheets()
    sheets[sheet_name].append_row(row)

def update_cell(sheet_name, row_index, col_index, value):
    sheets = get_sheets()
    sheets[sheet_name].update_cell(row_index, col_index, value)

def delete_row(sheet_name, row_index):
    sheets = get_sheets()
    sheets[sheet_name].delete_rows(row_index)

def find_row_index(sheet_name, col, value):
    sheets = get_sheets()
    records = sheets[sheet_name].get_all_values()
    for i, row in enumerate(records[1:], start=2):  # 跳過標題列
        if row[col] == value:
            return i
    return None

# =====================================================
# 使用者管理
# =====================================================

def get_user(username):
    records = get_all_records("users")
    for r in records:
        if r["username"] == username:
            return r
    return None

def create_user(username, password):
    append_row("users", [username, hash_password(password), 10, "True"])

def update_user_points(username, points):
    records = get_all_records("users")
    for i, r in enumerate(records, start=2):
        if r["username"] == username:
            update_cell("users", i, 3, points)
            return

def mark_first_use_done(username):
    records = get_all_records("users")
    for i, r in enumerate(records, start=2):
        if r["username"] == username:
            update_cell("users", i, 4, "False")
            return

# =====================================================
# 餐廳管理
# =====================================================

PRICE_LEVELS = ['200元以內', '200~500元', '500元以上']
DISTANCES = ['較近', '適中', '較遠']
TIME_SLOTS = ['早餐', '午餐', '下午茶', '晚餐', '宵夜']

def get_restaurants(username):
    records = get_all_records("restaurants")
    result = []
    for r in records:
        if r["username"] == username:
            result.append({
                "restaurant_name": r["restaurant_name"],
                "restaurant_category": r["restaurant_category"],
                "restaurant_price_level": int(r["restaurant_price_level"]),
                "restaurant_distance": int(r["restaurant_distance"]),
                "restaurant_time": json.loads(r["restaurant_time"]),
            })
    return result

def add_restaurant(username, name, category, price_level, distance, time_slots):
    append_row("restaurants", [
        username, name, category, price_level, distance, json.dumps(time_slots)
    ])

def delete_restaurant(username, name):
    records = get_all_records("restaurants")
    for i, r in enumerate(records, start=2):
        if r["username"] == username and r["restaurant_name"] == name:
            delete_row("restaurants", i)
            return

def modify_restaurant(username, old_name, field, new_value):
    sheets = get_sheets()
    records = get_all_records("restaurants")
    headers = ["username", "restaurant_name", "restaurant_category",
               "restaurant_price_level", "restaurant_distance", "restaurant_time"]
    col_index = headers.index(field) + 1
    for i, r in enumerate(records, start=2):
        if r["username"] == username and r["restaurant_name"] == old_name:
            if field == "restaurant_time":
                update_cell("restaurants", i, col_index, json.dumps(new_value))
            else:
                update_cell("restaurants", i, col_index, new_value)
            return

def to_display_list(restaurant_list):
    result = []
    for r in restaurant_list:
        result.append({
            "餐廳名稱": r["restaurant_name"],
            "料理種類": r["restaurant_category"],
            "價位等級": PRICE_LEVELS[r["restaurant_price_level"] - 1],
            "距離": DISTANCES[r["restaurant_distance"] - 1],
            "營業時段": "、".join([TIME_SLOTS[t - 1] for t in r["restaurant_time"]]),
        })
    return result

# =====================================================
# 歷史紀錄管理
# =====================================================

def get_verdict_history(username):
    one_month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    records = get_all_records("verdict_history")
    result = []
    to_delete = []
    for i, r in enumerate(records, start=2):
        if r["username"] == username:
            if r["date"] < one_month_ago:
                to_delete.append(i)
            else:
                result.append({
                    "date": r["date"],
                    "restaurant_name": r["restaurant_name"],
                    "restaurant_category": r["restaurant_category"],
                    "restaurant_price_level": int(r["restaurant_price_level"]),
                    "restaurant_distance": int(r.get("restaurant_distance", 1)),
                    "restaurant_time": json.loads(r.get("restaurant_time", "[]")),
                })
    # 刪除過期資料（從後往前刪避免索引錯位）
    for i in reversed(to_delete):
        delete_row("verdict_history", i)
    return sorted(result, key=lambda h: h["date"])

def add_verdict_history(username, restaurant):
    append_row("verdict_history", [
        username,
        datetime.now().strftime("%Y-%m-%d"),
        restaurant["restaurant_name"],
        restaurant["restaurant_category"],
        restaurant["restaurant_price_level"],
        restaurant.get("restaurant_distance", 1),
        json.dumps(restaurant.get("restaurant_time", [])),
    ])

def history_to_display(history):
    result = []
    for h in history:
        result.append({
            "日期": h["date"],
            "餐廳名稱": h["restaurant_name"],
            "料理種類": h["restaurant_category"],
            "價位等級": PRICE_LEVELS[h["restaurant_price_level"] - 1],
            "距離": DISTANCES[h["restaurant_distance"] - 1],
            "用餐時段": "、".join([TIME_SLOTS[t - 1] for t in h["restaurant_time"]]) or "未記錄",
        })
    return result

# =====================================================
# 上訴邏輯
# =====================================================

APPEAL_OPTIONS_2ND = {
    1: "距離太遠",
    2: "價位太高",
    3: "不想吃這種料理",
    4: "最近不想吃這家",
    5: "用餐時間不符",
}

APPEAL_OPTIONS_3RD = {
    1: {
        1: ("步行超過15分鐘", {"restaurant_distance": 3}),
        2: ("需要騎車或開車", {"restaurant_distance": 3}),
        3: ("今天天氣不適合出遠門", {"restaurant_distance": 3}),
        4: ("同行者不方便遠行", {"restaurant_distance": 3}),
    },
    2: {
        1: ("單次消費超過500元", {"restaurant_price_level": 3}),
        2: ("本週已有高消費", {"restaurant_price_level": 3}),
        3: ("今天想吃平價的", {"restaurant_price_level": 3}),
        4: ("最近有三次都是中高價位", {"restaurant_price_level": [2, 3]}),
    },
    3: {
        1: ("這週已吃過同種料理", "category_repeat"),
        2: ("身體狀況不適合吃這類料理", "category_exclude"),
        3: ("今天不想吃這種口味", "category_exclude"),
        4: ("同行者不吃這類料理", "category_exclude"),
    },
    4: {
        1: ("一週內已去過", "restaurant_repeat"),
        2: ("上次體驗不佳", "restaurant_exclude"),
        3: ("該餐廳近期有漲價情形", "restaurant_exclude"),
        4: ("同行者也去過", "restaurant_repeat"),
    },
    5: {
        1: ("店家此時段較貴", {"restaurant_price_level": 3}),
        2: ("此時段人潮擁擠", "restaurant_exclude"),
        3: ("此時段不提供想吃的餐點", "category_exclude"),
        4: ("同行者時間有限", {"restaurant_distance": 3}),
    },
}

def get_current_time_slot():
    hour = datetime.now().hour
    if 6 <= hour < 10:
        return 1
    elif 10 <= hour < 14:
        return 2
    elif 14 <= hour < 17:
        return 3
    elif 17 <= hour < 21:
        return 4
    else:
        return 5

def first_trial(restaurant, history):
    reasons = []
    recent3 = history[-3:] if len(history) >= 3 else history

    if any(h["restaurant_name"] == restaurant["restaurant_name"] for h in history):
        reasons.append("一個月內曾判決此餐廳")

    high_price_count = sum(1 for h in recent3 if h["restaurant_price_level"] == 3)
    if high_price_count >= 2:
        reasons.append("最近3次判決中有2次以上為高價位")

    category_count = sum(1 for h in recent3 if h["restaurant_category"] == restaurant["restaurant_category"])
    if category_count >= 2:
        reasons.append(f"最近3次判決中有2次以上為{restaurant['restaurant_category']}")

    return len(reasons) > 0, reasons

def detect_lie_2nd(choices, restaurant, history):
    lies = []
    for choice in choices:
        if choice == 1 and restaurant["restaurant_distance"] == 1:
            lies.append("「距離太遠」但該餐廳距離為較近")
        elif choice == 2 and restaurant["restaurant_price_level"] == 1:
            lies.append("「價位太高」但該餐廳價位為200元以內")
        elif choice == 4:
            if not any(h["restaurant_name"] == restaurant["restaurant_name"] for h in history):
                lies.append("「最近不想吃這家」但歷史紀錄中未曾去過此餐廳")
    return lies

def detect_lie_3rd(choices_with_filter, restaurant, history):
    lies = []
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    recent5 = history[-5:] if len(history) >= 5 else history

    for second_choice, third_choice, (desc, reason_filter) in choices_with_filter:
        if desc == "本週已有高消費":
            this_week = [h for h in history if h["date"] >= week_ago]
            if not any(h["restaurant_price_level"] == 3 for h in this_week):
                lies.append("「本週已有高消費」但本週歷史紀錄中無高價位消費")
        elif desc == "最近有三次都是中高價位":
            mid_high_count = sum(1 for h in recent5 if h["restaurant_price_level"] in [2, 3])
            if mid_high_count < 3:
                lies.append(f"「最近有三次都是中高價位」但最近5筆中僅有{mid_high_count}筆符合")
        elif desc == "這週已吃過同種料理":
            this_week = [h for h in history if h["date"] >= week_ago]
            if not any(h["restaurant_category"] == restaurant["restaurant_category"] for h in this_week):
                lies.append("「這週已吃過同種料理」但本週歷史紀錄中無同種料理")
        elif desc == "一週內已去過":
            this_week_names = [h["restaurant_name"] for h in history if h["date"] >= week_ago]
            if restaurant["restaurant_name"] not in this_week_names:
                lies.append("「一週內已去過」但歷史紀錄中本週未去過此餐廳")
    return lies

def calc_win_rate_2nd(choices, restaurant, history):
    base_rate = 0.15
    bonus = 0.0
    recent3 = history[-3:] if len(history) >= 3 else history

    for choice in choices:
        if choice == 1 and restaurant["restaurant_distance"] == 3:
            bonus += 0.05
        elif choice == 2 and restaurant["restaurant_price_level"] == 3:
            bonus += 0.05
        elif choice == 3:
            if any(h["restaurant_category"] == restaurant["restaurant_category"] for h in recent3):
                bonus += 0.05
        elif choice == 4:
            if any(h["restaurant_name"] == restaurant["restaurant_name"] for h in history):
                bonus += 0.05
        elif choice == 5:
            if get_current_time_slot() not in restaurant.get("restaurant_time", []):
                bonus += 0.05
    return min(base_rate + bonus, 0.30)

def calc_win_rate_3rd(choices_with_filter, restaurant, history):
    base_rate = 0.025
    bonus = 0.0
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    recent5 = history[-5:] if len(history) >= 5 else history

    for second_choice, third_choice, (desc, reason_filter) in choices_with_filter:
        if second_choice == 1:
            if restaurant["restaurant_distance"] == 3:
                bonus += 0.025
        elif second_choice == 2:
            if desc == "本週已有高消費":
                this_week = [h for h in history if h["date"] >= week_ago]
                if any(h["restaurant_price_level"] == 3 for h in this_week):
                    bonus += 0.025
            elif desc == "最近有三次都是中高價位":
                if sum(1 for h in recent5 if h["restaurant_price_level"] in [2, 3]) >= 3:
                    bonus += 0.025
            elif restaurant["restaurant_price_level"] == 3:
                bonus += 0.025
        elif second_choice == 3:
            if desc == "這週已吃過同種料理":
                this_week = [h for h in history if h["date"] >= week_ago]
                if any(h["restaurant_category"] == restaurant["restaurant_category"] for h in this_week):
                    bonus += 0.025
            else:
                bonus += 0.025
        elif second_choice == 4:
            if desc == "一週內已去過":
                this_week_names = [h["restaurant_name"] for h in history if h["date"] >= week_ago]
                if restaurant["restaurant_name"] in this_week_names:
                    bonus += 0.025
            else:
                bonus += 0.025
        elif second_choice == 5:
            bonus += 0.025
    return min(base_rate + bonus, 0.10)

def re_recommend(restaurant_list, original, reason_filters, history):
    current_slot = get_current_time_slot()
    pool = [r for r in restaurant_list if r["restaurant_name"] != original["restaurant_name"]]
    pool = [r for r in pool if current_slot in r.get("restaurant_time", [])]

    if reason_filters:
        for reason_filter in reason_filters:
            if isinstance(reason_filter, dict):
                for key, val in reason_filter.items():
                    if isinstance(val, list):
                        pool = [r for r in pool if r.get(key) not in val]
                    else:
                        pool = [r for r in pool if r.get(key) != val]
            elif reason_filter in ("category_repeat", "category_exclude"):
                pool = [r for r in pool if r["restaurant_category"] != original["restaurant_category"]]
            elif reason_filter in ("restaurant_repeat", "restaurant_exclude"):
                recent_names = [h["restaurant_name"] for h in history]
                pool = [r for r in pool if r["restaurant_name"] not in recent_names]

    if not pool:
        return None
    return random.choice(pool)

# =====================================================
# Streamlit 介面
# =====================================================

st.set_page_config(page_title="美食裁判所", page_icon="⚖️", layout="wide")

# ==================== Session State 初始化 ====================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = None
if "points" not in st.session_state:
    st.session_state.points = 0
if "recommend_result" not in st.session_state:
    st.session_state.recommend_result = None
if "appeal_stage" not in st.session_state:
    st.session_state.appeal_stage = None
if "second_choices" not in st.session_state:
    st.session_state.second_choices = []
if "verdict_added" not in st.session_state:
    st.session_state.verdict_added = False

# =====================================================
# 登入 / 註冊頁面
# =====================================================

if not st.session_state.logged_in:
    st.title("⚖️ 美食裁判所")
    st.markdown("---")

    tab1, tab2 = st.tabs(["登入", "註冊"])

    with tab1:
        with st.form("login_form"):
            username = st.text_input("使用者名稱")
            password = st.text_input("密碼", type="password")
            submitted = st.form_submit_button("登入")

        if submitted:
            if not username or not password:
                st.error("請輸入使用者名稱和密碼")
            else:
                user = get_user(username)
                if user is None:
                    st.error("使用者不存在，請先註冊")
                elif user["password"] != hash_password(password):
                    st.error("密碼錯誤")
                else:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.points = int(user["points"])
                    if user["is_first_use"] == "True":
                        st.success("【首次使用】贈送10點飽食點數！")
                        mark_first_use_done(username)
                    st.rerun()

    with tab2:
        with st.form("register_form"):
            new_username = st.text_input("使用者名稱")
            new_password = st.text_input("密碼", type="password")
            confirm_password = st.text_input("確認密碼", type="password")
            submitted = st.form_submit_button("註冊")

        if submitted:
            if not new_username or not new_password:
                st.error("請輸入使用者名稱和密碼")
            elif new_password != confirm_password:
                st.error("兩次密碼不一致")
            elif get_user(new_username):
                st.error("此使用者名稱已被使用")
            else:
                create_user(new_username, new_password)
                st.success("註冊成功！請登入")

# =====================================================
# 主程式（登入後）
# =====================================================

else:
    username = st.session_state.username

    # ==================== 側邊欄 ====================
    st.sidebar.title("⚖️ 美食裁判所")
    st.sidebar.markdown(f"👤 **{username}**")
    st.sidebar.markdown("---")

    st.sidebar.markdown("**📋 餐廳管理**")
    page = st.sidebar.radio(
        label="功能選單",
        options=["新增餐廳", "修改餐廳", "刪除餐廳", "查詢餐廳",
                 "🎲 今日推薦", "📝 手動飲食紀錄", "📊 歷史紀錄與飽食點數"],
        label_visibility="collapsed"
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**🍽️ 飽食點數：{st.session_state.points} 點**")

    if st.sidebar.button("登出"):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.points = 0
        st.session_state.recommend_result = None
        st.session_state.appeal_stage = None
        st.rerun()

    # ==================== 新增餐廳 ====================
    if page == "新增餐廳":
        st.title("📋 新增餐廳")
        st.markdown("---")

        with st.form("add_form"):
            name = st.text_input("餐廳名稱")
            category = st.text_input("料理種類（如：日式、美式、台式）")
            price_level = st.selectbox("價位等級", options=[1, 2, 3],
                                       format_func=lambda x: PRICE_LEVELS[x - 1])
            distance = st.selectbox("距離", options=[1, 2, 3],
                                    format_func=lambda x: DISTANCES[x - 1])
            time_slots = st.multiselect("營業時段（可複選）", options=[1, 2, 3, 4, 5],
                                        format_func=lambda x: TIME_SLOTS[x - 1])
            submitted = st.form_submit_button("新增餐廳")

        if submitted:
            if not name:
                st.error("請輸入餐廳名稱")
            elif not category:
                st.error("請輸入料理種類")
            elif not time_slots:
                st.error("請選擇至少一個營業時段")
            else:
                restaurants = get_restaurants(username)
                if any(r["restaurant_name"] == name for r in restaurants):
                    st.error(f"「{name}」已經在資料庫中")
                else:
                    add_restaurant(username, name, category, price_level, distance, sorted(time_slots))
                    st.success(f"「{name}」已成功送入判決內容")

    # ==================== 修改餐廳 ====================
    elif page == "修改餐廳":
        st.title("✏️ 修改餐廳")
        st.markdown("---")

        restaurants = get_restaurants(username)
        if not restaurants:
            st.warning("目前尚無餐廳資料")
        else:
            name_options = [r["restaurant_name"] for r in restaurants]
            selected_name = st.selectbox("請選擇欲修改的餐廳", options=name_options)
            target = next((r for r in restaurants if r["restaurant_name"] == selected_name), None)

            if target:
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"料理種類：{target['restaurant_category']}")
                    st.write(f"價位等級：{PRICE_LEVELS[target['restaurant_price_level'] - 1]}")
                with col2:
                    st.write(f"距離：{DISTANCES[target['restaurant_distance'] - 1]}")
                    st.write(f"營業時段：{'、'.join([TIME_SLOTS[t-1] for t in target.get('restaurant_time', [])])  or '未設定'}")

                st.markdown("---")
                field = st.selectbox("請選擇欲修改的項目",
                                     options=["餐廳名稱", "料理種類", "價位等級", "距離", "營業時段"])

                with st.form("modify_form"):
                    if field == "餐廳名稱":
                        new_value = st.text_input("新的餐廳名稱")
                        field_key = "restaurant_name"
                    elif field == "料理種類":
                        new_value = st.text_input("新的料理種類")
                        field_key = "restaurant_category"
                    elif field == "價位等級":
                        new_value = st.selectbox("新的價位等級", options=[1, 2, 3],
                                                 format_func=lambda x: PRICE_LEVELS[x - 1])
                        field_key = "restaurant_price_level"
                    elif field == "距離":
                        new_value = st.selectbox("新的距離", options=[1, 2, 3],
                                                 format_func=lambda x: DISTANCES[x - 1])
                        field_key = "restaurant_distance"
                    else:
                        new_value = st.multiselect("新的營業時段（可複選）", options=[1, 2, 3, 4, 5],
                                                   format_func=lambda x: TIME_SLOTS[x - 1])
                        field_key = "restaurant_time"

                    submitted = st.form_submit_button("確認修改")

                if submitted:
                    if field in ["餐廳名稱", "料理種類"] and not new_value:
                        st.error("請輸入新的值")
                    elif field == "營業時段" and not new_value:
                        st.error("請選擇至少一個營業時段")
                    else:
                        final_value = sorted(new_value) if field == "營業時段" else new_value
                        modify_restaurant(username, selected_name, field_key, final_value)
                        st.success("資料已成功更新")
                        st.rerun()

    # ==================== 刪除餐廳 ====================
    elif page == "刪除餐廳":
        st.title("🗑️ 刪除餐廳")
        st.markdown("---")

        restaurants = get_restaurants(username)
        if not restaurants:
            st.warning("目前尚無餐廳資料")
        else:
            name_options = [r["restaurant_name"] for r in restaurants]
            selected_name = st.selectbox("請選擇欲刪除的餐廳", options=name_options)
            target = next((r for r in restaurants if r["restaurant_name"] == selected_name), None)

            if target:
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"餐廳名稱：{target['restaurant_name']}")
                    st.write(f"料理種類：{target['restaurant_category']}")
                with col2:
                    st.write(f"價位等級：{PRICE_LEVELS[target['restaurant_price_level'] - 1]}")
                    st.write(f"距離：{DISTANCES[target['restaurant_distance'] - 1]}")

                st.warning(f"確定要刪除「{selected_name}」嗎？此操作無法復原！")
                if st.button("確認刪除", type="primary"):
                    delete_restaurant(username, selected_name)
                    st.success(f"「{selected_name}」已成功撤銷判決")
                    st.rerun()

    # ==================== 查詢餐廳 ====================
    elif page == "查詢餐廳":
        st.title("🔍 查詢餐廳")
        st.markdown("---")

        restaurants = get_restaurants(username)
        if not restaurants:
            st.warning("目前尚無餐廳資料")
        else:
            mode = st.selectbox("查詢方式", options=["全部", "名稱", "種類", "價位", "距離", "時段"])
            value = None

            if mode == "名稱":
                value = st.text_input("請輸入餐廳名稱")
            elif mode == "種類":
                value = st.text_input("請輸入料理種類")
            elif mode == "價位":
                value = st.selectbox("請選擇價位等級", options=[1, 2, 3],
                                     format_func=lambda x: PRICE_LEVELS[x - 1])
            elif mode == "距離":
                value = st.selectbox("請選擇距離", options=[1, 2, 3],
                                     format_func=lambda x: DISTANCES[x - 1])
            elif mode == "時段":
                value = st.multiselect("請選擇時段（可複選）", options=[1, 2, 3, 4, 5],
                                       format_func=lambda x: TIME_SLOTS[x - 1])

            if st.button("查詢"):
                if mode == "全部":
                    result = restaurants
                elif mode == "名稱":
                    result = [r for r in restaurants if r["restaurant_name"] == value]
                elif mode == "種類":
                    result = [r for r in restaurants if r["restaurant_category"] == value]
                elif mode == "價位":
                    result = [r for r in restaurants if r["restaurant_price_level"] == value]
                elif mode == "距離":
                    result = [r for r in restaurants if r["restaurant_distance"] == value]
                elif mode == "時段":
                    result = [r for r in restaurants if any(t in r["restaurant_time"] for t in value)]
                else:
                    result = []

                if not result:
                    st.warning("查無符合條件的餐廳")
                else:
                    st.success(f"共找到 {len(result)} 間餐廳")
                    st.dataframe(to_display_list(result), use_container_width=True)

    # ==================== 今日推薦 ====================
    elif page == "🎲 今日推薦":
        st.title("🎲 今日推薦")
        st.markdown("---")

        restaurants = get_restaurants(username)
        if not restaurants:
            st.warning("目前尚無餐廳資料")
        else:
            if st.button("🎰 開始判決", type="primary"):
                current_slot = get_current_time_slot()
                pool = [r for r in restaurants if current_slot in r["restaurant_time"]]
                if not pool:
                    st.warning(f"目前時段（{TIME_SLOTS[current_slot - 1]}）無可用餐廳")
                else:
                    st.session_state.recommend_result = random.choice(pool)
                    st.session_state.appeal_stage = "ask_appeal"
                    st.session_state.verdict_added = False
                    st.session_state.second_choices = []

            if st.session_state.recommend_result:
                r = st.session_state.recommend_result
                history = get_verdict_history(username)

                st.markdown("### ⚖️ 判決結果")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("餐廳名稱", r["restaurant_name"])
                    st.metric("料理種類", r["restaurant_category"])
                with col2:
                    st.metric("價位等級", PRICE_LEVELS[r["restaurant_price_level"] - 1])
                    st.metric("距離", DISTANCES[r["restaurant_distance"] - 1])
                st.markdown("---")

                # 詢問是否上訴
                if st.session_state.appeal_stage == "ask_appeal":
                    st.info(f"💰 目前飽食點數：{st.session_state.points} 點")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("⚖️ 提出上訴"):
                            st.session_state.appeal_stage = "first"
                            st.rerun()
                    with col2:
                        if st.button("✅ 接受判決"):
                            st.session_state.appeal_stage = "done"
                            st.rerun()

                # 一審
                elif st.session_state.appeal_stage == "first":
                    st.markdown("### 【一審】事實認定與證據蒐集")
                    win, reasons = first_trial(r, history)
                    if win:
                        st.success("✅ 發現以下事實，一審勝訴！")
                        for reason in reasons:
                            st.write(f"• {reason}")
                        new = re_recommend(restaurants, r, None, history)
                        if new:
                            st.session_state.recommend_result = new
                            add_verdict_history(username, new)
                            st.session_state.points += 1
                            update_user_points(username, st.session_state.points)
                            st.session_state.verdict_added = True
                        st.session_state.appeal_stage = "done"
                        st.rerun()
                    else:
                        st.error("❌ 未發現足夠事實依據，一審敗訴")
                        if st.session_state.points < 1:
                            st.warning("飽食點數不足，無法繼續上訴")
                            st.session_state.appeal_stage = "done"
                            st.rerun()
                        else:
                            st.info(f"💰 目前飽食點數：{st.session_state.points} 點（上訴將消耗1點）")
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button("⚖️ 繼續上訴至二審"):
                                    st.session_state.appeal_stage = "second"
                                    st.rerun()
                            with col2:
                                if st.button("🏳️ 放棄上訴"):
                                    st.session_state.appeal_stage = "done"
                                    st.rerun()

                # 二審
                elif st.session_state.appeal_stage == "second":
                    st.markdown("### 【二審】理由選擇")
                    choices = st.multiselect(
                        "請選擇上訴理由（最多3項）",
                        options=list(APPEAL_OPTIONS_2ND.keys()),
                        format_func=lambda x: APPEAL_OPTIONS_2ND[x],
                        max_selections=3
                    )
                    if st.button("提交二審"):
                        if not choices:
                            st.error("請至少選擇一項理由")
                        else:
                            st.session_state.points -= 1
                            update_user_points(username, st.session_state.points)

                            lies = detect_lie_2nd(choices, r, history)
                            if lies:
                                st.error("⚠️ 系統偵測到以下矛盾：")
                                for lie in lies:
                                    st.write(f"• {lie}")
                                st.error("【二審結果】陳述不實，判決敗訴，且不得上訴三審")
                                st.session_state.appeal_stage = "done"
                            else:
                                win_rate = calc_win_rate_2nd(choices, r, history)
                                result_2nd = random.random() < win_rate
                                st.info(f"勝訴機率：{int(win_rate * 100)}%")
                                if result_2nd:
                                    st.success("【二審結果】上訴成立，判決勝訴！")
                                    new = re_recommend(restaurants, r, None, history)
                                    if new:
                                        st.session_state.recommend_result = new
                                        add_verdict_history(username, new)
                                        st.session_state.points += 1
                                        update_user_points(username, st.session_state.points)
                                        st.session_state.verdict_added = True
                                    st.session_state.appeal_stage = "done"
                                else:
                                    st.error("【二審結果】上訴不成立，判決敗訴")
                                    st.session_state.second_choices = choices
                                    if st.session_state.points < 1:
                                        st.warning("飽食點數不足，無法繼續上訴")
                                        st.session_state.appeal_stage = "done"
                                    else:
                                        st.session_state.appeal_stage = "ask_third"
                            st.rerun()

                # 詢問是否繼續至三審
                elif st.session_state.appeal_stage == "ask_third":
                    st.info(f"💰 目前飽食點數：{st.session_state.points} 點（上訴將消耗1點）")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("⚖️ 繼續上訴至三審"):
                            st.session_state.appeal_stage = "third"
                            st.rerun()
                    with col2:
                        if st.button("🏳️ 放棄上訴"):
                            st.session_state.appeal_stage = "done"
                            st.rerun()

                # 三審
                elif st.session_state.appeal_stage == "third":
                    st.markdown("### 【三審】延伸理由選擇")
                    choices_with_filter = []
                    for second_choice in st.session_state.second_choices:
                        options = APPEAL_OPTIONS_3RD[second_choice]
                        third_choice = st.selectbox(
                            f"針對「{APPEAL_OPTIONS_2ND[second_choice]}」，請選擇細項：",
                            options=list(options.keys()),
                            format_func=lambda x, o=options: o[x][0],
                            key=f"third_{second_choice}"
                        )
                        choices_with_filter.append((second_choice, third_choice, options[third_choice]))

                    if st.button("提交三審"):
                        st.session_state.points -= 1
                        update_user_points(username, st.session_state.points)

                        lies = detect_lie_3rd(choices_with_filter, r, history)
                        if lies:
                            st.error("⚠️ 系統偵測到以下矛盾：")
                            for lie in lies:
                                st.write(f"• {lie}")
                            st.error("【三審結果】陳述不實，判決敗訴，維持原判決")
                        else:
                            win_rate = calc_win_rate_3rd(choices_with_filter, r, history)
                            result_3rd = random.random() < win_rate
                            st.info(f"勝訴機率：{int(win_rate * 100)}%")
                            if result_3rd:
                                st.success("【三審結果】上訴成立，判決勝訴！")
                                reason_filters = [f for _, _, (_, f) in choices_with_filter]
                                new = re_recommend(restaurants, r, reason_filters, history)
                                if new:
                                    st.session_state.recommend_result = new
                                    add_verdict_history(username, new)
                                    st.session_state.points += 1
                                    update_user_points(username, st.session_state.points)
                                    st.session_state.verdict_added = True
                            else:
                                st.error("【三審結果】上訴不成立，判決敗訴，維持原判決")
                        st.session_state.appeal_stage = "done"
                        st.rerun()

                # 判決完成
                elif st.session_state.appeal_stage == "done":
                    final = st.session_state.recommend_result
                    st.markdown("### 🍽️ 最終判決")
                    st.success(f"今天就吃：**{final['restaurant_name']}**")

                    if not st.session_state.verdict_added:
                        st.markdown("---")
                        st.write("請問您是否已完成用餐？")
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("✅ 是，已完成用餐"):
                                add_verdict_history(username, final)
                                st.session_state.points += 1
                                update_user_points(username, st.session_state.points)
                                st.session_state.verdict_added = True
                                st.success(f"用餐完成！獲得1點飽食點數，目前共 {st.session_state.points} 點")
                                st.rerun()
                        with col2:
                            if st.button("❌ 否，尚未用餐"):
                                add_verdict_history(username, final)
                                st.session_state.verdict_added = True
                                st.info("好的，點數將於實際用餐後再行發放")
                                st.rerun()

    # ==================== 手動飲食紀錄 ====================
    elif page == "📝 手動飲食紀錄":
        st.title("📝 手動飲食紀錄")
        st.markdown("---")

        one_month_ago = datetime.now() - timedelta(days=30)
        st.info(f"請輸入一個月內的飲食紀錄（{one_month_ago.strftime('%Y-%m-%d')} 之後）")

        with st.form("record_form"):
            name = st.text_input("餐廳名稱")
            date = st.date_input("用餐日期", value=datetime.now(),
                                 min_value=one_month_ago, max_value=datetime.now())
            category = st.text_input("料理種類（如：日式、美式、台式）")
            price_level = st.selectbox("價位等級", options=[1, 2, 3],
                                       format_func=lambda x: PRICE_LEVELS[x - 1])
            distance = st.selectbox("距離", options=[1, 2, 3],
                                    format_func=lambda x: DISTANCES[x - 1])
            time_slots = st.multiselect("用餐時段（可複選）", options=[1, 2, 3, 4, 5],
                                        format_func=lambda x: TIME_SLOTS[x - 1])

            restaurants = get_restaurants(username)
            existing = any(r["restaurant_name"] == name for r in restaurants) if name else True
            add_to_db = False
            if not existing:
                add_to_db = st.checkbox("同時新增至餐廳資料庫")

            submitted = st.form_submit_button("新增紀錄")

        if submitted:
            if not name:
                st.error("請輸入餐廳名稱")
            elif not category:
                st.error("請輸入料理種類")
            elif not time_slots:
                st.error("請選擇至少一個用餐時段")
            else:
                record = {
                    "restaurant_name": name,
                    "restaurant_category": category,
                    "restaurant_price_level": price_level,
                    "restaurant_distance": distance,
                    "restaurant_time": sorted(time_slots),
                    "date": date.strftime("%Y-%m-%d"),
                }
                add_verdict_history(username, record)
                st.success(f"「{name}」已成功記錄至飲食紀錄")
                if add_to_db:
                    add_restaurant(username, name, category, price_level, distance, sorted(time_slots))
                    st.success(f"「{name}」已同時新增至餐廳資料庫")

    # ==================== 歷史紀錄與飽食點數 ====================
    elif page == "📊 歷史紀錄與飽食點數":
        st.title("📊 歷史紀錄與飽食點數查詢")
        st.markdown("---")

        st.markdown("### 🍽️ 目前飽食點數")
        st.markdown(f"## {st.session_state.points} 點")
        st.markdown("---")
        st.markdown("### 📜 歷史紀錄查詢")

        mode = st.selectbox("查詢方式", options=["全部", "種類", "價位"])
        value = None

        if mode == "種類":
            value = st.text_input("請輸入料理種類")
        elif mode == "價位":
            value = st.selectbox("請選擇價位等級", options=[1, 2, 3],
                                 format_func=lambda x: PRICE_LEVELS[x - 1])

        if st.button("查詢"):
            history = get_verdict_history(username)
            if mode == "種類":
                history = [h for h in history if h["restaurant_category"] == value]
            elif mode == "價位":
                history = [h for h in history if h["restaurant_price_level"] == value]

            if not history:
                st.warning("查無符合條件的紀錄")
            else:
                st.success(f"共找到 {len(history)} 筆紀錄")
                st.dataframe(history_to_display(history), use_container_width=True)
