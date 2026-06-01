"""
FastAPI 后端服务：接收游戏截图，识别棋盘，求解，返回标注答案的图片。

POST /solve
  - 接收 multipart/form-data，字段名 file
  - 返回 image/png 标注了答案的图片
  - 错误返回 JSON {"error": "..."}

GET /
  - 手机友好的上传页面
"""

import io
import time
import base64

from fastapi import FastAPI, File, UploadFile, Query
from fastapi.responses import Response, JSONResponse, HTMLResponse
from PIL import Image

import recognizer
import solver
import renderer

app = FastAPI(title="Queens Puzzle Solver", version="1.0.0")


# ---------------------------------------------------------------------------
# CORS —— 允许快捷指令 / 浏览器跨域调用
# ---------------------------------------------------------------------------
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# 最新求解结果缓存（内存）
# ---------------------------------------------------------------------------
import threading
from datetime import datetime

_latest_lock = threading.Lock()
_latest_result: dict | None = None  # {"image_b64": str, "n": int, "time": str, "solution": list}

INDEX_HTML = """
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<title>Queens Solver</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, sans-serif;
    background: #f5f5f5;
    min-height: 100vh;
    display: flex; flex-direction: column; align-items: center;
    padding: 20px 16px;
    color: #333;
  }
  h1 { font-size: 22px; margin-bottom: 16px; }
  .upload-area {
    width: 100%; max-width: 400px;
    border: 2px dashed #aaa; border-radius: 12px;
    padding: 40px 20px; text-align: center;
    background: #fff; cursor: pointer;
    transition: border-color 0.2s;
  }
  .upload-area.active { border-color: #4a90d9; background: #f0f6ff; }
  .upload-area p { font-size: 16px; color: #666; }
  input[type=file] { display: none; }
  .btn {
    margin-top: 16px; padding: 12px 32px;
    font-size: 17px; border: none; border-radius: 8px;
    background: #4a90d9; color: #fff; cursor: pointer;
    width: 100%; max-width: 400px;
  }
  .btn:disabled { background: #aaa; cursor: not-allowed; }
  .status {
    margin-top: 12px; font-size: 14px; color: #888;
    min-height: 20px;
  }
  .result {
    margin-top: 16px; width: 100%; max-width: 400px; text-align: center;
  }
  .result img {
    max-width: 100%; border-radius: 8px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.15);
  }
  .error { color: #e44; font-weight: bold; }
  .preview { max-width: 100%; max-height: 200px; margin-top: 8px; border-radius: 8px; }
  .divider {
    width: 100%; max-width: 400px;
    border-top: 1px solid #ddd;
    margin: 24px 0 16px;
  }
  .section-title {
    font-size: 16px; font-weight: 600; color: #555;
    margin-bottom: 8px; width: 100%; max-width: 400px;
  }
  .latest-meta {
    font-size: 13px; color: #999; margin-bottom: 8px;
    width: 100%; max-width: 400px;
  }
  .latest-img {
    width: 100%; max-width: 400px; text-align: center;
  }
  .latest-img img {
    max-width: 100%; border-radius: 8px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.15);
  }
  .empty-hint { font-size: 14px; color: #bbb; padding: 20px 0; }
</style>
</head>
<body>
  <h1>Queens Puzzle Solver</h1>

  <div class="upload-area" id="uploadArea" onclick="fileInput.click()">
    <p>点击选择截图 / 拍照</p>
    <img id="preview" class="preview" style="display:none">
  </div>
  <input type="file" id="fileInput" accept="image/*">

  <button class="btn" id="solveBtn" disabled onclick="doSolve()">识别并求解</button>
  <div class="status" id="status"></div>
  <div class="result" id="result"></div>

  <div class="divider"></div>
  <div class="section-title">最新求解结果</div>
  <div class="latest-meta" id="latestMeta"></div>
  <div class="latest-img" id="latestImg">
    <span class="empty-hint">暂无求解记录</span>
  </div>

<script>
const fileInput = document.getElementById('fileInput');
const uploadArea = document.getElementById('uploadArea');
const preview = document.getElementById('preview');
const solveBtn = document.getElementById('solveBtn');
const status = document.getElementById('status');
const result = document.getElementById('result');
const latestMeta = document.getElementById('latestMeta');
const latestImg = document.getElementById('latestImg');
let selectedFile = null;
let lastLatestTime = '';

fileInput.addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (!file) return;
  selectedFile = file;
  solveBtn.disabled = false;
  result.innerHTML = '';
  status.textContent = '';
  const reader = new FileReader();
  reader.onload = (ev) => {
    preview.src = ev.target.result;
    preview.style.display = 'block';
    uploadArea.querySelector('p').textContent = file.name;
  };
  reader.readAsDataURL(file);
});

async function doSolve() {
  if (!selectedFile) return;
  solveBtn.disabled = true;
  status.textContent = '识别中...';
  status.className = 'status';
  result.innerHTML = '';

  const formData = new FormData();
  formData.append('file', selectedFile);

  try {
    const t0 = Date.now();
    const resp = await fetch('/solve', { method: 'POST', body: formData });
    const elapsed = ((Date.now() - t0) / 1000).toFixed(2);

    if (resp.ok) {
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      result.innerHTML = '<img src="' + url + '">';
      status.textContent = '求解完成 (' + elapsed + 's)';
      // 求解成功后立即刷新最新结果
      fetchLatest();
    } else {
      const err = await resp.json();
      status.textContent = err.error || '求解失败';
      status.className = 'status error';
    }
  } catch (e) {
    status.textContent = '网络错误: ' + e.message;
    status.className = 'status error';
  }
  solveBtn.disabled = false;
}

async function fetchLatest() {
  try {
    const resp = await fetch('/latest');
    if (!resp.ok) return;
    const data = await resp.json();
    if (!data || !data.image_b64) {
      latestMeta.textContent = '';
      latestImg.innerHTML = '<span class="empty-hint">暂无求解记录</span>';
      return;
    }
    // 只在有新结果时更新 DOM，避免闪烁
    if (data.time === lastLatestTime) return;
    lastLatestTime = data.time;

    latestMeta.textContent = data.n + 'x' + data.n
      + '  |  解: [' + data.solution.join(', ') + ']'
      + '  |  ' + data.time;
    latestImg.innerHTML = '<img src="data:image/jpeg;base64,' + data.image_b64 + '">';
  } catch (e) {
    // 静默失败
  }
}

// 页面加载时立即拉取一次，之后每 5 秒轮询
fetchLatest();
setInterval(fetchLatest, 5000);
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def index():
    """手机友好的上传页面"""
    return INDEX_HTML


@app.post("/solve")
async def solve_puzzle(
    file: UploadFile = File(...),
    fmt: str = Query("jpeg", description="返回格式: jpeg(小) 或 png(无损)"),
    quality: int = Query(75, ge=10, le=100, description="JPEG 质量 10-100"),
):
    """
    接收游戏截图，识别并求解 Queens 棋盘，返回标注答案的图片。

    快捷指令建议用默认参数 (jpeg, quality=75)，体积约 50-80KB，传输快。
    网页端如需高清可传 fmt=png。
    """
    t0 = time.time()

    # 读取上传图片
    try:
        contents = await file.read()
        img = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"error": f"无法读取图片: {e}"},
        )

    # 识别棋盘
    try:
        board_info = recognizer.recognize(img)
    except ValueError as e:
        return JSONResponse(
            status_code=422,
            content={"error": f"识别失败: {e}"},
        )

    t_recognize = time.time() - t0

    # 求解
    solution = solver.solve(board_info.n, board_info.grid)
    if solution is None:
        return JSONResponse(
            status_code=422,
            content={"error": "无法求解，请检查截图是否完整清晰"},
        )

    t_solve = time.time() - t0 - t_recognize

    # 渲染答案图片
    result_img = renderer.render(img, board_info, solution)

    t_total = time.time() - t0
    print(
        f"[solve] n={board_info.n}, "
        f"recognize={t_recognize:.3f}s, solve={t_solve:.3f}s, total={t_total:.3f}s"
    )

    # 缓存最新结果（JPEG 用于前端展示）
    cache_buf = io.BytesIO()
    result_img.save(cache_buf, format="JPEG", quality=75)
    cache_b64 = base64.b64encode(cache_buf.getvalue()).decode()
    with _latest_lock:
        global _latest_result
        _latest_result = {
            "image_b64": cache_b64,
            "n": board_info.n,
            "solution": solution,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    # 输出图片
    buf = io.BytesIO()
    if fmt.lower() == "png":
        result_img.save(buf, format="PNG")
        media_type = "image/png"
    else:
        result_img.save(buf, format="JPEG", quality=quality)
        media_type = "image/jpeg"
    buf.seek(0)

    return Response(content=buf.getvalue(), media_type=media_type)


@app.get("/latest")
async def latest():
    """返回最新一次求解的结果（JSON，含 base64 图片）"""
    with _latest_lock:
        if _latest_result is None:
            return JSONResponse(content=None)
        return JSONResponse(content=_latest_result)


@app.get("/health")
async def health():
    return {"status": "ok"}
