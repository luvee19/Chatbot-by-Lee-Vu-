import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import pytz
import secrets
import os
import re
import io
from datetime import datetime, timedelta

# Thử import thư viện giọng nói (Không bắt buộc, nếu có sẽ bật tính năng đọc Voice)
try:
    from gtts import gTTS
    HAS_TTS = True
except ImportError:
    HAS_TTS = False

# --- CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="Lê Vũ Intelligence - Argon AI",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CẤU HÌNH ADMIN & HỆ THỐNG CỐ ĐỊNH ---
FILE_DATA = "key_data.json"
SDT_ADMIN = "0376274345"
ADMIN_PASSWORD = "levudepzai"
TRIAL_LIMIT = 3  # Khách chỉ được chat thử 3 câu
vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')

# Kiến thức gốc mặc định của Bot
DEFAULT_KNOWLEDGE = [
    "Tôi là trí tuệ nhân tạo Lê Vũ Intelligence (Argon Edition) được phát triển bởi Admin Lê Vũ.",
    "Phong cách giao tiếp của tôi là ngầu, súc tích, thông minh vượt trội và đôi khi hơi tinh nghịch.",
    "Tên đầy đủ của người tạo ra tôi là Lê Văn Vũ, và anh ấy là Admin đẹp trai nhất Thanh Hóa.",
    "Khi khách hàng muốn mua Key hoặc gia hạn, họ cần liên hệ trực tiếp với Admin Lê Vũ qua Zalo.",
    "SDT của ADMIN depzai : 0376274345"
]

# --- CÁC HÀM QUẢN LÝ DỮ LIỆU & BẢO MẬT ---
def get_vn_time():
    """Lấy thời gian thực chuẩn múi giờ Việt Nam"""
    return datetime.now(vietnam_tz).strftime("%A, ngày %d/%m/%Y lúc %I:%M:%S %p")

