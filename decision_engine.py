class DecisionEngine:
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator

    def make_decision(self, lead_data):
        # 进行决策
        action = self.orchestrator.analyze_leads(lead_data)
        if action:
            fix_plan = self.orchestrator.generate_fix_plan(action)
            self.orchestrator.commit_changes("Codex optimization: improved lead scoring")
            return fix_plan
        return None
