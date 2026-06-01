"""
答案渲染模块：在原始截图上标注牛的位置。

在每个解对应的格子中心画一个醒目的白色实心圆 + 深色边框。
"""

from PIL import Image, ImageDraw
from typing import List
from recognizer import BoardInfo


def render(
    img: Image.Image,
    board_info: BoardInfo,
    solution: List[int],
) -> Image.Image:
    """
    在原图上标注答案。

    Args:
        img: 原始截图
        board_info: 棋盘识别结果
        solution: 长度为 N 的列表，solution[i] = 第 i 行牛所在的列

    Returns:
        标注后的 PIL Image
    """
    result = img.copy().convert("RGB")
    draw = ImageDraw.Draw(result)

    n = board_info.n
    # 计算格子大小（取平均间距）
    grid_x = board_info.grid_x
    grid_y = board_info.grid_y
    avg_cell_w = (grid_x[-1] - grid_x[0]) / (len(grid_x) - 1)
    avg_cell_h = (grid_y[-1] - grid_y[0]) / (len(grid_y) - 1)
    radius = int(min(avg_cell_w, avg_cell_h) * 0.28)

    for row in range(n):
        col = solution[row]
        cx, cy = board_info.cell_centers[row][col]

        # 外圈：深灰边框
        border = max(2, radius // 8)
        draw.ellipse(
            [cx - radius - border, cy - radius - border,
             cx + radius + border, cy + radius + border],
            fill=(60, 60, 60),
        )
        # 内圈：白色实心
        draw.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            fill=(255, 255, 255),
        )

    return result
