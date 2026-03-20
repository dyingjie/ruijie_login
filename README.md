# ruijie_login

一个用于校园网锐捷 ePortal 认证的小工具。

它会直接调用 portal 的 API 完成登录，并在登录前先检查你是否已经在线，适合想用命令行或脚本完成校园网认证的用户。

## 适用场景

- 学校使用锐捷 ePortal 登录页
- 你能在浏览器里正常打开认证页面
- 当前 portal 不要求验证码

如果学校的登录流程强依赖验证码、短信验证，或额外的运营商交互账号，本项目不适用。

## 快速开始

### 1. 准备运行环境

项目要求：

- Python 3.8 或更高版本
- Windows 用户如果已经按仓库约定准备好 conda 环境，可直接使用 `run.bat` 和 `status.bat`

如果你已经按本仓库约定创建了 conda 环境 `ruijie`，可以直接运行批处理文件。

如果没有这个 conda 环境，也可以直接用 Python 运行：

```powershell
python -m ruijie_login
```

如果你想把命令安装到当前 Python 环境里，可以执行：

```powershell
python -m pip install -e .
```

安装后可使用：

```powershell
ruijie_login
```

### 2. 编辑 `config.json`

首次使用时，请先打开根目录下的 `config.json`，把里面的内容改成你自己的信息。

最重要的是 `portal_url`。它必须是浏览器地址栏里的完整认证页 URL，而不是单纯的学校域名。

推荐获取方式：

1. 连接校园网，打开学校的登录页。
2. 在浏览器地址栏中复制完整 URL。
3. 把这个完整 URL 粘贴到 `config.json` 的 `portal_url` 字段。

一个可参考的配置如下：

```json
{
  "portal_url": "http://example.com/eportal/index.jsp?...完整查询参数...",
  "username": "你的账号",
  "password": "你的密码",
  "service": "",
  "timeout_seconds": 20,
  "use_portal_prefix": false
}
```

各字段说明：

- `portal_url`: 必填。必须包含 `?` 后面的完整查询参数，否则程序无法登录。
- `username`: 必填。通常是学号、工号或学校分配的上网账号。
- `password`: 必填。你的校园网密码。
- `service`: 可选。不确定时可以先留空，程序会优先选择 portal 返回的默认服务。
- `timeout_seconds`: 可选。网络请求超时时间，默认 `20` 秒。
- `use_portal_prefix`: 可选。只有学校要求在账号前自动补前缀时才设为 `true`。

建议不要把包含真实账号密码的 `config.json` 提交到代码仓库或发给别人。

### 3. 执行登录

Windows 快速方式：

```bat
run.bat
```

通用方式：

```powershell
python -m ruijie_login
```

或：

```powershell
ruijie_login
```

程序默认执行 `login` 命令。常见输出包括：

- `当前已经在线，无需重复认证。`
- `认证成功。`

### 4. 查看当前状态

Windows 快速方式：

```bat
status.bat
```

通用方式：

```powershell
python -m ruijie_login status
```

如果已经在线，通常会看到类似输出：

```text
当前已在线。
userId: ...
userName: ...
userGroup: ...
```

## 常用命令

使用其他配置文件：

```powershell
python -m ruijie_login --config my-config.json
```

临时覆盖配置文件中的账号：

```powershell
python -m ruijie_login --username 你的账号 --password 你的密码
```

查询状态时指定配置文件：

```powershell
python -m ruijie_login --config my-config.json status
```

## 这个项目会帮你处理什么

- 登录前先检查当前是否已经在线
- `service` 留空时自动选择 portal 返回的默认服务
- `passwordEncrypt=true` 时自动按 portal 要求加密密码
- 学校要求账号前缀时，可通过 `use_portal_prefix` 配合 portal 返回值自动拼接

## 常见问题

### 提示 `portal_url 不是有效的 URL`

说明你填入的不是完整登录页地址。请重新从浏览器地址栏复制完整 URL。

### 提示 `portal_url 必须包含认证页完整查询参数`

说明你只填了登录页路径，没有填 `?` 后面的查询参数。这个项目依赖这些参数完成认证。

### `run.bat` 提示找不到 Python

`run.bat` 默认会查找：

```text
%USERPROFILE%\miniconda3\envs\ruijie\python.exe
```

如果你的 Python 不在这个位置，请直接使用：

```powershell
python -m ruijie_login
```

或者按自己的环境修改批处理文件。

## 限制

- 不同学校可能不兼容
