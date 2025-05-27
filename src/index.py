import logging
from src.common.constant import DEFAULT_USER
    
# 配置日志
logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
def handler(event, context):
     print("src-----------------------------------")
     print("event:{}".format(event))
     print("context:{}".format(context))
     print(f"DEFAULT_USER:{DEFAULT_USER}")

if __name__ == "__main__":
    handler(None,None)
  