import json
import os
import random
import streamlit as st
from datetime import datetime, timedelta

# =====================================================
# 原有的四個 Class（邏輯不變）
# =====================================================

class RestaurantManager:
    PRICE_LEVELS = ['200元以內', '200~500元', '500元以上']
    DISTANCES = ['較近', '適中', '較遠']
    TIME_SLOTS = ['早餐', '午餐', '下午茶', '晚餐', '宵夜']

    def __init__(self):
        self.restaurant_list = self._load()

    def _load(self):
        if os.path.exists("restaurants.json"):
            with open("restaurants.json", "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def _save(self):
        with open("restaurants.json", "w", encoding="utf-8") as f:
            json.dump(self.restaurant_list, f, ensure_ascii=False, indent=4)

    def _find(self, name):
        for r in self.restaurant_list:
            if r["restaurant_name"] == name:
                return r
        return None

    def _get_current_time_slot(self):
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

    def add(self, name, category, price_level, distance, time_slots):
        if self._find(name):
            return False, f"「{name}」已經在資料庫中，若需修改請至修改系統"
        self.restaurant_list.append({
            "restaurant_name": name,
            "restaurant_category": category,
            "restaurant_price_level": price_level,
            "restaurant_distance": distance,
            "restaurant_time": time_slots,
        })
        self._save()
        return True, f"「{name}」已成功送入判決內容"

    def modify(self, name, field, new_value):
        target = self._find(name)
        if target is None:
            return False, f"找不到「{name}」，請確認名稱是否正確"
        if field == "restaurant_name":
            if self._find(new_value):
                return False, f"「{new_value}」已存在於資料庫中，無法使用此名稱"
            target[field] = new_value
        else:
            target[field] = new_value
        self._save()
        return True, "資料已成功更新"

    def delete(self, name):
        target = self._find(name)
        if target is None:
            return False, f"找不到「{name}」，請確認名稱是否正確"
        self.restaurant_list.remove(target)
        self._save()
        return True, f"「{name}」已成功撤銷判決"

    def query(self, mode, value=None):
        if mode == "全部":
            return self.restaurant_list
        elif mode == "名稱":
            target = self._find(value)
            return [target] if target else []
        elif mode == "種類":
            return [r for r in self.restaurant_list if r["restaurant_category"] == value]
        elif mode == "價位":
            return [r for r in self.restaurant_list if r["restaurant_price_level"] == value]
        elif mode == "距離":
            return [r for r in self.restaurant_list if r["restaurant_distance"] == value]
        elif mode == "時段":
            return [r for r in self.restaurant_list if any(t in r["restaurant_time"] for t in value)]
        return []

    def recommend(self):
        current_slot = self._get_current_time_slot()
        pool = [r for r in self.restaurant_list if current_slot in r["restaurant_time"]]
        if not pool:
            return None, self.TIME_SLOTS[current_slot - 1]
        return random.choice(pool), self.TIME_SLOTS[current_slot - 1]

    def to_display_list(self, restaurant_list):
        result = []
        for r in restaurant_list:
            result.append({
                "餐廳名稱": r["restaurant_name"],
                "料理種類": r["restaurant_category"],
                "價位等級": self.PRICE_LEVELS[r["restaurant_price_level"] - 1],
                "距離": self.DISTANCES[r["restaurant_distance"] - 1],
                "營業時段": "、".join([self.TIME_SLOTS[t - 1] for t in r["restaurant_time"]]),
            })
        return result


class AppealManager:
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

    def __init__(self):
        self.data = self._load()
        self._check_first_use()
        self._clean_old_history()

    def _load(self):
        if os.path.exists("appeal_data.json"):
            with open("appeal_data.json", "r", encoding="utf-8") as f:
                return json.load(f)
        return {
            "points": 0,
            "is_first_use": True,
            "verdict_history": [],
        }

    def _save(self):
        with open("appeal_data.json", "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=4)

    def _check_first_use(self):
        if self.data["is_first_use"]:
            self.data["points"] = 10
            self.data["is_first_use"] = False
            self._save()

    def _clean_old_history(self):
        one_month_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        before = len(self.data["verdict_history"])
        self.data["verdict_history"] = [
            h for h in self.data["verdict_history"]
            if h["date"] >= one_month_ago
        ]
        if len(self.data["verdict_history"]) < before:
            self._save()

    def add_verdict(self, restaurant, confirmed):
        self.data["verdict_history"].append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "restaurant_name": restaurant["restaurant_name"],
            "restaurant_category": restaurant["restaurant_category"],
            "restaurant_price_level": restaurant["restaurant_price_level"],
            "restaurant_distance": restaurant.get("restaurant_distance", 0),
            "restaurant_time": restaurant.get("restaurant_time", []),
        })
        if confirmed:
            self.data["points"] += 1
        self._save()

    def _get_current_time_slot(self):
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

    def first_trial(self, restaurant):
        reasons = []
        history = self.data["verdict_history"]
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

    def detect_lie_2nd(self, choices, restaurant):
        lies = []
        history = self.data["verdict_history"]
        for choice in choices:
            if choice == 1 and restaurant["restaurant_distance"] == 1:
                lies.append("「距離太遠」但該餐廳距離為較近")
            elif choice == 2 and restaurant["restaurant_price_level"] == 1:
                lies.append("「價位太高」但該餐廳價位為200元以內")
            elif choice == 4:
                if not any(h["restaurant_name"] == restaurant["restaurant_name"] for h in history):
                    lies.append("「最近不想吃這家」但歷史紀錄中未曾去過此餐廳")
        return lies

    def detect_lie_3rd(self, choices_with_filter, restaurant):
        lies = []
        history = self.data["verdict_history"]
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

    def calc_win_rate_2nd(self, choices, restaurant):
        base_rate = 0.15
        bonus = 0.0
        history = self.data["verdict_history"]
        for choice in choices:
            if choice == 1 and restaurant["restaurant_distance"] == 3:
                bonus += 0.05
            elif choice == 2 and restaurant["restaurant_price_level"] == 3:
                bonus += 0.05
            elif choice == 3:
                recent3 = history[-3:] if len(history) >= 3 else history
                if any(h["restaurant_category"] == restaurant["restaurant_category"] for h in recent3):
                    bonus += 0.05
            elif choice == 4:
                if any(h["restaurant_name"] == restaurant["restaurant_name"] for h in history):
                    bonus += 0.05
            elif choice == 5:
                if self._get_current_time_slot() not in restaurant.get("restaurant_time", []):
                    bonus += 0.05
        return min(base_rate + bonus, 0.30)

    def calc_win_rate_3rd(self, choices_with_filter, restaurant):
        base_rate = 0.025
        bonus = 0.0
        history = self.data["verdict_history"]
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
                    mid_high_count = sum(1 for h in recent5 if h["restaurant_price_level"] in [2, 3])
                    if mid_high_count >= 3:
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

    def re_recommend(self, restaurant_list, original, reason_filters):
        current_slot = self._get_current_time_slot()
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
                    recent_names = [h["restaurant_name"] for h in self.data["verdict_history"]]
                    pool = [r for r in pool if r["restaurant_name"] not in recent_names]

        if not pool:
            return None
        return random.choice(pool)


