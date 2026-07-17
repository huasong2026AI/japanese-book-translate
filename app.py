import os
import json
import zipfile
import io
import pdfplumber
import requests
import streamlit as st

# ================= 开发者配置区域 =================
# 🔒 终极安全：Key 和卡密统统不写死，全部从 Streamlit 云端 Secrets 中安全读取
if "DEEPSEEK_API_KEY" in st.secrets:
    MY_OWN_DEEPSEEK_KEY = st.secrets["DEEPSEEK_API_KEY"]
else:
    MY_OWN_DEEPSEEK_KEY = "暂未配置云端KEY"

# 从云端安全读取当前有效的卡密列表（云端配置时用英文逗号分隔）
if "VALID_CARD_KEYS" in st.secrets:
    VALID_CARD_KEYS = [k.strip() for k in st.secrets["VALID_CARD_KEYS"].split(",")]
else:
    VALID_CARD_KEYS = []
# ==================================================

API_URL = "https://api.deepseek.com/v1/chat/completions"

# 设置页面属性
st.set_page_config(page_title="和风·日语多读绘本批翻大师", page_icon="🌸", layout="wide")

# ================= 👘 日式高级感和风 CSS 注入 =================
st.markdown("""
<style>
    /* 全局背景色调 - 优雅和纸白 */
    .stApp {
        background-color: #F9F6F0;
        color: #2C3E50;
        font-family: "Helvetica Neue", Arial, "Hiragino Kaku Gothic ProN", "Segoe UI", sans-serif;
    }
    
    /* 侧边栏样式定制 - 经典深靛蓝 */
    [data-testid="stSidebar"] {
        background-color: #1B365D !important;
        color: #FFFFFF !important;
    }
    
    /* 侧边栏里的所有文字颜色适配 */
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, [data-testid="stSidebar"] label {
        color: #EAEAEA !important;
    }
    
    /* 主标题设计 */
    .main-title {
        color: #1B365D;
        font-size: 2.8rem;
        font-weight: 700;
        border-bottom: 3px solid #E60012;
        padding-bottom: 10px;
        margin-bottom: 5px;
        letter-spacing: 2px;
    }
    
    .sub-title {
        color: #7F8C8D;
        font-size: 1.1rem;
        margin-bottom: 30px;
        font-style: italic;
    }
    
    /* 卡片区域美化 */
    .section-card {
        background-color: #FFFFFF;
        padding: 25px;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        border-left: 5px solid #1B365D;
        margin-bottom: 25px;
    }
    
    /* 朱红色核心按钮样式定制 */
    div.stButton > button:first-child {
        background-color: #E60012 !important;
        color: white !important;
        border: none !important;
        padding: 12px 24px !important;
        font-size: 1.1rem !important;
        font-weight: bold !important;
        border-radius: 4px !important;
        box-shadow: 0 4px 10px rgba(230, 0, 18, 0.3) !important;
        transition: all 0.3s ease !important;
        width: 100%;
    }
    
    div.stButton > button:first-child:hover {
        background-color: #C80010 !important;
        box-shadow: 0 6px 15px rgba(230, 0, 18, 0.5) !important;
        transform: translateY(-1px);
    }
</style>
""", unsafe_allow_html=True)

# 初始化 Session 状态用于缓存翻译结果
if "translated_files" not in st.session_state:
    st.session_state.translated_files = {}

def call_deepseek(api_key, prompt, text):
    """底层请求函数：强行采用 UTF-8 字节流发送数据，彻底杜绝 latin-1 报错"""
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "user", "content": f"{prompt}\n\n以下是待处理文本：\n{text}"}
        ],
        "temperature": 0.1
    }
    try:
        data_bytes = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        response = requests.post(API_URL, data=data_bytes, headers=headers)
        if response.status_code == 200:
            response.encoding = 'utf-8'
            return response.json()['choices'][0]['message']['content']
        else:
            err_msg = response.json().get("error", {}).get("message", "未知错误")
            raise Exception(f"API 报错: {err_msg}")
    except Exception as e:
        raise Exception(f"网络请求失败: {e}")

# --- 🏯 主界面头部设计 ---
st.markdown('<div class="main-title">🌸 日语多读绘本批量翻译大师</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">~ 智能剔除振假名注音干扰 · 还原纯净中日双语童趣对白 ~</div>', unsafe_allow_html=True)

# --- 🗻 侧边栏：权限与专属通道 ---
st.sidebar.markdown("## ⛩️ 门票与通道")
channel = st.sidebar.radio("请选择您的使用路线：", ["路线 A：自带 DeepSeek Key（完全免费）", "路线 B：免 Key 快速通道（付费/卡密）"])

final_api_key = None

if channel == "路线 A：自带 DeepSeek Key（完全免费）":
    st.sidebar.markdown("---")
    user_key = st.sidebar.text_input("请输入您的 DeepSeek API Key (sk-...):", type="password")
    st.sidebar.markdown("""
    <small style='color: #D1D1D1;'>
    💡 <b>安全承诺</b>：您的 Key 仅保存在当前浏览器的内存会话中，关闭网页即刻抹除，本站绝不收集和存储任何用户的私钥。
    </small>
    """, unsafe_allow_html=True)
    if user_key.strip():
        final_api_key = user_key.strip()
