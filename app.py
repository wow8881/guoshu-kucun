import os
import glob
import pandas as pd
import numpy as np
import streamlit as st
# 自动检测matplotlib是否安装，没装就用streamlit原生图表
try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
    plt.rcParams['font.sans-serif'] = ['SimHei', 'WenQuanYi Micro Hei', 'Arial Unicode MS', 'Noto Sans CJK SC', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
except ImportError:
    MATPLOTLIB_AVAILABLE = False
from datetime import datetime
# ========== 页面基础配置 ==========
st.set_page_config(page_title="果蔬库存实时看板", layout="wide", page_icon="🥬", initial_sidebar_state="expanded")
# 自动找和py文件同一个目录下的inventory文件夹，不存在就自动创建
current_dir = os.path.dirname(os.path.abspath(__file__))
INVENTORY_FOLDER = os.path.join(current_dir, "inventory")
os.makedirs(INVENTORY_FOLDER, exist_ok=True)  # 自动创建文件夹，不用手动建
# 销售记录保存路径
SALES_FILE = os.path.join(INVENTORY_FOLDER, "销售记录.xlsx")
# 品类保质期配置文件路径
SHELF_CONFIG_FILE = os.path.join(INVENTORY_FOLDER, "品类保质期配置.xlsx")
# 内置默认品类保质期（常见果蔬）
DEFAULT_SHELF_LIFE = {
    "叶菜类": 3,
    "花果类": 7,
    "根茎类": 30,
    "菌菇类": 5,
    "豆类": 5,
    "瓜类": 10,
    "葱蒜类": 15,
    "柑橘类": 15,
    "仁果类": 30,
    "浆果类": 5,
    "核果类": 7,
    "瓜类水果": 10,
    "热带水果": 7
}
# 加载品类保质期配置
@st.cache_data(show_spinner=False)
def load_shelf_config():
    if os.path.exists(SHELF_CONFIG_FILE):
        config_df = pd.read_excel(SHELF_CONFIG_FILE)
        return dict(zip(config_df['品类'], config_df['默认保质期(天)']))
    else:
        # 第一次使用默认配置，保存到文件
        config_df = pd.DataFrame(list(DEFAULT_SHELF_LIFE.items()), columns=['品类', '默认保质期(天)'])
        config_df.to_excel(SHELF_CONFIG_FILE, index=False)
        return DEFAULT_SHELF_LIFE.copy()
shelf_config = load_shelf_config()
# 提前定义数据加载函数
@st.cache_data(show_spinner=False)
def load_latest_inventory():
    files = []
    for ext in ['xlsx', 'csv']:
        files.extend(glob.glob(os.path.join(INVENTORY_FOLDER, f"*.{ext}")))
    if not files:
        return None, "empty"
    latest_file = max(files, key=os.path.getmtime)
    try:
        if latest_file.endswith('.csv'):
            df = None
            for enc in ['utf-8-sig', 'utf-8', 'gbk', 'gb2312']:
                try:
                    df = pd.read_csv(latest_file, encoding=enc)
                    break
                except:
                    continue
            if df is None:
                return None, "read_error"
        else:
            df = pd.read_excel(latest_file)
        return df, os.path.basename(latest_file)
    except Exception as e:
        return None, f"error:{str(e)}"
# 加载销售记录
@st.cache_data(show_spinner=False)
def load_sales_records():
    if os.path.exists(SALES_FILE):
        return pd.read_excel(SALES_FILE)
    else:
        return pd.DataFrame(columns=['时间', '商品名称', '销售数量', '销售单价', '销售额', '毛利'])
# ========== 侧边栏配置 ==========
with st.sidebar:
    st.header("⚙️ 看板配置")
    SHOP_NAME = st.text_input("店铺名称", value="我的果蔬店")
    LOW_STOCK_WARN = st.number_input("库存预警阈值（低于该值提醒补货）", min_value=1, value=10, step=1)
    DEFAULT_UNIT = st.text_input("默认单位", value="斤")
    st.divider()
    # ========== 数据提报/上传区域 ==========
    st.header("📝 库存管理")
    data_tab1, data_tab2, data_tab3, data_tab4, data_tab5, data_tab6 = st.tabs(["📤 上传", "✍️ 新增", "📦 出库", "📊 盘点", "⏳ 保质期配置", "🗑️ 管理"])
    # 上传文件提报
    with data_tab1:
        uploaded_file = st.file_uploader("上传库存Excel/CSV", type=['xlsx', 'csv'], help="上传后自动保存到inventory文件夹，作为最新数据")
        if uploaded_file is not None:
            if st.button("确认上传并同步", use_container_width=True, type="primary"):
                # 保存上传的文件到inventory文件夹，用时间戳命名避免重名
                ext = os.path.splitext(uploaded_file.name)[1]
                save_name = f"库存提报_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
                save_path = os.path.join(INVENTORY_FOLDER, save_name)
                with open(save_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                st.success(f"✅ 已同步保存到文件夹：{save_name}")
                st.cache_data.clear()
                st.rerun()
    # 手动录入单个商品
    with data_tab2:
        # 先选品类，自动带出默认保质期
        existing_cats = list(shelf_config.keys())
        cat_options = sorted(existing_cats + ['自定义新分类'])
        with st.form("add_product_form", clear_on_submit=True):
            p_name = st.text_input("商品名称 *", placeholder="例如：上海青")
            col_cat, col_shelf = st.columns(2)
            selected_cat_option = col_cat.selectbox("品类 *", options=cat_options)
            if selected_cat_option == '自定义新分类':
                p_cat = col_cat.text_input("输入新品类名称", placeholder="例如：预制菜类")
                default_shelf = 7
            else:
                p_cat = selected_cat_option
                default_shelf = shelf_config.get(p_cat, 7)
            # 根据选的品类自动填充默认保质期
            p_shelf = col_shelf.number_input("保质期(天) *", min_value=1, value=default_shelf, step=1, help="系统已根据品类自动填充默认值，可手动修改")
            col1, col2 = st.columns(2)
            p_stock = col1.number_input("库存数量 *", min_value=0, step=1)
            p_in_date = col2.date_input("入库时间", value=datetime.now())
            p_unit = st.text_input("单位", value=DEFAULT_UNIT)
            p_price = st.number_input("进货价(元/单位)", min_value=0.0, step=0.1)
            p_supplier = st.text_input("供应商名称", value="未填写")
            if p_cat in shelf_config and p_cat != '自定义新分类':
                st.caption(f"✅ 已自动匹配「{p_cat}」默认保质期：{shelf_config[p_cat]}天，可手动修改")
            submit_add = st.form_submit_button("提交并同步到库存", use_container_width=True, type="primary")
            if submit_add:
                if not p_name or not p_cat:
                    st.error("请填写商品名称和品类")
                else:
                    # 先读取现有最新数据，追加新商品
                    existing_df, _ = load_latest_inventory()
                    new_row = pd.DataFrame([{
                        '商品名称': p_name.strip(),
                        '品类': p_cat.strip(),
                        '库存数量': p_stock,
                        '入库时间': pd.Timestamp(p_in_date),
                        '保质期(天)': p_shelf,
                        '单位': p_unit.strip() if p_unit else DEFAULT_UNIT,
                        '进货价': p_price if p_price > 0 else None,
                        '供应商名称': p_supplier.strip() if p_supplier else "未填写"
                    }])
                    if existing_df is not None:
                        updated_df = pd.concat([existing_df, new_row], ignore_index=True)
                    else:
                        updated_df = new_row
                    # 保存新文件到inventory
                    save_name = f"库存更新_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                    save_path = os.path.join(INVENTORY_FOLDER, save_name)
                    updated_df.to_excel(save_path, index=False)
                    # 自动把新品类加入保质期配置
                    if p_cat not in shelf_config and p_cat != '自定义新分类':
                        shelf_config[p_cat] = p_shelf
                        new_config = pd.DataFrame(list(shelf_config.items()), columns=['品类', '默认保质期(天)'])
                        new_config.to_excel(SHELF_CONFIG_FILE, index=False)
                    st.success(f"✅ 已添加商品「{p_name}」并同步到文件夹")
                    st.cache_data.clear()
                    st.rerun()
    # 销售/出库功能
    with data_tab3:
        existing_df, _ = load_latest_inventory()
        if existing_df is None or len(existing_df) == 0:
            st.info("暂无库存数据，先添加商品")
        else:
            if '单位' not in existing_df.columns:
                existing_df['单位'] = DEFAULT_UNIT
            if '进货价' not in existing_df.columns:
                existing_df['进货价'] = 0
            all_products = existing_df['商品名称'].tolist()
            with st.form("sales_form", clear_on_submit=True):
                sell_p = st.selectbox("选择出库商品", all_products)
                p_info = existing_df[existing_df['商品名称']==sell_p].iloc[0]
                col_s1, col_s2 = st.columns(2)
                sell_qty = col_s1.number_input("出库数量", min_value=0.1, step=0.1, max_value=float(p_info['库存数量']))
                sell_price = col_s2.number_input("销售单价(元)", min_value=0.0, step=0.1, value=float(p_info.get('进货价',0)*1.3))
                st.caption(f"当前库存：{p_info['库存数量']:.0f}{p_info['单位']}，进货价：{p_info.get('进货价',0):.1f}元/{p_info['单位']}")
                submit_sell = st.form_submit_button("确认出库并扣减库存", use_container_width=True, type="primary")
                if submit_sell:
                    # 扣减库存
                    existing_df.loc[existing_df['商品名称']==sell_p, '库存数量'] = p_info['库存数量'] - sell_qty
                    # 计算销售额和毛利
                    sales_amount = sell_qty * sell_price
                    profit = sell_qty * (sell_price - p_info.get('进货价',0))
                    # 保存更新库存
                    save_name = f"库存更新_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                    save_path = os.path.join(INVENTORY_FOLDER, save_name)
                    existing_df.to_excel(save_path, index=False)
                    # 保存销售记录
                    sales_df = load_sales_records()
                    new_sale = pd.DataFrame([{
                        '时间': datetime.now().strftime('%Y-%m-%d %H:%M'),
                        '商品名称': sell_p,
                        '销售数量': sell_qty,
                        '销售单价': sell_price,
                        '销售额': sales_amount,
                        '毛利': profit
                    }])
                    sales_df = pd.concat([sales_df, new_sale], ignore_index=True)
                    sales_df.to_excel(SALES_FILE, index=False)
                    st.success(f"✅ 出库成功：{sell_qty}{p_info['单位']} {sell_p}，销售额{sales_amount:.1f}元，毛利{profit:.1f}元")
                    st.cache_data.clear()
                    st.rerun()
    # 批量盘点功能
    with data_tab4:
        st.markdown("**快速盘点：一次性修改多个商品库存**")
        existing_df, _ = load_latest_inventory()
        if existing_df is None or len(existing_df) == 0:
            st.info("暂无库存数据")
        else:
            if '单位' not in existing_df.columns:
                existing_df['单位'] = DEFAULT_UNIT
            edited_df = st.data_editor(
                existing_df[['商品名称', '品类', '库存数量', '单位']],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "库存数量": st.column_config.NumberColumn(min_value=0, step=1)
                }
            )
            if st.button("保存盘点结果", use_container_width=True, type="primary"):
                # 更新库存数量
                for idx, row in edited_df.iterrows():
                    existing_df.loc[existing_df['商品名称']==row['商品名称'], '库存数量'] = row['库存数量']
                save_name = f"盘点更新_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                save_path = os.path.join(INVENTORY_FOLDER, save_name)
                existing_df.to_excel(save_path, index=False)
                st.success("✅ 盘点结果已保存，库存已更新")
                st.cache_data.clear()
                st.rerun()
    # 品类保质期配置
    with data_tab5:
        st.markdown("**品类保质期配置：选品类自动匹配默认保质期**")
        config_df = pd.DataFrame(list(shelf_config.items()), columns=['品类', '默认保质期(天)'])
        edited_config = st.data_editor(
            config_df,
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            column_config={
                "默认保质期(天)": st.column_config.NumberColumn(min_value=1, step=1)
            }
        )
        if st.button("保存保质期配置", use_container_width=True, type="primary"):
            edited_config.to_excel(SHELF_CONFIG_FILE, index=False)
            st.success("✅ 保质期配置已保存，新增商品会自动匹配，老数据自动补全")
            st.cache_data.clear()
            st.rerun()
        st.info("💡 可以新增/删除品类，修改对应默认保质期：\n- 新增商品选品类自动填充保质期\n- 上传的老数据如果保质期异常/没填，会自动按品类匹配默认保质期")
    # 管理现有商品：修改库存/删除
    with data_tab6:
        existing_df, _ = load_latest_inventory()
        if existing_df is None or len(existing_df) == 0:
            st.info("暂无库存数据，先上传或添加商品")
        else:
            # 补全列避免报错
            if '单位' not in existing_df.columns:
                existing_df['单位'] = DEFAULT_UNIT
            all_products = existing_df['商品名称'].tolist()
            selected_p = st.selectbox("选择要修改的商品", all_products)
            if selected_p:
                p_data = existing_df[existing_df['商品名称'] == selected_p].iloc[0]
                new_stock = st.number_input("修改库存数量", min_value=0, value=int(p_data['库存数量']), step=1)
                if st.button("更新库存", use_container_width=True):
                    existing_df.loc[existing_df['商品名称'] == selected_p, '库存数量'] = new_stock
                    save_name = f"库存更新_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                    save_path = os.path.join(INVENTORY_FOLDER, save_name)
                    existing_df.to_excel(save_path, index=False)
                    st.success(f"✅ 已更新「{selected_p}」库存为 {new_stock}")
                    st.cache_data.clear()
                    st.rerun()
                st.divider()
                if st.button("🗑️ 删除该商品", use_container_width=True, type="secondary"):
                    updated_df = existing_df[existing_df['商品名称'] != selected_p]
                    save_name = f"库存更新_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                    save_path = os.path.join(INVENTORY_FOLDER, save_name)
                    updated_df.to_excel(save_path, index=False)
                    st.success(f"✅ 已删除商品「{selected_p}」")
                    st.cache_data.clear()
                    st.rerun()
    st.divider()
    if st.button("🔄 刷新最新数据", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    if not MATPLOTLIB_AVAILABLE:
        st.info("💡 当前环境未安装matplotlib，图表已自动切换为Streamlit原生样式")
    st.markdown("""
    ### 📖 使用说明
    1. 系统自动创建`inventory`文件夹，无需手动新建
    2. 支持上传Excel/CSV、手动新增商品、销售出库扣库存、批量盘点、修改/删除商品
    3. 内置品类保质期自动匹配：选品类自动填保质期，老数据异常保质期自动补全，可自定义每个品类保质期
    4. 所有操作自动保存同步到文件夹，自动加载最新版本，自动记录销售和毛利
    5. **必填列**：商品名称、品类、库存数量、入库时间
    6. **可选列**：保质期(天)（不填自动按品类匹配）、单位、进货价、供应商名称
    7. 支持手机/电脑自适应显示
    """)
st.title(f"🥬 {SHOP_NAME} 库存实时数据看板")
st.caption(f"最后更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
result = load_latest_inventory()
if result[1] == "empty":
    st.info("💡 还没有库存数据，请在左侧上传Excel文件，或者手动新增商品开始使用~")
    st.stop()
elif result[1] == "read_error":
    st.error(f"读取文件失败：文件编码无法识别，请保存为UTF-8格式的Excel或CSV")
    st.stop()
elif result[1].startswith("error:"):
    st.error(f"读取文件失败：{result[1][6:]}，请检查文件格式")
    st.stop()
df, filename = result
st.success(f"✅ 正在读取最新库存文件：{filename}")
# 数据预处理
required_cols = ['商品名称','品类','库存数量','入库时间']
missing = [c for c in required_cols if c not in df.columns]
if missing:
    st.error(f"❌ 文件缺少必填列：{', '.join(missing)}，请检查列名")
    st.info("💡 必填列：商品名称、品类、库存数量、入库时间；可选列：保质期(天)（不填自动按品类匹配）、单位、进货价、供应商名称")
    st.stop()
# 数据清洗：处理异常值
df = df.dropna(subset=['商品名称', '品类'])  # 删除空名称空品类的行
df['商品名称'] = df['商品名称'].astype(str).str.strip()
df['品类'] = df['品类'].astype(str).str.strip()
df['库存数量'] = pd.to_numeric(df['库存数量'], errors='coerce').fillna(0).clip(lower=0)  # 负数库存转为0
df['保质期(天)'] = pd.to_numeric(df['保质期(天)'], errors='coerce')
# 自动按品类匹配保质期：异常值（空/0/超过365天）自动用配置里的默认值，匹配不到默认7天
def fill_shelf_by_cat(row):
    if pd.isna(row['保质期(天)']) or row['保质期(天)'] < 1 or row['保质期(天)'] > 365:
        return shelf_config.get(row['品类'], 7)
    return row['保质期(天)']
df['保质期(天)'] = df.apply(fill_shelf_by_cat, axis=1).astype(int)
# 补全可选字段
if '单位' not in df.columns:
    df['单位'] = DEFAULT_UNIT
df['单位'] = df['单位'].fillna(DEFAULT_UNIT).astype(str).str.strip()
if '供应商名称' not in df.columns:
    df['供应商名称'] = '未填写'
df['供应商名称'] = df['供应商名称'].fillna('未填写').astype(str).str.strip()
df['入库时间'] = pd.to_datetime(df['入库时间'], errors='coerce')
# 处理无效入库时间：超过今天的设为今天，空值设为今天
invalid_date_mask = df['入库时间'].isna() | (df['入库时间'] > pd.Timestamp(datetime.now()))
df.loc[invalid_date_mask, '入库时间'] = pd.Timestamp(datetime.now().date())
today = pd.Timestamp(datetime.now().date())
df['已存放天数'] = (today - df['入库时间']).dt.days
df['剩余保质期(天)'] = (df['保质期(天)'] - df['已存放天数']).clip(lower=0)  # 负剩余天数统一为0
# 进货价可选，没有就不计算货值
total_value = None
if '进货价' in df.columns:
    df['进货价'] = pd.to_numeric(df['进货价'], errors='coerce').fillna(0)
    df['库存货值(元)'] = df['库存数量'] * df['进货价']
    total_value = df['库存货值(元)'].sum()
def get_warn_info(remain):
    if remain < 1: return ('🔴 紧急', '今日必须处理', '#ff4757')
    if remain <= 3: return ('🟠 警告', '3天内过期', '#ffa502')
    if remain <= 7: return ('🟡 注意', '7天内过期', '#ffd32a')
    return ('🟢 正常', '库存健康', '#2ed573')
df[['预警标签','预警说明','颜色']] = df['剩余保质期(天)'].apply(lambda x: pd.Series(get_warn_info(x)))
df['预警等级排序'] = df['剩余保质期(天)'].apply(lambda x: 0 if x<1 else 1 if x<=3 else 2 if x<=7 else 3)
# ====================== 筛选区域 ======================
st.subheader("🔍 库存筛选")
filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)
# 品类筛选
all_cats = ['全部品类'] + sorted(df['品类'].unique().tolist())
selected_cat = filter_col1.selectbox("按品类筛选", all_cats)
# 临期等级筛选
warn_levels = ['全部状态', '🔴 紧急（今日处理）', '🟠 警告（3天内过期）', '🟡 注意（7天内过期）', '🟢 正常库存']
selected_level = filter_col2.selectbox("按临期状态筛选", warn_levels)
# 供应商筛选
all_suppliers = ['全部供应商'] + sorted(df['供应商名称'].unique().tolist())
selected_supplier = filter_col3.selectbox("按供应商筛选", all_suppliers)
# 搜索框
search_keyword = filter_col4.text_input("搜索商品名称", placeholder="输入商品名关键词搜索")
# 应用筛选
filtered_df = df.copy()
if selected_cat != '全部品类':
    filtered_df = filtered_df[filtered_df['品类'] == selected_cat]
if selected_level != '全部状态':
    level_map = {
        '🔴 紧急（今日处理）': '🔴 紧急',
        '🟠 警告（3天内过期）': '🟠 警告',
        '🟡 注意（7天内过期）': '🟡 注意',
        '🟢 正常库存': '🟢 正常'
    }
    filtered_df = filtered_df[filtered_df['预警标签'] == level_map[selected_level]]
if selected_supplier != '全部供应商':
    filtered_df = filtered_df[filtered_df['供应商名称'] == selected_supplier]
if search_keyword:
    filtered_df = filtered_df[filtered_df['商品名称'].str.contains(search_keyword, case=False)]
# 统一用主单位（出现最多的单位）
main_unit = df['单位'].mode()[0] if len(df['单位'].mode())>0 else DEFAULT_UNIT
st.info(f"当前筛选结果：共 {len(filtered_df)} 个SKU，总库存 {filtered_df['库存数量'].sum():.0f}{main_unit}")
st.divider()
# 顶部总览卡片（统一布局）
if len(filtered_df) == 0:
    st.warning("当前筛选条件下没有商品，请调整筛选条件")
    st.stop()
total_sku = len(filtered_df)
total_stock = filtered_df['库存数量'].sum()
urgent_count = len(filtered_df[filtered_df['剩余保质期(天)']<1])
warn_count = len(filtered_df[(filtered_df['剩余保质期(天)']>=1)&(filtered_df['剩余保质期(天)']<=3)])
notice_count = len(filtered_df[(filtered_df['剩余保质期(天)']>3)&(filtered_df['剩余保质期(天)']<=7)])
low_stock_count = len(filtered_df[filtered_df['库存数量'] <= LOW_STOCK_WARN])
filter_total_value = filtered_df['库存货值(元)'].sum() if '库存货值(元)' in filtered_df.columns else None
# 加载销售数据统计
sales_df = load_sales_records()
today_str = datetime.now().strftime('%Y-%m-%d')
today_sales = sales_df[sales_df['时间'].str.startswith(today_str)]['销售额'].sum() if len(sales_df) >0 else 0
today_profit = sales_df[sales_df['时间'].str.startswith(today_str)]['毛利'].sum() if len(sales_df) >0 else 0
# 库存健康度评分：0-100分
health_score = 100
health_score -= min(urgent_count*10, 40)  # 今日到期每个扣10分，最多扣40
health_score -= min(warn_count*5, 25)    # 3天到期每个扣5分，最多扣25
health_score -= min(low_stock_count*5, 25) # 库存不足每个扣5分，最多扣25
health_score = max(0, health_score)
# 健康度评分颜色
if health_score >= 80:
    score_color = "#2ed573"
    score_text = "优秀"
elif health_score >=60:
    score_color = "#ffd32a"
    score_text = "一般"
else:
    score_color = "#ff4757"
    score_text = "需改进"
# 6列卡片布局，兼容移动端自动换行
cols = st.columns(6)
cols[0].metric("筛选SKU总数", f"{total_sku} 个")
cols[1].metric("筛选总库存量", f"{total_stock:.0f}{main_unit}")
cols[2].metric("🔴 今日到期", f"{urgent_count} 个", delta="立即处理", delta_color="inverse")
cols[3].metric("🟠 3天内到期", f"{warn_count} 个", delta="优先销售", delta_color="inverse")
cols[4].metric("📉 库存不足", f"{low_stock_count} 个", delta=f"低于{LOW_STOCK_WARN}{main_unit}", delta_color="inverse")
cols[5].metric("💯 库存健康度", f"{health_score}分", delta=score_text)
# 第二行：货值/经营数据
value_text = f"{filter_total_value:.1f}元" if filter_total_value and filter_total_value>0 else "未统计"
st.markdown(f"<h4 style='text-align:center;color:{score_color};'>今日销售额：{today_sales:.1f}元 | 今日毛利：{today_profit:.1f}元 | 当前筛选货值：{value_text}</h4>", unsafe_allow_html=True)
st.divider()
# 临期预警区域（用筛选后的数据）
st.subheader("⚠️ 临期商品预警（按紧急程度排序）")
warn_df = filtered_df[filtered_df['剩余保质期(天)']<=7].sort_values(['剩余保质期(天)', '库存数量'], ascending=[True, False])
if len(warn_df) == 0:
    st.success("🎉 当前筛选条件下没有临期商品，库存健康~")
else:
    # 按预警等级分组显示
    tab_urgent, tab_warn, tab_notice = st.tabs([f"🔴 今日到期 ({urgent_count})", f"🟠 3天内到期 ({warn_count})", f"🟡 7天内到期 ({notice_count})"])
    # 今日到期
    with tab_urgent:
        urgent_df = warn_df[warn_df['剩余保质期(天)']<1]
        if len(urgent_df) == 0:
            st.success("✅ 今日没有到期商品")
        else:
            cols = st.columns(min(len(urgent_df), 3))
            for i, (_, r) in enumerate(urgent_df.iterrows()):
                with cols[i % len(cols)]:
                    suggest = "今日必须清完：降价/搭售/加工成净菜/员工内购"
                    st.markdown(f"""
                    <div style="padding:15px;border-radius:10px;background-color:{r['颜色']}15;border-left:5px solid {r['颜色']};margin-bottom:10px;">
                        <h4 style="margin:0;color:{r['颜色']};">{r['商品名称']}</h4>
                        <p style="margin:5px 0;font-size:14px;">{r['品类']} | 供应商：{r['供应商名称']}</p>
                        <p style="margin:0;font-size:16px;font-weight:bold;">当前库存：{r['库存数量']:.0f}{r['单位']}</p>
                        <p style="margin:8px 0 0 0;font-size:13px;">💡 {suggest}</p>
                    </div>
                    """, unsafe_allow_html=True)
    # 3天内到期
    with tab_warn:
        w_df = warn_df[(warn_df['剩余保质期(天)']>=1)&(warn_df['剩余保质期(天)']<=3)]
        if len(w_df) == 0:
            st.success("✅ 3天内没有到期商品")
        else:
            cols = st.columns(min(len(w_df), 3))
            for i, (_, r) in enumerate(w_df.iterrows()):
                with cols[i % len(cols)]:
                    suggest = "黄金陈列位销售，搭配临期品做组合优惠"
                    st.markdown(f"""
                    <div style="padding:15px;border-radius:10px;background-color:{r['颜色']}15;border-left:5px solid {r['颜色']};margin-bottom:10px;">
                        <h4 style="margin:0;color:{r['颜色']};">{r['商品名称']}</h4>
                        <p style="margin:5px 0;font-size:14px;">剩{r['剩余保质期(天)']}天 | {r['品类']} | {r['供应商名称']}</p>
                        <p style="margin:0;font-size:16px;font-weight:bold;">当前库存：{r['库存数量']:.0f}{r['单位']}</p>
                        <p style="margin:8px 0 0 0;font-size:13px;">💡 {suggest}</p>
                    </div>
                    """, unsafe_allow_html=True)
    # 7天内到期
    with tab_notice:
        n_df = warn_df[(warn_df['剩余保质期(天)']>3)&(warn_df['剩余保质期(天)']<=7)]
        if len(n_df) == 0:
            st.success("✅ 7天内没有临期商品")
        else:
            cols = st.columns(min(len(n_df), 4))
            for i, (_, r) in enumerate(n_df.iterrows()):
                with cols[i % len(cols)]:
                    suggest = "正常销售，每日检查新鲜度"
                    st.markdown(f"""
                    <div style="padding:15px;border-radius:10px;background-color:{r['颜色']}15;border-left:5px solid {r['颜色']};margin-bottom:10px;">
                        <h4 style="margin:0;color:{r['颜色']};">{r['商品名称']}</h4>
                        <p style="margin:5px 0;font-size:14px;">剩{r['剩余保质期(天)']}天 | {r['品类']}</p>
                        <p style="margin:0;font-size:16px;font-weight:bold;">当前库存：{r['库存数量']:.0f}{r['单位']}</p>
                        <p style="margin:8px 0 0 0;font-size:13px;">💡 {suggest}</p>
                    </div>
                    """, unsafe_allow_html=True)
st.divider()
# 库存不足提醒（筛选后）
st.subheader("📉 库存不足提醒")
low_df = filtered_df[filtered_df['库存数量'] <= LOW_STOCK_WARN].sort_values('库存数量')
if len(low_df) == 0:
    st.success(f"✅ 当前筛选条件下所有商品库存都高于{LOW_STOCK_WARN}{main_unit}，库存充足")
else:
    low_cols = st.columns(min(len(low_df), 3))
    for i, (_, r) in enumerate(low_df.iterrows()):
        with low_cols[i % len(low_cols)]:
            st.error(f"""
            **📦 {r['商品名称']}（{r['品类']}）**
            \n供应商：{r['供应商名称']}
            \n仅剩：**{r['库存数量']:.0f}{r['单位']}**
            \n保质期剩余：{r['剩余保质期(天)']}天
            """)
st.divider()
# 图表区域（全量数据，不受筛选影响，看整体结构）
st.subheader("📊 整体库存结构分析（全量数据）")
# 统计预警分布
status_counts = df['预警标签'].value_counts().reindex(['🔴 紧急', '🟠 警告', '🟡 注意', '🟢 正常']).fillna(0)
if MATPLOTLIB_AVAILABLE:
    fig_status, ax_status = plt.subplots(figsize=(10, 3))
    bars = ax_status.bar(status_counts.index, status_counts.values, 
                         color=['#ff4757', '#ffa502', '#ffd32a', '#2ed573'])
    ax_status.set_title("商品临期状态分布")
    for bar, val in zip(bars, status_counts.values):
        ax_status.text(bar.get_x()+bar.get_width()/2, val+0.1, f'{int(val)}个', ha='center')
    st.pyplot(fig_status)
else:
    # 无matplotlib时用streamlit原生柱状图
    st.markdown("**商品临期状态分布**")
    st.bar_chart(status_counts)
fig_col1, fig_col2 = st.columns(2)
with fig_col1:
    st.markdown("**各品类库存数量占比/对比**")
    cat_stock = df.groupby('品类')['库存数量'].sum().sort_values(ascending=False)
    if MATPLOTLIB_AVAILABLE:
        fig1, ax1 = plt.subplots(figsize=(7,6))
        colors = ['#ff6b6b', '#feca57', '#48dbfb', '#1dd1a1', '#ff9ff3', '#54a0ff', '#5f27cd']
        wedges, texts, autotexts = ax1.pie(cat_stock.values, labels=cat_stock.index, autopct='%1.1f%%', 
                                           startangle=90, colors=colors[:len(cat_stock)])
        ax1.set_title("品类库存数量占比")
        plt.setp(autotexts, size=10, weight="bold")
        st.pyplot(fig1)
    else:
        # 原生图表直接显示柱状图
        st.bar_chart(cat_stock)
with fig_col2:
    if MATPLOTLIB_AVAILABLE:
        st.markdown("**各品类库存数量对比**")
        fig2, ax2 = plt.subplots(figsize=(8,6))
        bars = ax2.barh(cat_stock.index[::-1], cat_stock.values[::-1], color='#48dbfb')
        ax2.set_xlabel(f'库存数量（{main_unit}）')
        for bar, val in zip(bars, cat_stock.values[::-1]):
            ax2.text(val+max(cat_stock.values)*0.01, bar.get_y()+bar.get_height()/2, f'{val:.0f}{main_unit}', va='center')
        st.pyplot(fig2)
    else:
        st.markdown("**剩余保质期分布**")
        shelf_df = df[['商品名称', '剩余保质期(天)']].set_index('商品名称').sort_values('剩余保质期(天)')
        st.bar_chart(shelf_df)
# 新增供应商库存统计
if len(df['供应商名称'].unique()) > 1:
    st.markdown("**各供应商库存分布**")
    sup_stock = df.groupby('供应商名称')['库存数量'].sum().sort_values(ascending=False)
    if MATPLOTLIB_AVAILABLE:
        fig3, ax3 = plt.subplots(figsize=(10,4))
        bars = ax3.bar(sup_stock.index, sup_stock.values, color='#00d2d3')
        ax3.set_ylabel(f'库存数量（{main_unit}）')
        for bar, val in zip(bars, sup_stock.values):
            ax3.text(bar.get_x()+bar.get_width()/2, val+max(sup_stock.values)*0.01, f'{val:.0f}{main_unit}', ha='center')
        plt.xticks(rotation=30, ha='right')
        st.pyplot(fig3)
    else:
        st.bar_chart(sup_stock)
st.divider()
# 补货建议：动态根据数据生成
st.subheader("📋 今日库存处理建议（智能生成）")
suggestions = []
# 临期处理建议
if urgent_count + warn_count > 0:
    suggestions.append("### 🔴 今日紧急处理")
    urgent_names = warn_df[warn_df['剩余保质期(天)']<1]['商品名称'].tolist()
    if urgent_names:
        suggestions.append(f"- **必须今日处理**：{', '.join(urgent_names)}，建议降价30%-50%、满赠、搭售或者加工处理，避免全损")
    warn3_names = warn_df[(warn_df['剩余保质期(天)']>=1)&(warn_df['剩余保质期(天)']<=3)]['商品名称'].tolist()
    if warn3_names:
        suggestions.append(f"- **3天内到期**：{', '.join(warn3_names)}，移到进门显眼位置做堆头销售，可组合做「新鲜菜包」优惠")
    suggestions.append("- 临期叶菜类建议傍晚后打折出清，不要留到第二天")
# 补货建议
if low_stock_count > 0:
    suggestions.append("\n### 🟡 补货提醒")
    low_by_supplier = low_df.groupby('供应商名称')['商品名称'].apply(list).to_dict()
    for sup, items in low_by_supplier.items():
        suggestions.append(f"- **{sup}**：{', '.join(items)} 库存不足，请及时补货")
# 正常库存建议
normal_count = len(df[df['预警标签']=='🟢 正常'])
if normal_count > 0:
    suggestions.append("\n### 🟢 库存健康提示")
    suggestions.append(f"- 当前共有 {normal_count} 个SKU库存状态健康，无需特殊处理")
    long_shelf = df[df['剩余保质期(天)']>15]
    if len(long_shelf) > 0:
        suggestions.append(f"- 长保商品（土豆、萝卜、苹果等根茎类/水果）剩余保质期均超过15天，库存充足，本周可不用补货")
st.markdown("\n".join(suggestions))
st.divider()
# 完整库存明细（筛选后的数据）
with st.expander("📋 查看当前筛选条件下的完整库存明细", expanded=False):
    show_cols = ['商品名称','品类','供应商名称','库存数量','单位','入库时间','剩余保质期(天)','预警标签']
    if '库存货值(元)' in df.columns:
        show_cols.append('库存货值(元)')
    sorted_df = filtered_df[show_cols].sort_values(['预警等级排序','剩余保质期(天)', '库存数量'])
    st.dataframe(sorted_df, use_container_width=True, hide_index=True)
    # 导出按钮
    col_export1, col_export2 = st.columns(2)
    csv = sorted_df.to_csv(index=False, encoding='utf-8-sig')
    col_export1.download_button(
        label="📥 导出当前筛选结果为CSV",
        data=csv,
        file_name=f"库存筛选结果_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        use_container_width=True
    )
    # 导出全量数据
    csv_all = df[show_cols].sort_values(['预警等级排序','剩余保质期(天)']).to_csv(index=False, encoding='utf-8-sig')
    col_export2.download_button(
        label="📥 导出全量库存数据为CSV",
        data=csv_all,
        file_name=f"全量库存_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        use_container_width=True
    )
st.divider()
# 销售记录查询
if len(sales_df) > 0:
    with st.expander("💰 查看销售出库记录", expanded=False):
        st.dataframe(sales_df.sort_values('时间', ascending=False), use_container_width=True, hide_index=True)
        # 导出销售记录
        sales_csv = sales_df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            label="📥 导出销售记录为CSV",
            data=sales_csv,
            file_name=f"销售记录_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
st.divider()
# 页脚统计
total_expiring_7d = len(df[df['剩余保质期(天)']<=7])
expiring_rate = total_expiring_7d / len(df) * 100 if len(df) >0 else 0
st.caption(f"📊 全店共 {len(df)} 个SKU，总库存 {df['库存数量'].sum():.0f}{main_unit}，7天内临期商品 {total_expiring_7d} 个，占比 {expiring_rate:.1f}% | 累计销售额 {sales_df['销售额'].sum():.1f} 元，累计毛利 {sales_df['毛利'].sum():.1f} 元 | 优化版看板 v3.1")