class EatingRecordManager:
    def __init__(self, appeal_manager, restaurant_manager):
        self.appeal_manager = appeal_manager
        self.restaurant_manager = restaurant_manager

    def add_record(self, name, date, category, price_level, distance, time_slots, add_to_db):
        record = {
            "date": date,
            "restaurant_name": name,
            "restaurant_category": category,
            "restaurant_price_level": price_level,
            "restaurant_distance": distance,
            "restaurant_time": time_slots,
        }
        self.appeal_manager.data["verdict_history"].append(record)
        self.appeal_manager.data["verdict_history"].sort(key=lambda h: h["date"])
        self.appeal_manager._save()

        if add_to_db and not self.restaurant_manager._find(name):
            self.restaurant_manager.restaurant_list.append({
                "restaurant_name": name,
                "restaurant_category": category,
                "restaurant_price_level": price_level,
                "restaurant_distance": distance,
                "restaurant_time": time_slots,
            })
            self.restaurant_manager._save()
            return True
        return False


class HistoryManager:
    PRICE_LEVELS = ['200元以內', '200~500元', '500元以上']
    DISTANCES = ['較近', '適中', '較遠']
    TIME_SLOTS = ['早餐', '午餐', '下午茶', '晚餐', '宵夜']

    def __init__(self, appeal_manager):
        self.appeal_manager = appeal_manager

    def query(self, mode, value=None):
        self.appeal_manager._clean_old_history()
        history = self.appeal_manager.data["verdict_history"]
        if mode == "全部":
            result = history
        elif mode == "種類":
            result = [h for h in history if h["restaurant_category"] == value]
        elif mode == "價位":
            result = [h for h in history if h["restaurant_price_level"] == value]
        else:
            result = history
        return self._to_display(result)

    def _to_display(self, history):
        result = []
        for h in history:
            result.append({
                "日期": h["date"],
                "餐廳名稱": h["restaurant_name"],
                "料理種類": h["restaurant_category"],
                "價位等級": self.PRICE_LEVELS[h["restaurant_price_level"] - 1],
                "距離": self.DISTANCES[h.get("restaurant_distance", 1) - 1],
                "用餐時段": "、".join([self.TIME_SLOTS[t - 1] for t in h.get("restaurant_time", [])]) or "未記錄",
            })
        return result