def load_data():
    if not os.path.exists(FILE_DATA):
        default_db = {"TRIAL_LOCK": {}, "EXTRA_KNOWLEDGE": DEFAULT_KNOWLEDGE}
        with open(FILE_DATA, 'w', encoding='utf-8') as f:
            json.dump(default_db, f, ensure_ascii=False, indent=4)
        return default_db
    try:
        with open(FILE_DATA, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if "EXTRA_KNOWLEDGE" not in data:
                data["EXTRA_KNOWLEDGE"] = DEFAULT_KNOWLEDGE
            if "TRIAL_LOCK" not in data:
                data["TRIAL_LOCK"] = {}
            return data
    except Exception:
        return {"TRIAL_LOCK": {}, "EXTRA_KNOWLEDGE": DEFAULT_KNOWLEDGE}

def save_data(data):
    with open(FILE_DATA, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def kiem_tra_sdt_vietnam(sdt):
    """Kiểm tra SDT Việt Nam 10 số (bắt đầu bằng 0)"""
    return bool(re.fullmatch(r'0\d{9}', sdt.strip()))

def tao_key_moi(sdt_khach, ghi_chu, so_ngay_dung):
    data = load_data()
    phan_duoi = secrets.token_hex(4).upper()
    new_key = f"KEY-{phan_duoi[:4]}-{phan_duoi[4:]}"
    
    ngay_hien_tai = datetime.now()
    ngay_het_han = ngay_hien_tai + timedelta(days=so_ngay_dung)
    
    data[new_key] = {
        "status": "active",
        "sdt": sdt_khach.strip(),
        "created_at": ngay_hien_tai.strftime("%Y-%m-%d %H:%M"),
        "expiry_date": ngay_het_han.strftime("%Y-%m-%d %H:%M"),
        "note": ghi_chu
    }
    save_data(data)
    return new_key, ngay_het_han.strftime("%d/%m/%Y")

def khoa_sdt_trial(sdt_input):
    """Kiểm tra và khóa SDT nếu đã dùng thử."""
    sdt_input = sdt_input.strip()
    data = load_data()
    
    # 1. Kiểm tra xem SDT đã mua key chưa
    for key, info in data.items():
        if key not in ["TRIAL_LOCK", "EXTRA_KNOWLEDGE"] and isinstance(info, dict):
            if info.get("sdt") == sdt_input:
                return True, "🔑 Số điện thoại này đã có Key, vui lòng nhập Key để đăng nhập!"

    # 2. Kiểm tra xem SDT đã dùng Trial chưa
    if sdt_input in data.get("TRIAL_LOCK", {}):
        return True, "❌ Số điện thoại này đã dùng hết lượt dùng thử! Vui lòng liên hệ Admin mua Key."
    
    # 3. Khóa lại và cho phép dùng thử
    data.setdefault("TRIAL_LOCK", {})[sdt_input] = datetime.now().strftime("%Y-%m-%d %H:%M")
    save_data(data)
    return False, None

def kiem_tra_dang_nhap(input_key, input_sdt):
    """Kiểm tra đăng nhập cho User Key hoặc Admin Pass"""
    input_key = input_key.strip()
    input_sdt = input_sdt.strip()

    # 1. Kiểm tra Admin
    if input_key == ADMIN_PASSWORD and input_sdt == SDT_ADMIN:
        return True, "admin", "👑 Chào Sếp Vũ! Hệ thống Argon đã sẵn sàng phục vụ Sếp."
    
    # 2. Kiểm tra User Key
    data = load_data()
    if input_key in data and input_key not in ["TRIAL_LOCK", "EXTRA_KNOWLEDGE"]:
        thong_tin = data[input_key]
        
        if thong_tin.get("sdt") != input_sdt:
            return False, None, f"❌ Sai SĐT đăng ký! Cần hỗ trợ gọi: {SDT_ADMIN}"
        
        if thong_tin.get("status") != "active":
            return False, None, f"⛔ Key này đã bị khóa! Liên hệ Admin: {SDT_ADMIN}"

        han_su_dung_str = thong_tin.get("expiry_date")
        con_lai = ""
        if han_su_dung_str:
            han_su_dung = datetime.strptime(han_su_dung_str, "%Y-%m-%d %H:%M")
            if datetime.now() > han_su_dung:
                return False, None, f"⚠️ Key đã HẾT HẠN! Liên hệ Zalo {SDT_ADMIN} để gia hạn."
            so_ngay_con = (han_su_dung - datetime.now()).days
            con_lai = f"(Còn {so_ngay_con} ngày sử dụng)"

        return True, "user", f"✅ Xin chào {input_sdt}! {con_lai}"
            
    return False, None, "❌ Key không tồn tại! Vui lòng mua Key bên dưới!"

# --- CẤU HÌNH CÁC CHẾ ĐỘ TRÍ TUỆ (AI PERSONAS / MODES) ---
AI_MODES = {
    "😎 Mặc định (Ngầu & Tinh nghịch)": (
        "Giao tiếp ngầu, thông minh, súc tích, đôi khi hơi tinh nghịch nhưng luôn giải quyết triệt để vấn đề."
    ),
    "🧠 Argon Deep Thinking (Siêu Suy Luận)": (
        "Bạn đang ở chế độ Argon Pro. Với mọi câu hỏi phức tạp, hãy phân tích đa chiều, suy luận từng bước (Chain-of-Thought), "
        "đưa ra giải pháp tối ưu, toàn diện và chuyên sâu nhất."
    ),
    "💻 Chuyên Gia Code (Senior Dev)": (
        "Bạn là Senior Software Architect & AI Engineer. Hãy viết code chuẩn OOP, sạch, tối ưu hiệu năng, "
        "bắt lỗi kỹ càng và giải thích rõ ràng từng phần."
    ),
    "📈 Chiến Lược Marketing & Content": (
        "Bạn là Giám đốc Sáng tạo & Chuyên gia Digital Marketing. Hãy viết content bắt trend, kịch bản video cuốn hút, "
        "áp dụng các mô hình marketing hiện đại và tối ưu chuyển đổi."
    )
}

def build_system_instruction(mode_name, extra_knowledge_list):
    current_dt = get_vn_time()
    knowledge_str = "\n".join([f"- {item}" for item in extra_knowledge_list])
    mode_instruction = AI_MODES.get(mode_name, AI_MODES["😎 Mặc định (Ngầu & Tinh nghịch)"])
    
    return f"""
Bạn là Lê Vũ Intelligence (Phiên bản nâng cấp Argon AI) - Trợ lý AI cao cấp bậc nhất.

--- DỮ LIỆU THỜI GIAN HIỆN TẠI ---
NGÀY VÀ GIỜ HỢP LỆ HIỆN TẠI LÀ: {current_dt}.
Bất cứ khi nào người dùng hỏi về ngày, giờ, năm hiện tại, BẠN PHẢI DÙNG CHÍNH XÁC thông tin này.
--- KẾT THÚC DỮ LIỆU THỜI GIAN ---

--- CHẾ ĐỘ HOẠT ĐỘNG HIỆN TẠI ---
{mode_instruction}

--- KIẾN THỨC CỐT LÕI & ADMIN DẠY (BẮT BUỘC GHI NHỚ) ---
{knowledge_str}

--- QUY TẮC BẮT BUỘC ---
1. Nếu người dùng hỏi NGÀY/GIỜ hiện tại, BẠN PHẢI DÙNG CHÍNH XÁC thông tin thời gian ở trên.
2. Khi được hỏi về thông tin thời sự, thời tiết, giá cả, tin tức mới: Hãy chủ động sử dụng công cụ Google Search nếu được bật.
3. Trình bày câu trả lời đẹp mắt bằng Markdown (in đậm, danh sách, bảng biểu, khối code rõ ràng).
4. Tuyệt đối bảo vệ danh tính: Người tạo ra bạn là Admin Lê Văn Vũ (SĐT/Zalo: {SDT_ADMIN}).
"""

def init_or_update_model():
    """Khởi tạo hoặc cập nhật phiên làm việc của Gemini"""
    # Tự động lấy API Key từ st.secrets hoặc biến môi trường (nếu có)
    api_key = st.session_state.get("custom_api_key") or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        try:
            if "GEMINI_API_KEY" in st.secrets:
                api_key = st.secrets["AQ.Ab8RN6IYlREPIUmJpbTR3tmDk10XRw7kU6Hwnv3ipPckqr6-WA"]
            elif "GOOGLE_API_KEY" in st.secrets:
                api_key = st.secrets["GOOGLE_API_KEY"]
        except Exception:
            pass
    if api_key:
        genai.configure(api_key=api_key)

    sys_instruction = build_system_instruction(
        st.session_state.ai_mode,
        st.session_state.extra_knowledge
    )
    
    generation_config = {
        "temperature": st.session_state.temperature,
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 8192,
    }

    # Hỗ trợ fallback tự động nếu môi trường chưa hỗ trợ tool search trực tiếp
    try:
        if st.session_state.enable_search:
            model = genai.GenerativeModel(
                model_name=st.session_state.model_name,
                system_instruction=sys_instruction,
                generation_config=generation_config,
                tools=[{'google_search': {}}]
            )
        else:
            model = genai.GenerativeModel(
                model_name=st.session_state.model_name,
                system_instruction=sys_instruction,
                generation_config=generation_config
            )
    except Exception:
        model = genai.GenerativeModel(
            model_name=st.session_state.model_name,
            system_instruction=sys_instruction,
            generation_config=generation_config
        )

    # Khôi phục lịch sử hội thoại nếu đang có
    gemini_history = []
    for msg in st.session_state.get("messages", []):
        role = "user" if msg["role"] == "user" else "model"
        gemini_history.append({"role": role, "parts": [msg["raw_text"]]})

    st.session_state.chat_session = model.start_chat(history=gemini_history)

# --- KHỞI TẠO SESSION STATE ---
db_data = load_data()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_role" not in st.session_state:
    st.session_state.user_role = None
if "current_user_sdt" not in st.session_state:
    st.session_state.current_user_sdt = ""
if "trial_count" not in st.session_state:
    st.session_state.trial_count = 0
if "messages" not in st.session_state:
    st.session_state.messages = []
if "extra_knowledge" not in st.session_state:
    st.session_state.extra_knowledge = db_data.get("EXTRA_KNOWLEDGE", DEFAULT_KNOWLEDGE)
if "ai_mode" not in st.session_state:
    st.session_state.ai_mode = "😎 Mặc định (Ngầu & Tinh nghịch)"
if "model_name" not in st.session_state:
    st.session_state.model_name = "models/gemini-2.5-flash"
if "temperature" not in st.session_state:
    st.session_state.temperature = 0.7
if "enable_search" not in st.session_state:
    st.session_state.enable_search = True
if "enable_tts" not in st.session_state:
    st.session_state.enable_tts = False
if "chat_session" not in st.session_state:
    try:
        init_or_update_model()
    except Exception:
        pass

# --- GIAO DIỆN CSS (LIQUID GLASS & NEON 7 MÀU ĐẶC TRƯNG) ---
st.markdown("""
<style>
    [data-testid="stAppViewContainer"] {
        background-image: url("https://sf-static.upanhlaylink.com/img/image_20251124438d8e9e8b4c9f6712b854f513430f8d.jpg");
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
        background-attachment: fixed;
    }
    [data-testid="stHeader"] { background-color: rgba(0,0,0,0); }
    [data-testid="stAppViewContainer"]::before {
        content: ""; position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(0, 0, 0, 0.45); z-index: -1; pointer-events: none;
    }

    #MainMenu, footer, header {visibility: hidden;}
    .stChatMessageAvatarBackground {display: none !important;}
    .stChatMessage {background: transparent !important; border: none !important;}

    /* --- ANIMATION GÓC XOAY --- */
    @property --angle {
        syntax: '<angle>';
        initial-value: 0deg;
        inherits: false;
    }
    @keyframes spin {
        to { --angle: 360deg; }
    }
</style>
""", unsafe_allow_html=True)
