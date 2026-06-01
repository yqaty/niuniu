"""
图像识别模块：从游戏截图中识别棋盘大小和颜色区域分布。

流程:
  1. 定位棋盘正方形区域（跳过 UI 元素）
  2. 检测灰色网格线，确定 N
  3. 采样每个格子中心颜色
  4. KMeans 聚类为 N 种颜色，输出颜色矩阵
"""

import numpy as np
from PIL import Image
from sklearn.cluster import KMeans
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class BoardInfo:
    """棋盘识别结果"""
    n: int                          # 棋盘大小 N×N
    grid: List[List[int]]           # N×N 颜色标签矩阵 (0 ~ N-1)
    board_rect: Tuple[int, int, int, int]  # (x1, y1, x2, y2) 棋盘在原图中的位置
    cell_centers: List[List[Tuple[int, int]]]  # N×N 每个格子中心在原图中的坐标
    grid_y: List[int]               # 水平网格线在棋盘内的 y 坐标
    grid_x: List[int]               # 垂直网格线在棋盘内的 x 坐标


def recognize(img: Image.Image) -> BoardInfo:
    """
    从游戏截图中识别棋盘。

    Args:
        img: PIL Image 对象

    Returns:
        BoardInfo 包含棋盘大小、颜色矩阵和坐标信息

    Raises:
        ValueError: 无法识别棋盘
    """
    arr = np.array(img.convert("RGB"))
    h, w, _ = arr.shape

    saturation = _saturation(arr)

    # Step 1: 定位棋盘区域
    board_y_start, board_y_end = _find_board_y(arr, saturation, w, h)
    board_x_start, board_x_end = _find_board_x(saturation, board_y_start, board_y_end, w)

    board = arr[board_y_start:board_y_end, board_x_start:board_x_end, :]
    board_sat = saturation[board_y_start:board_y_end, board_x_start:board_x_end]
    bh, bw = board.shape[:2]

    # Step 2: 检测网格线
    grid_y = _find_grid_lines(np.mean(board_sat, axis=1), bh)
    grid_x = _find_grid_lines(np.mean(board_sat, axis=0), bw)

    n_rows = len(grid_y) - 1
    n_cols = len(grid_x) - 1

    if n_rows != n_cols:
        raise ValueError(
            f"检测到的行数({n_rows})和列数({n_cols})不一致，无法识别棋盘"
        )
    if n_rows < 3:
        raise ValueError(f"检测到的棋盘太小: {n_rows}x{n_cols}")

    n = n_rows

    # Step 3: 采样格子中心颜色
    raw_colors = []
    cell_centers = []
    for r in range(n):
        row_centers = []
        cy = (grid_y[r] + grid_y[r + 1]) // 2
        for c in range(n):
            cx = (grid_x[c] + grid_x[c + 1]) // 2
            # 取中心 11x11 区域平均色
            y1 = max(0, cy - 5)
            y2 = min(bh, cy + 6)
            x1 = max(0, cx - 5)
            x2 = min(bw, cx + 6)
            region = board[y1:y2, x1:x2, :]
            avg_color = np.mean(region.reshape(-1, 3), axis=0)
            raw_colors.append(avg_color)
            # 格子中心在原图中的坐标
            row_centers.append((board_x_start + cx, board_y_start + cy))
        cell_centers.append(row_centers)

    # Step 4: KMeans 聚类
    raw_colors = np.array(raw_colors)
    kmeans = KMeans(n_clusters=n, random_state=42, n_init=10)
    labels = kmeans.fit_predict(raw_colors)
    grid = labels.reshape(n, n).tolist()

    # 验证: 每种颜色应该恰好出现合理的次数（至少1次）
    for label in range(n):
        count = sum(row.count(label) for row in grid)
        if count == 0:
            raise ValueError(f"颜色 {label} 没有出现在任何格子中")

    return BoardInfo(
        n=n,
        grid=grid,
        board_rect=(board_x_start, board_y_start, board_x_end, board_y_end),
        cell_centers=cell_centers,
        grid_y=[y + board_y_start for y in grid_y],
        grid_x=[x + board_x_start for x in grid_x],
    )


def _saturation(arr: np.ndarray) -> np.ndarray:
    """计算每个像素的饱和度 (max(RGB) - min(RGB))"""
    return np.max(arr, axis=2).astype(int) - np.min(arr, axis=2).astype(int)


def _find_board_y(
    arr: np.ndarray, saturation: np.ndarray, w: int, h: int
) -> Tuple[int, int]:
    """
    找到棋盘的垂直范围。

    策略: 找最大的连续非白色行块（允许小间隙跨过 grid line）。
    """
    # 判断每行是否为"白色"（中间区域亮度>250 且 饱和度<5）
    quarter = w // 4
    three_quarter = 3 * w // 4
    row_brightness = np.mean(arr[:, quarter:three_quarter, :], axis=(1, 2))
    row_sat = np.mean(saturation[:, quarter:three_quarter], axis=1)
    is_white = (row_brightness > 250) & (row_sat < 5)

    # 找连续非白色块，允许最多 15px 的白色间隙
    best_start, best_end, best_len = 0, 0, 0
    in_block = False
    start = 0
    gap = 0
    max_gap = 15

    for y in range(h):
        if not is_white[y]:
            if not in_block:
                start = y
                in_block = True
            gap = 0
        else:
            if in_block:
                gap += 1
                if gap > max_gap:
                    end = y - gap
                    length = end - start
                    if length > best_len:
                        best_start, best_end, best_len = start, end, length
                    in_block = False

    if in_block:
        end = h
        length = end - start
        if length > best_len:
            best_start, best_end = start, end

    if best_end - best_start < 100:
        raise ValueError("无法定位棋盘区域 (垂直方向)")

    return best_start, best_end


def _find_board_x(
    saturation: np.ndarray, y_start: int, y_end: int, w: int
) -> Tuple[int, int]:
    """找到棋盘的水平范围"""
    board_sat = saturation[y_start:y_end, :]
    col_max_sat = np.max(board_sat, axis=0)
    colored_cols = np.where(col_max_sat > 20)[0]

    if len(colored_cols) == 0:
        raise ValueError("无法定位棋盘区域 (水平方向)")

    return int(colored_cols[0]), int(colored_cols[-1]) + 1


def _find_grid_lines(avg_saturation: np.ndarray, length: int) -> List[int]:
    """
    在一维饱和度序列中检测网格线位置。

    网格线是饱和度极低的连续区域。
    首尾添加虚拟边界线。
    """
    threshold = 15
    mask = avg_saturation < threshold

    # 分组连续的低饱和度位置
    groups = []
    current: List[int] = []
    for i in range(length):
        if mask[i]:
            current.append(i)
        else:
            if current:
                groups.append(current)
                current = []
    if current:
        groups.append(current)

    centers = [int(np.mean(g)) for g in groups]

    # 在首尾添加虚拟边界（如果边缘没有检测到 grid line）
    if not centers or centers[0] > 20:
        centers.insert(0, 0)
    if not centers or centers[-1] < length - 20:
        centers.append(length - 1)

    return centers
