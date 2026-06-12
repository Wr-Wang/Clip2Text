# Clip2Text — Windows 11 IIS 部署指南

> 适用环境：Windows 11 + IIS + Python 3.14 (FastAPI ASGI 应用)
> 部署架构：IIS 反向代理 → Uvicorn 进程

---

## 架构概览

```
互联网用户 (端口 80/443)
    │
    ▼
┌─────────────────────────────────┐
│  IIS                            │
│  + URL Rewrite (反向代理)        │
│  + ARR 3.0                      │
│  + SSL 终止 (可选)              │
└──────────┬──────────────────────┘
           │ 转发到 http://127.0.0.1:8000
           ▼
┌─────────────────────────────────┐
│  Uvicorn (注册为 Windows 服务)  │
│  绑定 127.0.0.1:8000 (仅本地)   │
│  FastAPI 应用运行中              │
└─────────────────────────────────┘
```

---

## 前置条件检查

**已确认的当前状态：**

| 项目 | 状态 |
|---|---|
| Python 3.14.5 | ✅ 已安装 |
| IIS Web Server Role | ✅ 已启用 |
| IIS 管理控制台 | ✅ 已启用 |
| IIS WebSocket | ✅ 已启用 |
| IIS ISAPI 扩展 | ✅ 已启用 |
| IIS CGI | ✅ 已启用 |
| URL Rewrite | ❌ 需要安装 |
| ARR 3.0 | ❌ 需要安装 |
| NSSM | ❌ 需要安装 |
| Visual C++ Redistributable | ❌ 需要检查 |

---

## 详细部署步骤

### 第 1 步：安装 IIS 扩展组件

#### 1.1 安装 URL Rewrite 模块

1. 访问 https://www.iis.net/downloads/microsoft/url-rewrite
2. 下载 `rewrite_x64_zh-CN.msi`
3. 以管理员身份运行安装（一直点"下一步"即可）
4. **验证**: 打开 IIS 管理器，在站点主页中看到 **"URL 重写"** 图标

#### 1.2 安装 ARR 3.0 (Application Request Routing)

1. 访问 https://www.iis.net/downloads/microsoft/application-request-routing
2. 下载 `arr_setup_x64.exe`
3. 以管理员身份运行安装
4. **验证**: IIS 管理器根节点下看到 **"Application Request Routing Cache"** 图标

#### 1.3 启用反向代理功能

1. 打开 IIS 管理器
2. 点击左侧 **根节点**（计算机名称）
3. 双击 **"Application Request Routing Cache"**
4. 在右侧操作面板点击 **"Server Proxy Settings"**
5. **勾选** "Enable proxy"
6. 点击右上角 "应用"

---

### 第 2 步：配置 Python 生产环境

#### 2.1 检查 VC++ 运行库

Whisper (torch) 和 EasyOCR 依赖 Visual C++ Redistributable。打开终端运行：

```powershell
# 检查是否已安装
wmic product where "name like '%%Visual C++%%'" get name
```

如果列表中没有 "Visual C++ Redistributable for Visual Studio 2015-2022"，请从微软官网下载安装。

#### 2.2 创建 Python 虚拟环境

```powershell
cd /d e:\Demo\Cursor\Clip2Text\backend
python -m venv .venv
```

#### 2.3 激活虚拟环境并安装依赖

```powershell
.venv\Scripts\activate
pip install -r requirements.txt
pip install uvicorn[standard]
```

> ⚠️ 注意：Python 3.14 较新，如 `torch` 或 `whisper` 安装失败，可尝试：
> ```powershell
> pip install torch --index-url https://download.pytorch.org/whl/cpu
> pip install openai-whisper --no-deps
> pip install -r requirements.txt
> ```
> 或降级到 Python 3.11-3.12。

#### 2.4 修改 main.py（去掉 reload 模式）

编辑 `backend\app\main.py`，将第 71 行：

```python
if __name__ == "__main__":
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
```

改为：

```python
if __name__ == "__main__":
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)
```

