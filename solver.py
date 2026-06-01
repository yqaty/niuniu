"""
求解模块：使用 OR-Tools CP-SAT 约束编程求解 Queens 问题。

约束:
  1. 每行恰好一头牛（决策变量 queens[i] 表示第 i 行牛所在列）
  2. 每列恰好一头牛（AllDifferent）
  3. 相邻行的牛列距离 >= 2（八邻域无牛）
  4. 每种颜色区域恰好一头牛
"""

from ortools.sat.python import cp_model
from typing import List, Optional


def solve(n: int, grid: List[List[int]]) -> Optional[List[int]]:
    """
    求解 Queens 棋盘问题。

    Args:
        n: 棋盘大小 N×N
        grid: N×N 颜色标签矩阵，grid[r][c] ∈ [0, N-1]

    Returns:
        长度为 N 的列表，queens[i] 表示第 i 行牛放在第几列。
        无解返回 None。
    """
    model = cp_model.CpModel()

    # 决策变量: 每行牛放在哪一列
    queens = [model.new_int_var(0, n - 1, f"q_{i}") for i in range(n)]

    # 约束 1: 每列恰好一头牛
    model.add_all_different(queens)

    # 约束 2: 相邻行的牛列距离 >= 2（八邻域约束）
    for i in range(n - 1):
        diff = model.new_int_var(-n, n, f"diff_{i}")
        model.add(diff == queens[i] - queens[i + 1])
        abs_diff = model.new_int_var(0, n, f"abs_{i}")
        model.add_abs_equality(abs_diff, diff)
        model.add(abs_diff >= 2)

    # 约束 3: 每种颜色区域恰好一头牛
    # 预处理：每种颜色包含哪些 (row, col)
    color_cells: dict[int, list[tuple[int, int]]] = {}
    for r in range(n):
        for c in range(n):
            color = grid[r][c]
            color_cells.setdefault(color, []).append((r, c))

    for color, cells in color_cells.items():
        # 对该颜色的每个格子，创建布尔变量 "牛是否在这个格子"
        bools = []
        for r, c in cells:
            b = model.new_bool_var(f"cell_{r}_{c}")
            model.add(queens[r] == c).only_enforce_if(b)
            model.add(queens[r] != c).only_enforce_if(~b)
            bools.append(b)
        # 恰好一个为 True
        model.add(sum(bools) == 1)

    # 求解
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30.0
    status = solver.solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return [solver.value(queens[i]) for i in range(n)]

    return None
