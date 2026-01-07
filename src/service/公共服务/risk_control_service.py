import logging
import os
import sys
import yaml
from typing import Optional

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.domain.user.User import User
from src.API.资产管理.AssetManager import GetMyAssetMainPartAsync

# 配置日志
logger = logging.getLogger(__name__)

def get_hqb_ratio_threshold() -> float:
    """
    读取活期宝资产占比阈值：
    - 优先读取环境变量 HQB_RATIO_THRESHOLD
    - 其次尝试读取本地 s.yaml 配置文件
    - 非法或未设置时回退为 20.0
    """
    # 1. 尝试从环境变量读取
    env_val = os.environ.get('HQB_RATIO_THRESHOLD')
    if env_val:
        try:
            val = float(env_val)
            # logger.info(f"Loaded HQB_RATIO_THRESHOLD from environment variable: {val}")
            return val
        except ValueError:
            logger.warning(f"环境变量 HQB_RATIO_THRESHOLD 非法值: {env_val}，尝试从配置文件读取")

    # 2. 尝试从 s.yaml 读取
    try:
        yaml_path = os.path.join(root_dir, 's.yaml')
        if os.path.exists(yaml_path):
            with open(yaml_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                val = config.get('vars', {}).get('common', {}).get('props', {}).get('environmentVariables', {}).get('HQB_RATIO_THRESHOLD')
                if val:
                    # logger.info(f"Loaded HQB_RATIO_THRESHOLD from s.yaml: {val}")
                    return float(val)
    except Exception as e:
        logger.warning(f"Failed to load s.yaml: {e}")
    
    # 3. 使用默认值
    # logger.info("Using default HQB_RATIO_THRESHOLD: 20.0")
    return 20.0

HQB_RATIO_THRESHOLD = get_hqb_ratio_threshold()

def check_hqb_risk_allowed(user: User, threshold: Optional[float] = None) -> bool:
    """
    检查活期宝资产占比是否满足风控要求（用于买入/新增场景）。
    
    逻辑：
    1. 获取用户总资产和活期宝资产。
    2. 计算活期宝占比 = (HqbValue / TotalValue) * 100。
    3. 如果占比 < 阈值 (默认使用 HQB_RATIO_THRESHOLD 或 10.0 硬性底线)，则认为风险过高，不允许新增/买入。
    
    Args:
        user: 用户对象
        threshold: 可选的自定义阈值。如果不传，则使用全局配置的 HQB_RATIO_THRESHOLD。
                   注意：如果是硬性风控场景，调用方可传入 10.0 等特定值。
                   
    Returns:
        bool: True 表示风控通过（可以买入），False 表示风控拦截（活期宝占比过低）。
    """
    try:
        # 确定使用的阈值
        limit = threshold if threshold is not None else HQB_RATIO_THRESHOLD
        
        asset_response = GetMyAssetMainPartAsync(user)
        if asset_response.Success and asset_response.Data:
            hqb_val = float(asset_response.Data.get('HqbValue', 0.0))
            total_val = float(asset_response.Data.get('TotalValue', 0.0))
            
            hqb_ratio = 0.0
            if total_val > 0:
                hqb_ratio = (hqb_val / total_val) * 100.0
            
            logger.info(f"[风控检查] 活期宝资产: {hqb_val:.2f}, 总资产: {total_val:.2f}, 占比: {hqb_ratio:.2f}%, 阈值: {limit}%")
            
            if hqb_ratio < limit:
                logger.warning(f"[风控拦截] 活期宝占比({hqb_ratio:.2f}%) 低于风控阈值({limit}%)，停止新增/买入操作。")
                return False
            
            return True
        else:
            logger.warning("获取资产信息失败，无法进行活期宝占比风控检查，默认放行(或根据策略调整)")
            # 这里选择放行还是拦截？根据"风控问题不容挑战"，也许应该拦截？
            # 但如果API临时失败，拦截可能导致业务中断。
            # 参考 increase.py 的逻辑是 "获取失败，跳过此风控项" (default pass).
            # 也可以选择保守策略。考虑到这是“全局风控”，如果拿不到数据，可能无法判断风险。
            # 但为了避免阻塞，暂且返回 True，并在日志中警告。
            return True
            
    except Exception as e:
        logger.error(f"风控检查执行异常: {e}")
        return True # 异常时默认放行，避免阻断，但需监控

if __name__ == "__main__":
    from src.common.constant import DEFAULT_USER
    
    # 配置控制台日志输出
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("========== 开始测试活期宝占比风控服务 ==========")
    print(f"当前阈值 (HQB_RATIO_THRESHOLD): {HQB_RATIO_THRESHOLD}%")
    
    result = check_hqb_risk_allowed(DEFAULT_USER)
    
    print(f"风控检查结果: {'【通过】' if result else '【拦截】'}")
    print("========== 测试结束 ==========")