> 注意：实际运行时直接通过 `uvicorn` 命令启动，`if __name__ == "__main__"` 这段代码不会被 NSSM 服务用到。修改它是为了保持一致性。

#### 2.5 设置系统环境变量

右键"此电脑" → 属性 → 高级系统设置 → 环境变量 → 系统变量 → 新建：

| 变量名 | 变量值 |
|---|---|
| `HOST` | `127.0.0.1` |
| `PORT` | `8000` |
| `WHISPER_DEVICE` | `cpu` |
| `WHISPER_MODEL` | `base` |

---

### 第 3 步：配置 IIS 应用程序池和站点

以下命令请在 **PowerShell（管理员）** 中运行。

#### 3.1 创建应用程序池

```powershell
New-WebAppPool -Name "Clip2Text" -Force

# 禁用 .NET CLR（Python 不需要）
Set-ItemProperty -Path "IIS:\AppPools\Clip2Text" -Name "managedRuntimeVersion" -Value ""

# 始终运行，永不空闲停止
Set-ItemProperty -Path "IIS:\AppPools\Clip2Text" -Name "startMode" -Value "AlwaysRunning"
Set-ItemProperty -Path "IIS:\AppPools\Clip2Text" -Name "processModel.idleTimeout" -Value (New-TimeSpan -Minutes 0)

# 禁用定期自动回收
Set-ItemProperty -Path "IIS:\AppPools\Clip2Text" -Name "recycling.periodicRestart.time" -Value (New-TimeSpan -Hours 0)
```

#### 3.2 创建站点（两种方式选一种）

**方式 A：独立站点（推荐，使用端口 80）**

```powershell
# 注意：如果端口 80 已被"Default Web Site"占用，先停止它
Stop-WebSite "Default Web Site"

New-WebSite -Name "Clip2Text" `
  -PhysicalPath "e:\Demo\Cursor\Clip2Text\backend" `
  -ApplicationPool "Clip2Text" `
  -Port 80
```

**方式 B：作为默认站点的子应用**

```powershell
New-WebApplication -Name "Clip2Text" `
  -Site "Default Web Site" `
  -PhysicalPath "e:\Demo\Cursor\Clip2Text\backend" `
  -ApplicationPool "Clip2Text"
```

> 如果选择方式 B，访问地址变为 `http://localhost/Clip2Text/`，需要在 web.config 中调整反向代理规则（将 `/{R:1}` 改为 `/Clip2Text/{R:1}`）。

#### 3.3 创建 web.config

新建文件 `e:\Demo\Cursor\Clip2Text\backend\web.config`，写入以下内容：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <system.webServer>
        <rewrite>
            <rules>
                <clear />
                <rule name="ReverseProxyToClip2Text" stopProcessing="true">
                    <match url="(.*)" />
                    <action type="Rewrite" url="http://127.0.0.1:8000/{R:1}" />
                </rule>
            </rules>
            <outboundRules>
                <rule name="ReverseProxyChangeLocation" preCondition="IsRedirection">
                    <match serverVariable="RESPONSE_LOCATION" pattern="^http://127\.0\.0\.1:8000/(.*)" />
                    <action type="Rewrite" value="/{R:1}" />
                </rule>
                <preConditions>
                    <preCondition name="IsRedirection">
                        <add input="{RESPONSE_STATUS}" pattern="3\d\d" />
                    </preCondition>
                </preConditions>
            </outboundRules>
        </rewrite>
    </system.webServer>
