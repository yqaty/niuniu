# Queens Puzzle Solver

抖音小程序 "Queens" 棋盘游戏自动求解器。上传游戏截图，自动识别棋盘、求解、返回标注答案的图片。

## 规则

- N×N 棋盘，每个格子属于一种颜色，共 N 种颜色
- 放置 N 头牛，要求：
  - 每行恰好一头
  - 每列恰好一头
  - 任意两头牛不相邻（八方向）
  - 每种颜色区域恰好一头

## 技术栈

| 模块 | 技术 |
|------|------|
| 图像识别 | Pillow + NumPy + scikit-learn (KMeans) |
| 约束求解 | Google OR-Tools CP-SAT |
| API 服务 | FastAPI + Uvicorn |
| 前端页面 | 内嵌 HTML（手机浏览器直接用） |

## 项目结构

```
niuniu/
├── app.py              # FastAPI 服务入口，含网页前端
├── recognizer.py       # 图像识别：截图 → N×N 颜色矩阵
├── solver.py           # OR-Tools CP-SAT 约束求解
├── renderer.py         # 在原图上标注答案
├── requirements.txt    # Python 依赖
└── README.md
```

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务
uvicorn app:app --host 0.0.0.0 --port 8080
```

## 使用方式

### 方式一：网页端

浏览器打开 `http://<服务器IP>:8080`，上传截图，点击求解。

### 方式二：API 调用

```bash
curl -F "file=@screenshot.png" http://<服务器IP>:8080/solve -o answer.jpg
```

可选参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `fmt` | `jpeg` | 返回格式：`jpeg`（体积小）或 `png`（无损） |
| `quality` | `75` | JPEG 质量 10-100 |

### 方式三：iOS 快捷指令

无需安装 App，截图后通过分享菜单一键求解。

**创建步骤：**

1. 打开 iPhone **"快捷指令"** App → 点 **"+"** 新建
2. 改名为 **"牛牛秒解"**，点名称旁 **"v"** → 打开 **"在共享表单中显示"** → 类型选 **"图像"**
3. 添加动作 **"获取URL内容"**：
   - URL：`http://<服务器IP>:8080/solve`
   - 方法：`POST`
   - 请求体：`表单`
   - 添加字段 → 类型 `文件`，键 `file`，值选 `快捷指令输入`
4. 添加动作 **"快速查看"**

**使用：** 截屏 → 点缩略图 → 分享 → 选"牛牛秒解" → 答案弹出。

> 注意：无 HTTPS 时需在"获取URL内容"高级选项中开启"允许不安全的 HTTP 连接"。

## 处理流程

```
截图 → 定位棋盘区域 → 检测网格线确定 N
     → 采样格子颜色 → KMeans 聚类为 N 种
     → OR-Tools CP-SAT 约束求解
     → 在原图上画标记 → 返回答案图片
```

## 性能

| 棋盘 | 识别 | 求解 | 总耗时 |
|------|------|------|--------|
| 9×9  | ~200ms | ~5ms | ~200ms |
| 10×10 | ~220ms | ~11ms | ~240ms |