# =====================================================
# Streamlit 介面
# =====================================================

st.set_page_config(page_title="美食裁判所", page_icon="⚖️", layout="wide")

# ==================== Session State 初始化 ====================
if "manager" not in st.session_state:
    st.session_state.manager = RestaurantManager()
if "appeal_manager" not in st.session_state:
    st.session_state.appeal_manager = AppealManager()
if "record_manager" not in st.session_state:
    st.session_state.record_manager = EatingRecordManager(
        st.session_state.appeal_manager,
        st.session_state.manager
    )
if "history_manager" not in st.session_state:
    st.session_state.history_manager = HistoryManager(st.session_state.appeal_manager)

# 今日推薦相關狀態
if "recommend_result" not in st.session_state:
    st.session_state.recommend_result = None
if "appeal_stage" not in st.session_state:
    st.session_state.appeal_stage = None  # None / first / second / third / done
if "second_choices" not in st.session_state:
    st.session_state.second_choices = []
if "verdict_added" not in st.session_state:
    st.session_state.verdict_added = False

manager = st.session_state.manager
appeal_manager = st.session_state.appeal_manager
record_manager = st.session_state.record_manager
history_manager = st.session_state.history_manager

# ==================== 側邊欄 ====================
st.sidebar.title("⚖️ 美食裁判所")
st.sidebar.markdown("---")

st.sidebar.markdown("**📋 餐廳管理**")
page = st.sidebar.radio(
    label="功能選單",
    options=["新增餐廳", "修改餐廳", "刪除餐廳", "查詢餐廳", "🎲 今日推薦", "📝 手動飲食紀錄", "📊 歷史紀錄與飽食點數"],
    label_visibility="collapsed"
)

st.sidebar.markdown("---")
st.sidebar.markdown(f"**🍽️ 飽食點數：{appeal_manager.data['points']} 點**")

# ==================== 新增餐廳 ====================
if page == "新增餐廳":
    st.title("📋 新增餐廳")
    st.markdown("---")

    with st.form("add_form"):
        name = st.text_input("餐廳名稱")
        category = st.text_input("料理種類（如：日式、美式、台式）")
        price_level = st.selectbox("價位等級", options=[1, 2, 3],
                                   format_func=lambda x: ["200元以內", "200~500元", "500元以上"][x - 1])
        distance = st.selectbox("距離", options=[1, 2, 3],
                                format_func=lambda x: ["較近", "適中", "較遠"][x - 1])
        time_slots = st.multiselect("營業時段（可複選）",
                                    options=[1, 2, 3, 4, 5],
                                    format_func=lambda x: ["早餐", "午餐", "下午茶", "晚餐", "宵夜"][x - 1])
        submitted = st.form_submit_button("新增餐廳")

    if submitted:
        if not name:
            st.error("請輸入餐廳名稱")
        elif not category:
            st.error("請輸入料理種類")
        elif not time_slots:
            st.error("請選擇至少一個營業時段")
        else:
            success, msg = manager.add(name, category, price_level, distance, sorted(time_slots))
            if success:
                st.success(msg)
            else:
                st.error(msg)

