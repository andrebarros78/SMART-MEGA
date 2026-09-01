from pathlib import Path
p=Path(__file__).resolve().parents[1]/'smart_signal_agent.py'
s=p.read_text(encoding='utf-8-sig')
s=s.replace('self.expert_learning_guard = BoundedOnlineLearningGuard(eta=self.eta)','self.expert_learning_guard = BoundedOnlineLearningGuard(eta=self.eta, prior_observations=self.start)')
s=s.replace('self.family_learning_guard = BoundedOnlineLearningGuard(eta=self.eta)','self.family_learning_guard = BoundedOnlineLearningGuard(eta=self.eta, prior_observations=self.start)')
p.write_text(s,encoding='utf-8')
print('P10 maturity applied')
