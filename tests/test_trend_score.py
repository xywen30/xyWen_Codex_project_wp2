import json

def test_weights_sum_one():
    p=__import__("pathlib").Path(__file__).resolve().parents[1]/"config"/"trend_weights.json"
    assert abs(sum(json.loads(p.read_text())[k] for k in json.loads(p.read_text()))-1)<1e-9