# ==================== 修改餐廳 ====================
elif page == "修改餐廳":
    st.title("✏️ 修改餐廳")
    st.markdown("---")

    if not manager.restaurant_list:
        st.warning("目前尚無餐廳資料")
    else:
        name_options = [r["restaurant_name"] for r in manager.restaurant_list]
        selected_name = st.selectbox("請選擇欲修改的餐廳", options=name_options)
        target = manager._find(selected_name)

        if target:
            st.markdown(f"**目前資料：**")
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"料理種類：{target['restaurant_category']}")
                st.write(f"價位等級：{manager.PRICE_LEVELS[target['restaurant_price_level'] - 1]}")
            with col2:
                st.write(f"距離：{manager.DISTANCES[target['restaurant_distance'] - 1]}")
                st.write(f"營業時段：{'、'.join([manager.TIME_SLOTS[t-1] for t in target['restaurant_time']])}")

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
                                             format_func=lambda x: ["200元以內", "200~500元", "500元以上"][x - 1])
                    field_key = "restaurant_price_level"
                elif field == "距離":
                    new_value = st.selectbox("新的距離", options=[1, 2, 3],
                                             format_func=lambda x: ["較近", "適中", "較遠"][x - 1])
                    field_key = "restaurant_distance"
                else:
                    new_value = st.multiselect("新的營業時段（可複選）",
                                               options=[1, 2, 3, 4, 5],
                                               format_func=lambda x: ["早餐", "午餐", "下午茶", "晚餐", "宵夜"][x - 1])
                    field_key = "restaurant_time"

                submitted = st.form_submit_button("確認修改")

            if submitted:
                if field in ["餐廳名稱", "料理種類"] and not new_value:
                    st.error("請輸入新的值")
                elif field == "營業時段" and not new_value:
                    st.error("請選擇至少一個營業時段")
                else:
                    final_value = sorted(new_value) if field == "營業時段" else new_value
                    success, msg = manager.modify(selected_name, field_key, final_value)
                    if success:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

# ==================== 刪除餐廳 ====================
elif page == "刪除餐廳":
    st.title("🗑️ 刪除餐廳")
    st.markdown("---")

    if not manager.restaurant_list:
        st.warning("目前尚無餐廳資料")
    else:
        name_options = [r["restaurant_name"] for r in manager.restaurant_list]
        selected_name = st.selectbox("請選擇欲刪除的餐廳", options=name_options)
        target = manager._find(selected_name)

        if target:
            st.markdown("**確認刪除資料：**")
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"餐廳名稱：{target['restaurant_name']}")
                st.write(f"料理種類：{target['restaurant_category']}")
            with col2:
                st.write(f"價位等級：{manager.PRICE_LEVELS[target['restaurant_price_level'] - 1]}")
                st.write(f"距離：{manager.DISTANCES[target['restaurant_distance'] - 1]}")

            st.warning(f"確定要刪除「{selected_name}」嗎？此操作無法復原！")
            if st.button("確認刪除", type="primary"):
                success, msg = manager.delete(selected_name)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

# ==================== 查詢餐廳 ====================
elif page == "查詢餐廳":
    st.title("🔍 查詢餐廳")
    st.markdown("---")

    if not manager.restaurant_list:
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
                                 format_func=lambda x: ["200元以內", "200~500元", "500元以上"][x - 1])
        elif mode == "距離":
            value = st.selectbox("請選擇距離", options=[1, 2, 3],
                                 format_func=lambda x: ["較近", "適中", "較遠"][x - 1])
        elif mode == "時段":
            value = st.multiselect("請選擇時段（可複選）",
                                   options=[1, 2, 3, 4, 5],
                                   format_func=lambda x: ["早餐", "午餐", "下午茶", "晚餐", "宵夜"][x - 1])

        if st.button("查詢"):
            result = manager.query(mode, value)
            if not result:
                st.warning("查無符合條件的餐廳")
            else:
                st.success(f"共找到 {len(result)} 間餐廳")
                st.dataframe(manager.to_display_list(result), use_container_width=True)

