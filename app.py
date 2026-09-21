import os
import pandas as pd
import streamlit as st
from datetime import datetime, date
import uuid

# ========== 改你自己的密码 ==========
ADMIN_PASSWORD = "你自己设一个密码"
SHOP_NAME = "我的果蔬店"
SUPPLIER_LIST = ["本地蔬菜批发", "山东蔬菜基地", "菌菇配送中心", "烟台苹果直供", "本地草莓基地"]
# ======================================

# 云部署持久化数据，不会丢
@st.cache_data(ttl=0)
def load_data():
    if os.path.exists("delivery_records.csv"):
        return pd.read_csv("delivery_records.csv", dtype=str).fillna("")
    else:
        return pd.DataFrame(columns=[
            "提交时间","供应商名称","送货日期","商品名称","品类",
            "送货数量","单位","进货单价","保质期(天)"
        ])

def save_data(df):
    df.to_csv("delivery_records.csv", index=False, encoding='utf-8-sig')

st.set_page_config(page_title=f"{SHOP_NAME} 送货填报", layout="centered", page_icon="📝")
menu = st.sidebar.radio("菜单", ["📝 供应商填报", "🔒 后台导出数据"])

# ========== 供应商填报页 ==========
if menu == "📝 供应商填报":
    st.title(f"🚚 {SHOP_NAME} 送货登记")
    st.caption("填写当日送货信息，提交后商家即可收到")
    
    if 'rows' not in st.session_state:
        st.session_state.rows = 1
    if 'ok' not in st.session_state:
        st.session_state.ok = False

    if st.session_state.ok:
        st.success("✅ 提交成功！商家已收到，感谢配合")
        if st.button("填写新送货单"):
            st.session_state.ok = False
            st.session_state.rows = 1
            st.rerun()
        st.stop()

    with st.form("form"):
        col1, col2 = st.columns(2)
        with col1:
            supplier = st.selectbox("您的供应商名称", ["请选择"] + SUPPLIER_LIST + ["其他（手动填写）"])
            if supplier == "其他（手动填写）":
                supplier = st.text_input("输入名称", placeholder="例如：XX果蔬批发")
        with col2:
            delivery_date = st.date_input("送货日期", value=date.today())
        
        st.divider()
        st.subheader("商品明细")
        goods = []
        for i in range(st.session_state.rows):
            st.markdown(f"**商品 {i+1}**")
            c1,c2,c3 = st.columns(3)
            name = c1.text_input("品种名称", key=f"n{i}", placeholder="上海青")
            cat = c2.selectbox("品类", ["叶菜","根茎","花果","菌菇","水果","其他"], key=f"c{i}")
            unit = c3.selectbox("单位", ["斤","公斤","箱","袋"], key=f"u{i}")
            qty = c1.number_input("送货数量", min_value=0.0, step=0.5, key=f"q{i}")
            price = c2.number_input("进货单价(元)", min_value=0.0, step=0.1, key=f"p{i}")
            life = c3.number_input("保质期(天)", min_value=1, value=2, key=f"l{i}")
            if name and qty>0:
                goods.append({
                    "提交时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "供应商名称": supplier if supplier!="请选择" else "未填写",
                    "送货日期": delivery_date.strftime("%Y-%m-%d"),
                    "商品名称": name,
                    "品类": cat,
                    "送货数量": str(qty),
                    "单位": unit,
                    "进货单价": str(price),
                    "保质期(天)": str(life)
                })
            st.divider()
        
        b1,b2,_ = st.columns([1,1,3])
        add = b1.form_submit_button("➕ 加一个品种", use_container_width=True)
        delete = b2.form_submit_button("➖ 删除最后一行", use_container_width=True)
        submit = st.form_submit_button("✅ 提交送货单", type="primary", use_container_width=True)

    if add and st.session_state.rows < 20:
        st.session_state.rows += 1
        st.rerun()
    if delete and st.session_state.rows>1:
        st.session_state.rows -= 1
        st.rerun()

    if submit:
        if supplier == "请选择":
            st.error("❌ 请先选择供应商名称")
            st.stop()
        if len(goods) == 0:
            st.error("❌ 请至少填写一个商品")
            st.stop()
        df_old = load_data()
        df_new = pd.DataFrame(goods)
        df_all = pd.concat([df_old, df_new], ignore_index=True)
        save_data(df_all)
        st.session_state.ok = True
        st.rerun()

# ========== 后台导出页 ==========
else:
    st.title("🔒 数据后台")
    pwd = st.text_input("管理密码", type="password")
    if pwd != ADMIN_PASSWORD:
        st.warning("请输入正确密码")
        st.stop()
    
    df = load_data()
    # 转回数字类型
    for col in ["送货数量","进货单价","保质期(天)"]:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    st.success(f"登录成功，当前共 {len(df)} 条送货记录")
    
    st.subheader("数据筛选")
    f1,f2,f3 = st.columns(3)
    s_sup = f1.selectbox("按供应商", ["全部"] + sorted(df["供应商名称"].unique().tolist()))
    s_date = f2.date_input("按送货日期", value=None)
    s_cat = f3.selectbox("按品类", ["全部"] + sorted(df["品类"].dropna().unique().tolist()))
    
    df_show = df.copy()
    if s_sup != "全部":
        df_show = df_show[df_show["供应商名称"] == s_sup]
    if s_date:
        df_show = df_show[df_show["送货日期"] == s_date.strftime("%Y-%m-%d")]
    if s_cat != "全部":
        df_show = df_show[df_show["品类"] == s_cat]
    
    st.dataframe(df_show, use_container_width=True)
    
    c1,c2 = st.columns(2)
    csv = df_show.to_csv(index=False, encoding='utf-8-sig')
    c1.download_button("📥 导出当前筛选结果", csv, f"送货记录_{date.today()}.csv", "text/csv", use_container_width=True)
    all_csv = df.to_csv(index=False, encoding='utf-8-sig')
    c2.download_button("📥 导出全部历史记录", all_csv, f"全部送货记录_{date.today()}.csv", "text/csv", use_container_width=True)
    
    if st.button("⚠️ 清空所有记录（不可恢复）"):
        save_data(pd.DataFrame(columns=df.columns))
        st.success("已清空")
        st.rerun()
