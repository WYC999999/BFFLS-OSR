import math
import random
import matplotlib.pyplot as plt

def calculate_peanut_positions(center_x=0, center_y=0, radius=10, num_peanuts=8):
    """
    计算宫保鸡丁圆形区域内花生的随机摆放位置（极坐标转换法）
    
    参数:
        center_x (float): 圆形区域的圆心x坐标（默认原点）
        center_y (float): 圆形区域的圆心y坐标（默认原点）
        radius (float): 圆形区域的半径（默认10单位）
        num_peanuts (int): 花生数量（默认8颗）
    
    返回:
        list: 花生位置的坐标列表，每个元素为(x, y)元组
    """
    peanut_positions = []
    
    for _ in range(num_peanuts):
        # 1. 生成极角θ（弧度制，范围[0, 2π)）
        theta = 2 * math.pi * random.random()
        
        # 2. 生成极径ρ（确保均匀分布，使用平方根采样）
        # 原理：圆面积与半径平方成正比，sqrt(random)确保面积上的均匀性
        rho = radius * math.sqrt(random.random())
        
        # 3. 极坐标转直角坐标（相对于圆心）
        x = center_x + rho * math.cos(theta)
        y = center_y + rho * math.sin(theta)
        
        peanut_positions.append((round(x, 2), round(y, 2)))  # 保留2位小数
    
    return peanut_positions

def visualize_peanuts(peanut_positions, center_x=0, center_y=0, radius=10):
    """可视化花生摆放位置和圆形区域"""
    # 创建画布
    plt.figure(figsize=(8, 8))
    
    # 绘制圆形区域（宫保鸡丁盛放范围）
    circle = plt.Circle((center_x, center_y), radius, fill=False, color='orange', label='盘子边界')
    plt.gca().add_patch(circle)
    
    # 绘制花生位置
    x_coords = [pos[0] for pos in peanut_positions]
    y_coords = [pos[1] for pos in peanut_positions]
    plt.scatter(x_coords, y_coords, color='brown', s=50, label='花生')
    
    # 标记圆心
    plt.scatter(center_x, center_y, color='red', marker='+', s=100, label='圆心')
    
    # 设置坐标轴和标题
    plt.xlim(center_x - radius - 1, center_x + radius + 1)
    plt.ylim(center_y - radius - 1, center_y + radius + 1)
    plt.axis('equal')  # 等比例显示，避免圆形被拉伸
    plt.grid(linestyle='--', alpha=0.7)
    plt.title('宫保鸡丁上花生的随机摆放位置（极坐标转换法）')
    plt.legend()
    plt.show()

if __name__ == "__main__":
    # 配置参数（可根据实际调整）
    plate_center = (5, 5)  # 盘子圆心坐标
    plate_radius = 12      # 盘子半径
    peanut_count = 10      # 花生数量
    
    # 计算花生位置
    peanuts = calculate_peanut_positions(
        center_x=plate_center[0],
        center_y=plate_center[1],
        radius=plate_radius,
        num_peanuts=peanut_count
    )
    
    # 打印结果
    print(f"在圆心({plate_center[0]}, {plate_center[1]})、半径{plate_radius}的区域内，{peanut_count}颗花生的位置：")
    for i, (x, y) in enumerate(peanuts, 1):
        print(f"花生{i}: ({x}, {y})")
    
    # 可视化
    visualize_peanuts(peanuts, plate_center[0], plate_center[1], plate_radius)
