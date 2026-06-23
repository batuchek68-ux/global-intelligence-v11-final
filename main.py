from github import Github
from orchestrator import Orchestrator
from decision_engine import DecisionEngine

# 使用你的 GitHub 访问令牌
github_token = "你的生成的访问令牌"  # 替换为你的访问令牌
github_client = Github(github_token)

# 创建 Orchestrator 和 DecisionEngine 实例
orchestrator = Orchestrator(github_client)
decision_engine = DecisionEngine(orchestrator)

# 示例潜在客户数据
lead_data = {
    'conversion_rate': 0.15,  # 示例转化率
    'lead_count': 100          # 示例潜在客户数量
}

# 进行决策
fix_plan = decision_engine.make_decision(lead_data)

if fix_plan:
    print("生成的修复方案:", fix_plan)
else:
    print("没有需要优化的内容。")
