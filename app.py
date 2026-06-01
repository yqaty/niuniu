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

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import Response, JSONResponse, HTMLResponse
from PIL import Image

import recognizer
import solver
import renderer

app = FastAPI(title="Queens Puzzle Solver", version="1.0.0")

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

<script>
const fileInput = document.getElementById('fileInput');
const uploadArea = document.getElementById('uploadArea');
const preview = document.getElementById('preview');
const solveBtn = document.getElementById('solveBtn');
const status = document.getElementById('status');
const result = document.getElementById('result');
let selectedFile = null;

fileInput.addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (!file) return;
  selectedFile = file;
  solveBtn.disabled = false;
  result.innerHTML = '';
  status.textContent = '';
  // 预览
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
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def index():
    """手机友好的上传页面"""
    return INDEX_HTML


@app.post("/solve")
async def solve_puzzle(file: UploadFile = File(...)):
    """
    接收游戏截图，识别并求解 Queens 棋盘，返回标注答案的图片。
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

    # 输出 PNG
    buf = io.BytesIO()
    result_img.save(buf, format="PNG")
    buf.seek(0)

    return Response(content=buf.getvalue(), media_type="image/png")


@app.get("/health")
async def health():
    return {"status": "ok"}