else:
    st.sidebar.markdown("---")
    card_key = st.sidebar.text_input("请输入激活卡密：", type="password")
    st.sidebar.markdown("🙋‍♂️ **没有 Key 和卡密？**")
    st.sidebar.markdown("为了保护隐私，本站不公开微信。如果您想体验内置额度，请点击下方按钮留下您的联系方式，作者看到后会使用微信小号主动联系您发放卡密！")
    
    # 🔗 已经无缝接入你生成的专属腾讯文档表单链接
    form_link = "https://docs.qq.com/form/page/DTW1TVUZMYnFLWlhX" 
    
    st.sidebar.markdown(f"""
    <a href="{form_link}" target="_blank">
        <button style="
            width:100%; 
            background-color:#E60012; 
            color:white; 
            border:none; 
            padding:10px; 
            border-radius:4px; 
            cursor:pointer;
            font-weight:bold;
            box-shadow: 0 4px 6px rgba(0,0,0,0.2);">
            ✍️ 点击填写留言与联系方式
        </button>
    </a>
    """, unsafe_allow_html=True)
    st.sidebar.markdown("<small style='color:#D1D1D1;'>💡 提示：提交后请耐心等待，作者通常会在 24 小时内完成审核并主动联系您。</small>", unsafe_allow_html=True)
        
    if card_key.strip() in VALID_CARD_KEYS:
        st.sidebar.success("✅ 卡密验证通过！已激活作者内置额度通道。")
        final_api_key = MY_OWN_DEEPSEEK_KEY
    elif card_key.strip():
        st.sidebar.error("❌ 无效的卡密，请重新输入或联系作者。")

# --- 📦 主界面业务逻辑 ---

# 第一步：文件上传卡片（用 <div class="section-card"> 将上传组件完整包裹起来）
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.subheader("📥 第一步：上传需要处理的 PDF 绘本")
uploaded_files = st.file_uploader(
    "从电脑选择一本或多本 PDF 绘本拖拽到下方（支持批量上传）", 
    type=["pdf"], 
    accept_multiple_files=True
)
st.markdown('</div>', unsafe_allow_html=True)

# 第二步：批量翻译卡片（确保 <div class="section-card"> 只在有文件上传成功时，才在 if 内部渲染包裹）
if uploaded_files:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.info(f"📁 已成功载入 {len(uploaded_files)} 个 PDF 文件。")
    st.subheader("🚀 第二步：开始批量流水线翻译")
    
    start_btn = st.button("🔥 点击开始批量处理")
    
    if start_btn:
        if not final_api_key or final_api_key == "暂未配置云端KEY":
            st.error("🔒 启动失败：请先在左侧栏配置您的【API Key】或填入有效的【激活卡密】！")
        else:
            # 清空上一轮缓存
            st.session_state.translated_files = {}
            
            for file_idx, file_obj in enumerate(uploaded_files):
                st.markdown(f"### 📖 正在处理 ({file_idx+1}/{len(uploaded_files)}): `{file_obj.name}`")
                
                try:
                    with pdfplumber.open(file_obj) as pdf:
                        total_pages = len(pdf.pages)
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        file_results = []
                        
                        for i, page in enumerate(pdf.pages):
                            page_num = i + 1
                            status_text.text(f"正在提取并分析第 {page_num}/{total_pages} 页...")
                            
                            raw_text = page.extract_text()
                            if not raw_text or not raw_text.strip():
                                progress_bar.progress(page_num / total_pages)
                                continue
                                
                            prompt = (
                                "你是一个精通中日双语的儿童绘本翻译专家。\n"
                                "输入的内容是从带有汉字注音（振假名）的日语绘本中直接提取出的文本。\n"
                                "由于提取原因，汉字头顶的微小假名可能混在了正文里（例如：友（とも）动词は，或者断行错乱）。\n"
                                "请你完成两件事：\n"
                                "1. 帮我理顺语序，剔除多余的注音干扰，还原出原本干净的日语正文。\n"
                                "2. 将其翻译成富有童趣、生动、符合中国儿童阅读习惯的中文。\n\n"
                                "请严格按照以下格式回复，不要带有任何其他解释：\n"
                                f"【第 {page_num} 页】\n"
                                "日语原文：[这里填写还原后的干净日语]\n"
                                "中文翻译：[这里填写翻译的中文]"
                            )
                            
                            try:
                                page_result = call_deepseek(final_api_key, prompt, raw_text)
                                file_results.append(page_result)
                            except Exception as page_err:
                                st.warning(f"⚠️ 第 {page_num} 页翻译失败: {page_err}")
                            
                            progress_bar.progress(page_num / total_pages)
                        
                        status_text.text(f"✨ `{file_obj.name}` 翻译处理完毕！")
                        
                        if file_results:
                            txt_filename = f"{os.path.splitext(file_obj.name)[0]}_翻译结果.txt"
                            st.session_state.translated_files[txt_filename] = "\n\n".join(file_results)
                            st.success(f"已就绪: `{txt_filename}`")
                            
                except Exception as pdf_err:
                    st.error(f"❌ 解析该 PDF 文件失败: {pdf_err}")
                st.markdown("---")
            
            st.balloons()
            st.success("🎉 所有上传的绘本已全部在云端流水线处理完毕！")
    st.markdown('</div>', unsafe_allow_html=True)

# 第三步：结果打包与下载卡片
if st.session_state.translated_files:
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("🎁 第三步：一键打包下载结果")
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for txt_name, txt_content in st.session_state.translated_files.items():
            zip_file.writestr(txt_name, txt_content.encode('utf-8'))
            
    zip_buffer.seek(0)
    
    st.download_button(
        label="📥 点击一键下载全部翻译结果 (ZIP压缩包)",
        data=zip_buffer,
        file_name="绘本批量翻译结果.zip",
        mime="application/zip",
        use_container_width=True
    )
    st.markdown('</div>', unsafe_allow_html=True)