</configuration>
```

---

### 第 4 步：将 Uvicorn 注册为 Windows 服务

使用 **NSSM (Non-Sucking Service Manager)** 管理 Uvicorn 进程，实现：
- 开机自启
- 崩溃自动重启
- 日志轮转

#### 4.1 安装 NSSM

从 https://nssm.cc/download 下载并解压，将 `win64/nssm.exe` 复制到 `C:\Windows\System32\`。

#### 4.2 创建日志目录

```powershell
mkdir e:\Demo\Cursor\Clip2Text\backend\logs -Force
```

#### 4.3 安装服务

```powershell
nssm install Clip2TextUvicorn
```

在弹出的 GUI 窗口中配置：

| 配置项 | 值 |
|---|---|
| **Application Path** | `e:\Demo\Cursor\Clip2Text\backend\.venv\Scripts\uvicorn.exe` |
| **Startup Directory** | `e:\Demo\Cursor\Clip2Text\backend` |
| **Arguments** | `app.main:app --host 127.0.0.1 --port 8000 --workers 1 --log-level info` |
| **Service name** | `Clip2TextUvicorn` |

```powershell
nssm install Clip2TextUvicorn
```
切换到 **I/O** 选项卡：

| 配置项 | 值 |
|---|---|
| **Output (stdout)** | `e:\Demo\Cursor\Clip2Text\backend\logs\access.log` |
| **Error (stderr)** | `e:\Demo\Cursor\Clip2Text\backend\logs\error.log` |
| **Rotate files** | ✅ 勾选 |
| **Rotation seconds** | `86400`（每天轮转） |
| **Rotation bytes** | `10485760`（10MB 轮转） |

点击 **"Install Service"**。

> 或者在命令行一次性配置（不弹窗）：
> ```powershell
> nssm install Clip2TextUvicorn "e:\Demo\Cursor\Clip2Text\backend\.venv\Scripts\uvicorn.exe"
> nssm set Clip2TextUvicorn AppDirectory "e:\Demo\Cursor\Clip2Text\backend"
> nssm set Clip2TextUvicorn AppParameters "app.main:app --host 127.0.0.1 --port 8000 --workers 1 --log-level info"
> nssm set Clip2TextUvicorn Start SERVICE_AUTO_START
> nssm set Clip2TextUvicorn AppStdout "e:\Demo\Cursor\Clip2Text\backend\logs\access.log"
> nssm set Clip2TextUvicorn AppStderr "e:\Demo\Cursor\Clip2Text\backend\logs\error.log"
> nssm set Clip2TextUvicorn AppRotateFiles 1
> nssm set Clip2TextUvicorn AppRotateSeconds 86400
> nssm set Clip2TextUvicorn AppRotateBytes 10485760
> nssm set Clip2TextUvicorn AppRestartDelay 5000
> ```

#### 4.4 启动服务

```powershell
nssm start Clip2TextUvicorn
```

#### 4.5 验证服务状态

```powershell
# 检查服务是否运行
nssm status Clip2TextUvicorn

# 确认端口监听
netstat -an | findstr ":8000"

# 检查 uvicorn 进程
tasklist | findstr uvicorn
```

---

### 第 5 步：设置目录权限

IIS 应用程序池以虚拟身份运行，需要对数据目录有写入权限。

#### 5.1 数据目录权限

在 PowerShell（管理员）中运行：

```powershell
# 授予 IIS_IUSRS 对 data 目录的完全控制权（最简单的方案）
icacls "e:\Demo\Cursor\Clip2Text\data" /grant "BUILTIN\IIS_IUSRS:(OI)(CI)M" /T
```

或者精确到指定应用程序池：

```powershell
# 针对特定应用程序池标识授权
icacls "e:\Demo\Cursor\Clip2Text\data" /grant "IIS AppPool\Clip2Text:(OI)(CI)M" /T
```

#### 5.2 模型缓存目录权限

Whisper 和 EasyOCR 首次运行时会下载模型文件（~1GB），需要写入权限：

```powershell
# 方法 A：授予 AppPool 对用户缓存的访问权
icacls "%USERPROFILE%\.cache\whisper" /grant "BUILTIN\IIS_IUSRS:(OI)(CI)M" /T 2>nul
icacls "%USERPROFILE%\.EasyOCR\model" /grant "BUILTIN\IIS_IUSRS:(OI)(CI)M" /T 2>nul

# 方法 B（推荐）：将缓存目录重定向到 data 目录下
# 新建目录
mkdir e:\Demo\Cursor\Clip2Text\data\models\whisper -Force
mkdir e:\Demo\Cursor\Clip2Text\data\models\easyocr -Force

