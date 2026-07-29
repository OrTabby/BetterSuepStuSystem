"""项目全局配置"""

# ── 学校系统 URL ──────────────────────────────────────────
CAS_BASE_URL = "https://ids.shiep.edu.cn/authserver"
CAS_LOGIN_URL = f"{CAS_BASE_URL}/login"
CAS_CAPTCHA_URL = f"{CAS_BASE_URL}/captcha"
CAS_SERVICE_URL = "http://jw.shiep.edu.cn/eams/login.action"

# 教务系统（强智科技）
EAMS_BASE_URL = "https://jw.shiep.edu.cn/eams"
EAMS_INDEX_URL = f"{EAMS_BASE_URL}/index.action"
COURSE_TABLE_DATA_URL = f"{EAMS_BASE_URL}/courseTableForStd!courseTable.action"
GRADE_DATA_URL = f"{EAMS_BASE_URL}/teach/grade/course/person!search.action"

# ── 本地缓存 ───────────────────────────────────────────────
DB_PATH = "data/cache.db"

# ── 代理设置 ───────────────────────────────────────────────
# VPN 连接后通过本地 SOCKS5 代理访问教务系统
USE_PROXY = True
PROXY_URL = "socks5://127.0.0.1:1080"

# ── VPN 配置（SHIEP-Pipeline 深信服 EasyConnect）─────────
VPN_BINARY = "SHIEP-Pipeline-v2.0.0-windows-x64.exe"
VPN_SERVER = "vpn.shiep.edu.cn"  # VPN 服务器地址
VPN_USER = ""                    # VPN 用户名（学号）

# 请求超时（秒）
REQUEST_TIMEOUT = 45
