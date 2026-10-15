# Mint Town help

| Need | Read |
|---|---|
| Run the app and protect costs | [Operations](operations.md) |
| Open the public demo and understand team access | [Hosting and shutdown guard](hosting.md) |
| Present the saved cases in three minutes | [Demo script](demo-script.md) |
| Inspect/export data matching Gab’s dictionary | [Simulation data contract](environment-data.md) |
| Follow environment → BigQuery → investigation | [Architecture](architecture.md) |
| Review simulation, data plane and agent plane | [Mesh architecture and UML figures](fraud-agent-mesh.md) |
| Review the agent harness and teammate model contract | [Research-backed harness design](agent-harness-design.md) |
| Add a tool or another agent | [Agent extension guide](agents.md) |
| Curate cases and compare model experiments | [Risk scientist and validator](risk-lab.md) |
| Understand the evidence and research proposals | [Research](research.md) |
| See what actually passed, failed or remains unmeasured | [Evaluation](evaluation.md) |
| Review the implemented competition upgrades and current results | [Upgrade evidence](competition-upgrades.md) |
| Contribute Karlo's trained model | [Model artifact contract](model-artifacts.md) |
| Find a backend file or endpoint | [Application map](../web/README.md) |

Start with one complete case. A normal demo follows **Run world → complaint → selected tools → analyst review → approved knowledge → later payment hold**. A stopped investigation is a visible result, not a reason to silently retry it.

Mint Town is the product name. Existing Google project, bucket, dataset and environment-variable names retain `minttown` so the rename does not duplicate resources or reset accounting.

- [Investigation harness](harness-runtime.md): implemented roles, judges, model receipts, checkpoints, knowledge lifecycle and offline evaluation.
