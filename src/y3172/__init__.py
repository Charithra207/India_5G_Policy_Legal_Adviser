"""
ITU-T Y.3172 layer: an ML pipeline over the simulated 5G core, with the
policy and legal adviser as its policy (P) node.
================================================================================
    python run.py --intent intents/amf_signalling_storm.yaml

    intent.py        ML Intent (Y.3172 cl. 7.4, 8.1 NOTE 12) — declarative spec, validated on load
    nodes.py         SRC, C (collector) and PP (preprocessor) nodes
    models.py        M node — candidate ML models (train / evaluate / predict)
    policy_node.py   P node — legal and policy checks on the model output (advisory or blocking)
    distributor.py   D node and the SINKs it routes to (remediation, notices, evidence, escalation)
    notices.py       Draft regulatory notices with deadlines, each deadline phrase verified in its source
    mlfo.py          MLFO — instantiates the pipeline from the intent, trains and selects models in
                     the ML sandbox, deploys to the live (simulated) network, monitors and reselects

The "network" is the contained simulator in sim/; nothing here reaches a
real system.  Decision support for a training lab, not legal advice.
"""
