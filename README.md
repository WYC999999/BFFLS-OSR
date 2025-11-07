# 原理
## 一、基础原理：圆的参数
设圆的圆心为 $(x_0, y_0)$，半径为 $r$。任意点 $(x, y)$在圆内的条件是：  
$\sqrt{(x - x_0)^2 + (y - y_0)^2} \leq r$
## 二、均匀随机放置的方法
### 方法1：极坐标转换法（推荐，均匀性更好）
直接在直角坐标系中随机生成 $(x, y)$ 可能导致圆心附近点更密集（因为相同面积下，圆心附近的极坐标角度范围更大）。
1. **随机生成极径 \(ρ\)**：  
   若直接在 $[0, r]$ 内均匀取 \(ρ\)，仍会导致圆心附近点过密。正确做法是对半径进行**平方根采样**：  
   $ρ = r \times \sqrt{random(0, 1)}$
   （原理：圆的面积与半径平方成正比，平方根采样可保证面积上的均匀分布）
2. **随机生成极角 \(θ\)**：  
   在 $[0, 2π)$ 内均匀取角度：  
   $θ = 2π \times random(0, 1)$
3. **转换为直角坐标**：  
   $x = x_0 + ρ \times \cosθ \\
   y = y_0 + ρ \times \sinθ$
### 方法2：拒绝采样法（简单直观，效率略低）
1. 在圆的外切正方形内随机生成点 \((x, y)\)：  
   正方形范围为 $x \in [x_0 - r, x_0 + r]$ $y \in [y_0 - r, y_0 + r]$
2. 检查点是否在圆内：  
   若 $(x - x_0)^2 + (y - y_0)^2 \leq r^2$，则保留该点；否则重新生成，直到符合条件。
   （优点：实现简单；缺点：平均有 $1 - π/4 ≈ 21.5\%$ 的点会被拒绝，效率略低）
# 实践
   > [!NOTE]
> 坚持实践是检验真理的唯一标准,就是坚持马克思主义,坚持辨证唯物主义。————《毛泽东选集》

## 一、模型假设
1. **盛放区域**：宫保鸡丁放在一个圆形盘子里，圆心为 $(x_0, y_0)$（例如盘子中心坐标），半径为 $R$（盘子半径，单位可设为厘米）。
2. **花生摆放规则**：花生随机、均匀分布在圆形区域内（不超出盘子边界），每个花生的位置用中心点坐标表示。
3. **极坐标转换法**：通过极径和极角计算花生的直角坐标，确保分布均匀（避免中心过密）。
## 二、数学计算步骤
### 1. 定义基础参数
- 盘子圆心： $(x_0, y_0)$（例如取坐标原点 $(0, 0)$ 简化计算）
- 盘子半径： $R$（例如 $R = 10\ \text{cm}$，根据实际盘子大小调整）
- 需摆放的花生数量： $n$（例如 $n = 8$ 颗）
### 2. 随机生成极坐标参数
对每颗花生，生成独立的极径 $\rho$ 和极角 $\theta$：
- **极角 $\theta$**：在 $[0, 2\pi)$ 范围内均匀随机取值（确保角度方向均匀）：  
  $\theta = 2\pi \cdot \text{rand}(0, 1)$
  其中 $\text{rand}(0, 1)$ 是区间 $[0, 1)$ 内的均匀随机数。
- **极径 $\rho$**：为避免花生在中心聚集，需按“面积均匀”原则采样（极径与半径平方成正比）：  
  $\rho = R \cdot \sqrt{\text{rand}(0, 1)}$
  （原理：圆的面积 $S = \pi \rho^2$，通过平方根转换，确保随机点在单位面积内的分布概率相等）
### 3. 转换为直角坐标（花生位置）
通过极坐标 $(\rho, \theta)$ 计算花生在直角坐标系中的位置 $(x, y)$：   
$`
\begin{cases} 
x = x_0 + \rho \cdot \cos\theta \\
y = y_0 + \rho \cdot \sin\theta 
\end{cases}
`$
## 三、示例计算（以具体数值演示）
假设：
- 盘子圆心 $(x_0, y_0) = (0, 0)$，半径 $R = 10\ \text{cm}$
- 生成 1 颗花生的位置，随机数取 $\text{rand}(0, 1) = 0.36$（极角用）和 $\text{rand}(0, 1) = 0.64$（极径用）
计算过程：
1. 极角： $\theta = 2\pi \times 0.36 \approx 2.2619\ \text{弧度}$（约 $129.6^\circ$）
2. 极径： $\rho = 10 \times \sqrt{0.64} = 10 \times 0.8 = 8\ \text{cm}$
3. 直角坐标：  
   $`
   x = 0 + 8 \times \cos(2.2619) \approx 8 \times (-0.6) = -4.8\ \text{cm} \\
   y = 0 + 8 \times \sin(2.2619) \approx 8 \times 0.8 = 6.4\ \text{cm}
   `$  
   即这颗花生的位置为 $(-4.8, 6.4)\ \text{cm}$。
## 四、批量计算逻辑
对 $n$ 颗花生，重复步骤 2~3 即可，每颗花生使用独立的随机数，最终得到 $n$ 个坐标 $(x_1,y_1), (x_2,y_2), ..., (x_n,y_n)$，均落在半径为 $R$ 的圆内，且分布均匀。
## 五、代码演示
```ruby
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
```