# 设置系统环境变量（右键 此电脑 → 属性 → 高级系统设置 → 环境变量）
# 新建系统变量：
#   WHISPER_CACHE_DIR = e:\Demo\Cursor\Clip2Text\data\models\whisper
#   EASYOCR_MODULE_PATH = e:\Demo\Cursor\Clip2Text\data\models\easyocr
```

---

### 第 6 步：验证部署

#### 6.1 测试 Uvicorn 直连

```powershell
# 用 curl 测试后端直连（跳过 IIS）
curl http://127.0.0.1:8000/api/health
```

期望返回：
```json
{"name":"Clip2Text","status":"ok","version":"0.3.0","slogan":"粘贴链接，即得文案"}
```

#### 6.2 测试 IIS 反向代理

```powershell
# 通过 IIS 访问
curl http://localhost/api/health
```

期望返回与上面相同的结果。

#### 6.3 浏览器验证

1. 打开浏览器访问 `http://localhost`
2. 页面应正常加载（Bootstrap 样式从 CDN 加载，需要互联网连接）
3. 尝试粘贴一条视频分享文本并提交任务

#### 6.4 检查日志

```powershell
# IIS 日志
Get-Content "C:\inetpub\logs\LogFiles\W3SVC1\u_ex*.log" -Tail 10

# Uvicorn 日志
Get-Content "e:\Demo\Cursor\Clip2Text\backend\logs\access.log" -Tail 10
Get-Content "e:\Demo\Cursor\Clip2Text\backend\logs\error.log" -Tail 10
```

---

## 常见问题排查

### 502.3 - Bad Gateway

**原因**: IIS 无法连接到 Uvicorn 后端。

**排查步骤**：
1. 确认 Uvicorn 服务在运行：`nssm status Clip2TextUvicorn`
2. 确认端口监听：`netstat -an | findstr ":8000"`
3. 确认 ARR 代理已启用：IIS 根节点 → Application Request Routing Cache → Server Proxy Settings → Enable proxy
4. 检查是否有防火墙阻止 127.0.0.1:8000（本地回环通常不会被阻止）

### 404 - Not Found

**原因**: URL 转发路径不匹配。

**排查步骤**：
1. 确认 web.config 中 Rewrite URL 路径为 `http://127.0.0.1:8000/{R:1}`
2. 如果用子路径部署，`{R:1}` 需要替换为包含子路径的规则

### 500 - Internal Server Error

**原因**: Python 后端报错。

**排查步骤**：
1. 查看 Uvicorn 错误日志：`Get-Content "logs\error.log" -Tail 20`
2. 独立运行测试：`.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000` 观察控制台输出

### 403 - Forbidden

**原因**: 目录权限不足。

**排查步骤**：
1. 确认 data 目录权限：`icacls "e:\Demo\Cursor\Clip2Text\data"`
2. 确认 IIS_IUSRS 或 AppPool 标识有写入权限

---

## 后续可选优化

- **HTTPS**：使用 `win-acme` 工具申请 Let's Encrypt 免费证书
- **任务持久化**：修改 `task_manager.py`，将内存字典改为 SQLite 或 JSON 文件存储
- **超时调整**：ARR 代理默认转发超时 120 秒，可在 Server Proxy Settings 中加大
- **内存限制**：Whisper base 模型大约占用 1GB 内存，确保系统有足够内存

---

## 参考链接

| 组件 | 下载地址 |
|---|---|
| URL Rewrite | https://www.iis.net/downloads/microsoft/url-rewrite |
| ARR 3.0 | https://www.iis.net/downloads/microsoft/application-request-routing |
| NSSM | https://nssm.cc/download |
| Visual C++ Redistributable | https://aka.ms/vs/17/release/vc_redist.x64.exe |
| Python | https://www.python.org/downloads/ |
| win-acme (HTTPS) | https://www.win-acme.com/ |
