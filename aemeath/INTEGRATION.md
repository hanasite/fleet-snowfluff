# 集成爱弥斯 (Aemeath)

飞行雪绒可以直接嵌入爱弥斯的 HTTP 服务器（端口 9527），无需额外启动中继。

## 方式一：独立运行（推荐起步）

`python server.py` 独立启动，手机浏览器访问 `http://电脑IP:19877`。

爱弥斯的右键菜单或托盘可以加一个快捷入口：

### 在爱弥斯中添加菜单项

修改 `src-tauri/src/webui.rs`（如果没有则新建），加入启动飞行雪绒的逻辑：

```rust
// src-tauri/src/webui.rs +fleet-snowfluff 集成
pub fn launch_fleet_snowfluff() {
    let script_path = format!(
        r#"{}\fleet-snowfluff\server.py"#,
        std::env::var("USERPROFILE").unwrap_or_default()
    );
    let exists = std::path::Path::new(&script_path).exists();
    if !exists {
        // 如果是第一版运行，自动 clone
        // 这个 fallback 可以让用户不需要手动下载
        return;
    }
    // 检测端口 19877 是否已运行
    // 未运行则启动 pythonw server.py --no-browser
    // 打开浏览器 http://127.0.0.1:19877
}
```

然后在 `tray.rs` 中加一个菜单项 `📱 飞行雪绒`。

## 方式二：嵌入 Aemeath 服务器（进阶）

直接把飞行雪绒的 WebSocket/SSE + 静态文件嵌入爱弥斯的 `http.rs`：

```rust
// http.rs 中添加
use axum::response::Html;
use tower-http::services::ServeDir;

// 路由中注册
.route("/fleet/*path", get(serve_fleet_static))
.route("/fleet/api/messages/...", get(fleet_messages))

async fn serve_fleet_static(Path(path): Path<String>) -> Html<String> {
    let html = std::fs::read_to_string(
        format!("{}/.claude/fleet-snowfluff/templates/index.html",
            std::env::var("USERPROFILE").unwrap_or_default())
    ).unwrap_or_default();
    Html(html)
}
```

这样爱弥斯的 `:9527` 端口同时提供飞行雪绒的 Web 页面，手机直接访问 `http://电脑IP:9527/fleet` 即可。

## 架构对比

```
独立运行:
  手机 → :19877 (server.py) → JSONL 文件读取

嵌入爱弥斯:
  手机 → :9527 (http.rs) → JSONL 文件读取
```