# ==================== 今日推薦 ====================
elif page == "🎲 今日推薦":
    st.title("🎲 今日推薦")
    st.markdown("---")

    if not manager.restaurant_list:
        st.warning("目前尚無餐廳資料")
    else:
        # 開始推薦
        if st.button("🎰 開始判決", type="primary"):
            result, slot_name = manager.recommend()
            if result is None:
                st.warning(f"目前時段（{slot_name}）無可用餐廳")
            else:
                st.session_state.recommend_result = result
                st.session_state.appeal_stage = "ask_appeal"
                st.session_state.verdict_added = False
                st.session_state.second_choices = []

        # 顯示推薦結果
        if st.session_state.recommend_result:
            r = st.session_state.recommend_result
            st.markdown("### ⚖️ 判決結果")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("餐廳名稱", r["restaurant_name"])
                st.metric("料理種類", r["restaurant_category"])
            with col2:
                st.metric("價位等級", manager.PRICE_LEVELS[r["restaurant_price_level"] - 1])
                st.metric("距離", manager.DISTANCES[r["restaurant_distance"] - 1])

            st.markdown("---")

            # 詢問是否上訴
            if st.session_state.appeal_stage == "ask_appeal":
                st.info(f"💰 目前飽食點數：{appeal_manager.data['points']} 點")
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
                win, reasons = appeal_manager.first_trial(r)
                if win:
                    st.success("✅ 發現以下事實，一審勝訴！")
                    for reason in reasons:
                        st.write(f"• {reason}")
                    new = appeal_manager.re_recommend(manager.restaurant_list, r, None)
                    if new:
                        st.session_state.recommend_result = new
                        appeal_manager.add_verdict(new, True)
                        st.session_state.verdict_added = True
                    st.session_state.appeal_stage = "done"
                    st.rerun()
                else:
                    st.error("❌ 未發現足夠事實依據，一審敗訴")
                    if appeal_manager.data["points"] < 1:
                        st.warning("飽食點數不足，無法繼續上訴，維持原判決")
                        st.session_state.appeal_stage = "done"
                        st.rerun()
                    else:
                        st.info(f"💰 目前飽食點數：{appeal_manager.data['points']} 點（上訴將消耗1點）")
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
                    options=list(appeal_manager.APPEAL_OPTIONS_2ND.keys()),
                    format_func=lambda x: appeal_manager.APPEAL_OPTIONS_2ND[x],
                    max_selections=3
                )
                if st.button("提交二審"):
                    if not choices:
                        st.error("請至少選擇一項理由")
                    else:
                        appeal_manager.data["points"] -= 1
                        appeal_manager._save()

                        lies = appeal_manager.detect_lie_2nd(choices, r)
                        if lies:
                            st.error("⚠️ 系統偵測到以下矛盾：")
                            for lie in lies:
                                st.write(f"• {lie}")
                            st.error("【二審結果】陳述不實，判決敗訴，且不得上訴三審")
                            st.session_state.appeal_stage = "done"
                        else:
                            win_rate = appeal_manager.calc_win_rate_2nd(choices, r)
                            result_2nd = random.random() < win_rate
                            st.info(f"勝訴機率：{int(win_rate * 100)}%")

                            if result_2nd:
                                st.success("【二審結果】上訴成立，判決勝訴！")
                                new = appeal_manager.re_recommend(manager.restaurant_list, r, None)
                                if new:
                                    st.session_state.recommend_result = new
                                    appeal_manager.add_verdict(new, True)
                                    st.session_state.verdict_added = True
                                st.session_state.appeal_stage = "done"
                            else:
                                st.error("【二審結果】上訴不成立，判決敗訴")
                                st.session_state.second_choices = choices
                                if appeal_manager.data["points"] < 1:
                                    st.warning("飽食點數不足，無法繼續上訴，維持原判決")
                                    st.session_state.appeal_stage = "done"
                                else:
                                    st.session_state.appeal_stage = "ask_third"
                        st.rerun()

            # 詢問是否繼續至三審
            elif st.session_state.appeal_stage == "ask_third":
                st.info(f"💰 目前飽食點數：{appeal_manager.data['points']} 點（上訴將消耗1點）")
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
                valid = True

                for second_choice in st.session_state.second_choices:
                    options = appeal_manager.APPEAL_OPTIONS_3RD[second_choice]
                    third_choice = st.selectbox(
                        f"針對「{appeal_manager.APPEAL_OPTIONS_2ND[second_choice]}」，請選擇細項：",
                        options=list(options.keys()),
                        format_func=lambda x, o=options: o[x][0],
                        key=f"third_{second_choice}"
                    )
                    choices_with_filter.append((second_choice, third_choice, options[third_choice]))

                if st.button("提交三審"):
                    appeal_manager.data["points"] -= 1
                    appeal_manager._save()

                    lies = appeal_manager.detect_lie_3rd(choices_with_filter, r)
                    if lies:
                        st.error("⚠️ 系統偵測到以下矛盾：")
                        for lie in lies:
                            st.write(f"• {lie}")
                        st.error("【三審結果】陳述不實，判決敗訴，維持原判決")
                    else:
                        win_rate = appeal_manager.calc_win_rate_3rd(choices_with_filter, r)
                        result_3rd = random.random() < win_rate
                        st.info(f"勝訴機率：{int(win_rate * 100)}%")

                        if result_3rd:
                            st.success("【三審結果】上訴成立，判決勝訴！")
                            reason_filters = [f for _, _, (_, f) in choices_with_filter]
                            new = appeal_manager.re_recommend(manager.restaurant_list, r, reason_filters)
                            if new:
                                st.session_state.recommend_result = new
                                appeal_manager.add_verdict(new, True)
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
                            appeal_manager.add_verdict(final, True)
                            st.session_state.verdict_added = True
                            st.success(f"用餐完成！獲得1點飽食點數，目前共 {appeal_manager.data['points']} 點")
                            st.rerun()
                    with col2:
                        if st.button("❌ 否，尚未用餐"):
                            appeal_manager.add_verdict(final, False)
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
                                   format_func=lambda x: ["200元以內", "200~500元", "500元以上"][x - 1])
        distance = st.selectbox("距離", options=[1, 2, 3],
                                format_func=lambda x: ["較近", "適中", "較遠"][x - 1])
        time_slots = st.multiselect("用餐時段（可複選）",
                                    options=[1, 2, 3, 4, 5],
                                    format_func=lambda x: ["早餐", "午餐", "下午茶", "晚餐", "宵夜"][x - 1])

        existing = record_manager.restaurant_manager._find(name) if name else True
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
            date_str = date.strftime("%Y-%m-%d")
            added_to_db = record_manager.add_record(
                name, date_str, category, price_level,
                distance, sorted(time_slots), add_to_db
            )
            st.success(f"「{name}」已成功記錄至飲食紀錄")
            if added_to_db:
                st.success(f"「{name}」已同時新增至餐廳資料庫")

# ==================== 歷史紀錄與飽食點數 ====================
elif page == "📊 歷史紀錄與飽食點數":
    st.title("📊 歷史紀錄與飽食點數查詢")
    st.markdown("---")

    st.markdown("### 🍽️ 目前飽食點數")
    st.markdown(f"##### {appeal_manager.data['points']} 點")
    st.markdown("---")
    st.markdown("### 📜 歷史紀錄查詢")

    mode = st.selectbox("查詢方式", options=["全部", "種類", "價位"])
    value = None

    if mode == "種類":
        value = st.text_input("請輸入料理種類")
    elif mode == "價位":
        value = st.selectbox("請選擇價位等級", options=[1, 2, 3],
                             format_func=lambda x: ["200元以內", "200~500元", "500元以上"][x - 1])

    if st.button("查詢"):
        result = history_manager.query(mode, value)
        if not result:
            st.warning("查無符合條件的紀錄")
        else:
            st.success(f"共找到 {len(result)} 筆紀錄")
            st.dataframe(result, use_container_width=True)
